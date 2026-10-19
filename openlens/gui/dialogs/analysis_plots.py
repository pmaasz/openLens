"""
OpenLens PySide6 Analysis Plot Dialog
Reusable dialog for displaying Matplotlib plots
"""

import logging
from typing import TYPE_CHECKING, Any, Callable, Optional

from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QPushButton,
)
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar

from ..workers import AnalysisWorker

if TYPE_CHECKING:
    from matplotlib.axes import Axes
    from PySide6.QtWidgets import QWidget

logger = logging.getLogger(__name__)


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

        # Holds the in-flight AnalysisWorker so Qt does not collect it.
        self._pending_worker = None
        # The axes drawn into by show_computing/plot_async, created on first
        # use and rebuilt when the requested panel count changes.
        self._content_ax = None
        self._content_axes_list = None

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

    # ------------------------------------------------------------------
    # Non-blocking analysis
    # ------------------------------------------------------------------

    def _text_color(self) -> str:
        """Foreground colour matching the active theme."""
        dark = getattr(self.parent(), "_theme", "dark") == "dark"
        return "#e0e0e0" if dark else "black"

    def _content_axes(self, columns: int = 1):
        """The axes this dialog draws into, created (or rebuilt) on first use.

        Reused rather than re-created per run: calling ``get_axes()`` for both
        the status line and the result would stack a fresh subplot on every
        analysis and leave the stale "Calculating" axes on the figure. A
        multi-panel analysis (field curves) asks for several columns; the
        figure is rebuilt when the requested count differs from the current
        one, so a second run with another count cannot stack panels.

        Args:
            columns: How many side-by-side axes the analysis needs.

        Returns:
            A single Axes when ``columns == 1`` - the historical contract -
            otherwise a tuple of that many axes, left to right.
        """
        if self._content_axes_list is None or len(self._content_axes_list) != columns:
            self.figure.clear()
            self._content_axes_list = [
                self.get_axes(1, columns, index + 1) for index in range(columns)
            ]
        if columns == 1:
            self._content_ax = self._content_axes_list[0]
            return self._content_ax
        return tuple(self._content_axes_list)

    def show_computing(self, message: str = "Calculating…", columns: int = 1) -> None:
        """Paint a status line and make sure the window is on screen.

        Called before any expensive analysis, so the user sees a window
        immediately rather than a frozen app.

        Args:
            message: Status line to paint on the first panel.
            columns: How many panels the analysis will draw into.
        """
        axes = self._content_axes(columns)
        panels = axes if isinstance(axes, tuple) else (axes,)
        for panel in panels:
            panel.clear()
            panel.set_axis_off()
        panels[0].text(
            0.5,
            0.5,
            message,
            ha="center",
            va="center",
            transform=panels[0].transAxes,
            fontsize=12,
            color=self._text_color(),
        )
        self.canvas.draw_idle()
        self.show()
        # Without this the show() above is only queued, so the work that
        # follows would run before the event loop ever repaints - which is
        # the whole bug this method exists to fix.
        QApplication.processEvents()

    def plot_async(
        self,
        compute: Callable[[], Any],
        plot: Callable[[Any, Any], None],
        columns: int = 1,
    ) -> None:
        """Compute in a worker thread, then paint the result on the GUI thread.

        Args:
            compute: Zero-argument callable performing the heavy analysis.
            plot: Callable receiving the axes and the computed payload, and
                painting the finished plot. A single Axes when ``columns == 1``,
                otherwise a tuple of axes.
            columns: How many side-by-side panels to draw into.
        """
        self.show_computing(columns=columns)

        def _on_done(payload: Any) -> None:
            # Delivered on the GUI thread via the queued signal connection.
            axes = self._content_axes(columns)
            panels = axes if isinstance(axes, tuple) else (axes,)
            for panel in panels:
                panel.clear()
                panel.set_axis_on()
            plot(axes, payload)
            self.canvas.draw_idle()

        def _on_failed(message: str) -> None:
            axes = self._content_axes(columns)
            panels = axes if isinstance(axes, tuple) else (axes,)
            for panel in panels:
                panel.clear()
                panel.set_axis_off()
            panels[0].set_axis_on()
            panels[0].text(
                0.5,
                0.5,
                f"Analysis failed:\n{message}",
                ha="center",
                va="center",
                transform=panels[0].transAxes,
                fontsize=10,
                color=self._text_color(),
            )
            self.canvas.draw_idle()

        worker = AnalysisWorker(compute, self)
        worker.done.connect(_on_done)
        worker.failed.connect(_on_failed)
        worker.finished.connect(self._on_worker_finished)
        # Held so the QThread is not garbage-collected mid-run.
        self._pending_worker = worker
        # Non-modal on purpose: exec() would nest a second event loop and the
        # worker's signal still needs this one running to be delivered.
        worker.start()

    def _on_worker_finished(self) -> None:
        """Drop the finished worker so a later run can start cleanly."""
        self._pending_worker = None


def show_computing_dialog(
    parent: "QWidget",
    title: str,
    message: str = "Calculating…",
) -> QDialog:
    """Show a visible indeterminate-progress dialog and let Qt paint it.

    The minimum viable half of the non-blocking fix, for analyses that have no
    plot canvas to reuse: it guarantees a window is on screen and repainted
    before the blocking work begins.

    Args:
        parent: Widget to parent the dialog to.
        title: Dialog window title.
        message: Status line to display.

    Returns:
        The visible dialog; call ``exec()`` on it to block.
    """
    dialog = QDialog(parent)
    dialog.setWindowTitle(title)
    dialog.setMinimumWidth(320)
    layout = QVBoxLayout(dialog)
    layout.addWidget(QLabel(message))
    progress = QProgressBar(dialog)
    progress.setRange(0, 0)  # indeterminate
    layout.addWidget(progress)
    dialog.show()
    QApplication.processEvents()
    return dialog
