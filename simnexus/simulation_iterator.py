"""
Design studies: evaluating a graph once per design point, and finding
those results again afterwards.

``SimulationIterator`` runs the graph in a numbered job directory per
design point. ``JobIndex`` indexes those directories, which is what makes
past runs retrievable: it maps each job to the variable values it was run
with and to the group labels it carries.

The two belong in one module because they describe the same thing from
two sides - the iterator writes the results directory, the index reads it
- and because the index means nothing without the layout the iterator
creates.

Each design evaluation writes its variable values to
``iter_variables.json`` and its action outputs to ``actions_output.pkl``
inside its own ``job_N`` directory. Those files describe one job but say
nothing about the set: answering "which job used K=0.2?" or "which jobs
belong to the baseline study?" meant walking every directory and reading
every file.

``jobs_index.json`` at the results root records one entry per job::

    { "jobs": [ { "job": "job_0",
                  "groups": [ "baseline" ],
                  "variables": { "K": 0.2, "T": 75 },
                  "state": "done",
                  "created_at": 1753,  "updated_at": 1755 } ] }

The index is a *cache*, never the authority: ``JobIndex.rebuild`` derives
it from the job directories themselves, so result trees produced before
this file existed (and trees whose index was deleted) keep working. Only
the group labels are unique to the index - they are chosen by the caller
and cannot be recovered from the job directories - so a rebuild preserves
the labels of jobs it already knows.

Directory names stay ``job_0 ... job_N``. Encoding variable values in the
name would have to invent a float format, would break when a study adds a
variable, and could not express group membership at all.
"""

from pathlib import Path
import os, shutil
import json
import time
import pickle
import numbers
from itertools import product

import numpy as np

from simnexus.actions import WorkAction, _display_path, _copy_path_nodes
from simnexus.args import ACTIONS_OUTPUT_PATH, ITER_VARIABLES_PATH, JOBS_INDEX_PATH
from simnexus.errors import ( ActionNameError, ParameterError,
                              MissingPathError, DataNotFoundError )
from simnexus.progress import StatusReporter
import simnexus.args

import logging
logger = logging.getLogger(__name__)


# Default tolerance when matching float variable values. Values that made a
# round trip through JSON (or that a user typed as 0.30000000000000004) must
# still match, but distinct design points must not be merged.
MATCH_RTOL = 1.0e-9
MATCH_ATOL = 1.0e-12


def as_jsonable( value ):
    """Convert numpy scalars/arrays to plain Python so a value can be
    written to JSON. Variable values commonly come from ``np.arange``,
    whose items are ``np.float64`` and are not JSON serializable."""
    if isinstance( value, np.generic ):
        return value.item()
    if isinstance( value, np.ndarray ):
        return [ as_jsonable( v ) for v in value.tolist() ]
    if isinstance( value, dict ):
        return { k: as_jsonable( v ) for k, v in value.items() }
    if isinstance( value, ( list, tuple ) ):
        return [ as_jsonable( v ) for v in value ]
    return value


def values_match( a, b, rtol=MATCH_RTOL, atol=MATCH_ATOL ):
    """True when two variable values denote the same design point.

    Numbers compare with a tolerance (a value written to JSON and read
    back is not always bit-identical); everything else compares equal.
    Booleans are excluded from the numeric path so True does not match 1.
    """
    a, b = as_jsonable( a ), as_jsonable( b )
    if isinstance( a, bool ) or isinstance( b, bool ):
        return a is b or a == b
    if isinstance( a, numbers.Number ) and isinstance( b, numbers.Number ):
        return bool( np.isclose( a, b, rtol=rtol, atol=atol ) )
    return a == b


def normalise_groups( groups ):
    """Accept ``None``, a single label or an iterable of labels and return
    a list of unique labels in the order given."""
    if groups is None:
        return []
    if isinstance( groups, str ):
        groups = [ groups ]
    out = []
    for g in groups:
        g = str( g )
        if g not in out:
            out.append( g )
    return out


