
import os
import json
import glob
import subprocess
import pandas
import numpy as np

from pathlib import Path

from simflow.actions import WorkAction
from simflow.rare import HistoryEvaluation
from simflow.util.openradios_reader import OpenRadiosKeywordReader

import simflow.VTK.read_vtk as read_vtk
import simflow.args

import logging
logger = logging.getLogger(__name__)

RADIOSS_BASE_F_NAME = 'run_file'

#
# utilities
#

def get_last_run_idx():
    p = Path( '.' )
    max_idx = -1
    for g in p.glob(RADIOSS_BASE_F_NAME+'_*.vtk') :
        idx = int(str(g).split('.')[0].split('_')[-1])
        if idx > max_idx: max_idx = idx
    return max_idx

def get_last_run_name():
    max_idx = get_last_run_idx()
    return RADIOSS_BASE_F_NAME+'_%03d.vtk'%(max_idx)

#
# end utilities
#



class RadiossCSVHistory(HistoryEvaluation):
    """ Extraction of Radioss history 

    Returns:
      hist (list): [ [time vals],  [vals] ]
    """


    def __init__( self, name, cmd ):
        super().__init__(name, cmd )
        self.args = json.loads( cmd )
        self.parent_simu = None
        self.description = f'Radioss CSV history extraction of {self.args.get("quantity", "")}'


    def solve( self, val_dict=None ):

        df = pandas.read_csv( RADIOSS_BASE_F_NAME+'T01.csv' )

        time =  df[ 'time' ]
        val_key = self.args['quantity']
        vals = df[ val_key ]
        results = np.array( [ time, vals ]  )

        # this var 85 differs between databases-- cannot be used as fixed
        # the "var 85" is simply the offset in the csv file
        #print( df['TimeHistory1                             10851                                          var 85' ] )
        #print( df['TimeHistory1                             10851                                          var 88' ] )
        #print( df['TimeHistory1                             10851                                          var 91' ] )

        return results

class CSVNodeLocationHistory(HistoryEvaluation):
    """ Extraction of Radioss nodal location history 

    Shorter version which returns nodal locations

    """


    def __init__( self, name, node_id ):
        """ Extraction of Radioss nodal location history 

        Args:
            name (str)
            node_id (str):
        """
        super().__init__(name, "" )
        self.node_id = node_id
        self.parent_simu = None
        self.description = f'Radioss nodal location history for node {node_id}'


    def solve( self, val_dict=None ):
        """ Extraction of Radioss nodal location history 

        Returns:
          hist (list): [ [time vals],  [3][vals] ]
        """

        df = pandas.read_csv( RADIOSS_BASE_F_NAME+'T01.csv' )

        time =  df[ 'time' ]
        # "DATABASE_HISTORY_NODE                    682                                          var 22",

        # try using 'DATABASE_HISTORY_NODE'
        candidate_keys = df.filter( like='DATABASE_HISTORY_NODE' ).columns.tolist()
        sub_str = " %10d "%(self.node_id)
        candidate_keys = [k for k in candidate_keys if sub_str in k ]
        #print( ' --- candidate_keys A', candidate_keys )

        # try using 'TimeHistory'
        if not candidate_keys:
            candidate_keys = df.filter( like='TimeHistory1' ).columns.tolist()
            sub_str = " %10d "%(self.node_id)
            candidate_keys = [k for k in candidate_keys if sub_str in k ]
            #print( ' --- candidate_keys B', candidate_keys )


        val_x = df[ candidate_keys[0] ]
        val_y = df[ candidate_keys[1] ]
        val_z = df[ candidate_keys[2] ]

        return np.array( time ), np.array( (val_x, val_y, val_z) ) 

    def _dump(self,  val_dict=None ):
        h = val_dict[ self.name ]
        np.savez( self.name,  time=h[0], xyz=h[1] )


class CSVNodeLocation(CSVNodeLocationHistory):

    def __init__( self, name, node_id, step=-1 ):
        super().__init__(name, node_id )
        self.step = step
        self.description = f'Radioss nodal location for node {node_id} at step {step}'

    def solve( self,  val_dict=None ):
        h = super().solve( val_dict )
        return h[1][:, self.step]

    def _dump(self,  val_dict=None ):
        pass


