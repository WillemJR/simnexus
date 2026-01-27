
# Overview
The 'simflow' python module is for modelling of complex simulations worklows.
The workflow consists of of actions assembled into a directed graph.
The actions can be varied; e.g. a strutural evaluations, a mathematical operation, or a file edit.
Part of the graph can be performed on remote computers. 
Some actions depends on the outcomes of other actions and workflow delays
the execution of these actions till the required prior actions have completed.



# Project Directory Structure

The project directory and core classes are given below.

```
simflow/
├── GEMINI.md
├── LICENSE
├── pyproject.toml
├── README.md
├── requirements.txt
├── docs/                   # documentation maintained using sphinx
├── simflow/                # python code directory
│   ├── __init__.py
│   ├── actions.py          # base class for all action in the graph
│   ├── args.py             # enums, constaints and named tuples used in input arguments
│   ├── graph_actions.py    # graph containing sequence of actions.
│   ├── dyna_actions.py
│   ├── d3plot_actions.py   # read data from a d3plot file
│   ├── jinja_action.py
│   ├── radioss_actions.py
│   ├── openfoam_actions.py    
│   ├── remote_actions.py
│   ├── variables.py        # variable definition
│   └── ...
└── tests/                  # unit tests
```



# The Action base class

The `WorkAction` base class (defined in `simflow/actions.py`) is the base building block for operations in a workflow. It inherits from `Subject` to support the observer pattern, allowing the workflow manager (like `DirectedGraph` or `WorkFlow`) to track execution status.

Key features:
- **`eval(self, val_dict)`**: The abstract method that performs the action's logic. It receives a dictionary `val_dict` containing the current values of variables and results from prior actions. This method returns the data computed by the class.

Subclasses of `WorkAction` implement specific tasks, such as `MathEvaluation` (performing calculations), or `CurveSimilarity` (comparing simulation results to experimental data).

# Variables 
Actions can accept `Variable` objects as arguments during initialization.

The decorators `@WorkAction.allow_variables_as_arguments` and `@WorkAction.assign_variables_values_to_members` of an action are used to automatically resolve these variables to their numeric values from `val_dict` before `eval` is executed.


# Setting up a workflow
Actions are organized into a `DirectedGraph` or the simpler linear`WorkFlow` to define dependencies and execution order.

Asynchronous Execution: `_observed_eval_async` allows running the action in a separate process, which is useful for parallelizing independent tasks in a `DirectedGraph`.




# Results directory structure 

The sesults directory structure is needed to postprocess and display results.

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


The {NAME} is a name of a directory that is input to the program.
In side that directory are the job subdirectories named job_0, job_1, ..., job_{n}.
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




