The Windsurf model
==================

What is it?
-----------

The Windsurf model is a composite model that connects three different
model cores for simulating integrated nearshore and aeolian sediment
transport. The Windsurf model connects the following model cores:

* XBeach - Nearshore hydrodynamics (`<http://www.xbeach.org>`_)
* AeoLiS - Supply-limited aeolian sediment transport
  (`<http://openearth.github.io/aeolis/>`_)
* Coastal Dune Model (CDM) - Aeolian sediment transport and wind shear
  accounting for morphological feedback and vegetation

The Windsurf model simulates 2DH nearshore and aeolian sediment
transport as a result of short waves, infragravity waves, tides and
currents and wind. The Windsurf model accounts for multiple sediment
fractions and bed layers, sediment supply limitations in aeolian
transport as a result of moisture contents, sediment sorting and beach
armoring, morphological feedback and vegetation.

How to use it?
--------------

The Windsurf composite model features a Python interface that connects
the three different model cores and acts as a user-interface for the
end-user. The Python interface can be downloaded as Python package
from the OpenEarth GitHub respository:
`<https://github.com/openearth/windsurf/>`_.

The installation and configuration of a Windsurf model is described in
the following subsections.

.. _installation:

Installation
^^^^^^^^^^^^

Download the individual model cores from their respective repositories
and compile the models as libraries according to their manuals:

* XBeach:
  `<https://svn.oss.deltares.nl/repos/xbeach/branches/fedor-template/>`_
  (at this moment the XBeach trunk does not include the necessary BMI
  interface, use the "fedor-template" branch instead)
* AeoLiS: `<https://github.com/openearth/windsurf/>`_
* CDM: ?

Download the Windsurf Python package from
`<https://github.com/openearth/windsurf/>`_ and install using:

.. code-block:: text

   >>> python setup.py install

Check if the installation is successful using:

.. code-block:: text

   >>> windsurf --help
   windsurf : a composite model for simulating integrated nearshore and aeolian sediment transport

   Usage:
       windsurf <config> [--verbose=LEVEL]

   Positional arguments:
       config             configuration file

   Options:
       -h, --help         show this help message and exit
       --verbose=LEVEL    print logging messages [default: 30]
   
.. _configuration:

Configuration
^^^^^^^^^^^^^

The Windsurf model is configured through a single JSON file. The JSON
file contains different categories of configuration options that are
treated in this section. A JSON configuration file may contain the
following:

.. literalinclude:: ../example/windsurf.json
   :language: json

time
""""

Time management.

models
""""""

Model engine specification and configuration.

exchange
""""""""

Data exchange between model engines.

regimes
"""""""

Environmental regime specification and configuration.

scenario
""""""""

Scenario configuration (sequence of regimes)

Execution
^^^^^^^^^

Execute the model by calling the following command from the
command-line:

.. code-block:: text

   >>> windsurf windsurf.json

To print more output to the screen decrease the verbosity number as
follows:

.. code-block:: text

   >>> windsurf windsurf.json --verbose=20

Tow write the output to a file use the following:

.. code-block:: text

   >>> windsurf windsurf.json --verbose=20 > windsurf.log
