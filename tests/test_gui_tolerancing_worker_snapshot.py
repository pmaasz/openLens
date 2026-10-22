#!/usr/bin/env python3
"""
A running tolerance analysis must work on its own operands.

The workers were handed the window's live operand list. The analyzer iterates
it once per trial, and the tolerance table is still editable while the run is
in flight - so the user could change the analysis' input from another thread,
and adding rows made the run quadratic (it never finished).
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
class TestTolerancingWorkersTakeASnapshot(unittest.TestCase):
    """The analysis' input must not change under it."""

    class _FakeWindow(QWidget):
        def __init__(self, target):
            super().__init__()
            self._target = target
            self._tol_operands = []

        def _active_target(self):
            return self._target

    def setUp(self):
        from openlens.gui.tabs.tolerancing_tab import TolerancingTab
        from openlens.lens import Lens
        from openlens.optical_system import OpticalSystem
        from openlens.tolerancing import ToleranceOperand, ToleranceType

        system = OpticalSystem(name="Doublet")
        system.add_lens(
            Lens(
                name="L1",
                radius_of_curvature_1=50.0,
                radius_of_curvature_2=-50.0,
                refractive_index=1.5168,
                thickness=5.0,
                diameter=25.0,
            )
        )
        system.add_lens(
            Lens(
                name="L2",
                radius_of_curvature_1=-60.0,
                radius_of_curvature_2=60.0,
                refractive_index=1.6200,
                thickness=4.0,
                diameter=25.0,
            ),
            air_gap_before=2.0,
        )

        self.window = self._FakeWindow(system)
        self.tab = TolerancingTab(self.window)
        self.window._tol_operands.extend(
            [
                ToleranceOperand(0, ToleranceType.RADIUS_1, -0.1, 0.1),
                ToleranceOperand(0, ToleranceType.RADIUS_2, -0.1, 0.1),
            ]
        )
        self.tab._update_tolerance_operands_display()

    def tearDown(self):
        self.tab.deleteLater()
        self.window.deleteLater()

    def test_the_worker_does_not_hold_the_live_list(self):
        """The worker must analyse the operands it was given"""
        self.tab._tol_refocus_check.setChecked(False)
        self.tab._tol_num_trials.setValue(5)
        self.tab._on_run_monte_carlo()
        worker = self.tab._mc_worker

        self.assertIsNot(
            worker.tol_operands,
            self.window._tol_operands,
            msg="the worker holds the window's live operand list",
        )
        self.assertEqual(len(worker.tol_operands), len(self.window._tol_operands))

        worker.wait(30000)

    def test_editing_the_table_does_not_change_the_running_analysis(self):
        """Rows added during the run must not join it"""
        from openlens.tolerancing import ToleranceOperand, ToleranceType

        self.tab._tol_refocus_check.setChecked(False)
        self.tab._tol_num_trials.setValue(5)
        self.tab._on_run_monte_carlo()
        worker = self.tab._mc_worker
        before = list(worker.tol_operands)

        self.window._tol_operands.append(ToleranceOperand(1, ToleranceType.DECENTER_Y, -0.05, 0.05))
        self.window._tol_operands.pop(0)

        worker.wait(30000)

        self.assertEqual(
            list(worker.tol_operands),
            before,
            msg="the running analysis' input changed under it",
        )

    def test_the_inverse_sensitivity_worker_takes_a_snapshot_too(self):
        """Both workers need the snapshot"""
        self.tab._tol_refocus_check.setChecked(False)
        self.tab._on_run_inverse_sensitivity()
        worker = self.tab._inv_worker

        self.assertIsNot(worker.tol_operands, self.window._tol_operands)
        self.assertEqual(len(worker.tol_operands), len(self.window._tol_operands))

        worker.wait(30000)


if __name__ == "__main__":
    unittest.main()
