.. simnexus documentation master file, created by
   sphinx-quickstart on Sat Jan 17 10:54:09 2026.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

    Add your content using ``reStructuredText`` syntax. See the `reStructuredText <https://www.sphinx-doc.org/en/master/usage/restructuredtext/index.html>`_ documentation for details.

SimNexus
=========

A Python module for orchestrating complex simulations 
with native support for LS-DYNA, OpenRadioss, and OpenFOAM.

Overview
--------

SimNexus enables the automation and coordination of
multi-physics simulation workflows — from input preparation and
remote execution to results extraction and post-processing.
The module is particularly suited for simulations that span
multiple domains, such as combined structural and fluid dynamics analyses.

SimNexus has native support for
solvers like LS-DYNA, OpenRadioss, and OpenFOAM. 

Key Features
------------

- **Workflow Management**: Define simulation workflows as directed acyclic graphs (DAGs) where actions are executed based on dependency relationships and completion status of prerequisite tasks
- **Native Solver Support**: Specify input parameter values and the results to extract for a supported solver.  Currently implemented are LS-DYNA and OpenRadioss for structural analysis, and OpenFOAM for computational fluid dynamics
- **Remote Execution**: Submit computational subgraphs to remote computing resources while maintaining local workflow coordination
- **Discoverability**: Query any graph for its inputs (``variables()``) and outputs (``outputs()``) without running it — solver actions read their parameterised input files to report variable names, types, and default values
- **Scalability**: Designed to scale through integration with an LLM CLI for the extension and use of the module.

Typical Workflow
----------------

1. Configure input files for target solvers
2. Define analysis actions and their dependencies
3. Execute simulations on designated compute resources (local or remote)
4. Extract relevant results from solver outputs
5. Aggregate and summarize findings 

SimNexus streamlines the complexity of managing heterogeneous simulation environments, enabling researchers and engineers to focus on analysis rather than workflow orchestration.


.. toctree::
   :maxdepth: 2
   :caption: Contents:

   actions_descr
   dirs
   vars
   discover
   exa
   remote
   api

