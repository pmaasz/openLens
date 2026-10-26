#!/usr/bin/env python3
"""A manual detector plane must be saved like any other model edit.

The simulation tab writes ``image_plane_x_mm`` onto the active lens or
assembly, but it never scheduled the window's debounced save. The plane was
therefore used by the current trace and silently lost when the window closed.
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
    """Run the event loop until ``predicate()`` holds or time runs out."""
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
class TestFocalPlaneIsSaved(unittest.TestCase):
    """Changing the plane must reach SQLite before the window closes."""

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

    def _stored_plane(self, lens_id):
        from openlens.gui.storage import LensStorage

        for item in LensStorage(self.window._db_path).load_lenses():
            if item.id == lens_id:
                return item.image_plane_x_mm
        return None

    def test_a_manual_plane_reaches_the_database(self):
        """Setting the spin box must schedule the debounced save."""
        lens = self.window._current_lens
        self.assertIsNotNone(lens)
        self.window._save_to_database(reconcile=False)

        tab = self.window._sim_tab
        tab._sim_auto_focal_plane.setChecked(False)
        tab._sim_focal_plane_x.setValue(123.0)

        self.assertTrue(
            _spin_until(lambda: self._stored_plane(lens.id) == 123.0),
            "the focal plane never reached the database",
        )


if __name__ == "__main__":
    unittest.main()
