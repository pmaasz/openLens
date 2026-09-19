"""Regression: edited lenses must survive close/reopen.

Covers the deferred-load adoption: reopening must select the saved lens
instead of stranding the user on a fresh blank default (whose unchanged
values looked like "edits were not persisted").
"""

import os
import sys
import tempfile
import unittest

# Headless environments (CI): fall back to Qt's offscreen platform before
# any QApplication is created. A real DISPLAY always wins.
if os.environ.get("DISPLAY", "") == "" and sys.platform.startswith("linux"):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication

    from openlens import OpenLensWindow

    PYSIDE_AVAILABLE = True
    _PYSIDE_ERROR = None
except ImportError as _e:
    QApplication = None  # type: ignore
    OpenLensWindow = None  # type: ignore
    PYSIDE_AVAILABLE = False
    _PYSIDE_ERROR = _e

from src.lens import Lens

if not PYSIDE_AVAILABLE:

    class TestStartupPersistence(unittest.TestCase):
        @unittest.skip(f"PySide6 not available: {_PYSIDE_ERROR}")
        def test_skip(self):
            pass

else:
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 not available")
class TestReopenSelectsSavedLens(unittest.TestCase):
    """Save-edit-close-reopen must show the edited values."""

    def setUp(self):
        from src.gui.storage import LensStorage

        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
        self.storage = LensStorage(self.temp_db)

    def tearDown(self):
        for window in getattr(self, "_windows", []):
            window.close()
        if os.path.exists(self.temp_db):
            os.remove(self.temp_db)
        for ext in ["-shm", "-wal"]:
            if os.path.exists(self.temp_db + ext):
                os.remove(self.temp_db + ext)

    def _fresh_window(self):
        window = OpenLensWindow()
        window._storage = self.storage
        window._db_path = self.temp_db
        window._lenses = []
        window._assemblies = []
        window._current_lens = None
        window._current_assembly = None
        self._windows = getattr(self, "_windows", []) + [window]
        return window

    def test_reopen_selects_saved_lens(self):
        """Edited default lens must be current (and shown) after reopen."""
        session1 = self._fresh_window()
        session1._load_default_lens()
        session1._current_lens.radius_of_curvature_1 = 66.0
        session1._save_to_database()

        session2 = self._fresh_window()
        session2._load_default_lens()  # what _handle_startup does by default
        session2._load_from_database()  # what the deferred load does

        self.assertAlmostEqual(session2._current_lens.radius_of_curvature_1, 66.0)
        self.assertEqual(len(session2._lenses), 1)
        self.assertIs(session2._current_lens, session2._lenses[0])
        self.assertAlmostEqual(session2._lens_editor._r1_input.value(), 66.0)

    def test_explicit_new_lens_survives_reload(self):
        """A deliberately created lens must not be swapped away on reload."""
        session1 = self._fresh_window()
        session1._load_default_lens()
        session1._current_lens.radius_of_curvature_1 = 66.0
        session1._save_to_database()

        session2 = self._fresh_window()
        session2._load_from_database()
        session2._on_new_lens()
        new_id = session2._current_lens.id
        session2._load_from_database()  # e.g. File > Open reload

        self.assertEqual(session2._current_lens.id, new_id)
        self.assertEqual(len(session2._lenses), 2)


if __name__ == "__main__":
    unittest.main()
