"""
OpenLens PySide6 Simulation Tab
"""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from .base_tab import BaseTab


class SimulationTab(BaseTab):
    """Ray tracing simulation tab"""
    
    def _setup_ui(self):
        """Setup UI"""
        layout = QVBoxLayout(self)
        
        title = QLabel("Simulation")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)
        
        # Note: Full simulation visualization remains inline in openlens.py
        # This stub provides the tab structure
        placeholder = QLabel("Use inline simulation from openlens.py")
        placeholder.setStyleSheet("color: #666; padding: 50px;")
        layout.addWidget(placeholder)