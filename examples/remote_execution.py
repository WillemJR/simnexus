import sys
import os
import time
import threading
import logging

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from simflow.actions import WorkAction
from simflow.remote_actions import RemoteAction, ServerAction

logging.basicConfig(level=logging.INFO)

# 1. Define a simple action to run remotely
class MyRemoteTask(WorkAction):
    def eval(self, val_dict=None):
        print(f"  [Remote] Executing MyRemoteTask with inputs: {val_dict}")
        
        # Perform computation
        a = val_dict.get('a', 0)
        b = val_dict.get('b', 0)
        result = a + b
        
        # Create a file
        with open('result.txt', 'w') as f:
            f.write(f"The result of {a} + {b} is {result}\n")
            
        return result

# 2. Server setup
def run_server():
    server = ServerAction(port=50051)
    server.start()
    try:
        # Keep running
        server.wait_for_termination()
    except KeyboardInterrupt:
        server.stop()

if __name__ == "__main__":
    # Start server in a separate thread for this demo
    # In real usage, this would be on a different machine
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    
    # Give server a moment to start
    time.sleep(1)
    
    # 3. Client setup
    print("\n--- Starting Client ---")
    
    # Define the task to be run remotely
    task = MyRemoteTask("adder")
    
    # Create the RemoteAction wrapper
    # We want to retrieve 'result.txt'
    remote_task = RemoteAction(
        name="remote_adder",
        target_action=task,
        server_address='localhost:50051',
        input_files=[], # No input files for this demo
        output_patterns=['result.txt', ] 
    )
    
    # Data context
    data = {'a': 10, 'b': 32}
    
    # 4. Execute
    try:
        print(f"Sending task to remote... Data: {data}")
        result = remote_task.eval(data)
        print(f"Received Result: {result}")
        
        # Verify file reception
        if os.path.exists('result.txt'):
            with open('result.txt', 'r') as f:
                content = f.read()
            print(f"Received File Content: {content.strip()}")
            os.remove('result.txt') # Cleanup
        else:
            print("Error: result.txt was not received!")
            
    except Exception as e:
        print(f"Execution failed: {e}")
        
    print("--- Done ---")
