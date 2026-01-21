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

* How does FloatVariable interact with RunRadioss and eval()? SimulationIterator( parameter_list= )

* WorkArea should be argument to WorkFlow / Graph


* LS-DYNA should use dynakw.parameters()

* Git rid of RunFEA. All that does is make sure files are copied. Class FileRequiredments or class RequiredFile?
* Part of above copy_files = in work_area and simulationIterator and remote

* CurveSimilarity should be its own file. Move out of actions.

* similaritymeasures and numpy are requirements.

