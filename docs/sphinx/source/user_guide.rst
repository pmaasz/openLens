User Guide
==========

This guide covers the current PySide6 application: the library, lens and
assembly editors, simulation, image quality, optimization, tolerancing, and
export. For installation, see :doc:`getting_started`; for the physics behind a
number, see :doc:`scientific/index`.

.. contents:: Table of Contents
   :local:
   :depth: 2

GUI Overview
------------

The main window keeps one active target: either a single lens or an optical
assembly. Selecting a library row loads that target into the editor tabs.

Selection Tab
^^^^^^^^^^^^^

The **Selection** tab is the library browser. It supports:

- browsing and filtering lenses and assemblies;
- loading a row into the active-target tabs;
- creating, duplicating, renaming, and deleting library records;
- saving to the SQLite library;
- importing/exporting JSON for interchange.

The default library is a per-user SQLite database. The status bar reports save
and load failures; a failed save is never presented as a success.

Lens Editor Tab
^^^^^^^^^^^^^^^

The **Lens Editor** edits a single element and shows calculated properties as
the prescription changes.

**Surface parameters**

- Radius of curvature for each surface, in millimetres.
- Optional conic constant for each surface.
- Legacy parabolic sag control where a measured sag is preferred.
- Clear aperture and bevel for each surface.

**Geometry and material**

- Centre thickness and mechanical diameter.
- Material from the catalog, or a model glass defined by ``nd``/``Vd``.
- Design wavelength and operating temperature.
- Refractive index, either resolved from the selected glass or entered for a
  model glass.

**Coatings**

Each surface can carry a thin-film stack. Coating presets can be loaded from
the coating tools; the stack modulates reflected/transmitted energy while the
geometric ray direction continues to follow Snell's law.

**Calculated properties**

The panel updates focal length, optical power, back and front focal lengths,
working flange distance, edge thickness, and feasibility warnings. Thin or
negative edge thickness warnings mean the surfaces intersect inside the clear
aperture and the shape is not manufacturable as drawn.

Camera Mounts
^^^^^^^^^^^^^

The **Mount** group assigns a camera mount to the lens. It reports the
**working flange distance**, measured from the rear lens vertex to the sensor
plane:

.. code-block:: text

   working flange distance = back focal length + mount flange distance

Built-in mounts are C, CS, M42, M39, T, Fujifilm X, Leica M, Canon EF, and
Nikon F. Use **Manage mounts…** to add a custom mount from its flange
distance. Custom mounts are shared by every lens and stored in ``mounts.json``
under the per-user OpenLens data directory; ``OPENLENS_MOUNTS_PATH`` overrides
the file location.

.. code-block:: python

   from openlens.lens import Lens

   lens = Lens(radius_of_curvature_1=50.0, radius_of_curvature_2=-50.0)
   lens.mount_type = "M42"
   print(lens.calculate_working_flange_distance())

If the lens is afocal or the mount is unknown, the distance is ``None``. The
mount is saved with the lens in the SQLite library.

Assembly Tab
^^^^^^^^^^^^

The **Assembly** tab edits a multi-element ``OpticalSystem``:

- add, remove, reorder, and nest lens elements;
- set the air gap before each element;
- place an aperture stop in a gap and set its diameter;
- apply decenter and tilt to individual elements;
- inspect the optical layout and element positions;
- edit tolerances and alignment values for the assembly.

Assembly edits are undoable. The window-level undo/redo controls follow the
active lens editor or assembly stack.

Simulation Tab
^^^^^^^^^^^^^^

The **Simulation** tab traces rays through a lens or assembly:

- choose a parallel fan or point source;
- set ray count, field angle, and ray height range;
- trace at one or more wavelengths;
- enable ghost reflections to inspect unwanted paths;
- switch between 2-D and 3-D views;
- clear the trace and reset the view without changing the optical model.

Vignetted rays are dropped at clear apertures or the system stop. The status
area reports the trace result; a failed trace is not replaced by an empty
“perfect” image.

Performance Tab
^^^^^^^^^^^^^^^

The **Performance** tab calculates the image-quality dashboard:

- first-order values (EFL, BFL, f-number, numerical aperture);
- Seidel spherical, coma, astigmatism, field curvature, and distortion;
- axial and lateral chromatic estimates;
- RMS spot size and AIRY disk diameter;
- Strehl ratio and RMS wavefront error;
- MTF cutoff;
- spot diagram, ray fan, field curves, PSF, MTF, wavefront, and ghost views.

Expensive calculations run in background workers. If a trace or wavefront
sample fails, the affected field is reported as unavailable or invalid instead
of zero. See :doc:`scientific/image_quality` for the definitions and limits of
each metric.

Optimization Tab
^^^^^^^^^^^^^^^^

The **Optimization** tab builds a merit function from variables and targets:

- choose radii, thicknesses, air gaps, and selected system parameters as
  variables;
- target focal length, back focal length, aberration values, or other metrics;
- run the default simplex optimizer, or choose another available algorithm;
- inspect the merit value and variable values after convergence.

The merit function penalizes invalid geometry such as negative edge thickness.
Optimization runs on a copy of the model until the result is applied, so a
cancelled run does not leave a half-mutated assembly behind.

