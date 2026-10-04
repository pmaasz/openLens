#!/usr/bin/env python3
"""
Optimization tab Stop/Run thread lifecycle.

Stop used to clear ``_opt_is_running`` without touching the QThread, so the
thread kept running. A later Run overwrote ``_opt_worker``, dropping the last
Python reference to a live QThread; CPython destroyed it and
``QThread::~QThread`` aborted the process (repro: Run -> Stop -> Run, real
core dump).

The abort is fatal, so these tests assert the observable state instead of
expecting a crash: after Stop the thread must be stopped and the reference
released, and a fresh Run must be allowed to start.
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

if PYSIDE_AVAILABLE:
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)


if not PYSIDE_AVAILABLE:  # pragma: no cover - environment guard

    class TestOptimizationStop(unittest.TestCase):
        @unittest.skip(f"PySide6 not available: {_PYSIDE_ERROR}")
        def test_skip(self):
            pass


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 not available")
class _OptimizationTabFixture(unittest.TestCase):
    def setUp(self):
        from src.gui.tabs.optimization_tab import OptimizationTab

        class _Parent:
            def __init__(self, lens):
                self._current_lens = lens
                self._current_assembly = None
                self.statuses = []

            def _update_status(self, message):
                self.statuses.append(message)

        self.tab = OptimizationTab()
        lens = Lens(
            name="StopTest",
            radius_of_curvature_1=50.0,
            radius_of_curvature_2=-50.0,
            thickness=5.0,
            diameter=20.0,
            refractive_index=1.5,
        )
        self.parent = _Parent(lens)
        self.tab._parent = self.parent

        # Optimize every radius so the run is long enough to interrupt.
        self.tab._collect_variables = lambda target: self._all_variables()

    def tearDown(self):
        self.tab._on_stop_optimization()
        self.tab.deleteLater()

    def _all_variables(self):
        from src.gui.tabs.optimization_tab import OptimizationVariable, _sag_bounds

        variables = []
        lens = self.parent._current_lens
        for index, radius in ((1, lens.radius_of_curvature_1), (2, lens.radius_of_curvature_2)):
            low, high = _sag_bounds(lens)
            variables.append(
                OptimizationVariable(
                    name=f"r{index}",
                    element_index=0,
                    parameter=f"radius_of_curvature_{index}",
                    current_value=radius,
                    min_value=low,
                    max_value=high,
                )
            )
        return variables

    def _start(self):
        """Start a run and return once the worker thread is alive."""
        # One enabled target: focal length. The others are independent
        # checkboxes, not gates on the fl spin box.
        self.tab._opt_target_fl_enabled.setChecked(True)
        self.tab._opt_target_spot.setChecked(False)
        self.tab._opt_target_spherical.setChecked(False)
        self.tab._opt_target_coma.setChecked(False)
        self.tab._opt_target_astig.setChecked(False)
        self.tab._on_run_optimization()
        worker = self.tab._opt_worker
        self.assertIsNotNone(worker, "Run did not create a worker")
        for _ in range(200):
            if worker.isRunning():
                return worker
            QApplication.processEvents()
        self.fail("worker never started")


class TestStopActuallyStopsThread(_OptimizationTabFixture):
    def test_stop_leaves_no_running_thread(self):
        """The defect: Stop returned while the QThread kept running."""
        worker = self._start()
        self.assertTrue(worker.isRunning())

        self.tab._on_stop_optimization()

        self.assertFalse(
            worker.isRunning(),
            "Stop returned but the QThread is still running - a later Run "
            "would drop its last reference and abort in ~QThread",
        )
        self.assertFalse(self.tab._opt_is_running)

    def test_stop_releases_the_worker_reference(self):
        """_opt_worker must be cleared once the thread is known to be done."""
        worker = self._start()
        self.tab._on_stop_optimization()
        self.assertIsNone(self.tab._opt_worker)
        # Still safe to hold a reference from Python; nothing is destroyed
        # while it runs.
        self.assertFalse(worker.isRunning())

    def test_stop_sets_the_stopped_message(self):
        self._start()
        self.tab._on_stop_optimization()
        self.assertEqual(self.tab._opt_results_text.toPlainText(), "Optimization stopped by user.")

    def test_stop_without_a_run_is_a_no_op(self):
        self.tab._on_stop_optimization()
        self.assertFalse(self.tab._opt_is_running)
        self.assertIsNone(self.tab._opt_worker)

    def test_run_after_stop_is_allowed(self):
        """The repro path: Run -> Stop -> Run must not be refused or abort."""
        first = self._start()
        self.tab._on_stop_optimization()
        self.assertFalse(first.isRunning())

        # A fresh Run is accepted and gets its own worker.
        self.tab._opt_target_fl_enabled.setChecked(True)
        self.tab._on_run_optimization()
        second = self.tab._opt_worker
        self.assertIsNotNone(second)
        self.assertIsNot(second, first)
        self.assertNotEqual(
            self.tab._opt_results_text.toPlainText(), "Optimization stopped by user."
        )

        self.tab._on_stop_optimization()

    def test_second_run_while_running_is_refused(self):
        """The guard must reject a concurrent start, not orphan a thread."""
        worker = self._start()
        self.tab._on_run_optimization()
        self.assertIn("already running", self.tab._opt_results_text.toPlainText())
        self.assertIs(self.tab._opt_worker, worker)

        self.tab._on_stop_optimization()

    def test_start_guard_checks_the_thread_not_just_the_flag(self):
        """A stale flag must not be the only thing preventing an overwrite."""
        worker = self._start()
        # Simulate the old lie: flag cleared, thread still alive.
        self.tab._opt_is_running = False
        self.tab._on_run_optimization()
        self.assertIn("already running", self.tab._opt_results_text.toPlainText())
        self.assertIs(self.tab._opt_worker, worker)

        self.tab._opt_is_running = True
        self.tab._on_stop_optimization()
        self.assertFalse(worker.isRunning())


class TestCooperativeCancellation(_OptimizationTabFixture):
    def test_worker_stops_cooperatively_without_terminate(self):
        """Interruption is honoured at an iteration boundary, not killed."""
        worker = self._start()
        worker.requestInterruption()
        self.assertTrue(worker.wait(5000), "worker ignored requestInterruption()")
        self.assertFalse(worker.isRunning())

    def test_cancelled_worker_emits_no_result(self):
        """Stop must not be overwritten by a half-converged 'success'."""
        emitted = []

        worker = self._start()
        worker.finished.connect(lambda *a: emitted.append("finished"))
        worker.failed.connect(lambda *a: emitted.append("failed"))

        worker.requestInterruption()
        self.assertTrue(worker.wait(5000))
        # Let any queued signal drain.
        for _ in range(50):
            QApplication.processEvents()
        self.assertNotIn("finished", emitted)
        self.assertNotIn("failed", emitted)

    def test_callback_raises_the_cancel_exception(self):
        from src.gui.tabs.optimization_tab import OptimizationCancelled

        worker = self._start()
        worker.requestInterruption()
        with self.assertRaises(OptimizationCancelled):
            worker._check_interrupted(7, 0.0, [])

    def test_callback_is_a_no_op_when_not_interrupted(self):
        worker = self._start()
        self.assertIsNone(worker._check_interrupted(1, 0.0, []))
        self.tab._on_stop_optimization()


if __name__ == "__main__":
    unittest.main()
