"""#621: File > Save As must export the active assembly, not do nothing.

The action was always enabled, but ``_on_save_as()`` returned immediately when
``_current_lens`` was None - exactly the state while an assembly is selected.
No dialog, no file, no status message.
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

# Headless environments (CI): fall back to Qt's offscreen platform before
# any QApplication is created. A real DISPLAY always wins.
if os.environ.get("DISPLAY", "") == "" and sys.platform.startswith("linux"):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication

    from openlens.__main__ import OpenLensWindow
    from openlens.optical_system import OpticalSystem, create_doublet

    PYSIDE_AVAILABLE = True
    _PYSIDE_ERROR = None
except ImportError as _e:  # pragma: no cover - environment guard
    QApplication = None  # type: ignore
    OpenLensWindow = None  # type: ignore
    OpticalSystem = None  # type: ignore
    create_doublet = None  # type: ignore
    PYSIDE_AVAILABLE = False
    _PYSIDE_ERROR = _e

if PYSIDE_AVAILABLE:
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)


@unittest.skipUnless(PYSIDE_AVAILABLE, f"PySide6 not available: {_PYSIDE_ERROR}")
class TestSaveAsAssembly(unittest.TestCase):
    """The enabled Ctrl+Shift+S must do something for an assembly."""

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

        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        QApplication.processEvents()
        for suffix in ("", "-shm", "-wal"):
            path = self.temp_db + suffix
            if os.path.exists(path):
                os.remove(path)

    def _save_as(self, target, path):
        """Drive the action with a patched dialog; return the dialog calls."""
        calls = []

        def fake_dialog(*args, **kwargs):
            calls.append((args, kwargs))
            return (path, "")

        with mock.patch("openlens.__main__.QFileDialog.getSaveFileName", side_effect=fake_dialog):
            self.window._on_save_as()

        return calls

    def test_an_active_assembly_is_exported_to_json(self):
        system = create_doublet(focal_length=100.0, diameter=40.0)
        self.window._current_assembly = system
        self.window._current_lens = None
        path = os.path.join(self.tmp.name, "assembly.json")

        calls = self._save_as(system, path)

        self.assertEqual(len(calls), 1, "Save As never opened a dialog")
        self.assertTrue(os.path.exists(path), "no assembly JSON was written")
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        self.assertEqual(data["type"], "OpticalSystem")
        self.assertEqual(data["name"], system.name)
        self.assertEqual(len(data["elements"]), len(system.elements))
        self.assertIn("Assembly", calls[0][0][1], "the dialog title should say Assembly")

    def test_the_exported_assembly_loads_back(self):
        system = create_doublet(focal_length=100.0, diameter=40.0)
        self.window._current_assembly = system
        self.window._current_lens = None
        path = os.path.join(self.tmp.name, "assembly.json")

        self._save_as(system, path)
        loaded = OpticalSystem.load(path)

        self.assertIsNotNone(loaded)
        self.assertEqual(len(loaded.elements), len(system.elements))

    def test_an_active_lens_still_saves_its_dict(self):
        from openlens.lens import Lens

        lens = Lens(
            name="Single",
            radius_of_curvature_1=50.0,
            radius_of_curvature_2=-50.0,
            thickness=5.0,
            diameter=25.0,
        )
        self.window._current_lens = lens
        self.window._current_assembly = None
        path = os.path.join(self.tmp.name, "lens.json")

        calls = self._save_as(lens, path)

        self.assertEqual(len(calls), 1)
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        self.assertEqual(data["name"], "Single")
        self.assertEqual(data["radius_of_curvature_1"], 50.0)
        self.assertIn("Lens", calls[0][0][1])

    def test_nothing_active_reports_a_status_instead_of_silence(self):
        self.window._current_lens = None
        self.window._current_assembly = None

        calls = self._save_as(None, os.path.join(self.tmp.name, "unused.json"))

        self.assertEqual(calls, [], "a dialog was opened with nothing to save")
        self.assertEqual(self.window.statusBar().currentMessage(), "Nothing to save")

    def test_a_cancelled_dialog_writes_nothing(self):
        system = create_doublet(focal_length=100.0, diameter=40.0)
        self.window._current_assembly = system

        with mock.patch("openlens.__main__.QFileDialog.getSaveFileName", return_value=("", "")):
            self.window._on_save_as()

        self.assertEqual(os.listdir(self.tmp.name), [])


if __name__ == "__main__":
    unittest.main()
