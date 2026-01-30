import os
import numpy as np
import json
import subprocess
from pathlib import Path

import simflow.args
from simflow.actions import WorkAction
from simflow.graph_actions import WorkFlow

import logging
logger = logging.getLogger(__name__)

from lasso.dyna import D3plot, ArrayType, FilterType


class d3plot_File(WorkFlow):
    """
    This opens the d3plot file for data extractions.
    The subsequent d3plot read operations must be added using methods on this method.

    Args:
        name (str):
        d3plot_rootname (str): Default is 'd3plot'.
    Returns:
        success (bool):
    """

    def __init__( self, name, d3plot_rootname='d3plot' ):
        super().__init__(name, None )
        self.d3plot_rootname = d3plot_rootname

    def eval( self,  val_dict=None ):
        fname = self.d3plot_rootname 
        if not Path( fname ).exists():
            msg =  f"*** Error Cannot open '{fname}'. No such file in {Path.cwd()}" 
            logger.error( msg )
            exit( msg )

        d3plot = D3plot( fname )
        self.d3plot = d3plot
        return super().eval( val_dict ) # graph method
        
    def _node_idx_for_part( self, pid ):
        #f1 =  self._node_idx_for_shells_in_part(pid) # TODO maybe cache?
        #f2 = self.d3plot.get_part_filter( FilterType.SHELL, part_ids=[pid] )

        f1 = self.d3plot.get_part_filter( FilterType.NODE, part_ids=[pid] )

        return f1

    def _part_only_nodal( self,  pid , data ):
        node_mask = self.d3plot.get_part_filter( FilterType.NODE, part_ids=[pid] )
        if data.ndim == 1:
            return data[ node_mask ]
        else:
            return data[ node_mask ]

    def _part_only_element( self,  element_type,  pid , data ):
        mask = self.d3plot.get_part_filter( element_type, part_ids=[pid] )
        if data.ndim == 1:
            return data[ mask ]
        else:
            return data[ mask ]

    def num_state( self ):
        return self.d3plot.n_timesteps

    def meta_data( self ):
        d3p = self.d3plot

        node_ids = d3p.arrays['node_ids']
        coords = d3p.arrays['node_coordinates']
        cells = None
        return {'node_ids':node_ids, 'cells':cells, 'coords':coords}

    @staticmethod
    def check_if_d3plot_child(cls):
        assert isinstance( cls.parent, d3plot_File  ), f'd3plot extraction \'{cls.name}\' must be created using D3PlotOperations.add_action'

    def PartMetaData(self, name, *args, **kwargs):
        # outdated meta_data?
        return self.add_action(_d3plot_PartMetaData(name, *args, **kwargs))

    def NodalFieldData(self, name, *args, **kwargs):
        """
        Arguments:
            state (int): -1 is last
            component (str):
            required_part_id (int): optional
        Returns:
            Nodal field data
        """
        return self.add_action(_d3plot_NodalFieldData(name, *args, **kwargs))

    def MultNodalFieldData(self, name, *args, **kwargs):
        return self.add_action(_d3plot_MultNodalFieldData(name, *args, **kwargs))

    def MultElementNodalFieldData(self, name, *args, **kwargs):
        return self.add_action(_d3plot_MultElementNodalFieldData(name, *args, **kwargs))

    def MultElementFieldData(self, name, *args, **kwargs):
        return self.add_action(_d3plot_MultElementFieldData(name, *args, **kwargs))

    def NodalValue(self, name, *args, **kwargs):
        """
        Arguments:
            nid (int) :
            state (int) :
            component (str) :
        Returns:
            value at node
        """
        return self.add_action(_d3plot_NodalValue(name, *args, **kwargs))

    def NodalHistory(self, name, *args, **kwargs):
        """
        Arguments:
            nid (int) :
            component (str) :
        Returns:
            history at node
        """

        return self.add_action(_d3plot_NodalHistory(name, *args, **kwargs))


