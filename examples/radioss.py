import numpy as np

import logging
logging.basicConfig(level=logging.WARNING)

import os
import sys
from pathlib import Path

# Add project root to path to ensure simnexus is found
sys.path.append( str(Path(__file__).parent.parent) )

from simnexus.radioss_actions import RadiossAnalysis, RadiossCSVHistory, NodalFieldData_VTK
from simnexus.graph_actions import WorkFlow, WorkArea

def main():
    # Paths
    starter_deck = Path('models/cube_TYPE7_0000.rad')
    engine_deck  = Path('models/cube_TYPE7_0001.rad')

    if not starter_deck.exists() or not engine_deck.exists():
        print(f"Error: {starter_deck} or {engine_deck}not found. Run from project root.")
        return

    # 1. Define RadiossAnalysis to run the simulation
    run_rad = RadiossAnalysis( name='rad', 
                  starter_cmd='openradioss_starter',
                  starter_input_path=starter_deck,
                  engine_cmd='openradioss_engine',
                  engine_input_path=engine_deck,
                  create_d3plot=False,
                  create_vtk=True,
                  create_csv=True )

    # 2. Create a workflow and add actions
    wf = WorkFlow( 'Radioss_WorkFlow' )
    wf.add_action( run_rad )
    wf.add_action( RadiossCSVHistory('KE_hist', '{"quantity":"KINETIC ENERGY" }' ) )
    wf.add_action( NodalFieldData_VTK('disp_field', state=2, required_part_id=4,
                                        node_data_names=[ 'NODE_ID', 'Velocity' ] ) )
    wrk_area = WorkArea( wf, copy_paths=[starter_deck,engine_deck] )

    # Discover variables — WorkArea copies files first so DynaAnalysis can read them.
    discovered_vars = wrk_area.variables()
    print("Discovered variables:")
    for v in discovered_vars:
        print(f"  {v}")

    # 3. Execute the workflow
    # Provide values for the variables defined in the Jinja template
    val_dict = { 'E': 210.0, 'SIG_Y': 310.0 }

    print("Starting workflow...")
    print(f"Parameters: {val_dict}")
    
    try:
        ret = wrk_area.solve( val_dict )
        print("Workflow completed.")
        print("Available results.", ret.keys() )
    except Exception as e:
        print(f"Workflow execution stopped: {e}")

if __name__ == "__main__":
    main()

