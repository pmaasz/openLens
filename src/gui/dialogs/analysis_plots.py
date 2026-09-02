"""
OpenLens PySide6 Analysis Plot Dialog
Reusable dialog for displaying Matplotlib plots
"""

from typing import TYPE_CHECKING, Any, Optional

from PySide6.QtWidgets import QDialog, QVBoxLayout, QPushButton
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar

if TYPE_CHECKING:
    from matplotlib.axes import Axes
    from PySide6.QtWidgets import QWidget


class AnalysisPlotDialog(QDialog):
    """Reusable dialog for displaying Matplotlib plots."""

    def __init__(self, title: str, parent: Optional["QWidget"] = None) -> None:
        """Initialize the dialog with an empty figure and navigation toolbar.

        Args:
            title: Window title for the dialog.
            parent: Optional parent widget; its ``_theme`` attribute selects
                the figure face color ('dark' by default).
        """
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(800, 600)

        layout = QVBoxLayout(self)

        # Create figure and canvas
        self.figure = Figure(figsize=(8, 6), dpi=100)
        # Use a safe way to check theme from parent
        theme = getattr(parent, "_theme", "dark") if parent else "dark"
        if theme == "dark":
            self.figure.patch.set_facecolor("#1e1e1e")

        self.canvas = FigureCanvas(self.figure)
        layout.addWidget(self.canvas)

        # Add navigation toolbar
        self.toolbar = NavigationToolbar(self.canvas, self)
        layout.addWidget(self.toolbar)

        # Add close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

    def get_axes(self, *args: Any, **kwargs: Any) -> "Axes":
        """Get axes for the figure, setting dark theme if needed.

        Args:
            *args: Positional arguments forwarded to ``Figure.add_subplot``.
            **kwargs: Keyword arguments forwarded to ``Figure.add_subplot``.

        Returns:
            The newly created axes, restyled for the dark theme when active.
        """
        ax = self.figure.add_subplot(*args, **kwargs)
        theme = getattr(self.parent(), "_theme", "dark") if self.parent() else "dark"
        if theme == "dark":
            ax.set_facecolor("#1e1e1e")
            ax.tick_params(colors="#e0e0e0")
            ax.xaxis.label.set_color("#e0e0e0")
            ax.yaxis.label.set_color("#e0e0e0")
            ax.title.set_color("#e0e0e0")
            for spine in ax.spines.values():
                spine.set_edgecolor("#3f3f3f")
        return ax
