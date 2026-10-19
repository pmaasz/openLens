"""
OpenLens Image Simulation Dialog
Side-by-side comparison of original and simulated image
"""

import logging
import os
from typing import TYPE_CHECKING, Optional

import numpy as np
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QFileDialog,
    QMessageBox,
)
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar

from ..workers import AnalysisWorker, stop_worker

if TYPE_CHECKING:
    from matplotlib.axes import Axes
    from PySide6.QtWidgets import QWidget
    from ...optical_system import OpticalSystem

logger = logging.getLogger(__name__)


class ImageSimulationDialog(QDialog):
    """Dialog for image simulation with side-by-side comparison."""

    #: How long a running simulation gets to unwind before it is terminated.
    _WORKER_STOP_TIMEOUT_MS = 3000

    def __init__(self, system: "OpticalSystem", parent: Optional["QWidget"] = None) -> None:
        """Initialize the dialog for simulating an image through a system.

        Args:
            system: Optical system whose PSF is used for the simulation.
            parent: Optional parent widget; its ``_theme`` attribute selects
                the figure styling ('dark' by default).
        """
        super().__init__(parent)
        self._system = system
        self._original_image = None
        self._simulated_image = None

        self.setWindowTitle(f"Image Simulation - {system.name}")
        self.resize(1000, 700)

        layout = QVBoxLayout(self)

        # Controls
        ctrl_layout = QHBoxLayout()
        self._import_btn = QPushButton("Import Image")
        self._import_btn.clicked.connect(self._on_import_image)
        self._run_btn = QPushButton("Run Simulation")
        self._run_btn.clicked.connect(self._on_run_simulation)
        self._run_btn.setEnabled(False)
        self._reset_btn = QPushButton("Reset View")
        self._reset_btn.clicked.connect(self._reset_view)
        self._reset_btn.setEnabled(False)
        self._reset_btn.setToolTip("Zoom out to full image (also double-click)")

        ctrl_layout.addWidget(self._import_btn)
        ctrl_layout.addWidget(self._run_btn)
        ctrl_layout.addWidget(self._reset_btn)
        ctrl_layout.addStretch()
        layout.addLayout(ctrl_layout)

        # Visualization
        self.figure = Figure(figsize=(10, 6), dpi=100)
        theme = getattr(parent, "_theme", "dark") if parent else "dark"
        if theme == "dark":
            self.figure.patch.set_facecolor("#1e1e1e")

        self.canvas = FigureCanvas(self.figure)
        layout.addWidget(self.canvas)

        self.toolbar = NavigationToolbar(self.canvas, self)
        layout.addWidget(self.toolbar)

        # Buttons
        btn_layout = QHBoxLayout()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

        # Initialize plots – share view so zoom/pan is synchronized
        self._ax_orig = self.figure.add_subplot(121)
        self._ax_sim = self.figure.add_subplot(122, sharex=self._ax_orig, sharey=self._ax_orig)
        self._setup_axes(self._ax_orig, "Original Image")
        self._setup_axes(self._ax_sim, "Simulated Image")
        self.figure.tight_layout()

        # Click-to-zoom / drag-to-pan state
        self._is_panning = False
        self._pan_start_xy = None  # (x, y) in display coords
        self._pan_start_lim = None  # (xlim, ylim)
        self._last_click_time = 0.0

        # Holds the in-flight simulation so closing cannot collect a live
        # QThread. accept()/Esc do not send a closeEvent, so both paths stop it.
        self._pending_worker = None
        self.finished.connect(lambda _result=0: self._stop_pending_worker())

        # Connect mouse events for intuitive zoom/pan (in addition to toolbar)
        self.canvas.mpl_connect("button_press_event", self._on_mouse_press)
        self.canvas.mpl_connect("button_release_event", self._on_mouse_release)
        self.canvas.mpl_connect("motion_notify_event", self._on_mouse_move)
        self.canvas.mpl_connect("scroll_event", self._on_scroll)

    def _setup_axes(self, ax: "Axes", title: str) -> "Axes":
        """Apply dark-theme styling, hide axes, and set the subplot title."""
        theme = getattr(self.parent(), "_theme", "dark") if self.parent() else "dark"
        if theme == "dark":
            ax.set_facecolor("#1e1e1e")
            ax.tick_params(colors="#e0e0e0")
            ax.xaxis.label.set_color("#e0e0e0")
            ax.yaxis.label.set_color("#e0e0e0")
            ax.title.set_color("#e0e0e0")
            for spine in ax.spines.values():
                spine.set_edgecolor("#3f3f3f")
        ax.set_title(title)
        ax.axis("off")
        return ax

    @staticmethod
    def _view_is_zoomed(xlim, ylim, shape) -> bool:
        """Whether ``(xlim, ylim)`` shows less than the full ``shape`` image.

        imshow's full extent is ``[-0.5, w-0.5] x [h-0.5, -0.5]`` because the
        origin is upper, so the height difference is negative on the inverted
        y axis and must be compared by magnitude. The previous inline check in
        ``_on_simulation_done`` compared it signed, making ``was_zoomed``
        always True.
        """
        h, w = shape[0], shape[1]
        return not (abs((xlim[1] - xlim[0]) - w) < 1 and abs(abs(ylim[1] - ylim[0]) - h) < 1)

    def _is_zoomed(self) -> bool:
        """Return True if the current view is not the full image."""
        if self._original_image is None:
            return False
        try:
            return self._view_is_zoomed(
                self._ax_orig.get_xlim(), self._ax_orig.get_ylim(), self._original_image.shape
            )
        except Exception as e:
            logger.debug("Could not read the zoom state: %s", e)
            return False

    def _update_reset_button(self) -> None:
        """Enable Reset only when zoomed and an image is loaded."""
        try:
            self._reset_btn.setEnabled(self._original_image is not None and self._is_zoomed())
        except Exception as e:
            logger.debug("Could not update the Reset button: %s", e)

    def _reset_view(self) -> None:
        """Zoom out to show the full image on both sides."""
        if self._original_image is None:
            return
        try:
            h, w = self._original_image.shape[0], self._original_image.shape[1]
            # imshow default view
            self._ax_orig.set_xlim(-0.5, w - 0.5)
            self._ax_orig.set_ylim(h - 0.5, -0.5)
            self.canvas.draw_idle()
        except Exception as e:
            logger.debug("Could not reset the view: %s", e)
        self._update_reset_button()

    def _zoom_at(self, xdata: float, ydata: float, factor: float = 2.0) -> None:
        """Zoom centered at (xdata, ydata) by factor (>1 zoom in, <1 zoom out).

        Both sides stay synchronized via sharex/sharey.
        """
        if self._original_image is None or xdata is None or ydata is None:
            return
        try:
            xlim = self._ax_orig.get_xlim()
            ylim = self._ax_orig.get_ylim()
            cur_w = abs(xlim[1] - xlim[0])
            cur_h = abs(ylim[1] - ylim[0])
            # factor >1 => zoom in (smaller view), <1 => zoom out (larger view)
            new_w = cur_w / factor
            new_h = cur_h / factor
            # Clamp to image bounds and avoid degenerate view
            h, w = self._original_image.shape[0], self._original_image.shape[1]
            new_w = max(20, min(new_w, w))
            new_h = max(20, min(new_h, h))
            # Center at click, clamp so view stays inside image
            x0 = max(-0.5, min(xdata - new_w / 2, w - 0.5 - new_w))
            x1 = x0 + new_w
            # y is inverted: ylim[0] is top (h-0.5), ylim[1] is bottom (-0.5)
            y0 = max(-0.5, min(ydata - new_h / 2, h - 0.5 - new_h))
            y1 = y0 + new_h
            # Preserve inverted order
            if ylim[0] > ylim[1]:
                self._ax_orig.set_xlim(x0, x1)
                self._ax_orig.set_ylim(y0 + new_h, y0)
            else:
                self._ax_orig.set_xlim(x0, x1)
                self._ax_orig.set_ylim(y0, y0 + new_h)
            self.canvas.draw_idle()
        except Exception as e:
            logger.debug("Could not zoom to the clicked point: %s", e)
        self._update_reset_button()

    def _on_mouse_press(self, event) -> None:  # type: ignore[no-untyped-def]
        """Click to zoom in, double-click/right-click to zoom out, else start pan."""
        if event.inaxes not in (self._ax_orig, self._ax_sim):
            return
        if self._original_image is None:
            return
        # Double-click always resets
        if getattr(event, "dblclick", False):
            self._reset_view()
            return
        # Right-click resets
        if event.button == 3:
            self._reset_view()
            return
        if event.button != 1:
            return
        # If not zoomed, a single left-click magnifies at click position
        if not self._is_zoomed():
            if event.xdata is not None and event.ydata is not None:
                self._zoom_at(event.xdata, event.ydata, factor=2.0)
            return
        # Already zoomed – start panning
        self._is_panning = True
        self._pan_start_xy = (event.x, event.y)
        self._pan_start_lim = (self._ax_orig.get_xlim(), self._ax_orig.get_ylim())

    def _on_mouse_release(self, event) -> None:  # type: ignore[no-untyped-def]
        self._is_panning = False
        self._pan_start_xy = None
        self._pan_start_lim = None
        self._update_reset_button()

    def _on_mouse_move(self, event) -> None:  # type: ignore[no-untyped-def]
        if not getattr(self, "_is_panning", False):
            return
        if event.inaxes not in (self._ax_orig, self._ax_sim):
            # Allow dragging even if cursor leaves axes slightly
            pass
        if self._pan_start_xy is None or self._pan_start_lim is None:
            return
        if event.x is None or event.y is None:
            return
        try:
            dx = event.x - self._pan_start_xy[0]
            dy = event.y - self._pan_start_xy[1]
            # Convert display delta to data delta
            # Use axis transform: display -> data
            inv = self._ax_orig.transData.inverted()
            # Two points to get scale
            p0 = inv.transform((0, 0))
            p1 = inv.transform((1, 0))
            scale_x = p1[0] - p0[0]
            p0y = inv.transform((0, 0))
            p1y = inv.transform((0, 1))
            scale_y = p1y[1] - p0y[1]
            # Pan is opposite to mouse movement (like grabbing the image)
            (x0, x1), (y0, y1) = self._pan_start_lim
            new_x0 = x0 - dx * scale_x
            new_x1 = x1 - dx * scale_x
            new_y0 = y0 - dy * scale_y
            new_y1 = y1 - dy * scale_y
            # Clamp to image bounds
            h, w = self._original_image.shape[0], self._original_image.shape[1]
            # Clamp x
            view_w = new_x1 - new_x0
            if new_x0 < -0.5:
                new_x0 = -0.5
                new_x1 = new_x0 + view_w
            if new_x1 > w - 0.5:
                new_x1 = w - 0.5
                new_x0 = new_x1 - view_w
            # Clamp y (inverted)
            view_h = new_y1 - new_y0
            # y is inverted, but clamping same
            y_min, y_max = -0.5, h - 0.5
            low, high = (y_max, y_min) if y0 > y1 else (y_min, y_max)
            # Simpler: just ensure both within bounds
            if min(new_y0, new_y1) < y_min:
                shift = y_min - min(new_y0, new_y1)
                new_y0 += shift
                new_y1 += shift
            if max(new_y0, new_y1) > y_max:
                shift = y_max - max(new_y0, new_y1)
                new_y0 += shift
                new_y1 += shift
            self._ax_orig.set_xlim(new_x0, new_x1)
            self._ax_orig.set_ylim(new_y0, new_y1)
            self.canvas.draw_idle()
        except Exception as e:
            logger.debug("Could not pan the view: %s", e)

    def _on_scroll(self, event) -> None:  # type: ignore[no-untyped-def]
        """Mouse wheel zoom – scroll up to zoom in, down to zoom out."""
        if event.inaxes not in (self._ax_orig, self._ax_sim):
            return
        if self._original_image is None or event.xdata is None or event.ydata is None:
            return
        # Typical scroll: step 1.5x
        factor = 1.5 if event.button == "up" else 0.67 if event.button == "down" else 1.0
        if factor == 1.0:
            return
        self._zoom_at(event.xdata, event.ydata, factor=factor)

    def _on_import_image(self) -> None:
        """Load a user-selected image and display it as the original."""
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Select Image for Simulation",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp);;All Files (*)",
        )
        if filepath:
            try:
                from PIL import Image

                img = Image.open(filepath).convert("RGB")
                # Resize if too large for performance
                max_size = 512
                if max(img.size) > max_size:
                    img.thumbnail((max_size, max_size))

                self._original_image = np.array(img) / 255.0
                self._ax_orig.imshow(self._original_image)
                self._ax_orig.set_title(f"Original: {os.path.basename(filepath)}")
                self._run_btn.setEnabled(True)
                # Keep sim in sync with orig (shared axes already, but ensure)
                try:
                    self._ax_sim.set_xlim(self._ax_orig.get_xlim())
                    self._ax_sim.set_ylim(self._ax_orig.get_ylim())
                except Exception as e:
                    logger.debug("Could not sync the simulated view: %s", e)
                self.canvas.draw()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load image: {e}")

    def _on_run_simulation(self) -> None:
        """Simulate the loaded image; the analysis runs in a worker thread.

        ``simulate_image`` traces the PSF and convolves the image, which is
        fast enough to look like a hang when it runs inside the button
        handler. The status line is painted first and the result is drawn when
        the worker reports back.
        """
        if self._original_image is None:
            return
        if self._pending_worker is not None and self._pending_worker.isRunning():
            return

        try:
            from ...analysis.psf_mtf import ImageQualityAnalyzer

            analyzer = ImageQualityAnalyzer(self._system)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Simulation failed: {e}")
            return

        original = self._original_image

        # Show "Calculating..." message
        self._ax_sim.clear()
        self._setup_axes(self._ax_sim, "Calculating Simulation...")
        self.canvas.draw()

        worker = AnalysisWorker(lambda: analyzer.simulate_image(original), self)
        self._pending_worker = worker
        worker.done.connect(self._on_simulation_done)
        worker.failed.connect(self._on_simulation_failed)
        worker.finished.connect(lambda w=worker: self._on_worker_finished(w))
        worker.start()

    def _on_simulation_done(self, simulated) -> None:
        """Paint the simulated image, keeping the user's zoom in sync."""
        self._simulated_image = simulated

        # Show results – keep view synchronized with original
        # Save current view (so zoom is preserved across simulation)
        try:
            prev_xlim = self._ax_orig.get_xlim()
            prev_ylim = self._ax_orig.get_ylim()
            was_zoomed = self._view_is_zoomed(prev_xlim, prev_ylim, self._original_image.shape)
        except Exception as e:
            logger.debug("Could not snapshot the view before redrawing: %s", e)
            was_zoomed = False
            prev_xlim = prev_ylim = None

        self._ax_sim.clear()
        self._setup_axes(self._ax_sim, "Simulated Image")
        # No sharex/sharey re-binding here: the subplots were created shared
        # (add_subplot(..., sharex=, sharey=)) and clear() keeps them shared.
        self._ax_sim.imshow(self._simulated_image)
        # Restore synchronized view if user was zoomed, otherwise show full
        if was_zoomed and prev_xlim is not None and prev_ylim is not None:
            self._ax_orig.set_xlim(prev_xlim)
            self._ax_orig.set_ylim(prev_ylim)
        self.canvas.draw()

    def _on_simulation_failed(self, message: str) -> None:
        """Report a failed simulation without leaving the status line up."""
        logger.error("Image simulation failed: %s", message)
        QMessageBox.critical(self, "Error", f"Simulation failed: {message}")

    def _on_worker_finished(self, worker) -> None:
        """Drop the finished worker so a later run can start cleanly."""
        if self._pending_worker is worker:
            self._pending_worker = None

    def _stop_pending_worker(self) -> None:
        """Stop a simulation still running when the dialog closes.

        Without this, closing the dialog mid-run destroys a live QThread and
        ~QThread aborts the process. The reference is only dropped once the
        thread is known to be finished.
        """
        worker = self._pending_worker
        if worker is None:
            return
        if stop_worker(worker, self._WORKER_STOP_TIMEOUT_MS):
            self._pending_worker = None

    def closeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        """Stop the running simulation before the dialog goes away."""
        self._stop_pending_worker()
        super().closeEvent(event)