Tolerancing Tab
^^^^^^^^^^^^^^^

The **Tolerancing** tab studies manufacturing and environmental variation:

- define tolerance sets for radii, thickness, gaps, decentre, tilt, and index;
- run sensitivity or Monte Carlo analysis;
- inspect the distribution of spot, MTF, or other image-quality metrics;
- save tolerance sets with the lens or assembly metadata.

A nominal design with a small spot but no tolerance margin is not yet a
manufacturable design. Compensators and focus adjustment should be included
explicitly.

Lens Types and Sign Convention
------------------------------

OpenLens uses the standard Cartesian convention: positive radius means the
centre of curvature is to the right, and positive distances are to the right.
A biconvex lens in air therefore has ``R1 > 0`` and ``R2 < 0``.

.. list-table:: Common shapes
   :header-rows: 1
   :widths: 22 34 44

   * - Shape
     - Radii
     - Behaviour
   * - Biconvex
     - ``R1 > 0``, ``R2 < 0``
     - Positive (converging) power.
   * - Plano-convex
     - one radius flat/infinite, the other curved
     - Positive power.
   * - Biconcave
     - ``R1 < 0``, ``R2 > 0``
     - Negative (diverging) power.
   * - Meniscus
     - both radii same sign
     - Positive or negative depending on the relative magnitudes.

A flat surface is represented by an infinite radius; the model treats a zero
radius as flat in the property setters. Use ``conic_constant_1`` or
``conic_constant_2`` for an aspheric surface when a sphere is not sufficient.

Material Database
-----------------

The material catalog stores refractive index, Abbe number, Sellmeier
coefficients, thermal expansion, and Schott TIE-19 temperature coefficients
where available. Common entries include BK7, SF11, F2, and fused silica.

.. code-block:: python

   from openlens.material_database import MaterialDatabase

   db = MaterialDatabase()
   bk7 = db.get_material("BK7")
   print(f"BK7 nd: {bk7.nd:.4f}, Vd: {bk7.vd:.1f}")

   lens = Lens.for_material("BK7", radius_of_curvature_1=50.0,
                            radius_of_curvature_2=-50.0)
   print(f"Index at 550 nm: {lens.refractive_index_at(550.0):.4f}")

An unknown material is not silently replaced by BK7 when an explicit
``refractive_index`` is stored on the lens. Model glass defined by ``nd`` and
``Vd`` uses an analytic dispersion model and has no catalog thermal
coefficients.

Ray Tracing
-----------

The UI ray tracer and the Python tracers share the same surface intersection
and refraction code. A parallel fan is launched relative to the front vertex;
the default fills the full aperture so rim aberration is included. Point
sources use a position and an angular range. Off-axis analysis rotates or
displaces the bundle instead of changing the lens model.

For a first-order check, use the paraxial matrix results (EFL, BFL, FFL).
For a real design, inspect the ray fans and spot diagrams at the intended
field and wavelength.

Mounts and Mechanical Output
----------------------------

**File → Export** provides:

- **STL** for lens solids and printable models;
- **STEP** for lenses plus suggested cells, spacers, and a barrel;
- **ISO 10110** for a manufacturing-style drawing;
- **Report** for a text/plot summary.

The STEP housing is derived from the current assembly and mount. Threads are
specified in the part name but are not modeled as helical solids without a CAD
kernel. Treat the suggested housing as a mechanical starting point and verify
it in CAD before manufacture.

Persistence and Interchange
---------------------------

SQLite is the application's source of truth. **Save** updates the active
library record; **Save As...** writes a JSON copy. JSON is also used for
import/export and for user preferences such as custom mounts, but it is not the
primary library.

A lens stores its mount type, wavelength, temperature, conic/parabolic terms,
clear apertures, bevels, coatings, and metadata. An assembly stores its element
order, air gaps, stop, alignment, and tolerance metadata. Round-tripping through
SQLite or JSON preserves those fields.

Undo, Redo, and Safety
----------------------

- **Ctrl+Z / Ctrl+Y** (or the platform equivalents) undo and redo lens and
  assembly edits.
- Deleting a library row asks for confirmation; the last remaining lens cannot
  be deleted.
- Analysis runs in background workers and reports failures instead of freezing
  the window.
- Close with unsaved edits prompts before discarding them.
- Optional dependencies are guarded; missing plotting libraries disable those
  views without preventing startup.

Keyboard and Menu Reference
---------------------------

- **Ctrl+N** new lens, **Ctrl+O** open, **Ctrl+S** save, **Ctrl+Shift+S** save as.
- **Ctrl+D** duplicate the current lens.
- **Ctrl+0** reset the window layout.
- **Edit** provides undo, redo, duplicate, and delete.
- **Lens** lists library lenses and assemblies for quick switching.
- **View** switches the 2-D view orientation and resets the window.
- **Help** opens About and the keyboard-shortcut list.

Further Reading
---------------

- :doc:`scientific/optics` - sign conventions, surface sag, lens equations.
- :doc:`scientific/image_quality` - aberrations, PSF, MTF, Strehl.
- :doc:`scientific/thermal_mechanical` - thermal scaling, mounts, housings.
- :doc:`api/index` - Python API reference.
