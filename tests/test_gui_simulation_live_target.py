#!/usr/bin/env python3
"""
The simulation tab must trace the live model, not a snapshot of it.

``condition_at_temperature`` returns a deep copy at any temperature other
than the reference, and the widget stored that copy as its target. Its
``refresh()`` re-traced the copy, so every later edit of the lens was
silently discarded - the drawn lens was the new one and the drawn rays
belonged to the old one.
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


@unittest.skipUnless(PYSIDE_AVAILABLE, f"PySide6 not available: {_PYSIDE_ERROR}")
class TestSimulationTracesTheLiveModel(unittest.TestCase):
    """The widget must hold the model the user is editing."""

    class _FakeWindow(QWidget):
        def __init__(self, target):
            super().__init__()
            self._target = target

        def _active_target(self):
            return self._target

    def _lens(self, radius=50.0):
        from openlens.lens import Lens

        return Lens(
            name="TestLens",
            radius_of_curvature_1=radius,
            radius_of_curvature_2=-50.0,
            refractive_index=1.5168,
            thickness=5.0,
            diameter=25.0,
        )

    def _tab(self, lens, temperature=40.0):
        from openlens.gui.tabs.simulation_tab import SimulationTab

        tab = SimulationTab(self._FakeWindow(lens))
        tab.resize(900, 600)
        tab._sim_temperature.setValue(temperature)
        tab._on_run_simulation()
        return tab

    def test_the_widget_holds_the_live_model(self):
        """A conditioned copy must not become the widget's target"""
        lens = self._lens()
        tab = self._tab(lens)

        self.assertIs(
            tab._sim_viz._lens,
            lens,
            msg="the widget kept a conditioned copy of the model",
        )

    def test_an_edit_is_picked_up_by_the_refresh(self):
        """The refresh must trace the edited design"""
        lens = self._lens()
        tab = self._tab(lens)
        viz = tab._sim_viz
        before = viz._rays[-1].path[-1][1]

        lens.radius_of_curvature_1 = 120.0
        tab.refresh()

        self.assertEqual(
            viz._lens.radius_of_curvature_1,
            120.0,
            msg="the widget still holds the old design",
        )
        after = viz._rays[-1].path[-1][1]
        self.assertNotEqual(
            before,
            after,
            msg="the refresh re-traced the same (stale) design",
        )

    def test_the_environment_is_still_applied(self):
        """The trace must still be the conditioned one"""
        lens = self._lens()
        warm = self._tab(lens, temperature=40.0)
        cool = self._tab(lens, temperature=20.0)

        self.assertNotEqual(
            warm._sim_viz._rays[-1].path[-1][1],
            cool._sim_viz._rays[-1].path[-1][1],
            msg="the temperature no longer reaches the trace",
        )


if __name__ == "__main__":
    unittest.main()
