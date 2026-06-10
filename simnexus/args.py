
from enum import Enum, Flag, auto
from collections import namedtuple

class JobType(Flag):
    """ OpenFOAM job execution stages """
    CREATE_MESH = auto()
    RUN_SIMULATION = auto()
    POST_PRO = auto()
    EXTRACT_VTK = auto()

class EvalType(Flag):
    """ Can be multiple types. Use 'if EvalType.NUMERICAL in self.type:' """
    NOT_SPECIFIED = auto()  
    FLOAT = auto()  
    NUMERICAL = auto()  # float or numpy array
    FILE = auto()
    IMAGE = auto()

class Location(Enum):
    UNKNOWN = 1
    CELL = 2
    NODAL = 3

class OptType(Enum):
    LOCAL_W_GRAD = 1
    RESTART_LOCAL_W_GRAD= 2
    DIRECT = 3
    BRUTE = 4

class MetaType(Enum):
    LINEAR = 1
    MLP = 2

class ImgComparison(Enum):
    PHASH = 1
    HU_MOMENTS = 2
    HAUSDORFF = 3
    PROCRUSTE = 4

    
OptPar = namedtuple('OptPar', ['step_size', 'epochs', 'alg'],   # epochs should be deleted
                               defaults=(0.1, 1, OptType.RESTART_LOCAL_W_GRAD) ) 

MetaPar = namedtuple('MetaPar', ['doe_type', 'num_sample', 'factorial_order', 'meta_type' ],
                               defaults=('lhd', 0, 3, MetaType.MLP ) ) 

DesPar = namedtuple('DesPar', ['obj_func', 'start', 'var_bounds', ],
                               defaults=(None, None, None ) ) 

OPT_RESULTS_DIR = 'OptimizationResults'
ACTIONS_OUTPUT_PATH = 'actions_output.pkl'

DYNA_DFLT_CMD  = 'ls-dyna'
DYNA_BASE_FILE_NAME = 'dyna_action_inp'

RADIOSS_DFLT_FNAME = 'radioss_simnexus_file.k'
RADIOSS_ROOT_NAME = 'rad_run_file'
RADIOSS_BASE_F_NAME = 'rad_run_file_0000'
RADIOSS_ENGINE_F_NAME = 'rad_run_file_0001'

