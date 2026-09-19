"""Tests for aperture stops and element alignment (todo item 2)."""

import json
import os
import sqlite3
import tempfile
import unittest

from src.database import DatabaseManager
from src.lens import Lens
from src.optical_system import OpticalSystem


def _make_db():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    return DatabaseManager(tmp.name), tmp.name


def _two_element_system():
    system = OpticalSystem(name="Stop System")
    system.add_lens(Lens(name="A", diameter=25.0))
    system.add_lens(Lens(name="B", diameter=25.0), air_gap_before=5.0)
    return system


def _make_v3_db(path):
    """Hand-craft a pre-migration (user_version=3) database on disk."""
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
            is_parabolic_1 INTEGER NOT NULL DEFAULT 0,
            parabolic_sag_1 REAL NOT NULL DEFAULT 0.0,
            is_parabolic_2 INTEGER NOT NULL DEFAULT 0,
            parabolic_sag_2 REAL NOT NULL DEFAULT 0.0,
            clear_aperture_1 REAL,
            clear_aperture_2 REAL,
            bevel_1 REAL NOT NULL DEFAULT 0.0,
            bevel_2 REAL NOT NULL DEFAULT 0.0,
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
    conn.execute(
        "INSERT INTO lenses (id, name, radius1, radius2, thickness, material,"
        " refractive_index, diameter, created_at, modified_at, metadata)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "old-lens",
            "Old Lens",
            100.0,
            -100.0,
            5.0,
            "BK7",
            1.5168,
            40.0,
            "2024-01-01T00:00:00",
            "2024-01-01T00:00:00",
            json.dumps({}),
        ),
    )
    conn.execute("PRAGMA user_version = 3")
    conn.commit()
    conn.close()


class TestApertureStopModel(unittest.TestCase):
    def test_no_stop_by_default(self):
        """A new system should have no stop defined."""
        self.assertIsNone(_two_element_system().get_aperture_stop())

    def test_set_and_get_stop(self):
        """Set stop should report gap index, position, and diameter."""
        system = _two_element_system()
        system.set_aperture_stop(0, 20.0)
        stop = system.get_aperture_stop()
        self.assertEqual(stop["gap_index"], 0)
        self.assertAlmostEqual(stop["position"], 5.0)
        self.assertEqual(stop["diameter"], 20.0)

    def test_clear_stop(self):
        """Clearing should remove the stop definition."""
        system = _two_element_system()
        system.set_aperture_stop(0, 20.0)
        system.clear_aperture_stop()
        self.assertIsNone(system.get_aperture_stop())

    def test_invalid_gap_raises(self):
        """Out-of-range gap indices should raise."""
        system = _two_element_system()
        with self.assertRaises(ValueError):
            system.set_aperture_stop(5, 20.0)
        with self.assertRaises(ValueError):
            system.set_aperture_stop(-1, 20.0)

    def test_stale_stop_after_removal_reads_unset(self):
        """A stop whose gap no longer exists should read as unset."""
        system = _two_element_system()
        system.set_aperture_stop(0, 20.0)
        system.remove_lens(1)
        self.assertIsNone(system.get_aperture_stop())

    def test_dict_round_trip_preserves_stop(self):
        """to_dict/from_dict should carry the stop definition."""
        system = _two_element_system()
        system.set_aperture_stop(0, 20.0)
        clone = OpticalSystem.from_dict(system.to_dict())
        self.assertEqual(clone.get_aperture_stop()["gap_index"], 0)
        self.assertEqual(clone.get_aperture_stop()["diameter"], 20.0)


class TestElementAlignmentModel(unittest.TestCase):
    def test_defaults_are_zero(self):
        """Elements should start centered and unrotated."""
        system = _two_element_system()
        for element in system.elements:
            self.assertEqual(element.decenter_y, 0.0)
            self.assertEqual(element.tilt_x, 0.0)

    def test_set_alignment_syncs_node_and_record(self):
        """Alignment should land on both the tree node and the record."""
        system = _two_element_system()
        self.assertTrue(system.set_element_alignment(1, decenter_y=0.1, tilt_x=0.5))
        element = system.elements[1]
        self.assertEqual(element.decenter_y, 0.1)
        self.assertEqual(element.tilt_x, 0.5)
        node = system.root.children[1]
        self.assertEqual(node.position.y, 0.1)
        self.assertEqual(node.rotation.x, 0.5)

    def test_invalid_index_returns_false(self):
        """Out-of-range indices should fail cleanly."""
        system = _two_element_system()
        self.assertFalse(system.set_element_alignment(7, decenter_y=0.1))

    def test_dict_round_trip_preserves_alignment(self):
        """to_dict/from_dict should carry decenter and tilt."""
        system = _two_element_system()
        system.set_element_alignment(0, decenter_z=0.2, tilt_y=0.3, tilt_z=0.4)
        clone = OpticalSystem.from_dict(system.to_dict())
        element = clone.elements[0]
        self.assertEqual(element.decenter_z, 0.2)
        self.assertEqual(element.tilt_y, 0.3)
        self.assertEqual(element.tilt_z, 0.4)
        node = clone.root.children[0]
        self.assertEqual(node.position.z, 0.2)
        self.assertEqual(node.rotation.y, 0.3)


