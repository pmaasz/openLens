#!/usr/bin/env python3
"""Theme switching across the whole window (#468).

The theme toggle replaced the application stylesheet only. The status bar,
the menu bar and the editor tabs each carry their own sheet, set once at
creation, and the custom-painted views and plots had their dark colours
hard-coded. Choosing "light" therefore left most of the window dark, until
the next restart rebuilt everything from the light palette.

These tests cover the palette that now feeds both the stylesheets and the
canvases, the axis helper the plots share, and the propagation path from the
main window's toggle down to the drawing widgets.
"""

import os
import sys
import tempfile
import unittest
from unittest import mock

# Headless environments (CI): fall back to Qt's offscreen platform before
# any QApplication is created. A real DISPLAY always wins.
if os.environ.get("DISPLAY", "") == "" and sys.platform.startswith("linux"):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from openlens.analysis import plots
from openlens.gui import theme

try:
    from PySide6.QtWidgets import QApplication

    PYSIDE_AVAILABLE = True
except ImportError:  # pragma: no cover - depends on install
    QApplication = None  # type: ignore
    PYSIDE_AVAILABLE = False


_app = None


def _ensure_app():
    """Create (once) and return the QApplication every widget needs."""
    global _app
    if _app is None:
        _app = QApplication.instance() or QApplication([])
    return _app


class _LabelStub:
    """Minimal stand-in for ``matplotlib.axis.Axis.label``."""

    def __init__(self):
        self.color = None

    def set_color(self, color):
        self.color = color


class _AxisStub:
    def __init__(self):
        self.label = _LabelStub()


class _SpineStub:
    def __init__(self):
        self.edgecolor = None

    def set_edgecolor(self, color):
        self.edgecolor = color


class _AxesStub:
    """Enough of a matplotlib Axes for apply_axis_theme to style."""

    def __init__(self):
        self.facecolor = None
        self.tick_colors = None
        self.xaxis = _AxisStub()
        self.yaxis = _AxisStub()
        self.title = _LabelStub()
        self.spines = {"left": _SpineStub(), "right": _SpineStub()}

    def set_facecolor(self, color):
        self.facecolor = color

    def tick_params(self, colors=None, **kwargs):
        self.tick_colors = colors


class TestPalette(unittest.TestCase):
    """The palette is the one source of truth for both faces."""

    def test_light_and_dark_canvas_colours_differ(self):
        """A light canvas must not reuse any dark canvas colour."""
        dark = theme.get_palette(theme.DARK)
        light = theme.get_palette(theme.LIGHT)
        for key in (
            "plot_bg",
            "plot_text",
            "plot_axis",
            "plot_grid",
            "plot_spine",
            "code_bg",
            "text_dim",
        ):
            with self.subTest(key=key):
                self.assertNotEqual(dark[key], light[key])

    def test_get_palette_returns_a_copy(self):
        """Callers must not be able to mutate the shared palette."""
        palette = theme.get_palette(theme.DARK)
        palette["plot_bg"] = "#ff00ff"
        self.assertNotEqual(theme.get_palette(theme.DARK)["plot_bg"], "#ff00ff")

    def test_monospace_qss_follows_theme(self):
        """The results panes must be light in light mode."""
        dark = theme.get_monospace_qss(theme.DARK)
        light = theme.get_monospace_qss(theme.LIGHT)
        dark_palette = theme.get_palette(theme.DARK)
        light_palette = theme.get_palette(theme.LIGHT)

        self.assertIn(dark_palette["code_bg"], dark)
        self.assertIn(dark_palette["text"], dark)
        self.assertIn(light_palette["code_bg"], light)
        self.assertIn(light_palette["text"], light)
        self.assertNotEqual(dark, light)


