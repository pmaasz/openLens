Scientific Documentation
========================

These pages describe the optical model behind OpenLens: the conventions used
by the code, the equations that connect a prescription to first-order
properties, and how the image-quality metrics are computed and interpreted.

.. toctree::
   :maxdepth: 2

   optics
   image_quality
   thermal_mechanical

Scope and Conventions
---------------------

- Units are millimetres for lengths and nanometres for wavelengths unless a
  page says otherwise.
- Light travels left to right along the positive *x* axis.
- A positive radius of curvature places the centre of curvature to the right
  of the surface.
- The Lens model uses the helium d-line (587.6 nm) for catalog ``nd``/``Vd``
  data. Visualization and image-quality defaults use the photopic green line
  (550 nm).
- “Back focal length” means rear vertex to paraxial focus. “Working flange
  distance” means back focal length plus the camera-mount flange distance.

The pages are written for users who want to understand a result, and for
contributors who need to know which physical assumptions a module makes.
