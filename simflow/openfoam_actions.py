import os
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import re
import subprocess
from typing import List, Tuple, Optional

import logging
logger = logging.getLogger(__name__)

from simflow.args import Location, JobType
from simflow.actions import WorkAction
import simflow.variables as simvars
from simflow.util.openfoam_reader import OpenFOAMFieldReader


class OpenFOAMAnalysis( WorkAction ):
    """
    Action that runs an OpenFOAM job.

    It replaces values in system/parameters with provided values and 
    executes OpenFOAM commands based on the job_flag.

    Args:
        name (str): Name of the action.
        case_dir (str): Directory of the OpenFOAM case.
        job_flag (JobType, optional): Combination of flags for mesh, solve, post-pro, vtk.
            Defaults to all flags.
        solve_cmd (str, optional): The OpenFOAM solver command. Defaults to 'laplacianFoam'.
        mesh_cmd (str, optional): The mesh generation command. Defaults to 'blockMesh'.
    """

    @WorkAction.allow_variables_as_arguments
    def __init__( self, name, case_dir, job_flag=None, solve_cmd='laplacianFoam', mesh_cmd=None ):
        super().__init__( name )
        self.case_dir = case_dir
        self.solve_cmd = solve_cmd
        self.mesh_cmd = mesh_cmd
        if job_flag is None:
            self.job_flag = (JobType.CREATE_MESH | 
                             JobType.RUN_SIMULATION | 
                             JobType.POST_PRO | 
                             JobType.EXTRACT_VTK)
        else:
            self.job_flag = job_flag

    def variables( self ):
        """
        Returns the variables defined in system/parameters file.

        Returns:
            list: List of type Variable.
        """
        par_file = Path(self.case_dir) / 'system' / 'parameters'
        if not par_file.exists():
            logger.warning(f"Parameters file not found: {par_file}")
            return []
        
        vars_list = []
        with open(par_file, 'r') as f:
            content = f.read()
        
        # Remove comments
        content = re.sub(r'//.*', '', content)
        content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
        
        # Remove FoamFile section
        content = re.sub(r'FoamFile\s*\{.*?\}', '', content, flags=re.DOTALL)
        
        # Find key-value pairs
        matches = re.finditer(r'^\s*(\w+)\s+([^;]+);', content, flags=re.MULTILINE)
        for match in matches:
            name, val_str = match.groups()
            val_str = val_str.strip()
            try:
                val = float(val_str)
                vars_list.append(simvars.FloatVariable(name, val))
            except ValueError:
                vars_list.append(simvars.UnknownVariable(name, val_str))
        
        return vars_list

    def _update_parameters(self, val_dict):
        par_file = Path(self.case_dir) / 'system' / 'parameters'
        if not par_file.exists():
            return
        
        with open(par_file, 'r') as f:
            content = f.read()
        
        for name, value in val_dict.items():
            # Match parameter name at start of line (optionally with whitespace) 
            # followed by whitespace and current value
            pattern = rf'^(\s*{name})\s+[^;]+;'
            replacement = rf'\1 {value};'
            content = re.sub(pattern, replacement, content, flags=re.MULTILINE)
        
        with open(par_file, 'w') as f:
            f.write(content)

    def _run_command(self, cmd, run_dir):
        logger.info(f"Running command: {cmd} in {run_dir}")
        with open(run_dir / 'openfoam.stdout', 'a') as out, \
             open(run_dir / 'openfoam.stderr', 'a') as err_file:
            result = subprocess.run(cmd, shell=True, cwd=run_dir, stdout=out, stderr=subprocess.PIPE)
            stderr_output = result.stderr.decode('utf-8', errors='replace')
            if stderr_output:
                err_file.write(stderr_output)

        if result.returncode != 0:
            error_msg = stderr_output.strip() if stderr_output else f"exit code {result.returncode}"
            logger.error(f"Command failed: {cmd!r}\n  {error_msg}")

        return result.returncode == 0

    @WorkAction.assign_variables_values_to_members
    def solve( self, val_dict ):
        """
        Updates parameters and runs OpenFOAM commands.

        Args:
            val_dict (dict): Dictionary of parameter values.

        Returns:
            bool: True if all commands succeeded.
        """
        if val_dict:
            self._update_parameters(val_dict)
        
        run_dir = Path(self.case_dir).resolve()
        success = True

        if self.job_flag & JobType.CREATE_MESH:
            cmd = self.mesh_cmd if self.mesh_cmd else 'blockMesh'
            success = success and self._run_command(cmd, run_dir)
        
        if success and (self.job_flag & JobType.RUN_SIMULATION):
            success = success and self._run_command(self.solve_cmd, run_dir)
            
        if success and (self.job_flag & JobType.POST_PRO):
            success = success and self._run_command('paraFoam -builtin -touch', run_dir)
            
        if success and (self.job_flag & JobType.EXTRACT_VTK):
            success = success and self._run_command('foamToVtk', run_dir)
            
        return success


class OpenFOAM_Field( WorkAction ):

    @WorkAction.allow_variables_as_arguments
    def __init__( self, name, case_dir, field_variable, time, location=Location.UNKNOWN ):
        super().__init__( name )
        self.case_dir = case_dir
        self.time = time
        self.location = location
        self.field_var = field_variable

    @WorkAction.assign_variables_values_to_members
    def solve( self, val_dict ):
        #time_dir = str(int(self.time))
        time_dir = str(self.time)
        reader = OpenFOAMFieldReader( case_dir = self.case_dir )
        field_type, field_data = reader.field( self.field_var, time_dir = time_dir, location = self.location)
        return field_data



class OpenFOAM_History( WorkAction ):

    @WorkAction.allow_variables_as_arguments
    def __init__( self, name, case_dir, field_variable, point_idx ):
        super().__init__( name )
        self.case_dir = case_dir
        self.point_idx = point_idx
        self.field_var = field_variable

    @WorkAction.assign_variables_values_to_members
    def solve( self, val_dict ):
        reader = OpenFOAMFieldReader( case_dir = self.case_dir )
        reslts = reader.point_history( field_name=self.field_var, point_idx=self.point_idx )
        return reslts


