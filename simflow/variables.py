
import numpy as np

class Variable:
    """
    Abstract class for variables.
    """
    def __init__( self, name, value, data_type):
        self.name = name
        self._value = value
        self.type = data_type

    def __str__(self):
        type_name = self.type.__name__ if hasattr(self.type, '__name__') else str(self.type)
        return f"Variable Name: {self.name}, Data Type: {type_name}, Value: {self._value}"


class FloatVariable(Variable):
    """
    A variable that may only assume an float value.

    Arguments:
        name (str) : Name of the variable.
        value (float) : (Initial) Value of the variable.
        upper_bound (float) : Maximum value of the variable.
        lower_bound (float) : Minimum value of the variable.
    """

    def __init__( self, name, value, upper_bound=None, lower_bound=None ):
        super().__init__(name, value, float )
        self.upper_bound = upper_bound
        self.lower_bound = lower_bound
        
        if lower_bound is not None and value < lower_bound:
            raise ValueError( "FloatVariable value not in range." )
        if upper_bound is not None and value > upper_bound:
            raise ValueError( "FloatVariable value not in range." )
            
    @property
    def value(self):
        return self._value
    
    @value.setter
    def value(self, value):
        if self.lower_bound is not None:
            assert value >= self.lower_bound
        if self.upper_bound is not None:
            assert value <= self.upper_bound
        self._value = value



class IntSetVariable(Variable):
    """
    A variable that may only assume an integer value.
    It has a set of allowable values.

    Arguments:
        name (str) : Name of the variable.
        value (int) : (Initial) Value of the variable.
        allowable (set) : A set of allowable integer values.
    """

    def __init__( self, name, value, allowable={} ):
        super().__init__(name, value, int )
        if not allowable:
            allowable={value}
        if isinstance( allowable, list ) or isinstance( allowable, tuple ):
            self.allowable = set(allowable)
        else:
            assert isinstance( allowable, set )
            self.allowable = allowable

    @property
    def value(self):
        return self._value
    
    @value.setter
    def value(self, value):
        assert value in self.allowable
        self._value = value


class StrSetVariable(Variable):
    """
    A variable that may only assume an string value.
    It has a set of allowable values.

    Arguments:
        name (str) : Name of the variable.
        value (str) : (Initial) Value of the variable.
        allowable (set) : A set of allowable string values.
    """

    def __init__( self, name, value, allowable={} ):
        super().__init__(name, value, str )
        if not allowable:
            allowable={value}
        if isinstance( allowable, list ) or isinstance( allowable, tuple ):
            self.allowable = set(allowable)
        else:
            assert isinstance( allowable, set )
            self.allowable = allowable

    @property
    def value(self):
        return self._value
    
    @value.setter
    def value(self, value):
        assert value in self.allowable
        self._value = value

class UnknownVariable(Variable):
    """
    A variable that may assume a value of unknown type.

    Arguments:
        name (str) : Name of the variable.
        value (str) : (Initial) Value of the variable.
    """

    def __init__( self, name, value):
        super().__init__(name, value, None )

