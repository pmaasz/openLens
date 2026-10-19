"""#467: the image simulation dialog must report failures, not swallow them.

Zoom, pan, reset and view-sync failures disappeared in bare ``except: pass``
handlers, and a missing matplotlib (imported by the dialog module) only
produced a log line in the Performance tab, so the button looked dead. These
tests pin the reporting, the view-state math that decides whether a zoom
survives a simulation, and the visible "Dependency Missing" dialog.
"""

import os
import sys
import unittest
from unittest import mock

import numpy as np

if os.environ.get("DISPLAY", "") == "" and sys.platform.startswith("linux"):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    import matplotlib  # noqa: F401

    MPL_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency guard
    MPL_AVAILABLE = False

try:
    from PySide6.QtWidgets import QApplication, QWidget

    PYSIDE_AVAILABLE = True
except ImportError:  # pragma: no cover - environment guard
    PYSIDE_AVAILABLE = False

_app = None


def _ensure_app():
    global _app
    if _app is None:
        _app = QApplication.instance() or QApplication(sys.argv[:1])
    return _app


def _lens(radius: float = 60.0):
    from openlens.lens import Lens

    return Lens(
        name="Crown",
        radius_of_curvature_1=radius,
        radius_of_curvature_2=-radius,
        thickness=6.0,
        diameter=30.0,
        material="N-BK7",
        refractive_index=1.5168,
    )


_GUARD = "PySide6/matplotlib not available"


@unittest.skipUnless(PYSIDE_AVAILABLE and MPL_AVAILABLE, _GUARD)
class TestViewStateMath(unittest.TestCase):
    """Whether a view counts as zoomed, independent of a live dialog."""

    def setUp(self):
        from openlens.gui.dialogs.image_sim import ImageSimulationDialog

        self.view_is_zoomed = ImageSimulationDialog._view_is_zoomed

    def test_full_view_is_not_zoomed(self):
        # 8 wide, 6 high; imshow's inverted y extent is (h-0.5, -0.5)
        self.assertFalse(self.view_is_zoomed((-0.5, 7.5), (5.5, -0.5), (6, 8)))

    def test_zoomed_x_is_zoomed(self):
        self.assertTrue(self.view_is_zoomed((1.5, 5.5), (5.5, -0.5), (6, 8)))

    def test_zoomed_inverted_y_is_zoomed(self):
        """The old inline check compared the inverted height signed."""
        self.assertTrue(self.view_is_zoomed((-0.5, 7.5), (4.0, 1.0), (6, 8)))

    def test_a_view_wider_than_the_image_counts_as_changed(self):
        """Any view that is not exactly the full extent keeps the Reset button."""
        self.assertTrue(self.view_is_zoomed((-5.5, 12.5), (9.5, -4.5), (6, 8)))


@unittest.skipUnless(PYSIDE_AVAILABLE and MPL_AVAILABLE, _GUARD)
class _DialogFixture(unittest.TestCase):
    def setUp(self):
        _ensure_app()
        from openlens.gui.dialogs.image_sim import ImageSimulationDialog
        from openlens.optical_system import OpticalSystem

        system = OpticalSystem(name="Image Test")
        system.add_lens(_lens())
        self.dialog = ImageSimulationDialog(system, None)
        self.addCleanup(self._cleanup)

        self.dialog._original_image = np.zeros((8, 8, 3))
        # Paint it once so the axes carry imshow's full-view limits, exactly
        # as after a real image load.
        self.dialog._ax_orig.imshow(self.dialog._original_image)

    def _cleanup(self):
        self.dialog.close()
        self.dialog.deleteLater()


