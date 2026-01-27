from pathlib import Path
import os,shutil
import json
from abc import ABC, abstractmethod
from collections import defaultdict
from itertools import product

import numpy as np

from simflow.actions import WorkAction

import logging
logger = logging.getLogger(__name__)


class ContainerAction(WorkAction):
    """
    Move action to container, move files and results

    NYI: Actions should have observer / callback pattern

    Maybe command pattern.
    Maybe async pattern.


    Maybe use gRPC
    Maybe use Apache Kafka or Airflow
    """

    def __init__( self, name, action ):
        pass

    def eval(self,  val_dict=None ):
        pass



