
import sys, os
from pathlib import Path

from simuflow.graph_actions import WorkFlow, SimulationIterator
from simuflow.dyna_actions import RunDyna
from simuflow.d3plot_actions import d3plot_Open, d3plot_NodalValue

def run_example():

    fe_path = Path(__file__).parent.parent / "tests" / "spring.k"
    if not fe_path.exists(): exit(f"Error: {fe_path} does not exist.")

    wf = WorkFlow("DynaSpringWF")
    
    run_dyna = RunDyna("RunSpring", fe_path=str(fe_path))
    wf.add_action(run_dyna)
    
    # Results are extracted from the d3plot file.
    d3p = d3plot_Open( 'field' )
    d3p.add_action( d3plot_NodalValue('n5', state=1, nid=5, component= 'node_displacement'  ))
    d3p.add_action( d3plot_NodalValue('c5', state=1, nid=5, component= 'node_coordinates'  ))
    wf.add_action( d3p )

    # Create SimulationIterator. We copy the spring.k file to the run directory
    iterator = SimulationIterator( "SpringSimulation", wf,
                                    copy_files=[str(fe_path)], clean_start=True)
    
    # parameters values will be edited`
    params = {'floatpar1': 1.5, 'intpar2': 800}
    print(f"Running simulation with params: {params}")
    
    # Run
    try:
        results = iterator.eval(params)
        print("Results:", results)
    except Exception as e:
        print(f"Simulation execution failed: {e}")

if __name__ == "__main__":
    run_example()
