User Guide
==========

This guide covers the main features and workflows in OpenLens.

GUI Overview
------------

The OpenLens GUI is organized into several tabs:

Selection Tab
^^^^^^^^^^^^^

The Selection tab allows you to:

- Browse and select from a library of pre-defined lenses
- Filter lenses by type (biconvex, plano-convex, etc.)
- View lens properties at a glance
- Load lenses for editing or simulation

Editor Tab
^^^^^^^^^^

The Editor tab provides controls for:

- **Surface Parameters**: Set radius of curvature for both surfaces
- **Lens Geometry**: Configure thickness and diameter
- **Material Properties**: Choose refractive index or select from material database
- **Real-time Preview**: See lens shape update as you modify parameters

Simulation Tab
^^^^^^^^^^^^^^

Run ray tracing simulations:

- Configure number of rays
- Set ray source position and angle
- Visualize ray paths through the lens
- Identify focal point and aberrations

Performance Tab
^^^^^^^^^^^^^^^

Analyze optical performance:

- View aberration plots
- Calculate MTF (Modulation Transfer Function)
- Spot diagram analysis
- Through-focus analysis

Comparison Tab
^^^^^^^^^^^^^^

Compare multiple lens designs:

- Side-by-side parameter comparison
- Overlay ray trace diagrams
- Compare aberration characteristics

Export Tab
^^^^^^^^^^

Export your designs:

- Save to JSON format
- Export STL for 3D printing
- Generate ray trace images
- Create PDF reports

Lens Types
----------

OpenLens supports various lens configurations:

Biconvex Lens
^^^^^^^^^^^^^

Both surfaces curve outward (positive radii on front, negative on back).

.. code-block:: python

    # Biconvex: R1 > 0, R2 < 0
    lens = Lens(radius_1=50.0, radius_2=-50.0, ...)

Plano-Convex Lens
^^^^^^^^^^^^^^^^^

One flat surface, one curved surface.

.. code-block:: python

    # Plano-convex: R1 = infinity (use large value), R2 < 0
    lens = Lens(radius_1=1e10, radius_2=-50.0, ...)

Biconcave Lens
^^^^^^^^^^^^^^

Both surfaces curve inward (negative focal length).

.. code-block:: python

    # Biconcave: R1 < 0, R2 > 0
    lens = Lens(radius_1=-50.0, radius_2=50.0, ...)

Meniscus Lens
^^^^^^^^^^^^^

Both surfaces curve in the same direction.

.. code-block:: python

    # Positive meniscus: R1 > 0, R2 > 0, |R1| < |R2|
    lens = Lens(radius_1=30.0, radius_2=50.0, ...)

Sign Conventions
----------------

OpenLens uses the standard optics sign convention:

- **Radius of curvature**: Positive if center of curvature is to the right of the surface
- **Distances**: Positive to the right of the lens
- **Focal length**: Positive for converging lenses, negative for diverging

Material Database
-----------------

OpenLens includes a database of common optical materials:

.. list-table:: Common Optical Glasses
   :header-rows: 1

   * - Material
     - Refractive Index (nd)
     - Abbe Number (Vd)
   * - BK7
     - 1.5168
     - 64.2
   * - SF11
     - 1.7847
     - 25.8
   * - F2
     - 1.6200
     - 36.4
   * - Fused Silica
     - 1.4585
     - 67.8

Using the Material Database
^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    from src.material_database import MaterialDatabase

    db = MaterialDatabase()
    
    # Get material by name
    bk7 = db.get_material("BK7")
    print(f"BK7 refractive index: {bk7['n']}")
    
    # List all materials
    materials = db.list_materials()

Ray Tracing
-----------

Understanding Ray Trace Results
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The ray tracer returns detailed information for each ray:

.. code-block:: python

    ray_data = {
        'start_x': 0.0,        # Starting X position
        'start_y': 5.0,        # Starting Y position (height)
        'angle': 0.0,          # Initial angle (radians)
        'path': [...],         # List of (x, y) points
        'focus_x': 100.0,      # X position where ray crosses axis
        'refracted': True,     # Whether ray was refracted (not TIR)
    }

Total Internal Reflection
^^^^^^^^^^^^^^^^^^^^^^^^^

When rays exceed the critical angle, total internal reflection (TIR) occurs:

.. code-block:: python

    tracer = LensRayTracer(lens)
    rays = tracer.trace_parallel_rays(num_rays=21)

    for ray in rays:
        if not ray.get('refracted', True):
            print(f"TIR occurred for ray at height {ray['start_y']}")

Aberration Analysis
-------------------

OpenLens calculates several aberration types:

Spherical Aberration
^^^^^^^^^^^^^^^^^^^^

Rays at different heights focus at different points.

.. code-block:: python

    from src.aberrations import AberrationsCalculator

    calc = AberrationsCalculator(lens)
    spherical = calc.calculate_spherical_aberration()

Chromatic Aberration
^^^^^^^^^^^^^^^^^^^^

Different wavelengths focus at different points.

.. code-block:: python

    chromatic = calc.calculate_chromatic_aberration()

Coma
^^^^

Off-axis rays form comet-shaped spots.

.. code-block:: python

    coma = calc.calculate_coma()

Saving and Loading
------------------

JSON Format
^^^^^^^^^^^

.. code-block:: python

    import json
    from src.lens import Lens

    # Save lens
    lens_data = lens.to_dict()
    with open('my_lens.json', 'w') as f:
        json.dump(lens_data, f, indent=2)

    # Load lens
    with open('my_lens.json', 'r') as f:
        data = json.load(f)
    lens = Lens.from_dict(data)

STL Export for 3D Printing
^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    from src.stl_export import export_lens_to_stl

    export_lens_to_stl(lens, 'my_lens.stl', resolution=100)

Keyboard Shortcuts
------------------

In the GUI application:

.. list-table:: Keyboard Shortcuts
   :header-rows: 1

   * - Shortcut
     - Action
   * - Ctrl+S
     - Save current lens
   * - Ctrl+O
     - Open lens file
   * - Ctrl+N
     - New lens
   * - Ctrl+R
     - Run simulation
   * - Ctrl+E
     - Export current design
