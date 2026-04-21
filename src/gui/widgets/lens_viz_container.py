from PySide6.QtWidgets import QWidget, QTabWidget, QVBoxLayout
from PySide6.QtGui import QColor
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
        
        # Create 2D/3D tab structure
        self._viz_tabs = QTabWidget()
        self._viz_tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #3f3f3f; }
            QTabBar::tab { background: #2d2d2d; color: #e0e0e0; padding: 5px 10px; }
            QTabBar::tab:selected { background: #0078d4; }
        """)
        
        # 2D view (custom canvas)
        self._2d_widget = _2DVisualizationWidget()
        self._viz_tabs.addTab(self._2d_widget, "2D")
        
        # 3D view (matplotlib embedded)
        self._3d_widget = _3DVisualizationWidget()
        self._viz_tabs.addTab(self._3d_widget, "3D")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._viz_tabs)
    
    def set_view_mode(self, mode):
        """Set view mode (2D, 3D, Side)"""
        self._view_mode = mode
        if mode.startswith("3D"):
            self._viz_tabs.setCurrentIndex(1)
        else:
            self._viz_tabs.setCurrentIndex(0)
            self._2d_widget.set_view_mode(mode)
    
    def update_lens(self, lens):
        """Update visualization with new lens data"""
        self._lens = lens
        self._2d_widget.update_lens(lens)
        self._3d_widget.update_lens(lens)
