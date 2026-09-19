"""Tests for per-surface clear apertures and bevels (todo item 1)."""

import json
import os
import sqlite3
import tempfile
import unittest

from src.database import DatabaseManager
from src.lens import Lens
from src.optical_system import OpticalSystem
from src.validation import (
    ValidationError,
    validate_bevel,
    validate_clear_aperture,
)


def _make_db():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    return DatabaseManager(tmp.name), tmp.name


def _make_v2_db(path):
    """Hand-craft a pre-migration (user_version=2) database on disk."""
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
    conn.execute("PRAGMA user_version = 2")
    conn.commit()
    conn.close()


class TestClearApertureModel(unittest.TestCase):
    def test_defaults_mean_full_diameter(self):
        """New fields should default to full diameter and sharp edge."""
        lens = Lens(diameter=40.0)
        self.assertIsNone(lens.clear_aperture_1)
        self.assertIsNone(lens.clear_aperture_2)
        self.assertEqual(lens.bevel_1, 0.0)
        self.assertEqual(lens.bevel_2, 0.0)
        self.assertEqual(lens.get_clear_aperture_1(), 40.0)
        self.assertEqual(lens.get_clear_aperture_2(), 40.0)

    def test_explicit_apertures_are_returned(self):
        """Set apertures should be reported instead of the diameter."""
        lens = Lens(diameter=40.0, clear_aperture_1=36.0, clear_aperture_2=34.0)
        self.assertEqual(lens.get_clear_aperture_1(), 36.0)
        self.assertEqual(lens.get_clear_aperture_2(), 34.0)

    def test_dict_round_trip_preserves_fields(self):
        """to_dict/from_dict should carry the new fields exactly."""
        lens = Lens(
            diameter=40.0,
            clear_aperture_1=36.0,
            clear_aperture_2=34.0,
            bevel_1=0.3,
            bevel_2=0.5,
        )
        clone = Lens.from_dict(lens.to_dict())
        self.assertEqual(clone.clear_aperture_1, 36.0)
        self.assertEqual(clone.clear_aperture_2, 34.0)
        self.assertEqual(clone.bevel_1, 0.3)
        self.assertEqual(clone.bevel_2, 0.5)


class TestClearApertureValidation(unittest.TestCase):
    def test_none_passes_through(self):
        """None should mean full diameter and validate cleanly."""
        self.assertIsNone(validate_clear_aperture(None, 40.0))

    def test_valid_aperture_returns_value(self):
        """An aperture within the diameter should pass."""
        self.assertEqual(validate_clear_aperture(36.0, 40.0), 36.0)

    def test_oversize_aperture_raises(self):
        """An aperture larger than the diameter should raise."""
        with self.assertRaises(ValidationError):
            validate_clear_aperture(41.0, 40.0)

    def test_nonpositive_aperture_raises(self):
        """Zero or negative apertures should raise."""
        with self.assertRaises(ValidationError):
            validate_clear_aperture(0.0, 40.0)
        with self.assertRaises(ValidationError):
            validate_clear_aperture(-5.0, 40.0)

    def test_negative_bevel_raises(self):
        """Negative bevels should raise; zero should pass."""
        with self.assertRaises(ValidationError):
            validate_bevel(-0.1)
        self.assertEqual(validate_bevel(0.0), 0.0)
        self.assertEqual(validate_bevel(0.3), 0.3)


