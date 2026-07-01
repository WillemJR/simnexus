# Overview
The 'simnexus' python module is for modelling of complex simulations worklows.
The workflow consists of of actions assembled into a directed graph.
The actions can be varied; e.g. a strutural evaluations, a mathematical operation, or a file edit.
Part of the graph can be performed on remote computers. 
Some actions depends on the outcomes of other actions and workflow delays
the execution of these actions till the required prior actions have completed.



# Project Directory Structure

The project directory and core classes are given below.

```
simnexus/
├── GEMINI.md
├── LICENSE
├── pyproject.toml
├── README.md
├── requirements.txt
├── docs/                   # documentation maintained using sphinx
├── simnexus/                # python code directory
│   ├── GEMINI.md           # implementaion details of the classes
│   ├── __init__.py
│   ├── actions.py          # base class for all actions in the graph
│   ├── args.py             # enums, constaints and named tuples used in input arguments
│   ├── graph_actions.py    # graph containing sequence of actions.
│   ├── dyna_actions.py     # execution of ls-dyna
│   ├── d3plot_actions.py   # read ls-dyna data from a d3plot file
│   ├── jinja_actions.py    # substition of variables in a file with jinja markup
│   ├── radioss_actions.py  #  execution of Radioss and openRadioss
│   ├── openfoam_actions.py #  execution of OpenFOAM
│   ├── remote_actions.py   # remote execution
│   ├── variables.py        # variable definition
│   └── ...
└── tests/                  # unit tests
```



# The Action base class

The `WorkAction` base class (defined in `simnexus/actions.py`) is the base building block for operations in a workflow. It inherits from `Subject` to support the observer pattern, allowing the workflow manager (like `DirectedGraph` or `WorkFlow`) to track execution status.

Key features:
- **`solve(self, val_dict)`**: The abstract method that performs the action's logic. It receives a dictionary `val_dict` containing the current values of variables and results from prior actions. This method returns the data computed by the class.
- **`parameters(self)`**: Returns a set of `Variable` objects that the action requires as inputs. For a `DirectedGraph` or `WorkFlow` the variables of all children are returned (duplicates are eliminated automatically). Solver actions (`DynaAnalysis`, `RadiossAnalysis`, `OpenFOAMAnalysis`, `JinjaReplace`) read their parameterised input file to discover variables; the file must be present in the current working directory. Call `parameters()` on a `WorkArea` or `SimulationIterator` to ensure files are copied first — both copy `copy_paths` into a temporary subdirectory before delegating to the graph.
- **`outputs(self)`**: Returns a `(data_type, description)` tuple describing what the action produces. For a `DirectedGraph` or `WorkFlow` it returns a dictionary `{action_name: (data_type, description)}` covering all child actions. Used to inspect graph outputs without running the graph.
- **`print_tree(self, describe=False)` / `format_tree(...)`**: Prints (or returns) the action graph as an ASCII tree, rooted at any action. Call it on a top-level action (e.g. a `SimulationIterator` or `WorkArea`) to see the whole workflow, including wrappers, graphs and leaf actions. Pass `describe=True` to append each action's description.
- **`print_work_dir(self)` / `format_work_dir(...)`**: Prints (or returns) the *predicted* work-directory structure that running the workflow creates on disk. It is built from the actions' metadata, so it works before anything is run and without the solvers installed. A `SimulationIterator` shows a representative `job_0/` directory (one per design evaluation); a `WorkArea` shows the single directory it reuses; a `DirectedGraph` whose children are wrappers shows each child's subdirectory as a nested subtree. Solver actions (`DynaAnalysis`, `RadiossAnalysis`, `OpenFOAMAnalysis`, `JinjaReplace`) contribute the deck/log/result files they write via a `_produced_files()` hook.
- **`describe_workflow(self, describe=False)`**: Convenience method that prints both the action tree and the work-directory structure together.

Subclasses of `WorkAction` implement specific tasks, such as `MathEvaluation` (performing calculations), or `CurveSimilarity` (comparing simulation results to experimental data).

# Variables 
Actions can accept `Variable` objects as arguments during initialization.

The decorators `@WorkAction.allow_variables_as_arguments` and `@WorkAction.assign_variables_values_to_members` of an action are used to automatically resolve these variables to their numeric values from `val_dict` before `solve` is executed.


# Setting up a workflow
Actions are organized into a `DirectedGraph` or the simpler linear`WorkFlow` to define dependencies and execution order.

Asynchronous Execution: `_observed_eval_async` allows running the action in a separate process, which is useful for parallelizing independent tasks in a `DirectedGraph`.


# Remote execution
The `simnexus.remote_actions` module enables executing of actions on remote compute resources. It consists of the following:
- **`ServerAction` / `NamedServerAction` (Remote)**: A gRPC server that accepts tasks, executes them in isolated temporary directories, and returns results. It supports registering named graphs via `add_graph(name, graph, description)` to enforce a secure registry-based execution model.
- **`RemoteAction` (Client)**: A wrapper that specifies a `target_action_name` to execute a pre-registered action on the server. It retrieves the results and generated files. Discoverability of server-side actions is provided via `available_actions()`.


# Results directory structure for SimulationIterator

The results directory structure is needed to postprocess and display results.

OptimizationResults/
├── opt_hist.json

{NAME}/
├── job_0/             
│   ├── iter_variables.json
│   └── actions_output.pkl
├── job_1/              
│   ├── iter_variables.json
│   └── actions_output.pkl
├── job_{n}/              
│   ├── iter_variables.json
│   └── actions_output.pkl


The {NAME} is a name of a directory that is input to the program, typically the name of the graph.
Inside that directory are the job subdirectories named job_0, job_1, ..., job_{n}.
Inside each subdirectory are files named iter_variables.json and actions_output.pkl.
We want to plot the data in these two files.

The iter_variables.json file store the variables values.
An example of iter_variables.json file:
"""
{"K": 0.2, "T": 75}
"""
The keys of the are strings, and the values are floats or integers.

The actions_output.pkl file store the compute values of named actions.
The actions_output.pkl is a binary file written using the pickle module.
The content of the file is a dictionary. 
and the values can be integers, floats, a numpy float, a list of floats,
a numpy 1D array of floats, or an image stored as an numpy array.
