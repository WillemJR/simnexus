
# Implementation 

## Remote Execution (gRPC)

The `simnexus.remote_actions` module enables executing actions on remote compute resources.

**Architecture:**
- **`ServerAction` / `NamedServerAction` (Remote)**: A gRPC server that accepts tasks, executes them in isolated temporary directories, and returns results. Supports `add_graph(name, graph, description)` for pre-registering workflows.
- **`RemoteAction` (Client)**: A wrapper that specifies a `target_action_name` to execute a pre-registered graph. Accepts `copy_paths` (list of local files or directories) to upload before execution. Files are sent by basename; directories are walked recursively with their internal structure preserved on the remote side.

**Protocol:**
- Defined in `simnexus/protos/remote_actions.proto`.
- Supports bidirectional file transfer.
- Variable values and results are serialized as restricted JSON (`simnexus/serialization.py`): dict/list/str/int/float/bool/None plus numeric numpy arrays (tagged, base64, dtype whitelisted on decode). Anything else raises `SerializationError`. Tuples decode as lists; numpy scalars decode as Python scalars.
- **Security Note**: Decoding a payload cannot execute code (pickle was replaced for this reason), but the gRPC channel is unencrypted and unauthenticated — use only within trusted networks.


