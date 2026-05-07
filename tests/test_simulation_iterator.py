import sys, os, shutil
from pathlib import Path
import pytest

from simnexus.graph_actions import WorkFlow, WorkArea, SimulationIterator
from simnexus.actions import MathEvaluation

def test_work_area_custom_path():
    print("Testing WorkArea with custom path...")
    wf = WorkFlow("TestWF")
    wf.add_action(MathEvaluation("calc", "2 * x"))
    
    custom_path = Path("custom_work_area")
    if custom_path.exists():
        shutil.rmtree(custom_path)
        
    wa = WorkArea(wf, work_area_path=str(custom_path))
    params = {'x': 5}
    
    try:
        res = wa.solve(params)
        assert res['calc'] == 10
        assert custom_path.exists()
    finally:
        wa.rm_rundir()

@pytest.mark.parametrize("path_template", [
    "/tmp/simnexus_WA_test",
    "~/tmp/simnexus_WA_test",
    "$HOME/tmp/simnexus_WA_test"
])
def test_simulation_iterator_special_paths(path_template):
    print(f"Testing SimulationIterator with path: {path_template}")
    wf = WorkFlow("TestWF_Special")
    wf.add_action(MathEvaluation("calc", "x + 1"))
    
    # We need to resolve the path for verification in the test
    resolved_path = Path(os.path.expandvars(os.path.expanduser(path_template)))
    
    if resolved_path.exists():
        shutil.rmtree(resolved_path)
        
    sim_iter = SimulationIterator(wf, work_area_path=path_template, clean_start=True)
    
    try:
        # Run iteration
        params = {'x': 100}
        res = sim_iter.solve(params) 
        
        # Verify
        assert res['calc'] == 101
        assert sim_iter.work_area_path == resolved_path
        assert resolved_path.exists()
        assert (resolved_path / "job_0").exists()
        
    finally:
        sim_iter.rm_rundir()
        # Clean up the ~/tmp or $HOME/tmp if we created it
        if resolved_path.exists():
            shutil.rmtree(resolved_path)

if __name__ == "__main__":
    # If run directly, just run some examples
    pytest.main([__file__])
