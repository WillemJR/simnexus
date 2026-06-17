
Examples 
========
In addition to the examples below, see the ``examples`` directory.

LS-DYNA 
----------------------------------

The example does an analysis, substitute parameter values, and extracts results. 

The study is parameterized using the \*PARAMETER keyword.

.. code-block:: python

    from simnexus.graph_actions import WorkFlow, WorkArea
    from simnexus.dyna_actions import DynaAnalysis
    from simnexus.d3plot_actions import d3plot_File

    # 1. Define a workflow
    wf = WorkFlow("DynaWorkflow")

    # 2. Add an action to run LS-DYNA
    # The 'input_path' file contains *PARAMETER keywords for substitution
    run_dyna = DynaAnalysis("RunDyna", cmd='ls-dyna', input_path="model.k")
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

The example does an analysis, substitute parameter values, and extracts results. 

The study is parameterized using the /PARAMETER cards in
the OpenRadioss input deck.
Also shown is defining parameters using jinja double brace format in the
input deck (shown here only to demonstrate -- the use of jinja is not required).

.. code-block:: python

        from simnexus.radioss_actions import RadiossAnalysis
        from simnexus.d3plot_actions import d3plot_File
        from simnexus.graph_actions import WorkFlow, WorkArea

        # Paths
        starter_deck = Path('models/cube_TYPE7_0000.rad')
        engine_deck  = Path('models/cube_TYPE7_0001.rad')

        # 1. Define RadiossAnalysis to run the simulation
        run_rad = RadiossAnalysis( name='rad',
                          starter_cmd='openradioss_starter',
                          starter_input_path=starter_deck,
                          engine_cmd='openradioss_engine',
                          engine_input_path=engine_deck,
                          create_d3plot=True )

        # 2. Create a workflow and add actions
        wf = WorkFlow( 'Radioss_WorkFlow' )
        wf.add_action( run_rad )

        d3p = d3plot_File( name='d3plot' )
        d3p.NodalValue(name='n5', state=1, nid=5, component= 'node_displacement'  )
        wf.add_action( d3p )

        wrk_area = WorkArea( wf, copy_paths=[starter_deck,engine_deck] )

        # Discover variables defined in input deck and other actions
        discovered_vars = wrk_area.variables()
        print("Discovered variables:")
        for v in discovered_vars:
            print(f"  {v}")

        # 3. Execute the workflow. Provide values for the variables.
        ret = wrk_area.solve( { 'E': 210000.0, } )
        print( 'output', ret )


OpenFOAM
----------------------------------
The example does an analysis, substitute parameter values, and extracts results. 

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


