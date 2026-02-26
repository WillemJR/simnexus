import os
import shutil
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from simflow.openfoam_actions import OpenFOAMAnalysis
from simflow.args import JobType
import simflow.variables as simvars

# Source case directory — used as copy_paths source; never mutated by tests.
CASE_SOURCE = Path(__file__).parent / "openfoam_exa"

# Individual OpenFOAM subdirectories to copy into the work directory so that
# the standard case layout (system/, constant/, 0/) is reproduced at cwd level.
CASE_PATHS = [str(CASE_SOURCE / "system"), str(CASE_SOURCE / "constant"), str(CASE_SOURCE / "0")]


def test_openfoam_job_variables():
    job = OpenFOAMAnalysis(name="test_job", copy_paths=CASE_PATHS)
    variables = job.variables()

    assert len(variables) == 5
    names = [v.name for v in variables]
    assert "nCells" in names
    assert "lidVelocity" in names
    assert "nu" in names
    assert "endTime" in names
    assert "deltaT" in names

    for v in variables:
        if v.name == "nCells":
            assert v.value == 20
        if v.name == "lidVelocity":
            assert v.value == 1.0


@patch('subprocess.run')
def test_openfoam_job_solve(mock_run, tmp_path):
    mock_run.return_value = MagicMock(returncode=0, stderr=b'')

    job = OpenFOAMAnalysis(
        name="test_job",
        copy_paths=CASE_PATHS,
        job_flag=JobType.CREATE_MESH | JobType.RUN_SIMULATION
    )

    original_dir = os.getcwd()
    os.chdir(tmp_path)
    try:
        success = job.solve({"nCells": 30, "lidVelocity": 1.5})
    finally:
        os.chdir(original_dir)

    assert success is True

    # solve() copies system/, constant/, 0/ directly into tmp_path
    par_file = tmp_path / "system" / "parameters"
    content = par_file.read_text()
    assert "nCells 30;" in content
    assert "lidVelocity 1.5;" in content

    assert mock_run.call_count == 2
    assert "blockMesh" in mock_run.call_args_list[0][0][0]
    assert "laplacianFoam" in mock_run.call_args_list[1][0][0]


@patch('subprocess.run')
def test_openfoam_job_flags(mock_run, tmp_path):
    mock_run.return_value = MagicMock(returncode=0, stderr=b'')

    job = OpenFOAMAnalysis(
        name="test_job",
        copy_paths=CASE_PATHS,
        job_flag=JobType.RUN_SIMULATION | JobType.EXTRACT_VTK,
        solve_cmd="mySolver"
    )

    original_dir = os.getcwd()
    os.chdir(tmp_path)
    try:
        success = job.solve({})
    finally:
        os.chdir(original_dir)

    assert success is True
    assert mock_run.call_count == 2

    commands = [args[0][0] for args in mock_run.call_args_list]
    assert "mySolver" in commands
    assert "foamToVtk" in commands
    assert "blockMesh" not in commands
    assert "paraFoam" not in commands


def test_openfoam_job_init_defaults():
    job = OpenFOAMAnalysis(name="test_job", copy_paths=CASE_PATHS)
    assert job.solve_cmd == 'laplacianFoam'
    assert job.mesh_cmd is None
    assert job.job_flag == (JobType.CREATE_MESH |
                            JobType.RUN_SIMULATION |
                            JobType.POST_PRO |
                            JobType.EXTRACT_VTK)
