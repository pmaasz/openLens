"""Tests for per-surface coatings (todo item 3)."""

import json
import os
import sqlite3
import tempfile
import unittest

from src.coating_designer import (
    COATING_PRESETS,
    CoatingLayer,
    coated_reflectance,
    coating_label,
    design_preset,
)
from src.database import DatabaseManager
from src.lens import Lens
from src.optical_system import OpticalSystem
from src.validation import ValidationError, validate_coating_stack


def _make_db():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    return DatabaseManager(tmp.name), tmp.name


def _mgf2_stack(substrate=1.5168, wavelength=550.0):
    return [
        layer.to_dict()
        for layer in design_preset("MgF2 single-layer", substrate, wavelength)
    ]


class TestCoatingDesigner(unittest.TestCase):
    def test_presets_build_stacks(self):
        """Each named preset should build its documented stack."""
        single = design_preset("MgF2 single-layer", 1.5168, 550.0)
        self.assertEqual(len(single), 1)
        self.assertEqual(single[0].material, "MgF2")
        self.assertEqual(len(design_preset("Dual-layer AR", 1.5168, 550.0)), 2)
        self.assertEqual(len(design_preset("V-coating", 1.5168, 550.0)), 3)
        self.assertEqual(design_preset("Uncoated", 1.5168, 550.0), [])
        self.assertIn("Uncoated", COATING_PRESETS)

    def test_labels(self):
        """Stacks should format to short human labels."""
        self.assertEqual(coating_label([]), "Uncoated")
        single = design_preset("MgF2 single-layer", 1.5168, 550.0)
        self.assertEqual(coating_label(single), "MgF2 SLAR")
        dual = design_preset("Dual-layer AR", 1.5168, 550.0)
        self.assertTrue(coating_label(dual).startswith("2L AR"))

    def test_single_layer_beats_bare(self):
        """MgF2 SLAR should reflect less than bare glass at design wl."""
        bare = coated_reflectance([], 1.5168, 550.0)
        coated = coated_reflectance(
            design_preset("MgF2 single-layer", 1.5168, 550.0), 1.5168, 550.0
        )
        self.assertGreater(bare, 0.04)
        self.assertLess(coated, bare)

    def test_layer_round_trip(self):
        """CoatingLayer dicts should round-trip exactly."""
        layer = CoatingLayer("MgF2", 1.38, 99.64)
        clone = CoatingLayer.from_dict(layer.to_dict())
        self.assertEqual(clone.material, "MgF2")
        self.assertEqual(clone.refractive_index, 1.38)
        self.assertEqual(clone.thickness_nm, 99.64)


class TestCoatingValidation(unittest.TestCase):
    def test_none_and_empty_mean_uncoated(self):
        """None and [] should normalize to None."""
        self.assertIsNone(validate_coating_stack(None))
        self.assertIsNone(validate_coating_stack([]))

    def test_valid_stack_normalizes(self):
        """A valid stack should come back as plain layer dicts."""
        stack = _mgf2_stack()
        result = validate_coating_stack(stack)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["material"], "MgF2")

    def test_missing_key_raises(self):
        """Layers missing required keys should raise."""
        with self.assertRaises(ValidationError):
            validate_coating_stack([{"material": "MgF2"}])

    def test_bad_index_raises(self):
        """Out-of-range indices should raise."""
        with self.assertRaises(ValidationError):
            validate_coating_stack(
                [{"material": "X", "refractive_index": 9.0, "thickness_nm": 100.0}]
            )

    def test_nonpositive_thickness_raises(self):
        """Zero/negative film thickness should raise."""
        with self.assertRaises(ValidationError):
            validate_coating_stack(
                [{"material": "X", "refractive_index": 1.5, "thickness_nm": 0.0}]
            )

    def test_non_list_raises(self):
        """Non-list coatings should raise."""
        with self.assertRaises(ValidationError):
            validate_coating_stack("MgF2")