class JobIndex:
    """
    Reads and writes the ``jobs_index.json`` of one results root.

    Arguments:
        root (str|Path) : the results root - the directory holding the
            ``job_N`` directories (a ``SimulationIterator``'s
            ``work_area_path``).
        job_prefix (str) : directory name prefix, ``SimulationIterator.JNAME``.
    """

    def __init__( self, root, job_prefix='job_' ):
        self.root = Path( root )
        self.job_prefix = job_prefix
        self.records = []
        self._loaded = False

    # ------------------------------------------------------------------
    # persistence

    @property
    def path( self ):
        return self.root / JOBS_INDEX_PATH

    def load( self, rebuild_if_missing=True ):
        """Read the index from disk. When no index file exists but job
        directories do, derive one from them."""
        if self.path.exists():
            try:
                with open( self.path ) as f:
                    data = json.load( f )
                self.records = data.get( 'jobs', [] )
                self._loaded = True
                # jobs written by a run that never reached the index (or by
                # an older version) are still adopted
                if rebuild_if_missing: self._adopt_unindexed()
                return self
            except ( OSError, ValueError ) as exc:
                logger.warning( f'Could not read {self.path}: {exc}. Rebuilding.' )
        self.records = []
        self._loaded = True
        if rebuild_if_missing:
            self.rebuild()
        return self

    def save( self ):
        """Write the index atomically, so a reader polling the file never
        sees it half-written."""
        if not self.root.exists():
            return
        data = { 'jobs': self.records }
        tmp = self.path.with_name( self.path.name + '.tmp' )
        try:
            with open( tmp, 'w' ) as f:
                json.dump( data, f, indent=1 )
            os.replace( tmp, self.path )
        except OSError as exc:
            # Indexing must never break a workflow that otherwise ran fine.
            logger.warning( f'Could not write {self.path}: {exc}' )

    def rebuild( self, save=True ):
        """Derive the index from the job directories on disk.

        Group labels of jobs already in the index are preserved - they
        exist nowhere else.
        """
        known = { r.get( 'job' ): r for r in self.records }
        records = []
        for job_dir in self.iter_job_dirs():
            rec = self._record_from_dir( job_dir )
            if rec is None:
                continue
            old = known.get( job_dir.name )
            if old is not None:
                rec['groups'] = normalise_groups( old.get( 'groups' ) )
                rec['created_at'] = old.get( 'created_at', rec['created_at'] )
            records.append( rec )
        self.records = records
        self._loaded = True
        if save:
            self.save()
        return self

    def _adopt_unindexed( self ):
        """Add job directories that are on disk but not in the index."""
        known = { r.get( 'job' ) for r in self.records }
        added = False
        for job_dir in self.iter_job_dirs():
            if job_dir.name in known:
                continue
            rec = self._record_from_dir( job_dir )
            if rec is not None:
                self.records.append( rec )
                added = True
        if added:
            self.records.sort( key=lambda r: self._job_number( r.get( 'job', '' ) ) )
            self.save()

    def _record_from_dir( self, job_dir ):
        """Build an index record by reading one job directory."""
        var_path = job_dir / ITER_VARIABLES_PATH
        variables = {}
        if var_path.exists():
            try:
                with open( var_path ) as f:
                    variables = json.load( f )
            except ( OSError, ValueError ) as exc:
                logger.warning( f'Could not read {var_path}: {exc}' )
                return None
        elif not ( job_dir / ACTIONS_OUTPUT_PATH ).exists():
            # neither variables nor outputs: not a job directory
            return None
        # A job whose outputs were written ran to completion; one without
        # them was interrupted (or is running right now).
        done = ( job_dir / ACTIONS_OUTPUT_PATH ).exists()
        try:
            stamp = job_dir.stat().st_mtime
        except OSError:
            stamp = time.time()
        return { 'job': job_dir.name,
                 'groups': [],
                 'variables': variables,
                 'state': 'done' if done else 'unknown',
                 'created_at': stamp,
                 'updated_at': stamp }

    def _ensure( self ):
        if not self._loaded:
            self.load()
        return self

    # ------------------------------------------------------------------
    # job directories

    def _job_number( self, name ):
        try:
            return int( name[ len( self.job_prefix ): ] )
        except ( ValueError, TypeError ):
            return -1

    def iter_job_dirs( self ):
        """Job directories on disk, in numeric order."""
        if not self.root.exists():
            return []
        dirs = [ d for d in self.root.iterdir()
                 if d.is_dir() and d.name.startswith( self.job_prefix )
                 and self._job_number( d.name ) >= 0 ]
        return sorted( dirs, key=lambda d: self._job_number( d.name ) )

    def next_job_number( self ):
        """The first unused job number, considering both the index and the
        directories on disk (either may be ahead of the other)."""
        used = [ self._job_number( d.name ) for d in self.iter_job_dirs() ]
        self._ensure()
        used += [ self._job_number( r.get( 'job', '' ) ) for r in self.records ]
        used = [ n for n in used if n >= 0 ]
        return max( used ) + 1 if used else 0

    def job_path( self, job ):
        """Absolute path of a job directory, given its name or record."""
        if isinstance( job, dict ):
            job = job.get( 'job' )
        return self.root / job

    # ------------------------------------------------------------------
    # updating

    def record_job( self, job, variables, groups=None, state='running' ):
        """Insert or update the entry for one job."""
        self._ensure()
        groups = normalise_groups( groups )
        variables = as_jsonable( variables )
        now = time.time()
        for rec in self.records:
            if rec.get( 'job' ) == job:
                rec['variables'] = variables
                rec['state'] = state
                rec['updated_at'] = now
                for g in groups:
                    if g not in rec.setdefault( 'groups', [] ):
                        rec['groups'].append( g )
                self.save()
                return rec
        rec = { 'job': job,
                'groups': groups,
                'variables': variables,
                'state': state,
                'created_at': now,
                'updated_at': now }
        self.records.append( rec )
        self.save()
        return rec

    def set_state( self, job, state ):
        """Set the state ('running', 'done', 'failed') of one job."""
        self._ensure()
        for rec in self.records:
            if rec.get( 'job' ) == job:
                rec['state'] = state
                rec['updated_at'] = time.time()
                self.save()
                return rec
        return None

    def add_groups( self, jobs, groups ):
        """Add group labels to the given jobs (names or records).

        Returns the list of job names that were changed.
        """
        self._ensure()
        groups = normalise_groups( groups )
        names = { j.get( 'job' ) if isinstance( j, dict ) else str( j ) for j in jobs }
        changed = []
        for rec in self.records:
            if rec.get( 'job' ) not in names:
                continue
            have = rec.setdefault( 'groups', [] )
            for g in groups:
                if g not in have:
                    have.append( g )
                    if rec['job'] not in changed: changed.append( rec['job'] )
            rec['updated_at'] = time.time()
        if changed:
            self.save()
        return changed

    def remove_groups( self, jobs, groups ):
        """Remove group labels from the given jobs. Returns the job names
        that were changed."""
        self._ensure()
        groups = normalise_groups( groups )
        names = { j.get( 'job' ) if isinstance( j, dict ) else str( j ) for j in jobs }
        changed = []
        for rec in self.records:
            if rec.get( 'job' ) not in names:
                continue
            have = rec.setdefault( 'groups', [] )
            for g in groups:
                if g in have:
                    have.remove( g )
                    if rec['job'] not in changed: changed.append( rec['job'] )
            rec['updated_at'] = time.time()
        if changed:
            self.save()
        return changed

    # ------------------------------------------------------------------
    # querying

    def group_names( self ):
        """All group labels in use, sorted."""
        self._ensure()
        names = set()
        for rec in self.records:
            names.update( rec.get( 'groups', [] ) )
        return sorted( names )

    def find( self, where=None, groups=None, state='done',
              match_all_groups=False, rtol=MATCH_RTOL, atol=MATCH_ATOL ):
        """Records matching a partial set of variable values and/or groups.

        Arguments:
            where (dict) : variable values that must match. Only the given
                variables are compared, so ``{'K': 0.2}`` matches every job
                run with that K whatever else varied.
            groups (str|list) : keep jobs carrying any of these labels (all
                of them when ``match_all_groups``).
            state (str) : required job state, ``None`` to accept any.
                Defaults to 'done' - a job that failed or is still running
                has no results to retrieve.
        Returns:
            list of records, in job order.
        """
        self._ensure()
        groups = normalise_groups( groups )
        out = []
        for rec in self.records:
            if state is not None and rec.get( 'state' ) != state:
                continue
            if groups:
                have = rec.get( 'groups', [] )
                hits = [ g for g in groups if g in have ]
                if match_all_groups:
                    if len( hits ) != len( groups ): continue
                elif not hits:
                    continue
            if where:
                rvars = rec.get( 'variables', {} )
                if any( k not in rvars or not values_match( rvars[k], v, rtol, atol )
                        for k, v in where.items() ):
                    continue
            out.append( rec )
        return out

    def find_exact( self, variables, state='done', rtol=MATCH_RTOL, atol=MATCH_ATOL ):
        """The record of the job run with exactly this set of variable
        values (same names, matching values), or None.

        The same design point can legitimately be run more than once (a
        changed deck, a new solver version), so the *most recent* matching
        job wins - it describes the current state of that design point.

        Used for reuse: a job that differs in a variable not mentioned in
        ``variables`` is a different design point and must not be reused.
        """
        self._ensure()
        variables = as_jsonable( variables )
        found = None
        for rec in self.records:
            if state is not None and rec.get( 'state' ) != state:
                continue
            rvars = rec.get( 'variables', {} )
            if set( rvars.keys() ) != set( variables.keys() ):
                continue
            if all( values_match( rvars[k], v, rtol, atol ) for k, v in variables.items() ):
                found = rec
        return found

    def read_outputs( self, job ):
        """Unpickle the action outputs of one job (name or record)."""
        path = self.job_path( job ) / ACTIONS_OUTPUT_PATH
        if not path.exists():
            raise DataNotFoundError( f'No results in {path}: the job did not complete.' )
        with open( path, 'rb' ) as f:
            return pickle.load( f )


