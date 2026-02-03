
# Simflow

A Python module for orchestrating complex simulation workflows across multiple solvers and compute environments with native support for LS-DYNA, Radioss, and OpenFOAM.

## Overview

Simflow enables the automation and coordination of
multi-physics simulation workflows — from input preparation and
remote execution to results extraction and post-processing.
The module is particularly suited for simulations that span multiple domains, such as combined structural and fluid dynamics analyses.


Simflow has a native support for
solvers like LS-DYNA, Radioss, and OpenFOAM. 

## Key Features

- **Workflow Management**: Define simulation workflows as directed acyclic graphs (DAGs) where actions are executed based on dependency relationships and completion status of prerequisite tasks
- **Remote Execution**: Submit computational subgraphs to remote computing resources while maintaining local workflow coordination
- **Multi-Solver Support**: Currently compatible with LS-DYNA and Radioss for structural analysis, and OpenFOAM for computational fluid dynamics
- **Dependency Resolution**: Automatically manages execution order based on inter-action dependencies, ensuring downstream actions wait for required upstream results
- **Scalability**: Designed to scale through integration with the Gemini CLI for the extension and use of the module.

## Typical Workflow

1. Configure input files for target solvers
2. Define analysis actions and their dependencies
3. Execute simulations on designated compute resources (local or remote)
4. Extract relevant results from solver outputs
5. Aggregate and summarize findings for review

Simflow streamlines the complexity of managing heterogeneous simulation environments, enabling researchers and engineers to focus on analysis rather than workflow orchestration.



## Installation

```bash
pip install simflow
```

## Usage

(Coming soon)

## Documentation

## License

## Todo

* Documentation
    Several: variables, graph, examples.

* How does FloatVariable interact with eval()?
     SimulationIterator( parameter_list= ) : for default values if not provided in eval

* WorkArea 
    * WorkArea should be argument to WorkFlow / Graph. copy_files?
            self.work_area = WorkArea(self)?
    * SimIter should be subclass of WorkArea?
    * Part of above copy_files = in work_area and simulationIterator and remote

* Simiter 
    * DONE: Write variable values -- right now it is the input to eval

* D3Plot clean up
    * argument specifying how results are read. Component names differ
    * Arguments doc and clean up
    * Report BUG: coordinates is initial coordinates for all timesteps,
               node_displacement are coordinates

* similaritymeasures and numpy are requirements.

* Set up remote using grpc
   * Advanced? Graph defined on remote.

