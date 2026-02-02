
# Implementation 

## Remote Execution (gRPC)

The `simflow.remote_actions` module enables executing actions on remote compute resources.

**Architecture:**
- **`ServerAction` (Remote)**: A gRPC server that accepts tasks, executes them in isolated temporary directories, and returns results.
- **`RemoteAction` (Client)**: A wrapper that serializes a target `WorkAction` and its inputs (via `pickle`), sends them to the server, and retrieves the results and generated files.

**Protocol:**
- Defined in `simflow/protos/remote_actions.proto`.
- Supports bidirectional file transfer.
- **Security Note**: Relies on `pickle` for serialization. Should only be used within trusted networks.


