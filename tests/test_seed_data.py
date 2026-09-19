"""Tests for src/seed_data.py — Nikon Series E 50mm example seeding."""

import os
import tempfile
import unittest

from src.database import DatabaseManager
from src.seed_data import (
    NIKON_SERIES_E_ASSEMBLY_ID,
    NIKON_SERIES_E_LENS_IDS,
    build_nikon_series_e_lenses,
    build_nikon_series_e_system,
    ensure_nikon_series_e_example,
    is_nikon_series_e_seeded,
)


def _make_db():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    return DatabaseManager(tmp.name), tmp.name


class TestNikonSeriesEPrescription(unittest.TestCase):
    def test_build_returns_six_lenses_with_stable_ids(self):
        """Builder should return six lenses with the documented stable IDs."""
        lenses = build_nikon_series_e_lenses()
        self.assertEqual(len(lenses), 6)
        self.assertEqual([lens.id for lens in lenses], NIKON_SERIES_E_LENS_IDS)

    def test_all_seed_lenses_have_realizable_geometry(self):
        """Every seed element should have positive edge thickness."""
        for lens in build_nikon_series_e_lenses():
            edge = lens.calculate_edge_thickness()
            self.assertIsNotNone(edge)
            self.assertGreater(edge, 0)

    def test_system_focal_length_matches_50mm_design(self):
        """Assembly EFL should be ~50mm with SLR back focus ~37.5mm."""
        system = build_nikon_series_e_system()
        self.assertEqual(system.id, NIKON_SERIES_E_ASSEMBLY_ID)
        self.assertEqual(len(system.elements), 6)
        efl = system.get_system_focal_length()
        self.assertAlmostEqual(efl, 50.0, delta=0.5)
        self.assertAlmostEqual(system.calculate_back_focal_length(), 37.5, delta=0.5)
        self.assertAlmostEqual(system.get_total_length(), 27.615, places=3)

    def test_cemented_doublet_has_zero_gap(self):
        """L4a-L4b should be cemented (zero air gap)."""
        system = build_nikon_series_e_system()
        self.assertEqual(len(system.air_gaps), 5)
        self.assertAlmostEqual(system.air_gaps[3].thickness, 0.0)


class TestEnsureSeedData(unittest.TestCase):
    def setUp(self):
        self.db, self._path = _make_db()

    def tearDown(self):
        os.unlink(self._path)

    def test_ensure_inserts_lenses_and_assembly(self):
        """Ensure should materialize six lenses plus one assembly."""
        self.assertFalse(is_nikon_series_e_seeded(self.db))
        self.assertTrue(ensure_nikon_series_e_example(self.db))
        self.assertTrue(is_nikon_series_e_seeded(self.db))
        ids = self.db.all_ids()
        for lid in NIKON_SERIES_E_LENS_IDS:
            self.assertIn(lid, ids["lenses"])
        self.assertIn(NIKON_SERIES_E_ASSEMBLY_ID, ids["assemblies"])

    def test_ensure_is_idempotent(self):
        """Second ensure should report no work done."""
        ensure_nikon_series_e_example(self.db)
        self.assertFalse(ensure_nikon_series_e_example(self.db))
        ids = self.db.all_ids()
        self.assertEqual(len([i for i in ids["lenses"] if i in NIKON_SERIES_E_LENS_IDS]), 6)

    def test_ensure_does_not_overwrite_user_edits(self):
        """Pre-existing seed lens rows should keep user modifications."""
        from src.lens import Lens

        edited = Lens(
            name="My custom L1",
            radius_of_curvature_1=45.4915,
            radius_of_curvature_2=612.3255,
            thickness=3.39,
            diameter=28.0,
            refractive_index=1.713,
            material="Custom",
        )
        edited.id = NIKON_SERIES_E_LENS_IDS[0]
        self.db.save_lens(edited.to_dict())

        ensure_nikon_series_e_example(self.db)

        rows = {r["id"]: r for r in self.db.load_all()}
        self.assertEqual(rows[NIKON_SERIES_E_LENS_IDS[0]]["name"], "My custom L1")
        self.assertTrue(is_nikon_series_e_seeded(self.db))

    def test_seeded_assembly_loads_with_correct_gaps(self):
        """Seeded assembly should round-trip with patent air gaps."""
        ensure_nikon_series_e_example(self.db)
        assemblies = [r for r in self.db.load_all() if r.get("type") == "OpticalSystem"]
        seed = [a for a in assemblies if a["id"] == NIKON_SERIES_E_ASSEMBLY_ID]
        self.assertEqual(len(seed), 1)
        self.assertEqual(len(seed[0]["elements"]), 6)
        gaps = [g["thickness"] for g in seed[0]["air_gaps"]]
        self.assertEqual(gaps, [0.095, 1.55, 8.82, 0.0, 0.095])


if __name__ == "__main__":
    unittest.main()
