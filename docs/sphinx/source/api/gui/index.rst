GUI Package
===========

The ``openlens.gui`` package provides PySide6 windows, tabs, dialogs, widgets,
and persistence helpers for the desktop application.

.. toctree::
   :maxdepth: 2

   theme
   storage
   tabs

Package Overview
----------------

- ``openlens.gui.tabs`` - main-window workspaces.
- ``openlens.gui.widgets`` - lens editor, 2-D/3-D lens views, simulation,
  assembly, and performance visualizations.
- ``openlens.gui.dialogs`` - startup, mount manager, analysis plots, and image
  simulation dialogs.
- ``openlens.gui.services`` - library and export coordination used by the
  window.
- ``openlens.gui.workers`` - background analysis worker.
- ``openlens.gui.theme`` - dark/light palettes and stylesheets.
- ``openlens.gui.storage`` - SQLite-backed ``LensStorage`` facade.

The package imports optional GUI pieces defensively so the optical core and CLI
still work in a headless environment without a display.

Usage
-----

.. code-block:: python

    from openlens.gui.tabs import (
        AssemblyTab,
        EditorTab,
        OptimizationTab,
        PerformanceTab,
        SelectionTab,
        SimulationTab,
        TolerancingTab,
    )

The main window is created by :func:`openlens.__main__.main`; embedders should
normally launch the application rather than constructing individual tabs.
