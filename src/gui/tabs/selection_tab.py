"""
OpenLens PySide6 Selection Tab
"""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QListWidget
from .base_tab import BaseTab


class SelectionTab(BaseTab):
    """Lens selection tab"""
    
    def _setup_ui(self):
        """Setup UI"""
        layout = QVBoxLayout(self)
        
        title = QLabel("Lens Library")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)
        
        self._list_widget = QListWidget()
        layout.addWidget(self._list_widget)
    
    def refresh(self):
        """Refresh the lens list"""
        # Placeholder - would load from storage
        pass