"""
OpenLens PySide6 Editor Tab
"""

from PySide6.QtWidgets import QVBoxLayout
from .base_tab import BaseTab


class EditorTab(BaseTab):
    """Lens editor tab"""

    def _setup_ui(self) -> None:
        """Setup UI.

        Places the shared ``LensEditorWidget`` inside a vertical layout.
        """
        layout = QVBoxLayout(self)

        # This will use the extracted LensEditorWidget
        from ..widgets import LensEditorWidget

        self._editor = LensEditorWidget()
        layout.addWidget(self._editor)

    def load_lens(self, lens) -> None:
        """Load lens into editor.

        Args:
            lens: Lens model instance to display in the embedded editor widget.
                Ignored when the editor widget has not been created yet.
        """
        if hasattr(self, "_editor"):
            self._editor.load_lens(lens)
