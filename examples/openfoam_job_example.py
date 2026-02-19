import os
import shutil
from pathlib import Path
from simflow.args import JobType
import simflow.variables as simvars
from simflow.graph_actions import WorkFlow
from simflow.openfoam_actions import OpenFOAMAnalysis
from simflow.openfoam_actions import OpenFOAM_Field, OpenFOAM_History

def openfoam_example():

    case_dir = Path(__file__).parent.parent / "tests" / "openfoam_exa"
    if not case_dir.exists(): exit(f"Error: {case_dir} does not exist.")

    wf = WorkFlow('OpenFOAM_Extraction')

    job = wf.add_action( OpenFOAMAnalysis(
        name="my_job",
        case_dir=str(case_dir),
        job_flag=JobType.CREATE_MESH | JobType.RUN_SIMULATION,
        solve_cmd="icoFoam",
        mesh_cmd="blockMesh" ) )

    # Discover variables
    discovered_vars = job.variables()
    print("Discovered variables:")
    for v in discovered_vars:
        print(f"  {v}")


    field_ext = OpenFOAM_Field(
        name='temp_field',
        case_dir=case_dir, 
        field_variable='T',
        time=50
    )
    wf.add_action(field_ext)

    # Run the job with new parameter values
    print("Running job.solve({'lidVelocity': 1.2, 'nCells': 6})...")
    success = wf.solve({"lidVelocity": 1.2, "nCells": 6})
    print(f"Job success: {success}")

    

if __name__ == "__main__":
    openfoam_example()
