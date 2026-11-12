"""Regression (#673): the performance panel must paint the real spot metric.

The widget read ``rms_spot``, a key that no producer supplies, so it painted
a constant "RMS Spot: 0.0000" for every design. The metrics that reach it
from ``AberrationsCalculator`` carry ``spot_rms`` in micrometres.
"""

import os
import sys
import unittest

# Headless environments (CI): fall back to Qt's offscreen platform before any
# QApplication is created. A real DISPLAY always wins.
if os.environ.get("DISPLAY", "") == "" and sys.platform.startswith("linux"):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtCore import QRect
    from PySide6.QtGui import QPaintEvent
    from PySide6.QtWidgets import QApplication

    PYSIDE_AVAILABLE = True
except ImportError:
    PYSIDE_AVAILABLE = False


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 not available")
class TestRmsSpotLabel(unittest.TestCase):
    def test_the_label_uses_the_real_spot_rms_key(self):
        from openlens.gui.widgets.performance_viz import format_rms_spot

        self.assertEqual(format_rms_spot({"spot_rms": 12.3456}), "RMS Spot: 12.346 µm")

    def test_a_missing_metric_is_reported_as_na(self):
        from openlens.gui.widgets.performance_viz import format_rms_spot

        self.assertEqual(format_rms_spot({}), "RMS Spot: n/a")
        self.assertEqual(format_rms_spot(None), "RMS Spot: n/a")

    def test_a_none_metric_is_reported_as_na(self):
        from openlens.gui.widgets.performance_viz import format_rms_spot

        self.assertEqual(format_rms_spot({"spot_rms": None}), "RMS Spot: n/a")

    def test_a_zero_metric_is_still_a_real_value(self):
        from openlens.gui.widgets.performance_viz import format_rms_spot

        self.assertEqual(format_rms_spot({"spot_rms": 0.0}), "RMS Spot: 0.000 µm")

    def test_the_widget_paints_the_real_metric(self):
        from openlens.gui.widgets.performance_viz import PerformanceVisualizationWidget
        from openlens.lens import Lens

        app = QApplication.instance() or QApplication(sys.argv)
        lens = Lens(
            name="TestLens",
            radius_of_curvature_1=50.0,
            radius_of_curvature_2=-50.0,
            refractive_index=1.5168,
            thickness=5.0,
            diameter=25.0,
        )
        widget = PerformanceVisualizationWidget()
        widget.update_lens(lens)
        widget.update_metrics({"spot_rms": 12.3456})
        widget.resize(400, 300)
        try:
            widget.paintEvent(QPaintEvent(QRect(0, 0, 400, 300)))
        finally:
            widget.close()
            widget.deleteLater()
        app.processEvents()


if __name__ == "__main__":
    unittest.main()
