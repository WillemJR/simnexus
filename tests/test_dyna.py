
import sys, os
from pathlib import Path

from simflow.graph_actions import WorkFlow, WorkArea
from simflow.dyna_actions import RunDyna
from simflow.d3plot_actions import d3plot_Open, d3plot_NodalValue

def test_dyna_run_extract():

    fe_path = Path(__file__).parent.parent / "tests" / "spring.k"
    if not fe_path.exists(): exit(f"Error: {fe_path} does not exist.")

    wf = WorkFlow("SpringWorkFlow")
    
    run_dyna = RunDyna("RunSpring", fe_path=str(fe_path))
    wf.add_action(run_dyna)
    
    # Results are extracted from the d3plot file.
    d3p = d3plot_Open( 'field' )
    d3p.add_action( d3plot_NodalValue('n5', state=1, nid=5, component= 'node_displacement'  ))
    d3p.add_action( d3plot_NodalValue('c5', state=1, nid=5, component= 'node_coordinates'  ))
    wf.add_action( d3p )

    # Create WorkArea. We copy the spring.k file to the run directory
    wrk_area = WorkArea( wf, copy_files=[str(fe_path)] )
    
    # parameters values will be edited`
    params = {'floatpar1': 1.5, 'intpar2': 800}
    print(f"Running simulation with params: {params}")
    
    # Run
    try:
        results = wrk_area.eval(params)
        print("Results:", results)
    except Exception as e:
        print(f"Simulation execution failed: {e}")
    wrk_area.rm_rundir() 

if __name__ == "__main__":
    test_dyna_run_extract()
