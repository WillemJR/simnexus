
Variables
=========
Variables are used to parameterize the simulation for design changes,
creating ML training data, and design optimization.

Discovering variables
---------------------
Actions that read parameterized input files expose a ``variables()`` method
that returns the set of variables defined in the template.
For ``JinjaReplace`` and ``DynaAnalysis`` the action first looks for the
template at ``input_file_path``. If that path cannot be opened it falls back
to searching ``copy_paths`` for an entry whose filename matches
``input_file_path``. This allows variable discovery before the file has been
copied to the run directory.

.. code-block:: python

    from simflow.jinja_actions import JinjaReplace

    jj = JinjaReplace(name='SetVars', input_file_path='template.k',
                      copy_paths=['path/to/source/template.k'])
    for v in jj.variables():
        print(v)



Variable description
--------------------
Each variable has an optional ``description`` argument.
If not provided, the class docstring is used as the description.

.. code-block:: python

    from simflow.variables import FloatVariable

    temperature = FloatVariable('T', 75., lower_bound=10., upper_bound=200.,
                                description='Inlet temperature in Kelvin')
    print(temperature.description)  # 'Inlet temperature in Kelvin'

    # Without description, falls back to the class docstring:
    k = FloatVariable('K', 0.2)
    print(k.description)  # 'A variable that may only assume an float value. ...'


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

