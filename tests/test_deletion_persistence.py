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

    class TestAssemblyDeletionRepointsEditor(unittest.TestCase):
        """Deleting the current assembly must re-point the editor.

        The lens branch calls _set_current_item()/_update_all_tabs() after a
        delete; the assembly branch did neither. The Assembly Editor kept
        displaying the deleted assembly and self._optical_system still pointed
        at it, so the next edit there fired _on_assembly_changed ->
        _save_to_database and RE-INSERTED the row just deleted (under a new id,
        so it appeared twice).
        """

        def setUp(self):
            self.h = _Harness()
            self.addCleanup(self.h.close)
            self.w = self.h.window

        def _two_assemblies(self):
            w = self.w
            for name in ("Assembly 1", "Second"):
                system = OpticalSystem(name=name)
                system.add_lens(
                    Lens(
                        name=f"{name} lens",
                        radius_of_curvature_1=50.0,
                        radius_of_curvature_2=-50.0,
                        thickness=5.0,
                        diameter=20.0,
                    )
                )
                w._assemblies.append(system)
                w._save_to_database()
            w._set_current_item(w._assemblies[0], is_assembly=True)

        def test_editor_is_repointed_after_delete(self):
            self._two_assemblies()
            self.w._on_delete_lens()

            self.assertEqual(self.w._current_assembly.name, "Second")
            # The Assembly Editor's own copy is what _save_to_database reads.
            self.assertIs(
                self.w._assembly_tab_widget._optical_system,
                self.w._current_assembly,
                "assembly editor still bound to the deleted assembly",
            )
            self.assertIs(self.w._optical_system, self.w._current_assembly, "window is stale")

        def test_deleted_assembly_is_not_reinserted_by_a_later_edit(self):
            """The user-visible failure: the row comes back, duplicated."""
            self._two_assemblies()
            self.w._on_delete_lens()

            # Simulate the user editing the Assembly Editor tab.
            self.w._assembly_tab_widget._optical_system.name = "Second (edited)"
            self.w._assembly_tab_widget._on_assembly_changed()
            self.w._save_to_database()

            fresh = LensStorage(self.h.db_path)
            names = sorted(o.name for o in fresh.load_lenses() if hasattr(o, "name"))
            self.assertNotIn("Assembly 1", names)
            self.assertEqual(names.count("Second (edited)"), 1)

        def test_deleting_last_assembly_clears_the_editor(self):
            w = self.w
            system = OpticalSystem(name="Only One")
            system.add_lens(
                Lens(
                    name="Only lens",
                    radius_of_curvature_1=50.0,
                    radius_of_curvature_2=-50.0,
                    thickness=5.0,
                    diameter=20.0,
                )
            )
            w._assemblies.append(system)
            w._save_to_database()
            w._set_current_item(system, is_assembly=True)

            w._on_delete_lens()

            self.assertIsNone(w._current_assembly)
            self.assertIsNone(w._optical_system)
            self.assertIsNone(w._assembly_tab_widget._optical_system)

    class TestLensDeletionRepointsEditor(unittest.TestCase):
        """The lens branch already did this; keep it pinned."""

        def setUp(self):
            self.h = _Harness()
            self.addCleanup(self.h.close)
            self.w = self.h.window

        def test_deleting_current_lens_selects_another(self):
            w = self.w
            w._on_new_lens()
            w._on_new_lens()
            w._save_to_database()
            w._current_lens = w._lenses[0]
            w._on_delete_lens()

            self.assertIsNotNone(w._current_lens)
            remaining = [lens.name for lens in w._lenses]
            self.assertEqual(len(remaining), 1)
            self.assertIn(w._current_lens.name, remaining)


if __name__ == "__main__":
    unittest.main()
