#!/usr/bin/env python3
"""Regression: the two tolerance analyses must not share a completion slot.

Both workers connected ``finished``/``failed`` to ``_on_analysis_finished`` and
``_on_analysis_failed``, and each of those cleared **both** running flags. So:

1. Start Monte Carlo, then Inverse Sensitivity.
2. Inverse finishes, and its handler clears ``_mc_running`` while Monte Carlo is
   still running.
3. Clicking "Run Monte Carlo" again overwrites ``self._mc_worker`` while the
   old thread is live.
4. The workers had no Qt parent, so Python destroyed a running QThread and the
   process aborted - "QThread: Destroyed while thread is still running" -
   which is exactly the crash the surrounding comments say they guard against.

Each worker now clears only its own flag, each has its own completion slot, the
workers are parented to the tab so Qt owns them, and a live worker is never
replaced.

The fixture builds a real TolerancingTab rather than a stub, so the slots under
test are the ones the workers are actually wired to.
"""

import inspect
import os
import sys
import unittest

if os.environ.get("DISPLAY", "") == "" and sys.platform.startswith("linux"):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication

    PYSIDE_AVAILABLE = True
except ImportError as _e:  # pragma: no cover - environment guard
    QApplication = None  # type: ignore
    PYSIDE_AVAILABLE = False
    _PYSIDE_ERROR = _e

if PYSIDE_AVAILABLE:
    _app = QApplication.instance()
    if not _app:
        _app = QApplication(sys.argv)


class _FakeWorker:
    """Stands in for a QThread, recording only what the tab consults."""

    def __init__(self, running=True):
        self._running = running

    def isRunning(self):
        return self._running

    def deleteLater(self):
        pass


class _UncertainWorker:
    def isRunning(self):
        raise RuntimeError("thread state unavailable")


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 not available")
class _TabFixture(unittest.TestCase):
    def setUp(self):
        from src.gui.tabs.tolerancing_tab import TolerancingTab

        self.tab = TolerancingTab()

    def tearDown(self):
        self.tab.deleteLater()


class TestFinishedAnalysisUnblocksOnlyItself(_TabFixture):
    """A finished analysis must not unblock the other one."""

    def _both_running(self):
        self.tab._mc_running = True
        self.tab._inv_running = True
        # The Monte Carlo worker is still live; the inverse one has stopped.
        self.tab._mc_worker = _FakeWorker(running=True)
        self.tab._inv_worker = _FakeWorker(running=False)

    def test_finished_inverse_does_not_clear_the_monte_carlo_flag(self):
        """The bug: this handler used to clear both flags."""
        self._both_running()

        self.tab._on_inv_finished("report", {"yield": 1.0})

        self.assertFalse(self.tab._inv_running, "the inverse-sensitivity flag was not cleared")
        self.assertTrue(
            self.tab._mc_running,
            "a finished inverse-sensitivity run unblocked the still-running " "Monte Carlo run",
        )

    def test_finished_monte_carlo_does_not_clear_the_inverse_flag(self):
        self._both_running()

        self.tab._on_mc_finished("report", {"yield": 1.0})

        self.assertFalse(self.tab._mc_running)
        self.assertTrue(
            self.tab._inv_running,
            "a finished Monte Carlo run unblocked the still-running " "inverse-sensitivity run",
        )

    def test_a_failed_inverse_does_not_clear_the_monte_carlo_flag(self):
        self._both_running()

        self.tab._on_inv_failed("boom")

        self.assertFalse(self.tab._inv_running)
        self.assertTrue(self.tab._mc_running)

    def test_a_failed_monte_carlo_does_not_clear_the_inverse_flag(self):
        self._both_running()

        self.tab._on_mc_failed("boom")

        self.assertFalse(self.tab._mc_running)
        self.assertTrue(self.tab._inv_running)

    def test_a_live_worker_is_not_replaced_by_the_release(self):
        """The crash path: the still-running worker must survive."""
        self._both_running()
        mc = self.tab._mc_worker

        self.tab._on_inv_finished("report", {})

        self.assertIs(
            self.tab._mc_worker,
            mc,
            "the live Monte Carlo worker was released, so a later run could "
            "replace a running thread",
        )

    def test_the_generic_slot_still_clears_both(self):
        """Kept for callers that finish an analysis from outside the run handlers."""
        self._both_running()

        self.tab._on_analysis_finished("report", {})

        self.assertFalse(self.tab._mc_running)
        self.assertFalse(self.tab._inv_running)


