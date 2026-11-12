"""The simulation tab must expose, store and draw the focal plane.

The plane belongs to the design (``image_plane_x_mm``), not to the widget:
the optimizer and the performance report read the same field, so the tab must
write it rather than keep a private copy. Auto mode clears it and falls back
to the paraxial focus.
"""

import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication, QWidget

    PYSIDE_AVAILABLE = True
    _PYSIDE_ERROR = ""
except ImportError as _e:  # pragma: no cover - environment guard
    PYSIDE_AVAILABLE = False
    _PYSIDE_ERROR = str(_e)

if PYSIDE_AVAILABLE:
    app = QApplication.instance() or QApplication(sys.argv)


def _lens(**kwargs):
    from openlens.lens import Lens

    options = dict(
        name="Simulation focal plane",
        radius_of_curvature_1=50.0,
        radius_of_curvature_2=-50.0,
        refractive_index=1.5168,
        thickness=5.0,
        diameter=25.0,
    )
    options.update(kwargs)
    return Lens(**options)


class _FakeWindow(QWidget):
    """Minimal parent providing the one method BaseTab needs."""

    def __init__(self, target):
        super().__init__()
        self._target = target

    def _active_target(self):
        return self._target


@unittest.skipUnless(PYSIDE_AVAILABLE, f"PySide6 not available: {_PYSIDE_ERROR}")
class TestSimulationWidgetFocalPlane(unittest.TestCase):
    def _widget(self):
        from openlens.gui.widgets.simulation_viz import SimulationVisualizationWidget

        widget = SimulationVisualizationWidget()
        widget.resize(640, 480)
        return widget

    def test_a_stored_plane_is_used_and_measured(self):
        widget = self._widget()

        widget.run_simulation(_lens(image_plane_x_mm=80.0), num_rays=5)

        self.assertFalse(widget.focal_plane_is_auto)
        self.assertAlmostEqual(widget.focal_plane_x_mm, 80.0, places=6)
        self.assertIsNotNone(widget.focal_plane_rms_um)
        self.assertGreater(widget.focal_plane_rms_um, 0.0)

    def test_auto_uses_the_paraxial_focus(self):
        from openlens.analysis.paraxial import find_paraxial_focus
        from openlens.optical_system import as_system

        lens = _lens()
        expected = find_paraxial_focus(as_system(lens))
        widget = self._widget()

        widget.run_simulation(lens, num_rays=5)

        self.assertTrue(widget.focal_plane_is_auto)
        self.assertIsNotNone(expected)
        self.assertAlmostEqual(widget.focal_plane_x_mm, expected, places=4)

    def test_a_defocused_plane_reports_a_larger_spot(self):
        from openlens.analysis.paraxial import find_paraxial_focus
        from openlens.optical_system import as_system

        lens = _lens()
        focus = find_paraxial_focus(as_system(lens))
        widget = self._widget()
        widget.run_simulation(lens, num_rays=5)
        at_focus = widget.focal_plane_rms_um

        lens.image_plane_x_mm = focus + 10.0
        widget.run_simulation(lens, num_rays=5)

        self.assertIsNotNone(at_focus)
        self.assertIsNotNone(widget.focal_plane_rms_um)
        self.assertGreater(widget.focal_plane_rms_um, at_focus)

    def test_the_plane_is_painted_without_error(self):
        widget = self._widget()

        widget.run_simulation(_lens(image_plane_x_mm=80.0), num_rays=5)

        self.assertFalse(widget.grab().isNull())

    def test_clearing_drops_the_plane(self):
        widget = self._widget()
        widget.run_simulation(_lens(image_plane_x_mm=80.0), num_rays=5)

        widget.clear_simulation()

        self.assertIsNone(widget.focal_plane_x_mm)
        self.assertIsNone(widget.focal_plane_rms_um)
        self.assertTrue(widget.focal_plane_is_auto)


@unittest.skipUnless(PYSIDE_AVAILABLE, f"PySide6 not available: {_PYSIDE_ERROR}")
class TestSimulationTabFocalPlaneControls(unittest.TestCase):
    def setUp(self):
        from openlens.gui.tabs.simulation_tab import SimulationTab

        self.lens = _lens()
        self.tab = SimulationTab(_FakeWindow(self.lens))
        self.tab.resize(900, 600)

    def test_manual_plane_is_stored_on_the_model(self):
        self.tab._sim_auto_focal_plane.setChecked(False)

        self.tab._sim_focal_plane_x.setValue(75.0)

        self.assertEqual(self.lens.image_plane_x_mm, 75.0)

    def test_auto_clears_the_model_plane(self):
        self.lens.image_plane_x_mm = 75.0
        self.tab._sync_focal_plane_controls()

        self.tab._sim_auto_focal_plane.setChecked(True)

        self.assertIsNone(self.lens.image_plane_x_mm)
        self.assertFalse(self.tab._sim_focal_plane_x.isEnabled())

    def test_sync_reflects_the_model(self):
        self.lens.image_plane_x_mm = 62.5

        self.tab.refresh()

        self.assertFalse(self.tab._sim_auto_focal_plane.isChecked())
        self.assertEqual(self.tab._sim_focal_plane_x.value(), 62.5)
        self.assertTrue(self.tab._sim_focal_plane_x.isEnabled())

    def test_run_measures_at_the_manual_plane(self):
        self.tab._sim_auto_focal_plane.setChecked(False)
        self.tab._sim_focal_plane_x.setValue(75.0)

        self.tab._on_run_simulation()

        self.assertAlmostEqual(self.tab._sim_viz.focal_plane_x_mm, 75.0, places=6)
        self.assertIn("75.000", self.tab._sim_focal_status.text())

    def test_run_in_auto_reports_the_paraxial_focus(self):
        self.tab._on_run_simulation()

        self.assertTrue(self.tab._sim_viz.focal_plane_is_auto)
        self.assertIn("auto", self.tab._sim_focal_status.text())

    def test_hiding_the_plane_still_measures_it(self):
        self.tab._sim_show_focal_plane.setChecked(False)

        self.tab._on_run_simulation()

        self.assertIsNotNone(self.tab._sim_viz.focal_plane_x_mm)
        self.assertIsNotNone(self.tab._sim_viz.focal_plane_rms_um)


@unittest.skipUnless(PYSIDE_AVAILABLE, f"PySide6 not available: {_PYSIDE_ERROR}")
class TestPerformanceReportFollowsThePlane(unittest.TestCase):
    def test_a_lone_lens_keeps_its_plane_in_the_analysis_wrapper(self):
        from openlens.gui.tabs.performance_tab import PerformanceTab

        lens = _lens(image_plane_x_mm=91.0)

        system = PerformanceTab._wrap_in_system(lens)

        self.assertEqual(system.image_plane_x_mm, 91.0)


if __name__ == "__main__":
    unittest.main()
