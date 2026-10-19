"""Regression: closing the window must not lose the last edit, or abort.

Edits are saved ``EDIT_COMMIT_DELAY_MS`` after the last change, so quitting
inside that 400 ms window dropped the final edit with nothing to say so.

Nothing stopped or waited for the optimization, tolerancing or analysis threads
on exit, so quitting mid-run let CPython destroy a live QThread and ``~QThread``
abort the process - "QThread: Destroyed while thread is still running".
"""

import os
import sys
import unittest

if os.environ.get("DISPLAY", "") == "" and sys.platform.startswith("linux"):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication

    PYSIDE_AVAILABLE = True
except ImportError:  # pragma: no cover - environment guard
    PYSIDE_AVAILABLE = False

if PYSIDE_AVAILABLE:
    _app = QApplication.instance() or QApplication(sys.argv)


def _window_class():
    """Import the main window lazily: it pulls in the whole GUI."""
    from openlens.__main__ import OpenLensWindow

    return OpenLensWindow


class _Worker:
    """Stands in for a QThread, recording what was done to it."""

    def __init__(self, running=True, honours=True):
        self._running = running
        self._honours = honours
        self.interrupted = False
        self.terminated = False
        self.waits = []

    def isRunning(self):
        return self._running

    def requestInterruption(self):
        self.interrupted = True
        if self._honours:
            self._running = False

    def wait(self, timeout=None):
        self.waits.append(timeout)
        return not self._running

    def terminate(self):
        self.terminated = True
        self._running = False


class _RaisingWorker(_Worker):
    def isRunning(self):
        raise RuntimeError("thread state unknown")


class _CloseEvent:
    def __init__(self):
        self.accepted = None

    def accept(self):
        self.accepted = True

    def ignore(self):
        self.accepted = False


class _Bare:
    """A stand-in with only the attributes _shutdown_workers reaches for.

    Deliberately not a QOpenLensWindow: closeEvent only touches _flush_pending_edit,
    _shutdown_workers and the worker attributes, and a real OpenLensWindow drags in
    the database and a large widget tree for no added coverage here.

    ``_confirm_close_with_work`` is the one deliberate seam: the real one opens a
    modal QMessageBox, which would block the suite. It records the counts it was
    asked about so tests can assert the prompt happened.
    """

    def __init__(self, confirm_answer=True):
        self.flushed = 0
        self.events = []
        self._opt_tab = None
        self._tol_tab = None
        self._analysis_dialogs = []
        self.confirm_answer = confirm_answer
        self.confirmations = []

    def _flush_pending_edit(self):
        self.flushed += 1

    def _stop_worker(self, worker, timeout_ms=3000):
        return OpenLensWindow._stop_worker(self, worker, timeout_ms)

    def _worker_still_running(self, worker):
        return OpenLensWindow._worker_still_running(self, worker)

    def _running_work_count(self):
        return OpenLensWindow._running_work_count(self)

    def _confirm_close_with_work(self, count):
        self.confirmations.append(count)
        return self.confirm_answer

    def _shutdown_workers(self):
        return OpenLensWindow._shutdown_workers(self)

    def closeEvent(self, event):
        return OpenLensWindow.closeEvent(self, event)

    def _retire_analysis_dialog(self, dialog):
        self.events.append(("retire", dialog))


