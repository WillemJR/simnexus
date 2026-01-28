from pathlib import Path
import os,shutil
import json
from abc import ABC, abstractmethod
from collections import defaultdict
from itertools import product
import pickle
import numbers

import numpy as np

from simflow.actions import WorkAction
from simflow.util.observer import Observer
import simflow.args

import logging
logger = logging.getLogger(__name__)

class WorkArea(WorkAction):
    """
    Evaluates graph in a seperate directory.
    Previous results in the directory are overwritten.
    Required files may be copied to this area.
    This can be nested with other WorkAreas (?).

    Arguments:
        graph (DirectedGraph) : DirectedGraph or WorkFlow  
        work_area_path (str) : Default is to ./{graph.name}
        copy_files (list) : List of names of file to be copied to work area.
    Returns:
        dict: Output from graph (it adds nothing).
    """

    def __init__( self, graph, work_area_path=None, copy_files=None ):

        super().__init__( graph.name+'_WorkArea', "" )
        assert isinstance( graph, DirectedGraph ) # ?
        self.graph = graph
        self.copy_paths = copy_files
        if work_area_path is None:
            work_area_path = Path.cwd().joinpath( self.graph.name )
        self.work_area_path = Path( work_area_path )

        self._reset_file_paths()


    def _reset_file_paths( self ):
        """
        If solver has '../par_tens.k', then that is no longer correct from
        the iterator directory.
        So if the file is copied then reset the name to be local .
        """
        pass
        #for e in self.graph.child_actions:
        #        if e.fea_file_path in self.copy_paths:
        #            e.fea_file_path = Path( e.fea_file_path ).name



    def eval_types(self):
        return self.graph.eval_types()


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


    def eval(self,  val_dict=None ):
        # see base class
        
        sim_path = self.work_area_path
        if sim_path.exists():
            self._clean_inrundir()

        root_dir = Path.cwd()
        #self.wa_path = root_dir.joinpath( self.name )
        self.wa_path = self.work_area_path
        self.wa_path.mkdir(mode=0o777, parents=True, exist_ok=True)

        if self.copy_paths is not None:
            logger.info( f'Copying files {self.copy_paths}' )
            #print( f'Copying files {self.copy_paths}' )
            for fname in self.copy_paths:
                if not Path( fname ).exists():
                    exit( f'File \"{fname}\" not found. Either the file does not exists or you must specify the full path.' )
                shutil.copy2( fname, self.wa_path )

        os.chdir( self.wa_path )
        logger.info( f'Running in directory {self.wa_path}' )

        ret = self.graph.eval( val_dict )

        os.chdir( root_dir )

        return ret

    def _check_names( self, name_list=[] ):
        """ Cannot have duplicates -- create a problem with callbacks """
        if self.name in name_list: exit( f" *** Error Duplicate actions name \'{self.name}\'" )
        name_list.append( self.name )
        self.graph._check_names( name_list )





class SimulationIterator(WorkAction):
    """
    Calls a graph in different subdirectories -- a subdirectory per design.
    Used to iterate over different parameters/design values.

    args:
        name (str) :
        graph (DirectedGraph) : DirectedGraph or WorkFlow  
        parameter_list (list) : Only needed to provided default values to eval.
        copy_files (list) : 
        clean_start (bool) : 

    Returns:
        dict: Output from graph (it adds nothing).
    """

    def __init__( self, name, graph, parameter_list=[], copy_files=None, clean_start=False):

        super().__init__( name, "" )

        # todo copy_files
        #assert isinstance( graph, DirectedGraph ) # ? must be a graph

        self.graph = graph
        self.parameter_list = parameter_list
        self.copy_paths = copy_files

        self.last_job_path = None

        if clean_start: self.rm_rundir()
        self._check_names( [] )

        self.run_iter = 0

    def rm_rundir( self ):
        sim_path = Path.cwd().joinpath( self.name )
        if sim_path.exists():  shutil.rmtree( sim_path )

    def _check_names( self, name_list=[] ):
        """ Cannot have duplicates -- create a problem with callbacks """
        if self.name in name_list: exit( f" *** Error Duplicate actions name \'{self.name}\'" )
        name_list.append( self.name )
        self.graph._check_names( name_list )

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
        with open(simflow.args.ACTIONS_OUTPUT_PATH, 'wb') as f:
            pickle.dump(evals, f)

    def read_outputs( self ):
        """
        Called in run subdirectory.
        """
        with open(simflow.args.ACTIONS_OUTPUT_PATH, 'rb') as f:
            ret = pickle.load(f)
        return ret

    def gather_outputs( self ):
        """
        Called in root subdirectory.
        """

        dir_idx = 0
        root_dir = Path.cwd()
        wrk_dir = Path.cwd().joinpath( self.name ).joinpath( 'job_' + str( dir_idx ) )

        ret = []
        while wrk_dir.exists():
            os.chdir( wrk_dir )
            ret.append( self.read_outputs() )
            dir_idx += 1
            wrk_dir = root_dir.joinpath( self.name ).joinpath( 'job_' + str( dir_idx ) )
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
        job_path = root_dir.joinpath( self.name )
        job_path = job_path.joinpath( 'job_' + str( j_iter ) )
        while job_path.exists() :
            dirs.append( job_path )
            j_iter = j_iter + 1
            job_path = root_dir.joinpath( self.name )
            job_path = job_path.joinpath( 'job_' + str( j_iter ) )
        
        return dirs


    def eval(self,  val_dict=None ):
        # see base class
        
        for def_par in self.parameter_list:
            if def_par.name not in val_dict: val_dict[def_par.name]=def_par.value

        sim_path = Path.cwd().joinpath( self.name )
        if 0 == self.run_iter and sim_path.exists():
            exit( f' *** Error Results directory {sim_path} already exists. Restart is not yet supported.' )

        root_dir = Path.cwd()
        self.last_job_path = root_dir.joinpath( self.name )
        self.last_job_path = self.last_job_path.joinpath( 'job_' + str( self.run_iter ) )
        self.last_job_path.mkdir(mode=0o777, parents=True, exist_ok=True)

        if self.copy_paths is not None:
            logger.info( f'Copying files {self.copy_paths}' )
            for fname in self.copy_paths:
                if not Path( fname ).exists():
                    exit( f'File \"{fname}\" not found. Either the file does not exists or you must specify the full path.' )
                shutil.copy2( fname, self.last_job_path )

        os.chdir( self.last_job_path )
        logger.info( f'Running in directory {self.last_job_path}' )

        with open( 'iter_variables.json','w' ) as vf:
            json.dump( val_dict, vf )

        ret = self.graph.eval( val_dict )

        self.write_outputs( ret )

        os.chdir( root_dir )
        self.run_iter += 1

        return ret

    def eval_types(self):
        return self.graph.eval_types()

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
            evals = self.eval( pars_vals )
            for k,v in evals.items():
                if isinstance(v,numbers.Number):
                    logger.info( f'\t\t Action: {k},{v}' )
                else:
                    logger.info( f'\t\t Action: {k},{type(v)}' )

            list_of_evals.append( evals )

        outcome = SimulationIterator.outcomes_as_lists( list_of_evals )

        all_combinations = np.array( all_combinations )
        par_val_dict = {key: None for key in var_names }
        for i, key in enumerate( var_names ):
            par_val_dict[key] = all_combinations[:,i]

        return par_val_dict, outcome


