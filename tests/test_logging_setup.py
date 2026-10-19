"""#478: one logging setup for every entry point.

The GUI entry point configured stderr only; the CLI configured nothing, no
log file existed, and ``--verbose`` did nothing. These tests pin the two
sinks, idempotence, the verbose level, the read-only fallback, and that both
entry points call the setup.
"""

import contextlib
import io
import logging
import logging.handlers
import tempfile
import unittest
from pathlib import Path
from typing import List
from unittest import mock

from openlens import logging_setup


class RootLoggingFixture(unittest.TestCase):
    """Run each test with a clean root logger, then restore it."""

    def setUp(self):
        root = logging.getLogger()
        self._saved_handlers = list(root.handlers)
        self._saved_level = root.level
        for handler in list(root.handlers):
            root.removeHandler(handler)
        self.addCleanup(self._restore)

    def _restore(self):
        root = logging.getLogger()
        for handler in list(root.handlers):
            root.removeHandler(handler)
            handler.close()
        for handler in self._saved_handlers:
            root.addHandler(handler)
        root.setLevel(self._saved_level)


def _stream_handlers() -> List[logging.Handler]:
    return [
        handler
        for handler in logging.getLogger().handlers
        if isinstance(handler, logging.StreamHandler)
        and not isinstance(handler, logging.handlers.RotatingFileHandler)
    ]


def _file_handlers() -> List[logging.Handler]:
    return [
        handler
        for handler in logging.getLogger().handlers
        if isinstance(handler, logging.handlers.RotatingFileHandler)
    ]


class TestSetupLogging(RootLoggingFixture):
    def test_stderr_and_a_rotating_file_are_installed(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_file = Path(tmp) / "nested" / "openlens.log"

            logging_setup.setup_logging(log_file=log_file)

            self.assertEqual(len(_stream_handlers()), 1)
            self.assertEqual(len(_file_handlers()), 1)
            self.assertTrue(log_file.parent.is_dir())

            logging.getLogger("tests.canary").error("boom")
            for handler in logging.getLogger().handlers:
                handler.flush()
            self.assertIn("boom", log_file.read_text(encoding="utf-8"))

    def test_a_second_call_does_not_double_the_handlers(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_file = Path(tmp) / "openlens.log"

            logging_setup.setup_logging(log_file=log_file)
            count = len(logging.getLogger().handlers)
            logging_setup.setup_logging(log_file=log_file)

            self.assertEqual(len(logging.getLogger().handlers), count)

    def test_non_verbose_is_info(self):
        with tempfile.TemporaryDirectory() as tmp:
            logging_setup.setup_logging(log_file=Path(tmp) / "openlens.log")

        self.assertEqual(logging.getLogger().level, logging.INFO)

    def test_verbose_keeps_debug_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_file = Path(tmp) / "openlens.log"

            logging_setup.setup_logging(verbose=True, log_file=log_file)
            logging.getLogger("tests.canary").debug("a detail")
            for handler in logging.getLogger().handlers:
                handler.flush()

            self.assertEqual(logging.getLogger().level, logging.DEBUG)
            self.assertIn("a detail", log_file.read_text(encoding="utf-8"))

    def test_an_unwritable_log_location_still_leaves_stderr(self):
        with mock.patch.object(Path, "mkdir", side_effect=OSError("read-only install")):
            logging_setup.setup_logging(log_file=Path("/nonexistent/openlens.log"))

        self.assertEqual(len(_stream_handlers()), 1)
        self.assertEqual(_file_handlers(), [])

    def test_verbose_requested_recognises_the_flags(self):
        self.assertTrue(logging_setup.verbose_requested(["--verbose"]))
        self.assertTrue(logging_setup.verbose_requested(["-v"]))
        self.assertFalse(logging_setup.verbose_requested([]))
        self.assertFalse(logging_setup.verbose_requested(["--version"]))


class TestEntryPointsConfigureLogging(unittest.TestCase):
    def test_the_gui_entry_installs_the_shared_setup(self):
        import openlens.__main__ as entry

        with mock.patch.object(entry, "setup_logging") as setup:
            entry._configure_logging()

        setup.assert_called_once_with(verbose=False)

    def test_the_gui_entry_passes_verbose_through(self):
        import openlens.__main__ as entry

        with mock.patch.object(entry, "setup_logging") as setup:
            entry._configure_logging(verbose=True)

        setup.assert_called_once_with(verbose=True)

    def test_the_cli_entry_installs_the_shared_setup(self):
        from openlens import lens_editor

        with mock.patch.object(lens_editor, "setup_logging") as setup:
            with mock.patch.object(lens_editor, "verbose_requested", return_value=False):
                with mock.patch.object(lens_editor, "LensManager"):
                    with mock.patch("builtins.input", return_value="6"):
                        with contextlib.redirect_stdout(io.StringIO()):
                            lens_editor.main()

        setup.assert_called_once_with(verbose=False)


if __name__ == "__main__":
    unittest.main()
