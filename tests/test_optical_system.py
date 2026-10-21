#!/usr/bin/env python3
"""
Test multi-element optical systems
"""

import unittest
import json
import math
import os
import tempfile

from openlens.optical_system import (
    OpticalSystem,
    create_doublet,
    create_triplet,
)
from openlens.lens import Lens


class TestOpticalSystem(unittest.TestCase):

    def setUp(self):
        # Create some basic lenses for testing
        self.lens1 = Lens(
            name="Lens 1",
            radius_of_curvature_1=100,
            radius_of_curvature_2=-100,
            thickness=10,
            diameter=50,
            material="BK7",
        )
        self.lens2 = Lens(
            name="Lens 2",
            radius_of_curvature_1=80,
            radius_of_curvature_2=-80,
            thickness=8,
            diameter=50,
            material="BK7",
        )

    def test_initialization(self):
        system = OpticalSystem(name="Test System")
        self.assertEqual(system.name, "Test System")
        self.assertEqual(len(system.elements), 0)
        self.assertEqual(len(system.air_gaps), 0)
        self.assertEqual(system.get_total_length(), 0.0)

    def test_add_lens(self):
        system = OpticalSystem()
        system.add_lens(self.lens1)

        self.assertEqual(len(system.elements), 1)
        self.assertEqual(system.elements[0].lens, self.lens1)
        self.assertEqual(system.elements[0].position, 0.0)
        self.assertEqual(system.get_total_length(), 10.0)

        # Add second lens with air gap
        system.add_lens(self.lens2, air_gap_before=20.0)

        self.assertEqual(len(system.elements), 2)
        self.assertEqual(len(system.air_gaps), 1)
        self.assertEqual(system.air_gaps[0].thickness, 20.0)

        # Position check: 0 + 10 (thick) + 20 (gap) = 30
        self.assertEqual(system.elements[1].position, 30.0)
        # Total length: 30 + 8 (thick) = 38
        self.assertEqual(system.get_total_length(), 38.0)

    def test_system_focal_length_two_lenses(self):
        system = OpticalSystem()
        system.add_lens(self.lens1)
        system.add_lens(self.lens2, air_gap_before=20.0)

        calculated_f = system.get_system_focal_length()

        # Exact matrix EFL (-1/C), which accounts for lens thickness and
        # principal-plane offsets that the thin combination
        # 1/f = 1/f1 + 1/f2 - d/(f1*f2) (= 49.31 here) ignores.
        A, B, C, D = system._calculate_system_matrix()
        self.assertIsNotNone(calculated_f)
        self.assertAlmostEqual(calculated_f, -1.0 / C, places=9)

        f1 = self.lens1.calculate_focal_length()
        f2 = self.lens2.calculate_focal_length()
        thin_f = 1 / (1 / f1 + 1 / f2 - 20.0 / (f1 * f2))
        self.assertNotAlmostEqual(calculated_f, thin_f, places=1)

    def test_system_matrix_uses_effective_radii(self):
        """System matrix must honor parabolic sags, not stale raw radii."""
        lens = Lens(
            radius_of_curvature_1=100.0,
            radius_of_curvature_2=-100.0,
            thickness=5.0,
            diameter=25.0,
            refractive_index=1.5,
            is_parabolic_1=True,
            parabolic_sag_1=3.0,
        )
        system = OpticalSystem()
        system.add_lens(lens)

        A, B, C, D = system._calculate_system_matrix()
        # Effective front radius is 26.04, not the stale 100.0.
        self.assertAlmostEqual(-1.0 / C, lens.calculate_focal_length(), places=3)
        self.assertAlmostEqual(
            system.calculate_back_focal_length(),
            lens.calculate_back_focal_length(),
            places=3,
        )

    def test_system_f_number(self):
        """Test system f-number calculation"""
        system = OpticalSystem()
        # Single lens
        system.add_lens(self.lens1)
        f = self.lens1.calculate_focal_length()
        D = self.lens1.diameter
        expected_f_num = f / D

        self.assertAlmostEqual(system.get_system_f_number(), expected_f_num, places=2)

        # Two lenses
        system.add_lens(self.lens2, air_gap_before=20.0)
        f_sys = system.get_system_focal_length()
        # Entrance pupil is still lens1 diameter (approximation used in implementation)
        expected_f_num_sys = abs(f_sys) / D

        self.assertAlmostEqual(system.get_system_f_number(), expected_f_num_sys, places=2)

    def test_achromatic_doublet_creation(self):
        doublet = create_doublet(focal_length=100, diameter=50)

        f_sys = doublet.get_system_focal_length()
        self.assertIsNotNone(f_sys)
        # It's an approximation, so allow some error margin (e.g. 10%)
        self.assertTrue(90 < f_sys < 110, f"Expected ~100mm, got {f_sys}")

    def test_chromatic_aberration(self):
        doublet = create_doublet(focal_length=100, diameter=50)
        chrom = doublet.calculate_chromatic_aberration()

        self.assertIn("longitudinal", chrom)
        self.assertIn("corrected", chrom)

        # Should be corrected (achromatic)
        self.assertTrue(chrom["corrected"])
        self.assertLess(chrom["longitudinal"], 1.0)  # Arbitrary small threshold

    def test_triplet_creation(self):
        triplet = create_triplet(focal_length=100, diameter=50)

        self.assertEqual(len(triplet.elements), 3)
        self.assertEqual(len(triplet.air_gaps), 2)

        f_sys = triplet.get_system_focal_length()
        self.assertIsNotNone(f_sys)
        # Allow wider margin for triplet approximation
        self.assertTrue(50 < f_sys < 150, f"Expected ~100mm, got {f_sys}")

    def test_serialization(self):
        system = OpticalSystem(name="SaveLoadTest")
        system.add_lens(self.lens1)
        system.add_lens(self.lens2, air_gap_before=5.0)

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            system.save(tmp_path)

            # Load back
            loaded_sys = OpticalSystem.load(tmp_path)

            self.assertEqual(loaded_sys.name, system.name)
            self.assertEqual(len(loaded_sys.elements), len(system.elements))
            self.assertEqual(len(loaded_sys.air_gaps), len(system.air_gaps))

            # Check element details
            self.assertEqual(loaded_sys.elements[0].lens.name, system.elements[0].lens.name)
            self.assertEqual(loaded_sys.air_gaps[0].thickness, system.air_gaps[0].thickness)

        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_update_positions(self):
        system = OpticalSystem()
        system.add_lens(self.lens1)  # 10mm thick
        system.add_lens(self.lens2, air_gap_before=5.0)  # 8mm thick

        # Initial checks
        self.assertEqual(system.elements[0].position, 0.0)
        self.assertEqual(system.elements[1].position, 15.0)  # 0 + 10 + 5

        # Modify gap
        system.air_gaps[0].thickness = 10.0
        system._update_positions()

        self.assertEqual(system.elements[1].position, 20.0)  # 0 + 10 + 10