class TestLensCoatingModel(unittest.TestCase):
    def test_defaults_uncoated(self):
        """New lenses should have no coating."""
        lens = Lens(material="BK7")
        self.assertEqual(lens.get_coating_1(), [])
        self.assertEqual(lens.coating_label(1), "Uncoated")

    def test_set_coating_round_trip(self):
        """Stacks should survive to_dict/from_dict."""
        lens = Lens(material="BK7")
        lens.set_coating(1, _mgf2_stack())
        self.assertEqual(lens.coating_label(1), "MgF2 SLAR")
        clone = Lens.from_dict(lens.to_dict())
        self.assertEqual(clone.coating_label(1), "MgF2 SLAR")

    def test_set_coating_bad_surface_raises(self):
        """Only surfaces 1 and 2 exist."""
        lens = Lens(material="BK7")
        with self.assertRaises(ValueError):
            lens.set_coating(3, _mgf2_stack())

    def test_coated_reflectance_beats_bare(self):
        """A coated surface should reflect less at its design wavelength."""
        lens = Lens(material="BK7")
        bare = lens.coating_reflectance(1, 550.0)
        lens.set_coating(1, _mgf2_stack())
        self.assertLess(lens.coating_reflectance(1, 550.0), bare)

    def test_custom_glass_uses_stored_index(self):
        """Unknown materials must not silently fall back to BK7."""
        lens = Lens(material="Custom", refractive_index=1.713)
        # Bare BK7 would be ~0.0424; n=1.713 gives ~0.0691.
        self.assertAlmostEqual(lens.coating_reflectance(1, 550.0), 0.0691, places=3)


class TestCoatingPersistence(unittest.TestCase):
    def setUp(self):
        self.db, self._path = _make_db()

    def tearDown(self):
        os.unlink(self._path)

    def test_save_and_load_preserves_coatings(self):
        """Standalone lens rows should round-trip coating stacks."""
        lens = Lens(name="Coated", material="BK7")
        lens.set_coating(1, _mgf2_stack())
        self.db.save_lens(lens.to_dict())
        rows = {r["id"]: r for r in self.db.load_all()}
        loaded = Lens.from_dict(rows[lens.id])
        self.assertEqual(loaded.coating_label(1), "MgF2 SLAR")
        self.assertEqual(loaded.get_coating_2(), [])

    def test_assembly_elements_preserve_coatings(self):
        """Assembly element lenses should round-trip coatings."""
        lens = Lens(name="Coated Element", material="BK7")
        lens.set_coating(2, _mgf2_stack())
        system = OpticalSystem(name="Coated System")
        system.add_lens(lens)
        self.db.save_assembly(system.to_dict())
        assemblies = [r for r in self.db.load_all() if r.get("type") == "OpticalSystem"]
        self.assertEqual(len(assemblies), 1)
        element_lens = assemblies[0]["elements"][0]["lens"]
        self.assertEqual(len(element_lens["coating_2"]), 1)
        self.assertEqual(element_lens["coating_2"][0]["material"], "MgF2")

    def test_v4_database_migrates_with_uncoated_defaults(self):
        """A v4 DB should gain coating columns; old rows read uncoated."""
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        path = tmp.name
        try:
            conn = sqlite3.connect(path)
            conn.execute("""
                CREATE TABLE lenses (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL,
                    radius1 REAL NOT NULL, radius2 REAL NOT NULL,
                    thickness REAL NOT NULL, material TEXT NOT NULL,
                    refractive_index REAL, diameter REAL,
                    created_at TEXT, modified_at TEXT,
                    is_parabolic_1 INTEGER NOT NULL DEFAULT 0,
                    parabolic_sag_1 REAL NOT NULL DEFAULT 0.0,
                    is_parabolic_2 INTEGER NOT NULL DEFAULT 0,
                    parabolic_sag_2 REAL NOT NULL DEFAULT 0.0,
                    clear_aperture_1 REAL, clear_aperture_2 REAL,
                    bevel_1 REAL NOT NULL DEFAULT 0.0,
                    bevel_2 REAL NOT NULL DEFAULT 0.0,
                    metadata TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE assemblies (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL,
                    created_at TEXT, modified_at TEXT,
                    aperture_stop_gap INTEGER, aperture_stop_diameter REAL,
                    metadata TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE assembly_elements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    assembly_id TEXT NOT NULL, lens_id TEXT NOT NULL,
                    position REAL NOT NULL, order_index INTEGER NOT NULL,
                    decenter_y REAL NOT NULL DEFAULT 0.0,
                    decenter_z REAL NOT NULL DEFAULT 0.0,
                    tilt_x REAL NOT NULL DEFAULT 0.0,
                    tilt_y REAL NOT NULL DEFAULT 0.0,
                    tilt_z REAL NOT NULL DEFAULT 0.0,
                    FOREIGN KEY (assembly_id) REFERENCES assemblies (id) ON DELETE CASCADE,
                    FOREIGN KEY (lens_id) REFERENCES lenses (id)
                )
            """)
            conn.execute("""
                CREATE TABLE assembly_air_gaps (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    assembly_id TEXT NOT NULL, thickness REAL NOT NULL,
                    position REAL NOT NULL, order_index INTEGER NOT NULL,
                    FOREIGN KEY (assembly_id) REFERENCES assemblies (id) ON DELETE CASCADE
                )
            """)
            conn.execute(
                "INSERT INTO lenses (id, name, radius1, radius2, thickness,"
                " material, metadata) VALUES ('o','O',100,-100,5,'BK7','{}')"
            )
            conn.execute("PRAGMA user_version = 4")
            conn.commit()
            conn.close()
            db = DatabaseManager(path)
            conn = sqlite3.connect(path)
            try:
                self.assertEqual(conn.execute("PRAGMA user_version").fetchone()[0], 5)
            finally:
                conn.close()
            rows = {r["id"]: r for r in db.load_all()}
            lens = Lens.from_dict(rows["o"])
            self.assertEqual(lens.get_coating_1(), [])
            self.assertEqual(lens.coating_label(1), "Uncoated")
        finally:
            os.unlink(path)