# -------------------

class SimulationIterator(WorkAction):
    """
    Used to evaluate different designs in different directories.
    It calls the graph in different subdirectories -- a subdirectory per design.
    Use WorkArea to overwrite the results in a directory.

    This is designed as a top-level action.

    Every job is recorded in a ``jobs_index.json`` at the results root
    (see ``JobIndex`` in this module), which maps the job directories to the
    variable values they were run with and to the group labels they carry.
    That index backs the retrieval methods (``find_jobs``, ``results_for``,
    ``collect``) and ``reuse_existing``, and can be rebuilt from the job
    directories at any time.

    An existing results directory is added to: jobs are numbered after the
    ones already there, so a study can be extended in a later session and
    a finished job is never written over. Pass ``clean_start=True`` to
    delete the results directory first.

    args:
        graph (DirectedGraph) : DirectedGraph or WorkFlow
        parameter_list (list) : Only needed to provided default values to eval. Maybe not needed.
        work_area_path (str) : Default is to ./{graph.name}
        copy_paths (list) :
        clean_start (bool) : delete the results directory (jobs, index and
            all) before starting.
        groups (str|list) : default group label(s) for the jobs this
            iterator runs. Overridden per call by the ``groups`` argument
            of ``solve``/``collect_for_expdes``/``collect_for_varrange``,
            and settable at any time as ``iterator.groups``.
        reuse_existing (bool) : when True, a design point that already has
            a completed job in the results directory is not run again: its
            stored outputs are returned instead. Default False, which runs
            every design point given, whether or not an equivalent job is
            already there.

    Returns:
        dict: Output from graph (it adds nothing).
    """

    JNAME = 'job_'

    def __init__( self, graph, parameter_list=None,
                 work_area_path=None, copy_paths=None, clean_start=False,
                 groups=None, reuse_existing=False):

        assert isinstance( graph, WorkAction )
        #assert isinstance( graph, DirectedGraph ) # ? must be a graph

        super().__init__( graph.name+'_Iter', "", copy_paths=( copy_paths or [] )+graph.copy_paths )

        self.graph = graph
        self.parameter_list = parameter_list

        self.last_job_path = None

        self._check_names( [] )

        self.run_iter = 0
        self.jobs_total = None          # known when collect_for_expdes runs
        self._status_reporter = None    # created on first solve()

        if work_area_path is None:
            work_area_path = Path.cwd().joinpath( self.graph.name )
        
        # Expand ~ and environment variables
        expanded_path = os.path.expandvars(os.path.expanduser(str(work_area_path)))
        self.work_area_path = Path(expanded_path)

        self.groups = groups            # default labels; str or list
        self.reuse_existing = reuse_existing
        self._index = JobIndex( self.work_area_path, job_prefix=self.JNAME )
        self.reused_jobs = []           # jobs loaded instead of re-run

        if clean_start: self.rm_rundir()
        self.description = f'Simulation iterator for graph {graph.name}'

    def rm_rundir( self ):
        sim_path = self.work_area_path
        if sim_path.exists():  shutil.rmtree( sim_path )
        self._index = JobIndex( self.work_area_path, job_prefix=self.JNAME )

    def _check_names( self, name_list=None ):
        """ Cannot have duplicates -- create a problem with callbacks """
        if name_list is None: name_list = []
        if self.name in name_list: raise ActionNameError( f"Duplicate actions name \'{self.name}\'" )
        name_list.append( self.name )
        self.graph._check_names( name_list )

    def _tree_children( self ):
        return [ self.graph ]

    def _work_dir_tree( self ):
        job_children = [
            ( 'iter_variables.json   (this design\'s variable values)', [] ),
            ( 'actions_output.pkl   (this design\'s action outputs)', [] ),
        ]
        job_children += _copy_path_nodes( self.copy_paths )
        job_children += self.graph._work_dir_entries()
        children = [
            ( 'status.json   (run progress: current job, jobs done; see simnexus.progress)', [] ),
            ( 'jobs_index.json   (job -> variable values and group labels; see simnexus.simulation_iterator)', [] ),
            ( f'{self.JNAME}0/   (one directory per design evaluation)', job_children ),
            ( f'{self.JNAME}1/ … {self.JNAME}N/', [] ),
        ]
        return ( f'{_display_path(self.work_area_path)}/   (results root)', children )

    def _work_dir_entries( self ):
        # A SimulationIterator creates its own results directory: contribute
        # it as a subtree rather than flattening files into the parent.
        return [ self._work_dir_tree() ]

    def _in_last_run_dir( func ):
        """ decorator execute last run """
        def wrapper( self, *args, **kwargs ):
            root_dir = Path.cwd()
            os.chdir( self.last_job_path )
            try:
                vals = func( self, *args, **kwargs )
            finally:
                os.chdir( root_dir )
            return vals
        return wrapper

    def write_outputs( self, evals ):
        """
        Called in run subdirectory.
        """
        with open(simnexus.args.ACTIONS_OUTPUT_PATH, 'wb') as f:
            pickle.dump(evals, f)

    def read_outputs( self ):
        """
        Called in run subdirectory.
        """
        with open(simnexus.args.ACTIONS_OUTPUT_PATH, 'rb') as f:
            ret = pickle.load(f)
        return ret

    def gather_outputs( self ):
        """
        The action outputs of every completed job in the results directory,
        in job order.

        Taken from the job index, so a gap in the numbering (a job
        directory deleted or archived) no longer cuts the list short, and
        jobs that failed or are still running are skipped instead of
        raising.

        Returns:
            list: one ``{action_name: value}`` dict per completed job.
        """
        idx = self.job_index()
        ret = []
        for rec in idx.find( state='done' ):
            if not ( idx.job_path( rec ) / simnexus.args.ACTIONS_OUTPUT_PATH ).exists():
                # stale index entry: the directory was removed by hand
                logger.warning( f'Skipping {rec["job"]}: no {simnexus.args.ACTIONS_OUTPUT_PATH}.' )
                continue
            ret.append( idx.read_outputs( rec ) )
        return ret

    @staticmethod
    def outcomes_as_lists( list_of_evals ):
        """
        Transform list of evals (a list of dictionaries) to a dictionary of lists.
        [{'a':1},{'a':1}] -> {'a':[1,2]}

        Args:
            list_of_evals: a list of dictionaries
        Returns:
            dict_lists:  dictionaries of lists
        """
        outcome = None
        for evals in list_of_evals:
            if outcome is None: outcome = {k:[] for k in evals.keys() }
            for k,val in evals.items():
                if k not in outcome.keys(): raise ParameterError( f'Variable \'{k}\' not set in all runs' )
            for k,val in evals.items(): outcome[k].append( val )
        SimulationIterator._subdicts_as_lists( outcome ) # transforms the list of dictionaries into a dictionary of lists.
        return outcome


    def iterdir( self ):
        """
        The run directories of jobs that were previously run, in job order.

        Every job directory present in the results directory is returned,
        including after a gap in the numbering; the former scan stopped at
        the first missing number. Use ``find_jobs`` to select by variable
        value, group or state.

        Returns:
            list: Path instances.
        """
        return self.job_index().iter_job_dirs()


    def _resolve_groups( self, groups=None ):
        """Group labels for a job: the ones given for this call, else the
        iterator's own (constructor argument or ``iterator.groups``)."""
        if groups is None: groups = self.groups
        return normalise_groups( groups )

    def _allocate_job_path( self ):
        """Path of the next job directory.

        The number continues after whatever is already in the results
        directory (index and directories on disk both consulted), so a
        study can be added to across sessions and an existing job is never
        written over. Use ``clean_start=True`` to start from an empty
        results directory instead.
        """
        return self.work_area_path.joinpath( self.JNAME + str( self._index.next_job_number() ) )

    def _report_job( self, job_name ):
        """Run-level progress for external consumers (e.g. a GUI process):
        a status.json at the results root with job counts and current job."""
        if self._status_reporter is None:
            self._status_reporter = StatusReporter( self.name, directory=self.work_area_path )
            self._status_reporter.start( actions=None,
                                         jobs_total=self.jobs_total,
                                         jobs_done=self.run_iter,
                                         current_job=job_name )
        else:
            self._status_reporter.update( state='running',
                                          jobs_total=self.jobs_total,
                                          jobs_done=self.run_iter,
                                          current_job=job_name )

    def _reuse( self, val_dict, job_groups ):
        """Return the stored outputs of a completed job run with exactly
        these variable values, or None when there is no such job.

        The job is re-labelled with this call's groups, so a design point
        computed for one study can be pulled into another without running
        the graph again.
        """
        rec = self._index.find_exact( val_dict )
        if rec is None:
            return None
        job_name = rec['job']
        try:
            ret = self._index.read_outputs( job_name )
        except DataNotFoundError:
            # index says done but the outputs are gone: run it again
            logger.warning( f'Job {job_name} has no {simnexus.args.ACTIONS_OUTPUT_PATH}; re-running.' )
            self._index.set_state( job_name, 'unknown' )
            return None

        if job_groups:
            self._index.add_groups( [ job_name ], job_groups )
        self.last_job_path = self._index.job_path( job_name )
        self.reused_jobs.append( job_name )
        logger.debug( f'Reusing {job_name} for {val_dict}' )

        self._report_job( job_name )
        self.run_iter += 1
        self._status_reporter.update( state='idle', jobs_done=self.run_iter )
        return ret

    def solve(self,  val_dict=None, groups=None ):
        """
        Args:
            val_dict (dict) : variable values for this design point.
            groups (str|list) : group label(s) for this job, overriding
                the iterator's default.

        Returns:
            dict: Output from graph (it adds nothing).
        """

        if val_dict is None: val_dict = {}

        pl = self.parameter_list if self.parameter_list is not None else self.parameters()
        for def_par in pl:
            if def_par.name not in val_dict:
                if def_par.value is None:
                   raise ParameterError( f'Parameter \'{def_par.name}\' must have a value defined in SimulationIterator.solve().' )
                val_dict[def_par.name]=def_par.value

        job_groups = self._resolve_groups( groups )

        if self.reuse_existing:
            reused = self._reuse( val_dict, job_groups )
            if reused is not None:
                return reused

        root_dir = Path.cwd()
        self.last_job_path = self._allocate_job_path()

        self.last_job_path.mkdir(mode=0o777, parents=True, exist_ok=True)

        self._report_job( self.last_job_path.name )

        # record the job before it runs, so an interrupted run still leaves
        # the design point and its group labels in the index
        job_name = self.last_job_path.name
        self._index.record_job( job_name, val_dict, groups=job_groups, state='running' )

        if self.copy_paths is not None:
            logger.debug( f'Copying paths {self.copy_paths}' )
            for fname in self.copy_paths:
                src = Path(fname)
                if not src.exists():
                    raise MissingPathError( f'Path \"{fname}\" not found. Either the path does not exist or you must specify the full path.' )
                if src.is_dir():
                    shutil.copytree(src, self.last_job_path / src.name)
                else:
                    shutil.copy2(src, self.last_job_path)

        os.chdir( self.last_job_path )
        logger.debug( f'Running in directory {self.last_job_path}' )

        try:
            with open( simnexus.args.ITER_VARIABLES_PATH,'w' ) as vf:
                json.dump( as_jsonable( val_dict ), vf )

            ret = self.graph.solve( val_dict )

            self.write_outputs( ret )
        except BaseException:
            self._status_reporter.update( state='failed' )
            self._index.set_state( job_name, 'failed' )
            raise
        finally:
            os.chdir( root_dir )
        self._index.set_state( job_name, 'done' )
        self.run_iter += 1
        self._status_reporter.update( state='idle', jobs_done=self.run_iter )

        return ret

    # ------------------------------------------------------------------
    # retrieving and grouping results already on disk
    #
    # These methods never run the graph. They work on an iterator that was
    # only just constructed (pointed at an existing results directory), so
    # results can be inspected in a separate session or by a GUI.

    def job_index( self, rebuild=False ):
        """The ``JobIndex`` of the results directory.

        Arguments:
            rebuild (bool) : re-derive the index from the job directories
                on disk. Group labels of known jobs are preserved.
        """
        if rebuild:
            self._index.load( rebuild_if_missing=False )
            self._index.rebuild()
        else:
            self._index._ensure()
        return self._index

    def find_jobs( self, where=None, groups=None, state='done', match_all_groups=False ):
        """Paths of the job directories matching variable values and/or groups.

        Arguments:
            where (dict) : variable values to match; only the variables
                given are compared (``{'K': 0.2}`` matches any T).
            groups (str|list) : keep jobs carrying any of these labels
                (all of them when ``match_all_groups``).
            state (str) : required job state, default 'done'; None for any.
        """
        idx = self.job_index()
        return [ idx.job_path( r ) for r in
                 idx.find( where=where, groups=groups, state=state,
                           match_all_groups=match_all_groups ) ]

    def find_job( self, where=None, groups=None, state='done' ):
        """Path of the first matching job directory, or None."""
        hits = self.find_jobs( where=where, groups=groups, state=state )
        return hits[0] if hits else None

    def results_for( self, variables, groups=None ):
        """The stored action outputs of the job run with these variable
        values - the results of a past run, without running the graph.

        A job whose variables are exactly ``variables`` is preferred - the
        most recent one, if the design point was run more than once; a
        partial match is accepted when it is unambiguous.

        Raises:
            DataNotFoundError: when no job matches, or when several jobs
                match only partially. Use ``find_jobs`` or ``collect`` to
                get every job for a design point that was run repeatedly.
        """
        idx = self.job_index()
        rec = idx.find_exact( variables )
        if rec is None:
            hits = idx.find( where=variables, groups=groups )
            if not hits:
                raise DataNotFoundError(
                    f'No completed job in {self.work_area_path} was run with {variables}.' )
            if len( hits ) > 1:
                names = ', '.join( r['job'] for r in hits[:5] )
                raise DataNotFoundError(
                    f'{len(hits)} jobs match {variables} ({names}...): the request is '
                    f'ambiguous. Use find_jobs() or collect() to get them all.' )
            rec = hits[0]
        return idx.read_outputs( rec )

    def variables_of( self, job ):
        """The variable values a job was run with (job name or Path)."""
        idx = self.job_index()
        name = Path( job ).name if isinstance( job, ( str, Path ) ) else job
        for rec in idx.records:
            if rec.get( 'job' ) == name:
                return rec.get( 'variables', {} )
        raise DataNotFoundError( f'No job \'{name}\' in {self.work_area_path}.' )

    def groups_of( self, job ):
        """The group labels of a job (job name or Path)."""
        idx = self.job_index()
        name = Path( job ).name if isinstance( job, ( str, Path ) ) else job
        for rec in idx.records:
            if rec.get( 'job' ) == name:
                return list( rec.get( 'groups', [] ) )
        raise DataNotFoundError( f'No job \'{name}\' in {self.work_area_path}.' )

    def group_names( self ):
        """All group labels in use in this results directory."""
        return self.job_index().group_names()

    def add_groups( self, groups, jobs=None, where=None, state='done' ):
        """Label jobs with one or more groups.

        Give either ``jobs`` (names or Paths) or ``where`` (variable values
        selecting the jobs). Grouping is metadata, so jobs can be labelled
        long after they ran, and a job can be in several groups.

        Returns:
            list: names of the jobs that were changed.
        """
        idx = self.job_index()
        if jobs is None:
            jobs = [ p.name for p in self.find_jobs( where=where, state=state ) ]
        else:
            jobs = [ Path( j ).name if isinstance( j, ( str, Path ) ) else j for j in jobs ]
        return idx.add_groups( jobs, groups )

    def remove_groups( self, groups, jobs=None, where=None, state='done' ):
        """Remove group labels from jobs. See ``add_groups``."""
        idx = self.job_index()
        if jobs is None:
            jobs = [ p.name for p in self.find_jobs( where=where, state=state ) ]
        else:
            jobs = [ Path( j ).name if isinstance( j, ( str, Path ) ) else j for j in jobs ]
        return idx.remove_groups( jobs, groups )

    def collect( self, groups=None, where=None, state='done', match_all_groups=False ):
        """Read back the results of a set of jobs already on disk.

        Returns the same pair as ``collect_for_expdes`` - so a group of
        runs can be plotted or post-processed exactly like a fresh sweep -
        but nothing is executed.

        Arguments:
            groups (str|list) : keep jobs carrying any of these labels.
            where (dict) : variable values to match (partial).
            match_all_groups (bool) : require every label instead of any.

        Returns:
            par_val_dict (dict): variable name -> array of values, one per job.
            outcome (dict): action name -> list of values, one per job.
        """
        idx = self.job_index()
        recs = idx.find( where=where, groups=groups, state=state,
                         match_all_groups=match_all_groups )
        if not recs:
            raise DataNotFoundError(
                f'No completed job in {self.work_area_path} matches '
                f'groups={groups}, where={where}.' )

        list_of_evals = [ idx.read_outputs( r ) for r in recs ]
        outcome = SimulationIterator.outcomes_as_lists( list_of_evals )

        var_names = list( recs[0].get( 'variables', {} ).keys() )
        par_val_dict = {}
        for key in var_names:
            vals = []
            for r in recs:
                if key not in r.get( 'variables', {} ):
                    raise ParameterError( f'Variable \'{key}\' not set in all runs' )
                vals.append( r['variables'][key] )
            par_val_dict[key] = np.array( vals )

        return par_val_dict, outcome

    def outputs(self):
        return self.graph.outputs()

    @staticmethod
    def _subdicts_as_lists( outcome ):
        """
        Rewrites the values of the input dictionary if they are lists of dictionaries.

        This function iterates over the items in the input dictionary `outcome`. For each key-value pair,
        if the value is a list and the first element of the list is a dictionary, it transforms the list 
        of dictionaries into a dictionary of lists. The keys of the new dictionary are the keys of the 
        dictionaries in the list, and the values are lists of the corresponding values from the original 
        dictionaries.

        Args:
            outcome (dict): The input dictionary to be rewritten.

        Returns:
            None: The function modifies the input dictionary in place.
        """
        for k, val_list in outcome.items():
            if len(val_list) > 0:
                if type(val_list[0]) == dict:
                    nd = {kk:[] for kk in val_list[0].keys()}
                    for vv in val_list:
                        for kk in nd.keys():
                            nd[kk].append( vv[kk] )
                    outcome[k] = nd



    def collect_for_varrange( self, var_range_dict, dependent_pars=None, groups=None ):
        """
        Creates a combination of var_range_dict. Input is not a experimental design.

        Args:
            var_range_dict (dict) : variable name, values to combine.
            dependent_pars (dict) : variable name, expression.
            groups (str|list) : group label(s) for the jobs of this sweep,
                overriding the iterator's default.

        Returns:
            par_val_dict (dict): parameter names, value list
            outcome (dict): evaluation name, value list. Value can be list or dict (of lists).
        """

        iterators_values = var_range_dict.values()
        exp_des =  [p for p in product(*iterators_values)]
        var_names = [key for key in var_range_dict.keys() ]
        return self.collect_for_expdes( exp_des, var_names, dependent_pars, groups=groups )

    def collect_for_expdes( self, exp_des, var_names, dependent_pars=None, groups=None ):
        """
        Args:
            exp_des
            groups (str|list) : group label(s) for the jobs of this sweep,
                overriding the iterator's default.

        Returns:
            par_val_dict (dict): parameter names, value list
            outcome (dict): evaluation name, value list. Value can be list or dict (of lists).
        """
        disp = []
        more_node_data = []

        self.jobs_total = len( exp_des )

        all_combinations = []
        list_of_evals = []
        for iexp, combination in enumerate(exp_des):
            all_combinations.append( combination )

            pars_vals = {key:combination[i] for i,key in enumerate(var_names) }
            if dependent_pars is not None:
                dp_dict = {}
                for key in dependent_pars:
                    dp_dict[key] = eval( dependent_pars[key], {}, pars_vals )
            else:
                dp_dict = {}
            pars_vals.update( dp_dict )
            logger.debug( f'\n\tRunning evaluation {iexp+1} of {len(exp_des)} {pars_vals}' )
            logger.debug( f'\n\t Parameters: {pars_vals}' )
            logger.debug(   f'\t Dependent parameters: {dependent_pars}' )
            evals = self.solve( pars_vals, groups=groups )
            for k,v in evals.items():
                if isinstance(v,numbers.Number):
                    logger.debug( f'\t\t Result: {k},{v}' )
                else:
                    logger.debug( f'\t\t Result: {k},{type(v)}' )

            list_of_evals.append( evals )

        outcome = SimulationIterator.outcomes_as_lists( list_of_evals )

        if self._status_reporter is not None:
            self._status_reporter.update( state='done' )

        all_combinations = np.array( all_combinations )
        par_val_dict = {key: None for key in var_names }
        for i, key in enumerate( var_names ):
            par_val_dict[key] = all_combinations[:,i]

        return par_val_dict, outcome

    def parameters(self):
        if self._parameters_cache is not None:
            return self._parameters_cache
        tmp_path = self.work_area_path / 'variables_discovery'
        tmp_path.mkdir(mode=0o777, parents=True, exist_ok=True)

        if self.copy_paths:
            logger.debug(f'Copying paths {self.copy_paths}')
            for fname in self.copy_paths:
                src = Path(fname)
                if not src.exists():
                    raise MissingPathError(f'Path "{fname}" not found. Either the path does not exist or you must specify the full path.')
                if src.is_dir():
                    shutil.copytree(src, tmp_path / src.name, dirs_exist_ok=True)
                else:
                    shutil.copy2(src, tmp_path)

        root_dir = Path.cwd()
        os.chdir(tmp_path)
        try:
            vrs = self.graph.parameters()
        finally:
            os.chdir(root_dir)
        self._parameters_cache = vrs
        return vrs
