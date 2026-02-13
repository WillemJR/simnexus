.. simflow documentation master file, created by
   sphinx-quickstart on Sat Jan 17 10:54:09 2026.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

    Add your content using ``reStructuredText`` syntax. See the `reStructuredText <https://www.sphinx-doc.org/en/master/usage/restructuredtext/index.html>`_ documentation for details.

Simflow
=========

A Python module for orchestrating complex simulations 
with native support for LS-DYNA, Radioss, and OpenFOAM.

Overview
--------

Simflow enables the automation and coordination of
multi-physics simulation workflows — from input preparation and
remote execution to results extraction and post-processing.
The module is particularly suited for simulations that span multiple domains, such as combined structural and fluid dynamics analyses.

Simflow has native support for
solvers like LS-DYNA, Radioss, and OpenFOAM. 

Key Features
------------

- **Workflow Management**: Define simulation workflows as directed acyclic graphs (DAGs) where actions are executed based on dependency relationships and completion status of prerequisite tasks
- **Remote Execution**: Submit computational subgraphs to remote computing resources while maintaining local workflow coordination
- **Multi-Solver Support**: Currently compatible with LS-DYNA and Radioss for structural analysis, and OpenFOAM for computational fluid dynamics
- **Dependency Resolution**: Automatically manages execution order based on inter-action dependencies, ensuring downstream actions wait for required upstream results
- **Scalability**: Designed to scale through integration with the Gemini CLI for the extension and use of the module.

Typical Workflow
----------------

1. Configure input files for target solvers
2. Define analysis actions and their dependencies
3. Execute simulations on designated compute resources (local or remote)
4. Extract relevant results from solver outputs
5. Aggregate and summarize findings for review

Simflow streamlines the complexity of managing heterogeneous simulation environments, enabling researchers and engineers to focus on analysis rather than workflow orchestration.


.. toctree::
   :maxdepth: 2
   :caption: Contents:

   actions_descr
   vars
   exa
   remote
   api

