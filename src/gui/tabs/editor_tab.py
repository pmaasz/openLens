"""
OpenLens PySide6 Editor Tab
"""

from PySide6.QtWidgets import QVBoxLayout
from .base_tab import BaseTab


class EditorTab(BaseTab):
    """Lens editor tab"""
    
    def _setup_ui(self):
        """Setup UI"""
        layout = QVBoxLayout(self)
        
        # This will use the extracted LensEditorWidget
        from ..widgets import LensEditorWidget
        self._editor = LensEditorWidget()
        layout.addWidget(self._editor)
    
    def load_lens(self, lens):
        """Load lens into editor"""
        if hasattr(self, '_editor'):
            self._editor.load_lens(lens)