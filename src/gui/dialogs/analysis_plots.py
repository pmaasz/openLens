"""
OpenLens PySide6 Analysis Plot Dialog
Reusable dialog for displaying Matplotlib plots
"""

import logging
from typing import TYPE_CHECKING, Any, Callable, Optional

from PySide6.QtCore import QThread, Signal
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

if TYPE_CHECKING:
    from matplotlib.axes import Axes
    from PySide6.QtWidgets import QWidget

logger = logging.getLogger(__name__)


class AnalysisWorker(QThread):
    """Runs one analysis off the GUI thread and hands back its payload.

    Every analysis dialog used to do its multi-second computation *before*
    creating a window, so nothing was on screen and the app simply looked
    hung. Computing in a worker lets the dialog be up and repainting first.

    Only the analysis runs here; matplotlib painting stays on the GUI thread,
    which Qt requires and the signal connection provides.
    """

    #: Emitted with whatever ``compute()`` returned.
    done = Signal(object)
    #: Emitted with the failure message when ``compute()`` raises.
    failed = Signal(str)

    def __init__(self, compute: Callable[[], Any], parent: Optional["QThread"] = None) -> None:
        """Initialize the worker.

        Args:
            compute: Zero-argument callable doing the heavy analysis.
            parent: Optional owning thread, for orderly teardown.
        """
        super().__init__(parent)
        self._compute = compute

    def run(self) -> None:
        """Execute the analysis, reporting success or failure."""
        try:
            self.done.emit(self._compute())
        except Exception as exc:  # noqa: BLE001 - reported to the user via failed
            logger.error("Analysis computation failed: %s", exc, exc_info=True)
            self.failed.emit(str(exc))


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
        # The single axes drawn into by show_computing/plot_async.
        self._content_ax = None

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

    def _content_axes(self) -> "Axes":
        """The one axes this dialog draws into, created on first use.

        Reused rather than re-created per run: calling ``get_axes()`` for both
        the status line and the result would stack a fresh subplot on every
        analysis and leave the stale "Calculating" axes on the figure.
        """
        if self._content_ax is None:
            self._content_ax = self.get_axes()
        return self._content_ax

    def show_computing(self, message: str = "Calculating…") -> None:
        """Paint a status line and make sure the window is on screen.

        Called before any expensive analysis, so the user sees a window
        immediately rather than a frozen app.
        """
        ax = self._content_axes()
        ax.clear()
        ax.text(
            0.5,
            0.5,
            message,
            ha="center",
            va="center",
            transform=ax.transAxes,
            fontsize=12,
            color=self._text_color(),
        )
        ax.set_axis_off()
        self.canvas.draw_idle()
        self.show()
        # Without this the show() above is only queued, so the work that
        # follows would run before the event loop ever repaints - which is
        # the whole bug this method exists to fix.
        QApplication.processEvents()

    def plot_async(
        self,
        compute: Callable[[], Any],
        plot: Callable[["Axes", Any], None],
    ) -> None:
        """Compute in a worker thread, then paint the result on the GUI thread.

        Args:
            compute: Zero-argument callable performing the heavy analysis.
            plot: Callable receiving the axes and the computed payload, and
                painting the finished plot.
        """
        self.show_computing()

        def _on_done(payload: Any) -> None:
            # Delivered on the GUI thread via the queued signal connection.
            ax = self._content_axes()
            ax.clear()
            ax.set_axis_on()
            plot(ax, payload)
            self.canvas.draw_idle()

        def _on_failed(message: str) -> None:
            ax = self._content_axes()
            ax.clear()
            ax.set_axis_on()
            ax.text(
                0.5,
                0.5,
                f"Analysis failed:\n{message}",
                ha="center",
                va="center",
                transform=ax.transAxes,
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
