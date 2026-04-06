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
    Executes a registered WorkAction on a remote server via gRPC.
    Requires a target_action_name to execute a pre-registered action on the server.
    """
    def __init__(self, name, target_action_name=None, server_address=None, input_files=None, output_patterns=None):
        """
        Args:
            name (str): Name of this action.
            target_action_name (str, optional): Name of a pre-registered action on the server.
            server_address (str): 'host:port' of the remote server.
            input_files (list): List of file paths (local) to send to the remote.
            output_patterns (list): List of glob patterns for files to retrieve from remote.
        """
        super().__init__(name)
        self.target_action_name = target_action_name
        self.server_address = server_address
        self.input_files = input_files or []
        self.output_patterns = output_patterns or []
        self.description = f'Remote action executing {target_action_name} on {server_address}'

    def available_actions(self):
        """
        Queries the remote server for available registered actions.
        
        Returns:
            dict: A dictionary mapping action names to their descriptions.
        """
        try:
            with grpc.insecure_channel(self.server_address, options=OPTIONS) as channel:
                stub = remote_actions_pb2_grpc.SimFlowRemoteStub(channel)
                resp = stub.GetAvailableActions(remote_actions_pb2.Empty())
                return {a.name: a.description for a in resp.actions}
        except grpc.RpcError as e:
            logger.error(f"Error querying available actions: {e}")
            raise

    def solve(self, val_dict=None):
        if not self.target_action_name:
            raise ValueError("target_action_name must be provided to execute a remote action.")

        # 1. Prepare Request
        req = remote_actions_pb2.ActionRequest()
        
        req.action_name = self.target_action_name
        req.target_action_name = self.target_action_name
        
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
    def __init__(self, actions_registry=None):
        self.actions_registry = actions_registry or {}

    def GetAvailableActions(self, request, context):
        resp = remote_actions_pb2.AvailableActionsResponse()
        for name, info in self.actions_registry.items():
            action_info = resp.actions.add()
            action_info.name = name
            action_info.description = info.get('description', '')
        return resp

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
            
            # 2. Resolve action
            if request.target_action_name:
                if request.target_action_name in self.actions_registry:
                    action = self.actions_registry[request.target_action_name]['graph']
                else:
                    resp.success = False
                    resp.error_message = f"Action '{request.target_action_name}' not found on server."
                    return resp
            else:
                resp.success = False
                resp.error_message = "target_action_name not provided."
                return resp
            
            val_dict = pickle.loads(request.pickled_val_dict)
            
            # 3. Execute
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
    Can be configured with pre-registered actions (graphs).
    """
    def __init__(self, port=50051, max_workers=10):
        self.port = port
        self.max_workers = max_workers
        self.server = None
        self.actions_registry = {}

    def add_graph(self, name, graph, description=""):
        """
        Registers a graph (WorkAction) with a name and description.
        """
        self.actions_registry[name] = {'graph': graph, 'description': description}

    def start(self):
        self.server = grpc.server(
            futures.ThreadPoolExecutor(max_workers=self.max_workers),
            options=OPTIONS
        )
        remote_actions_pb2_grpc.add_SimFlowRemoteServicer_to_server(
            SimFlowService(self.actions_registry), 
            self.server
        )
        self.server.add_insecure_port(f'[::]:{self.port}')
        logger.info(f"Server starting on port {self.port}...")
        self.server.start()
        
    def wait_for_termination(self):
        if self.server:
            self.server.wait_for_termination()
            
    def stop(self):
        if self.server:
            self.server.stop(0)

class NamedServerAction(ServerAction):
    """
    Alias for ServerAction supporting named graphs.
    """
    pass