class TestWorkerIsRunning(_TabFixture):
    """The guard that stops a live worker being replaced."""

    def test_no_worker_is_not_running(self):
        self.tab._mc_worker = None
        self.assertFalse(self.tab._worker_is_running("_mc_worker"))

    def test_a_running_worker_is_reported(self):
        self.tab._mc_worker = _FakeWorker(running=True)
        self.assertTrue(self.tab._worker_is_running("_mc_worker"))

    def test_a_stopped_worker_is_not_reported(self):
        self.tab._mc_worker = _FakeWorker(running=False)
        self.assertFalse(self.tab._worker_is_running("_mc_worker"))

    def test_an_unknown_state_counts_as_running(self):
        """Never replace a worker on a guess."""
        self.tab._mc_worker = _UncertainWorker()
        self.assertTrue(self.tab._worker_is_running("_mc_worker"))


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 not available")
class TestWorkersAreParented(unittest.TestCase):
    """An unparented QThread can be destroyed while it runs, aborting the process."""

    def test_both_worker_classes_accept_a_parent(self):
        from src.gui.tabs.tolerancing_tab import (
            InverseSensitivityWorker,
            MonteCarloWorker,
        )

        for worker_class in (MonteCarloWorker, InverseSensitivityWorker):
            with self.subTest(worker=worker_class.__name__):
                parameters = inspect.signature(worker_class.__init__).parameters
                self.assertIn(
                    "parent",
                    parameters,
                    f"{worker_class.__name__} takes no Qt parent, so Qt does "
                    f"not own the thread and it can be destroyed while running",
                )


class _RecordingSignal:
    def __init__(self):
        self.connected = []

    def connect(self, slot):
        self.connected.append(slot)


class _RecordingWorker:
    """Records what the tab wires up instead of starting a thread."""

    instances = []

    def __init__(self, *args, **kwargs):
        self.finished = _RecordingSignal()
        self.failed = _RecordingSignal()
        self.parent_arg = kwargs.get("parent")
        self.started = False
        _RecordingWorker.instances.append(self)

    def start(self):
        self.started = True

    def isRunning(self):
        return False


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 not available")
class TestRunHandlersWireTheRightSlots(unittest.TestCase):
    """The crash came from the wiring, so the wiring is what is tested."""

    def setUp(self):
        import src.gui.tabs.tolerancing_tab as module
        from src.gui.tabs.tolerancing_tab import TolerancingTab

        from src.lens import Lens
        from src.tolerancing import ToleranceOperand, ToleranceType

        self.module = module
        _RecordingWorker.instances = []

        class _Parent:
            def __init__(self):
                self._current_lens = Lens(name="T", radius_of_curvature_1=50.0, thickness=5.0)
                self._current_assembly = None
                self._tol_operands = [
                    ToleranceOperand(
                        element_index=0,
                        param_type=ToleranceType.RADIUS_1,
                        min_val=-1.0,
                        max_val=1.0,
                    )
                ]

            def _update_status(self, message):
                pass

        self.tab = TolerancingTab()
        self.tab._parent = _Parent()

        self._saved = (
            module.MonteCarloWorker,
            module.InverseSensitivityWorker,
        )
        module.MonteCarloWorker = _RecordingWorker
        module.InverseSensitivityWorker = _RecordingWorker

    def tearDown(self):
        (
            self.module.MonteCarloWorker,
            self.module.InverseSensitivityWorker,
        ) = self._saved
        self.tab.deleteLater()

    def test_monte_carlo_is_wired_to_the_monte_carlo_slots(self):
        self.tab._on_run_monte_carlo()

        worker = _RecordingWorker.instances[-1]
        self.assertIn(self.tab._on_mc_finished, worker.finished.connected)
        self.assertIn(self.tab._on_mc_failed, worker.failed.connected)
        self.assertNotIn(
            self.tab._on_analysis_finished,
            worker.finished.connected,
            "Monte Carlo is wired to the both-flags slot, so a finished "
            "inverse-sensitivity run would unblock it",
        )

    def test_inverse_sensitivity_is_wired_to_the_inverse_slots(self):
        self.tab._on_run_inverse_sensitivity()

        worker = _RecordingWorker.instances[-1]
        self.assertIn(self.tab._on_inv_finished, worker.finished.connected)
        self.assertIn(self.tab._on_inv_failed, worker.failed.connected)
        self.assertNotIn(self.tab._on_analysis_finished, worker.finished.connected)

    def test_both_workers_are_parented_to_the_tab(self):
        """No Qt parent means Python can destroy a running QThread and abort."""
        self.tab._on_run_monte_carlo()
        self.tab._on_run_inverse_sensitivity()

        self.assertEqual(len(_RecordingWorker.instances), 2)
        for worker in _RecordingWorker.instances:
            with self.subTest(parent=worker.parent_arg):
                self.assertIs(
                    worker.parent_arg,
                    self.tab,
                    "the worker has no Qt parent, so Qt does not own the "
                    "thread and Python can destroy it while it runs",
                )

    def test_a_running_worker_is_not_replaced(self):
        """Clicking again while the first is live must not overwrite it."""
        self.tab._mc_worker = _FakeWorker(running=True)
        self.tab._mc_running = False  # as if a stale handler had cleared it

        self.tab._on_run_monte_carlo()

        self.assertIsInstance(
            self.tab._mc_worker,
            _FakeWorker,
            "the live worker was replaced, destroying a running QThread",
        )
        self.assertFalse(
            self.tab._mc_running,
            "the flag was set even though the run was refused",
        )


if __name__ == "__main__":
    unittest.main()
