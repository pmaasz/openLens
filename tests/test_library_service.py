#!/usr/bin/env python3
"""Headless tests for the Qt-free library persistence service (#583).

The window keeps selection, editor synchronization, tolerance state and the
delete re-pointing. The service only sequences storage operations, partitions
the loaded library and classifies failures. These tests need no QApplication.
"""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from openlens.database import LensInUseError
from openlens.gui.services.library_service import (
    LibraryDelete,
    LibraryLoad,
    LibrarySave,
    LibraryService,
)
from openlens.gui.storage import LensStorage
from openlens.lens import Lens
from openlens.optical_system import create_doublet

REPO_ROOT = Path(__file__).resolve().parent.parent


class FakeStorage:
    """Records every call and returns canned results."""

    def __init__(self, items=None, save_result=True, last_error=None):
        self.items = list(items or [])
        self.save_result = save_result
        self.last_error = last_error
        self.load_calls = 0
        self.saved = []
        self.deleted = []
        self.delete_error = None

    def load_lenses(self):
        self.load_calls += 1
        return list(self.items)

    def save_lenses(self, items, show_status=True, reconcile=False, library_snapshot=False):
        self.saved.append(
            {
                "items": list(items),
                "show_status": show_status,
                "reconcile": reconcile,
                "library_snapshot": library_snapshot,
            }
        )
        return self.save_result

    def delete_item(self, item_id):
        if self.delete_error is not None:
            raise self.delete_error
        self.deleted.append(item_id)
        return True