class _d3plot_PartMetaData(WorkAction):
    # may be outdated
    """
    Retrieves the meta_data.

    Arguments:
            required_part_id (int):
    Returns:
            node ids, cell conn
    """
    def eval( self,  val_dict=None ):
        d3p = self.parent.d3plot

        node_ids = d3p.arrays['node_ids']
        coords = d3p.arrays['node_coordinates']
        cells = None
        return {'node_ids':node_ids, 'cells':cells, 'coords':coords}



class _d3plot_NodalFieldData(WorkAction):
    """
    Arguments:
        state (int): -1 is last
        component (str):
        required_part_id (int): optional
    Returns:
        Nodal field data
    """

    def __init__( self, name, *args, **kwargs ):
        super().__init__(name, None )
        self.args= args
        self.kwargs= kwargs

    def eval( self,  val_dict=None ):
        d3plot_File.check_if_d3plot_child(self)
        d3p = self.parent.d3plot
        try:
            data = d3p.arrays[self.kwargs['component']][self.kwargs['state']] if d3p.arrays[self.kwargs['component']].ndim > 2 else d3p.arrays[self.kwargs['component']] 
        except:
            if self.kwargs['component'] not in d3p.arrays.keys():
                print( ' *** ERROR: Not all requested data in d3plot. Missing:', self.kwargs['component'] )
                print( ' *** ERROR Data available in d3plot:', d3p.arrays.keys() )
            elif d3p.arrays[self.kwargs['component']].shape[0] < self.kwargs['state']+1 :
                print( f' *** ERROR: State {self.kwargs["state"]} requested. Data has {d3p.arrays[self.kwargs["component"]].shape[0]} states. Note that first state has index 0.' )
            exit( f' *** ERROR Requested component data not available in d3plot for \'{self.name}\'')
        if 'required_part_id' in self.kwargs:
            data = self.parent._part_only_nodal( self.kwargs['required_part_id'], dat ) 
        return data


class _d3plot_MultNodalFieldData(WorkAction):
    """
    Arguments:
        state (int): -1 is last
        node_data_names (list):
        required_part_id (int): optional
    Returns:
        nodal field data
    """

    def __init__( self, name, *args, **kwargs ):
        super().__init__(name, None )
        self.args= args
        self.kwargs= kwargs

    def eval( self,  val_dict=None ):
        d3plot_File.check_if_d3plot_child(self)
        d3p = self.parent.d3plot
        try:
            data = { k:d3p.arrays[k][self.kwargs['state']] if d3p.arrays[k].ndim > 2 else d3p.arrays[k] for k in self.kwargs['node_data_names'] }
        except:
            if self.kwargs['component'] not in d3p.arrays.keys():
                print( ' *** ERROR: Not all requested data in d3plot. Missing:', self.kwargs['component'] )
                print( ' *** ERROR Data available in d3plot:', d3p.arrays.keys() )
            elif d3p.arrays[self.kwargs['component']].shape[0] < self.kwargs['state']+1 :
                print( f' *** ERROR: State {self.kwargs["state"]} requested. Data has {d3p.arrays[self.kwargs["component"]].shape[0]} states. Note that first state has index 0.' )
            exit( f' *** ERROR Requested component data not available in d3plot for \'{self.name}\'')
        if 'required_part_id' in self.kwargs:
            #print( ' Data available in d3plot:', d3p.arrays.keys() )
            data = {k: self.parent._part_only_nodal( self.kwargs['required_part_id'], dat ) for k,dat in data.items()}
        return data

