# Simuflow

A Python module for modelling complex simulation workflows.

The workflow consists of of actions assembled into a directed graph.
Some of the actions can be performed on remove computers. 
Some actions depends on the outcomes of other actions and workflow delays
the execution of these actions till the required prior actions have completed.

LS-DYNA, Radioss, and OpenFOAM are currently supported.

The library is designed to scale by using the Gemini CLI.


## Installation

```bash
pip install simuflow
```

## Usage

(Coming soon)

## Documentation

## License

## Todo

* How does FloatVariable interact with eval()?
     SimulationIterator( parameter_list= ) : for default values if not provided in eval


* WorkArea 
    * WorkArea and SimIter should not have a name. Instead graphName_WA and graphName_SI
    * WorkArea should have a path argument; no name
    * WorkArea should be argument to WorkFlow / Graph
    * SimIter should be subclass of WorkArea?
    * Part of above copy_files = in work_area and simulationIterator and remote


* LS-DYNA
    * should use dynakw.parameters()

* D3Plot clean up
    * Arguments doc and clean up
    * readname xxxx_d3plot must be d3plot__xxxx
    * Report BUG: coordinates is initial coordinates for all timesteps,
               node_displacement are coordinates

* similaritymeasures and numpy are requirements.

* Set up remote using grpc

