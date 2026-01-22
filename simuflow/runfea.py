import jinja2

from pathlib import Path
from jinja2 import meta

from simuflow.actions import WorkAction

class RunFEA(WorkAction):
    """ """
    def __init__( self, name, cmd, fe_path=None ):
        """ 

        Args:
            name (str):
            cmd (str): not used
            fe_path (str):
        """
        super().__init__(name, cmd )
        self.fea_file_path = fe_path
        self.base_fea_file_path = fe_path[:-2]