class _d3plot_MultElementNodalFieldData(WorkAction):
    """
    Arguments:
        state (int): -1 is last
        required_part_id (int):
        element_nodal_data_names (list):
    Returns:
        nodal field data
    """

    def __init__( self, name, *args, **kwargs ):
        super().__init__(name, None )
        self.args= args
        self.kwargs= kwargs

    def eval( self,  val_dict=None ):
        d3plot_File.check_if_d3plot_child(self)
        d3p = self.parent.d3plot
        try:
            data = { k:d3p.arrays[k][self.kwargs['state']] if d3p.arrays[k].ndim > 1 else d3p.arrays[k] for k in self.kwargs['element_nodal_data_names'] }
        except:
            if self.kwargs['component'] not in d3p.arrays.keys():
                print( ' *** ERROR: Not all requested data in d3plot. Missing:', self.kwargs['component'] )
                print( ' *** ERROR Data available in d3plot:', d3p.arrays.keys() )
            elif d3p.arrays[self.kwargs['component']].shape[0] < self.kwargs['state']+1 :
                print( f' *** ERROR: State {self.kwargs["state"]} requested. Data has {d3p.arrays[self.kwargs["component"]].shape[0]} states. Note that first state has index 0.' )
            exit( f' *** ERROR Requested component data not available in d3plot for \'{self.name}\'')
        if 'required_part_id' in self.kwargs:
            #print( ' Data available in d3plot:', d3p.arrays.keys() )
            data = {k: self.parent._part_only_element( self.kwargs['element_type'], self.kwargs['required_part_id'], dat ) for k,dat in data.items()}
        # convert to element nodal
        assert 0, 'TODO convert to element nodal'
        return data


class _d3plot_MultElementFieldData(WorkAction):
    """
    Arguments:
        state (int): -1 is last
        required_part_id (int):
        element_data_names (list):
    Returns:
        element field data
    """

    def __init__( self, name, *args, **kwargs ):
        super().__init__(name, None )
        self.args= args
        self.kwargs= kwargs

    def eval( self,  val_dict=None ):
        d3plot_File.check_if_d3plot_child(self)
        d3p = self.parent.d3plot
        try:
            data = { k:d3p.arrays[k][self.kwargs['state']] if d3p.arrays[k].ndim > 1 else d3p.arrays[k] for k in self.kwargs['element_data_names'] }
        except:
            if self.kwargs['component'] not in d3p.arrays.keys():
                print( ' *** ERROR: Not all requested data in d3plot. Missing:', self.kwargs['component'] )
                print( ' *** ERROR Data available in d3plot:', d3p.arrays.keys() )
            elif d3p.arrays[self.kwargs['component']].shape[0] < self.kwargs['state']+1 :
                print( f' *** ERROR: State {self.kwargs["state"]} requested. Data has {d3p.arrays[self.kwargs["component"]].shape[0]} states. Note that first state has index 0.' )
            exit( f' *** ERROR Requested component data not available in d3plot for \'{self.name}\'')
        if 'required_part_id' in self.kwargs:
            data = {k: self.parent._part_only_element( self.kwargs['element_type'], self.kwargs['required_part_id'], dat ) for k,dat in data.items()}
        return data



class _d3plot_NodalValue( _d3plot_NodalFieldData):

    def eval( self,  val_dict=None ):
        data = super().eval( val_dict )
        #print( 'super data', data )

        assert 'nid' in self.kwargs, '\'nid\' is an required argument for d3plot_NodalValue.' 
        assert 'required_part_id' not in self.kwargs, '\'required_part_id\' is not allowed for d3plot_NodalValue.' 

        nids = self.parent.meta_data()['node_ids']
        #print( 'nids nids', nids )
        w = np.where( nids == self.kwargs['nid'] )[0]

        if len(w) == 0:
            exit( f' *** ERROR Node with id {self.kwargs["nid"]} not found in d3plot.' )

        data = data[w][0]
        #assert 'idx' in self.kwargs, '\'idx\' is an required argument for d3plot_NodalValue.' 
        return data


class _d3plot_NodalHistory( _d3plot_NodalValue):

    def eval( self,  val_dict=None ):

        ns = self.parent.num_state()

        hist = []
        for istate in range( ns ):
            self.kwargs['state'] = istate
            data = super().eval( val_dict )
            hist.append( data )
        return np.array( (self.parent.d3plot.arrays['timesteps'],hist) )
