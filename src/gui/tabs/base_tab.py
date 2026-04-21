"""
OpenLens PySide6 Base Tab
Base class for tab implementations
"""

from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Signal


class BaseTab(QWidget):
    """Base tab class"""
    
    # Signal emitted when tab data updated
    data_updated = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._parent = parent
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup UI - override in subclasses"""
        pass
    
    def on_show(self):
        """Called when tab is shown"""
        pass
    
    def on_hide(self):
        """Called when tab is hidden"""
        pass
    
    def refresh(self):
        """Refresh tab data"""
        pass