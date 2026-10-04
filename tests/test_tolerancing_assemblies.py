#!/usr/bin/env python3
"""
The tolerancing tab must work for assemblies, not just single lenses.

Every entry point gated on ``_current_lens``, which is explicitly None
whenever an assembly is current. So the whole multi-element workflow - the
tab's reason to exist - was unreachable, and "Add Tolerance", "Default Set"
and "Load Grade" were *silent* no-ops that gave the user no feedback at all.
"""

import os
import sys
import unittest

if os.environ.get("DISPLAY", "") == "" and sys.platform.startswith("linux"):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QEventLoop, QTimer

    PYSIDE_AVAILABLE = True
except ImportError as _e:
    QApplication = None  # type: ignore
    PYSIDE_AVAILABLE = False
    _PYSIDE_ERROR = _e

from src.lens import Lens
from src.optical_system import OpticalSystem
from src.tolerancing import ToleranceOperand, ToleranceType

if not PYSIDE_AVAILABLE:  # pragma: no cover - environment guard

    class TestTolerancingAssemblies(unittest.TestCase):
        @unittest.skip(f"PySide6 not available: {_PYSIDE_ERROR}")
        def test_skip(self):
            pass


class _Parent:
    """Minimal stand-in for the main window the tab reads from."""

    def __init__(self, target, operands):
        if isinstance(target, OpticalSystem):
            self._current_lens = None
            self._current_assembly = target
        else:
            self._current_lens = target
            self._current_assembly = None
        self._tol_operands = operands
        self.statuses = []

    def _update_status(self, message):
        self.statuses.append(message)


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 not available")
class TestTolerancingAssemblies(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def _doublet(self):
        system = OpticalSystem(name="Doublet")
        system.add_lens(
            Lens(
                name="Crown",
                radius_of_curvature_1=50.0,
                radius_of_curvature_2=-50.0,
                thickness=5.0,
                diameter=20.0,
            )
        )
        system.add_lens(
            Lens(
                name="Flint",
                radius_of_curvature_1=-60.0,
                radius_of_curvature_2=100.0,
                thickness=4.0,
                diameter=20.0,
            ),
            air_gap_before=2.0,
        )
        return system

    def _tab(self, target, element_index=1):
        from src.gui.tabs.tolerancing_tab import TolerancingTab

        operands = [ToleranceOperand(element_index, ToleranceType.RADIUS_1, -0.01, 0.01)]
        tab = TolerancingTab()
        tab._parent = _Parent(target, operands)
        return tab

    def _await_report(self, tab, started_flag):
        loop = QEventLoop()
        tab._tol_results_text.textChanged.connect(loop.quit)
        QTimer.singleShot(60000, loop.quit)  # never hang the suite
        self.assertTrue(getattr(tab, started_flag), "run did not start")
        loop.exec()
        self.assertFalse(getattr(tab, started_flag), "run flag never cleared")
        self.assertEqual(tab._tol_progress.maximum(), 100)

    def test_resolve_target_prefers_the_assembly(self):
        """The gate the old code got wrong."""
        tab = self._tab(self._doublet())
        self.assertIsNone(tab._parent._current_lens)
        self.assertIs(tab._resolve_target(), tab._parent._current_assembly)

    def test_resolve_target_falls_back_to_the_lens(self):
        system = self._doublet()
        tab = self._tab(system.elements[0].lens, element_index=0)
        self.assertIs(tab._resolve_target(), system.elements[0].lens)

    def test_monte_carlo_runs_for_an_assembly(self):
        tab = self._tab(self._doublet())
        tab._tol_num_trials.setValue(10)
        tab._tol_refocus_check.setChecked(False)
        tab._on_run_monte_carlo()
        self._await_report(tab, "_mc_running")
        self.assertIn("MONTE CARLO", tab._tol_results_text.toPlainText())

    def test_inverse_sensitivity_runs_for_an_assembly(self):
        tab = self._tab(self._doublet())
        tab._on_run_inverse_sensitivity()
        self._await_report(tab, "_inv_running")
        self.assertIn("INVERSE SENSITIVITY", tab._tol_results_text.toPlainText())

    def test_monte_carlo_still_runs_for_a_single_lens(self):
        system = self._doublet()
        tab = self._tab(system.elements[0].lens, element_index=0)
        tab._tol_num_trials.setValue(10)
        tab._tol_refocus_check.setChecked(False)
        tab._on_run_monte_carlo()
        self._await_report(tab, "_mc_running")
        self.assertIn("MONTE CARLO", tab._tol_results_text.toPlainText())

    def test_default_set_is_not_a_silent_no_op_for_an_assembly(self):
        """It used to return with no message at all."""
        tab = self._tab(self._doublet())
        tab._parent._tol_operands = []
        tab._on_add_default_tolerances()
        self.assertTrue(
            tab._parent._tol_operands,
            "Default Set did nothing for an assembly and said nothing",
        )

    def test_load_grade_is_not_a_silent_no_op_for_an_assembly(self):
        tab = self._tab(self._doublet())
        tab._parent._tol_operands = []
        tab._on_load_grade()
        self.assertTrue(tab._parent._tol_operands)

    def test_add_tolerance_offers_every_assembly_element(self):
        tab = self._tab(self._doublet())
        # The element-count logic read _current_lens, so an assembly always
        # looked like one element.
        target = tab._resolve_target()
        self.assertEqual(len(getattr(target, "elements", None) or [target]), 2)

    def test_nothing_selected_reports_instead_of_silently_returning(self):
        from src.gui.tabs.tolerancing_tab import TolerancingTab

        tab = TolerancingTab()
        tab._parent = _Parent(None, [])
        tab._parent._current_lens = None
        tab._parent._current_assembly = None
        self.assertIsNone(tab._resolve_target())
        self.assertFalse(tab._require_target())
        self.assertIn("No lens or assembly", tab._tol_results_text.toPlainText())

    def test_worker_keeps_an_assembly_intact(self):
        """A bare-lens wrapper would discard elements and gaps."""
        from src.gui.tabs.tolerancing_tab import _as_system

        system = self._doublet()
        self.assertIs(_as_system(system), system)

        wrapped = _as_system(system.elements[0].lens)
        self.assertIsInstance(wrapped, OpticalSystem)
        self.assertEqual(len(wrapped.elements), 1)


if __name__ == "__main__":
    unittest.main()
