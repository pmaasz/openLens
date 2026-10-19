"""Regression: File > Export to STEP must actually produce a file.

The menu action called ``STEPExporter`` while the module imported the class as
``StepExporter``. The resulting ``NameError`` was swallowed by the broad
``except Exception`` around the export, so the user only ever saw "Failed to
export STEP: name 'STEPExporter' is not defined" - STEP export from the GUI
could never succeed, and nothing in the test suite noticed because the
exporter itself is well covered while its GUI wiring was not.

These tests drive ``_on_export_step`` end to end through a patched file dialog.
"""

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

    from openlens.__main__ import OpenLensWindow

    PYSIDE_AVAILABLE = True
    _PYSIDE_ERROR = None
except ImportError as _e:
    QApplication = None  # type: ignore
    OpenLensWindow = None  # type: ignore
    PYSIDE_AVAILABLE = False
    _PYSIDE_ERROR = _e

if PYSIDE_AVAILABLE:
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 not available")
class TestStepExportGuiWiring(unittest.TestCase):
    """The File > Export to STEP action must run end to end."""

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

        handle, self.step_path = tempfile.mkstemp(suffix=".step")
        os.close(handle)
        os.remove(self.step_path)  # the exporter must create the file itself

    def tearDown(self):
        self.window.close()
        for path in [self.temp_db, self.temp_db + "-shm", self.temp_db + "-wal", self.step_path]:
            if os.path.exists(path):
                os.remove(path)

    def _run_export(self, path):
        """Drive the action, returning the error dialogs it raised."""
        errors = []

        def record(kind):
            def handler(*args, **kwargs):
                errors.append(
                    (kind, args[1] if len(args) > 1 else "", args[2] if len(args) > 2 else "")
                )
                return None

            return handler

        with mock.patch(
            "openlens.__main__.QFileDialog.getSaveFileName", return_value=(path, "")
        ), mock.patch(
            "openlens.__main__.QMessageBox.critical", side_effect=record("critical")
        ), mock.patch(
            "openlens.__main__.QMessageBox.warning", side_effect=record("warning")
        ):
            self.window._on_export_step()

        return errors

    def test_export_step_writes_a_step_file(self):
        """Exporting must write a non-empty Part 21 file to the chosen path."""
        errors = self._run_export(self.step_path)

        self.assertEqual(errors, [], f"the action reported an error dialog: {errors}")
        self.assertTrue(os.path.exists(self.step_path), "no .step file was written")

        with open(self.step_path) as handle:
            content = handle.read()
        self.assertGreater(len(content), 0, "the .step file is empty")
        self.assertIn("ISO-10303-21", content)

    def test_export_step_status_reports_success(self):
        """A successful export must set a success status, not an error one."""
        self._run_export(self.step_path)
        status = self.window.statusBar().currentMessage()
        self.assertIn("STEP", status)

    def test_exporter_name_resolves_in_the_gui_module(self):
        """The GUI module must expose the class name it imports.

        This is the exact defect: the call site used a name that is not bound in
        the module, and no import or attribute check caught it.
        """
        import openlens.__main__ as openlens

        self.assertTrue(hasattr(openlens, "StepExporter"))
        self.assertFalse(hasattr(openlens, "STEPExporter"))


if __name__ == "__main__":
    unittest.main()
