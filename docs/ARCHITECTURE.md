# OpenLens Architecture

> **The authoritative page is
> [`docs/sphinx/source/architecture.rst`](sphinx/source/architecture.rst).**
> This file is kept as a short entry point for links to `docs/ARCHITECTURE.md`.
> Build the full documentation with `cd docs/sphinx && make html`.

OpenLens is a Python 3.10+ desktop application built on one optical core:

- **Presentation** - `openlens/gui/` (PySide6 tabs, widgets, dialogs) and
  `openlens/__main__.py`.
- **Optical domain** - `lens.py`, `optical_system.py`, `ray.py`,
  `material_database.py`, and `mounts.py`.
- **Analysis and design** - `analysis/`, `aberrations.py`, `ray_tracer.py`,
  `optimizer.py`, `tolerancing.py`, and `environmental.py`.
- **Persistence** - `database.py` and `paths.py`; SQLite is the source of truth.
- **Interchange and export** - `io/`, `stl_export.py`, and `export_formats.py`.

The GUI and CLI construct model objects and ask the analysis and persistence
layers for results. They do not own optical state. Expensive GUI analysis runs in
worker threads, and invalid or failed calculations return `None` rather than a
misleading zero.

See the Sphinx page for the current module map, tab layout, ray-tracing pipeline,
persistence rules, and extension points.
