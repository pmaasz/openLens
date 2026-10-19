"""#475: one ``save_lenses`` call must be one transaction.

The storage layer saved each item through its own ``save_lens`` /
``save_assembly`` call, each of which committed. A failure on item three left
items one and two in the library - a partially saved snapshot that looked
like a successful save.
"""

import os
import tempfile
import unittest

from openlens.database import DatabaseManager
from openlens.gui.storage import LensStorage
from openlens.lens import Lens


def _lens(name):
    return Lens(
        name=name,
        radius_of_curvature_1=50.0,
        radius_of_curvature_2=-50.0,
        thickness=5.0,
        diameter=25.0,
        refractive_index=1.5168,
    )


class TestLibrarySaveIsAtomic(unittest.TestCase):
    def setUp(self):
        handle, self.path = tempfile.mkstemp(suffix=".db")
        os.close(handle)
        os.unlink(self.path)
        self.addCleanup(self._remove_database)
        self.db = DatabaseManager(self.path)
        self.storage = LensStorage(self.path)

    def _remove_database(self):
        for suffix in ("", "-shm", "-wal"):
            try:
                os.unlink(self.path + suffix)
            except FileNotFoundError:
                pass

    def test_a_failure_mid_save_leaves_no_rows(self):
        first = _lens("L1")
        second = _lens("L2")
        # float("oops") raises inside the row write, after the first row was
        # already INSERTed in the caller's transaction.
        second.bevel_1 = "oops"

        saved = self.storage.save_lenses([first, second], show_status=False, library_snapshot=True)

        self.assertFalse(saved)
        self.assertEqual(self.db.load_all(), [])

    def test_a_successful_save_still_writes_every_item(self):
        saved = self.storage.save_lenses(
            [_lens("L1"), _lens("L2")], show_status=False, library_snapshot=True
        )

        self.assertTrue(saved)
        self.assertEqual(sorted(item["name"] for item in self.db.load_all()), ["L1", "L2"])


if __name__ == "__main__":
    unittest.main()
