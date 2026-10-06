#!/usr/bin/env python3
"""
Tolerancing tab worker completion.

The Run Monte Carlo / Inverse Sensitivity handlers connected their workers'
``finished``/``failed`` signals to ``_on_analysis_finished`` /
``_on_analysis_failed``, neither of which existed. PySide6 swallows the
AttributeError from the missing slot, so ``.start()`` was never reached and
the busy progress bar (range 0..0) spun forever.

These tests cover the slot contract against the real widgets.
"""

import os
import sys
import unittest

if os.environ.get("DISPLAY", "") == "" and sys.platform.startswith("linux"):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication

    PYSIDE_AVAILABLE = True
except ImportError as _e:
    QApplication = None  # type: ignore
    PYSIDE_AVAILABLE = False
    _PYSIDE_ERROR = _e

from src.lens import Lens
from src.tolerancing import ToleranceOperand, ToleranceType

if PYSIDE_AVAILABLE:
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)


if not PYSIDE_AVAILABLE:  # pragma: no cover - environment guard

    class TestTolerancingWorkers(unittest.TestCase):
        @unittest.skip(f"PySide6 not available: {_PYSIDE_ERROR}")
        def test_skip(self):
            pass


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 not available")
class TestTolerancingWorkerSlots(unittest.TestCase):
    """Both workers' completion signals must land in a real slot."""

    def setUp(self):
        from src.gui.tabs.tolerancing_tab import TolerancingTab

        class _Parent:
            """Minimal stand-in for the main window the tab reads from."""

            def __init__(self, lens):
                self._current_lens = lens
                self._tol_operands = [ToleranceOperand(0, ToleranceType.RADIUS_1, -0.01, 0.01)]

            def _update_status(self, *_args, **_kwargs):
                pass

        self.tab = TolerancingTab()
        lens = Lens(
            name="Test",
            radius_of_curvature_1=50.0,
            radius_of_curvature_2=-50.0,
            thickness=5.0,
            diameter=20.0,
            refractive_index=1.5,
        )
        self.tab._parent = _Parent(lens)

    def tearDown(self):
        self.tab.deleteLater()

    def test_slots_connected_by_both_run_handlers_exist(self):
        """The handlers must resolve to real slots, not missing attributes."""
        for name in ("_on_analysis_finished", "_on_analysis_failed"):
            self.assertTrue(callable(getattr(self.tab, name)), f"{name} is not callable")

    def test_finished_slot_resets_busy_progress_and_shows_report(self):
        """A finished run must leave busy mode and display the report."""
        tab = self.tab
        tab._mc_running = True
        tab._inv_running = True
        # Busy mode, as the run handlers set it before .start().
        tab._tol_progress.setMinimum(0)
        tab._tol_progress.setMaximum(0)
        tab._tol_progress.setVisible(True)

        tab._on_analysis_finished("=== RESULTS ===", {"yield": 98.5})

        self.assertEqual(tab._tol_progress.maximum(), 100)
        self.assertEqual(tab._tol_progress.value(), 100)
        self.assertEqual(tab._tol_results_text.toPlainText(), "=== RESULTS ===")
        self.assertFalse(tab._mc_running)
        self.assertFalse(tab._inv_running)
        self.assertEqual(tab._tol_last_results, {"yield": 98.5})

    def test_failed_slot_resets_busy_progress_and_shows_error(self):
        """A failed run must leave busy mode and display the error."""
        tab = self.tab
        tab._mc_running = True
        tab._tol_progress.setMinimum(0)
        tab._tol_progress.setMaximum(0)
        tab._tol_progress.setVisible(True)

        tab._on_analysis_failed("Monte Carlo Error: boom")

        self.assertEqual(tab._tol_progress.maximum(), 100)
        self.assertEqual(tab._tol_progress.value(), 0)
        self.assertIn("boom", tab._tol_results_text.toPlainText())
        self.assertFalse(tab._mc_running)

    def test_progress_bar_is_not_left_busy(self):
        """Regression guard: the spinner used to be left in range 0..0."""
        tab = self.tab
        for slot, args in (
            ("_on_analysis_finished", ("ok", {})),
            ("_on_analysis_failed", ("nope",)),
        ):
            tab._tol_progress.setMaximum(0)
            tab._tol_progress.setValue(0)
            getattr(tab, slot)(*args)
            self.assertNotEqual(
                tab._tol_progress.maximum(),
                0,
                f"{slot} left the progress bar indeterminate",
            )

    def test_second_run_is_rejected_while_one_is_in_flight(self):
        """The guard must stop a duplicate start, not launch a second thread."""
        tab = self.tab
        tab._mc_running = True
        tab._on_run_monte_carlo()
        self.assertIn("already running", tab._tol_results_text.toPlainText())
        # _mc_worker is initialized to None and released once a run finishes,
        # so test for "no live thread" rather than for absence of the slot.
        self.assertFalse(tab._mc_worker is not None and tab._mc_worker.isRunning())

        tab._mc_running = False
        tab._inv_running = True
        tab._on_run_inverse_sensitivity()
        self.assertIn("already running", tab._tol_results_text.toPlainText())

    def test_monte_carlo_run_completes_and_clears_busy_state(self):
        """End to end through the real thread: busy in, report out."""
        from PySide6.QtCore import QEventLoop, QTimer

        tab = self.tab
        tab._tol_num_trials.setValue(10)
        tab._tol_refocus_check.setChecked(False)

        loop = QEventLoop()
        tab._tol_results_text.textChanged.connect(loop.quit)
        QTimer.singleShot(30000, loop.quit)  # hard stop, never hangs the suite
        tab._on_run_monte_carlo()
        self.assertTrue(tab._mc_running)
        self.assertEqual(tab._tol_progress.maximum(), 0)  # busy
        loop.exec()

        self.assertFalse(tab._mc_running)
        self.assertEqual(tab._tol_progress.maximum(), 100)
        self.assertIn("MONTE CARLO", tab._tol_results_text.toPlainText())

    def test_inverse_sensitivity_run_completes_and_clears_busy_state(self):
        """Same for the inverse-sensitivity worker."""
        from PySide6.QtCore import QEventLoop, QTimer

        tab = self.tab

        loop = QEventLoop()
        tab._tol_results_text.textChanged.connect(loop.quit)
        QTimer.singleShot(30000, loop.quit)
        tab._on_run_inverse_sensitivity()
        self.assertTrue(tab._inv_running)
        self.assertEqual(tab._tol_progress.maximum(), 0)  # busy
        loop.exec()

        self.assertFalse(tab._inv_running)
        self.assertEqual(tab._tol_progress.maximum(), 100)
        self.assertIn("INVERSE SENSITIVITY", tab._tol_results_text.toPlainText())


if __name__ == "__main__":
    unittest.main()
