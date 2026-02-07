import sys
import os
import time
import threading
import logging

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from simflow.actions import WorkAction
from simflow.remote_actions import RemoteAction, NamedServerAction

logging.basicConfig(level=logging.INFO)

# 1. Define actions to register on the server
class AdderAction(WorkAction):
    def solve(self, val_dict=None):
        a = val_dict.get('a', 0)
        b = val_dict.get('b', 0)
        return a + b

class MultiplierAction(WorkAction):
    def solve(self, val_dict=None):
        a = val_dict.get('a', 1)
        b = val_dict.get('b', 1)
        return a * b

# 2. Server setup
def run_server():
    server = NamedServerAction(port=50051)
    
    # Register graphs
    server.add_graph("adder", AdderAction("Adder"), "Adds two numbers 'a' and 'b'")
    server.add_graph("multiplier", MultiplierAction("Multiplier"), "Multiplies two numbers 'a' and 'b'")
    
    server.start()
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        server.stop()

if __name__ == "__main__":
    # Start server in a separate thread
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    
    # Give server a moment to start
    time.sleep(1)
    
    # 3. Client setup
    print("\n--- Starting Client ---")
    
    # Create a RemoteAction that points to the server
    # Note: we don't need a target_action here if we query or know the name
    client = RemoteAction(
        name="remote_client",
        server_address='localhost:50051',
        target_action_name="dummy" # Just to satisfy init, will be changed or used
    )
    
    # 4. Query available actions
    print("Querying available actions...")
    available = client.available_actions()
    for name, desc in available.items():
        print(f"  - {name}: {desc}")
    
    # 5. Execute registered actions
    data = {'a': 7, 'b': 6}
    
    for action_name in available.keys():
        print(f"\nExecuting '{action_name}' with data {data}...")
        
        # We can reuse the RemoteAction object by updating target_action_name
        # or create new ones.
        execution_action = RemoteAction(
            name=f"remote_{action_name}",
            target_action_name=action_name,
            server_address='localhost:50051'
        )
        
        result = execution_action.solve(data)
        print(f"Result from {action_name}: {result}")
        
    print("\n--- Done ---")