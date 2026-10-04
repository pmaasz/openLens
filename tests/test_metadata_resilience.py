#!/usr/bin/env python3
"""
A corrupt metadata blob must not empty the whole library.

`load_all` called `json.loads(lens["metadata"])` unguarded in three places.
A truncated or hand-edited blob raised JSONDecodeError out of load_all, and
`LensStorage.load_lenses` catches broad `Exception` and returns `[]` - so one
bad row left the user looking at a completely empty library with only a log
line to explain it.

`_metadata_merge` mirrors the `_coating_parse` pattern that already existed in
the same file.
"""

import os
import sqlite3
import tempfile
import unittest

from src.database import DatabaseManager, _metadata_merge


def _db():
    handle, path = tempfile.mkstemp(suffix=".db")
    os.close(handle)
    db = DatabaseManager(path)

    def cleanup():
        for suffix in ("", "-wal", "-shm"):
            if os.path.exists(path + suffix):
                os.unlink(path + suffix)

    return db, path, cleanup


def _assembly():
    """save_assembly wants each element's lens inline, not a lens_id."""
    return {
        "id": "asm-1",
        "name": "Asm",
        "elements": [{"lens": _lens("shared", "Shared"), "position": 0.0}],
        "air_gaps": [],
    }


def _lens(lens_id, name):
    return {
        "id": lens_id,
        "name": name,
        "radius_of_curvature_1": 100.0,
        "radius_of_curvature_2": -100.0,
        "thickness": 5.0,
        "material": "BK7",
        "diameter": 25.0,
    }


class TestMetadataMerge(unittest.TestCase):
    """The helper in isolation."""

    def test_merges_a_valid_object(self):
        target = {"a": 1}
        _metadata_merge(target, '{"b": 2}', "test")
        self.assertEqual(target, {"a": 1, "b": 2})

    def test_truncated_blob_is_ignored(self):
        target = {"a": 1}
        _metadata_merge(target, "{trunc", "test")
        self.assertEqual(target, {"a": 1})

    def test_json_array_is_ignored(self):
        target = {"a": 1}
        _metadata_merge(target, "[1, 2, 3]", "test")
        self.assertEqual(target, {"a": 1})

    def test_json_scalar_is_ignored(self):
        target = {"a": 1}
        _metadata_merge(target, '"just a string"', "test")
        self.assertEqual(target, {"a": 1})

    def test_non_string_non_dict_is_ignored(self):
        target = {"a": 1}
        _metadata_merge(target, 42, "test")
        self.assertEqual(target, {"a": 1})

    def test_empty_blob_is_a_no_op(self):
        target = {"a": 1}
        _metadata_merge(target, "", "test")
        _metadata_merge(target, None, "test")
        self.assertEqual(target, {"a": 1})

    def test_already_parsed_dict_is_merged(self):
        target = {"a": 1}
        _metadata_merge(target, {"b": 2}, "test")
        self.assertEqual(target, {"a": 1, "b": 2})


class TestLoadAllSurvivesCorruptMetadata(unittest.TestCase):
    def setUp(self):
        self.db, self.path, self.cleanup = _db()
        self.addCleanup(self.cleanup)

    def _corrupt(self, table, row_id, blob):
        conn = sqlite3.connect(self.path)
        conn.execute(f"UPDATE {table} SET metadata = ? WHERE id = ?", (blob, row_id))
        conn.commit()
        conn.close()

    def test_corrupt_lens_metadata_still_loads_every_lens(self):
        """Regression: one bad row returned an empty library."""
        self.db.save_lens(_lens("good1", "Good One"))
        self.db.save_lens(_lens("bad1", "Corrupt"))
        self._corrupt("lenses", "bad1", "{trunc")

        rows = self.db.load_all()
        names = sorted(r["name"] for r in rows)
        self.assertEqual(names, ["Corrupt", "Good One"])

    def test_corrupt_lens_metadata_keeps_its_columns(self):
        """The blob is dropped; the real columns still apply."""
        self.db.save_lens(_lens("bad1", "Corrupt"))
        self._corrupt("lenses", "bad1", "{trunc")
        row = next(r for r in self.db.load_all() if r["id"] == "bad1")
        self.assertEqual(row["radius_of_curvature_1"], 100.0)
        self.assertEqual(row["thickness"], 5.0)

    def test_corrupt_assembly_metadata_still_loads(self):
        self.db.save_assembly(_assembly())
        self._corrupt("assemblies", "asm-1", "{trunc")
        rows = self.db.load_all()
        self.assertIn("Asm", [r["name"] for r in rows])

    def test_corrupt_element_lens_metadata_still_loads_assembly(self):
        """The third unguarded site: a lens embedded in an assembly."""
        self.db.save_assembly(_assembly())
        conn = sqlite3.connect(self.path)
        conn.execute("UPDATE lenses SET metadata = ? WHERE name = ?", ("{trunc", "Shared"))
        conn.commit()
        conn.close()

        asm = next(r for r in self.db.load_all() if r.get("type") == "OpticalSystem")
        self.assertEqual(asm["elements"][0]["lens"]["name"], "Shared")


if __name__ == "__main__":
    unittest.main()
