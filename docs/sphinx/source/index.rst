OpenLens Documentation
======================

OpenLens is an interactive optical lens design and simulation tool for single 
glass lens elements. It provides a comprehensive GUI for designing, analyzing, 
and simulating optical lenses.

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   getting_started
   user_guide
   api/index
   contributing

Features
--------

* **Interactive Lens Design**: Create and modify lens parameters in real-time
* **Ray Tracing Simulation**: Visualize ray paths through the lens
* **Aberration Analysis**: Calculate and display optical aberrations
* **3D Visualization**: View lenses in both 2D and 3D modes
* **STL Export**: Export lens geometry for 3D printing
* **Material Database**: Pre-configured optical glass materials

Quick Start
-----------

.. code-block:: bash

   # Run the GUI application
   python3 openlens.py

   # Run the CLI application
   python3 -m src.lens_editor

Installation
------------

.. code-block:: bash

   # Install package
   pip install -e .

   # Install with development dependencies
   pip install -e .[dev]

   # Install documentation dependencies
   pip install sphinx sphinx-rtd-theme

Build Documentation
-------------------

.. code-block:: bash

   cd docs/sphinx
   make html

   # View documentation
   open build/html/index.html

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
