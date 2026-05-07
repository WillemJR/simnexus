
Examples 
========


LS-DYNA 
----------------------------------

The example does an analysis and extracts results. 

The study is parameterized using the \*PARAMETER keyword.

.. code-block:: python

    from simnexus.graph_actions import WorkFlow, WorkArea
    from simnexus.dyna_actions import DynaAnalysis
    from simnexus.d3plot_actions import d3plot_File

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

    # 4. Create a WorkArea; supply the source file via copy_paths.
    wa = WorkArea(wf, "./simulation_run", copy_paths=["path/to/model.k"])

    # 5. Discover variables (WorkArea copies files first so DynaAnalysis can read them)
    for v in wa.variables():
        print(v)

    # 6. Execute
    params = {'VELOCITY': 10.0, 'THICKNESS': 2.5}
    results = wa.solve(params)

    print(f"Displacement at node 5: {results['disp_n5']}")


OpenRadioss 
----------------------------------

The example does an analysis and extracts results. 

The study is parameterized using the jinja double brace format in the
input deck.

.. code-block:: python

    from simnexus.jinja_actions import JinjaReplace
    from simnexus.radioss_actions import RadiossAnalysis
    from simnexus.graph_actions import WorkFlow

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

The study is parameterized using the ``system/parameters`` file.
Case files (``system/``, ``constant/``, ``0/``) are supplied to ``WorkArea``
via ``copy_paths`` and are copied to the work directory before the solver runs.

.. code-block:: python

    from simnexus.openfoam_actions import OpenFOAMAnalysis, OpenFOAM_Field
    from simnexus.graph_actions import WorkFlow, WorkArea

    case_paths = ['path/to/case/system', 'path/to/case/constant', 'path/to/case/0']

    wf = WorkFlow('OpenFOAM_WorkFlow')
    wf.add_action(OpenFOAMAnalysis(name='run', solve_cmd='icoFoam'))
    wf.add_action(OpenFOAM_Field(name='p', field_variable='p', time=0.5))

    wa = WorkArea(wf, copy_paths=case_paths)

    # Discover variables from system/parameters (files are copied first)
    for v in wa.variables():
        print(v)

    results = wa.solve({'lidVelocity': 1.2})

Extraction of field data and histories from OpenFOAM cases.

.. code-block:: python

    from simnexus.openfoam_actions import OpenFOAM_Field, OpenFOAM_History
    from simnexus.graph_actions import WorkFlow

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


