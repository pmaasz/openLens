Base Tab
========

.. automodule:: openlens.gui.tabs.base_tab
   :members:
   :undoc-members:
   :show-inheritance:

Overview
--------

``BaseTab`` is the common ``QWidget`` base for main-window tabs. It provides
shared status reporting and hooks used when the active lens or assembly changes.

Tabs are constructed by ``OpenLensWindow`` and receive model updates through
signals; they do not own the library or the persistence layer.

Example
-------

.. code-block:: python

    from PySide6.QtWidgets import QLabel, QVBoxLayout
    from openlens.gui.tabs import BaseTab

    class SummaryTab(BaseTab):
        def __init__(self, parent=None) -> None:
            super().__init__(parent)
            self._label = QLabel("No active lens")
            layout = QVBoxLayout(self)
            layout.addWidget(self._label)

        def set_status(self, message: str) -> None:
            self._label.setText(message)
