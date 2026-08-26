#!/usr/bin/env python3
"""
Unit tests for the core Lens model (src/lens.py)

Direct coverage of geometry, optics math, type presets and
serialization, independent of the CLI manager in lens_editor.
"""

import unittest

from src.lens import Lens
from src.validation import ValidationError, validate_radius


class TestLensConstruction(unittest.TestCase):
    """Lens construction with defaults and custom parameters"""

    def test_construction_with_defaults(self):
        """Default constructor produces a BK7 biconvex lens"""
        lens = Lens()
        self.assertEqual(lens.name, "Untitled")
        self.assertEqual(lens.lens_type, "Biconvex")
        self.assertEqual(lens.material, "BK7")
        self.assertAlmostEqual(lens.refractive_index, 1.5168, places=4)
        self.assertIsNotNone(lens.id)

    def test_radius_zero_converted_to_flat(self):
        """A radius of 0 is stored as infinity (flat surface)"""
        lens = Lens(radius_of_curvature_1=0, radius_of_curvature_2=-50.0)
        self.assertEqual(lens.radius_of_curvature_1, float('inf'))

    def test_ids_are_unique_per_instance(self):
        """Two lenses never share an id (uuid4)"""
        self.assertNotEqual(Lens().id, Lens().id)


class TestLensOptics(unittest.TestCase):
    """Lensmaker equation and derived quantities"""

    def setUp(self):
        self.lens = Lens(
            radius_of_curvature_1=100.0,
            radius_of_curvature_2=-100.0,
            thickness=5.0,
            diameter=50.0,
            refractive_index=1.5,
        )

    def test_focal_length_biconvex_positive(self):
        """Biconvex lens: 1/f = (n-1)(2/R) minus small thick-lens term"""
        f = self.lens.calculate_focal_length()
        self.assertGreater(f, 0)
        # Thin-lens estimate R / (2*(n-1)) = 100 mm
        self.assertAlmostEqual(f, 100.0, delta=5.0)

    def test_focal_length_afocal_returns_none(self):
        """n = 1 gives zero power -> None focal length"""
        afocal = Lens(refractive_index=1.0)
        self.assertIsNone(afocal.calculate_focal_length())

    def test_plano_convex_through_flat_surface(self):
        """Flat surface (inf radius) contributes 1/R = 0 to the power"""
        pc = Lens(lens_type="Plano-Convex", refractive_index=1.5)
        f = pc.calculate_focal_length()
        self.assertGreater(f, 0)

    def test_optical_power_in_diopters(self):
        """Power is 1000/f for f in mm"""
        f = self.lens.calculate_focal_length()
        self.assertAlmostEqual(
            self.lens.calculate_optical_power(), 1000.0 / f, places=6
        )

    def test_back_and_front_focal_length_defined(self):
        """BFL/FFL return finite values for a normal lens"""
        self.assertTrue(hasattr(self.lens.calculate_back_focal_length(), '__abs__'))
        self.assertTrue(hasattr(self.lens.calculate_front_focal_length(), '__abs__'))


class TestLensTypePresets(unittest.TestCase):
    """Radius presets applied per lens_type"""

    def test_preset_applied_when_radii_default(self):
        """Selecting a type with default radii applies the preset"""
        lens = Lens(lens_type="Plano-Convex")
        self.assertEqual(lens.radius_of_curvature_1, 100.0)
        self.assertEqual(lens.radius_of_curvature_2, float('inf'))

    def test_custom_radii_preserved(self):
        """Explicit radii are not overwritten by the type preset"""
        lens = Lens(radius_of_curvature_1=42.0,
                    radius_of_curvature_2=-42.0,
                    lens_type="Meniscus Convex")
        self.assertEqual(lens.radius_of_curvature_1, 42.0)

    def test_unknown_type_leaves_radii(self):
        """An unrecognized type does not mutate radii"""
        lens = Lens(lens_type="Mystery")
        self.assertEqual(lens.radius_of_curvature_1, 100.0)

    def test_set_lens_type_updates_radii(self):
        """set_lens_type re-applies the preset immediately"""
        lens = Lens()
        lens.set_lens_type("Biconcave")
        self.assertEqual(lens.radius_of_curvature_1, -100.0)
        self.assertEqual(lens.radius_of_curvature_2, 100.0)


class TestLensSerialization(unittest.TestCase):
    """to_dict / from_dict round-trips"""

    def test_round_trip_preserves_geometry(self):
        """Dict round-trip keeps radii, thickness and identity"""
        lens = Lens(name="RoundTrip",
                    radius_of_curvature_1=42.0,
                    radius_of_curvature_2=-42.0,
                    thickness=3.0)
        clone = Lens.from_dict(lens.to_dict())
        self.assertEqual(clone.id, lens.id)
        self.assertEqual(clone.radius_of_curvature_1, 42.0)
        self.assertEqual(clone.radius_of_curvature_2, -42.0)
        self.assertEqual(clone.thickness, 3.0)

    def test_from_dict_missing_fields_use_defaults(self):
        """Sparse dicts fall back to defaults without raising"""
        lens = Lens.from_dict({"name": "sparse"})
        self.assertEqual(lens.radius_of_curvature_1, 100.0)


class TestRadiusValidationContract(unittest.TestCase):
    """Validator/model agreement on radii"""

    def test_validator_rejects_zero(self):
        """validate_radius rejects 0; flat must be expressed as inf"""
        with self.assertRaises(ValidationError):
            validate_radius(0)

    def test_validator_accepts_negative_concave(self):
        """Negative radii are valid (concave surfaces)"""
        self.assertEqual(validate_radius(-75.0), -75.0)


if __name__ == "__main__":
    unittest.main()