class TestClearAperturePersistence(unittest.TestCase):
    def setUp(self):
        self.db, self._path = _make_db()

    def tearDown(self):
        os.unlink(self._path)

    def test_save_and_load_preserves_fields(self):
        """Standalone lens rows should round-trip the new columns."""
        lens = Lens(
            name="CA Lens",
            diameter=40.0,
            clear_aperture_1=36.0,
            clear_aperture_2=34.0,
            bevel_1=0.3,
            bevel_2=0.5,
        )
        self.db.save_lens(lens.to_dict())
        rows = {r["id"]: r for r in self.db.load_all()}
        self.assertIn(lens.id, rows)
        loaded = Lens.from_dict(rows[lens.id])
        self.assertEqual(loaded.clear_aperture_1, 36.0)
        self.assertEqual(loaded.clear_aperture_2, 34.0)
        self.assertEqual(loaded.bevel_1, 0.3)
        self.assertEqual(loaded.bevel_2, 0.5)

    def test_assembly_elements_preserve_fields(self):
        """Assembly element lenses should round-trip the new columns."""
        lens = Lens(
            name="CA Element",
            diameter=40.0,
            clear_aperture_1=36.0,
            bevel_1=0.3,
        )
        system = OpticalSystem(name="CA System")
        system.add_lens(lens)
        self.db.save_assembly(system.to_dict())
        assemblies = [r for r in self.db.load_all() if r.get("type") == "OpticalSystem"]
        self.assertEqual(len(assemblies), 1)
        element_lens = assemblies[0]["elements"][0]["lens"]
        self.assertEqual(element_lens["clear_aperture_1"], 36.0)
        self.assertEqual(element_lens["bevel_1"], 0.3)

    def test_v2_database_migrates_to_v3_with_defaults(self):
        """A v2 DB should gain the columns; old rows read as full/sharp."""
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        path = tmp.name
        try:
            _make_v2_db(path)
            db = DatabaseManager(path)
            conn = sqlite3.connect(path)
            try:
                self.assertEqual(conn.execute("PRAGMA user_version").fetchone()[0], 3)
            finally:
                conn.close()
            rows = {r["id"]: r for r in db.load_all()}
            lens = Lens.from_dict(rows["old-lens"])
            self.assertIsNone(lens.clear_aperture_1)
            self.assertEqual(lens.get_clear_aperture_1(), 40.0)
            self.assertEqual(lens.bevel_1, 0.0)
        finally:
            os.unlink(path)


class TestClearApertureExports(unittest.TestCase):
    def _system_with_ca_lens(self):
        lens = Lens(
            name="Export Lens",
            radius_of_curvature_1=100.0,
            radius_of_curvature_2=-100.0,
            thickness=5.0,
            diameter=40.0,
            clear_aperture_1=36.0,
            clear_aperture_2=34.0,
            bevel_1=0.3,
            material="BK7",
        )
        system = OpticalSystem(name="Export System")
        system.add_lens(lens)
        return system, lens

    def test_iso_table_shows_clear_aperture(self):
        """ISO SVG table should gain a CA column with per-surface values."""
        from src.io.export import ISO10110Generator

        system, _ = self._system_with_ca_lens()
        svg = ISO10110Generator(system)._render_svg(800, 600)
        self.assertIn("CA", svg)
        self.assertIn("36.00", svg)
        self.assertIn("34.00", svg)

    def test_step_solid_name_carries_aperture_data(self):
        """STEP solids should label non-default CA/bevel in the name."""
        from src.io.step_export import StepExporter

        system, _ = self._system_with_ca_lens()
        with tempfile.NamedTemporaryFile(suffix=".step", delete=False, mode="w") as tmp:
            step_path = tmp.name
        try:
            StepExporter(system).export(step_path)
            with open(step_path) as f:
                content = f.read()
            self.assertIn("CA 36.0/34.0", content)
            self.assertIn("bevel 0.3/0.0", content)
        finally:
            os.unlink(step_path)

    def test_step_default_lens_keeps_plain_name(self):
        """Lenses without CA/bevel should keep their plain STEP name."""
        from src.io.step_export import StepExporter

        system = OpticalSystem(name="Plain System")
        system.add_lens(Lens(name="Plain", diameter=40.0))
        with tempfile.NamedTemporaryFile(suffix=".step", delete=False, mode="w") as tmp:
            step_path = tmp.name
        try:
            StepExporter(system).export(step_path)
            with open(step_path) as f:
                content = f.read()
            self.assertIn("'Plain'", content)
            self.assertNotIn("(CA ", content)
        finally:
            os.unlink(step_path)

    def test_zemax_surfaces_use_clear_aperture(self):
        """Zemax DIAM lines should use the clear aperture, not the OD."""
        from src.export_formats import ZemaxExporter

        _, lens = self._system_with_ca_lens()
        with tempfile.NamedTemporaryFile(suffix=".zmx", delete=False, mode="w") as tmp:
            zmx_path = tmp.name
        try:
            ZemaxExporter.export_lens(lens, zmx_path)
            with open(zmx_path) as f:
                content = f.read()
            self.assertIn("DIAM 36.0", content)
            self.assertIn("DIAM 34.0", content)
        finally:
            os.unlink(zmx_path)


if __name__ == "__main__":
    unittest.main()
