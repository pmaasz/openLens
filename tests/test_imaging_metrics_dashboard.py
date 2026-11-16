#!/usr/bin/env python3
"""First-order imaging metrics dashboard (#787)."""

import math
import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication

    PYSIDE_AVAILABLE = True
except ImportError:  # pragma: no cover - environment guard
    PYSIDE_AVAILABLE = False

from openlens.lens import Lens
from openlens.optical_system import OpticalSystem
from openlens.performance_metrics import PerformanceMetrics


def _converging_lens():
    return Lens(
        name="conv",
        radius_of_curvature_1=100.0,
        radius_of_curvature_2=-100.0,
        thickness=5.0,
        diameter=25.0,
        refractive_index=1.5168,
    )


class TestImagingMetrics(unittest.TestCase):
    def test_converging_lens_has_first_order_values(self):
        lens = _converging_lens()
        pm = PerformanceMetrics(lens)
        f = lens.calculate_focal_length()

        self.assertAlmostEqual(pm.calculate_field_of_view(36.0), 20.9, delta=0.2)
        self.assertAlmostEqual(pm.calculate_magnification(1000.0), f / (f - 1000.0), places=9)
        self.assertAlmostEqual(pm.calculate_working_distance(1.0), abs(f) * 2.0, places=9)
        dof = pm.calculate_depth_of_field(1000.0)
        self.assertIsNotNone(dof)
        self.assertTrue(math.isfinite(dof["hyperfocal"]))
        self.assertTrue(math.isfinite(dof["near"]))
        self.assertTrue(math.isfinite(dof["far"]))
        self.assertTrue(pm.estimate_resolution_rayleigh(f_number=pm.calculate_f_number()) > 0)

    def test_afocal_or_zero_power_reports_undefined(self):
        afocal = Lens(
            name="afocal",
            radius_of_curvature_1=float("inf"),
            radius_of_curvature_2=float("inf"),
            thickness=5.0,
            diameter=25.0,
            refractive_index=1.5168,
        )
        pm = PerformanceMetrics(afocal)

        self.assertIsNone(pm.calculate_field_of_view(36.0))
        self.assertIsNone(pm.calculate_magnification(1000.0))
        self.assertIsNone(pm.calculate_working_distance(1.0))
        self.assertIsNone(pm.calculate_depth_of_field(1000.0))
        self.assertIsNone(pm.estimate_resolution_rayleigh(f_number=None))
        # Degenerate conjugate: object at focus
        lens = _converging_lens()
        pm2 = PerformanceMetrics(lens)
        self.assertIsNone(pm2.calculate_magnification(lens.calculate_focal_length()))

    def test_sensor_dimensions_change_field_of_view(self):
        pm = PerformanceMetrics(_converging_lens())
        fov_small = pm.calculate_field_of_view(12.0)
        fov_large = pm.calculate_field_of_view(36.0)
        self.assertLess(fov_small, fov_large)


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 not available")
class TestImagingMetricsReport(unittest.TestCase):
    def setUp(self):
        from openlens.gui.tabs.performance_tab import PerformanceTab

        self.app = QApplication.instance() or QApplication(sys.argv)
        self.tab = PerformanceTab()

    def tearDown(self):
        self.tab.deleteLater()

    def _render_report(self, target, *, infinite=True, distance=1000.0, sensor_diag=36.0):
        import time

        if infinite:
            self.tab._perf_object_infinite.setChecked(True)
        else:
            self.tab._perf_object_infinite.setChecked(False)
            self.tab._perf_object_distance.setValue(distance)
        self.tab._perf_sensor_size.setValue(sensor_diag)

        class Parent:
            def __init__(self, target):
                self._current_assembly = target if isinstance(target, OpticalSystem) else None
                self._current_lens = target if isinstance(target, Lens) else None

            def _active_target(self):
                return target

            def _update_status(self, _msg):
                pass

        self.tab._parent = Parent(target)
        self.tab._on_calculate_performance_metrics()
        deadline = time.time() + 60.0
        while time.time() < deadline:
            self.app.processEvents()
            text = self.tab._perf_metrics_text.toPlainText()
            if "First-order / Imaging" in text or text.startswith("Error"):
                return text
            time.sleep(0.02)
        return self.tab._perf_metrics_text.toPlainText()

    def test_report_labels_assumption_and_shows_imaging_section(self):
        text = self._render_report(_converging_lens())
        self.assertIn("First-order / Imaging", text)
        self.assertIn("Calculation object distance", text)
        self.assertIn("first-order only; not used for aberration/ray-trace metrics", text)
        self.assertIn("Field of view (H/V/D)", text)
        self.assertIn("Magnification", text)
        self.assertIn("Depth of field", text)
        self.assertIn("Rayleigh resolution", text)
        self.assertIn("Image-circle coverage", text)

    def test_report_updates_with_inputs_and_shows_na_cases(self):
        text_inf = self._render_report(_converging_lens(), infinite=True, sensor_diag=36.0)
        text_near = self._render_report(
            _converging_lens(), infinite=False, distance=1000.0, sensor_diag=12.0
        )
        self.assertIn("infinity (collimated)", text_inf)
        self.assertIn("1000.000 mm", text_near)
        # Different sensor diagonal -> different FOV values reported.
        self.assertNotEqual(text_inf, text_near)

        afocal = Lens(
            name="afocal",
            radius_of_curvature_1=float("inf"),
            radius_of_curvature_2=float("inf"),
            thickness=5.0,
            diameter=25.0,
            refractive_index=1.5168,
        )
        text_afocal = self._render_report(afocal, infinite=False, distance=1000.0)
        self.assertIn("Field of view (H/V/D): N/A / N/A / N/A", text_afocal)
        self.assertIn("Magnification: N/A", text_afocal)
        self.assertIn("Depth of field (near/far): N/A", text_afocal)
        self.assertNotIn("nan", text_afocal.lower())


if __name__ == "__main__":
    unittest.main()
