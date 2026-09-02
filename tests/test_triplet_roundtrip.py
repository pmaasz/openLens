#!/usr/bin/env python3
"""
OpticalSystem.save <-> load round-trip through JSON using a triplet.

Guards against to_dict/from_dict asymmetries (dropped fields, lost air
gaps, duplicated lens instances).
"""

import os
import tempfile
import unittest

from src.optical_system import OpticalSystem, create_triplet


class TestTripletRoundTrip(unittest.TestCase):
    """save()/load() fidelity for a three-element system"""

    def setUp(self):
        self.system = create_triplet()

    def _round_trip(self):
        fd, path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        try:
            self.assertTrue(self.system.save(path))
            loaded = OpticalSystem.load(path)
            self.assertIsNotNone(loaded)
            return loaded
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_element_count_preserved(self):
        loaded = self._round_trip()
        self.assertEqual(len(loaded.elements), len(self.system.elements))

    def test_ids_radii_positions_gaps_preserved(self):
        loaded = self._round_trip()
        for orig, copy in zip(self.system.elements, loaded.elements):
            self.assertEqual(copy.lens.id, orig.lens.id)
            self.assertAlmostEqual(
                copy.lens.radius_of_curvature_1,
                orig.lens.radius_of_curvature_1,
                places=9,
            )
            self.assertAlmostEqual(
                copy.lens.radius_of_curvature_2,
                orig.lens.radius_of_curvature_2,
                places=9,
            )
            self.assertAlmostEqual(copy.position, orig.position, places=9)
        self.assertEqual(len(loaded.air_gaps), len(self.system.air_gaps))
        for g_orig, g_copy in zip(self.system.air_gaps, loaded.air_gaps):
            self.assertAlmostEqual(g_copy.thickness, g_orig.thickness, places=9)

    def test_optics_survive_round_trip(self):
        """Loaded system computes the same paraxial BFL as the original"""
        loaded = self._round_trip()
        bfl_orig = self.system.calculate_back_focal_length()
        bfl_loaded = loaded.calculate_back_focal_length()
        self.assertIsNotNone(bfl_orig)
        self.assertAlmostEqual(bfl_loaded, bfl_orig, places=6)

    def test_save_to_unwritable_path_fails_gracefully(self):
        """save() returns False instead of raising on a bad directory"""
        bad = os.path.join(tempfile.gettempdir(), "no_such_dir_openlens_test", "x.json")
        self.assertFalse(self.system.save(bad))


if __name__ == "__main__":
    unittest.main()