if PYSIDE_AVAILABLE:
    OpenLensWindow = _window_class()


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 not available")
class TestThePendingEditIsCommitted(unittest.TestCase):
    def setUp(self):
        self.window = _Bare()

    def test_closing_commits_the_pending_edit(self):
        event = _CloseEvent()

        self.window.closeEvent(event)

        self.assertEqual(
            self.window.flushed,
            1,
            msg="the debounced edit was dropped on exit",
        )

    def test_closing_is_accepted(self):
        event = _CloseEvent()

        self.window.closeEvent(event)

        self.assertTrue(event.accepted, "closeEvent did not accept, so the window hangs")

    def test_a_real_debounced_edit_reaches_the_save(self):
        """The end-to-end claim: edit, quit inside the window, nothing lost.

        Uses the real ``_flush_pending_edit`` with a real QTimer, so this
        covers the part the stand-in cannot - that an *active* debounce timer
        is what triggers the commit.
        """
        from PySide6.QtCore import QTimer

        from openlens.__main__ import OpenLensWindow

        window = OpenLensWindow.__new__(OpenLensWindow)
        window._pending_edit_status = "edited"
        window._edit_timer = QTimer()
        window._edit_timer.setSingleShot(True)
        window._edit_timer.start(30000)
        self.assertTrue(window._edit_timer.isActive())

        commits = []
        window._save_to_database = lambda **kw: commits.append(kw)
        window._update_all_tabs = lambda: None

        OpenLensWindow.closeEvent(window, _CloseEvent())

        self.assertEqual(
            commits,
            [{"reconcile": False}],
            msg="the pending edit never reached the save, so it was lost on quit",
        )
        self.assertIsNone(window._pending_edit_status, "the pending edit was left pending")

    def test_closing_with_no_debounce_pending_still_saves_nothing_extra(self):
        from PySide6.QtCore import QTimer

        from openlens.__main__ import OpenLensWindow

        window = OpenLensWindow.__new__(OpenLensWindow)
        window._pending_edit_status = None
        window._edit_timer = QTimer()
        window._edit_timer.setSingleShot(True)

        commits = []
        window._save_to_database = lambda **kw: commits.append(kw)
        window._update_all_tabs = lambda: None

        OpenLensWindow.closeEvent(window, _CloseEvent())

        self.assertEqual(commits, [], "saved with nothing pending to save")


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 not available")
class TestWorkersAreStopped(unittest.TestCase):
    def setUp(self):
        self.window = _Bare()

    def test_a_running_tolerancing_worker_is_interrupted(self):
        worker = _Worker()
        self.window._tol_tab = type("T", (), {"_mc_worker": worker, "_inv_worker": None})()

        self.window._shutdown_workers()

        self.assertTrue(
            worker.interrupted,
            msg="quitting mid-run leaves the Monte Carlo thread alive, so ~QThread aborts",
        )

    def test_a_cooperative_worker_is_not_terminated(self):
        worker = _Worker(honours=True)
        self.window._tol_tab = type("T", (), {"_mc_worker": worker, "_inv_worker": None})()

        self.window._shutdown_workers()

        self.assertFalse(worker.terminated, "terminated a worker that had already unwound")

    def test_a_stubborn_worker_is_terminated(self):
        """A thread stuck inside one long evaluation never sees the request."""
        worker = _Worker(honours=False)
        self.window._tol_tab = type("T", (), {"_mc_worker": worker, "_inv_worker": None})()

        self.window._shutdown_workers()

        self.assertTrue(worker.terminated, "a worker ignoring the request was left running")
        self.assertEqual(
            worker.waits[0],
            3000,
            msg="escalated to terminate without first waiting for the cooperative request",
        )

    def test_both_tolerancing_workers_are_stopped(self):
        mc, inv = _Worker(), _Worker()
        self.window._tol_tab = type("T", (), {"_mc_worker": mc, "_inv_worker": inv})()

        self.window._shutdown_workers()

        self.assertTrue(mc.interrupted)
        self.assertTrue(inv.interrupted)

    def test_a_stopped_worker_reference_is_released(self):
        worker = _Worker()
        tab = type("T", (), {"_mc_worker": worker, "_inv_worker": None})()
        self.window._tol_tab = tab

        self.window._shutdown_workers()

        self.assertIsNone(
            tab._mc_worker,
            msg="the reference was kept; that is the safe side, so a failure here "
            "means the thread stopped and was not released",
        )

    def test_an_unstoppable_worker_keeps_its_reference(self):
        """Dropping a live QThread's last reference aborts the process."""
        worker = _RaisingWorker()
        tab = type("T", (), {"_mc_worker": worker, "_inv_worker": None})()
        self.window._tol_tab = tab

        self.window._shutdown_workers()

        self.assertIs(
            tab._mc_worker,
            worker,
            msg="the reference was dropped while the thread's state was unknown",
        )

    def test_a_running_analysis_worker_is_interrupted(self):
        worker = _Worker()
        dialog = type("D", (), {"_pending_worker": worker})()
        self.window._analysis_dialogs = [dialog]

        self.window._shutdown_workers()

        self.assertTrue(worker.interrupted, "quitting left an analysis thread running")

    def test_a_finished_analysis_dialog_is_retired(self):
        dialog = type("D", (), {"_pending_worker": _Worker(running=False)})()
        self.window._analysis_dialogs = [dialog]

        self.window._shutdown_workers()

        self.assertIn(("retire", dialog), self.window.events)

    def test_the_optimizer_stop_path_is_reused(self):
        """Two ways to stop a thread is how they come to disagree."""

        class _OptTab:
            def __init__(self):
                self.calls = 0

            def _on_stop_optimization(self):
                self.calls += 1

        tab = _OptTab()
        self.window._opt_tab = tab

        self.window._shutdown_workers()

        self.assertEqual(tab.calls, 1)

    def test_a_raising_optimizer_tab_does_not_abort_shutdown(self):
        class _BadOpt:
            def _on_stop_optimization(self):
                raise RuntimeError("boom")

        self.window._opt_tab = _BadOpt()
        worker = _Worker()
        self.window._tol_tab = type("T", (), {"_mc_worker": worker, "_inv_worker": None})()

        self.window._shutdown_workers()

        self.assertTrue(
            worker.interrupted,
            msg="one failing tab stopped every later tab from shutting down",
        )

    def test_closing_stops_the_workers(self):
        """closeEvent, not just the helper.

        Testing _shutdown_workers directly left this uncaught: with the call
        removed from closeEvent every test here still passed, and quitting
        mid-run would still abort.
        """
        worker = _Worker()
        self.window._tol_tab = type("T", (), {"_mc_worker": worker, "_inv_worker": None})()

        self.window.closeEvent(_CloseEvent())

        self.assertTrue(
            worker.interrupted,
            msg="closeEvent does not shut the workers down, so quitting " "mid-run still aborts",
        )

    def test_closing_commits_the_edit_and_stops_the_workers(self):
        """Both halves, through the one entry point that runs on quit."""
        worker = _Worker()
        self.window._tol_tab = type("T", (), {"_mc_worker": worker, "_inv_worker": None})()

        self.window.closeEvent(_CloseEvent())

        self.assertEqual(self.window.flushed, 1)
        self.assertTrue(worker.interrupted)


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 not available")
class TestRunningWorkIsConfirmedBeforeQuit(unittest.TestCase):
    """#528: quitting mid-run must not silently discard the work.

    A four-minute Monte Carlo run and an idle window look the same from the
    outside, so quitting with work in flight has to ask first.
    """

    def setUp(self):
        self.window = _Bare()

    @staticmethod
    def _tol_tab(mc=None, inv=None):
        return type("T", (), {"_mc_worker": mc, "_inv_worker": inv})()

    def test_a_running_operation_is_confirmed_before_quitting(self):
        worker = _Worker()
        self.window._tol_tab = self._tol_tab(mc=worker)

        event = _CloseEvent()
        self.window.closeEvent(event)

        self.assertEqual(
            self.window.confirmations,
            [1],
            msg="quit with work in flight and never asked",
        )
        self.assertTrue(event.accepted)

    def test_declining_keeps_the_window_and_the_work(self):
        worker = _Worker()
        self.window.confirm_answer = False
        self.window._tol_tab = self._tol_tab(mc=worker)

        event = _CloseEvent()
        self.window.closeEvent(event)

        self.assertFalse(event.accepted, "declined the quit and closed anyway")
        self.assertEqual(self.window.flushed, 0, "saved and shut down after the user declined")
        self.assertFalse(worker.interrupted, "stopped the work the user chose to keep")

    def test_an_idle_window_closes_without_asking(self):
        event = _CloseEvent()

        self.window.closeEvent(event)

        self.assertEqual(self.window.confirmations, [], "asked about work that was not running")
        self.assertTrue(event.accepted)
        self.assertEqual(self.window.flushed, 1)

    def test_every_running_operation_is_counted(self):
        finished = type("D", (), {"_pending_worker": _Worker(running=False)})()
        self.window._tol_tab = self._tol_tab(mc=_Worker(), inv=_Worker())
        self.window._analysis_dialogs = [type("D", (), {"_pending_worker": _Worker()})(), finished]

        self.window.closeEvent(_CloseEvent())

        self.assertEqual(
            self.window.confirmations,
            [3],
            msg="the prompt must say how much is at stake",
        )

    def test_the_optimizer_counts_even_before_a_worker_object_exists(self):
        """_opt_is_running is set before the QThread is constructed."""

        class _Opt:
            _opt_is_running = True
            _opt_worker = None

            def _on_stop_optimization(self):
                self._opt_is_running = False

        self.window._opt_tab = _Opt()

        self.window.closeEvent(_CloseEvent())

        self.assertEqual(self.window.confirmations, [1])

    def test_a_finished_worker_is_not_counted(self):
        self.window._tol_tab = self._tol_tab(mc=_Worker(running=False), inv=_Worker(running=False))
        self.window._analysis_dialogs = [
            type("D", (), {"_pending_worker": _Worker(running=False)})()
        ]

        self.window.closeEvent(_CloseEvent())

        self.assertEqual(self.window.confirmations, [])

    def test_a_worker_with_unknown_state_is_counted(self):
        """Unknown is treated as running: a needless prompt costs one click,
        silently discarding the run costs the run."""
        self.window._tol_tab = self._tol_tab(mc=_RaisingWorker())

        self.window.closeEvent(_CloseEvent())

        self.assertEqual(self.window.confirmations, [1])

    def test_confirming_still_stops_the_workers(self):
        worker = _Worker()
        self.window._tol_tab = self._tol_tab(mc=worker)

        event = _CloseEvent()
        self.window.closeEvent(event)

        self.assertTrue(worker.interrupted, "confirmed the quit but left the thread running")
        self.assertTrue(event.accepted)


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 not available")
class TestTheConfirmationDialog(unittest.TestCase):
    """The real _confirm_close_with_work, with the modal box patched out."""

    def setUp(self):
        self.window = OpenLensWindow.__new__(OpenLensWindow)

    def _ask(self, count, answer):
        from unittest import mock

        from PySide6.QtWidgets import QMessageBox

        with mock.patch.object(QMessageBox, "question", return_value=answer) as asked:
            result = OpenLensWindow._confirm_close_with_work(self.window, count)
        return result, asked

    def test_yes_returns_true(self):
        from PySide6.QtWidgets import QMessageBox

        result, _ = self._ask(2, QMessageBox.StandardButton.Yes)

        self.assertTrue(result)

    def test_no_returns_false(self):
        from PySide6.QtWidgets import QMessageBox

        result, _ = self._ask(2, QMessageBox.StandardButton.No)

        self.assertFalse(result)

    def test_the_count_appears_in_the_message(self):
        from PySide6.QtWidgets import QMessageBox

        _, asked = self._ask(3, QMessageBox.StandardButton.No)

        self.assertIn("3", asked.call_args[0][2])

    def test_singular_wording_for_one_operation(self):
        from PySide6.QtWidgets import QMessageBox

        _, asked = self._ask(1, QMessageBox.StandardButton.No)
        text = asked.call_args[0][2]

        self.assertIn("1 operation is", text)
        self.assertNotIn("1 operations", text)

    def test_the_default_button_is_no(self):
        """A stray Return must keep the work, not throw it away."""
        from PySide6.QtWidgets import QMessageBox

        _, asked = self._ask(1, QMessageBox.StandardButton.No)

        self.assertEqual(asked.call_args[0][4], QMessageBox.StandardButton.No)


