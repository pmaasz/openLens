"""
OpenLens PySide6 Editor Tab
"""

from PySide6.QtWidgets import QWidget, QVBoxLayout
from .base_tab import BaseTab


class EditorTab(BaseTab):
    """Lens editor tab"""
    
    def _setup_ui(self):
        """Setup UI"""
        layout = QVBoxLayout(self)
        
        # This will use the extracted LensEditorWidget
        try:
            from src.gui.widgets import LensEditorWidget
            self._editor = LensEditorWidget()
            layout.addWidget(self._editor)
        except ImportError:
            # Fallback - inline widget will be used
            pass
    
    def load_lens(self, lens):
        """Load lens into editor"""
        if hasattr(self, '_editor'):
            self._editor.load_lens(lens)