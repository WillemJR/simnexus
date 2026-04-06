
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


class DynaAnalysis(WorkAction):

    """ This runs an LS-DYNA simulation.
        It will substitute the PARAMETER values with
        provided values.

        Args:
            name (str):
            cmd (str): path to ls-dyna executable or command
            input_path (str): parameterized keyword file
            copy_paths (list) : List of file and directories to be copied to work area.
    """

    def __init__( self, name, cmd=simflow.args.DYNA_DFLT_CMD, input_path=None,copy_paths=[] ):

        assert input_path is not None, 'No input LS-DYNA file specified.'

        super().__init__(name, cmd, copy_paths=copy_paths )
        self.input_file_path = input_path
        self.description = f'LS-DYNA analysis using input file {input_path}'

    def solve( self,  val_dict=None ):
        """ """

        if not Path( self.input_file_path ).exists():
            exit( f' *** Error {self.input_file_path} not in run directory. Likely not copied by Iterator.' )

        if val_dict is None: val_dict = {}

        with open( 'dyna_variables.json','w' ) as vf:
            json.dump( val_dict, vf )

        base_file_name = simflow.args.DYNA_BASE_FILE_NAME+'.k'
        
        with dynakw.DynaKeywordReader( self.input_file_path ) as dkr:
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

        Tries self.input_file_path first; if that cannot be opened,
        searches self.copy_paths for an entry whose filename matches.

        Returns
            set : Set of Variables.
        """
        file_to_open = None
        input_path = Path( self.input_file_path )

        if input_path.exists():
            file_to_open = input_path
        else:
            target_name = input_path.name
            for cp in self.copy_paths:
                cp_path = Path(cp)
                if cp_path.is_file() and cp_path.name == target_name:
                    file_to_open = cp_path
                    break
                elif cp_path.is_dir():
                    candidate = cp_path / target_name
                    if candidate.exists():
                        file_to_open = candidate
                        break

        if file_to_open is None:
            logger.warning( f"Cannot find input file for variables(): {self.input_file_path}" )
            return set()

        variables = set()
        with dynakw.DynaKeywordReader( file_to_open ) as dkr:
            params = dkr.parameters()
            for name, value in params.items():
                if isinstance(value, float):
                    variables.add( simvars.FloatVariable(name, value) )
                elif isinstance(value, int):
                    variables.add( simvars.IntSetVariable(name, value) )
                elif isinstance(value, str):
                    variables.add( simvars.StrSetVariable(name, value) )
                else:
                    variables.add( simvars.UnknownVariable(name, "") )

        return variables



