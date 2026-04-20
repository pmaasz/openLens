"""
OpenLens PySide6 Lens Visualization Container
Container widget that combines 2D and 3D lens views with tab switching
"""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QTabWidget
from PySide6.QtCore import Qt

from .lens_viz_2d import _2DVisualizationWidget
from .lens_viz_3d import _3DVisualizationWidget


class LensVisualizationWidget(QWidget):
    """Lens visualization widget with 2D and 3D views"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._lens = None
        self._view_mode = "2D"
        self._rotation = 0
        
        self.setMinimumSize(400, 300)
        self.setStyleSheet("background-color: #1e1e1e;")
        
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Create tab widget for 2D/3D toggle
        self._tab_widget = QTabWidget()
        self._tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #3f3f3f;
                background-color: #1e1e1e;
            }
            QTabBar::tab {
                background-color: #2d2d2d;
                color: #aaa;
                padding: 8px 16px;
                border: 1px solid #3f3f3f;
            }
            QTabBar::tab:selected {
                background-color: #1e1e1e;
                color: #fff;
            }
        """)
        
        # 2D visualization
        self._2d_widget = _2DVisualizationWidget()
        self._tab_widget.addTab(self._2d_widget, "2D")
        
        # 3D visualization
        self._3d_widget = _3DVisualizationWidget()
        self._tab_widget.addTab(self._3d_widget, "3D")
        
        self._tab_widget.currentChanged.connect(self._on_tab_changed)
        
        layout.addWidget(self._tab_widget)
    
    def _on_tab_changed(self, index):
        """Handle tab switch"""
        if index == 0:
            self._view_mode = "2D"
        else:
            self._view_mode = "3D"
    
    def update_lens(self, lens):
        """Update visualization with new lens data"""
        self._lens = lens
        self._2d_widget.update_lens(lens)
        self._3d_widget.update_lens(lens)