from pathlib import Path
import os,shutil
import json
from abc import ABC, abstractmethod
from collections import defaultdict
from itertools import product
import pickle
import numbers

import numpy as np

from simnexus.actions import WorkAction
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

    def __init__( self, graph, work_area_path=None, copy_paths=[] ):

        assert isinstance( graph, DirectedGraph ) 
        super().__init__( graph.name+'_WorkArea', "", copy_paths=copy_paths+graph.copy_paths )
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
            logger.info(f'Copying paths {self.copy_paths}')
            for fname in self.copy_paths:
                src = Path(fname)
                if not src.exists():
                    exit(f'Path "{fname}" not found. Either the path does not exist or you must specify the full path.')
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
        logger.info( f'Running in directory {self.wa_path}' )

        ret = self.graph.solve( val_dict )

        os.chdir( root_dir )

        return ret

    def _check_names( self, name_list=[] ):
        """ Cannot have duplicates -- create a problem with callbacks """
        if self.name in name_list: exit( f" *** Error Duplicate actions name \'{self.name}\'" )
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
                 work_area_path=None, copy_paths=[], clean_start=False):

        assert isinstance( graph, WorkAction ) 
        #assert isinstance( graph, DirectedGraph ) # ? must be a graph

        super().__init__( graph.name+'_Iter', "", copy_paths=copy_paths+graph.copy_paths )

        self.graph = graph
        self.parameter_list = parameter_list

        self.last_job_path = None

        self._check_names( [] )

        self.run_iter = 0

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

    def _check_names( self, name_list=[] ):
        """ Cannot have duplicates -- create a problem with callbacks """
        if self.name in name_list: exit( f" *** Error Duplicate actions name \'{self.name}\'" )
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
            vals = func( self, *args, **kwargs )
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
        #wrk_dir = Path.cwd().joinpath( self.name ).joinpath( self.JNAME + str( dir_idx ) )
        wrk_dir = self.work_area_path.joinpath( self.JNAME + str( dir_idx ) )

        ret = []
        while wrk_dir.exists():
            os.chdir( wrk_dir )
            ret.append( self.read_outputs() )
            dir_idx += 1
            #wrk_dir = root_dir.joinpath( self.name ).joinpath( self.JNAME + str( dir_idx ) )
            wrk_dir = self.work_area_path.joinpath( self.JNAME + str( dir_idx ) )
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
                if k not in outcome.keys(): exit( f' *** ERROR Variable \'{k}\' not set in all runs' )
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
        
        pl = self.parameter_list if self.parameter_list is not None else self.parameters()
        for def_par in pl:
            if def_par.name not in val_dict:
                if def_par.value is None:
                   exit( f' *** Error Parameter \'{def_par.name}\' must have a value defined in SimulationIterator.solve().' )
                val_dict[def_par.name]=def_par.value

        root_dir = Path.cwd()
        self.last_job_path = self.work_area_path
        self.last_job_path = self.last_job_path.joinpath( self.JNAME + str( self.run_iter ) )

        #sim_path = Path.cwd().joinpath( self.name )
        sim_path = self.work_area_path
        #if 0 == self.run_iter and sim_path.exists():
        if 0 == self.run_iter and self.last_job_path.exists():
            exit( f' *** Error Results directory {sim_path} already exists. Restart is not yet supported.' )

        self.last_job_path.mkdir(mode=0o777, parents=True, exist_ok=True)

        if self.copy_paths is not None:
            logger.info( f'Copying paths {self.copy_paths}' )
            for fname in self.copy_paths:
                src = Path(fname)
                if not src.exists():
                    exit( f'Path \"{fname}\" not found. Either the path does not exist or you must specify the full path.' )
                if src.is_dir():
                    shutil.copytree(src, self.last_job_path / src.name)
                else:
                    shutil.copy2(src, self.last_job_path)

        os.chdir( self.last_job_path )
        logger.info( f'Running in directory {self.last_job_path}' )

        with open( 'iter_variables.json','w' ) as vf:
            json.dump( val_dict, vf )

        ret = self.graph.solve( val_dict )

        self.write_outputs( ret )

        os.chdir( root_dir )
        self.run_iter += 1

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
            print( f'\n\tRunning evaluation {iexp+1} of {len(exp_des)} {pars_vals}' )
            logger.info( f'\n\t Parameters: {pars_vals}' )
            logger.info(   f'\t Dependent parameters: {dependent_pars}' )
            evals = self.solve( pars_vals )
            for k,v in evals.items():
                if isinstance(v,numbers.Number):
                    logger.info( f'\t\t Result: {k},{v}' )
                else:
                    logger.info( f'\t\t Result: {k},{type(v)}' )

            list_of_evals.append( evals )

        outcome = SimulationIterator.outcomes_as_lists( list_of_evals )

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
            logger.info(f'Copying paths {self.copy_paths}')
            for fname in self.copy_paths:
                src = Path(fname)
                if not src.exists():
                    exit(f'Path "{fname}" not found. Either the path does not exist or you must specify the full path.')
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
        if self.parent_list[nname] == []:
            return val_dict
        p_list = [ self.child_actions[p] for p in self.parent_list[nname] ]
        in_dict = { k:v for p in p_list for k,v in p.results().items() }
        return in_dict

    def solve(self, val_dict={}):
        """
        A graph will append any computed results to
        val_dict and return that. 
        So A.solve( {'v1':1.2} ) may return {'v1':1.2, 'A':3.4},
        where the 'A':3.4 was added with 'A' the name of the action.

        Returns:
            dict: Dictionary containing action_name:action_result pairs
                  appended to val_dict.
        """

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
            if nname in val_dict: exit( f' *** ERROR Name \'{nname}\' used for both variables and actions.' )
        drain_names = []
        for nname, node in self.child_actions.items():
            if nname not in parent_names:
                drain_names.append(nname)

        self.finished, self.started = set(), set()

        # start as parents are ready, and wait till all done
        while len(self.finished) < len(self.child_actions):
            for nname, node in self.child_actions.items():
                if nname in self.finished:
                    continue
                if all(parent in self.finished for parent in self.parent_list[nname]):
                    in_dict = self._parent_results( nname, val_dict )
                    if node.name not in self.started:
                        if self.asynch:
                            node._observed_eval_async(in_dict.copy())
                        else:
                            node._observed_eval(in_dict.copy())
                        self.started.add(node.name)
                    
        for nname in drain_names:
            node = self.child_actions[nname]
            nret = node.results()
            if isinstance( node, DirectedGraph ):  # Flatten, but maybe it should be nested
                        val_dict.update( nret[node.name] )
            elif isinstance( node, WorkArea ):
                        # A WorkArea wraps a graph and adds nothing of its own:
                        # flatten the wrapped graph's outputs into val_dict and
                        # record the WorkArea's own contribution as None instead
                        # of leaving the graph's dict nested under its name.
                        val_dict.update( nret[node.name] )
                        val_dict[node.name] = None
            else:
                        val_dict.update( nret )
    
        for n,e in self.child_actions.items():
            e._dump( val_dict )

        return val_dict


    def update(self, message):
        """
        From observer pattern. Called by actions that have finished.

        Arguments:
            message (any) :
        """
        nname = message[0].name
        logger.info( f'Observed action \'{nname}\' finished.' )
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

    def _check_names( self, name_list=[] ):
        """ Cannot have duplicates -- create a problem with callbacks """
        if self.name in name_list: exit( f" *** Error Duplicate actions name \'{self.name}\'" )
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
        entries = []
        seen = set()
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


