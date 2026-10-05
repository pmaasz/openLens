#!/usr/bin/env python3
"""
The refractive index cache must be per-instance, not class-wide.

get_refractive_index carried @lru_cache(maxsize=1024), so the cache key
included `self`: one class-wide cache holding every MaterialDatabase ever
used, strongly, forever.

    after one lookup, del m; gc.collect()
    -> MaterialDatabase instances alive: 1

chromatic_analyzer.py constructs a fresh MaterialDatabase() per analyzer, so
the count grew without bound and no instance was ever collected.

Two related defects came with it:

- add_material and clear_cache called cache_clear() on the *shared* wrapper,
  so one instance adding a material wiped every other instance's cache.
- Direct mutation of self.materials (a re-read materials.json) never
  invalidated anything.

The cache is now a per-instance dict that dies with its owner.
"""

import gc
import json
import os
import tempfile
import unittest

from src.material_database import MaterialDatabase, MaterialProperties


def _live_instances():
    return sum(1 for obj in gc.get_objects() if type(obj).__name__ == "MaterialDatabase")


def _db():
    handle, path = tempfile.mkstemp(suffix=".json")
    os.close(handle)
    with open(path, "w") as f:
        json.dump({}, f)
    return path


def _material(name="TEST_GLASS", b1=1.0, c1=0.0001, nd=1.5):
    return MaterialProperties(name=name, catalog="TEST", nd=nd, vd=60.0, B1=b1, C1=c1)


class TestNoInstanceLeak(unittest.TestCase):
    def test_instance_is_collectable_after_a_lookup(self):
        """Regression: the class-wide cache held `self` strongly."""
        path = _db()
        self.addCleanup(os.unlink, path)
        before = _live_instances()

        db = MaterialDatabase(path)
        db.get_refractive_index("N-BK7", 550.0)
        del db
        gc.collect()

        self.assertLessEqual(_live_instances(), before)

    def test_repeated_construction_leaves_nothing_behind(self):
        """chromatic_analyzer builds one per analyzer."""
        path = _db()
        self.addCleanup(os.unlink, path)
        gc.collect()
        before = _live_instances()

        for _ in range(25):
            db = MaterialDatabase(path)
            db.get_refractive_index("N-BK7", 587.6)
            del db
        gc.collect()

        self.assertLessEqual(_live_instances(), before)

    def test_the_method_no_longer_exposes_an_lru_cache(self):
        self.assertFalse(hasattr(MaterialDatabase.get_refractive_index, "cache_info"))
        self.assertFalse(hasattr(MaterialDatabase.get_refractive_index, "cache_clear"))


class TestCachesAreIndependent(unittest.TestCase):
    """Regression: clear_cache() wiped every instance's cache."""

    def setUp(self):
        path = _db()
        self.addCleanup(os.unlink, path)
        self.a = MaterialDatabase(path)
        self.b = MaterialDatabase(path)

    def test_each_instance_has_its_own_dict(self):
        self.assertIsNot(self.a._index_cache, self.b._index_cache)

    def test_clearing_one_leaves_the_other_populated(self):
        self.a.get_refractive_index("N-BK7", 550.0)
        self.b.get_refractive_index("SF11", 550.0)
        self.assertEqual(len(self.a._index_cache), 1)
        self.assertEqual(len(self.b._index_cache), 1)

        self.a.clear_cache()

        self.assertEqual(len(self.a._index_cache), 0)
        self.assertEqual(len(self.b._index_cache), 1)

    def test_add_material_only_clears_its_own_instance(self):
        self.a.add_material(_material())
        self.b.get_refractive_index("N-BK7", 550.0)
        self.assertEqual(len(self.b._index_cache), 1)

        self.a.add_material(_material(b1=2.0))

        self.assertEqual(len(self.b._index_cache), 1)


class TestInvalidation(unittest.TestCase):
    def setUp(self):
        path = _db()
        self.addCleanup(os.unlink, path)
        self.db = MaterialDatabase(path)

    def test_add_material_invalidates(self):
        self.db.add_material(_material())
        first = self.db.get_refractive_index("TEST_GLASS", 550.0)
        self.db.add_material(_material(b1=2.0))
        second = self.db.get_refractive_index("TEST_GLASS", 550.0)
        self.assertNotAlmostEqual(first, second)

    def test_clear_cache_forces_recomputation(self):
        self.db.add_material(_material())
        before = self.db.get_refractive_index("TEST_GLASS", 550.0)
        base = self.db.get_material("TEST_GLASS")
        self.db.materials["TEST_GLASS"] = MaterialProperties(**{**base.__dict__, "B1": base.B1 * 2})
        self.assertEqual(self.db.get_refractive_index("TEST_GLASS", 550.0), before)

        self.db.clear_cache()

        self.assertNotAlmostEqual(self.db.get_refractive_index("TEST_GLASS", 550.0), before)

    def test_loading_the_database_invalidates(self):
        """A re-read materials.json must not serve stale indices."""
        path = _db()
        self.addCleanup(os.unlink, path)
        db = MaterialDatabase(path)
        first = db.get_refractive_index("N-BK7", 550.0)
        self.assertGreater(len(db._index_cache), 0)

        db._load_database()

        self.assertEqual(len(db._index_cache), 0)
        self.assertAlmostEqual(db.get_refractive_index("N-BK7", 550.0), first)


class TestCacheBehaviour(unittest.TestCase):
    def setUp(self):
        path = _db()
        self.addCleanup(os.unlink, path)
        self.db = MaterialDatabase(path)
        self.db.add_material(_material())

    def test_repeat_lookups_are_identical(self):
        first = self.db.get_refractive_index("TEST_GLASS", 550.0)
        second = self.db.get_refractive_index("TEST_GLASS", 550.0)
        self.assertEqual(first, second)

    def test_distinct_keys_get_distinct_entries(self):
        self.db.get_refractive_index("TEST_GLASS", 550.0)
        self.db.get_refractive_index("TEST_GLASS", 486.1)
        self.db.get_refractive_index("TEST_GLASS", 550.0, 35.0)
        self.assertEqual(len(self.db._index_cache), 3)

    def test_cache_is_bounded(self):
        for wavelength in range(400, 400 + MaterialDatabase.INDEX_CACHE_MAX + 50):
            self.db.get_refractive_index("TEST_GLASS", float(wavelength))
        self.assertLessEqual(len(self.db._index_cache), MaterialDatabase.INDEX_CACHE_MAX)

    def test_unknown_material_falls_back(self):
        self.assertEqual(self.db.get_refractive_index("NOPE", 550.0), 1.5168)

    def test_values_match_the_uncached_computation(self):
        for wavelength in (486.1, 550.0, 587.6, 656.3):
            with self.subTest(wavelength=wavelength):
                cached = self.db.get_refractive_index("N-BK7", wavelength)
                direct = self.db._compute_refractive_index("N-BK7", wavelength, 20.0)
                self.assertEqual(cached, direct)


if __name__ == "__main__":
    unittest.main()
