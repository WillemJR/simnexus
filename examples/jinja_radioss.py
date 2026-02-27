import logging
logging.basicConfig(level=logging.WARNING)

import os
import sys
from pathlib import Path

# Add project root to path to ensure simflow is found
sys.path.append( str(Path(__file__).parent.parent) )

from simflow.jinja_actions import JinjaReplace
from simflow.radioss_actions import RadiossAnalysis
from simflow.graph_actions import WorkFlow, WorkArea

def main():
    # Paths
    input_deck = Path('tests/par_tens.k')

    if not input_deck.exists():
        print(f"Error: {input_deck} not found. Run from project root.")
        return

    # 1. Define JinjaReplace to substitute parameters
    # This reads 'tests/par_tens.k', substitutes {{E}} and {{SIG_Y}}, 
    # and writes to 'par_tens_ready.k'
    jinja_act = JinjaReplace( 
        name='prepare_deck', 
        input_file_path=str(input_deck),
        val_format="%10.3g"
    )

    # 2. Define RadiossAnalysis to run the simulation
    # It takes the substituted file 'par_tens_ready.k' as input.
    run_rad = RadiossAnalysis( name='rad', cmd='radioss_using_dyna_inp' )

    # 3. Create a workflow and add actions
    wf = WorkFlow( 'Radioss_WorkFlow' )
    wf.add_action( jinja_act )
    wf.add_action( run_rad )
    wrk_area = WorkArea( wf, copy_paths=[str(input_deck)] )

    # 4. Execute the workflow
    # Provide values for the variables defined in the Jinja template
    val_dict = { 'E': 210.0, 'SIG_Y': 310.0 }

    print("Starting workflow...")
    print(f"Parameters: {val_dict}")
    
    try:
        wrk_area.solve( val_dict )
        print("Workflow completed.")
    except Exception as e:
        print(f"Workflow execution stopped (expected if solver is missing): {e}")

if __name__ == "__main__":
    main()

