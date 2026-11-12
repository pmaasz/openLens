OpenLens Documentation
======================

OpenLens is an interactive optical lens design and simulation tool for single
glass elements and multi-element systems. It provides a PySide6 desktop
application, a command-line interface, and a Python API for designing,
tracing, analyzing, and exporting optical systems.

.. toctree::
   :maxdepth: 2
   :caption: User Documentation

   getting_started
   user_guide
   nikon_series_e_50mm
   mcp

.. toctree::
   :maxdepth: 2
   :caption: Technical Documentation

   architecture
   contributing
   api/index

.. toctree::
   :maxdepth: 2
   :caption: Scientific Documentation

   scientific/index

Features
--------

* **Interactive lens design** with spherical, conic, parabolic, and Fresnel
  surfaces, clear apertures, bevels, and coatings.
* **Multi-element assemblies** with air gaps, an aperture stop, element
  alignment, nesting, and undo/redo.
* **Ray tracing** in 2-D and 3-D, including point sources, off-axis fields,
  multiple wavelengths, ghosts, and total internal reflection.
* **Image quality** through Seidel aberrations, spot diagrams, PSF, MTF,
  wavefront error, Strehl ratio, and encircled energy.
* **Design tools** for optimization, tolerancing, thermal/environmental
  perturbations, and desensitization.
* **Mechanical and manufacturing** output: camera mounts, working flange
  distance, lens cells, spacers, STL/STEP solids, and ISO 10110-style drawings.
* **SQLite library** for lenses, assemblies, and tolerance sets, with JSON
  interchange and image/report export.
* **Material catalog** with Sellmeier dispersion, thermal expansion, and
  Schott TIE-19 temperature coefficients where available.
* **Optional dependencies** are guarded: the core model and ray tracer start
  without numpy, matplotlib, scipy, or Pillow.

Quick Start
-----------

.. code-block:: bash

   # Install in editable mode
   pip install -e .

   # Full plotting and numerical support
   pip install -e .[visualization]

   # Run the desktop application
   python3 -m openlens

   # Run the command-line application
   python3 -m openlens.lens_editor

Installation
------------

.. code-block:: bash

   git clone https://github.com/pmaasz/openLens.git
   cd openLens
   pip install -e .
   pip install -e .[dev]     # tests, formatters, linters

PySide6 is required. numpy and matplotlib are highly recommended for
simulation and plots; scipy and Pillow enable advanced diffraction and image
simulation features.

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
   ├── openlens/__main__.py      # PySide6 GUI entry point
   ├── openlens/                 # Source package
   │   ├── lens.py               # Lens model and first-order calculations
   │   ├── optical_system.py     # Multi-element systems
   │   ├── tracer_2d.py          # 2-D geometric ray tracer
   │   ├── tracer_3d.py          # 3-D geometric ray tracer
   │   ├── aberrations.py        # Seidel and image-quality metrics
   │   ├── database.py           # SQLite persistence
   │   ├── analysis/             # PSF, MTF, spot, wavefront, ghost, thermal
   │   ├── gui/                  # PySide6 tabs, widgets, dialogs, services
   │   └── io/                   # STEP and ISO drawing export
   ├── tests/                    # Unit, functional, and GUI-flow tests
   ├── docs/                     # Sphinx documentation and mirrors
   └── setup.py                  # Package distribution

The Sphinx tree is the documentation source of truth. Start with
:doc:`getting_started` for installation and a first lens, then
:doc:`user_guide` for the application workflows. Contributors should read
:doc:`architecture` and :doc:`contributing`.

License
-------

OpenLens is released under the MIT License.

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
