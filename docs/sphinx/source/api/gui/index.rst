GUI Package
===========

The ``openlens.gui`` package provides modular GUI components for the OpenLens application.

.. toctree::
   :maxdepth: 2

   tooltip
   theme
   storage
   tabs

Package Overview
----------------

The GUI package extracts reusable components from the main ``lens_editor_gui.py``:

- **tooltip** - Tooltip widget for displaying hover information
- **theme** - Theme management and color definitions
- **storage** - Lens persistence and storage utilities
- **tabs** - Tab component wrappers for the main window

Usage
-----

Import GUI components directly from the package:

.. code-block:: python

    from openlens.gui import ToolTip, ThemeManager, LensStorage
    from openlens.gui.tabs import SelectionTab, EditorTab, SimulationTab
