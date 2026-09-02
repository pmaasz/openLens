"""
OpenLens PySide6 Selection Tab
"""

from PySide6.QtWidgets import QVBoxLayout, QLabel, QListWidget
from .base_tab import BaseTab


class SelectionTab(BaseTab):
    """Lens selection tab"""

    def _setup_ui(self) -> None:
        """Setup UI.

        Builds the title label and the lens library list widget.
        """
        layout = QVBoxLayout(self)

        title = QLabel("Lens Library")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        self._list_widget = QListWidget()
        layout.addWidget(self._list_widget)

    def refresh(self) -> None:
        """Refresh the lens list.

        Reloads the list from the parent window's current lens/system state.
        """
        # Placeholder - would load from storage
        pass
