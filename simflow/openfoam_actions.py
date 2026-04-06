import os
import shutil
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
    Action that runs an OpenFOAM job in the current working directory.

    Before running, files and directories listed in copy_paths are copied
    into the current working directory.  Parameter values are then written
    to system/parameters and the OpenFOAM commands are executed.

    Args:
        name (str): Name of the action.
        copy_paths (list, optional): Paths (files or directories) to copy
            into the current working directory before running.
        job_flag (JobType, optional): Combination of flags for mesh, solve,
            post-pro, vtk.  Defaults to all flags.
        solve_cmd (str, optional): The OpenFOAM solver command. Defaults to
            'laplacianFoam'.
        mesh_cmd (str, optional): The mesh generation command. Defaults to
            'blockMesh'.
    """

    @WorkAction.allow_variables_as_arguments
    def __init__( self, name, copy_paths=[], job_flag=None, solve_cmd='laplacianFoam', mesh_cmd=None ):
        super().__init__(name, copy_paths=copy_paths )
        self.solve_cmd = solve_cmd
        self.mesh_cmd = mesh_cmd
        if job_flag is None:
            self.job_flag = (JobType.CREATE_MESH |
                             JobType.RUN_SIMULATION |
                             JobType.POST_PRO |
                             JobType.EXTRACT_VTK)
        else:
            self.job_flag = job_flag
        self.description = f'OpenFOAM analysis using solver {solve_cmd}'

    def _find_parameters_file(self):
        """Locate system/parameters, checking cwd first then copy_paths sources."""
        # 1. Already present in the working directory (after a previous copy or
        #    when the action runs directly inside the case directory).
        par_file = Path.cwd() / 'system' / 'parameters'
        if par_file.exists():
            return par_file

        # 2. Search each entry in copy_paths.
        if self.copy_paths:
            for cp in self.copy_paths:
                cp = Path(cp)
                # Entry is the system/ directory itself
                candidate = cp / 'parameters'
                if candidate.exists():
                    return candidate
                # Entry is the case root directory
                candidate = cp / 'system' / 'parameters'
                if candidate.exists():
                    return candidate

        return None

    def variables( self ):
        """
        Returns the variables defined in system/parameters file.

        Returns:
            set: Set of type Variable.
        """
        par_file = self._find_parameters_file()
        if par_file is None:
            logger.warning("Parameters file not found. Have the file been copied yet?")
            return set()

        vars_list = set()
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
                vars_list.add(simvars.FloatVariable(name, val))
            except ValueError:
                vars_list.add(simvars.UnknownVariable(name, val_str))

        return vars_list

    def _update_parameters(self, val_dict):
        par_file = Path.cwd() / 'system' / 'parameters'
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
        Copies case files, updates parameters and runs OpenFOAM commands.

        Args:
            val_dict (dict): Dictionary of parameter values.

        Returns:
            bool: True if all commands succeeded.
        """

        if val_dict:
            self._update_parameters(val_dict)

        run_dir = Path.cwd()
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
    """
    Action that extracts a field from an OpenFOAM case at a given time step.

    Args:
        name (str): Name of the action.
        field_variable (str): Name of the OpenFOAM field to extract (e.g. 'U', 'p').
        time (float or Variable): Time step directory to read the field from.
        location (Location, optional): Cell location (e.g. CELL_CENTRE, FACE).
            Defaults to Location.UNKNOWN.
    """

    @WorkAction.allow_variables_as_arguments
    def __init__( self, name, field_variable, time, location=Location.UNKNOWN ):
        super().__init__( name )
        self.time = time
        self.location = location
        self.field_var = field_variable
        self.description = f'OpenFOAM field of variable {field_variable} at time {time} at location {location}'

    @WorkAction.assign_variables_values_to_members
    def solve( self, val_dict ):
        time_dir = str(self.time)
        reader = OpenFOAMFieldReader( case_dir='.' )
        field_type, field_data = reader.field( self.field_var, time_dir=time_dir, location=self.location )
        if field_type is None and field_data is None:
           logger.error(f"Could not extract OpenFOAM_Field \'{self.name}\'")

        return field_data



class OpenFOAM_History( WorkAction ):
    """
    Action that extracts the time history of a field at a single point from an OpenFOAM case.

    Args:
        name (str): Name of the action.
        field_variable (str): Name of the OpenFOAM field to extract (e.g. 'U', 'p').
        point_idx (int or Variable): Index of the point in the mesh to sample.
    """

    @WorkAction.allow_variables_as_arguments
    def __init__( self, name, field_variable, point_idx ):
        super().__init__( name )
        self.point_idx = point_idx
        self.field_var = field_variable
        self.description = f'OpenFOAM time history of variable {field_variable} at point index {point_idx}'

    @WorkAction.assign_variables_values_to_members
    def solve( self, val_dict ):
        reader = OpenFOAMFieldReader( case_dir='.' )
        reslts = reader.point_history( field_name=self.field_var, point_idx=self.point_idx )
        return reslts


