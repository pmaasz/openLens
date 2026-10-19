"""Catalog imports must persist once, and a failed persist must be visible.

#474: ``add_material`` rewrites the whole JSON catalog on every call, so
importing N glasses rewrote ``materials.json`` N times. When a write failed -
a read-only install, a full disk - the importer's broad ``except Exception``
swallowed it, logged, and returned a partial count as if the import had
succeeded. Lower-case keys in the JSON file were also invisible because
``get_material`` upper-cases the lookup and ``_load_database`` stored the key
verbatim.
"""

import json
import os
import tempfile
import unittest

from openlens.material_database import MaterialDatabase, MaterialProperties

_AGF = """\
NM GLASS_A 2 517642 1.5168 64.17 7.1 2.51 0 0 0 0 0 0
CD 1.03961212 0.00600069867 0.231792344 0.0200179144 1.01046945 103.560653
NM GLASS_B 2 462384 1.7847 25.68 6.1 3.22 0 0 0 0 0 0
CD 1.73759695 0.013188707 0.313747346 0.0623068142 1.89877801 155.23629
"""

_CSV = """\
Name,Catalog,Nd,Vd,B1,B2,B3,C1,C2,C3
CSV_A,Custom,1.6,50.0,1.0,0.2,0.1,0.01,0.02,100.0
CSV_B,Custom,1.7,40.0,1.0,0.2,0.1,0.01,0.02,100.0
"""


class _ImportCase(unittest.TestCase):
    def setUp(self):
        handle, self.db_path = tempfile.mkstemp(suffix=".json")
        os.close(handle)
        self.addCleanup(os.unlink, self.db_path)
        self.db = MaterialDatabase(self.db_path)

        self.catalog_path = self._write_catalog(".agf", _AGF)

    def _write_catalog(self, suffix, text):
        handle = tempfile.NamedTemporaryFile("w", suffix=suffix, delete=False)
        handle.write(text)
        handle.close()
        self.addCleanup(os.unlink, handle.name)
        return handle.name

    def _count_saves(self):
        calls = []
        original = self.db.save_database

        def counting():
            calls.append(1)
            original()

        self.db.save_database = counting
        return calls


class TestImportsSaveOnce(_ImportCase):
    def test_agf_import_writes_the_catalog_once(self):
        saves = self._count_saves()

        count = self.db.import_agf_catalog(self.catalog_path)

        self.assertEqual(count, 2)
        self.assertEqual(saves, [1], "the catalog was rewritten once per glass")

    def test_the_single_write_contains_the_whole_batch(self):
        self.db.import_agf_catalog(self.catalog_path)

        reloaded = MaterialDatabase(self.db_path)
        self.assertIsNotNone(reloaded.get_material("GLASS_A"))
        self.assertIsNotNone(reloaded.get_material("GLASS_B"))

    def test_csv_import_writes_the_catalog_once(self):
        csv_path = self._write_catalog(".csv", _CSV)
        saves = self._count_saves()

        count = self.db.import_csv_catalog(csv_path)

        self.assertEqual(count, 2)
        self.assertEqual(saves, [1], "the catalog was rewritten once per row")

    def test_add_material_still_saves_by_default(self):
        self.db.add_material(MaterialProperties(name="ONE_OFF", catalog="Custom", nd=1.5, vd=50.0))

        reloaded = MaterialDatabase(self.db_path)
        self.assertIsNotNone(reloaded.get_material("ONE_OFF"))


class TestWriteFailuresReachTheCaller(_ImportCase):
    def _fail_writes(self):
        def fail():
            raise OSError("catalog is read-only")

        self.db.save_database = fail

    def test_agf_import_propagates_a_write_failure(self):
        self._fail_writes()

        with self.assertRaises(OSError):
            self.db.import_agf_catalog(self.catalog_path)

    def test_csv_import_propagates_a_write_failure(self):
        csv_path = self._write_catalog(".csv", _CSV)
        self._fail_writes()

        with self.assertRaises(OSError):
            self.db.import_csv_catalog(csv_path)


class TestLowercaseKeysAreLoadable(unittest.TestCase):
    def test_a_lowercase_key_is_found_by_name(self):
        payload = {
            "lower_glass": {"name": "LOWER-GLASS", "catalog": "Custom", "nd": 1.5, "vd": 50.0}
        }
        handle, path = tempfile.mkstemp(suffix=".json")
        os.close(handle)
        self.addCleanup(os.unlink, path)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f)

        db = MaterialDatabase(path)

        self.assertIsNotNone(db.get_material("lower_glass"))
        self.assertIsNotNone(db.get_material("LOWER_GLASS"))
        self.assertEqual(db.get_material("lower_glass").name, "LOWER-GLASS")


if __name__ == "__main__":
    unittest.main()
