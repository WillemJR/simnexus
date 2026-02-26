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

    wf = WorkFlow('OpenFOAM_Extraction')

    job = wf.add_action( OpenFOAMAnalysis(
        name="my_job",
        copy_paths=case_paths,
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
        field_variable='T',
        time=50
    )
    wf.add_action(field_ext)

    wa = WorkArea(wf, work_area_path='FOAM_WorkArea')

    # Run the job with new parameter values
    print("Running job.solve({'lidVelocity': 1.2, 'nCells': 6})...")
    success = wa.solve({"lidVelocity": 1.2, "nCells": 6})
    print(f"Job success: {success}")


if __name__ == "__main__":
    openfoam_example()
