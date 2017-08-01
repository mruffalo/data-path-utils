Data path utilities
===================

Overview
--------

Over the past few years, I've organically standardized on a structure for the
code I write for my research. I've preferred to have each step of an analysis
pipeline implemented as a standalone script, though usually with functions and
classes that are importable in other modules -- such scripts often load some
data, perform some processing, save that processed data, save plots/figures,
etc.

This package provides utilities for creating and finding labeled paths, which
are suitable for storing data and plots. It's often important to be able to
compare results between different versions of some analysis step, so these
paths are timestamped to prevent repeated runs of a script from overwriting
previous results.

This package differentiates between "data" paths, to save things which might
be loaded by another script at a further stage of an analysis pipeline, and
"output" paths, for plots/etc. which are only intended for people to examine.

The main interface to this code is through the complementary functions
``create_data_path`` and ``find_newest_data_path``, which each take a single
"label" string argument and return a ``pathlib.Path``. These can be used as
follows::

  input_path = find_newest_data_path('previous_script')
  with open(input_path / 'filename') as f:
      data = load(f)

  processed_data = do_something_with(data)

  data_path = create_data_path('name_of_this_script')
  with open(data_path / 'whatever_filename', 'w') as f:
      save(processed_data, f)

Output paths are likewise created by ``create_output_path``. It is recommended
that scripts which call ``create_data_path`` use the name of the script as the
"label" argument, but this is not enforced -- one can include parameter values
or anything else relevant.

Additional functionality
------------------------

With these calls to ``create_data_path`` and ``find_newest_data_path``, one
can then model a set of such scripts as a directed graph, with nodes
representing both scripts and data paths, and edges denoting a "requires"
relationship, e.g. "script X requires data label Y, which is produced by
script Z". This package also contains standalone scripts (which require the
package NetworkX) that parse the Python files in a certain project, construct
this graph, and use this graph to provide other useful functionality in the
form of three standalone executable scripts:

* ``dependency_graph``: Plots this graph, using the ``pydotplus`` package, and
  a call to the ``dot`` GraphViz executable.

* ``list_script_dependencies``: takes a script filename as a command-line
  argument, and produces an ordered list of the data/script dependencies of
  that script by performing a topological sort on the subset of the graph
  reachable from that script. Useful for answering questions like "what should
  I run, in what order, to have everything in place to run this script of
  interest?" Note that this requires that the subgraph reachable from a script
  node be acyclic (which it should be anyway).

* ``archive_script_data_dependencies``: takes a script filename as a
  command-line argument, and identifies all data dependencies of that script.
  Archives all files under those data paths to a zip file which can easily be
  transported between machines.

Requirements
------------

Python 3.6 or newer.

Things listed under "Additional functionality" require NetworkX and pydotplus.