class TestStopAlignmentPersistence(unittest.TestCase):
    def setUp(self):
        self.db, self._path = _make_db()

    def tearDown(self):
        os.unlink(self._path)

    def test_save_and_load_preserves_stop_and_alignment(self):
        """Assembly rows should round-trip stop plus alignment."""
        system = _two_element_system()
        system.set_element_alignment(1, decenter_y=0.1, tilt_x=0.5)
        system.set_aperture_stop(0, 20.0)
        self.db.save_assembly(system.to_dict())
        assemblies = [r for r in self.db.load_all() if r.get("type") == "OpticalSystem"]
        self.assertEqual(len(assemblies), 1)
        loaded = assemblies[0]
        self.assertEqual(loaded["aperture_stop_gap"], 0)
        self.assertEqual(loaded["aperture_stop_diameter"], 20.0)
        element = loaded["elements"][1]
        self.assertEqual(element["decenter_y"], 0.1)
        self.assertEqual(element["tilt_x"], 0.5)

    def test_storage_objects_rehydrate_stop(self):
        """LensStorage loading should rebuild working stop objects."""
        from src.gui.storage import LensStorage

        system = _two_element_system()
        system.set_aperture_stop(0, 20.0)
        storage = LensStorage(self._path)
        storage.save_lenses([system])
        items = storage.load_lenses()
        systems = [i for i in items if isinstance(i, OpticalSystem)]
        self.assertEqual(len(systems), 1)
        self.assertEqual(systems[0].get_aperture_stop()["diameter"], 20.0)

    def test_v3_database_migrates_to_v4(self):
        """A v3 DB should gain stop/alignment columns with zero defaults."""
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        path = tmp.name
        try:
            _make_v3_db(path)
            db = DatabaseManager(path)
            conn = sqlite3.connect(path)
            try:
                self.assertEqual(conn.execute("PRAGMA user_version").fetchone()[0], 5)
            finally:
                conn.close()
            rows = {r["id"]: r for r in db.load_all()}
            self.assertIn("old-lens", rows)
        finally:
            os.unlink(path)

    def test_update_assembly_stop_backfills(self):
        """Stop backfill should not touch elements."""
        system = _two_element_system()
        self.db.save_assembly(system.to_dict())
        self.db.update_assembly_stop(system.id, 0, 18.0)
        assemblies = {r["id"]: r for r in self.db.load_all()}
        self.assertEqual(assemblies[system.id]["aperture_stop_gap"], 0)
        self.assertEqual(assemblies[system.id]["aperture_stop_diameter"], 18.0)
        self.assertEqual(len(assemblies[system.id]["elements"]), 2)


class TestSeriesEStopSeed(unittest.TestCase):
    def test_series_e_assembly_has_stop(self):
        """The Series E seed should carry the L3-L4a stop."""
        from src.seed_data import build_nikon_series_e_system

        system = build_nikon_series_e_system()
        stop = system.get_aperture_stop()
        self.assertIsNotNone(stop)
        self.assertEqual(stop["gap_index"], 2)
        self.assertEqual(stop["diameter"], 20.0)

    def test_seed_ensure_backfills_missing_stop(self):
        """Ensure should add the stop to a stop-less seed assembly."""
        from src.seed_data import (
            NIKON_SERIES_E_ASSEMBLY_ID,
            ensure_nikon_series_e_example,
        )

        db, path = _make_db()
        try:
            ensure_nikon_series_e_example(db)
            db.update_assembly_stop(NIKON_SERIES_E_ASSEMBLY_ID, None, None)
            self.assertTrue(ensure_nikon_series_e_example(db))
            rows = {r["id"]: r for r in db.load_all()}
            self.assertEqual(rows[NIKON_SERIES_E_ASSEMBLY_ID]["aperture_stop_gap"], 2)
        finally:
            os.unlink(path)

    def test_iso_marks_stop(self):
        """ISO SVG output should label the stop plane."""
        from src.io.export import ISO10110Generator
        from src.seed_data import build_nikon_series_e_system

        svg = ISO10110Generator(build_nikon_series_e_system())._render_svg(800, 600)
        self.assertIn("STOP", svg)
        self.assertIn("gap 2", svg)


if __name__ == "__main__":
    unittest.main()
