#!/usr/bin/env python3
"""
Persistence reconciliation (review items 1.4 / 2.13).

Guards the whole delete/rename/drift lifecycle:
- deleted items stay deleted across sessions (resurrection regression)
- renames persist (INSERT OR REPLACE on stable id)
- full-snapshot saves reconcile away rows written by other instances
- partial-list saves (CLI) never wipe assemblies they did not load
"""

import os
import sys
import tempfile
import unittest

if os.environ.get("DISPLAY", "") == "" and sys.platform.startswith("linux"):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication

    PYSIDE_AVAILABLE = True
except ImportError as _e:
    QApplication = None  # type: ignore
    PYSIDE_AVAILABLE = False
    _PYSIDE_ERROR = _e

from src.lens import Lens
from src.optical_system import OpticalSystem
from src.gui.storage import LensStorage

if not PYSIDE_AVAILABLE:

    class TestReconciliation(unittest.TestCase):
        @unittest.skip(f"PySide6 not available: {_PYSIDE_ERROR}")
        def test_skip(self):
            pass

else:

    class _Harness:
        """Owns a temp database and a window bound to it."""

        def __init__(self):
            fd, self.db_path = tempfile.mkstemp(suffix=".db")
            os.close(fd)
            self.app = QApplication.instance() or QApplication(sys.argv)
            import openlens

            self.openlens = openlens
            self.window = openlens.OpenLensWindow()
            self.window._db_path = self.db_path
            from src.gui.storage import LensStorage

            self.storage = LensStorage(self.db_path)
            self.window._storage = self.storage
            # Detach from real user data
            self.window._lenses = []
            self.window._assemblies = []

        def close(self):
            self.window.close()
            for suffix in ("", "-shm", "-wal"):
                p = self.db_path + suffix
                if os.path.exists(p):
                    os.unlink(p)

        def stored_names(self):
            return sorted(o.name for o in self.storage.load_lenses() if hasattr(o, "name"))

    class TestReconciliation(unittest.TestCase):
        def setUp(self):
            self.h = _Harness()
            self.addCleanup(self.h.close)

        def test_deleted_item_stays_deleted_across_sessions(self):
            """Regression: deleting then relaunching must not resurrect."""
            w = self.h.window
            w._on_new_lens()
            w._on_new_lens()
            w._save_to_database()  # ensure both rows are persisted
            w._current_lens = w._lenses[0]
            w._on_delete_lens()

            fresh = LensStorage(self.h.db_path)
            names = sorted(o.name for o in fresh.load_lenses())
            self.assertEqual(names, ["Lens 2"])

        def test_rename_persists_on_stable_id(self):
            """Same id, new name: one row, updated name"""
            w = self.h.window
            w._on_new_lens()
            lens = w._lenses[0]
            lens.name = "Renamed"
            w._save_to_database()

            fresh = LensStorage(self.h.db_path)
            lenses = list(fresh.load_lenses())
            self.assertEqual(len(lenses), 1)
            self.assertEqual(lenses[0].name, "Renamed")

        def test_reconcile_removes_rows_from_other_instances(self):
            """A row written by a second instance is reconciled away by a
            full-snapshot save from this window."""
            w = self.h.window
            w._on_new_lens()

            # Simulate another instance adding its own item behind our back
            rogue = Lens(name="Rogue")
            self.h.storage.save_lenses([rogue], show_status=False)
            names = self.h.stored_names()
            self.assertIn("Rogue", names)

            # Full snapshot from our window (reconcile=True via GUI path)
            w._save_to_database()
            names = self.h.stored_names()
            self.assertNotIn("Rogue", names)
            self.assertIn("Lens 1", names)

        def test_partial_save_without_reconcile_keeps_assemblies(self):
            """CLI-style lens-only list with reconcile=False must not wipe
            assemblies living only in the database (CLI safety contract)."""
            storage = self.h.storage
            asm = OpticalSystem(name="Precious")
            storage.save_lenses([asm], show_status=False)

            lens_only = [Lens(name="JustALens")]
            storage.save_lenses(lens_only, show_status=False, reconcile=False)

            kinds = [
                ("assembly" if hasattr(d, "elements") else "lens") for d in storage.load_lenses()
            ]
            self.assertIn("assembly", kinds)


if __name__ == "__main__":
    unittest.main()
