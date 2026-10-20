"""
OpenLens PySide6 Base Tab
Base class for tab implementations
"""

from typing import Optional

from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Signal

from ..theme import DARK


class BaseTab(QWidget):
    """Base class for all main-window tabs.

    Provides the shared Qt signal and the refresh/on-show lifecycle that
    concrete tabs override.
    """

    # Signal emitted when tab data updated
    data_updated = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialize the tab and run its UI setup.

        Args:
            parent: Optional parent widget (usually the main window).
        """
        super().__init__(parent)
        self._parent = parent
        self._theme = DARK
        self._setup_ui()

    def set_theme(self, theme: str = DARK) -> None:
        """Apply *theme* to the tab.

        Subclasses that own themed panes override this and call ``super()``
        so ``self._theme`` stays in step.

        Args:
            theme: "dark" or "light".
        """
        self._theme = theme

    def _setup_ui(self) -> None:
        """Set up the tab's widgets. Override in subclasses."""
        pass

    def on_show(self) -> None:
        """Called when the tab becomes visible. Override in subclasses."""
        pass

    def on_hide(self) -> None:
        """Called when the tab stops being visible. Override in subclasses."""
        pass

    def refresh(self) -> None:
        """Reload the tab's display from current model state.

        Override in subclasses; the default implementation does nothing.
        """
        pass
