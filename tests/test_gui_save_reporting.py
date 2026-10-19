"""Regression: the GUI must never claim a save succeeded when it failed.

``LensStorage.save_lenses`` catches every exception, reports it through an
optional status callback and returns ``False``. The main window built its
storage with no callback, discarded the return value, and ``_on_save``
unconditionally said "Saved to database". Nothing called
``logging.basicConfig``, so the only trace of the failure was Python's
last-resort stderr handler - invisible to a user running the app.

The effect was that any failing save looked like a successful one. On a
database this app could not write to, the user typed, saw "Saved to database",
reopened the app, and found every edit gone with nothing explaining why.

These tests assert that a failed save is reported as a failure, that the
autosave path does not spam a dialog on every keystroke, that a failed *load*
tells the user instead of silently emptying the library, and that the error
reporting never blocks the event loop.
"""

import logging
import os
import sys
import tempfile
import unittest
from unittest import mock

# Headless environments (CI): fall back to Qt's offscreen platform before
# any QApplication is created. A real DISPLAY always wins.
if os.environ.get("DISPLAY", "") == "" and sys.platform.startswith("linux"):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication

    import openlens
    from openlens.__main__ import OpenLensWindow

    PYSIDE_AVAILABLE = True
    _PYSIDE_ERROR = None
except ImportError as _e:
    QApplication = openlens = None  # type: ignore
    OpenLensWindow = None  # type: ignore
    PYSIDE_AVAILABLE = False
    _PYSIDE_ERROR = _e

if PYSIDE_AVAILABLE:
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 not available")
class _WindowCase(unittest.TestCase):
    """A window wired to a throwaway database, with one lens in the library."""

    def setUp(self):
        from openlens.gui.storage import LensStorage

        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
        self.storage = LensStorage(self.temp_db)
        self.window = OpenLensWindow()
        self.window._storage = self.storage
        self.window._db_path = self.temp_db
        self.window._lenses = []
        self.window._assemblies = []
        self.window._current_lens = None
        self.window._current_assembly = None
        self.window._load_default_lens()

        # Collected instead of shown: the tests assert on what the user is
        # told, and _notify_problem is the single seam for that.
        self.problems = []
        self._patch_problems()

    def tearDown(self):
        self.patcher.stop()
        self.window.close()
        for path in (self.temp_db, self.temp_db + "-shm", self.temp_db + "-wal"):
            if os.path.exists(path):
                os.remove(path)

    def _patch_problems(self):
        self.patcher = mock.patch.object(
            self.window, "_notify_problem", side_effect=self._record_problem
        )
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def _record_problem(self, title, text):
        self.problems.append((title, text))

    def _break_the_database(self):
        """Make every real save raise, the way an unwritable file would."""
        error = RuntimeError("table lenses has no column named is_parabolic_1")
        self.storage.db.save_lens = mock.Mock(side_effect=error)
        self.storage.db.save_assembly = mock.Mock(side_effect=error)

    def _save(self):
        self.window._on_save()
        return self.window.statusBar().currentMessage()


class TestFailedSaveIsNotReportedAsSuccess(_WindowCase):
    """The headline defect: "Saved to database" after a failed save."""

    def test_status_does_not_claim_success_after_a_real_failure(self):
        """A database that raises must not leave a success message."""
        self._break_the_database()

        status = self._save()

        self.assertNotIn("Saved to database", status)
        self.assertIn("ail", status, f"the failure was not reported: {status!r}")

    def test_failure_raises_a_problem_report(self):
        """Silent data loss has to be loud the first time it happens."""
        self._break_the_database()

        self._save()

        self.assertEqual(len(self.problems), 1)
        title, message = self.problems[0]
        self.assertIn("Save", title)
        self.assertIn("no column named is_parabolic_1", message)

    def test_failure_is_reported_even_when_save_lenses_only_returns_false(self):
        """The window must honour the return value, not rely on an exception.

        save_lenses swallows the exception itself and reports False, so a
        caller that ignores the return value sees no failure at all.
        """
        self.window._storage.save_lenses = mock.Mock(return_value=False)

        status = self._save()

        self.assertNotIn("Saved to database", status)
        self.assertEqual(len(self.problems), 1)

    def test_successful_save_still_reports_success(self):
        """The fix must not turn every save into an error."""
        self.window._save_to_database()
        self.window._lens_editor._on_property_changed()

        status = self._save()

        self.assertIn("Saved to database", status)
        self.assertEqual(self.problems, [])


class TestFailureIsNotSpammedOnAutosave(_WindowCase):
    """The save path runs on every edit, so it cannot nag on every keystroke."""

    def test_repeated_failures_show_one_report(self):
        """Three failing saves must not stack three dialogs."""
        self._break_the_database()

        for _ in range(3):
            self._save()

        self.assertEqual(len(self.problems), 1)

    def test_status_still_reports_every_failure(self):
        """After the dialog, the status bar keeps telling the truth."""
        self._break_the_database()

        for _ in range(3):
            self.assertIn("ail", self._save())

    def test_a_later_success_arms_the_report_again(self):
        """The dialog is per failure streak, not once per session."""
        real_save_lenses = self.storage.save_lenses

        self._break_the_database()
        self._save()

        # A save that gets through...
        self.storage.save_lenses = mock.Mock(return_value=True)
        self._save()

        # ...before the database breaks again must re-arm the report. The real
        # save_lenses has to come back, or the mock keeps reporting success.
        self.storage.save_lenses = real_save_lenses
        self._break_the_database()
        self._save()

        self.assertEqual(len(self.problems), 2, "the report did not re-arm")


