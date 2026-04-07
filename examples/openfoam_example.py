import logging
logging.basicConfig(level=logging.WARNING)

from pathlib import Path
from simflow.args import JobType
from simflow.graph_actions import WorkFlow, WorkArea
from simflow.openfoam_actions import OpenFOAMAnalysis
from simflow.openfoam_actions import OpenFOAM_Field, OpenFOAM_History

def openfoam_example():

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

    field_ext = OpenFOAM_Field(
        name='p',
        field_variable='p',
        time=0.5
    )
    wf.add_action(field_ext)

    wa = WorkArea(wf, copy_paths=case_paths)

    # Discover variables — WorkArea copies files first so OpenFOAMAnalysis can read system/parameters.
    discovered_vars = wa.variables()
    print("Discovered variables:")
    for v in discovered_vars:
        print(f"  {v}")

    # Run the job with new parameter values
    print("Running job.solve({'lidVelocity': 1.2, 'nCells': 6})...")
    outcomes = wa.solve({"lidVelocity": 1.2, "nCells": 6})
    print(f"Job outcomes: {outcomes}")


if __name__ == "__main__":
    openfoam_example()
