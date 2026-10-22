#!/usr/bin/env python3
"""
A failed library load must not delete the stored library.

``LensStorage.load_lenses()`` caught every exception and returned an empty
list, so a read error was indistinguishable from an empty library: the window
adopted its default lens, and the next explicit save reconciled the database
against that one-item snapshot - deleting every row that had failed to load.
"""

import os
import sys
import tempfile
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication

    PYSIDE_AVAILABLE = True
    _PYSIDE_ERROR = ""
except ImportError as _e:  # pragma: no cover - environment guard
    PYSIDE_AVAILABLE = False
    _PYSIDE_ERROR = str(_e)

if PYSIDE_AVAILABLE:
    app = QApplication.instance() or QApplication(sys.argv)


@unittest.skipUnless(PYSIDE_AVAILABLE, f"PySide6 not available: {_PYSIDE_ERROR}")
class TestFailedLoadKeepsTheLibrary(unittest.TestCase):
    """A read failure must be reported and must not delete anything."""

    def setUp(self):
        from openlens.__main__ import OpenLensWindow
        from openlens.database import DatabaseManager
        from openlens.lens import Lens
        from openlens.optical_system import OpticalSystem

        self._tmpdir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self._tmpdir.name, "test.db")
        self._env = mock.patch.dict(
            os.environ,
            {"OPENLENS_DATA_DIR": self._tmpdir.name, "OPENLENS_DB_PATH": self.db_path},
        )
        self._env.start()

        # Seed the library the window will later read.
        db = DatabaseManager(self.db_path)
        lens = Lens(
            name="Lens A",
            radius_of_curvature_1=50.0,
            radius_of_curvature_2=-50.0,
            thickness=5.0,
            diameter=25.0,
            material="BK7",
        )
        other = Lens(
            name="Lens B",
            radius_of_curvature_1=60.0,
            radius_of_curvature_2=-60.0,
            thickness=5.0,
            diameter=25.0,
            material="BK7",
        )
        assembly = OpticalSystem(name="Asm")
        assembly.add_lens(lens)
        db.save_library(
            [lens.to_dict(), other.to_dict(), assembly.to_dict()],
            library_lens_ids=[lens.id, other.id],
            demote=True,
        )
        self.seeded = sorted(row["name"] for row in db.load_all())

        self.window = OpenLensWindow()
        self.window.show()
        QApplication.processEvents()

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        QApplication.processEvents()
        self._env.stop()
        self._tmpdir.cleanup()

    def _rows(self):
        from openlens.database import DatabaseManager

        db = DatabaseManager(self.db_path)
        return sorted(row["name"] for row in db.load_all())

    def _break_the_read(self):
        """Make the next read of the library fail."""
        from openlens.database import DatabaseManager

        original = DatabaseManager.load_all

        def _boom(self):
            raise RuntimeError("simulated database read failure")

        return mock.patch.object(DatabaseManager, "load_all", _boom), original

    def test_a_read_failure_is_reported(self):
        """The window must say the load failed instead of showing an empty library."""
        patcher, _ = self._break_the_read()
        with patcher:
            self.window._load_from_database()
        QApplication.processEvents()

        self.assertTrue(
            self.window._problem_boxes,
            "a failed load showed no error dialog",
        )

    def test_a_failed_load_does_not_replace_the_library(self):
        """The in-memory library must survive a failed load."""
        before = list(self.window._lenses)
        self.assertTrue(before, "the window started with an empty library")

        patcher, _ = self._break_the_read()
        with patcher:
            self.window._load_from_database()
        QApplication.processEvents()

        self.assertEqual(
            sorted(lens.name for lens in self.window._lenses),
            sorted(lens.name for lens in before),
            "a failed load replaced the in-memory library",
        )

    def test_a_save_after_a_failed_load_keeps_the_rows(self):
        """The rows that failed to load must still be there afterwards."""
        patcher, _ = self._break_the_read()
        with patcher:
            self.window._load_from_database()
        QApplication.processEvents()

        # The explicit save path: Ctrl+S reconciles the database against the
        # in-memory snapshot.
        self.window._save_to_database(reconcile=True)

        self.assertEqual(
            self._rows(),
            self.seeded,
            "the save after a failed load deleted the stored library",
        )


if __name__ == "__main__":
    unittest.main()
