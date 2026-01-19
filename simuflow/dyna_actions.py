
import os
import numpy as np

from simuflow.actions import WorkAction
from simuflow.graph_actions import WorkFlow

import logging
logger = logging.getLogger(__name__)

from lasso.dyna import D3plot, ArrayType, FilterType

class SetDynaParameters(WorkAction):
    def __init__( self, name, simuflow, clean_start=False):
        exit( "SetDynaParameters NYI" )




class D3PlotOperations(WorkFlow):

    def __init__( self, name, is_radioss=False, d3plot_rootname='d3plot' ):
        super().__init__(name, None )
        self.is_radioss= is_radioss
        self.d3plot_rootname = d3plot_rootname

    def eval( self,  val_dict=None ):
        # "element_shell_part_indexes" shell idx -> pid
        if self.is_radioss:
            d3plot = D3plot("run_file.d3plot")
        else:
            d3plot = D3plot( self.d3plot_rootname )
        self.d3plot = d3plot
        return super().eval( val_dict ) # graph method
        
    """
    def _node_idx_for_shells_in_part( self, pid ):
        #"" idx that are in part for shells ""#
        node_ids = self.d3plot.arrays['node_ids']
        num_n = len(node_ids)
        element_shell_part_indexes = self.d3plot.arrays['element_shell_part_indexes']
        element_shell_node_indexes = self.d3plot.arrays['element_shell_node_indexes']

        prt_id_offset = np.where( self.d3plot.arrays['part_ids'] == pid ) [0]
        prt_id_offset = prt_id_offset[0]

        shell_idices = np.where( element_shell_part_indexes == prt_id_offset )[0]

        node_idxs = set()
        for shell_idx in shell_idices:
             node_idxs.update( element_shell_node_indexes[shell_idx].tolist() )
        node_idxs = sorted( node_idxs )

        return [i in node_idxs for i in range(num_n) ] # fast?
    """

    #def mask_array(self, arr, mask):
    #    if arr.ndim == 1:
    #        return arr[mask]
    #    else:
    #        # Add new axes to the mask array to match the shape of the original array
    #        mask = mask[(slice(None),) + (np.newaxis,) * (arr.ndim - 2)]
    #
    #                # Apply the mask to the array
    #            return arr[:, mask, ...]

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


class D3PlotOperationsChild(WorkFlow):

    @staticmethod
    def check(cls):
        assert isinstance( cls.parent, D3PlotOperations  ), f'd3plot extraction \'{cls.name}\' must be created using D3PlotOperations.add_action'

