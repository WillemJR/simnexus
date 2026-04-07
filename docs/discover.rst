
Discovering graph usage
--------------------------
The usage of a graph is described using the ``variables()`` and ``outputs()`` methods.
The methods will return the variables and outputs for all the actions in the graph.

Retrieving the graph variables
==============================
The ``variables()`` method returns the set of ``Variable`` objects that a graph
or action expects as inputs.

For actions that read parameterised input files (``DynaAnalysis``,
``RadiossAnalysis``, ``OpenFOAMAnalysis``, ``JinjaReplace``), the input file
must be present in the current working directory when ``variables()`` is called.
``WorkArea`` and ``SimulationIterator`` both handle this automatically: they
copy all required files to a work directory before delegating to the graph.

Using ``WorkArea``:

.. code-block:: python

    from simflow.graph_actions import WorkFlow, WorkArea
    from simflow.dyna_actions import DynaAnalysis
    from simflow.d3plot_actions import d3plot_File

    wf = WorkFlow(name='SpringWorkFlow')
    wf.add_action(DynaAnalysis(name='RunSpring', input_path='spring.k'))
    wf.add_action(d3plot_File(name='field'))

    wa = WorkArea(wf, copy_paths=['path/to/spring.k'])
    for v in wa.variables():
        print(v)

Using ``SimulationIterator``:

.. code-block:: python

    from simflow.graph_actions import WorkFlow, SimulationIterator
    from simflow.dyna_actions import DynaAnalysis

    wf = WorkFlow(name='SpringWorkFlow')
    wf.add_action(DynaAnalysis(name='RunSpring', input_path='spring.k'))

    itr = SimulationIterator(wf, copy_paths=['path/to/spring.k'])
    for v in itr.variables():
        print(v)

Both copy files into a temporary subdirectory so the source files are never
modified. Each variable carries its name, type, default value, and description:

.. code-block:: text

    Variable Name: K, Data Type: float, Value: 200.0, Description: 'Spring stiffness [N/m]'


Retrieving the graph outputs
=============================
The ``outputs()`` method returns information about what an action produces.
For a single action it returns a ``(eval_type, description)`` tuple.
For a ``WorkFlow`` or ``DirectedGraph`` it returns a dictionary
``{action_name: (eval_type, description)}`` covering all child actions.

.. code-block:: python

    from simflow.graph_actions import WorkFlow, WorkArea
    from simflow.dyna_actions import DynaAnalysis
    from simflow.d3plot_actions import d3plot_File

    wf = WorkFlow(name='SpringWorkFlow')
    wf.add_action(DynaAnalysis(name='RunSpring', input_path='spring.k'))
    wf.add_action(d3plot_File(name='field'))

    for name, (eval_type, description) in wf.outputs().items():
        print(f'{name}: {eval_type} — {description}')

