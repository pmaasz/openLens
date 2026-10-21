Architecture
============

OpenLens is a Python 3.10+ desktop application for designing, tracing, and
analyzing single lenses and multi-element optical systems. This page describes
the current code structure. For the underlying equations, see the
:doc:`scientific/index` section; for day-to-day use, see the
:doc:`user_guide`.

.. contents:: Table of Contents
   :local:
   :depth: 2

System Context
--------------

The application has three entry points over one shared optical core:

.. code-block:: text

   ┌──────────────────────────┐   ┌──────────────────────────┐
   │ PySide6 desktop GUI      │   │ Command line / Python    │
   │ python3 -m openlens      │   │ python3 -m openlens.     │
   │                          │   │ lens_editor              │
   └────────────┬─────────────┘   └────────────┬─────────────┘
                │                              │
                └──────────────┬───────────────┘
                               ▼
   ┌──────────────────────────────────────────────────────────┐
   │ Optical domain                                           │
   │ Lens · OpticalSystem · surfaces · mounts · materials     │
   └──────────────┬───────────────────────────────┬───────────┘
                  │                               │
                  ▼                               ▼
   ┌────────────────────────────┐   ┌──────────────────────────┐
   │ Analysis and design        │   │ Persistence and export   │
   │ ray tracers · aberrations  │   │ SQLite · JSON · STL     │
   │ PSF/MTF · optimizer        │   │ STEP · SVG · reports    │
   └────────────────────────────┘   └──────────────────────────┘

The GUI and CLI never own optical state. They construct and mutate model
objects, then ask the analysis and persistence layers for results.

Application Layers
------------------

.. list-table::
   :header-rows: 1
   :widths: 24 34 42

   * - Layer
     - Main modules
     - Responsibility
   * - Presentation
     - ``openlens/__main__.py``, ``openlens/gui/``
     - Main window, tabs, widgets, dialogs, theming, background workers.
   * - Application services
     - ``openlens/gui/services/``, ``openlens/gui/storage.py``,
       ``openlens/updater.py``
     - Library operations, export coordination, GUI-facing persistence, and
       release checks/self-update planning.
   * - Optical domain
     - ``openlens/lens.py``, ``optical_system.py``, ``optical_node.py``,
       ``ray.py``, ``material_database.py``, ``mounts.py``
     - Validation, surfaces, systems, glass models, and camera mounts.
   * - Analysis and design
     - ``openlens/analysis/``, ``aberrations.py``, ``ray_tracer.py``,
       ``optimizer.py``, ``tolerancing.py``, ``environmental.py``
     - Ray tracing, image quality, optimization, tolerancing, and
       environmental perturbations.
   * - Persistence
     - ``openlens/database.py``, ``openlens/paths.py``
     - SQLite schema, migrations, and per-user file locations.
   * - Interchange and export
     - ``openlens/io/``, ``stl_export.py``, ``export_formats.py``
     - STEP/STL geometry, ISO 10110 drawings, plots, and reports.

GUI Structure
-------------

``openlens/__main__.py`` owns the ``OpenLensWindow`` and the active model.
The center of the window is a tab widget:

.. code-block:: text

   OpenLensWindow
   ├── Selection tab       library list, filters, lens/assembly activation
   ├── Lens Editor tab     LensEditorWidget with live calculated properties
   ├── Assembly tab        OpticalSystem elements, gaps, stop, alignment
   ├── Simulation tab      ray fans, wavelengths, ghosts, 2-D/3-D views
   ├── Performance tab     metrics, spot/PSF/MTF, image simulation
   ├── Optimization tab    variables, targets, optimization runs
   └── Tolerancing tab     tolerance sets, Monte Carlo, reports

Tabs derive from ``BaseTab`` and receive model updates from the window.
Expensive analysis runs in ``AnalysisWorker`` (``openlens/gui/workers.py``)
rather than on the GUI thread. Long operations report progress through
signals and keep the window responsive.

The lens editor is a reusable widget rather than tab-specific logic. It
emits ``lens_modified`` and ``lens_updated``, and uses a ``QUndoStack`` for
property edits. The assembly editor maintains its own undo stack; a
window-level ``QUndoGroup`` routes the active stack.

Core Models
-----------

``Lens``
    One refracting element. It stores the two surface radii, center thickness,
    diameter, material/index, wavelength, temperature, conic/parabolic terms,
    clear apertures, bevels, coatings, and the camera ``mount_type``. It
    calculates focal lengths, back/front focal distances, working flange
    distance, edge thickness, and serialization dictionaries.

``OpticalSystem``
    An ordered collection of ``LensElement`` records and ``AirGap`` records.
    It also owns an ``OpticalAssembly`` tree for nested groups, decenter/tilt
    alignment, and the aperture stop. The flat element and gap lists are kept
    in sync with the tree.

