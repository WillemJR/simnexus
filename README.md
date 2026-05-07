
# SimNexus

A Python module for orchestrating complex simulations 
with native support for LS-DYNA, OpenRadioss, and OpenFOAM.

## Overview

SimNexus enables the automation and coordination of
multi-physics simulation workflows.
The module is particularly suited for simulations that span multiple domains, such as combined structural and fluid dynamics analyses.

It supports tasks from from input preparation and
remote execution to results extraction and post-processing.


SimNexus has a native support for
solvers like LS-DYNA, OpenRadioss, and OpenFOAM. 

## Key Features

- **Workflow Management**: Define simulation workflows as directed acyclic graphs (DAGs) where actions are executed based on dependency relationships and completion status of prerequisite tasks
- **Native Solver Support**: Specify input parameter values and the results to extract for a supported solver.  Currently implemented are LS-DYNA and OpenRadioss for structural analysis, and OpenFOAM for computational fluid dynamics
- **Remote Execution**: Submit computational subgraphs to remote computing resources while maintaining local workflow coordination
- **Dependency Resolution**: Automatically manages execution order based on inter-action dependencies, ensuring downstream actions wait for required upstream results
- **Discoverability**: Query any graph for its inputs (`variables()`) and outputs (`outputs()`) without running it — solver actions read their parameterised input files to report variable names, types, and default values
- **Scalability using ML**: Designed to scale through integration with the Gemini CLI for the extension and use of the module.

## Typical Workflow

1. Configure input files for target solvers
2. Define analysis actions and their dependencies
3. Execute simulations on designated compute resources (local or remote)
4. Extract relevant results from solver outputs
5. Aggregate and summarize findings 

SimNexus streamlines the complexity of managing heterogeneous simulation environments, enabling researchers and engineers to focus on analysis rather than workflow orchestration.


## Documentation
(Path to be added. One provided is not yet active)

[Online documentation is available here](https://willemjr.github.io/simnexus/)

See also the docs directory.


## Installation

```bash
pip install simnexus
```

## Usage
See the documentation and the examples directory for examples.

(Coming soon)



# Example problems
The example problems demonstrate:

 - An LS-DYNA workflow consisting of editing parameter values, job submission, and results extraction.
 - An OpenRadioss workflow consisting of editing parameter values, job submission, and results extraction.
 - An OpenFOAM. workflow consisting of editing parameter values, job submission, and results extraction.
 - Remote execution examples.


## License
This project is licensed under the MIT License.

