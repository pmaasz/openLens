"""Regression (#674): the 3D caption must follow the active theme."""

import os
import sys
import unittest

# Headless environments (CI): fall back to Qt's offscreen platform before any
# QApplication is created. A real DISPLAY always wins.
if os.environ.get("DISPLAY", "") == "" and sys.platform.startswith("linux"):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication

    from openlens.gui.theme import DARK, LIGHT, get_palette
    from openlens.gui.widgets.lens_viz_3d import _3DVisualizationWidget
    from openlens.lens import Lens

    PYSIDE_AVAILABLE = True
except ImportError:
    PYSIDE_AVAILABLE = False

try:
    import matplotlib  # noqa: F401

    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False


@unittest.skipUnless(PYSIDE_AVAILABLE and HAS_MATPLOTLIB, "PySide6/matplotlib not available")
class TestCaptionTheme(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.widget = _3DVisualizationWidget()
        self.lens = Lens(
            name="T",
            radius_of_curvature_1=50.0,
            radius_of_curvature_2=-50.0,
            refractive_index=1.5168,
            thickness=5.0,
            diameter=25.0,
        )

    def tearDown(self):
        self.widget.close()
        self.widget.deleteLater()
        self.app.processEvents()

    def _caption_color(self):
        return self.widget._ax.texts[0].get_color()

    def test_switching_to_the_light_theme_recolours_an_existing_caption(self):
        self.widget.update_lens(self.lens)

        self.widget.set_theme(LIGHT)

        self.assertEqual(self._caption_color(), get_palette(LIGHT)["plot_text"])
        self.assertNotEqual(self._caption_color(), get_palette(LIGHT)["plot_bg"])

    def test_a_light_theme_caption_is_created_with_the_palette_text_colour(self):
        self.widget.set_theme(LIGHT)

        self.widget.update_lens(self.lens)

        self.assertEqual(self._caption_color(), get_palette(LIGHT)["plot_text"])

    def test_switching_back_to_dark_restores_the_dark_caption(self):
        self.widget.update_lens(self.lens)
        self.widget.set_theme(LIGHT)

        self.widget.set_theme(DARK)

        self.assertEqual(self._caption_color(), get_palette(DARK)["plot_text"])


if __name__ == "__main__":
    unittest.main()
