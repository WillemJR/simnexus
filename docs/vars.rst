
Variables
=========
Variables are used to parameterize the simulation for design changes,
creating ML training data, and design optimization.


Using a variable as an argument to an action
--------------------------------------------

First, you have to define the variable

.. code-block:: python

        from simflow.variables import FloatVariable

        temperature = FloatVariable( 'T', 75., lower_bound=10.0, upper_bound=200. )
        etime = FloatVariable( 'ET', 40. )


Having defined a variable you can use it to control actions

.. code-block:: python

        from simflow.variables import FloatVariable
        from simflow.openfoam_actions import OpenFOAM_Field

        # define variable
        etime = FloatVariable( 'ET', 40. )
        # The variable can be used to construct an action
        # Below it is used to control an extraction time
        f = OpenFOAM_Field( name='TF', case_dir="WING", field_variable='T',
                            time=etime, location=Location.NODAL)
        f.solve( {'ET':50} )

