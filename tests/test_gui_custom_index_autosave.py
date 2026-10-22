#!/usr/bin/env python3
"""
A hand-typed refractive index must be saved like every other edit.

The editor emits ``lens_updated`` for the custom-index edit, but the window
only listens to ``lens_modified`` - and ``lens_updated`` has no connections
anywhere in the repository. The value therefore reached the in-memory model
only, and was lost when the window closed unless the user happened to edit
something else afterwards.
"""

import os
import sys
import tempfile
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtCore import QEventLoop, QTimer
    from PySide6.QtWidgets import QApplication

    PYSIDE_AVAILABLE = True
    _PYSIDE_ERROR = ""
except ImportError as _e:  # pragma: no cover - environment guard
    PYSIDE_AVAILABLE = False
    _PYSIDE_ERROR = str(_e)

if PYSIDE_AVAILABLE:
    app = QApplication.instance() or QApplication(sys.argv)


def _spin_until(predicate, timeout_ms=8000):
    """Run the event loop until ``predicate()`` holds or the time runs out."""
    loop = QEventLoop()
    steps = {"n": 0}
    timer = QTimer()

    def _tick():
        steps["n"] += 1
        if predicate() or steps["n"] * 10 >= timeout_ms:
            loop.quit()

    timer.timeout.connect(_tick)
    timer.start(10)
    loop.exec()
    timer.stop()
    return predicate()


@unittest.skipUnless(PYSIDE_AVAILABLE, f"PySide6 not available: {_PYSIDE_ERROR}")
class TestCustomIndexIsSaved(unittest.TestCase):
    """The custom refractive index must reach the database."""

    def setUp(self):
        from openlens.__main__ import OpenLensWindow

        self._tmpdir = tempfile.TemporaryDirectory()
        self._env = mock.patch.dict(
            os.environ,
            {
                "OPENLENS_DATA_DIR": self._tmpdir.name,
                "OPENLENS_DB_PATH": os.path.join(self._tmpdir.name, "test.db"),
            },
        )
        self._env.start()
        self.window = OpenLensWindow()
        self.window.show()
        QApplication.processEvents()

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        QApplication.processEvents()
        self._env.stop()
        self._tmpdir.cleanup()

    def _stored_index(self, lens_id):
        """The refractive index the database holds for this lens."""
        from openlens.database import DatabaseManager

        db = DatabaseManager(self.window._db_path)
        for row in db.load_all():
            if row.get("id") == lens_id:
                return row.get("refractive_index")
        return None

    def test_the_index_edit_emits_the_save_triggering_signal(self):
        """``lens_modified`` is the signal the window connects to the autosave."""
        editor = self.window._lens_editor
        editor._on_material_changed("Custom")

        seen = []
        editor.lens_modified.connect(seen.append)

        editor._n_input.setValue(1.75)

        self.assertTrue(seen, "a custom index edit emitted no lens_modified signal")
        self.assertEqual(editor._lens.refractive_index, 1.75)

    def test_the_index_edit_reaches_the_database(self):
        """The value must be in SQLite after the debounce."""
        editor = self.window._lens_editor
        lens = editor._lens
        editor._on_material_changed("Custom")

        # Let the material edit's own save land first, so the index edit
        # cannot ride on a pending debounce from it.
        self.assertTrue(
            _spin_until(lambda: not self.window._edit_timer.isActive()),
            "the material edit never reached the database",
        )

        editor._n_input.setValue(1.75)

        # The window debounces the save; wait for it to land.
        self.assertTrue(
            _spin_until(lambda: self._stored_index(lens.id) == 1.75),
            f"the custom index never reached the database "
            f"(stored: {self._stored_index(lens.id)})",
        )


if __name__ == "__main__":
    unittest.main()
