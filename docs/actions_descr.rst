
A graph of actions
==================
All the steps in a simulation are encapsulated in actions.
The basic action types can be a change to an input deck, running an OpenFOAM analysis, or
extracting results from an analysis.

Some actions are used for control e.g. to set up the simulation as a graph where some actions depend on other actions.

The diagram below illustrates a workflow where a single geometry creation step leads to two parallel analysis branches: one for OpenRadioss and another for LS-DYNA. Each branch includes meshing and parameterization steps, and finally, the results from both solvers are combined to compute the overall design performance.

.. image:: _static/workflow_graph.svg
   :align: center
   :alt: Multi-solver workflow graph

Using an action
---------------
An action defines an operation in the workflow.
It can be anything from a geometry creation, an FEA analysis, 
to mathematical computations.
Once you have an action defined, you can call the 'solve()' method
to execute.
The return value of the 'solve()' method depends on the action; for example,
for a d3plot database extraction it may return the extracted data
as a numpy array.

.. code-block:: python

        from simflow.dyna_actions import RunDyna
        dyna = RunDyna("RunSpring", input_path="spring.k")
        ret = dyna.solve( {'K': 100.} )

You can chain actions to edit a mesh or extract results as described below.


Defining a user action
========================
You can create your own action by subclassing WorkAction 
and defining the action in the 'solve()' method.

.. code-block:: python

    from simflow.actions import WorkAction

    class AdderAction(WorkAction):
        """Adds two numbers and creates a result file."""
        def solve(self, val_dict=None):
            print(f"  [Remote] Executing AdderAction with inputs: {val_dict}")
            a = val_dict.get('a', 0)
            b = val_dict.get('b', 0)
            result = a + b

            return result



Setting up a graph
------------------
Two types of graphs are available:
firstly, a WorkFlow, a simple version executing the actions sequentially;
and a DirectedGraph, which allows execution to branch and execute
actions in parallel.

To use a WorkFlow to evaluate actions sequentially:

.. code-block:: python

    from simflow.dyna_actions import RunDyna
    from simflow.graph_actions import WorkFlow

    wf = WorkFlow("SpringWorkFlow")
    wf.add_action( RunDyna("RunSpring", input_path="spring.k") )
    d3p = d3plot_File( 'field' )
    d3p.NodalValue('n5', state=1, nid=5, component= 'node_displacement'  )
    wf.add_action( d3p )

    ret = wf.solve( {'K': 100.} )

    print( 'Displacement of node 5', ret['n5'] ) 

To use a DirectedGraph:

.. code-block:: python

    # FINISH TEST : ADD AS EXAMPLE
    from simflow.dyna_actions import RunDyna
    from simflow.graph_actions import DirectedGraph

    dg = DirectedGraph( 'MDO' )

    # OpenRadioss branch
    rr = dg.add_action( RunRadioss( name='rad',
                                    cmd='radioss_using_dyna_inp',
                                    create_d3plot=True ) )


    # LS-DYNA branch
    rs = dg.add_action( RunDyna("RunSpring", input_path="spring.k") )

    d3p = d3plot_File( 'field' )
    d3p.NodalValue('n5', state=1, nid=5, component= 'node_displacement'  )
    d3p.NodalValue('c5', state=1, nid=5, component= 'node_coordinates'  )
    dg.add_action( d3p, = 


    # Merge back
    dg.add_action( tail_a, [rr, d3p ] )


