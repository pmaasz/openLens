User Guide
==========

This guide covers the main features and workflows in OpenLens.

.. contents:: Table of Contents
   :local:
   :depth: 2

GUI Overview
------------

The OpenLens GUI is organized into several tabs for different workflows.

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

The OpenLens ray tracing system allows you to visualize how light rays travel 
through optical lenses.

Using Ray Tracing in the GUI
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Step 1: Select or Create a Lens
"""""""""""""""""""""""""""""""

1. Open the OpenLens application
2. Go to the **"Lens Selection"** tab
3. Either:
   
   - Select an existing lens from the list, OR
   - Create a new lens using the **"Editor"** tab

Step 2: Configure Simulation Parameters
"""""""""""""""""""""""""""""""""""""""

1. Navigate to the **"Simulation"** tab
2. Set the simulation parameters:
   
   - **Number of Rays**: How many light rays to trace (recommended: 10-20)
     
     - Fewer rays = faster rendering, clearer visualization
     - More rays = more detailed, denser visualization
   
   - **Ray Angle**: Controls the type of ray source
     
     - ``0°`` = Parallel rays (collimated beam, like sunlight)
     - ``>0°`` = Point source rays (diverging from a point)

Step 3: Run the Simulation
""""""""""""""""""""""""""

1. Click the **"Run Simulation"** button
2. The visualization will display:
   
   - **Lens outline** (light blue filled area with blue border)
   - **Optical axis** (dashed gray line)
   - **Ray paths** (colored lines showing light propagation)
     
     - Red = Edge rays (at the top and bottom of the lens)
     - Green = Center ray (along the optical axis)
     - Orange = Interior rays
   
   - **Focal point** (green circle, if rays converge)

Step 4: Interpret the Results
"""""""""""""""""""""""""""""

The status bar will show:

- Number of rays traced
- Focal point location (if found)
- Any errors or warnings

Understanding Ray Behavior
^^^^^^^^^^^^^^^^^^^^^^^^^^

Converging Lenses (Positive Focal Length)
"""""""""""""""""""""""""""""""""""""""""

**Examples**: Biconvex, Plano-Convex, Meniscus (with appropriate curvatures)

**Parallel Ray Behavior**:

- Rays entering parallel to the optical axis converge to a focal point
- Focal point location indicates the lens power
- Closer focal point = stronger lens

**Point Source Behavior**:

- Rays from a nearby point source are refocused to form an image
- Ray paths show how the lens bends light

Diverging Lenses (Negative Focal Length)
""""""""""""""""""""""""""""""""""""""""

**Examples**: Biconcave, Plano-Concave

**Parallel Ray Behavior**:

- Rays entering parallel spread out (diverge) after passing through
- No real focal point is formed
- Rays appear to originate from a virtual focal point behind the lens

**Point Source Behavior**:

- Source rays diverge even more after passing through
- Used for vision correction (nearsightedness) or beam expansion

Optical Principles
^^^^^^^^^^^^^^^^^^

Snell's Law
"""""""""""

The ray tracer implements Snell's law of refraction:

.. math::

   n_1 \sin(\theta_1) = n_2 \sin(\theta_2)

Where:

- n₁, n₂ = refractive indices of the two media
- θ₁, θ₂ = angles of incidence and refraction

Ray Path Segments
"""""""""""""""""

Each ray visualization shows:

1. **Initial path**: Ray approaching the lens (straight line)
2. **First refraction**: Ray enters the lens (bends at front surface)
3. **Internal path**: Ray travels through lens material
4. **Second refraction**: Ray exits the lens (bends at back surface)
5. **Final path**: Ray continues after the lens

Spherical Aberration
""""""""""""""""""""

You may notice that edge rays don't converge to exactly the same point as 
center rays. This is **spherical aberration**, a real optical phenomenon 
where rays at different heights focus at different distances.

Ray Tracing Tips
^^^^^^^^^^^^^^^^

1. **Start Simple**: Begin with parallel rays (angle = 0°) to understand basic lens behavior
2. **Moderate Ray Count**: 10-15 rays provides good visualization without clutter
3. **Compare Lenses**: Try different lens types to see how curvature affects ray paths
4. **Edge Ray Analysis**: Watch the red edge rays to see maximum refraction effects
5. **Use Clear Simulation**: Click "Clear Simulation" to reset before trying new parameters

Example Scenarios
^^^^^^^^^^^^^^^^^

Scenario 1: Measuring Focal Length
""""""""""""""""""""""""""""""""""

1. Select a biconvex lens
2. Set rays = 10, angle = 0°
3. Run simulation
4. The green dot shows the focal point location
5. Compare measured focal length with theoretical value (shown in status)

Scenario 2: Point Source Imaging
""""""""""""""""""""""""""""""""

1. Select any converging lens
2. Set rays = 11, angle = 10° (or higher)
3. Run simulation
4. Observe how rays from a point source are refocused

Scenario 3: Diverging Lens Behavior
"""""""""""""""""""""""""""""""""""

1. Select a biconcave lens
2. Set rays = 15, angle = 0°
3. Run simulation
4. Notice rays spreading out after the lens
5. No focal point is formed (negative focal length)

Programmatic Ray Tracing
^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   from src.ray_tracer import LensRayTracer
   from src.lens import Lens

   # Create a lens
   lens = Lens(
       radius_1=50.0,
       radius_2=-50.0,
       thickness=5.0,
       diameter=25.0,
       n=1.5168
   )

   # Create ray tracer
   tracer = LensRayTracer(lens)

   # Trace parallel rays
   rays = tracer.trace_parallel_rays(num_rays=21)

   # Examine results
   for ray in rays:
       print(f"Ray at height {ray['start_y']:.2f} mm")
       print(f"  Focus at x = {ray.get('focus_x', 'N/A')} mm")

Understanding Ray Trace Results
"""""""""""""""""""""""""""""""

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
"""""""""""""""""""""""""

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

Advanced Aberration Analysis
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

After running a simulation in the GUI, you can:

1. Switch to the **"Aberrations"** tab
2. Click **"Analyze Aberrations"**
3. View detailed optical quality metrics including:
   
   - Spherical aberration
   - Chromatic aberration
   - Coma, astigmatism, distortion
   - Overall lens quality score

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

Troubleshooting
---------------

Common Issues
^^^^^^^^^^^^^

**"Simulation visualizer not available"**

- **Solution**: Ensure matplotlib and numpy are installed:

  .. code-block:: bash

     pip install matplotlib numpy

**Rays go straight through without bending**

- **Solution**: Check that the lens has non-zero curvatures and valid refractive index

**No focal point found for converging lens**

- **Solution**: This may indicate high spherical aberration or the focal point 
  is outside the simulation bounds

**Visualization is cluttered**

- **Solution**: Reduce the number of rays to 5-10 for clearer paths

Technical Details
^^^^^^^^^^^^^^^^^

Ray Tracing Algorithm
"""""""""""""""""""""

- Uses geometric ray tracing with Snell's law
- Calculates surface normals from lens curvatures
- Propagates rays through air → glass → air transitions
- Detects ray-surface intersections analytically
- Handles total internal reflection

Performance
"""""""""""

- Typical simulation: <100ms for 20 rays
- Real-time updates in GUI
- Scales linearly with number of rays

Coordinate System
"""""""""""""""""

- X-axis: Optical axis (position along light path)
- Y-axis: Height above optical axis
- Origin: Typically at lens center
- Units: millimeters (mm)
