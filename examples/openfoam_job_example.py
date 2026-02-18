import os
import shutil
from pathlib import Path
from simflow.openfoam_actions import OpenFOAM_Job
from simflow.args import JobType
import simflow.variables as simvars

def openfoam_example():

    case_dir = Path(__file__).parent.parent / "tests" / "openfoam_exa"
    if not case_dir.exists(): exit(f"Error: {case_dir} does not exist.")

    job = OpenFOAM_Job(
        name="my_job",
        dir_name=str(case_dir),
        job_flag=JobType.CREATE_MESH | JobType.RUN_SIMULATION,
        solve_cmd="icoFoam",
        mesh_cmd="blockMesh"
    )

    # Discover variables
    discovered_vars = job.variables()
    print("Discovered variables:")
    for v in discovered_vars:
        print(f"  {v}")

    # Run the job with new parameter values
    print("Running job.solve({'lidVelocity': 1.2, 'nCells': 6})...")
    success = job.solve({"lidVelocity": 1.2, "nCells": 6})
    print(f"Job success: {success}")


if __name__ == "__main__":
    openfoam_example()
