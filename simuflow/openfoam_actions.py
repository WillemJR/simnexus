
# DELETE BELOW
import sys, os
sys.path.append( "/home/willem/DEV/A_DEV/" )

import os
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import re
from typing import List, Tuple, Optional

import logging
logger = logging.getLogger(__name__)

from simuflow.args import Location
from simuflow.actions import WorkAction
from simuflow.util.openfoam_reader import OpenFOAMFieldReader


class OpenFOAM_Field( WorkAction ):

    @WorkAction.allow_variables_as_arguments
    def __init__( self, name, case_name, field_variable, time, location=Location.UNKNOWN ):
        super().__init__( name )
        self.case_name = case_name
        self.time = time
        self.location = location
        self.field_var = field_variable

    @WorkAction.assign_variables_values_to_members
    def eval( self, val_dict ):
        time_dir = str(int(self.time))
        reader = OpenFOAMFieldReader( case_dir = self.case_name )
        field_type, field_data = reader.field( self.field_var, time_dir = time_dir, location = self.location)
        return field_data



class OpenFOAM_History( WorkAction ):

    @WorkAction.allow_variables_as_arguments
    def __init__( self, name, case_name, field_variable, point_idx ):
        super().__init__( name )
        self.case_name = case_name
        self.point_idx = point_idx
        self.field_var = field_variable

    @WorkAction.assign_variables_values_to_members
    def eval( self, val_dict ):
        reader = OpenFOAMFieldReader( case_dir = self.case_name )
        reslts = reader.point_history( field_name=self.field_var, point_idx=self.point_idx )
        return reslts


