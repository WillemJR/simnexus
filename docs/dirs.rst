
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
    ├── jobs_index.json
    ├── job_0/
    │   ├── iter_variables.json
    │   └── actions_output.pkl
    ├── job_1/
    │   ├── iter_variables.json
    │   └── actions_output.pkl

Pass ``clean_start=True`` to remove any existing results directory
before starting::

    itr = SimulationIterator(wf, copy_paths=['path/to/spring.k'], clean_start=True)

The job directories are always named ``job_0 … job_N``; the prefix comes
from the class attribute ``SimulationIterator.JNAME`` and can be changed
(``itr.JNAME = 'design_'``) if another name suits better.  Variable
values are *not* encoded in the directory name — they are recorded in
``jobs_index.json``, which is what the retrieval methods below use.


Retrieving and grouping past runs
---------------------------------

``jobs_index.json`` at the results root maps each job directory to the
variable values it was run with, its state, and any group labels::

    { "jobs": [ { "job": "job_0",
                  "groups": [ "baseline" ],
                  "variables": { "K": 100.0 },
                  "state": "done",
                  "created_at": 1753.0, "updated_at": 1755.0 } ] }

**Retrieving results without running the graph.**  Point a new
``SimulationIterator`` at an existing results directory and ask it for
results by variable value.  Nothing is executed:

.. code-block:: python

    itr = SimulationIterator(wf, work_area_path='SpringWorkFlow')

    out  = itr.results_for({'K': 100.0})    # the stored actions_output.pkl
    path = itr.find_job(where={'K': 100.0}) # SpringWorkFlow/job_0

``results_for`` prefers the job whose variables are exactly the ones
given, and otherwise accepts an unambiguous partial match, so
``results_for({'K': 100.0})`` works in a study that also varied ``T``
as long as only one job has that ``K``.  It raises ``DataNotFoundError``
when no job matches and when several do.

**Grouping runs.**  A job may carry any number of group labels.  Set a
default for the iterator, per sweep, or per job — the most specific wins:

.. code-block:: python

    itr = SimulationIterator(wf, groups='baseline')       # default for all jobs
    itr.collect_for_varrange({'K': [100., 200.]})         # -> 'baseline'
    itr.collect_for_varrange({'K': [300.]}, groups='stiff')
    itr.solve({'K': 400.}, groups=['stiff', 'hand_check'])
    itr.groups = 'later_runs'                             # from here on

Because the labels are metadata rather than directories, runs can be
grouped long after they finished, and one job can belong to several
groups:

.. code-block:: python

    itr.add_groups('converged', where={'K': 100.0})
    itr.add_groups('report', jobs=['job_0', 'job_3'])
    itr.remove_groups('stiff', jobs=['job_2'])
    itr.group_names()                    # ['baseline', 'converged', ...]

Read a group back in the same form a sweep returns — so grouped runs can
be plotted or post-processed like a fresh study:

.. code-block:: python

    pars, out = itr.collect(groups='baseline')
    # pars: {'K': array([100., 200.])}, out: {'disp': [...], ...}

    pars, out = itr.collect(groups=['baseline', 'converged'],
                            match_all_groups=True)   # in both groups
    jobs = itr.find_jobs(groups='report', state=None)

**Reusing completed runs.**  With ``reuse_existing=True`` a design point
that already has a completed job is not run again — its stored outputs
are returned and its labels extended, while new design points run as
usual and are numbered after the existing jobs:

.. code-block:: python

    itr = SimulationIterator(wf, work_area_path='SpringWorkFlow',
                             reuse_existing=True, groups='study_2')
    pars, out = itr.collect_for_varrange({'K': [100., 500.]})
    itr.reused_jobs        # ['job_0']  — K=100 came off disk

Without this flag the behaviour is unchanged: an existing results
directory is refused.  Note that reuse matches on the *complete* set of
variable values, so a job that differs in any variable is treated as a
different design point.

The index is a cache, never the authority.  ``itr.job_index(rebuild=True)``
re-derives it by reading the job directories, so result trees created
before the index existed keep working; only the group labels — which
exist nowhere else — are lost if the file is deleted.


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
