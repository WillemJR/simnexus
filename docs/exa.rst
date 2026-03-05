
Examples 
========


LS-DYNA 
----------------------------------

The example does an analysis and extracts results. 

The study is parameterized using the \*PARAMETER keyword.

.. code-block:: python

    from simflow.graph_actions import WorkFlow, WorkArea
    from simflow.dyna_actions import DynaAnalysis
    from simflow.d3plot_actions import d3plot_File

    # 1. Define a workflow
    wf = WorkFlow("DynaWorkflow")

    # 2. Add an action to run LS-DYNA
    # The 'input_path' file contains *PARAMETER keywords for substitution
    run_dyna = DynaAnalysis("RunSimulation", input_path="model.k")
    wf.add_action(run_dyna)

    # 3. Add an action to extract results from d3plot
    d3p = d3plot_File('results_extraction')
    d3p.NodalValue('disp_n5', state=-1, nid=5, component='node_displacement')
    wf.add_action(d3p)

    # 4. Create a WorkArea and execute
    # This will copy 'model.k' to the 'simulation_run' directory
    wa = WorkArea(wf, "./simulation_run", copy_paths=["model.k"])
    params = {'VELOCITY': 10.0, 'THICKNESS': 2.5}
    results = wa.solve(params)

    print(f"Displacement at node 5: {results['disp_n5']}")


OpenRadioss 
----------------------------------

The example does an analysis and extracts results. 

The study is parameterized using the jinja double brace format in the
input deck.

.. code-block:: python

    from simflow.jinja_actions import JinjaReplace
    from simflow.radioss_actions import RadiossAnalysis
    from simflow.graph_actions import WorkFlow

    wf = WorkFlow('RadiossWorkflow')

    # 1. Prepare the input deck using Jinja2 templates
    # Substitutes {{E}} and {{SIG_Y}} in 'model.rad'
    jinja_act = JinjaReplace(
        name='prepare_deck',
        input_file_path='model.rad'
    )
    wf.add_action(jinja_act)

    # 2. Run the OpenRadioss solver
    run_rad = RadiossAnalysis(
        name='run_solver',
        cmd='starter_linux64_gf' # Path to your Radioss executable
    )
    wf.add_action(run_rad)

    # 3. Execute the workflow
    val_dict = {'E': 210000.0, 'SIG_Y': 250.0}
    wf.solve(val_dict)


OpenFOAM 
----------------------------------

The study is parameterized using the system/parameters file.

Extraction of field data and histories from OpenFOAM cases.

NOT COMPLETE. ADD RunOpenFOAM

.. code-block:: python

    from simflow.openfoam_actions import OpenFOAM_Field, OpenFOAM_History
    from simflow.graph_actions import WorkFlow

    wf = WorkFlow('OpenFOAM_Extraction')

    # 1. Extract a field at a specific time
    field_ext = OpenFOAM_Field(
        name='temp_field',
        field_variable='T',
        time=50
    )
    wf.add_action(field_ext)

    # 2. Extract history for a specific point index
    hist_ext = OpenFOAM_History(
        name='temp_history',
        field_variable='T',
        point_idx=10
    )
    wf.add_action(hist_ext)

    # 3. Run the extraction
    results = wf.solve({})
    print(f"Field data: {results['temp_field']}")
    print(f"History data: {results['temp_history']}")


