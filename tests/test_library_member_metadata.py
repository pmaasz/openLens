#!/usr/bin/env python3
"""
A library lens that is also an assembly member must keep its metadata.

The lens row's blob was built differently by the two writers: a standalone
lens folded the model's metadata into the blob's top level, an assembly
element kept it nested one level deeper. The reader subtracts the model's own
keys from the blob, and ``metadata`` is one of them - so the nested copy was
dropped and the user's settings (the tolerance set) were lost on every save.
"""

import os
import tempfile
import unittest

from openlens.database import DatabaseManager
from openlens.lens import Lens
from openlens.optical_system import OpticalSystem


class TestLibraryMemberKeepsItsMetadata(unittest.TestCase):
    """The tolerance set of a library lens must survive a save."""

    def setUp(self):
        handle, self.path = tempfile.mkstemp(suffix=".db")
        os.close(handle)
        os.unlink(self.path)
        self.addCleanup(lambda: os.path.exists(self.path) and os.unlink(self.path))
        self.db = DatabaseManager(self.path)

        self.lens = Lens(
            name="Tol",
            radius_of_curvature_1=50.0,
            radius_of_curvature_2=-50.0,
            thickness=5.0,
            diameter=25.0,
            material="N-BK7",
            refractive_index=1.5168,
        )
        self.lens.metadata = {"tolerances": {"radius_1": {"min": 49.0, "max": 51.0}}}

        self.assembly = OpticalSystem(name="Asm")
        self.assembly.add_lens(self.lens, air_gap_before=0.0)

    def _reloaded_lens(self):
        for row in self.db.load_all():
            if row.get("name") == "Tol":
                return Lens.from_dict(row)
        return None

    def test_the_metadata_survives_the_save(self):
        """The lens is a library member and an assembly element at once"""
        self.db.save_library(
            [self.lens.to_dict(), self.assembly.to_dict()],
            library_lens_ids=[self.lens.id],
            demote=True,
        )

        reloaded = self._reloaded_lens()
        self.assertIsNotNone(reloaded)
        self.assertIn(
            "tolerances",
            reloaded.metadata,
            msg="the tolerance set was dropped by the save",
        )
        self.assertEqual(
            reloaded.metadata["tolerances"]["radius_1"]["min"],
            49.0,
        )

    def test_the_blob_has_one_shape(self):
        """The stored blob must not carry a nested copy of the metadata"""
        self.db.save_library(
            [self.lens.to_dict(), self.assembly.to_dict()],
            library_lens_ids=[self.lens.id],
            demote=True,
        )

        for row in self.db.load_all():
            if row.get("name") != "Tol":
                continue
            blob = row.get("metadata") or {}
            self.assertNotIn(
                "metadata",
                blob,
                msg="the blob still carries a nested copy of the metadata",
            )
            self.assertIn("tolerances", blob)

    def test_a_legacy_nested_blob_is_rescued(self):
        """A row written by an older version must still load its metadata"""
        legacy = dict(self.lens.to_dict())
        legacy["metadata"] = {"metadata": dict(self.lens.metadata)}
        self.db.save_library([legacy], library_lens_ids=[self.lens.id], demote=True)

        # The row the old writer would have produced: the blob nested.
        with self.db._connection() as conn:
            row = conn.execute(
                "SELECT metadata FROM lenses WHERE id = ?", (self.lens.id,)
            ).fetchone()
        blob = __import__("json").loads(row["metadata"])
        self.assertIn("metadata", blob, "the test fixture did not nest the metadata")

        # Written the old way, the reader dropped the nested copy.
        lens = Lens.from_dict({"metadata": blob})
        self.assertIn(
            "tolerances",
            lens.metadata,
            msg="the nested metadata of a legacy row was not rescued",
        )


if __name__ == "__main__":
    unittest.main()
