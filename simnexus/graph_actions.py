from pathlib import Path
import os,shutil
import json
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from itertools import product
import pickle
import numbers

import numpy as np

from simnexus.actions import WorkAction
from simnexus.errors import SimNexusError, ActionNameError, ParameterError, MissingPathError, AsyncActionError
from simnexus.progress import StatusReporter
from simnexus.util.observer import Observer
import simnexus.args

import logging
logger = logging.getLogger(__name__)


def _display_path( path ):
    """Show a work path relative to the current directory when it lives
    underneath it, otherwise as-is. Keeps nested directory trees readable."""
    try:
        return str( Path( path ).relative_to( Path.cwd() ) )
    except ValueError:
        return str( path )


def _copy_path_nodes( copy_paths ):
    """Build work-directory tree nodes for files/dirs that get copied in."""
    nodes = []
    seen = set()
    for cp in copy_paths:
        p = Path( cp )
        name = p.name + ( '/' if p.is_dir() else '' )
        if name in seen:
            continue
        seen.add( name )
        nodes.append( ( f'{name}   (copied in)', [] ) )
    return nodes

class WorkArea(WorkAction):
    """
    Evaluates graph in a seperate directory.
    Previous results in the directory are overwritten.
    Required files may be copied to this area.

    Use SimulationIterator if you wish to have a subdirectory
    for each design evaluated.

    Arguments:
        graph (DirectedGraph) : DirectedGraph or WorkFlow  
        work_area_path (str) : Default is to ./{graph.name}
        copy_paths (list) : List of names of file to be copied to work area.
    Returns:
        dict: Output from graph (it adds nothing).
    """

    def __init__( self, graph, work_area_path=None, copy_paths=None ):

        assert isinstance( graph, DirectedGraph )
        super().__init__( graph.name+'_WorkArea', "", copy_paths=( copy_paths or [] )+graph.copy_paths )
        self.graph = graph
        if work_area_path is None:
            # Keep the default relative (./{graph.name}) so the work area is
            # created under the *current* directory at run time. This lets a
            # WorkArea nest inside a SimulationIterator's per-design job
            # directory instead of being created next to it (baking in the
            # cwd at construction time put it outside the job directory).
            work_area_path = self.graph.name

        # Expand ~ and environment variables
        expanded_path = os.path.expandvars(os.path.expanduser(str(work_area_path)))
        self.work_area_path = Path(expanded_path)

        self.description = f'Work area for graph {graph.name} at {self.work_area_path}'


    def _prepare_work_area(self):
        """Create the work area directory and copy all required files into it."""
        self.wa_path = self.work_area_path
        self.wa_path.mkdir(mode=0o777, parents=True, exist_ok=True)

        if self.copy_paths:
            logger.debug(f'Copying paths {self.copy_paths}')
            for fname in self.copy_paths:
                src = Path(fname)
                if not src.exists():
                    raise MissingPathError(f'Path "{fname}" not found. Either the path does not exist or you must specify the full path.')
                if src.is_dir():
                    shutil.copytree(src, self.wa_path / src.name, dirs_exist_ok=True)
                else:
                    shutil.copy2(src, self.wa_path)

    def parameters(self):
        if self._parameters_cache is not None:
            return self._parameters_cache
        self._prepare_work_area()
        root_dir = Path.cwd()
        os.chdir(self.wa_path)
        try:
            vrs = self.graph.parameters()
        finally:
            os.chdir(root_dir)
        self._parameters_cache = vrs
        return vrs

    def outputs(self):
        return self.graph.outputs()


    def rm_rundir( self ):
        sim_path = self.work_area_path
        if sim_path.exists():  shutil.rmtree( sim_path )

    def _clean_inrundir( self ):
        sim_path = self.work_area_path
        if sim_path.exists():
            for item in sim_path.iterdir():
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()


    def solve(self,  val_dict=None ):
        """
        Returns:
            dict: Output from graph (it adds nothing).
        """

        if self.work_area_path.exists():
            self._clean_inrundir()

        self._prepare_work_area()

        root_dir = Path.cwd()
        os.chdir( self.wa_path )
        logger.debug( f'Running in directory {self.wa_path}' )

        try:
            ret = self.graph.solve( val_dict )
        finally:
            os.chdir( root_dir )

        return ret

    def _check_names( self, name_list=None ):
        """ Cannot have duplicates -- create a problem with callbacks """
        if name_list is None: name_list = []
        if self.name in name_list: raise ActionNameError( f"Duplicate actions name \'{self.name}\'" )
        name_list.append( self.name )
        self.graph._check_names( name_list )

    def _tree_children( self ):
        return [ self.graph ]

    def _work_dir_tree( self ):
        children = _copy_path_nodes( self.copy_paths ) + self.graph._work_dir_entries()
        return ( f'{_display_path(self.work_area_path)}/   (work area, overwritten each run)', children )

    def _work_dir_entries( self ):
        # A WorkArea creates its own directory: contribute it as a subtree
        # rather than flattening files into the parent directory.
        return [ self._work_dir_tree() ]





