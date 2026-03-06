OpenLens Documentation
======================

OpenLens is an interactive optical lens design and simulation tool for single 
glass lens elements. It provides a comprehensive GUI for designing, analyzing, 
and simulating optical lenses.

.. toctree::
   :maxdepth: 2
   :caption: User Documentation

   getting_started
   user_guide

.. toctree::
   :maxdepth: 2
   :caption: Developer Documentation

   architecture
   contributing
   api/index

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

   # Clone the repository
   git clone https://github.com/yourusername/openLens.git
   cd openLens

   # Install package
   pip install -e .

   # Install with development dependencies
   pip install -e .[dev]

   # Install optional dependencies for full functionality
   pip install matplotlib numpy scipy

Build Documentation
-------------------

.. code-block:: bash

   cd docs/sphinx
   make html

   # View documentation
   open build/html/index.html

Project Structure
-----------------

.. code-block:: text

   openLens/
   ├── openlens.py          # Main entry point
   ├── src/                 # Source code (30+ modules)
   │   ├── lens.py         # Core Lens class
   │   ├── ray_tracer.py   # Ray tracing engine
   │   ├── aberrations.py  # Aberration calculations
   │   └── gui/            # GUI components
   ├── tests/              # Test suites (34 test files)
   ├── docs/               # Documentation
   │   └── sphinx/         # Sphinx documentation
   └── setup.py            # Package distribution

License
-------

OpenLens is released under the MIT License.

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
