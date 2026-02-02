Remote Execution
================

Simflow supports executing actions on remote compute resources using gRPC. This allows you to offload heavy computations or specific solver tasks to dedicated servers or containers while orchestrating the workflow locally.

Architecture
------------

The remote execution system consists of two main components:

1.  **Server (`ServerAction`)**: A process running on the remote machine that listens for incoming tasks. It executes each task in an isolated temporary directory.
2.  **Client (`RemoteAction`)**: A special action type in your local workflow that wraps a standard action. It serializes the action and its inputs, sends them to the server, waits for the result, and retrieves any generated files.

.. warning::
    **Security Notice**: The data transfer relies on Python's `pickle` module for maximum flexibility. `pickle` is **not secure** against erroneous or maliciously constructed data. Never unpickle data received from an untrusted or unauthenticated source. This feature should only be used within trusted networks (e.g., internal HPC clusters, VPNs).

Setting up the Server
---------------------

On the remote machine (or container), you need to start the `ServerAction`. This server will listen for incoming gRPC requests.

.. code-block:: python

    from simflow.remote_actions import ServerAction

    # Start the server on port 50051
    server = ServerAction(port=50051)
    
    print("Server is running...")
    server.start()
    
    # Keep the main thread alive
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        server.stop()

Defining Remote Actions
-----------------------

To run an action remotely, you wrap it in a `RemoteAction`.

Arguments:
    - ``name``: The name of the remote action wrapper.
    - ``target_action``: The actual `WorkAction` instance you want to execute remotely.
    - ``server_address``: The address (`host:port`) of the remote server.
    - ``input_files``: A list of local file paths that need to be sent to the remote server.
    - ``output_patterns``: (Optional) A list of file patterns to retrieve (currently, the server attempts to return all created files).

Example
-------

Here is a complete example of defining a task and running it on a local "remote" server.

.. code-block:: python

    import os
    from simflow.actions import WorkAction
    from simflow.remote_actions import RemoteAction

    # 1. Define the task logic
    class AnalysisTask(WorkAction):
        def solve(self, val_dict=None):
            # This code runs on the remote server
            x = val_dict.get('x', 0)
            result = x * 2
            
            # Write a file on the remote server
            with open('output.txt', 'w') as f:
                f.write(f"Result is {result}")
            
            return result

    # 2. Configure the remote wrapper
    task = AnalysisTask("remote_analysis")
    
    remote_task = RemoteAction(
        name="remote_wrapper",
        target_action=task,
        server_address='localhost:50051',  # Address of the running ServerAction
        input_files=['local_config.ini'],  # Files to send
        output_patterns=['output.txt']     # Files to expect back
    )

    # 3. Execute
    # The solve() method will:
    #   - Send 'task' and 'val_dict' to the server
    #   - Send 'local_config.ini'
    #   - Wait for completion
    #   - Return the result (x * 2)
    #   - Download 'output.txt' to the local current directory
    result = remote_task.solve({'x': 21})

Implementation Details
----------------------

- **Isolation**: Each action runs in a unique temporary directory on the server. This prevents file conflicts between concurrent jobs.
- **Dependencies**: The remote environment must have `simflow` and all necessary dependencies installed.
- **File Transfer**: Large files (up to ~50MB) are supported by default. For very large datasets, consider using a shared file system or external storage service, passing only the paths in the `val_dict`.