class TestFlatSurfaceRoundTrip(unittest.TestCase):
    """A flat surface must survive the JSON interchange format (#601).

    The model stores a flat surface as an infinite radius, which JSON cannot
    spell: the writer emitted the bare ``Infinity`` literal and the reader
    rejected it, so any system with a plano surface could never be loaded
    back.
    """

    @staticmethod
    def _system(r1, r2):
        system = OpticalSystem(name="Plano")
        system.add_lens(
            Lens(
                name="PlanoLens",
                radius_of_curvature_1=r1,
                radius_of_curvature_2=r2,
                thickness=5.0,
                diameter=25.0,
                material="BK7",
            )
        )
        return system

    def _round_trip(self, system):
        """Save and load the system, returning the loaded system and the path."""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            path = tmp.name
        try:
            self.assertTrue(system.save(path))
            return OpticalSystem.load(path), path
        finally:
            if os.path.exists(path):
                os.remove(path)

    def test_plano_first_surface_round_trips(self):
        """A flat first surface survives save and load"""
        loaded, _ = self._round_trip(self._system(float("inf"), -50.0))
        self.assertIsNotNone(loaded)
        self.assertTrue(math.isinf(loaded.elements[0].lens.radius_of_curvature_1))
        self.assertEqual(loaded.elements[0].lens.radius_of_curvature_2, -50.0)

    def test_plano_second_surface_round_trips(self):
        """A flat second surface survives save and load"""
        loaded, _ = self._round_trip(self._system(50.0, float("inf")))
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.elements[0].lens.radius_of_curvature_1, 50.0)
        self.assertTrue(math.isinf(loaded.elements[0].lens.radius_of_curvature_2))

    def test_both_surfaces_flat_round_trip(self):
        """A plane-parallel plate survives save and load"""
        loaded, _ = self._round_trip(self._system(float("inf"), float("inf")))
        self.assertIsNotNone(loaded)
        self.assertTrue(math.isinf(loaded.elements[0].lens.radius_of_curvature_1))
        self.assertTrue(math.isinf(loaded.elements[0].lens.radius_of_curvature_2))

    def test_written_file_is_valid_json(self):
        """The file the app writes is JSON a strict parser accepts"""
        system = self._system(float("inf"), -50.0)
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            path = tmp.name
        try:
            self.assertTrue(system.save(path))
            with open(path) as handle:
                text = handle.read()
            self.assertNotIn("Infinity", text)
            # A strict parser rejects the bare NaN/Infinity literals.
            json.loads(
                text,
                parse_constant=lambda name: (_ for _ in ()).throw(
                    ValueError(f"non-standard JSON constant: {name}")
                ),
            )
        finally:
            if os.path.exists(path):
                os.remove(path)

    def test_legacy_file_with_infinity_literal_still_loads(self):
        """A file written by an older version (bare Infinity) still loads"""
        payload = {
            "id": "legacy",
            "name": "LegacyPlano",
            "type": "OpticalSystem",
            "elements": [
                {
                    "lens": {
                        "name": "PlanoLens",
                        "radius_of_curvature_1": float("inf"),
                        "radius_of_curvature_2": -50.0,
                        "thickness": 5.0,
                        "diameter": 25.0,
                        "refractive_index": 1.5168,
                    },
                    "position": 0.0,
                }
            ],
            "air_gaps": [],
        }
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            path = tmp.name
        try:
            with open(path, "w") as handle:
                json.dump(payload, handle)
            loaded = OpticalSystem.load(path)
            self.assertIsNotNone(loaded)
            self.assertTrue(math.isinf(loaded.elements[0].lens.radius_of_curvature_1))
        finally:
            if os.path.exists(path):
                os.remove(path)


if __name__ == "__main__":
    unittest.main()
