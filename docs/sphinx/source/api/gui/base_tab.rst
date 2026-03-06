Base Tab
========

.. automodule:: src.gui.tabs.base_tab
   :members:
   :undoc-members:
   :show-inheritance:

Overview
--------

The ``BaseTab`` class provides a common interface for all tab components.

.. code-block:: python

    from abc import ABC, abstractmethod
    import tkinter as tk

    class BaseTab(ABC):
        def __init__(self, parent: tk.Frame, window: 'LensEditorWindow'):
            self.parent = parent
            self.window = window

        @abstractmethod
        def setup(self) -> None:
            """Set up the tab contents."""
            pass
