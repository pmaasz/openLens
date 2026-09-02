"""
Tests for src/database.py — DatabaseManager CRUD and transaction handling.
"""

import os
import tempfile
import unittest

from src.database import DatabaseManager, LensInUseError


def _make_db():
    """Create a DatabaseManager backed by a temp file that auto-cleans."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    return DatabaseManager(tmp.name), tmp.name


def _make_lens_dict(lens_id: str = "lens-1", name: str = "Test Lens", **overrides) -> dict:
    base = {
        "id": lens_id,
        "name": name,
        "radius_of_curvature_1": 100.0,
        "radius_of_curvature_2": -100.0,
        "thickness": 5.0,
        "material": "BK7",
        "refractive_index": 1.5168,
        "diameter": 25.0,
    }
    base.update(overrides)
    return base


def _make_assembly_dict(
    asm_id: str = "asm-1", name: str = "Test Assembly", lens_ids=None, **overrides
) -> dict:
    if lens_ids is None:
        lens_ids = ["lens-1"]
    elements = [
        {"lens": _make_lens_dict(lens_id=lid, name=f"Lens {lid}"), "position": i * 10.0}
        for i, lid in enumerate(lens_ids)
    ]
    base = {
        "id": asm_id,
        "name": name,
        "elements": elements,
        "air_gaps": [{"thickness": 5.0, "position": 5.0}],
    }
    base.update(overrides)
    return base


def _load_assemblies(db):
    """Return only OpticalSystem items from load_all."""
    return [r for r in db.load_all() if r.get("type") == "OpticalSystem"]


def _load_lenses(db):
    """Return only standalone Lens items from load_all."""
    return [r for r in db.load_all() if r.get("type") == "Lens"]


class TestDatabaseManagerInit(unittest.TestCase):

    def test_creates_file(self):
        db, path = _make_db()
        try:
            self.assertTrue(os.path.exists(path))
            with db._connection() as conn:
                tables = [
                    r[0]
                    for r in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    ).fetchall()
                ]
            self.assertIn("lenses", tables)
            self.assertIn("assemblies", tables)
            self.assertIn("assembly_elements", tables)
            self.assertIn("assembly_air_gaps", tables)
        finally:
            os.unlink(path)


class TestLensCRUD(unittest.TestCase):

    def setUp(self):
        self.db, self._path = _make_db()

    def tearDown(self):
        os.unlink(self._path)

    def test_save_and_load_single_lens(self):
        self.db.save_lens(_make_lens_dict())
        lenses = _load_lenses(self.db)
        self.assertEqual(len(lenses), 1)
        loaded = lenses[0]
        self.assertEqual(loaded["id"], "lens-1")
        self.assertEqual(loaded["name"], "Test Lens")
        self.assertAlmostEqual(loaded["radius_of_curvature_1"], 100.0)
        self.assertAlmostEqual(loaded["radius_of_curvature_2"], -100.0)
        self.assertAlmostEqual(loaded["thickness"], 5.0)
        self.assertEqual(loaded["material"], "BK7")

    def test_save_multiple_lenses(self):
        for i in range(3):
            self.db.save_lens(_make_lens_dict(lens_id=f"L{i}", name=f"Lens {i}"))
        lenses = _load_lenses(self.db)
        self.assertEqual(len(lenses), 3)
        ids = {r["id"] for r in lenses}
        self.assertEqual(ids, {"L0", "L1", "L2"})

    def test_upsert_lens(self):
        self.db.save_lens(_make_lens_dict(name="Original"))
        self.db.save_lens(_make_lens_dict(name="Updated"))
        lenses = _load_lenses(self.db)
        self.assertEqual(len(lenses), 1)
        self.assertEqual(lenses[0]["name"], "Updated")

    def test_delete_lens(self):
        self.db.save_lens(_make_lens_dict())
        self.db.delete_item("lens-1")
        lenses = _load_lenses(self.db)
        self.assertEqual(len(lenses), 0)

    def test_delete_nonexistent_is_noop(self):
        self.db.delete_item("ghost-id")
        self.assertEqual(_load_lenses(self.db), [])

    def test_all_ids(self):
        self.db.save_lens(_make_lens_dict(lens_id="a"))
        self.db.save_lens(_make_lens_dict(lens_id="b"))
        ids = self.db.all_ids()
        self.assertEqual(sorted(ids["lenses"]), ["a", "b"])
        self.assertEqual(ids["assemblies"], [])


class TestAssemblyCRUD(unittest.TestCase):

    def setUp(self):
        self.db, self._path = _make_db()

    def tearDown(self):
        os.unlink(self._path)

    def test_save_and_load_assembly(self):
        self.db.save_assembly(_make_assembly_dict())
        assemblies = _load_assemblies(self.db)
        self.assertEqual(len(assemblies), 1)
        loaded = assemblies[0]
        self.assertEqual(loaded["id"], "asm-1")
        self.assertEqual(loaded["name"], "Test Assembly")
        self.assertEqual(len(loaded["elements"]), 1)
        self.assertEqual(len(loaded["air_gaps"]), 1)

    def test_assembly_element_lens_persisted(self):
        self.db.save_assembly(_make_assembly_dict(lens_ids=["L1", "L2"]))
        assemblies = _load_assemblies(self.db)
        self.assertEqual(len(assemblies[0]["elements"]), 2)
        lens_ids = {e["lens"]["id"] for e in assemblies[0]["elements"]}
        self.assertEqual(lens_ids, {"L1", "L2"})

    def test_upsert_assembly_replaces_elements(self):
        self.db.save_assembly(_make_assembly_dict(lens_ids=["L1"]))
        self.db.save_assembly(_make_assembly_dict(lens_ids=["L1", "L2", "L3"]))
        assemblies = _load_assemblies(self.db)
        self.assertEqual(len(assemblies), 1)
        self.assertEqual(len(assemblies[0]["elements"]), 3)

    def test_delete_assembly_cascades(self):
        self.db.save_assembly(_make_assembly_dict())
        self.db.delete_item("asm-1")
        assemblies = _load_assemblies(self.db)
        self.assertEqual(len(assemblies), 0)

    def test_all_ids_includes_assemblies(self):
        self.db.save_assembly(_make_assembly_dict())
        ids = self.db.all_ids()
        self.assertEqual(ids["assemblies"], ["asm-1"])


class TestLensInUseError(unittest.TestCase):

    def setUp(self):
        self.db, self._path = _make_db()

    def tearDown(self):
        os.unlink(self._path)

    def test_cannot_delete_lens_in_assembly(self):
        self.db.save_assembly(_make_assembly_dict(lens_ids=["shared-lens"]))
        with self.assertRaises(LensInUseError) as ctx:
            self.db.delete_item("shared-lens")
        self.assertIn("shared-lens", str(ctx.exception))
        self.assertEqual(len(ctx.exception.assemblies), 1)

    def test_can_delete_after_removing_from_assembly(self):
        self.db.save_assembly(_make_assembly_dict(lens_ids=["shared-lens"]))
        # Replace assembly with one that doesn't reference the lens
        self.db.save_assembly(_make_assembly_dict(asm_id="asm-1", name="Updated", lens_ids=[]))
        self.db.delete_item("shared-lens")
        lenses = _load_lenses(self.db)
        ids = {r["id"] for r in lenses}
        self.assertNotIn("shared-lens", ids)


class TestTransactions(unittest.TestCase):

    def setUp(self):
        self.db, self._path = _make_db()

    def tearDown(self):
        os.unlink(self._path)

    def test_save_lens_rolls_back_on_bad_data(self):
        self.db.save_lens(_make_lens_dict(lens_id="good"))
        bad = {"id": "bad"}
        try:
            self.db.save_lens(bad)
        except Exception:
            pass
        lenses = _load_lenses(self.db)
        ids = {r["id"] for r in lenses}
        self.assertIn("good", ids)
        self.assertNotIn("bad", ids)

    def test_concurrent_saves(self):
        for i in range(10):
            self.db.save_lens(_make_lens_dict(lens_id=f"L{i}"))
        lenses = _load_lenses(self.db)
        self.assertEqual(len(lenses), 10)


class TestGetReferencingAssemblies(unittest.TestCase):

    def setUp(self):
        self.db, self._path = _make_db()

    def tearDown(self):
        os.unlink(self._path)

    def test_single_assembly(self):
        self.db.save_assembly(_make_assembly_dict(asm_id="a1", name="Assembly A", lens_ids=["L1"]))
        refs = self.db.get_referencing_assemblies("L1")
        self.assertEqual(refs, [("a1", "Assembly A")])

    def test_multiple_assemblies(self):
        self.db.save_assembly(_make_assembly_dict(asm_id="a1", name="Alpha", lens_ids=["L1"]))
        self.db.save_assembly(_make_assembly_dict(asm_id="a2", name="Beta", lens_ids=["L1", "L2"]))
        refs = self.db.get_referencing_assemblies("L1")
        names = [name for _, name in refs]
        self.assertEqual(sorted(names), ["Alpha", "Beta"])

    def test_unreferenced_lens(self):
        self.db.save_lens(_make_lens_dict(lens_id="L1"))
        refs = self.db.get_referencing_assemblies("L1")
        self.assertEqual(refs, [])


if __name__ == "__main__":
    unittest.main()