class ScalarEvaluation(RadiossCSVHistory):
    """
    Evaluation of FEA results
    Returns: float
    """

    def __init__( self, name, cmd ):
        super().__init__(name, cmd )
        self.args = json.loads( cmd )
        self.parent_simu = None
        self.description = f'Radioss scalar evaluation of {self.args.get("quantity", "")} at step {self.args.get("step", "")}'

    def solve( self,  val_dict=None ):
        #h = self.get_radios_hist( val_dict )
        h = super().solve( val_dict )
        return h[1][ self.args['step'] ]

    def _dump(self,  val_dict=None ):
        pass




class FieldData(WorkAction):
    """
    More complex than NodalFieldData_VTK, ElementNodalFieldData_VTK, ElementFieldData_VTK

    Args:
        state (int): -1 is last
        args, kwargs: required_part_id, node_data_names=None, el_data_names=None, el_nodal_data_names
    Returns:
        ndict, edict # ndict={coords,data}, edict={..., data}
    """
    def __init__( self, name, state=-1, *args, **kwargs ):
        super().__init__(name, None )
        self.state= state
        self.args= args
        self.kwargs= kwargs
        self.description = f'Radioss field data at state {state}'


    def solve( self,  val_dict=None ):
        breakpoint()
        assert( 0 ), 'Deprecated use NodalFieldData_VTK etc'

    def eval_old( self,  val_dict=None ):
        if self.state > -1:
            vtk_file_name = RADIOSS_BASE_F_NAME+'_%03d.vtk'%(self.state)
        else:
            vtk_file_name = get_last_run_name()
        v = read_vtk.read_part_mesh( vtk_file_name, *self.args, **self.kwargs )
        return v

    def _dump(self,  val_dict=None ):
        pass

class MetaData_VTK(FieldData):
    """
    Metadata

    Arguments:
        required_part_id (int):
    Returns:
        node ids
        cells
        coords
    """
    def solve( self,  val_dict=None ):
        data = super().eval_old( val_dict )
        ndata = data[0]
        edata = data[1]
        node_ids = ndata['data']['node_ids']
        coords = ndata['coords']
        cells = edata['cells']
        return {'node_ids':node_ids, 'cells':cells, 'coords':coords}


class NodalFieldData_VTK(FieldData):
    """

    Arguments:
        state (int): -1 is last
        required_part_id (int):
        node_data_names (list):
    Returns:
        node data
    """
    def solve( self,  val_dict=None ):
        data = super().eval_old( val_dict )[0]['data']
        return data



class ElementNodalFieldData_VTK(FieldData):
    """

    Arguments:
        state (int): -1 is last
        required_part_id (int):
        element_nodal_data_names (list):
    Returns:
        node data
    """
    def solve( self,  val_dict=None ):
        data = super().eval_old( val_dict )[0]['data']
        return data



class ElementFieldData_VTK(FieldData):
    """
    NYI: TEST. ELEMENT_IDs match?

    Arguments:
        state (int): -1 is last
        required_part_id (int):
        element_nodal_data_names (list):
    Returns:
        node data
    """
    def solve( self,  val_dict=None ):
        assert 0, 'not tested'
        data = super().eval_old( val_dict )[1]['data']
        return data





class FieldDataHist(WorkAction):

    def __init__( self, name, *args, **kwargs ):
        super().__init__(name, None )
        self.args= args
        self.kwargs= kwargs
        self.description = f'Radioss field data history'


    def solve( self,  val_dict=None ):
        coords = []
        #data =  # node_data_names
        # el_nodal_data_names becomes node data
        ndata = {name:[] for name in self.kwargs['node_data_names']+self.kwargs['el_nodal_data_names'] }
        edata = {name:[] for name in self.kwargs['el_data_names'] }
        for run_idx in range( 1, get_last_run_idx()+1 ):
            vtk_file_name = RADIOSS_BASE_F_NAME+'_%03d.vtk'%(run_idx)
            nv, ev = read_vtk.read_part_mesh( vtk_file_name, *self.args, **self.kwargs )
            coords.append( nv['coords'] )

            for key,value in ndata.items():
                ndata[key].append( nv['data'][key] )
            for key,value in edata.items():
                edata[key].append( ev['data'][key] )
        coords = np.array( coords )
        for key,value in ndata.items():
            ndata[key] = np.stack( value )
        for key,value in edata.items():
            edata[key] = np.stack( value )
        nvl, evl = {'coords':coords, 'data':ndata}, {'data':edata}
        return nvl, evl

    def _dump(self,  val_dict=None ):
        pass


