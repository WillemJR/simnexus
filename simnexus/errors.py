"""
Exception hierarchy for simnexus.

All errors raised by simnexus derive from SimNexusError, so callers can
catch any workflow failure with a single ``except SimNexusError``.
Previously these conditions called ``exit()``, which raises SystemExit:
that kills notebooks and long-running processes (e.g. the gRPC server in
``remote_actions``, whose handler catches Exception but not SystemExit).
"""


class SimNexusError(Exception):
    """Base class for all simnexus errors."""


class ActionNameError(SimNexusError):
    """An action name is invalid, duplicated, or clashes with a variable name."""


class ParameterError(SimNexusError):
    """A parameter/variable is missing, has no value, or cannot be resolved."""


class EvaluationError(SimNexusError):
    """A MathEvaluation expression could not be evaluated."""


class SolverError(SimNexusError):
    """An external solver run (LS-DYNA, OpenRadioss, OpenFOAM) failed."""


class MissingPathError(SimNexusError, FileNotFoundError):
    """A required file or directory was not found."""


class DataNotFoundError(SimNexusError):
    """Requested result data (e.g. a d3plot component or node id) is not available."""


class SerializationError(SimNexusError):
    """A value cannot be encoded for (or decoded from) the remote connection."""


class AsyncActionError(SimNexusError):
    """An action running asynchronously in a child process failed."""