class TestCoatingExports(unittest.TestCase):
    def _coated_system(self):
        lens = Lens(
            name="Coated Export",
            radius_of_curvature_1=100.0,
            radius_of_curvature_2=-100.0,
            thickness=5.0,
            diameter=40.0,
            material="BK7",
        )
        lens.set_coating(1, _mgf2_stack())
        system = OpticalSystem(name="Coated Export System")
        system.add_lens(lens)
        return system, lens

    def test_iso_table_shows_coating(self):
        """ISO SVG table should carry per-surface coating labels."""
        from src.io.export import ISO10110Generator

        system, _ = self._coated_system()
        svg = ISO10110Generator(system)._render_svg(800, 600)
        self.assertIn("Coat", svg)
        self.assertIn("MgF2 SLAR", svg)

    def test_step_name_carries_coating(self):
        """STEP solid names should note non-default coatings."""
        from src.io.step_export import StepExporter

        system, _ = self._coated_system()
        with tempfile.NamedTemporaryFile(suffix=".step", delete=False, mode="w") as tmp:
            step_path = tmp.name
        try:
            StepExporter(system).export(step_path)
            with open(step_path) as f:
                content = f.read()
            self.assertIn("coat MgF2 SLAR/Uncoated", content)
        finally:
            os.unlink(step_path)

    def test_zemax_has_coat_lines(self):
        """Zemax surfaces should carry COAT lines when coated."""
        from src.export_formats import ZemaxExporter

        _, lens = self._coated_system()
        with tempfile.NamedTemporaryFile(suffix=".zmx", delete=False, mode="w") as tmp:
            zmx_path = tmp.name
        try:
            ZemaxExporter.export_lens(lens, zmx_path)
            with open(zmx_path) as f:
                content = f.read()
            self.assertIn("COAT MgF2 SLAR", content)
        finally:
            os.unlink(zmx_path)


class TestCoatingGhosts(unittest.TestCase):
    def _system(self, coated):
        lens = Lens(
            name="Ghost Lens",
            radius_of_curvature_1=50.0,
            radius_of_curvature_2=-50.0,
            thickness=10.0,
            diameter=25.0,
            material="BK7",
        )
        if coated:
            lens.set_coating(1, _mgf2_stack())
            lens.set_coating(2, _mgf2_stack())
        system = OpticalSystem(name="Ghost System")
        system.add_lens(lens)
        return system

    def test_coated_ghosts_dimmer(self):
        """Coated ghost pairs should report lower intensity."""
        from src.analysis.ghost import GhostAnalyzer

        bare_ghosts = GhostAnalyzer(self._system(False)).trace_ghosts(num_rays=3)
        coated_ghosts = GhostAnalyzer(self._system(True)).trace_ghosts(num_rays=3)
        self.assertTrue(bare_ghosts)
        self.assertEqual(len(coated_ghosts), len(bare_ghosts))
        for bare, coated in zip(bare_ghosts, coated_ghosts):
            self.assertLess(coated.intensity, bare.intensity)


class TestSeriesECoatingSeed(unittest.TestCase):
    def test_seed_air_surfaces_single_coated(self):
        """Fresh Series E seeds should carry the historic single coat."""
        from src.seed_data import build_nikon_series_e_lenses

        lenses = build_nikon_series_e_lenses()
        # L1 front/back, L4a front, L4b back spot-checks.
        self.assertEqual(lenses[0].coating_label(1), "MgF2 SLAR")
        self.assertEqual(lenses[0].coating_label(2), "MgF2 SLAR")
        self.assertEqual(lenses[3].coating_label(1), "MgF2 SLAR")
        # Cemented interface stays bare.
        self.assertEqual(lenses[3].coating_label(2), "Uncoated")
        self.assertEqual(lenses[4].coating_label(1), "Uncoated")
        self.assertEqual(lenses[4].coating_label(2), "MgF2 SLAR")


if __name__ == "__main__":
    unittest.main()