class TestSimulationPreservesOnlyARealZoom(_DialogFixture):
    def test_unzoomed_simulation_is_not_reclipped_to_the_original(self):
        """was_zoomed was always True, so a fresh simulation view was reset."""
        simulated = np.ones((12, 12, 3))
        self.dialog._on_simulation_done(simulated)

        xlim = self.dialog._ax_orig.get_xlim()
        self.assertAlmostEqual(xlim[0], -0.5, places=6)
        self.assertAlmostEqual(xlim[1], 11.5, places=6)

    def test_axes_stay_shared_after_a_simulation(self):
        """clear() re-establishes sharing itself; the explicit re-bind was dead code."""
        self.dialog._on_simulation_done(np.ones((8, 8, 3)))

        self.dialog._ax_orig.set_xlim(2.0, 6.0)
        self.assertEqual(self.dialog._ax_sim.get_xlim(), (2.0, 6.0))


class TestFailuresAreReported(_DialogFixture):
    LOGGER = "openlens.gui.dialogs.image_sim"

    def test_reset_view_reports_a_failed_redraw(self):
        with mock.patch.object(self.dialog._ax_orig, "set_xlim", side_effect=RuntimeError("boom")):
            with self.assertLogs(self.LOGGER, level="DEBUG") as captured:
                self.dialog._reset_view()

        self.assertTrue(any("reset the view" in message for message in captured.output))

    def test_zoom_at_reports_a_failed_redraw(self):
        with mock.patch.object(self.dialog.canvas, "draw_idle", side_effect=RuntimeError("boom")):
            with self.assertLogs(self.LOGGER, level="DEBUG") as captured:
                self.dialog._zoom_at(4.0, 4.0, 2.0)

        self.assertTrue(any("could not zoom" in message.lower() for message in captured.output))

    def test_pan_failure_is_reported(self):
        self.dialog._is_panning = True
        self.dialog._pan_start_xy = (10.0, 10.0)
        self.dialog._pan_start_lim = (
            self.dialog._ax_orig.get_xlim(),
            self.dialog._ax_orig.get_ylim(),
        )
        event = mock.Mock(inaxes=self.dialog._ax_orig, x=12.0, y=14.0)

        with mock.patch.object(
            self.dialog._ax_orig.transData, "inverted", side_effect=RuntimeError("boom")
        ):
            with self.assertLogs(self.LOGGER, level="DEBUG") as captured:
                self.dialog._on_mouse_move(event)

        self.assertTrue(any("could not pan" in message.lower() for message in captured.output))

    def test_reset_button_failure_is_reported(self):
        with mock.patch.object(self.dialog, "_is_zoomed", side_effect=RuntimeError("boom")):
            with self.assertLogs(self.LOGGER, level="DEBUG") as captured:
                self.dialog._update_reset_button()

        self.assertTrue(any("reset button" in message.lower() for message in captured.output))


@unittest.skipUnless(PYSIDE_AVAILABLE and MPL_AVAILABLE, _GUARD)
class TestMissingDependencyIsVisible(unittest.TestCase):
    def setUp(self):
        _ensure_app()
        from openlens.gui.tabs.performance_tab import PerformanceTab

        class _Parent(QWidget):
            def __init__(self):
                super().__init__()
                self._current_assembly = None
                self._current_lens = None
                self._theme = "dark"
                self._analysis_dialogs = []

            def _update_status(self, message):
                pass

        self.parent = _Parent()
        self.addCleanup(self.parent.deleteLater)
        self.parent._current_lens = _lens()
        self.tab = PerformanceTab(self.parent)
        self.addCleanup(self.tab.deleteLater)

    def test_missing_matplotlib_shows_the_dependency_dialog(self):
        from PySide6.QtWidgets import QMessageBox

        blocked = {"openlens.gui.dialogs.image_sim": None}
        with mock.patch.dict(sys.modules, blocked):
            with mock.patch.object(QMessageBox, "warning") as warning:
                self.tab._on_show_image_simulation()

        warning.assert_called_once()
        args = warning.call_args[0]
        self.assertEqual(args[1], "Dependency Missing")
        self.assertIn("matplotlib", args[2])


if __name__ == "__main__":
    unittest.main()