class TestAxisTheme(unittest.TestCase):
    """One helper styles both faces of the analysis plots."""

    def test_light_axis_uses_light_palette(self):
        ax = _AxesStub()
        palette = theme.get_palette(theme.LIGHT)

        plots.apply_axis_theme(ax, theme.LIGHT)

        self.assertEqual(ax.facecolor, palette["plot_bg"])
        self.assertEqual(ax.tick_colors, palette["plot_text"])
        self.assertEqual(ax.xaxis.label.color, palette["plot_text"])
        self.assertEqual(ax.yaxis.label.color, palette["plot_text"])
        self.assertEqual(ax.title.color, palette["plot_text"])
        for spine in ax.spines.values():
            self.assertEqual(spine.edgecolor, palette["plot_spine"])

    def test_dark_axis_uses_dark_palette(self):
        ax = _AxesStub()
        palette = theme.get_palette(theme.DARK)

        plots.apply_axis_theme(ax, theme.DARK)

        self.assertEqual(ax.facecolor, palette["plot_bg"])
        self.assertEqual(ax.tick_colors, palette["plot_text"])
        self.assertEqual(ax.title.color, palette["plot_text"])

    def test_compatibility_wrapper_stays_dark(self):
        ax = _AxesStub()
        plots.apply_dark_axis_theme(ax)
        self.assertEqual(ax.facecolor, theme.get_palette(theme.DARK)["plot_bg"])

    def test_unknown_theme_falls_back_to_dark(self):
        ax = _AxesStub()
        plots.apply_axis_theme(ax, "chartreuse")
        self.assertEqual(ax.facecolor, theme.get_palette(theme.DARK)["plot_bg"])


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 is not installed")
class TestViewTheming(unittest.TestCase):
    """Every custom-painted view accepts the toggle's theme."""

    def setUp(self):
        _ensure_app()

    def tearDown(self):
        QApplication.processEvents()

    def test_painted_views_adopt_light_canvas(self):
        from openlens.gui.widgets.assembly_viz import AssemblyVisualizationWidget
        from openlens.gui.widgets.lens_viz_2d import LensViz2DWidget
        from openlens.gui.widgets.performance_viz import PerformanceVisualizationWidget
        from openlens.gui.widgets.simulation_viz import SimulationVisualizationWidget

        palette = theme.get_palette(theme.LIGHT)
        factories = (
            LensViz2DWidget,
            SimulationVisualizationWidget,
            AssemblyVisualizationWidget,
            PerformanceVisualizationWidget,
        )
        for factory in factories:
            with self.subTest(widget=factory.__name__):
                widget = factory()
                try:
                    self.assertEqual(widget._theme, theme.DARK)
                    widget.set_theme(theme.LIGHT)
                    self.assertEqual(widget._theme, theme.LIGHT)
                    self.assertEqual(widget._bg_color.name(), palette["plot_bg"])
                finally:
                    widget.close()
                    widget.deleteLater()

    def test_container_propagates_theme_to_both_views(self):
        from openlens.gui.widgets.lens_viz_container import LensVisualizationWidget

        palette = theme.get_palette(theme.LIGHT)
        container = LensVisualizationWidget()
        try:
            container.set_theme(theme.LIGHT)
            self.assertEqual(container._theme, theme.LIGHT)
            self.assertEqual(container._2d_widget._theme, theme.LIGHT)
            self.assertEqual(container._2d_widget._bg_color.name(), palette["plot_bg"])
            self.assertEqual(container._3d_widget._theme, theme.LIGHT)
        finally:
            container.close()
            container.deleteLater()

    def test_lens_editor_inputs_follow_theme(self):
        from openlens.gui.widgets.lens_editor import LensEditorWidget

        palette = theme.get_palette(theme.LIGHT)
        editor = LensEditorWidget()
        try:
            editor.set_theme(theme.LIGHT)
            self.assertEqual(editor._theme, theme.LIGHT)
            self.assertIn(palette["input_bg"], editor._name_input.styleSheet())
            self.assertIn(palette["input_bg"], editor._n_input.styleSheet())
        finally:
            editor.close()
            editor.deleteLater()

    def test_results_tabs_follow_theme(self):
        from openlens.gui.tabs.optimization_tab import OptimizationTab
        from openlens.gui.tabs.performance_tab import PerformanceTab
        from openlens.gui.tabs.tolerancing_tab import TolerancingTab

        palette = theme.get_palette(theme.LIGHT)
        cases = (
            (TolerancingTab, ("_tol_table", "_tol_results_text")),
            (OptimizationTab, ("_opt_results_text",)),
            (PerformanceTab, ("_perf_metrics_text",)),
        )
        for factory, attributes in cases:
            with self.subTest(tab=factory.__name__):
                tab = factory()
                try:
                    tab.set_theme(theme.LIGHT)
                    self.assertEqual(tab._theme, theme.LIGHT)
                    for attribute in attributes:
                        sheet = getattr(tab, attribute).styleSheet()
                        self.assertIn(palette["code_bg"], sheet)
                        self.assertIn(palette["text"], sheet)
                finally:
                    tab.close()
                    tab.deleteLater()


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 is not installed")
class TestMainWindowThemeToggle(unittest.TestCase):
    """The toggle restyles chrome and views, not just the app sheet."""

    def setUp(self):
        _ensure_app()
        self._tmpdir = tempfile.TemporaryDirectory()
        self._env = mock.patch.dict(
            os.environ,
            {
                "OPENLENS_DATA_DIR": self._tmpdir.name,
                "OPENLENS_DB_PATH": os.path.join(self._tmpdir.name, "test.db"),
            },
        )
        self._env.start()

        from openlens.__main__ import OpenLensWindow

        self.window = OpenLensWindow()
        self.window.show()
        QApplication.processEvents()

    def tearDown(self):
        # Leave the shared application sheet dark for any later test.
        if getattr(self.window, "_theme", None) != theme.DARK:
            self.window._apply_theme(theme.DARK)
        self.window.close()
        self.window.deleteLater()
        QApplication.processEvents()
        self._env.stop()
        self._tmpdir.cleanup()

    def test_toggle_restyles_chrome_and_drawing_views(self):
        from openlens.gui.widgets.lens_editor import LensEditorWidget
        from openlens.gui.widgets.lens_viz_2d import LensViz2DWidget

        editor = self.window.findChild(LensEditorWidget)
        viz = self.window.findChild(LensViz2DWidget)
        self.assertIsNotNone(editor)
        self.assertIsNotNone(viz)

        self.window._on_toggle_theme()
        QApplication.processEvents()

        light = theme.get_palette(theme.LIGHT)
        self.assertEqual(self.window._theme, theme.LIGHT)
        self.assertEqual(
            self.window._status_bar.styleSheet(), theme.get_status_bar_qss(theme.LIGHT)
        )
        self.assertEqual(
            self.window._editor_tabs.styleSheet(), theme.get_tab_widget_qss(theme.LIGHT)
        )
        self.assertEqual(self.window.menuBar().styleSheet(), theme.get_menubar_qss(theme.LIGHT))
        self.assertEqual(
            QApplication.instance().styleSheet(), theme.get_app_stylesheet(theme.LIGHT)
        )
        self.assertEqual(editor._theme, theme.LIGHT)
        self.assertEqual(viz._theme, theme.LIGHT)
        self.assertEqual(viz._bg_color.name(), light["plot_bg"])

        self.window._on_toggle_theme()
        QApplication.processEvents()

        dark = theme.get_palette(theme.DARK)
        self.assertEqual(self.window._theme, theme.DARK)
        self.assertEqual(self.window._status_bar.styleSheet(), theme.get_status_bar_qss(theme.DARK))
        self.assertEqual(editor._theme, theme.DARK)
        self.assertEqual(viz._bg_color.name(), dark["plot_bg"])


if __name__ == "__main__":
    unittest.main()
