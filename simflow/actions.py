import os
from abc import ABC, abstractmethod
import pandas
import numpy as np

from simflow.args import EvalType

import logging
logger = logging.getLogger(__name__)

from abc import ABC, abstractmethod

from simflow.util.observer import Subject, notify_observers

from simflow.variables import Variable


class WorkAction(Subject):
    """
    Base class for the nodes in the graph.
    Each action encapsulate an operations on the data stream.

    args:
        name (str) :
        cmd (str) :
        copy_paths (list) : List of file and directories to be copied to work area.
        lower_bound (float) : Lower bound on output value during design
        upper_bound (float) : Lower bound on output value during design
    Returns:
        Any: outcome of operation
    """

    def __init__( self, name, cmd=None, copy_paths=[], lower_bound=None, upper_bound=None,
                  description=None, data_type = EvalType.NOT_SPECIFIED ):
        """
        """
        super().__init__()
        self.name = name
        self.cmd = cmd          # backward compatible with simulation
        self.copy_paths = copy_paths
        self.upper_bound = upper_bound # backward compatible with simulation
        self.lower_bound = lower_bound # backward compatible with simulation
        self.parent = None # typically workflow
        self.description = description if description is not None else (
            self.__class__.__doc__.strip() if self.__class__.__doc__ else ""
        )

        self._results = None

        self.data_type = data_type
        self._par_dict = {}

    def _collect_arg_pars(self ):
        self._par_dict = {}
        for k,v in self.__dict__.items():
            if isinstance(v, Variable ):
                self._par_dict[k] = v
                self.__dict__[k] = v.value


    def _set_arg_pars(self, val_dict ):

        for k,v in self._par_dict.items():
            #breakpoint()
            if v.name in val_dict:
                self.__dict__[k] = val_dict[v.name]

    def allow_variables_as_arguments( func ):
        """ A decorator for the __init__() method allowing you to
        use variables as arguments constructing this class.

        The  arguments to a class can be declared to be variables,
        e.g. Action( name=, cmd=, arg1=FloatVariable( 'E', 123.4 ) )
        to be used as action.solve( {'E':3.} )
        This requires that the subclass must used the decorators
        allow_variables_as_arguments and
        assign_variables_values_to_members as:

        @WorkAction.allow_variables_as_arguments

        def __init__( self, name, cmd=None, v=None ):
            ...

        @WorkAction.assign_variables_values_to_members

        def solve(self,  val_dict=None ):
            ...
                    
        Child actions are created with the variables.

        You cannot do computations with the variables in
        __init__() because the values are only set at the end.
        """
        def wrapper( self, *args, **kwargs ):
            v = func( self, *args, **kwargs )
            self._collect_arg_pars() 
            return v
        return wrapper

    def assign_variables_values_to_members( func ):
        """ A decorator for the solve() method allowing you to
        use variables as arguments constructing this class."""
        def wrapper( self, val_dict ):
            self._set_arg_pars( val_dict )
            v = func( self, val_dict )
            return v
        return wrapper


    def _reset_class_member_vals(self,  val_dict):
        """
        Reset values of 'action_name.member' in class. val_dict can be {'img_extraction.zoom': 12.3} and
        if the class hass a member 'zoom' then that will be reset to 12.3

        OUTDATED: use allow_variables_as_arguments and assign_variables_values_to_members decorators
        """
        if val_dict is None: return
        needle = self.name+'.'
        for variable_name in val_dict:
            if needle in variable_name and variable_name.rfind( needle ) == 0:
                subkey = variable_name.replace( needle, '' )
                if subkey in self.__dict__:
                    self.__dict__[  subkey] = val_dict[variable_name]
                else:
                    exit( f' *** ERROR Key \'{variable_name}\' not found in action \'{self.name}\' ' )


    #@notify_observers
    def _observed_eval(self,  val_dict=None ):
        """
        used by the call graph to check if jobs have finished

        returns:
            dict : { self.name:..., .... } # including items in val_dict
        """
        self._results =  val_dict.copy()
        e = self.solve( val_dict )
        self._results[self.name] = e
        self._notify_observers( [self, 'Done'] )
        return self._results 

    def _observed_eval_async(self, val_dict=None):
        import multiprocessing
        import threading

        """
        Asynchronously run solve in a separate process.
        Notifies observers only when the process finishes.
        """
        def eval_worker(val_dict, result_dict):
            e = self.solve(val_dict)
            result_dict[self.name] = e

        def watcher(proc, result_dict):
            proc.join()
            # Update self._results in the main process
            self._results = dict(result_dict)
            self._notify_observers([self, 'Done'])

        manager = multiprocessing.Manager()
        result_dict = manager.dict(val_dict.copy() if val_dict else {})
        p = multiprocessing.Process(target=eval_worker, args=(val_dict, result_dict))
        p.start()
        # Start watcher thread to notify when done
        t = threading.Thread(target=watcher, args=(p, result_dict), daemon=True)
        t.start()
        # Return immediately, results will be set when done
        return None

    @abstractmethod
    def solve(self,  val_dict: dict = None ) -> dict:
        """
        Solve/compute for action or graph.
        An action will return any computed results.

        A graph will append any computed results to
        val_dict and return that. 
        So A.solve( {'v1':1.2} ) may return {'v1':1.2, 'A':3.4},
        where the 'A':3.4 was added with 'A' the name of the action.

        Arguments:
            val_dict (dict) : variable values and input of any type.
        Returns:
            dict : dict with all results and inputs
        """
        assert 0, 'should not be called'

    def variables( self ):
        """
        These are the variabls defined for the WorkAction
        and used in the solve() method.
        For a graph this would be the variables used in
        all the children.

        Returns:
            set : Set of type Variable.
        """
        var_set = { v for k,v in self._par_dict.items() }
        return var_set

    def results(self):
        return self._results

    def _dump(self,  val_dict=None ):
        pass

    def outputs(self):
        """
        Returns the output type and description of this action.

        Returns:
            tuple: (data_type, description)
        """
        return (self.data_type, self.description)

    def _check_names( self, name_list=[] ):
        """ Cannot have duplicates -- create a problem with callbacks """
        if self.name in name_list: exit( f" *** Error Duplicate actions name \'{self.name}\'" )
        name_list.append( self.name )

    def __str__(self ):
        r = f'WorkAction: \'{self.name}\' {type(self)}' 
        return r


class MathEvaluation(WorkAction):
    """
    Mathematical operation on results.

    args:
        name (str) :
        cmd (str) :
    Returns:
        Any: outcome of operation
    """

    #def __init__( self, name, cmd ):
    #    super().__init__(name, cmd )

    def solve(self,  val_dict=None ):
        try:
            v = eval( self.cmd, None, val_dict )
        except NameError as err:
            exit( f' *** Could not evaluate action \'{self.name}\'. Error is \'{err}\'. Either a named action was not defined or have not finished.' )
        except Exception as err:
            exit( f' *** Error in MathEvaluation \'{self.name}\'. {err}' )
        return v



