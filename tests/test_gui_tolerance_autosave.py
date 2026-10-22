#!/usr/bin/env python3
"""
A tolerance set must be saved like every other edit.

The tolerancing tab mutates the window's operand list and refreshes its
table, but never told the window about it: the tolerance set was stamped
into the target's metadata by the save path, and the save path only ran for
a lens edit. A tolerance set built after the last lens edit was therefore
lost when the window closed.
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
class TestToleranceSetIsSaved(unittest.TestCase):
    """The tolerance set must reach the database."""

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

    def _stored_tolerances(self, lens_id):
        """The tolerance set the database holds for this lens."""
        from openlens.database import DatabaseManager

        db = DatabaseManager(self.window._db_path)
        for row in db.load_all():
            if row.get("id") == lens_id:
                return (row.get("metadata") or {}).get("tolerances")
        return None

    def test_the_default_set_reaches_the_database(self):
        """Adding the default tolerance set must schedule a save."""
        tab = self.window._tol_tab
        lens = self.window._current_lens
        self.assertIsNotNone(lens)

        tab._on_add_default_tolerances()
        self.assertTrue(self.window._tol_operands, "the default set was not added")

        self.assertTrue(
            _spin_until(lambda: self._stored_tolerances(lens.id)),
            "the tolerance set never reached the database",
        )
        stored = self._stored_tolerances(lens.id)
        self.assertEqual(len(stored), len(self.window._tol_operands))

    def test_removing_an_operand_reaches_the_database(self):
        """A removal must be saved too, not only an addition."""
        tab = self.window._tol_tab
        lens = self.window._current_lens

        tab._on_add_default_tolerances()
        self.assertTrue(
            _spin_until(lambda: self._stored_tolerances(lens.id)),
            "the tolerance set never reached the database",
        )
        count = len(self.window._tol_operands)

        tab._on_remove_tolerance()
        self.assertEqual(len(self.window._tol_operands), count - 1)

        self.assertTrue(
            _spin_until(lambda: len(self._stored_tolerances(lens.id) or []) == count - 1),
            f"the removal never reached the database "
            f"(stored: {self._stored_tolerances(lens.id)})",
        )


if __name__ == "__main__":
    unittest.main()
