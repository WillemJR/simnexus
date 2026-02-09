
import sys, os
sys.path.append( "/".join(os.path.dirname(os.path.realpath(__file__)).split("/")[:-2]) )
from pathlib import Path

import simflow
import simflow.radioss_actions
import simflow.jinja_actions
from simflow.variables import FloatVariable
from simflow.graph_actions import DirectedGraph, WorkFlow, WorkArea, SimulationIterator
from simflow.actions import WorkAction


fe_path = Path(__file__).parent.parent / "tests" / "spring.k"


# Example subclass of WorkAction
class ExampleNode(WorkAction):
    def solve(self, val_dict=None):
        # Example solve logic
        print( 'vd', self.name, val_dict)
        input_val = val_dict.get(self.name, 0) if val_dict else 0
        return input_val + 1
import time
class ExampleNodeLong(WorkAction):
    def solve(self, val_dict=None):
        # Example solve logic
        print( 'vd', self.name, val_dict)
        input_val = val_dict.get(self.name, 0) if val_dict else 0
        time.sleep(3)
        return input_val + 1


def test_chain(): 
    # Create nodes
    node_a = ExampleNode("S1")
    node_b = ExampleNode("B")
    node_c = ExampleNode("C")

    # Create graph and add nodes
    graph = WorkFlow( 'WF', actions = [ node_a, node_b, node_c ] )

    # Evaluate starting from node A
    #result = graph.solve( {"S1": 5,'E':3 })
    result = graph.solve( {"V1": 5,'V2':3 })
    print("Final result:", result)

    assert result == {'V1': 5, 'V2': 3, 'S1': 1, 'B': 1, 'C': 1}

def test_area(): 
    fe_path = Path(__file__).parent.parent / "tests" / "spring.k"

    head_a = ExampleNode("Head")
    node_b11 = ExampleNode("Branch_11")
    tail_a = ExampleNode("Tail")

    graph = DirectedGraph( 'aGraph' )
    graph.add_action( head_a )
    graph.add_action( node_b11, [head_a] )
    graph.add_action( tail_a, [node_b11 ] )

    area = WorkArea( graph, copy_files=[fe_path] )

    result = area.solve( {"V1": 5, "Unused": -1} )

    print("Final result:", result)

    #assert result == {'Head': 6, 'Unused': -1, 'Branch_11': 1, 'Branch_12': 1, 'Branch_21': 1, 'Tail': 1}
    
    area.rm_rundir()

def test_iter(): 
    head_a = ExampleNode("Head")
    node_b11 = ExampleNode("Branch_11")
    tail_a = ExampleNode("Tail")

    graph = DirectedGraph( 'aGraph' )
    graph.add_action( head_a )
    graph.add_action( node_b11, [head_a] )
    graph.add_action( tail_a, [node_b11 ] )

    itr = SimulationIterator( graph, copy_files=[fe_path]  )

    result = itr.solve( {"V1": 5, "Unused": -1} )
    print("Result:", result)
    assert result ==  {'V1': 5, 'Unused': -1, 'Head': 1, 'Branch_11': 1, 'Tail': 1}

    result = itr.solve( {"V1": 4, "Unused": -1} )
    print("Result:", result)
    assert result == {'V1': 4, 'Unused': -1, 'Head': 1, 'Branch_11': 1, 'Tail': 1}
    
    itr.rm_rundir()


def test_split_stream(): 
    head_a = ExampleNodeLong("Head")
    node_b11 = ExampleNodeLong("Branch_11")
    node_b12 = ExampleNode("Branch_12")
    node_b2 = ExampleNode("Branch_21")
    tail_a = ExampleNode("Tail")

    graph = DirectedGraph( 'aGraph' )
    graph.add_action( head_a )
    graph.add_action( node_b11, [head_a] )
    graph.add_action( node_b12, [node_b11] )
    graph.add_action( node_b2, [head_a] )
    graph.add_action( tail_a, [node_b12, node_b2] )

    result = graph.solve( {"V1": 5, "Unused": -1} )

    print("Final result:", result)

    assert result == {'V1': 5, 'Unused': -1, 'Head': 1, 'Branch_11': 1, 'Branch_12': 1, 'Branch_21': 1, 'Tail': 1}

# Example usage
def test_graph(): 
    """
    S1     S2
     |
     B
     | |    
     |  CC
     |   |
     C   D
     |  |
     | |
     E
    """
    # Create nodes
    node_a = ExampleNode("S1")
    node_aa = ExampleNode("S2")
    node_b = ExampleNode("B")
    node_c = ExampleNode("C")
    node_cc = ExampleNode("CC")
    node_d = ExampleNode("D")
    node_e = ExampleNode("E")

    # Create graph and add nodes
    graph = DirectedGraph( 'aGraph' )
    graph.add_action(node_a)
    graph.add_action(node_e)
    graph.add_action(node_b)
    graph.add_action(node_d)
    graph.add_action(node_c)
    graph.add_action(node_cc)
    graph.add_action(node_aa)


    #Add edges
    graph.add_edge(node_a, node_b)
    graph.add_edge(node_cc, node_d)
    graph.add_edge(node_d, node_e)
    graph.add_edge(node_c, node_e)
    graph.add_edge(node_b, node_c)
    graph.add_edge(node_b, node_cc)
    graph.add_edge(node_b, node_c)

    # Evaluate starting from node A
    result = graph.solve( {"H": 1})
    print("Final result:", result)

    assert result == {'H': 1, 'S1': 1, 'B': 1, 'CC': 1, 'D': 1, 'C': 1, 'E': 1, 'S2': 1}
    assert node_e.results() == {'H': 1, 'S1': 1, 'B': 1, 'CC': 1, 'D': 1, 'C': 1, 'E': 1}
    assert node_aa.results() == {'H': 1, 'S2': 1}




def test_mdo(): 
    """ MDO has an iterator with multiple workareas
           head
        are1 area2
           tail
    """

    head_a = ExampleNode("Head")
    node_b11 = ExampleNode("Branch_11")
    node_b22 = ExampleNode("Branch_22")
    tail_a = ExampleNode("Tail")

    graph_main = DirectedGraph( 'Main' )

    graph_main.add_action( head_a )

    graph1 = DirectedGraph( 'SOLVER_1' )
    graph1.add_action( node_b11 )
    area1 = WorkArea( graph1, copy_files=[fe_path] )

    graph_main.add_action( area1, [head_a ] )

    graph2 = DirectedGraph( 'SOLVER_2' )
    graph2.add_action( node_b22 )
    area2 = WorkArea( graph2, copy_files=[fe_path] )

    graph_main.add_action( area2, [head_a ] )

    graph_main.add_action( tail_a, [area1, area2 ] )

    itr = SimulationIterator( graph_main, clean_start=True )

    result = itr.solve( {"V1": 5, "Unused": -1} )
    print("Result:", result)
    #assert result ==  {'Head': 6, 'Unused': -1, 'Branch_11': 1, 'Tail': 1}

    # TODO need to check duplicate names, duplicate nodes

    itr.rm_rundir()
    area1.rm_rundir()
    area2.rm_rundir()


if __name__ == "__main__":
    test_mdo()
    #test_split_stream()
    #test_area()
    #test_iter()
    #test_graph()
    #test_chain()
