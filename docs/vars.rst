
Variables
=========
Variables are used to parameterize the simulation for design changes,
creating ML training data, and design optimzation.


Using a variable as an argument to an action
--------------------------------------------

First you have to define the variable

.. code-block:: python

        from simflow.variables import FloatVariable

        temperature = FloatVariable( 'T', 75., lower_bound=10.0, upper_bound=200. )
        hv = FloatVariable( 'H', 40. )


