

# Results directory structure 

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