# ------------------- 

class DirectedGraph(WorkAction, Observer):
    
    """
    A directed graph implementation using edges keeping track of the parents.
    The parents are used to determine the order of evaluation.

    Used e.g. for MDO for solvers run in parallel.
    """ 

    def __init__(self, name, asynch=False):
        #self.adjacency_list = defaultdict(list)
        super().__init__( name, "" )
        self.parent_list = defaultdict(list)
        self.child_actions = {}
        self.asynch = asynch

    def add_action(self, action, parents=None):
        """
        Add a node to the graph.

        args:
            action (action) :
            parents (action) : Optional argument. Creates an graph edge from the parents to this node.
        """
        if not isinstance(action, WorkAction):
            raise TypeError("Node must be an instance of WorkAction")
        if action.name in self.child_actions.keys():
            raise NameError(f'Cannot re-use an action name \'{action.name}\'')
        self.child_actions[action.name] = action
        if parents is not None: 
            for p in parents: self.add_edge( p, action )
        action.attach( self )
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

    def eval(self, val_dict={}):
        # see base class

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
                            node._observed_eval_async(in_dict)
                        else:
                            node._observed_eval(in_dict)
                        self.started.add(node.name)
                    
        for nname in drain_names:
            node = self.child_actions[nname]
            nret = node.results()
            if isinstance( node, DirectedGraph ):  # Flatten, but maybe it should be nested
                        val_dict.update( nret[node.name] )
            else:
                        val_dict.update( nret )
    
        for n,e in self.child_actions.items():
            e._dump( val_dict )

        return val_dict


    def update(self, message):
        """
        From observer subject
        """
        nname = message[0].name
        #print( f'Observed action \'{nname}\' finished.' )
        logger.info( f'Observed action \'{nname}\' finished.' )
        self.finished.add(nname)


    def eval_types(self):
        types = {}
        for n,e in self.child_actions.items():
            types[e.name] = e.eval_types()
        return types

    def _check_names( self, name_list=[] ):
        """ Cannot have duplicates -- create a problem with callbacks """
        if self.name in name_list: exit( f" *** Error Duplicate actions name \'{self.name}\'" )
        name_list.append( self.name )
        for n,e in self.child_actions.items():
            e._check_names( name_list )

    def get_action(self, name ):
        return self.child_actions[name]

    def __repr__(self ):
        r = f'DirectedGraph: \'{self.name}\' {type(self)}\n' 
        for a in self.child_actions.values():
            r = r + f'\tChild: {a}\n' 
        return r



class WorkFlow(DirectedGraph):
    """
    Calls a chain of evaluations. Results get passed down the chain.

    Used e.g. when everything is sequential.
    """

    def __init__( self, name, actions=None ):
        super().__init__( name  )
        self.sequence = []
        if actions is not None:
            for e in actions: self.add_action(e)

    def add_action( self, action ):
        assert action.name != 'objective',  'objective is set using the \'set_call_protocol\' method.'
        action.parent = self

        super().add_action(action)
        if len(self.sequence) > 0 :
            self.add_edge(self.sequence[-1], action)

        self.sequence.append( action )

        return action


