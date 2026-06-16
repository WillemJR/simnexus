
import logging
logger = logging.getLogger(__name__)

import json
from pathlib import Path
import subprocess

from simnexus.radioss_actions import RadiossAnalysis
from simnexus.dyna_actions import DynaAnalysis

from simnexus.args import RADIOSS_ROOT_NAME
from simnexus.args import RADIOSS_BASE_F_NAME # _0000
from simnexus.args import RADIOSS_ENGINE_F_NAME # _0001


#class DynaUsingRadioss(RadiossAnalysis,DynaAnalysis):
class RadiossUsingDynaInput(RadiossAnalysis):

    """ Runs an LS-DYNA deck using OpenRadioss. 
        A command/script running the LS-DYNA deck using OpenRadioss must be provided.
        The script should be usable as, for example, 'rad_dyna_inp zug_test3_RS.k'

        Args:
            name (str): A name for this action.
            cmd (str): path to the script executing OpenRadioss.
            input_path (str): LS-DYNA keyword file. (Possibly parameterized?)
            create_d3plot (bool): Creates a d3plot files using
                            vortex_radioss.animtod3plot.Anim_to_D3plot
    """

    def __init__( self, name, cmd, input_path,
                  create_d3plot=False,
                  create_vtk=False, to_vtk_cmd='anim_to_vtk_linux64_gf',
                  create_csv=False, to_csv_cmd='th_to_csv_linux64_gf'):

        RadiossAnalysis.__init__( self, name, 
                                  starter_cmd=cmd,
                                  starter_input_path=input_path,
                                  engine_cmd=cmd+'_DUMMY_ENGINE',
                                  engine_input_path=input_path+'_DUMMY',
                                  create_d3plot=create_d3plot,
                                  create_vtk=create_vtk,
                                  to_vtk_cmd=to_vtk_cmd,
                                  create_csv=create_csv,
                                  to_csv_cmd=to_csv_cmd )

        #DynaAnalysis.__init__(self, name, cmd, input_path=input_path )

    def solve( self,  val_dict=None ):
        if not Path( self.starter_input_path ).exists():
            exit( f' *** Error {self.starter_input_path} not in run directory. Likely not copied by Iterator.' )

        if val_dict is None: val_dict = {}

        with open( 'dyna_variables.json','w' ) as vf:
            json.dump( val_dict, vf )

        #start_file_name = RADIOSS_BASE_F_NAME+'.rad'
        start_file_name = RADIOSS_ROOT_NAME+'.k'

        #DynaAnalysis._replace_parameters( base_file_name )
        #breakpoint()
        DynaAnalysis._replace_parameters( val_dict, self.starter_input_path, start_file_name )

        #shutil.copy( self.engine_input_path, RADIOSS_ENGINE_F_NAME+'.rad' )

        self._run_in_dir( start_file_name )

        if self.create_d3plot : self._create_d3plot_file(RADIOSS_ROOT_NAME)
        if self.create_vtk: self. _create_vtk_file( )
        if self.create_csv: self. _create_csv_file( )

        return True 


    def _run_in_dir( self, start_file_name ):
        """
        new_input:
        """

        out_file = open( RADIOSS_BASE_F_NAME+'.starter.stdout' , 'w' )
        err_file = open( RADIOSS_BASE_F_NAME+'.starter.stderr' , 'w')

        #subprocess.run( self.starter_cmd + ' -i ' + start_file_name, shell=True, stdout=out_file, stderr=err_file )
        subprocess.run( self.starter_cmd + ' ' + start_file_name + ' 1', shell=True, stdout=out_file, stderr=err_file )

        have_error_termination = False
        with open( RADIOSS_BASE_F_NAME+'.starter.stdout',  'r' ) as outfile:
            for line in outfile.readlines():
                if 'ERROR TERMINATION' in line:
                    have_error_termination = True
        #if have_error_termination is False:
        #  with open( RADIOSS_ENGINE_F_NAME+'.starter.stdout',  'r' ) as outfile:
        #    for line in outfile.readlines():
        #        if 'ERROR TERMINATION' in line:
        #            have_error_termination = True
        if have_error_termination is True:
            exit( f'ERROR OpenRadios run failed in \"{Path.cwd()}\"' )

        out_file.close()
        err_file.close()


    def variables( self ):
        return DynaAnalysis.variables(self)


