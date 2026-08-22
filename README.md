
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
- **Discoverability**: Query any graph for its inputs and outputs without running it — solver actions read their parameterised input files to report variable names, types, and default values

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
See also the documentation and the examples directory.

### OpenRadioss
An example for OpenRadioss is given below. The OpenFOAM, LS-DYNA and OpenRadioss workflows follows the same pattern.

```
starter_deck = Path('models/cube_TYPE7_0000.rad')
engine_deck  = Path('models/cube_TYPE7_0001.rad')

# 1. Define RadiossAnalysis to run the simulation
run_rad = RadiossAnalysis( name='rad', 
                  starter_cmd='openradioss_starter',
                  starter_input_path=starter_deck,
                  engine_cmd='openradioss_engine',
                  engine_input_path=engine_deck,
                  create_d3plot=True )

# 2. Create a workflow and add the d3plot extraction actions
wf = WorkFlow( 'Radioss_WorkFlow' )
wf.add_action( run_rad )

d3p = d3plot_File( name='d3plot' )
d3p.NodalValue(name='n5', state=1, nid=5, component= 'node_displacement'  )
wf.add_action( d3p )

wrk_area = WorkArea( wf, copy_paths=[starter_deck,engine_deck] )

# Discover variables defined in input deck and other actions
discovered_vars = wrk_area.parameters()
print("Discovered variables:")
for v in discovered_vars:
        print(f"  {v}")

# 3. Execute the workflow. Provide values for the variables.
val_dict = { 'E': 210000.0, }

print("Starting workflow...")
print(f"Parameters: {val_dict}")
    
ret = wrk_area.solve( val_dict )
print("Available results.", ret.keys() )

```

### OpenFOAM
An example for OpenFOAM is given below. The OpenFOAM, LS-DYNA and OpenRadioss workflows follows the same pattern.

```
import logging
logging.basicConfig(level=logging.WARNING)

from pathlib import Path
from simnexus.args import JobType
from simnexus.graph_actions import WorkFlow, WorkArea
from simnexus.openfoam_actions import OpenFOAMAnalysis
from simnexus.openfoam_actions import OpenFOAM_Field, OpenFOAM_History

def create_openfoam_graph():

    case_dir = Path(__file__).parent.parent / "tests" / "openfoam_exa"
    if not case_dir.exists(): exit(f"Error: {case_dir} does not exist.")

    case_paths = [
        str(case_dir / "system"),
        str(case_dir / "constant"),
        str(case_dir / "0"),
    ]

    wf = WorkFlow('OpenFOAM_WorkFlow')

    wf.add_action( OpenFOAMAnalysis(
        name="my_job",
        job_flag=JobType.CREATE_MESH | JobType.RUN_SIMULATION,
        solve_cmd="icoFoam",
        mesh_cmd="blockMesh" ) )

    wf.add_action(  OpenFOAM_Field(  # Extract field of pressure values
        name='pressure',
        field_variable='p',
        time=0.5 ) )

    wa = WorkArea(wf, copy_paths=case_paths)

    return wa


of_graph = create_openfoam_graph()

# List graph variables and outputs
print("\n\nGraph variables:")
for v in of_graph.parameters():
        print(f" - {v}")

print("\n\nGraph outputs:")
for name, (eval_type, description) in of_graph.outputs().items():
    print(f' - {name}: {eval_type} — {description}')


# Run the job with new parameter values
print("\n\nRunning job.solve({'lidVelocity': 1.2, 'nCells': 6})...")
outcomes = of_graph.solve({"lidVelocity": 1.2, "nCells": 6})

# Print the computed field
print(f"Pressure field:", outcomes['pressure'] )
```

## Example problems
The example problems demonstrate:

 - An LS-DYNA workflow consisting of editing parameter values, job submission, and results extraction.
 - An OpenRadioss workflow consisting of editing parameter values, job submission, and results extraction.
 - An OpenFOAM. workflow consisting of editing parameter values, job submission, and results extraction.
 - Remote execution examples.


## License
This project is licensed under the MIT License.

