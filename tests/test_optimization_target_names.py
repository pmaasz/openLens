#!/usr/bin/env python3
"""
The optimization tab's target checkboxes must control real merit terms.

The tab built ``OptimizationTarget("spot_size")`` and
``OptimizationTarget("spherical")``, but the merit function's dispatch table
only knows ``rms_spot_radius`` and ``spherical_aberration`` - and an unknown
name was skipped silently. The default-checked spot-size box therefore did
nothing, and an optimization with only that box selected "converged" after one
iteration without changing the design.
"""

import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication

    PYSIDE_AVAILABLE = True
    _PYSIDE_ERROR = ""
except ImportError as _e:  # pragma: no cover - environment guard
    PYSIDE_AVAILABLE = False
    _PYSIDE_ERROR = str(_e)

if PYSIDE_AVAILABLE:
    app = QApplication.instance() or QApplication(sys.argv)


@unittest.skipUnless(PYSIDE_AVAILABLE, f"PySide6 not available: {_PYSIDE_ERROR}")
class TestOptimizationTargetNames(unittest.TestCase):
    """The GUI's target names must be the ones the merit function knows."""

    def setUp(self):
        from openlens.gui.tabs.optimization_tab import OptimizationTab

        self.tab = OptimizationTab()

    def tearDown(self):
        self.tab.deleteLater()

    def test_every_target_name_is_known_to_the_merit_function(self):
        """A name the dispatch table does not have contributes nothing"""
        from openlens.optimizer import MeritFunction

        known = set(MeritFunction._TARGET_DISPATCH)
        names = [target.name for target in self.tab._collect_targets()]

        self.assertTrue(names, "the tab collected no targets at all")
        for name in names:
            self.assertIn(name, known, f"the tab asks for the unknown target {name!r}")

    def test_the_spot_size_checkbox_asks_for_the_rms_spot_radius(self):
        """The default-checked box must reach a real merit term"""
        from openlens.optimizer import MeritFunction

        self.tab._opt_target_spot.setChecked(True)
        names = [target.name for target in self.tab._collect_targets()]

        self.assertIn("rms_spot_radius", names)

    def test_an_unknown_target_name_is_rejected(self):
        """An unknown name must not be a target that silently contributes zero"""
        from openlens.lens import Lens
        from openlens.optical_system import OpticalSystem
        from openlens.optimizer import MeritFunction, OptimizationTarget

        system = OpticalSystem()
        system.add_lens(
            Lens(
                radius_of_curvature_1=50.0,
                radius_of_curvature_2=-50.0,
                thickness=5.0,
                diameter=25.0,
                refractive_index=1.5168,
            )
        )
        merit = MeritFunction(system, [OptimizationTarget("spot_size", 0, 1.0, "minimize")])

        with self.assertRaises(ValueError):
            merit.evaluate(system)


if __name__ == "__main__":
    unittest.main()
