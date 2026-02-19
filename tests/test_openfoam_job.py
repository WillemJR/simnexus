import os
import shutil
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from simflow.openfoam_actions import OpenFOAMAnalysis
from simflow.args import JobType
import simflow.variables as simvars

@pytest.fixture
def dummy_case(tmp_path):
    source_dir = Path(__file__).parent / "openfoam_exa"
    case_dir = tmp_path / "openfoam_exa"
    shutil.copytree(source_dir, case_dir)
    return case_dir

def test_openfoam_job_variables(dummy_case):
    job = OpenFOAMAnalysis(name="test_job", case_dir=str(dummy_case))
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
def test_openfoam_job_solve(mock_run, dummy_case):
    # Mock subprocess.run to return success
    mock_run.return_value = MagicMock(returncode=0)
    
    job = OpenFOAMAnalysis(
        name="test_job", 
        case_dir=str(dummy_case),
        job_flag=JobType.CREATE_MESH | JobType.RUN_SIMULATION
    )
    
    success = job.solve({"nCells": 30, "lidVelocity": 1.5})
    
    assert success is True
    
    # Check if parameters were updated
    par_file = dummy_case / "system" / "parameters"
    content = par_file.read_text()
    assert "nCells 30;" in content
    assert "lidVelocity 1.5;" in content
    
    # Check if commands were called
    assert mock_run.call_count == 2
    # First call should be mesh_cmd (default blockMesh)
    assert "blockMesh" in mock_run.call_args_list[0][0][0]
    # Second call should be solve_cmd (default laplacianFoam)
    assert "laplacianFoam" in mock_run.call_args_list[1][0][0]

@patch('subprocess.run')
def test_openfoam_job_flags(mock_run, dummy_case):
    mock_run.return_value = MagicMock(returncode=0)
    
    # Only RUN_SIMULATION and EXTRACT_VTK
    job = OpenFOAMAnalysis(
        name="test_job", 
        case_dir=str(dummy_case),
        job_flag=JobType.RUN_SIMULATION | JobType.EXTRACT_VTK,
        solve_cmd="mySolver"
    )
    
    success = job.solve({})
    
    assert success is True
    assert mock_run.call_count == 2
    
    commands = [args[0][0] for args in mock_run.call_args_list]
    assert "mySolver" in commands
    assert "foamToVtk" in commands
    assert "blockMesh" not in commands
    assert "paraFoam" not in commands

def test_openfoam_job_init_defaults(dummy_case):
    job = OpenFOAMAnalysis(name="test_job", case_dir=str(dummy_case))
    assert job.solve_cmd == 'laplacianFoam'
    assert job.mesh_cmd is None
    assert job.job_flag == (JobType.CREATE_MESH | 
                            JobType.RUN_SIMULATION | 
                            JobType.POST_PRO | 
                            JobType.EXTRACT_VTK)
