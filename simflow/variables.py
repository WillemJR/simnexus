
import numpy as np

class Variable:
    """
    Abstract class for variables.
    """
    def __init__( self, name, value=None):
        self.name = name
        self.value = value
        self.type = None # Later more types as needed 
        self.upper_bound = None
        self.lower_bound = None

class FloatVariable(Variable):
    """
    Float variables.
    """

    def __init__( self, name, value=None, upper_bound=None, lower_bound=None ):
        super().__init__(name, value )
        self.value = value
        self.type = float
        self.upper_bound = upper_bound
        self.lower_bound = lower_bound
        
        if lower_bound is not None and value < lower_bound:
            raise ValueError( "FloatVariable value not in range." )
        if upper_bound is not None and value > upper_bound:
            raise ValueError( "FloatVariable value not in range." )
            