class SimulationIterator(WorkAction):
    """
    Used to evaluate different designs in different directories.
    It calls the graph in different subdirectories -- a subdirectory per design.
    Use WorkArea to overwrite the results in a directory.

    This is designed as a top-level action.

    args:
        graph (DirectedGraph) : DirectedGraph or WorkFlow  
        parameter_list (list) : Only needed to provided default values to eval. Maybe not needed.
        work_area_path (str) : Default is to ./{graph.name}
        copy_paths (list) : 
        clean_start (bool) : 

    Returns:
        dict: Output from graph (it adds nothing).
    """

    JNAME = 'job_'

    def __init__( self, graph, parameter_list=None,
                 work_area_path=None, copy_paths=None, clean_start=False):

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

        if clean_start: self.rm_rundir()
        self.description = f'Simulation iterator for graph {graph.name}'

    def rm_rundir( self ):
        sim_path = self.work_area_path
        if sim_path.exists():  shutil.rmtree( sim_path )

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
        Called in root subdirectory.
        """

        dir_idx = 0
        root_dir = Path.cwd()
        wrk_dir = self.work_area_path.joinpath( self.JNAME + str( dir_idx ) )

        ret = []
        try:
            while wrk_dir.exists():
                os.chdir( wrk_dir )
                ret.append( self.read_outputs() )
                dir_idx += 1
                wrk_dir = self.work_area_path.joinpath( self.JNAME + str( dir_idx ) )
                os.chdir( root_dir )
        finally:
            os.chdir( root_dir )

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
        Iterator for the run directories. These are jobs that were previously run.

        Returns:
            Path instances.
        """

        dirs = []

        j_iter = 0

        root_dir = Path.cwd()
        #job_path = root_dir.joinpath( self.name )
        job_path = self.work_area_path
        job_path = job_path.joinpath( self.JNAME + str( j_iter ) )
        while job_path.exists() :
            dirs.append( job_path )
            j_iter = j_iter + 1
            #job_path = root_dir.joinpath( self.name )
            job_path = self.work_area_path
            job_path = job_path.joinpath( self.JNAME + str( j_iter ) )
        
        return dirs


    def solve(self,  val_dict=None ):
        """
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

        root_dir = Path.cwd()
        self.last_job_path = self.work_area_path
        self.last_job_path = self.last_job_path.joinpath( self.JNAME + str( self.run_iter ) )

        #sim_path = Path.cwd().joinpath( self.name )
        sim_path = self.work_area_path
        #if 0 == self.run_iter and sim_path.exists():
        if 0 == self.run_iter and self.last_job_path.exists():
            raise SimNexusError( f'Results directory {sim_path} already exists. Restart is not yet supported.' )

        self.last_job_path.mkdir(mode=0o777, parents=True, exist_ok=True)

        # run-level progress for external consumers (e.g. a GUI process):
        # a status.json at the results root with job counts and current job
        if self._status_reporter is None:
            self._status_reporter = StatusReporter( self.name, directory=self.work_area_path )
            self._status_reporter.start( actions=None,
                                         jobs_total=self.jobs_total,
                                         jobs_done=self.run_iter,
                                         current_job=self.last_job_path.name )
        else:
            self._status_reporter.update( state='running',
                                          jobs_total=self.jobs_total,
                                          jobs_done=self.run_iter,
                                          current_job=self.last_job_path.name )

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
            with open( 'iter_variables.json','w' ) as vf:
                json.dump( val_dict, vf )

            ret = self.graph.solve( val_dict )

            self.write_outputs( ret )
        except BaseException:
            self._status_reporter.update( state='failed' )
            raise
        finally:
            os.chdir( root_dir )
        self.run_iter += 1
        self._status_reporter.update( state='idle', jobs_done=self.run_iter )

        return ret

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



    def collect_for_varrange( self, var_range_dict, dependent_pars=None ):
        """
        Creates a combination of var_range_dict. Input is not a experimental design.

        Returns:
            par_val_dict (dict): parameter names, value list
            outcome (dict): evaluation name, value list. Value can be list or dict (of lists).
        """

        iterators_values = var_range_dict.values()
        exp_des =  [p for p in product(*iterators_values)]
        var_names = [key for key in var_range_dict.keys() ]
        return self.collect_for_expdes( exp_des, var_names, dependent_pars )

    def collect_for_expdes( self, exp_des, var_names, dependent_pars=None ):
        """
        Args:
            exp_des

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
            evals = self.solve( pars_vals )
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

