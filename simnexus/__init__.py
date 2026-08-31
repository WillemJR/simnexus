__version__ = '1.2.1'

from simnexus.errors import (
    SimNexusError,
    ActionNameError,
    ParameterError,
    EvaluationError,
    SolverError,
    MissingPathError,
    DataNotFoundError,
    SerializationError,
    AsyncActionError,
)

from simnexus.args import Cleanup

import logging
logging.getLogger(__name__).addHandler(logging.NullHandler())

