
import os
import numpy as np
import json
import subprocess
from pathlib import Path

import simflow.args
import simflow.variables as simvars
from simflow.actions import WorkAction
from simflow.graph_actions import WorkFlow

import logging
logger = logging.getLogger(__name__)

import dynakw


class RunDyna(WorkAction):

    """ This runs an LS-DYNA simulation.
        It will substitute the \*PARAMETER values with
        provided values.

        Args:
            name (str):
            cmd (str): path to ls-dyna executable or command
            input_path (str): parameterized keyword file
    """

    def __init__( self, name, cmd=simflow.args.DYNA_DFLT_CMD, input_path=None ):

        assert input_path is not None, 'No input LS-DYNA file specified.'

        super().__init__(name, cmd )
        self.input_file_path = input_path
        self.fea_file_path = Path( self.input_file_path ).name

    def solve( self,  val_dict=None ):
        """ """

        if not Path( self.fea_file_path ).exists():
            exit( f' *** Error {self.fea_file_path} not in run directory. Likely not copied by Iterator.' )

        fea_file_path = Path(self.fea_file_path).resolve()
        
        if val_dict is None: val_dict = {}

        with open( 'dyna_variables.json','w' ) as vf:
            json.dump( val_dict, vf )

        base_file_name = simflow.args.DYNA_BASE_FILE_NAME+'.k'
        
        with dynakw.DynaKeywordReader( fea_file_path ) as dkr:
            # Get existing parameters
            params = dkr.parameters()
            logger.info("\nExisting parameters:")
            for name, value in params.items():
                logger.info(f"  {name}: {value}")

            dkr.set_parameters( val_dict )

            # Get parameters after update
            params_updated = dkr.parameters()
            logger.info("\nUpdated parameters:")
            for name, value in params_updated.items():
                 logger.info(f"  {name}: {value}")

            dkr.write( base_file_name )

        have_normal_termination = self._run_solver_in_dir( base_file_name )

        return have_normal_termination 

    def _run_solver_in_dir( self, base_file_name ):
        """
        """

        out_file = open( 'run_file.stdout' , 'w' )
        err_file = open( 'run_file.stderr' , 'w')

        # LS-DYNA command syntax: ls-dyna i=input.k
        run_cmd = f"{self.cmd} i={base_file_name}"
        
        flag = subprocess.run( run_cmd, shell=True, stdout=out_file, stderr=err_file )

        out_file.close()
        err_file.close()
        
        have_normal_termination = False
        if Path('run_file.stdout').exists():
            with open( 'run_file.stdout', 'r' ) as outfile:
                 if 'Normal termination' in outfile.read():
                     have_normal_termination = True
        
        if not have_normal_termination and Path('d3hsp').exists():
             with open( 'd3hsp', 'r' ) as f:
                 if 'Normal termination' in f.read():
                     have_normal_termination = True
                 # below needs checking with ls-dyna. This is the way I remember it
                 if 'N o r m a l  t e r m i n a t i o n' in f.read():
                     have_normal_termination = True
             
             if not have_normal_termination:
                 # Check for explicit error
                 have_error = False
                 if Path('run_file.stdout').exists():
                     with open( 'run_file.stdout', 'r' ) as outfile:
                         if 'Error termination' in outfile.read():
                             have_error = True
                 
                 if have_error:
                      exit( f'ERROR LS-DYNA run failed in \"{os.getcwd()}\"' )
                 else:
                      logger.warning( f"LS-DYNA run in {os.getcwd()} finished but 'Normal termination' not found." )

        return have_normal_termination


    def variables( self ):
        """ Returns the variables defined in the template.
        The type and value of the variables are as in
        the LS-DYNA input deck.

        Returns
            list : List of Variables.
        """
        variables = []
        with dynakw.DynaKeywordReader( self.input_file_path ) as dkr:
            params = dkr.parameters()
            for name, value in params.items():
                if isinstance(value, float):
                    variables.append(simvars.FloatVariable(name, value) )
                elif isinstance(value, int):
                    variables.append(simvars.IntSetVariable(name, value) )
                elif isinstance(value, str):
                    variables.append(simvars.StrSetVariable(name, value) )
                else:
                    variables.append(simvars.UnknownVariable(name, "") )
        return variables



