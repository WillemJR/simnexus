
Creating directories and copying files
=======================================

Solver actions such as ``DynaAnalysis``, ``RadiossAnalysis``, and
``OpenFOAMAnalysis`` expect their input files to be present in the
current working directory when they run.  Two classes handle directory
creation and file copying automatically: ``WorkArea`` and
``SimulationIterator``.

``copy_paths`` is always specified on ``WorkArea`` or
``SimulationIterator`` — not on individual solver actions.


WorkArea
--------

``WorkArea`` evaluates a graph in a dedicated directory.
Each call to ``solve()`` cleans the directory and re-copies the required
files, so previous results are overwritten.  This is the right choice
for a single run or when you want to inspect intermediate files after
the run.

.. code-block:: python

    from simnexus.graph_actions import WorkFlow, WorkArea
    from simnexus.dyna_actions import DynaAnalysis
    from simnexus.d3plot_actions import d3plot_File

    wf = WorkFlow('SpringWorkFlow')
    wf.add_action(DynaAnalysis(name='run', input_path='spring.k'))
    wf.add_action(d3plot_File(name='field'))

    # 'spring.k' is copied from its source location into ./SpringWorkFlow/
    # before the graph runs.
    wa = WorkArea(wf, copy_paths=['path/to/spring.k'])
    results = wa.solve({'K': 200.0})

By default the work directory is ``./{graph.name}`` — created relative to
the current directory at run time (not the directory in which the
``WorkArea`` was constructed). This means a ``WorkArea`` can be nested
inside a ``SimulationIterator``: it is created *inside* the current
``job_N`` directory rather than next to it. A custom path can be supplied
as the second argument::

    wa = WorkArea(wf, work_area_path='~/runs/spring', copy_paths=['path/to/spring.k'])

An explicit relative path is likewise resolved against the current
directory at run time, while an absolute path is used as given. The
directory path may contain ``~`` and environment variables; both are
expanded automatically.


SimulationIterator
------------------

``SimulationIterator`` evaluates a graph once per design point, placing
each run in its own numbered subdirectory (``job_0``, ``job_1``, …).
The required files are copied into each job directory before the graph
runs.  Use this when you need to keep the results from every run, for
example during a parameter study or optimisation.

.. code-block:: python

    from simnexus.graph_actions import WorkFlow, SimulationIterator
    from simnexus.dyna_actions import DynaAnalysis
    from simnexus.d3plot_actions import d3plot_File

    wf = WorkFlow('SpringWorkFlow')
    wf.add_action(DynaAnalysis(name='run', input_path='spring.k'))
    wf.add_action(d3plot_File(name='field'))

    itr = SimulationIterator(wf, copy_paths=['path/to/spring.k'])

    # Each call to solve() creates a new job_N subdirectory.
    itr.solve({'K': 100.0})   # writes to SpringWorkFlow/job_0/
    itr.solve({'K': 200.0})   # writes to SpringWorkFlow/job_1/

The resulting directory layout is::

    SpringWorkFlow/
    ├── job_0/
    │   ├── iter_variables.json
    │   └── actions_output.pkl
    ├── job_1/
    │   ├── iter_variables.json
    │   └── actions_output.pkl

Pass ``clean_start=True`` to remove any existing results directory
before starting::

    itr = SimulationIterator(wf, copy_paths=['path/to/spring.k'], clean_start=True)


Variable discovery
------------------

Both ``WorkArea`` and ``SimulationIterator`` support variable discovery
via ``parameters()``.  Files are copied into a temporary subdirectory
first so that solver actions can read their input files.

.. code-block:: python

    wa = WorkArea(wf, copy_paths=['path/to/spring.k'])
    for v in wa.parameters():
        print(v)

    itr = SimulationIterator(wf, copy_paths=['path/to/spring.k'])
    for v in itr.parameters():
        print(v)

See :doc:`discover` for more details on variable and output discovery.
