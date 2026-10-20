#!/usr/bin/env python3
"""The wavelength pickers share one preset table (#563).

The Performance tab matched a bare ``[400, 450, 550, 650, 700]`` list by combo
index, and the Simulation tab owned a second copy with the same numbers. Both
now build their pickers from ``constants.WAVELENGTH_PRESETS``. These tests pin
the shared table, the derived labels, and the index-to-wavelength mapping in
the Performance tab.
"""

import os
import sys
import unittest

# Headless environments (CI): fall back to Qt's offscreen platform before
# any QApplication is created. A real DISPLAY always wins.
if os.environ.get("DISPLAY", "") == "" and sys.platform.startswith("linux"):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from openlens import constants
from openlens.gui.tabs import performance_tab, simulation_tab

try:
    from PySide6.QtWidgets import QApplication

    PYSIDE_AVAILABLE = True
except ImportError as _pyside_error:  # pragma: no cover - depends on install
    QApplication = None  # type: ignore
    PYSIDE_AVAILABLE = False


_app = None


def _ensure_app():
    """Create (once) and return the QApplication every widget needs."""
    global _app
    if _app is None:
        _app = QApplication.instance() or QApplication([])
    return _app


def _expected_labels():
    """The combo labels the shared presets produce."""
    return [f"{nanometres:g} nm ({name})" for nanometres, name in constants.WAVELENGTH_PRESETS]


class TestPresetTables(unittest.TestCase):
    """Both tabs derive their tables from the constants module."""

    def test_presets_are_sorted_positive_and_unique(self):
        presets = constants.WAVELENGTH_PRESETS
        values = [nanometres for nanometres, _name in presets]

        self.assertEqual(values, sorted(values))
        self.assertEqual(len(values), len(set(values)))
        self.assertIn(constants.WAVELENGTH_GREEN, values)
        for nanometres, name in presets:
            with self.subTest(nanometres=nanometres):
                self.assertGreater(nanometres, 0)
                self.assertTrue(name)

    def test_simulation_table_matches_the_presets(self):
        expected = tuple(
            (nanometres, f"{nanometres:g} nm ({name})")
            for nanometres, name in constants.WAVELENGTH_PRESETS
        )

        self.assertEqual(simulation_tab.SIMULATION_WAVELENGTHS, expected)
        self.assertEqual(simulation_tab.CUSTOM_WAVELENGTH_INDEX, len(expected))
        self.assertEqual(
            expected[simulation_tab.DEFAULT_WAVELENGTH_INDEX][0],
            constants.WAVELENGTH_GREEN,
        )

    def test_performance_table_matches_the_presets(self):
        self.assertEqual(
            performance_tab._PRESET_WAVELENGTHS,
            tuple(nanometres for nanometres, _name in constants.WAVELENGTH_PRESETS),
        )


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 is not installed")
class TestPerformanceWavelengthPicker(unittest.TestCase):
    """The combo shows, and selects, the shared presets."""

    def setUp(self):
        _ensure_app()
        self.tab = performance_tab.PerformanceTab()

    def tearDown(self):
        self.tab.close()
        self.tab.deleteLater()
        QApplication.processEvents()

    def test_combo_lists_the_shared_presets(self):
        actual = [
            self.tab._perf_wavelength.itemText(index)
            for index in range(self.tab._perf_wavelength.count())
        ]
        self.assertEqual(actual, _expected_labels())

    def test_selected_wavelength_matches_each_item(self):
        for index, (nanometres, _name) in enumerate(constants.WAVELENGTH_PRESETS):
            with self.subTest(index=index):
                self.tab._perf_wavelength.setCurrentIndex(index)
                self.assertEqual(self.tab._selected_wavelength(), nanometres)

    def test_default_is_the_photopic_peak(self):
        self.assertEqual(self.tab._selected_wavelength(), constants.WAVELENGTH_GREEN)


if __name__ == "__main__":
    unittest.main()
