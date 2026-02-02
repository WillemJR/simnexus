import grpc
import pickle
import os
import shutil
import tempfile
import glob
from concurrent import futures
import logging

from simflow.actions import WorkAction
from simflow.protos import remote_actions_pb2
from simflow.protos import remote_actions_pb2_grpc

# Increase max message size to 50MB
MAX_MESSAGE_LENGTH = 50 * 1024 * 1024
OPTIONS = [
    ('grpc.max_send_message_length', MAX_MESSAGE_LENGTH),
    ('grpc.max_receive_message_length', MAX_MESSAGE_LENGTH),
]

logger = logging.getLogger(__name__)

class RemoteAction(WorkAction):
    """
    Executes a wrapped WorkAction on a remote server via gRPC.
    """
    def __init__(self, name, target_action, server_address, input_files=None, output_patterns=None):
        """
        Args:
            name (str): Name of this action.
            target_action (WorkAction): The action to execute remotely.
            server_address (str): 'host:port' of the remote server.
            input_files (list): List of file paths (local) to send to the remote.
            output_patterns (list): List of glob patterns for files to retrieve from remote.
        """
        super().__init__(name)
        self.target_action = target_action
        self.server_address = server_address
        self.input_files = input_files or []
        self.output_patterns = output_patterns or []

    def solve(self, val_dict=None):
        # 1. Prepare Request
        req = remote_actions_pb2.ActionRequest()
        req.action_name = self.target_action.name
        
        # Security Warning: pickling code/objects is dangerous if the server is untrusted.
        req.pickled_action = pickle.dumps(self.target_action)
        req.pickled_val_dict = pickle.dumps(val_dict)
        if self.output_patterns:
            req.output_patterns.extend(self.output_patterns)

        # Read input files
        for fpath in self.input_files:
            if os.path.exists(fpath):
                with open(fpath, 'rb') as f:
                    content = f.read()
                # Use basename for the remote side
                fname = os.path.basename(fpath)
                req.input_files.append(remote_actions_pb2.File(name=fname, content=content))
            else:
                logger.warning(f"Input file not found: {fpath}")

        # 2. Connect and Send
        try:
            with grpc.insecure_channel(self.server_address, options=OPTIONS) as channel:
                stub = remote_actions_pb2_grpc.SimFlowRemoteStub(channel)
                logger.info(f"Sending action '{self.name}' to {self.server_address}...")
                resp = stub.RunAction(req)
        except grpc.RpcError as e:
            logger.error(f"gRPC error: {e}")
            raise

        # 3. Process Response
        if not resp.success:
            raise RuntimeError(f"Remote action failed: {resp.error_message}")

        # Unpack results
        result = pickle.loads(resp.pickled_results)
        
        # Save output files
        for f_msg in resp.output_files:
            # We save them in the current directory (or we could specify a dir)
            # Assuming current working directory for now as per simflow conventions
            with open(f_msg.name, 'wb') as f:
                f.write(f_msg.content)
            logger.info(f"Received file: {f_msg.name}")

        return result


class SimFlowService(remote_actions_pb2_grpc.SimFlowRemoteServicer):
    def RunAction(self, request, context):
        resp = remote_actions_pb2.ActionResponse()
        tmp_dir = tempfile.mkdtemp(prefix=f"simflow_remote_{request.action_name}_")
        original_cwd = os.getcwd()
        
        try:
            logger.info(f"Received action: {request.action_name}")
            
            # 1. Setup environment
            os.chdir(tmp_dir)
            
            # Write input files
            for f_msg in request.input_files:
                with open(f_msg.name, 'wb') as f:
                    f.write(f_msg.content)
            
            # 2. Unpickle action and arguments
            action = pickle.loads(request.pickled_action)
            val_dict = pickle.loads(request.pickled_val_dict)
            
            # 3. Execute
            # Ensure the action uses the current directory (tmp_dir)
            # Many actions in simflow likely write to CWD.
            
            # We need to make sure the action doesn't crash
            try:
                result = action.solve(val_dict)
                resp.success = True
                resp.pickled_results = pickle.dumps(result)
            except Exception as e:
                import traceback
                traceback.print_exc()
                resp.success = False
                resp.error_message = str(e)
                return resp

            # 4. Collect output files
            found_files = set()
            for pattern in request.output_patterns:
                matches = glob.glob(pattern, recursive=True)
                for match in matches:
                    if os.path.isfile(match):
                        found_files.add(match)

            for fname in found_files:
                # potentially filter out input files if needed, but maybe not necessary
                # limit size?
                if os.path.getsize(fname) > MAX_MESSAGE_LENGTH:
                    logger.warning(f"File {fname} too large to send back via gRPC")
                    continue
                    
                with open(fname, 'rb') as f:
                    content = f.read()
                resp.output_files.append(remote_actions_pb2.File(name=fname, content=content))
                    
        except Exception as e:
            logger.error(f"Server error: {e}")
            resp.success = False
            resp.error_message = f"Server internal error: {str(e)}"
        finally:
            os.chdir(original_cwd)
            shutil.rmtree(tmp_dir)
            
        return resp


class ServerAction:
    """
    Starts a gRPC server to execute actions remotely.
    """
    def __init__(self, port=50051, max_workers=10):
        self.port = port
        self.max_workers = max_workers
        self.server = None

    def start(self):
        self.server = grpc.server(
            futures.ThreadPoolExecutor(max_workers=self.max_workers),
            options=OPTIONS
        )
        remote_actions_pb2_grpc.add_SimFlowRemoteServicer_to_server(SimFlowService(), self.server)
        self.server.add_insecure_port(f'[::]:{self.port}')
        logger.info(f"Server starting on port {self.port}...")
        self.server.start()
        
    def wait_for_termination(self):
        if self.server:
            self.server.wait_for_termination()
            
    def stop(self):
        if self.server:
            self.server.stop(0)