``MountCatalog``
    Nine built-in mounts plus user-defined mounts. Custom mounts are stored in
    a per-user JSON configuration file because they are user preferences, not
    optical library records.

``MaterialDatabase``
    Glass catalog with Sellmeier dispersion, Abbe numbers, thermal expansion,
    and dn/dT data. Missing catalog entries fall back gracefully, and model
    glass can be defined by ``nd``/``Vd`` without a catalog row.

Analysis Pipeline
-----------------

Ray tracing has a paraxial path and exact geometric paths:

1. Build rays from the selected source (parallel fan, point source, or grid).
2. Intersect each ray with the next surface. Sphere, plane, parabolic, conic,
   and Fresnel profiles have separate intersection routines.
3. Refract with Snell's law, including total internal reflection handling.
4. Apply clear apertures, bevels, and the system stop; mark vignetted rays.
5. Record the path and optical path length for visualization and analysis.

The analysis modules reuse those traced rays:

- ``analysis/paraxial.py`` places the paraxial focus and provides the
  near-axis reference.
- ``analysis/spot_diagram.py`` and ``analysis/geometric.py`` measure spot size,
  field curves, distortion, and encircled energy.
- ``analysis/psf_mtf.py`` computes PSF, MTF, and related image-quality data.
- ``aberrations.py`` combines exact traces with Seidel estimators, clearly
  returning ``None`` when a trace fails instead of reporting a perfect lens.
- ``performance_metrics.py`` assembles the dashboard and text reports.

Optimization and tolerancing operate on copies or controlled mutations of the
live system. The merit function penalizes invalid geometry such as negative
edge thickness.

Persistence
-----------

SQLite is the application's source of truth. ``DatabaseManager`` creates and
migrates the schema, stores individual lenses, assemblies, and tolerance-set
metadata, and keeps them consistent when rows are renamed or deleted. The
default database lives under the per-user OpenLens data directory; an explicit
path is used by tests and by callers that need an isolated library.

JSON is an interchange and export format, not primary application state.
``Lens.to_dict()``/``from_dict()`` and the matching ``OpticalSystem`` methods
round-trip both database payloads and user exports. User preferences that are
not library records - custom mounts, for example - use small atomic JSON files
under the same user-data directory.

Export
------

- STL and STEP write solid geometry for lenses and suggested housings.
- ``io/step_reader.py`` imports STEP parts for mechanical integration.
- ``export_formats.py`` and ``io/export.py`` produce plots, prescriptions, and
  ISO 10110-style drawings.
- The Export service in the GUI resolves the active lens or assembly and shows
  failures instead of silently writing a truncated file.

Threading and Failure Handling
------------------------------

- GUI analysis runs in worker threads; results return by Qt signals.
- The startup release check and update download also run in
  ``AnalysisWorker``. ``openlens/updater.py`` performs the HTTP and version
  work without importing Qt, so it is testable on its own.
- A frozen Linux or Windows update writes a small helper script, launches it
  detached, and exits. The helper waits for the old PID, replaces the
  executable, and starts it again; the next launch runs the usual database
  migrations. macOS extracts the downloaded app and hands it to the desktop.
- Database and file writes use transactions or atomic replacement.
- Optional dependencies (``numpy``, ``matplotlib``, ``scipy``, ``Pillow``) are
  imported behind availability flags. The core Lens model, ray tracer, and CLI
  start without them.
- Public calculations return ``None`` for undefined results (afocal systems,
  failed traces) rather than inventing a zero.

Extension Points
----------------

Adding a material
    Extend the material catalog or call ``MaterialDatabase`` at runtime. Keep
    the ``nd``/``Vd`` values and any thermal coefficients together.

Adding an analysis
    Build it under ``openlens/analysis/``, accept a ``Lens`` or
    ``OpticalSystem``, return plain dictionaries/dataclasses, and keep expensive
    work out of constructors. Add a tab/dialog hook only after the calculator
    is testable without Qt.

Adding an export format
    Put pure file writing in ``openlens/io/`` or the existing export module,
    validate the active model before writing, and return a summary for the GUI.

Adding a surface profile
    Update the Lens model, validation, sag/normal geometry, and all tracers
    that claim to support it. Add intersection tests against an analytic case.

Further Reading
---------------

- :doc:`scientific/optics` - sign conventions, thick-lens equations, Snell's law.
- :doc:`scientific/image_quality` - aberrations, PSF, MTF, and Strehl.
- :doc:`scientific/thermal_mechanical` - thermal scaling, dn/dT, and housings.
- :doc:`api/index` - module and class reference.
- :doc:`contributing` - development setup, tests, and review process.