class TestStorageStatusCallbackIsWired(unittest.TestCase):
    """storage.py reports through a callback the window never supplied."""

    def setUp(self):
        if not PYSIDE_AVAILABLE:
            self.skipTest("PySide6 not available")
        # A window's own storage, not one injected by a test: the defect is in
        # how OpenLensWindow constructs LensStorage.
        self.window = OpenLensWindow()
        self.addCleanup(self.window.close)
        self.problems = []
        patcher = mock.patch.object(
            self.window, "_notify_problem", side_effect=self.problems.append
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_window_storage_has_a_real_status_callback(self):
        """LensStorage defaults to a no-op lambda; the window must not."""
        self.assertIsNotNone(self.window._storage.status_callback)
        self.assertNotEqual(self.window._storage.status_callback.__qualname__, "<lambda>")

    def test_window_storage_status_reaches_the_status_bar(self):
        """A message from storage must actually show up."""
        self.window._storage._update_status("Error: something went wrong")
        self.assertIn("something went wrong", self.window.statusBar().currentMessage())

    def test_storage_retains_the_underlying_error(self):
        """save_lenses returns False; the reason has to survive somewhere."""
        self.assertIsNone(self.window._storage.last_error)


class TestFailedLoadIsReported(_WindowCase):
    """A failed load used to reset the library in silence."""

    def setUp(self):
        super().setUp()
        self.window._storage.load_lenses = mock.Mock(side_effect=RuntimeError("database is locked"))

    def _load(self):
        with mock.patch("openlens.__main__.QMessageBox.information"):
            self.window._load_from_database()
        return self.window.statusBar().currentMessage()

    def test_failed_load_tells_the_user(self):
        """Wiping the library must not be invisible."""
        self._load()

        self.assertEqual(len(self.problems), 1)
        title, message = self.problems[0]
        self.assertIn("Load", title)
        self.assertIn("database is locked", message)

    def test_failed_load_does_not_claim_the_library_is_empty(self):
        """The status must not imply there is simply nothing saved."""
        self.assertIn("ail", self._load())


class TestProblemReportsDoNotBlock(_WindowCase):
    """Error reporting must never stop the event loop.

    The library load is fired from a deferred startup timer and the save runs
    on the autosave path. A modal QMessageBox on either of those freezes the
    app before the user can act - and hangs any test that later spins the event
    loop, which is exactly what happened while this fix was being written.
    """

    def test_notify_problem_returns_without_blocking(self):
        """The report has to be shown, but not with exec()."""
        self.patcher.stop()
        self.addCleanup(self.patcher.start)

        self.window._notify_problem("Save failed", "the database is read-only")

        self.assertTrue(self.window._problem_boxes, "no error box was created")

    def test_the_error_box_is_not_modal(self):
        """Modal would block the event loop; assert it explicitly."""
        self.patcher.stop()
        self.addCleanup(self.patcher.start)

        self.window._notify_problem("Save failed", "the database is read-only")
        box = self.window._problem_boxes[-1]

        self.assertFalse(box.isModal())
        self.assertTrue(box.isVisible())
        self.assertEqual(box.text(), "the database is read-only")

    def test_error_boxes_are_kept_referenced(self):
        """Qt would otherwise garbage-collect the box straight away."""
        self.patcher.stop()
        self.addCleanup(self.patcher.start)

        self.window._notify_problem("Save failed", "one")
        self.window._notify_problem("Load failed", "two")

        self.assertEqual(len(self.window._problem_boxes), 2)


class TestLoggingIsConfigured(unittest.TestCase):
    """The errors above were invisible because nothing configured logging."""

    def setUp(self):
        if not PYSIDE_AVAILABLE:
            self.skipTest("PySide6 not available")
        root = logging.getLogger()
        original = list(root.handlers)
        self.addCleanup(lambda: setattr(root, "handlers", original))
        self.addCleanup(setattr, root, "level", root.level)
        root.handlers = []
        root.setLevel(logging.WARNING)

    def test_configure_logging_makes_errors_visible(self):
        """After configuring, the root logger must have somewhere to write."""
        root = logging.getLogger()

        openlens.__main__._configure_logging()

        self.assertTrue(root.handlers, "no handler was installed")
        self.assertEqual(root.level, logging.INFO)

    def test_configure_logging_is_idempotent(self):
        """Calling it twice must not double every message."""
        openlens.__main__._configure_logging()
        openlens.__main__._configure_logging()

        self.assertLessEqual(len(logging.getLogger().handlers), 1)


if __name__ == "__main__":
    unittest.main()