class TestStopWorkerEdgeCases(unittest.TestCase):
    def setUp(self):
        if not PYSIDE_AVAILABLE:
            self.skipTest("PySide6 not available")
        self.window = _Bare()

    def test_none_is_already_stopped(self):
        self.assertTrue(self.window._stop_worker(None))

    def test_an_already_finished_worker_is_left_alone(self):
        worker = _Worker(running=False)

        self.assertTrue(self.window._stop_worker(worker))
        self.assertFalse(worker.interrupted, "asked a finished thread to stop")
        self.assertFalse(worker.terminated)

    def test_a_worker_raising_on_terminate_is_reported_as_unstopped(self):
        class _Bad(_Worker):
            def terminate(self):
                raise RuntimeError("cannot terminate")

        worker = _Bad(honours=False)
        worker.wait = lambda timeout=None: False

        self.assertFalse(
            self.window._stop_worker(worker),
            msg="reported stopped when the thread is still running, so its "
            "reference would be dropped and the process aborted",
        )


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 not available")
class TestTheWindowReallyHasCloseEvent(unittest.TestCase):
    def test_main_window_defines_close_event(self):
        from openlens.__main__ import OpenLensWindow

        self.assertTrue(
            hasattr(OpenLensWindow, "closeEvent"),
            msg="the main window has no closeEvent, so nothing runs on quit",
        )


if __name__ == "__main__":
    unittest.main()
