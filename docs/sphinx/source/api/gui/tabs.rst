Tab Components
==============

The ``src.gui.tabs`` package provides wrapper classes for the main window tabs.

.. toctree::
   :maxdepth: 1

   base_tab
   selection_tab
   editor_tab
   simulation_tab
   performance_tab
   comparison_tab
   export_tab

Overview
--------

Each tab class wraps the corresponding setup method from the main ``LensEditorWindow``
class, providing a modular structure for the GUI.

Base Tab Class
--------------

All tabs inherit from ``BaseTab``:

.. code-block:: python

    from src.gui.tabs import BaseTab

    class CustomTab(BaseTab):
        def setup(self) -> None:
            # Tab-specific setup code
            pass
