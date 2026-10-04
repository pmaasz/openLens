#!/usr/bin/env python3
"""
One malformed entry must not discard a whole materials catalog.

`_load_database` looped over the JSON inside a single try/except, and
`MaterialProperties.from_dict` is `cls(**data)` with no key filtering. So one
unknown key raised TypeError, aborted the loop mid-file, and left the user
with a warning plus a silently truncated material list - and because the
built-in defaults are loaded first, nothing visibly looked wrong.
"""

import json
import os
import tempfile
import unittest

from src.material_database import MaterialDatabase

_GOOD = {"name": "N-BK7", "catalog": "SCHOTT", "nd": 1.5168, "vd": 64.17}


def _write(payload):
    handle, path = tempfile.mkstemp(suffix=".json")
    os.close(handle)
    with open(path, "w", encoding="utf-8") as f:
        if isinstance(payload, str):
            f.write(payload)
        else:
            json.dump(payload, f)
    return path


class TestMaterialDatabaseResilience(unittest.TestCase):
    def _db(self, payload):
        path = _write(payload)
        self.addCleanup(os.unlink, path)
        return MaterialDatabase(path)

    def _from_file(self, db):
        """Only the names this file contributed, ignoring built-in defaults."""
        return {name for name in db.materials if name in self._payload}

    def setUp(self):
        self._payload = {
            "AAA": dict(_GOOD, name="AAA"),
            "BBB": dict(_GOOD, name="BBB"),
            "BAD": dict(_GOOD, name="BAD", unknown_key=1),
            "CCC": dict(_GOOD, name="CCC"),
            "DDD": dict(_GOOD, name="DDD"),
        }
        self.db = self._db(self._payload)

    def test_bad_entry_does_not_discard_the_rest(self):
        """Regression: one unknown key used to cost every later material."""
        loaded = self._from_file(self.db)
        self.assertEqual(loaded, {"AAA", "BBB", "CCC", "DDD"})

    def test_missing_required_field_costs_only_itself(self):
        self._payload = {
            "GOOD1": dict(_GOOD, name="GOOD1"),
            "NOFIELD": {"name": "NOFIELD"},  # missing catalog/nd/vd
            "GOOD2": dict(_GOOD, name="GOOD2"),
        }
        db = self._db(self._payload)
        self.assertEqual(self._from_file(db), {"GOOD1", "GOOD2"})

    def test_non_object_entry_is_skipped(self):
        self._payload = {
            "GOOD1": dict(_GOOD, name="GOOD1"),
            "NOTADICT": 42,
            "GOOD2": dict(_GOOD, name="GOOD2"),
        }
        db = self._db(self._payload)
        self.assertEqual(self._from_file(db), {"GOOD1", "GOOD2"})

    def test_empty_file_loads_only_the_defaults(self):
        db = self._db({})
        self.assertEqual(self._from_file(db), set())
        self.assertIn("N-BK7", db.materials)  # defaults survive

    def test_unreadable_json_is_survivable(self):
        db = self._db("{not json at all")
        self.assertIn("N-BK7", db.materials)

    def test_json_that_is_not_an_object_is_ignored(self):
        db = self._db([1, 2, 3])
        self.assertIn("N-BK7", db.materials)

    def test_missing_file_leaves_defaults(self):
        self.assertFalse(os.path.exists("/nonexistent/materials.json"))
        # Constructing against a missing path must not raise.
        db = MaterialDatabase("/nonexistent/materials.json")
        self.assertIn("N-BK7", db.materials)

    def test_a_lone_bad_entry_still_loads_the_good_ones(self):
        """The reported worst case, in isolation."""
        self._payload = {"BAD": dict(_GOOD, name="BAD", oops=1)}
        db = self._db(self._payload)
        self.assertIn("N-BK7", db.materials)

    def test_file_is_read_as_utf8(self):
        """A non-ASCII name must round-trip, not raise UnicodeDecodeError."""
        path = _write({"CAFÉ": dict(_GOOD, name="CAFÉ", catalog="SCHOTT")})
        self.addCleanup(os.unlink, path)
        db = MaterialDatabase(path)
        self.assertIn("CAFÉ", db.materials)


if __name__ == "__main__":
    unittest.main()