class RadiossAnalysis(WorkAction):

    """ Runs an openRadioss simulation

        Args:
            name (str):
            cmd (str): path to ls-dyna executable or command
            input_path (str): parameterized keyword file
            create_d3plot (bool): Creates a d3plot files using
                            vortex_radioss.animtod3plot.Anim_to_D3plot
    """

    def __init__( self, name, cmd='rad_dyna_inp', input_path=simflow.args.RADIOSS_DFLT_FNAME, create_d3plot=True, copy_paths=[] ):

        assert input_path is not None, 'No input OpenRadioss file specified. Specify the path to radioss input file.'

        super().__init__(name, cmd, copy_paths=copy_paths )
        self.input_file_path = input_path
        self.input_file_path = Path( self.input_file_path ).name

        self.create_d3plot = create_d3plot

        self.evaluations = []
        self.description = f'OpenRadioss analysis using input file {input_path}'


    def _create_d3plot_file( self ):
        try:
            from vortex_radioss.animtod3plot.Anim_to_D3plot import readAndConvert
        except:
            exit( ' *** Error Install vortex_radioss.animtod3plot from \'https://www.vortex-cae.com/vortex-radioss\'.' )

        readAndConvert( str( Path.cwd().joinpath( RADIOSS_BASE_F_NAME) )  )

        # Rename generated d3plot files
        # Pattern: filename.d3plot* -> d3plot*
        pattern = f"{RADIOSS_BASE_F_NAME}.d3plot*"
        for file_path in glob.glob(pattern):
            # We only want to replace the prefix in the basename
            base_name = os.path.basename(file_path)
            if base_name.startswith(f"{RADIOSS_BASE_F_NAME}."):
                new_name = base_name.replace(f"{RADIOSS_BASE_F_NAME}.", "", 1)
                logger.info(f"Renaming {base_name} to {new_name}")
                os.rename(file_path, new_name)




    def solve( self,  val_dict=None ):

        if not Path( self.input_file_path ).exists():
            exit( f' *** Error {self.input_file_path} not in run directory. Likely not copied by Iterator.' )

        if val_dict is None: val_dict = {}

        with open( 'radioss_variables.json','w' ) as vf:
            json.dump( val_dict, vf )

        base_file_name = RADIOSS_BASE_F_NAME+'.k'

        with OpenRadiosKeywordReader( self.input_file_path ) as orkr:
            params = orkr.parameters()
            logger.info("Existing parameters:")
            for name, (ptype, value) in params.items():
                logger.info(f"  {name} ({ptype}): {value}")

            orkr.set_parameters( val_dict )

            params_updated = orkr.parameters()
            logger.info("Updated parameters:")
            for name, (ptype, value) in params_updated.items():
                logger.info(f"  {name} ({ptype}): {value}")

            orkr.write( base_file_name )

        self._run_solver_in_dir( base_file_name )


        if self.create_d3plot : self._create_d3plot_file()

        return True 


    def write_deck( self, dpath, variable_dict=None ):
        """ write FEA deck using given parameter values.

        e.g write_deck( {'E':210.0, 'SIG_Y':sigy} )
        """
        with OpenRadiosKeywordReader( self.input_file_path ) as orkr:
            if variable_dict:
                orkr.set_parameters( variable_dict )
            orkr.write( dpath )



    def _run_solver_in_dir( self, base_file_name ):
        """
        new_input:
        """

        out_file = open( RADIOSS_BASE_F_NAME+'.stdout' , 'w' )
        err_file = open( RADIOSS_BASE_F_NAME+'.stderr' , 'w')

        subprocess.run( self.cmd + ' ' + base_file_name + ' 0', shell=True, stdout=out_file, stderr=err_file )

        subprocess.run( ['to_vtk', RADIOSS_BASE_F_NAME ], stdout=out_file, stderr=err_file )

        have_error_termination = False
        with open( RADIOSS_BASE_F_NAME+'_0000.out',  'r' ) as outfile:
            for line in outfile.readlines():
                if 'ERROR TERMINATION' in line:
                    have_error_termination = True
        if have_error_termination is False:
          with open( RADIOSS_BASE_F_NAME+'_0001.out',  'r' ) as outfile:
            for line in outfile.readlines():
                if 'ERROR TERMINATION' in line:
                    have_error_termination = True
        if have_error_termination is True:
            exit( f'ERROR OpenRadios run failed in \"{self.last_job_path}\"' )

        out_file.close()
        err_file.close()