class MetaData_D3Plot(WorkAction):
    """
    Metadata, see also meta_data above. This version is maybe outdated.

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



class NodalFieldData_D3Plot(WorkAction):
    """
    Arguments:
        state (int): -1 is last
        required_part_id (int):
        node_data_names (list):
    Returns:
        node data
    """

    def __init__( self, name, *args, **kwargs ):
        super().__init__(name, None )
        self.args= args
        self.kwargs= kwargs

    def eval( self,  val_dict=None ):
        D3PlotOperationsChild.check(self)
        d3p = self.parent.d3plot
        try:
            data = d3p.arrays[self.kwargs['component']][self.kwargs['state']] if d3p.arrays[self.kwargs['component']].ndim > 2 else d3p.arrays[self.kwargs['component']] 
        except:
            if self.kwargs['component'] not in d3p.arrays.keys():
                print( ' *** ERROR: Not all requested data in d3plot. Missing:', self.kwargs['component'] )
                print( ' *** ERROR Data available in d3plot:', d3p.arrays.keys() )
            elif d3p.arrays[self.kwargs['component']].shape[0] < self.kwargs['state']+1 :
                print( f' *** ERROR: State {self.kwargs["state"]} requested. Data has {d3p.arrays[self.kwargs["component"]].shape[0]} states. Note that first state has index 0.' )
            exit( f' *** ERROR Requested component data not available in d3plot for \'{self.name}\'' )
        if 'required_part_id' in self.kwargs:
            data = self.parent._part_only_nodal( self.kwargs['required_part_id'], dat ) 
        return data


class MultNodalFieldData_D3Plot(WorkAction):
    """
    Arguments:
        state (int): -1 is last
        required_part_id (int):
        node_data_names (list):
    Returns:
        node data
    """

    def __init__( self, name, *args, **kwargs ):
        super().__init__(name, None )
        self.args= args
        self.kwargs= kwargs

    def eval( self,  val_dict=None ):
        D3PlotOperationsChild.check(self)
        d3p = self.parent.d3plot
        try:
            data = { k:d3p.arrays[k][self.kwargs['state']] if d3p.arrays[k].ndim > 2 else d3p.arrays[k] for k in self.kwargs['node_data_names'] }
        except:
            if self.kwargs['component'] not in d3p.arrays.keys():
                print( ' *** ERROR: Not all requested data in d3plot. Missing:', self.kwargs['component'] )
                print( ' *** ERROR Data available in d3plot:', d3p.arrays.keys() )
            elif d3p.arrays[self.kwargs['component']].shape[0] < self.kwargs['state']+1 :
                print( f' *** ERROR: State {self.kwargs["state"]} requested. Data has {d3p.arrays[self.kwargs["component"]].shape[0]} states. Note that first state has index 0.' )
            exit( f' *** ERROR Requested component data not available in d3plot for \'{self.name}\'' )
        if 'required_part_id' in self.kwargs:
            #print( ' Data available in d3plot:', d3p.arrays.keys() )
            data = {k: self.parent._part_only_nodal( self.kwargs['required_part_id'], dat ) for k,dat in data.items()}
        return data

class MultElementNodalFieldData_D3Plot(WorkAction):
    """
    Arguments:
        state (int): -1 is last
        required_part_id (int):
        element_nodal_data_names (list):
    Returns:
        node data
    """

    def __init__( self, name, *args, **kwargs ):
        super().__init__(name, None )
        self.args= args
        self.kwargs= kwargs

    def eval( self,  val_dict=None ):
        D3PlotOperationsChild.check(self)
        d3p = self.parent.d3plot
        try:
            data = { k:d3p.arrays[k][self.kwargs['state']] if d3p.arrays[k].ndim > 1 else d3p.arrays[k] for k in self.kwargs['element_nodal_data_names'] }
        except:
            if self.kwargs['component'] not in d3p.arrays.keys():
                print( ' *** ERROR: Not all requested data in d3plot. Missing:', self.kwargs['component'] )
                print( ' *** ERROR Data available in d3plot:', d3p.arrays.keys() )
            elif d3p.arrays[self.kwargs['component']].shape[0] < self.kwargs['state']+1 :
                print( f' *** ERROR: State {self.kwargs["state"]} requested. Data has {d3p.arrays[self.kwargs["component"]].shape[0]} states. Note that first state has index 0.' )
            exit( f' *** ERROR Requested component data not available in d3plot for \'{self.name}\'' )
        if 'required_part_id' in self.kwargs:
            #print( ' Data available in d3plot:', d3p.arrays.keys() )
            data = {k: self.parent._part_only_element( self.kwargs['element_type'], self.kwargs['required_part_id'], dat ) for k,dat in data.items()}
        # convert to element nodal
        assert 0, 'TODO convert to element nodal'
        return data


class MultElementFieldData_D3Plot(WorkAction):
    """
    Arguments:
        state (int): -1 is last
        required_part_id (int):
        element_data_names (list):
    Returns:
        node data
    """

    def __init__( self, name, *args, **kwargs ):
        super().__init__(name, None )
        self.args= args
        self.kwargs= kwargs

    def eval( self,  val_dict=None ):
        D3PlotOperationsChild.check(self)
        d3p = self.parent.d3plot
        try:
            data = { k:d3p.arrays[k][self.kwargs['state']] if d3p.arrays[k].ndim > 1 else d3p.arrays[k] for k in self.kwargs['element_data_names'] }
        except:
            if self.kwargs['component'] not in d3p.arrays.keys():
                print( ' *** ERROR: Not all requested data in d3plot. Missing:', self.kwargs['component'] )
                print( ' *** ERROR Data available in d3plot:', d3p.arrays.keys() )
            elif d3p.arrays[self.kwargs['component']].shape[0] < self.kwargs['state']+1 :
                print( f' *** ERROR: State {self.kwargs["state"]} requested. Data has {d3p.arrays[self.kwargs["component"]].shape[0]} states. Note that first state has index 0.' )
            exit( f' *** ERROR Requested component data not available in d3plot for \'{self.name}\'' )
        if 'required_part_id' in self.kwargs:
            data = {k: self.parent._part_only_element( self.kwargs['element_type'], self.kwargs['required_part_id'], dat ) for k,dat in data.items()}
        return data



class NodalValue_D3Plot( NodalFieldData_D3Plot ):
    """ nid, state, component, idx """

    def eval( self,  val_dict=None ):
        data = super().eval( val_dict )

        assert 'nid' in self.kwargs, '\'nid\' is an required argument for NodalHistory_D3Plot.' 
        assert 'required_part_id' not in self.kwargs, '\'required_part_id\' is not allowed for NodalHistory_D3Plot.' 

        nids = self.parent.meta_data()['node_ids']
        w = np.where( nids == self.kwargs['nid'] )[0]

        if len(w) == 0:
            exit( f' *** ERROR Node with id {self.kwargs["nid"]} not found in d3plot.' )

        data = data[w][0]
        assert 'idx' in self.kwargs, '\'idx\' is an required argument for NodalHistory_D3Plot.' 
        return data[self.kwargs['idx']]


class NodalHistory_D3Plot( NodalValue_D3Plot ):

    def eval( self,  val_dict=None ):

        ns = self.parent.num_state()

        hist = []
        for istate in range( ns ):
            self.kwargs['state'] = istate
            data = super().eval( val_dict )
            hist.append( data )
        return np.array( (self.parent.d3plot.arrays['timesteps'],hist) )