# -------------------

class DirectedGraph(WorkAction, Observer):
    
    """
    A directed graph used to determine the order of evaluation and
    dependencies.

    Used e.g. for MDO for solvers run in parallel.

    A graph will append any computed results to
    val_dict and return that. 
    So A.solve( {'v1':1.2} ) may return {'v1':1.2, 'A':3.4},
    where the 'A':3.4 was added with 'A' the name of the action.

    Arguments:
        name (str) : 
        asynch (list) : 
        work_area_path (str) : 
    Returns:
        dict: Dictionary containing action_name:action_result pairs
    """ 

    def __init__(self, name, asynch=False, work_area_path=None):
        #self.adjacency_list = defaultdict(list)
        super().__init__( name, copy_paths=[] )
        self.parent_list = defaultdict(list)
        self.child_actions = {}
        self.finished, self.started, self.failed = set(), set(), set()
        self.asynch = asynch
        self.work_area_path = work_area_path
        if self.work_area_path:
            self.work_area = WorkArea( self, work_area_path=self.work_area_path )
        else:
            self.work_area = None
        self.description = f'Directed graph {name}'

    def add_action(self, action, parents=None):
        """
        Add a node to the graph.

        args:
            action (action) :
            parents (list) : Creates an graph edge from the parent actions to this node. The action will wait for the parent actions to finish.
        """
        if not isinstance(action, WorkAction):
            raise TypeError("Node must be an instance of WorkAction")
        if action.name in self.child_actions.keys():
            raise NameError(f'Cannot re-use an action name \'{action.name}\'')
        self.child_actions[action.name] = action
        if parents is not None: 
            for p in parents: self.add_edge( p, action )
        action.attach( self )
        self.copy_paths.extend( action.copy_paths )
        return action

    def add_edge(self, from_node, to_node):
        if from_node.name not in self.child_actions or to_node.name not in self.child_actions:
            raise ValueError("Both nodes must be added to the graph before creating an edge")
        self.parent_list[to_node.name].append(from_node.name)


    def _parent_results(self, nname, val_dict ):
        # Results are kept structured: a WorkArea or sub-graph contributes
        # its outputs as a nested dict under its own name. Downstream actions
        # receive them as-is; a MathEvaluation flattens this namespace itself
        # so its expression can reference nested action outputs by name.
        if self.parent_list[nname] == []:
            return val_dict
        p_list = [ self.child_actions[p] for p in self.parent_list[nname] ]
        in_dict = { k:v for p in p_list for k,v in p.results().items() }
        return in_dict

    def solve(self, val_dict=None):
        """
        A graph will append any computed results to
        val_dict and return that.
        So A.solve( {'v1':1.2} ) may return {'v1':1.2, 'A':3.4},
        where the 'A':3.4 was added with 'A' the name of the action.

        Returns:
            dict: Dictionary containing action_name:action_result pairs
                  appended to val_dict.
        """

        if val_dict is None: val_dict = {}

        if self.work_area:
            if not hasattr(self, '_in_work_area') or not self._in_work_area:
                self._in_work_area = True
                try:
                    return self.work_area.solve(val_dict)
                finally:
                    self._in_work_area = False

        source_names = []
        parent_names = set()
        for nname, node in self.child_actions.items():
            if self.parent_list[nname] == []:
                source_names.append( node.name )
            else:
                for p in self.parent_list[nname]:
                    parent_names.add(p)
            if nname in val_dict: raise ActionNameError( f'Name \'{nname}\' used for both variables and actions.' )
        drain_names = []
        for nname, node in self.child_actions.items():
            if nname not in parent_names:
                drain_names.append(nname)

        self.finished, self.started, self.failed = set(), set(), set()

        # progress for external consumers (e.g. a GUI process): a status.json
        # in the run directory, updated on every action state change
        reporter = StatusReporter( self.name )
        reporter.start( actions=list( self.child_actions.keys() ) )

        # A graph nested inside an owning graph's directory has an inactive
        # reporter; report through the owner's instead, so this graph's
        # action states and solver fractions still reach the status file.
        report_to = reporter if reporter.active else self._progress_reporter
        if report_to is None:
            report_to = reporter

        reported_done = set()

        def _sweep_done():
            """Report actions that finished since the last sweep.
            Copies self.finished: async watcher threads mutate it."""
            newly_done = set( self.finished ) - reported_done
            for done_name in newly_done:
                report_to.action_state( done_name, 'done' )
                reported_done.add( done_name )
            return bool( newly_done )

        current_name = None
        try:
            # start as parents are ready, and wait till all done
            while len(self.finished) < len(self.child_actions):
                if self.failed:
                    # an asynchronous child failed: report, stop the other
                    # running children, and abort the graph
                    current_name = None
                    self._abort_on_async_failure( report_to, _sweep_done )
                progressed = False
                for nname, node in self.child_actions.items():
                    if nname in self.finished:
                        continue
                    if all(parent in self.finished for parent in self.parent_list[nname]):
                        in_dict = self._parent_results( nname, val_dict )
                        if node.name not in self.started:
                            current_name = nname
                            node._progress_reporter = report_to
                            report_to.action_state( nname, 'running' )
                            if self.asynch:
                                node._observed_eval_async(in_dict.copy())
                            else:
                                node._observed_eval(in_dict.copy())
                            self.started.add(node.name)
                            progressed = True
                            # a sync eval finished just now: report it done
                            # before the next action starts
                            _sweep_done()
                if _sweep_done():
                    progressed = True
                if not progressed:
                    # every startable action is already running (asynch mode):
                    # pace the wait instead of spinning a core
                    time.sleep( 0.05 )

            _sweep_done()

            for nname in drain_names:
                node = self.child_actions[nname]
                # Merge each terminal node's results as-is. Sub-graphs and
                # WorkAreas stay nested under their own name, preserving structure
                # and provenance (and avoiding name collisions between branches).
                val_dict.update( node.results() )

            for n,e in self.child_actions.items():
                e._dump( val_dict )
        except BaseException:
            # actions that did complete before the failure still show as done
            _sweep_done()
            if current_name is not None and current_name not in self.finished:
                report_to.action_state( current_name, 'failed' )
            reporter.finish( 'failed' )
            raise

        reporter.finish( 'done' )
        return val_dict


    def _abort_on_async_failure( self, report_to, sweep_done ):
        """
        An asynchronous child process failed (raised, crashed, or returned
        no result). Report the failure, terminate the children still
        running -- their results could not be used anyway -- and raise
        AsyncActionError with the child's error (traceback included).
        """
        sweep_done()
        failed_names = set( self.failed )   # copy: watcher threads mutate it
        for fname in failed_names:
            err = getattr( self.child_actions[fname], '_async_error', None )
            first_line = str( err ).splitlines()[0] if err else None
            report_to.action_state( fname, 'failed', message=first_line )

        for sname in self.started - set( self.finished ) - failed_names:
            proc = getattr( self.child_actions[sname], '_async_proc', None )
            if proc is not None and proc.is_alive():
                proc.terminate()
                proc.join( timeout=2.0 )
            report_to.action_state( sname, 'failed',
                                    message='terminated: a sibling action failed' )

        first = sorted( failed_names )[0]
        err = getattr( self.child_actions[first], '_async_error', None )
        raise AsyncActionError(
            f"Asynchronous action '{first}' failed: {err or 'unknown error'}" )

    def update(self, message):
        """
        From observer pattern. Called by actions that have finished
        (``[action, 'Done']``) or failed asynchronously
        (``[action, 'Failed']``).

        Arguments:
            message (any) :
        """
        nname = message[0].name
        if len(message) > 1 and message[1] == 'Failed':
            logger.debug( f'Observed action \'{nname}\' failed.' )
            self.failed.add(nname)
            return
        logger.debug( f'Observed action \'{nname}\' finished.' )
        self.finished.add(nname)


    def outputs(self):
        """
        Collects outputs of all child actions.

        Returns:
            dict: {action_name: (data_type, description)}
        """
        result = {}
        for n, e in self.child_actions.items():
            out = e.outputs()
            if isinstance(out, dict):
                result.update(out)
            else:
                result[e.name] = out
        return result

    def _check_names( self, name_list=None ):
        """ Cannot have duplicates -- create a problem with callbacks """
        if name_list is None: name_list = []
        if self.name in name_list: raise ActionNameError( f"Duplicate actions name \'{self.name}\'" )
        name_list.append( self.name )
        for n,e in self.child_actions.items():
            e._check_names( name_list )

    def get_action(self, name ):
        return self.child_actions[name]

    def _tree_children( self ):
        return list( self.child_actions.values() )

    def _work_dir_entries( self ):
        """Child actions of a graph run in the same directory, so their
        produced files are aggregated here. Children that create their own
        directory (a WorkArea, SimulationIterator, or a graph with its own
        work area) contribute that directory as a subtree instead."""
        if self.work_area is not None:
            return [ self.work_area._work_dir_tree() ]
        entries = [ ( 'status.json   (live action states; see simnexus.progress)', [] ) ]
        seen = { entries[0][0] }
        for ch in self.child_actions.values():
            for node in ch._work_dir_entries():
                if node[0] in seen:
                    continue
                seen.add( node[0] )
                entries.append( node )
        return entries

    def _work_dir_tree( self ):
        if self.work_area is not None:
            return self.work_area._work_dir_tree()
        return ( './   (current working directory)', self._work_dir_entries() )

    def parameters(self ):
        if self._parameters_cache is not None:
            return self._parameters_cache
        vrs = []
        for ch in self.child_actions.values():
            self._merge_parameters( vrs, ch.parameters() )
        self._parameters_cache = vrs
        return vrs

    def __str__(self ):
        r = f'DirectedGraph: \'{self.name}\' {type(self)}\n' 
        for a in self.child_actions.values():
            r = r + f'\tChild: {a}\n' 
        return r



class WorkFlow(DirectedGraph):
    """
    Calls a chain of evaluations. Results get passed down the chain.
    Used when everything is sequential.

    Arguments:
        name (str) : 
        actions (list) : 
        work_area_path (str) : 
    Returns:
        dict: Dictionary containing action_name:action_result pairs
    """

    def __init__( self, name, actions=None, work_area_path=None ):
        super().__init__( name, work_area_path=work_area_path )
        self.sequence = []
        if actions is not None:
            for e in actions: self.add_action(e)
        self.description = f'Workflow {name}'

    def add_action( self, action ):
        """
        Adds action to workflow.

        Arguments:
            name (action) : Action to add
        """
        assert action.name != 'objective',  'objective is set using the \'set_call_protocol\' method.'
        action.parent = self

        super().add_action(action)
        if len(self.sequence) > 0 :
            self.add_edge(self.sequence[-1], action)

        self.sequence.append( action )

        return action


