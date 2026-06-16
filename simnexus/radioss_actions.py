
import os
import json
import glob
import subprocess
import numpy as np
import pandas
import shutil

from pathlib import Path

from simnexus.actions import WorkAction
from simnexus.rare import HistoryEvaluation
from simnexus.util.openradios_reader import OpenRadiosKeywordReader
import simnexus.variables as simvars

import simnexus.VTK.read_vtk as read_vtk
import simnexus.args

import logging
logger = logging.getLogger(__name__)

from simnexus.args import RADIOSS_ROOT_NAME
from simnexus.args import RADIOSS_BASE_F_NAME # _0000
from simnexus.args import RADIOSS_ENGINE_F_NAME # _0001

#
# utilities
#

def get_last_run_idx(root_name=RADIOSS_ROOT_NAME):
    p = Path( '.' )
    max_idx = -1
    for g in p.glob(root_name+'_*.vtk') :
        idx = int(str(g).split('.')[0].split('_')[-1])
        if idx > max_idx: max_idx = idx
    return max_idx

def get_last_run_name(root_name=RADIOSS_ROOT_NAME):
    max_idx = get_last_run_idx(root_name)
    return root_name+'_%03d.vtk'%(max_idx)

#
# end utilities
#



class RadiossCSVHistory(HistoryEvaluation):
    """ Extraction of Radioss history 

    Args:
        name (str) :
        cmd (str) :
        root_name (str) : root_name of radios input. E.g. 'dyna_action_inp' to read dyna_action_inpT01.csv
    Returns:
      hist (list): [ [time vals],  [vals] ]
    """


    def __init__( self, name, cmd, root_name=RADIOSS_ROOT_NAME ):
        super().__init__(name, cmd )
        self.args = json.loads( cmd )
        self.parent_simu = None
        self.root_name = root_name
        self.description = f'Radioss CSV history extraction of {self.args.get("quantity", "")}'


    def solve( self, val_dict=None ):

        fname = self.root_name+'T01.csv'
        if not Path(fname).exists():
            logger.error(f"Cannot open OpenRadioss CSV file. Did you set \'create_csv=True\' ")
            raise FileNotFoundError(f'RadiossCSVHistory: CSV file not found: {fname}')
        logger.info( f'RadiossCSVHistory reading \'{fname}\'' )
        df = pandas.read_csv( fname )

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


    def __init__( self, name, node_id, root_name=RADIOSS_ROOT_NAME ):
        """ Extraction of Radioss nodal location history

        Args:
            name (str)
            node_id (str):
            root_name (str):
        """
        super().__init__(name, "" )
        self.node_id = node_id
        self.parent_simu = None
        self.root_name = root_name
        self.description = f'Radioss nodal location history for node {node_id}'


    def solve( self, val_dict=None ):
        """ Extraction of Radioss nodal location history

        Returns:
          hist (list): [ [time vals],  [3][vals] ]
        """

        df = pandas.read_csv( self.root_name+'T01.csv' )

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

    def __init__( self, name, node_id, step=-1, root_name=RADIOSS_ROOT_NAME ):
        super().__init__(name, node_id, root_name )
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

    def __init__( self, name, cmd, root_name=RADIOSS_ROOT_NAME ):
        super().__init__(name, cmd, root_name )
        self.args = json.loads( cmd )
        self.parent_simu = None
        self.description = f'Radioss scalar evaluation of {self.args.get("quantity", "")} at step {self.args.get("step", "")}'

    def solve( self,  val_dict=None ):
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
    def __init__( self, name, state=-1, *args, root_name=RADIOSS_ROOT_NAME, **kwargs ):
        super().__init__(name, None )
        self.state= state
        self.args= args
        self.kwargs= kwargs
        self.root_name = root_name
        self.description = f'Radioss field data at state {state}'


    def solve( self,  val_dict=None ):
        assert( 0 ), 'Deprecated use NodalFieldData_VTK etc'

    def eval_old( self,  val_dict=None ):
        if self.state > -1:
            vtk_file_name = self.root_name+'_%03d.vtk'%(self.state)
        else:
            vtk_file_name = get_last_run_name(self.root_name)
        if not Path(vtk_file_name).exists():
            logger.error(f"Cannot open VTK file. Did you set \'create_vtk=True\' ")
            raise FileNotFoundError(f'VTK file not found: {vtk_file_name}')
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

    def __init__( self, name, *args, root_name=RADIOSS_ROOT_NAME, **kwargs ):
        super().__init__(name, None )
        self.args= args
        self.kwargs= kwargs
        self.root_name = root_name
        self.description = f'Radioss field data history'


    def solve( self,  val_dict=None ):
        coords = []
        #data =  # node_data_names
        # el_nodal_data_names becomes node data
        ndata = {name:[] for name in self.kwargs['node_data_names']+self.kwargs['el_nodal_data_names'] }
        edata = {name:[] for name in self.kwargs['el_data_names'] }
        for run_idx in range( 1, get_last_run_idx(self.root_name)+1 ):
            vtk_file_name = self.root_name+'_%03d.vtk'%(run_idx)
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