class TestLibraryService(unittest.TestCase):
    def test_load_partitions_lenses_and_assemblies(self):
        lens = Lens(name="Single")
        system = create_doublet(focal_length=100.0, diameter=40.0)
        storage = FakeStorage([lens, system])

        result = LibraryService(lambda: storage).load()

        self.assertIsInstance(result, LibraryLoad)
        self.assertTrue(result.ok)
        self.assertEqual(result.lenses, [lens])
        self.assertEqual(result.assemblies, [system])
        self.assertIsNone(result.error)

    def test_load_resolves_the_storage_provider_every_call(self):
        first = FakeStorage([Lens(name="First")])
        second = FakeStorage([Lens(name="Second")])
        current = {"storage": first}
        service = LibraryService(lambda: current["storage"])

        one = service.load()
        # The tests replace window._storage after construction, so the service
        # must not capture the first storage object.
        current["storage"] = second
        two = service.load()

        self.assertEqual(one.lenses[0].name, "First")
        self.assertEqual(two.lenses[0].name, "Second")
        self.assertEqual(first.load_calls, 1)
        self.assertEqual(second.load_calls, 1)

    def test_load_exception_returns_a_failure_instead_of_raising(self):
        class BrokenStorage:
            last_error = None

            def load_lenses(self):
                raise RuntimeError("database is locked")

        result = LibraryService(lambda: BrokenStorage()).load()

        self.assertFalse(result.ok)
        self.assertEqual(result.lenses, [])
        self.assertEqual(result.assemblies, [])
        self.assertIn("database is locked", result.error)
        self.assertIsInstance(result.cause, RuntimeError)

    def test_save_deduplicates_by_id_and_passes_the_snapshot_flags(self):
        first = Lens(name="First")
        second = Lens(name="Second")
        second.id = first.id
        storage = FakeStorage()

        result = LibraryService(lambda: storage).save([first, second], reconcile=False)

        self.assertIsInstance(result, LibrarySave)
        self.assertTrue(result.ok)
        self.assertEqual(result.count, 1)
        call = storage.saved[-1]
        self.assertEqual([item.name for item in call["items"]], ["Second"])
        self.assertFalse(call["reconcile"])
        self.assertTrue(call["library_snapshot"])
        self.assertTrue(call["show_status"])

    def test_save_defaults_to_reconcile(self):
        storage = FakeStorage()

        LibraryService(lambda: storage).save([])

        self.assertTrue(storage.saved[-1]["reconcile"])

    def test_rejected_save_surfaces_storage_last_error(self):
        storage = FakeStorage(save_result=False, last_error="disk is full")

        result = LibraryService(lambda: storage).save([Lens()])

        self.assertFalse(result.ok)
        self.assertEqual(result.error, "disk is full")

    def test_rejected_save_without_last_error_uses_the_existing_message(self):
        storage = FakeStorage(save_result=False)

        result = LibraryService(lambda: storage).save([Lens()])

        self.assertEqual(result.error, "the database rejected the save")

    def test_save_exception_returns_a_failure_instead_of_raising(self):
        class BrokenStorage:
            last_error = None

            def save_lenses(self, items, **kwargs):
                raise OSError("read-only file system")

        result = LibraryService(lambda: BrokenStorage()).save([Lens()])

        self.assertFalse(result.ok)
        self.assertIn("read-only file system", result.error)
        self.assertIsInstance(result.cause, OSError)

    def test_delete_success(self):
        storage = FakeStorage()

        result = LibraryService(lambda: storage).delete("lens-id")

        self.assertIsInstance(result, LibraryDelete)
        self.assertTrue(result.ok)
        self.assertFalse(result.blocked)
        self.assertEqual(storage.deleted, ["lens-id"])

    def test_delete_blocked_by_an_assembly_is_classified(self):
        storage = FakeStorage()
        storage.delete_error = LensInUseError("lens-id", [(7, "Doublet")])

        result = LibraryService(lambda: storage).delete("lens-id")

        self.assertFalse(result.ok)
        self.assertTrue(result.blocked)
        self.assertIsInstance(result.cause, LensInUseError)
        self.assertIn("still used", result.error)

    def test_delete_ordinary_failure_is_not_classified_as_blocked(self):
        storage = FakeStorage()
        storage.delete_error = ValueError("row is gone")

        result = LibraryService(lambda: storage).delete("lens-id")

        self.assertFalse(result.ok)
        self.assertFalse(result.blocked)
        self.assertIn("row is gone", result.error)

    def test_duplicate_lens_copies_fields_with_a_fresh_id(self):
        original = Lens(
            name="Original",
            radius_of_curvature_1=80.0,
            thickness=4.0,
            material="SF11",
        )

        duplicate = LibraryService.duplicate_lens(original)

        self.assertNotEqual(duplicate.id, original.id)
        self.assertEqual(duplicate.name, "Original (copy)")
        self.assertEqual(duplicate.radius_of_curvature_1, 80.0)
        self.assertEqual(duplicate.thickness, 4.0)
        self.assertEqual(duplicate.material, "SF11")
        self.assertEqual(original.name, "Original")

    def test_real_database_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "library.db")
            lens = Lens(name="DB Lens")
            system = create_doublet(focal_length=100.0, diameter=40.0)

            saver = LibraryService(lambda: LensStorage(path))
            saved = saver.save([lens, system])
            self.assertTrue(saved.ok, saved.error)

            loaded = LibraryService(lambda: LensStorage(path)).load()

        self.assertTrue(loaded.ok, loaded.error)
        self.assertEqual(len(loaded.lenses), 1)
        self.assertEqual(loaded.lenses[0].name, "DB Lens")
        self.assertEqual(len(loaded.assemblies), 1)
        self.assertEqual(loaded.assemblies[0].name, system.name)

    def test_the_service_runs_without_pyside6(self):
        code = """
import sys


class _BlockPySide6:
    def find_spec(self, name, path=None, target=None):
        if name == "PySide6" or name.startswith("PySide6."):
            raise ImportError("PySide6 blocked for the headless service test")
        return None


sys.meta_path.insert(0, _BlockPySide6())

from openlens.gui.services.library_service import LibraryService


class Storage:
    last_error = None

    def load_lenses(self):
        return []

    def save_lenses(self, items, **kwargs):
        return True

    def delete_item(self, item_id):
        return True


service = LibraryService(lambda: Storage())
assert service.load().ok
assert service.save([]).ok
assert service.delete("id").ok
assert "PySide6" not in sys.modules, sorted(
    name for name in sys.modules if name.startswith("PySide6")
)
"""
        completed = subprocess.run(
            [sys.executable, "-c", code],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)


if __name__ == "__main__":
    unittest.main()
