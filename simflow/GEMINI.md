
# Implementation 

## Remote Execution (gRPC)

The `simflow.remote_actions` module enables executing actions on remote compute resources.

**Architecture:**
- **`ServerAction` / `NamedServerAction` (Remote)**: A gRPC server that accepts tasks, executes them in isolated temporary directories, and returns results. Supports `add_graph(name, graph, description)` for pre-registering workflows.
- **`RemoteAction` (Client)**: A wrapper that serializes a target `WorkAction` or specifies a `target_action_name` to execute a pre-registered graph.

**Protocol:**
- Defined in `simflow/protos/remote_actions.proto`.
- Supports bidirectional file transfer.
- **Security Note**: Relies on `pickle` for serialization. Should only be used within trusted networks.


