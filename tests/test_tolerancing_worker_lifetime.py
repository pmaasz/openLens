#!/usr/bin/env python3
"""
Tolerancing tab worker lifetime.

Both workers hand back a payload holding a deep copy of the whole optical
system, and `_mc_worker` / `_inv_worker` were assigned and never set back to
None. Holding the last Python reference to a finished worker therefore kept
that payload alive for the tab's lifetime - one retained deep copy per
analysis run, and the same mechanism behind the earlier optimization-tab core
dump (see tests/test_optimization_stop.py).

The release must be conservative. These slots run on the GUI thread while the
worker may still be returning from `run()`; dropping a live QThread's last
reference makes CPython destroy it and `~QThread` aborts the process. So a
worker is only released once it is known to have stopped.
"""

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

from src.lens import Lens

if PYSIDE_AVAILABLE:
    _app = QApplication.instance()
    if not _app:
        _app = QApplication(sys.argv)


class _FakeWorker:
    """Stands in for a QThread, recording only what the release consults."""

    def __init__(self, running):
        self._running = running
        self.deleted_later = False

    def isRunning(self):
        return self._running

    def deleteLater(self):
        self.deleted_later = True


def _lens():
    return Lens(
        name="TolTest",
        radius_of_curvature_1=50.0,
        radius_of_curvature_2=-50.0,
        thickness=5.0,
        diameter=20.0,
        refractive_index=1.5,
    )


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 not available")
class _TolerancingTabFixture(unittest.TestCase):
    def setUp(self):
        from src.gui.tabs.tolerancing_tab import TolerancingTab

        class _Parent:
            def __init__(self, lens):
                self._current_lens = lens
                self._current_assembly = None
                self._tol_operands = []
                self.statuses = []

            def _update_status(self, message):
                self.statuses.append(message)

        self.tab = TolerancingTab()
        self.parent = _Parent(_lens())
        self.tab._parent = self.parent

    def tearDown(self):
        self.tab.deleteLater()


class TestWorkerAttributesExist(_TolerancingTabFixture):
    def test_worker_slots_start_as_none(self):
        """They were never initialized, so any early read would raise."""
        self.assertIsNone(self.tab._mc_worker)
        self.assertIsNone(self.tab._inv_worker)

    def test_no_attribute_error_when_released_before_any_run(self):
        self.tab._release_finished_workers()  # must not raise


class TestReleaseIsConservative(_TolerancingTabFixture):
    def test_stopped_worker_is_released(self):
        worker = _FakeWorker(running=False)
        self.tab._mc_worker = worker
        self.tab._release_finished_workers()
        self.assertIsNone(self.tab._mc_worker)

    def test_running_worker_is_kept(self):
        """Dropping a live QThread aborts the process - must not happen."""
        worker = _FakeWorker(running=True)
        self.tab._mc_worker = worker
        self.tab._release_finished_workers()
        self.assertIs(self.tab._mc_worker, worker)

    def test_inconclusive_check_keeps_the_worker(self):
        """No usable isRunning() answer means keep - holding costs nothing."""

        class _UncertainWorker:
            def isRunning(self):
                raise RuntimeError("thread state unavailable")

            def deleteLater(self):
                pass

        worker = _UncertainWorker()
        self.tab._inv_worker = worker
        self.tab._release_finished_workers()  # must not raise
        self.assertIs(self.tab._inv_worker, worker)

    def test_uncertain_check_does_not_break_the_report_handler(self):
        """The release sits mid-handler; it must never cost the user results."""

        class _UncertainWorker:
            def isRunning(self):
                raise RuntimeError("thread state unavailable")

        self.tab._inv_worker = _UncertainWorker()
        self.tab._tol_results_text.setPlainText("before")
        self.tab._on_analysis_finished("the report", {"yield": 0.5})
        self.assertEqual(self.tab._tol_results_text.toPlainText(), "the report")

    def test_both_workers_are_considered(self):
        mc, inv = _FakeWorker(False), _FakeWorker(False)
        self.tab._mc_worker, self.tab._inv_worker = mc, inv
        self.tab._release_finished_workers()
        self.assertIsNone(self.tab._mc_worker)
        self.assertIsNone(self.tab._inv_worker)

    def test_a_live_mc_worker_does_not_block_releasing_the_inverse_one(self):
        mc, inv = _FakeWorker(True), _FakeWorker(False)
        self.tab._mc_worker, self.tab._inv_worker = mc, inv
        self.tab._release_finished_workers()
        self.assertIs(self.tab._mc_worker, mc)
        self.assertIsNone(self.tab._inv_worker)


class TestHandlersRelease(_TolerancingTabFixture):
    def test_finished_handler_releases_and_resets_flags(self):
        worker = _FakeWorker(running=False)
        self.tab._mc_worker = worker
        self.tab._mc_running = True
        self.tab._on_analysis_finished("report", {"yield": 0.9})
        self.assertIsNone(self.tab._mc_worker)
        self.assertFalse(self.tab._mc_running)
        self.assertFalse(self.tab._inv_running)
        self.assertEqual(self.tab._tol_last_results, {"yield": 0.9})

    def test_failed_handler_releases_and_resets_flags(self):
        worker = _FakeWorker(running=False)
        self.tab._inv_worker = worker
        self.tab._inv_running = True
        self.tab._on_analysis_failed("boom")
        self.assertIsNone(self.tab._inv_worker)
        self.assertFalse(self.tab._inv_running)

    def test_finished_handler_keeps_a_still_running_worker(self):
        worker = _FakeWorker(running=True)
        self.tab._mc_worker = worker
        self.tab._on_analysis_finished("report", {})
        self.assertIs(self.tab._mc_worker, worker)


if __name__ == "__main__":
    unittest.main()
