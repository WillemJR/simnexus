
import os
import sys
from pathlib import Path

# Add project root to path to ensure simflow is found
sys.path.append( str(Path(__file__).parent.parent) )

from simflow.jinja_actions import JinjaReplace
from simflow.radioss_actions import RunRadioss
from simflow.graph_actions import WorkFlow

def main():
    # Paths
    input_deck = Path('tests/par_tens.k')
    #ready_deck = Path('par_tens_ready.k')

    if not input_deck.exists():
        print(f"Error: {input_deck} not found. Run from project root.")
        return

    # 1. Define JinjaReplace to substitute parameters
    # This reads 'tests/par_tens.k', substitutes {{E}} and {{SIG_Y}}, 
    # and writes to 'par_tens_ready.k'
    jinja_act = JinjaReplace( 
        name='prepare_deck', 
        input_file_path=str(input_deck),
        #output_file_path=str(ready_deck),
        val_format="%10.3g"
    )

    # 2. Define RunRadioss to run the simulation
    # It takes the substituted file 'par_tens_ready.k' as input.
    # Note: In a real scenario, set 'cmd' to your Radioss executable path (e.g. 'starter_linux64_gf').
    # Here we use a dummy command for demonstration.
    run_rad = RunRadioss( 
        name='run_solver', 
        #fe_path=str(ready_deck),
        cmd='echo "Running Radioss Solver..."'
    )

    # 3. Create a workflow and add actions
    wf = WorkFlow( 'tensile_test_workflow' )
    wf.add_action( jinja_act )
    wf.add_action( run_rad )

    # 4. Execute the workflow
    # Provide values for the variables defined in the Jinja template
    val_dict = {
        'E': 210000.0, 
        'SIG_Y': 250.0
    }

    print("Starting workflow...")
    print(f"Parameters: {val_dict}")
    
    try:
        wf.eval( val_dict )
        print("Workflow completed.")
    except Exception as e:
        print(f"Workflow execution stopped (expected if solver is missing): {e}")

    # Verification
    if ready_deck.exists():
        print(f"\nVerification: '{ready_deck}' was created.")
        with open(ready_deck, 'r') as f:
            content = f.read()
            # Check a few lines around the substitution
            # In par_tens.k: 1, 7.8000E-06, {{E}}, 0.3, {{SIG_Y}}, ...
            if "2.1e+05" in content and "250" in content:
                print("Verification: Substitution successful.")
                # find the line
                for line in content.splitlines():
                     if "2.1e+05" in line:
                         print(f"Substituted line: {line.strip()}")
            else:
                print("Verification: Substitution content check failed.")
    
    if Path('run_file.k').exists():
         print("Verification: 'run_file.k' was created by RunRadioss.")

if __name__ == "__main__":
    main()
