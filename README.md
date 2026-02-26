
# Simflow

A Python module for orchestrating complex simulations 
with native support for LS-DYNA, Radioss, and OpenFOAM.

## Overview

Simflow enables the automation and coordination of
multi-physics simulation workflows.
The module is particularly suited for simulations that span multiple domains, such as combined structural and fluid dynamics analyses.

It supports tasks from from input preparation and
remote execution to results extraction and post-processing.


Simflow has a native support for
solvers like LS-DYNA, Radioss, and OpenFOAM. 

## Key Features

- **Workflow Management**: Define simulation workflows as directed acyclic graphs (DAGs) where actions are executed based on dependency relationships and completion status of prerequisite tasks
- **Native Multi-Solver Support**: Currently compatible with LS-DYNA and Radioss for structural analysis, and OpenFOAM for computational fluid dynamics
- **Remote Execution**: Submit computational subgraphs to remote computing resources while maintaining local workflow coordination
- **Dependency Resolution**: Automatically manages execution order based on inter-action dependencies, ensuring downstream actions wait for required upstream results
- **Scalability using ML**: Designed to scale through integration with the Gemini CLI for the extension and use of the module.

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

* OpenFOAM should reset parameter file? Create backup?

* Document OpenFOAM 
  - Needs data in VTK and constant/polyMesh/points

* How does Variable interact with solve()?
     * solve( variables=, val_dict=)
     * solve( *args, **kwargs )?
     * SimulationIterator( parameter_list= ) : for default values if not provided in solve
     * solve_dict not val_dict ?

* DONE? WorkArea 
    * SimIter should be subclass of WorkArea?
    * Part of above copy_files = in work_area and simulationIterator and remote

* DONE: variables() method on action returning Variables
 - DONE: Unknown variable

* Extracting DSA from adjointOptimisaFoam

* Documentation
    Several: variables, graph, examples.
    variables() method and return values

* D3Plot clean up
    * argument specifying how results are read. Component names differ
    * Arguments doc and clean up
    * Report BUG: coordinates is initial coordinates for all timesteps,
               node_displacement are coordinates

* similaritymeasures and numpy are requirements.

* Set up remote using grpc
   * Security
   * Advanced? Graph defined on remote.
   * Test in container.

