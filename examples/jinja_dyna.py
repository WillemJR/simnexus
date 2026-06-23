import logging
logging.basicConfig(level=logging.WARNING)

import os
import sys
from pathlib import Path

# Add project root to path to ensure simnexus is found
sys.path.append( str(Path(__file__).parent.parent) )

from simnexus.graph_actions import WorkFlow, WorkArea
from simnexus.jinja_actions import JinjaReplace
from simnexus.dyna_actions import DynaAnalysis

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
        input_file_path=str(input_deck), output_file_path='edited.k',
        val_format="%10.3g"
    )

    # 2. Use DynaAnalysis to run the simulation
    # It takes the substituted file 'edited.k' as input.
    run_dyna = DynaAnalysis("DYNA", cmd='ls-dyna', input_path='edited.k')


    # 3. Create a workflow and add actions
    wf = WorkFlow( 'JD_WorkFlow' )
    wf.add_action( jinja_act )
    wf.add_action( run_dyna )
    wrk_area = WorkArea( wf )

    # Discover variables — WorkArea copies files first so DynaAnalysis can read them.
    discovered_vars = wrk_area.parameters()
    print("Discovered variables:")
    for v in discovered_vars:
        print(f"  {v}")

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

