"""Regression: a zero-size assembly must paint without dividing by zero."""

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

    from openlens.gui.widgets.assembly_viz import AssemblyVisualizationWidget
    from openlens.lens import Lens
    from openlens.optical_system import OpticalSystem

    PYSIDE_AVAILABLE = True
except ImportError:
    PYSIDE_AVAILABLE = False


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 not available")
class TestDegenerateAssemblyPaint(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_a_zero_thickness_and_diameter_element_does_not_crash(self):
        lens = Lens(
            name="degenerate",
            radius_of_curvature_1=50.0,
            radius_of_curvature_2=-50.0,
            refractive_index=1.5168,
            thickness=0.0,
            diameter=0.0,
        )
        system = OpticalSystem(name="Degenerate")
        system.add_lens(lens)

        widget = AssemblyVisualizationWidget()
        widget.update_system(system)
        widget.resize(500, 400)
        try:
            # Call the handler directly so an exception fails the test instead
            # of becoming a Qt event-loop diagnostic.
            widget.paintEvent(QPaintEvent(QRect(0, 0, 500, 400)))
        finally:
            widget.close()
            widget.deleteLater()


if __name__ == "__main__":
    unittest.main()
