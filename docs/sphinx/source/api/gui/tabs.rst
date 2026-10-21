Tab Components
==============

The ``openlens.gui.tabs`` package contains the main-window workspaces. Every
tab derives from :class:`openlens.gui.tabs.base_tab.BaseTab` and receives the
active lens or assembly from ``OpenLensWindow``.

.. toctree::
   :maxdepth: 1

   base_tab
   selection_tab
   editor_tab
   assembly_tab
   simulation_tab
   performance_tab
   optimization_tab
   tolerancing_tab

Overview
--------

+----------------------+-----------------------------------------------------+
| Tab                  | Responsibility                                      |
+======================+=====================================================+
| ``SelectionTab``     | Browse and load library lenses and assemblies.      |
+----------------------+-----------------------------------------------------+
| ``EditorTab``        | Host the single-lens editor widget.                 |
+----------------------+-----------------------------------------------------+
| ``AssemblyTab``      | Edit element order, gaps, stop, alignment, undo.    |
+----------------------+-----------------------------------------------------+
| ``SimulationTab``    | Trace and display ray fans in 2-D/3-D.              |
+----------------------+-----------------------------------------------------+
| ``PerformanceTab``   | Aberrations, spot/PSF/MTF, wavefront, reports.      |
+----------------------+-----------------------------------------------------+
| ``OptimizationTab``  | Build and run merit-function optimization.          |
+----------------------+-----------------------------------------------------+
| ``TolerancingTab``   | Sensitivity and Monte Carlo yield analysis.         |
+----------------------+-----------------------------------------------------+

All tabs use Qt signals to report changes back to the window. Analysis tabs
move expensive work to worker threads so the GUI remains responsive.

Example
-------

.. code-block:: python

    from PySide6.QtWidgets import QVBoxLayout, QLabel
    from openlens.gui.tabs import BaseTab

    class CustomTab(BaseTab):
        def __init__(self, parent=None) -> None:
            super().__init__(parent)
            layout = QVBoxLayout(self)
            layout.addWidget(QLabel("Custom analysis"))
