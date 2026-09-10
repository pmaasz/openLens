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

    def test_fresh_db_is_v2_with_parabolic_columns(self):
        """New databases are created at user_version=2 directly."""
        import sqlite3

        db, path = _make_db()
        try:
            conn = sqlite3.connect(path)
            try:
                self.assertEqual(conn.execute("PRAGMA user_version").fetchone()[0], 2)
                columns = {r[1] for r in conn.execute("PRAGMA table_info(lenses)").fetchall()}
                for col in (
                    "is_parabolic_1",
                    "parabolic_sag_1",
                    "is_parabolic_2",
                    "parabolic_sag_2",
                ):
                    self.assertIn(col, columns)
            finally:
                conn.close()
        finally:
            os.unlink(path)

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


def _make_v1_db(path):
    """Hand-craft a pre-migration (user_version=1) database on disk."""
    import json
    import sqlite3

    conn = sqlite3.connect(path)
    conn.execute("""
        CREATE TABLE lenses (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            radius1 REAL NOT NULL,
            radius2 REAL NOT NULL,
            thickness REAL NOT NULL,
            material TEXT NOT NULL,
            refractive_index REAL,
            diameter REAL,
            created_at TEXT,
            modified_at TEXT,
            metadata TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE assemblies (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            created_at TEXT,
            modified_at TEXT,
            metadata TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE assembly_elements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assembly_id TEXT NOT NULL,
            lens_id TEXT NOT NULL,
            position REAL NOT NULL,
            order_index INTEGER NOT NULL,
            FOREIGN KEY (assembly_id) REFERENCES assemblies (id) ON DELETE CASCADE,
            FOREIGN KEY (lens_id) REFERENCES lenses (id)
        )
    """)
    conn.execute("""
        CREATE TABLE assembly_air_gaps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assembly_id TEXT NOT NULL,
            thickness REAL NOT NULL,
            position REAL NOT NULL,
            order_index INTEGER NOT NULL,
            FOREIGN KEY (assembly_id) REFERENCES assemblies (id) ON DELETE CASCADE
        )
    """)
    # Pre-parabolic-era row: metadata carries no parabolic keys.
    conn.execute(
        "INSERT INTO lenses (id, name, radius1, radius2, thickness, material,"
        " refractive_index, diameter, created_at, modified_at, metadata)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "old-spherical",
            "Old Spherical",
            100.0,
            -100.0,
            5.0,
            "BK7",
            1.5168,
            40.0,
            "2024-01-01T00:00:00",
            "2024-01-01T00:00:00",
            json.dumps({"lens_type": "Biconvex"}),
        ),
    )
    # Parabolic-era v1 row: parabolic fields live only in the metadata blob.
    conn.execute(
        "INSERT INTO lenses (id, name, radius1, radius2, thickness, material,"
        " refractive_index, diameter, created_at, modified_at, metadata)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "old-parabolic",
            "Old Parabolic",
            100.0,
            -100.0,
            5.0,
            "BK7",
            1.5168,
            40.0,
            "2024-01-01T00:00:00",
            "2024-01-01T00:00:00",
            json.dumps({"is_parabolic_1": True, "parabolic_sag_1": 2.0}),
        ),
    )
    conn.execute("PRAGMA user_version = 1")
    conn.commit()
    conn.close()


class TestMigrationV1ToV2(unittest.TestCase):
    """Pre-parabolic databases migrate and hydrate correctly."""

    def setUp(self):
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        self._path = tmp.name
        _make_v1_db(self._path)
        self.db = DatabaseManager(self._path)

    def tearDown(self):
        os.unlink(self._path)

    def test_migration_stamps_v2_with_columns(self):
        """Opening a v1 DB migrates schema and version."""
        import sqlite3

        conn = sqlite3.connect(self._path)
        try:
            version = conn.execute("PRAGMA user_version").fetchone()[0]
            self.assertEqual(version, 2)
            columns = {r[1] for r in conn.execute("PRAGMA table_info(lenses)").fetchall()}
            for col in (
                "is_parabolic_1",
                "parabolic_sag_1",
                "is_parabolic_2",
                "parabolic_sag_2",
            ):
                self.assertIn(col, columns)
        finally:
            conn.close()

    def test_pre_parabolic_row_hydrates_spherical(self):
        """A row from before parabolic existed loads as plain spherical."""
        from src.lens import Lens

        rows = {r["id"]: r for r in _load_lenses(self.db)}
        lens = Lens.from_dict(rows["old-spherical"])
        self.assertFalse(lens.is_parabolic_1)
        self.assertFalse(lens.is_parabolic_2)
        self.assertEqual(lens.parabolic_sag_1, 0.0)
        self.assertEqual(lens.calculate_edge_thickness() is not None, True)

    def test_metadata_blob_still_wins_after_migration(self):
        """Migrated columns default 0; the metadata blob keeps the truth."""
        from src.lens import Lens

        rows = {r["id"]: r for r in _load_lenses(self.db)}
        lens = Lens.from_dict(rows["old-parabolic"])
        self.assertTrue(lens.is_parabolic_1)
        self.assertAlmostEqual(lens.parabolic_sag_1, 2.0)

    def test_resave_promotes_to_columns(self):
        """Re-saving a migrated lens writes explicit columns, not the blob."""
        import json
        import sqlite3

        from src.lens import Lens

        rows = {r["id"]: r for r in _load_lenses(self.db)}
        lens = Lens.from_dict(rows["old-parabolic"])
        self.db.save_lens(lens.to_dict())

        conn = sqlite3.connect(self._path)
        try:
            row = conn.execute(
                "SELECT is_parabolic_1, parabolic_sag_1, metadata FROM lenses WHERE id = ?",
                ("old-parabolic",),
            ).fetchone()
            self.assertEqual(row[0], 1)
            self.assertAlmostEqual(row[1], 2.0)
            self.assertNotIn("parabolic_sag_1", json.loads(row[2]))
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