class RadiossAnalysisBase:

    def _create_d3plot_file( self, root_name ):
        try:
            from vortex_radioss.animtod3plot.Anim_to_D3plot import readAndConvert
        except:
            exit( ' *** Error Install vortex_radioss.animtod3plot from \'https://www.vortex-cae.com/vortex-radioss\'.' )

        try:
            readAndConvert( str( Path.cwd().joinpath( root_name) )  )
        except Exception as e:
            logger.error(f"Cannot convert OpenRadioss output to d3plot file: {e}")

        # Rename generated d3plot files
        # Pattern: filename.d3plot* -> d3plot*
        pattern = f"{root_name}.d3plot*"
        for file_path in glob.glob(pattern):
            # We only want to replace the prefix in the basename
            base_name = os.path.basename(file_path)
            if base_name.startswith(f"{root_name}."):
                new_name = base_name.replace(f"{root_name}.", "", 1)
                logger.info(f"Renaming {base_name} to {new_name}")
                os.rename(file_path, new_name)







class RadiossAnalysis(WorkAction,RadiossAnalysisBase):

    """ Runs an openRadioss simulation. 

        Args:
            name (str): A name for this action.
            starter_cmd (str): path to OpenRadioss executable or command. Command may include arguments 'runradios -np 1 -nt 4' 
            starter_input_path (str): OpenRadioss keyword file. Possibly parameterized.
            engine_cmd (str): path to OpenRadioss executable or command. Command may include arguments 'runradios -np 1 -nt 4' 
            engine_input_path (str): OpenRadioss input file. 
            create_d3plot (bool): Creates a d3plot files using
                            vortex_radioss.animtod3plot.Anim_to_D3plot
    """

    def __init__( self, name,
                  starter_cmd='openradioss_starter',
                  starter_input_path=simnexus.args.RADIOSS_DFLT_FNAME,
                  engine_cmd='openradioss_engine',
                  engine_input_path=None,
                  create_d3plot=False,
                  create_vtk=False,
                  to_vtk_cmd='anim_to_vtk_linux64_gf',
                  create_csv=False,
                  to_csv_cmd='th_to_csv_linux64_gf' ):

        assert starter_input_path is not None, 'No input OpenRadioss file specified. Specify the path.'
        assert engine_input_path is not None, 'No engine input OpenRadioss file specified. Specify the path.'

        super().__init__(name, starter_cmd, copy_paths=[] )
        self.starter_input_path = starter_input_path
        self.starter_input_path = Path( self.starter_input_path ).name
        self.engine_input_path = engine_input_path
        self.engine_input_path = Path( self.engine_input_path ).name
        self.starter_cmd = starter_cmd
        self.engine_cmd = engine_cmd

        self.create_d3plot = create_d3plot
        self.create_vtk = create_vtk
        self.to_vtk_cmd = to_vtk_cmd
        self.create_csv = create_csv
        self.to_csv_cmd = to_csv_cmd

        self.evaluations = []
        self.description = f'OpenRadioss analysis using input file {starter_input_path}'


    def  _clean_dir( self, base_file ):
        r = subprocess.run( [f'rm  {base_file}*.vtk {base_file}*.csv'], shell=True )


    def _create_vtk_file( self ):
        print( 'Converting openRadioss to vtk files' )

        out_file = open( 'vtk_conversion.stdout' , 'w' )
        err_file = open( 'vtk_conversion.stderr' , 'w')

        anim_files = glob.glob(RADIOSS_ROOT_NAME+'A*')

        #self._clean_dir( RADIOSS_BASE_F_NAME )

        for af in anim_files:
            #idx = '_' + af.split( RADIOSS_BASE_F_NAME )[1][1:] +'.vtk'
            idx = '_' + af.split( RADIOSS_ROOT_NAME )[1][1:] +'.vtk'
            cmd = ' ' + af + ' > ' + RADIOSS_ROOT_NAME + idx
            subprocess.run( args=[self.to_vtk_cmd+  cmd], shell=True, stdout=out_file, stderr=err_file )

        out_file.close()
        err_file.close()


    def _create_csv_file( self ):
        print( 'Converting openRadioss to csv files' )

        out_file = open( 'csv_conversion.stdout' , 'w' )
        err_file = open( 'csv_conversion.stderr' , 'w')

        hist_files = glob.glob(RADIOSS_ROOT_NAME+'T*')
        for tf in hist_files:
            print( 'Converting', tf )
            subprocess.run( args=['th_to_csv_linux64_gf '+ tf], shell=True, stdout=out_file, stderr=err_file )

        out_file.close()
        err_file.close()

    def solve( self,  val_dict=None ):

        if not Path( self.starter_input_path ).exists():
            exit( f' *** Error {self.starter_input_path} not in run directory. Likely not copied by Iterator.' )

        if val_dict is None: val_dict = {}

        with open( 'radioss_variables.json','w' ) as vf:
            json.dump( val_dict, vf )

        start_file_name = RADIOSS_BASE_F_NAME+'.rad'

        with OpenRadiosKeywordReader( self.starter_input_path ) as orkr:
            #params = orkr.parameters()
            #logger.info("Existing parameters:")
            #for name, (ptype, value) in params.items():
            #    logger.info(f"  {name} ({ptype}): {value}")

            orkr.set_parameters( val_dict )

            #params_updated = orkr.parameters()
            #logger.info("Updated parameters:")
            #for name, (ptype, value) in params_updated.items():
            #    logger.info(f"  {name} ({ptype}): {value}")

            orkr.write( start_file_name )

        shutil.copy( self.engine_input_path, RADIOSS_ENGINE_F_NAME+'.rad' )

        self._run_starter_in_dir( start_file_name )
        self._run_engine_in_dir( RADIOSS_ENGINE_F_NAME+'.rad' )

        if self.create_d3plot : self._create_d3plot_file(RADIOSS_ROOT_NAME)
        if self.create_vtk: self. _create_vtk_file( )
        if self.create_csv: self. _create_csv_file( )

        return True 


    def variables(self):
        """Returns the variables defined in the Radioss input file.

        Returns:
            set: Set of Variable instances.
        """
        file_to_open = Path(self.starter_input_path)

        if not file_to_open.exists():
            logger.warning(f"Cannot find input file for variables(): {self.starter_input_path}")
            return set()

        variables = set()
        with OpenRadiosKeywordReader(file_to_open) as orkr:
            for name, (ptype, value) in orkr.parameters().items():
                if ptype == 'REAL':
                    variables.add(simvars.FloatVariable(name, float(value)))
                elif ptype == 'INTEGER':
                    variables.add(simvars.IntSetVariable(name, int(value)))
                elif ptype in ('REAL_EXPR', 'INT_EXPR'):
                    variables.add(simvars.UnknownVariable(name, value))
                elif ptype == 'TEXT':
                    variables.add(simvars.StrSetVariable(name, str(value)))
                else:
                    variables.add(simvars.UnknownVariable(name, value))
        return variables

    def write_deck( self, dpath, variable_dict=None ):
        """ write FEA deck using given parameter values.

        e.g write_deck( {'E':210.0, 'SIG_Y':sigy} )
        """
        with OpenRadiosKeywordReader( self.starter_input_path ) as orkr:
            if variable_dict:
                orkr.set_parameters( variable_dict )
            orkr.write( dpath )


    def _run_starter_in_dir( self, start_file_name ):
        """
        new_input:
        """

        out_file = open( RADIOSS_BASE_F_NAME+'.starter.stdout' , 'w' )
        err_file = open( RADIOSS_BASE_F_NAME+'.starter.stderr' , 'w')

        subprocess.run( self.starter_cmd + ' -i ' + start_file_name, shell=True, stdout=out_file, stderr=err_file )

        have_error_termination = False
        with open( RADIOSS_BASE_F_NAME+'.starter.stdout',  'r' ) as outfile:
            for line in outfile.readlines():
                if 'ERROR TERMINATION' in line:
                    have_error_termination = True
        if have_error_termination is False:
          with open( RADIOSS_ENGINE_F_NAME+'.starter.stdout',  'r' ) as outfile:
            for line in outfile.readlines():
                if 'ERROR TERMINATION' in line:
                    have_error_termination = True
        if have_error_termination is True:
            exit( f'ERROR OpenRadios run failed in \"{self.last_job_path}\"' )

        out_file.close()
        err_file.close()




    def _run_engine_in_dir( self, engine_file_name ):
        """
        new_input:
        """

        out_file = open( RADIOSS_BASE_F_NAME+'.engine.stdout' , 'w' )
        err_file = open( RADIOSS_BASE_F_NAME+'.engine.stderr' , 'w')

        subprocess.run( self.engine_cmd + ' -i ' + engine_file_name, shell=True, stdout=out_file, stderr=err_file )


        have_error_termination = False
        with open( RADIOSS_BASE_F_NAME+'.engine.stdout',  'r' ) as outfile:
            for line in outfile.readlines():
                if 'ERROR TERMINATION' in line:
                    have_error_termination = True
        if have_error_termination is False:
          with open( RADIOSS_ENGINE_F_NAME+'.engine.stdout',  'r' ) as outfile:
            for line in outfile.readlines():
                if 'ERROR TERMINATION' in line:
                    have_error_termination = True
        if have_error_termination is True:
            exit( f'ERROR OpenRadios run failed in \"{self.last_job_path}\"' )

        out_file.close()
        err_file.close()




