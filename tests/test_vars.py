
from pathlib import Path

import simflow.variables
from simflow.jinja_actions import JinjaReplace
from simflow.graph_actions import WorkFlow, SimulationIterator, DirectedGraph
from simflow.dyna_actions import DynaAnalysis

input_path = Path(__file__).parent.parent / "tests" / "spring.k"

def test_float():
    fv = simflow.variables.FloatVariable( 'F', 1.0 )
    fv.value = 1.23

    fv = simflow.variables.FloatVariable( 'F', 4.0, upper_bound=5., lower_bound=4. )
    fv.value = 4.3

def test_intset():
    iv = simflow.variables.IntSetVariable( 'I', 1, [1,2,7] )

    iv.value = 7

def test_strset():
    iv = simflow.variables.StrSetVariable( 'I', 'foo', ['foo','fam'] )

    iv.value = 'fam'

def print_varlist( vl ):
    for v in vl:
        print( '\t', v)

def test_call():

    wf = WorkFlow("SpringWorkFlow")
    
    run_dyna = DynaAnalysis("RunSpring", input_path=str(input_path))
    wf.add_action(run_dyna)

    print( 'dyna vars', run_dyna.variables() )
    print( 'dyna vars', run_dyna.variables()[0] )
    print( 'workflow vars' )
    print_varlist( wf.variables() )

    jj =  JinjaReplace( name='SetVars', input_file_path='tests/par_tens.k' )
    wf.add_action( jj )

    print( 'JinjaReplace vars:', jj.variables() )
    print( 'workflow vars:' )
    print_varlist( wf.variables() )

    # Graph
    graph = DirectedGraph( 'aGraph' )
    graph.add_action( run_dyna )
    graph.add_action( jj )
    print( 'graph vars' )
    print_varlist( graph.variables() )

    # SimulationIterator
    itr = SimulationIterator( graph, copy_files=[input_path]  )
    print( 'SimulationIterator vars' )
    print_varlist( itr.variables() )

    itr.rm_rundir() 

if __name__ == "__main__":
    #test_float()
    #test_intset()
    #test_strset()
    test_call()
