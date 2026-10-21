Getting Started
===============

This guide installs OpenLens, starts the desktop application, and runs a first
lens through the Python API.

Installation
------------

From Source
^^^^^^^^^^^

.. code-block:: bash

   git clone https://github.com/pmaasz/openLens.git
   cd openLens
   pip install -e .

For plotting, optimization, and the full development toolset:

.. code-block:: bash

   pip install -e .[visualization]
   pip install -e .[dev]

Requirements
^^^^^^^^^^^^

- Python 3.10 or newer (CI tests 3.10, 3.11, and 3.12).
- PySide6 for the desktop application.
- numpy and matplotlib are strongly recommended for ray-tracing plots,
  spot/PSF/MTF analysis, and optimization.
- scipy and Pillow enable advanced diffraction and image-simulation features.

The optional packages are guarded: the core model and command-line interface
still start without them.

Quick Start
-----------

Desktop Application
^^^^^^^^^^^^^^^^^^^

.. code-block:: bash

   python3 -m openlens

The main window opens on the **Lens Selection** tab. Select a library lens or
create one, then use the **Lens Editor**, **Simulation**, **Performance**,
**Optimization**, and **Tolerancing** tabs.

Command-Line Application
^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: bash

   python3 -m openlens.lens_editor

The installed console scripts are equivalent:

.. code-block:: bash

   openlens          # desktop GUI
   openlens-cli      # command-line editor

Basic Usage Example
-------------------

Creating a Lens Programmatically
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   from openlens.lens import Lens

   lens = Lens(
       name="Biconvex demo",
       radius_of_curvature_1=50.0,   # mm, centre to the right
       radius_of_curvature_2=-50.0,  # mm, centre to the left
       thickness=10.0,               # centre thickness, mm
       diameter=25.0,                # mechanical diameter, mm
       material="BK7",
   )

   print(f"EFL: {lens.calculate_focal_length():.2f} mm")
   print(f"BFL: {lens.calculate_back_focal_length():.2f} mm")
   print(f"Working flange: {lens.calculate_working_flange_distance():.2f} mm")

The constructor resolves the stored refractive index from the material defaults.
Use :meth:`Lens.for_material` when the index should be read from the full glass
catalog, or pass ``refractive_index`` explicitly for a model glass.

Ray Tracing
^^^^^^^^^^^

.. code-block:: python

   from openlens.lens import Lens
   from openlens.ray_tracer import LensRayTracer

   lens = Lens(radius_of_curvature_1=50.0, radius_of_curvature_2=-50.0,
               thickness=5.0, diameter=25.0)
   tracer = LensRayTracer(lens)

   rays = tracer.trace_parallel_rays(num_rays=11)
   focus = tracer.find_focal_point(rays)

   print(f"Traced {len(rays)} rays")
   print(f"Paraxial focus: {focus}")

Each returned ``Ray`` carries its final position, direction, path points, and
termination state. The 3-D tracer is available as ``LensRayTracer3D``.

Aberration and Image-Quality Analysis
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   from openlens.aberrations import AberrationsCalculator
   from openlens.performance_metrics import PerformanceMetrics

   calc = AberrationsCalculator(lens)
   aberrations = calc.calculate_all_aberrations(field_angle_deg=5.0)

   print(f"Spherical: {aberrations['spherical']:.4f} mm")
   print(f"Coma: {aberrations['coma']}")
   print(f"Strehl: {aberrations['strehl']:.3f}")

   report = PerformanceMetrics(lens).format_metrics_report()
   print(report)

A failed trace can leave a field-dependent value as ``None``. That is
deliberate: it means “not measurable”, not “zero aberration”.

Optical Systems
^^^^^^^^^^^^^^^

.. code-block:: python

   from openlens.lens import Lens
   from openlens.optical_system import OpticalSystem

   crown = Lens.for_material(
       "BK7", radius_of_curvature_1=50.0, radius_of_curvature_2=-50.0,
       thickness=5.0, diameter=25.0,
   )
   flint = Lens.for_material(
       "F2", radius_of_curvature_1=-50.0, radius_of_curvature_2=-200.0,
       thickness=3.0, diameter=25.0,
   )

   system = OpticalSystem(name="Two-element demo")
   system.add_lens(crown)
   system.add_lens(flint, air_gap_before=0.5)

   print(f"System EFL: {system.get_system_focal_length():.2f} mm")
   print(f"System BFL: {system.calculate_back_focal_length():.2f} mm")

Use ``add_lens`` with the desired air gap, then ``set_aperture_stop`` to place a
stop in one of the gaps. Assemblies can also be loaded from the SQLite library
or from a JSON export.

Testing the Installation
------------------------

.. code-block:: bash

   # Full unit suite
   python3 -m unittest discover -s tests -t .

   # One module
   python3 -m unittest tests.test_lens

   # GUI flow tests (pytest-qt from the dev extra)
   QT_QPA_PLATFORM=offscreen pytest tests/gui_flows -q

Next Steps
----------

- Read the :doc:`user_guide` for the GUI workflows and export options.
- Read the :doc:`scientific/index` section for the optical equations and
  metric definitions.
- Explore the :doc:`api/index` for module and class reference.
- See :doc:`contributing` for development setup, tests, and review process.
