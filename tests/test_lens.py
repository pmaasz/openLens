#!/usr/bin/env python3
"""
Unit tests for the core Lens model (src/lens.py)

Direct coverage of geometry, optics math, type presets and
serialization, independent of the CLI manager in lens_editor.
"""

import unittest

from src.lens import Lens
from src.validation import (
    ValidationError,
    validate_radius,
    check_physical_feasibility,
)


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
        self.assertEqual(lens.radius_of_curvature_1, float("inf"))

    def test_ids_are_unique_per_instance(self):
        """Two lenses never share an id (uuid4)"""
        self.assertNotEqual(Lens().id, Lens().id)

    def test_default_lens_is_feasible(self):
        """Default geometry has positive edge thickness (surfaces do not cross)"""
        lens = Lens()
        edge = lens.calculate_edge_thickness()
        self.assertIsNotNone(edge)
        self.assertGreater(edge, 0)
        feasible, message = check_physical_feasibility(
            lens.radius_of_curvature_1,
            lens.radius_of_curvature_2,
            lens.thickness,
            lens.diameter,
        )
        self.assertTrue(feasible)
        self.assertIsNone(message)

    def test_edge_thickness_none_when_aperture_overhangs(self):
        """|R| < D/2 gives undefined sag, so edge thickness is None"""
        lens = Lens(
            radius_of_curvature_1=20.0,
            radius_of_curvature_2=-20.0,
            thickness=5.0,
            diameter=50.0,
        )
        self.assertIsNone(lens.calculate_edge_thickness())

    def test_edge_thickness_negative_when_surfaces_cross(self):
        """R=86.63/-109.97, t=5, D=50 crosses inside the aperture"""
        lens = Lens(
            radius_of_curvature_1=86.63,
            radius_of_curvature_2=-109.97,
            thickness=5.0,
            diameter=50.0,
        )
        edge = lens.calculate_edge_thickness()
        self.assertIsNotNone(edge)
        self.assertLess(edge, 0)


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
        self.assertAlmostEqual(self.lens.calculate_optical_power(), 1000.0 / f, places=6)

    def test_back_and_front_focal_length_defined(self):
        """BFL/FFL return finite values for a normal lens"""
        self.assertTrue(hasattr(self.lens.calculate_back_focal_length(), "__abs__"))
        self.assertTrue(hasattr(self.lens.calculate_front_focal_length(), "__abs__"))

    def test_front_focal_length_cartesian_sign(self):
        """Converging lens: front focus is left of front vertex (FFL < 0)."""
        biconvex = Lens(
            radius_of_curvature_1=100.0,
            radius_of_curvature_2=-100.0,
            thickness=5.0,
            diameter=40.0,
            refractive_index=1.5168,
        )
        self.assertLess(biconvex.calculate_front_focal_length(), 0)
        self.assertGreater(biconvex.calculate_back_focal_length(), 0)

    def test_symmetric_lens_ffl_mirrors_bfl(self):
        """Symmetric biconvex: FFL = -BFL by mirror symmetry."""
        biconvex = Lens(
            radius_of_curvature_1=100.0,
            radius_of_curvature_2=-100.0,
            thickness=5.0,
            diameter=40.0,
            refractive_index=1.5168,
        )
        self.assertAlmostEqual(
            biconvex.calculate_front_focal_length(),
            -biconvex.calculate_back_focal_length(),
            places=6,
        )

    def test_diverging_lens_ffl_positive(self):
        """Diverging lens: virtual front focus is right of vertex (FFL > 0)."""
        biconcave = Lens(
            radius_of_curvature_1=-100.0,
            radius_of_curvature_2=100.0,
            thickness=5.0,
            diameter=40.0,
            refractive_index=1.5168,
        )
        self.assertGreater(biconcave.calculate_front_focal_length(), 0)
        self.assertLess(biconcave.calculate_back_focal_length(), 0)

    def test_afocal_focal_lengths_are_none(self):
        """Afocal (flat-flat) lens: BFL/FFL are None like the system API."""
        window = Lens(
            radius_of_curvature_1=float("inf"),
            radius_of_curvature_2=float("inf"),
            thickness=5.0,
            diameter=40.0,
            refractive_index=1.5168,
        )
        self.assertIsNone(window.calculate_focal_length())
        self.assertIsNone(window.calculate_back_focal_length())
        self.assertIsNone(window.calculate_front_focal_length())


class TestLensTypePresets(unittest.TestCase):
    """Radius presets applied per lens_type"""

    def test_preset_applied_when_radii_default(self):
        """Selecting a type with use_type_defaults applies the preset"""
        lens = Lens(lens_type="Plano-Convex", use_type_defaults=True)
        self.assertEqual(lens.radius_of_curvature_1, 100.0)
        self.assertEqual(lens.radius_of_curvature_2, float("inf"))

    def test_custom_radii_preserved(self):
        """Explicit radii are not overwritten by the type preset"""
        lens = Lens(
            radius_of_curvature_1=42.0,
            radius_of_curvature_2=-42.0,
            lens_type="Meniscus Convex",
        )
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

    def test_set_lens_type_clears_parabolic(self):
        """Spherical type presets reset parabolic surfaces (exclusive)."""
        lens = Lens(is_parabolic_1=True, parabolic_sag_1=3.0)
        lens.set_lens_type("Biconvex")
        self.assertFalse(lens.is_parabolic_1)
        self.assertFalse(lens.is_parabolic_2)
        self.assertEqual(lens.parabolic_sag_1, 0.0)
        self.assertEqual(lens.parabolic_sag_2, 0.0)

    def test_classify_uses_effective_radii(self):
        """Parabolic shape classifies by sag, not stale spherical radii."""
        lens = Lens(
            radius_of_curvature_1=-100.0,  # stale concave value
            radius_of_curvature_2=-100.0,
            is_parabolic_1=True,
            parabolic_sag_1=2.0,  # convex parabola (R_eff = +100)
        )
        self.assertEqual(lens.classify_lens_type(), "Biconvex")

    def test_every_preset_classifies_as_its_own_type(self):
        """set_lens_type presets must round-trip through classify_lens_type."""
        from src.constants import ALL_LENS_TYPES

        for lens_type in ALL_LENS_TYPES:
            lens = Lens()
            lens.set_lens_type(lens_type)
            self.assertEqual(
                lens.classify_lens_type(),
                lens_type,
                f"Preset for {lens_type} classifies as " f"{lens.classify_lens_type()}",
            )

    def test_meniscus_presets_have_same_sign_radii(self):
        """Meniscus presets need same-sign radii and matching power sign."""
        lens = Lens()
        lens.set_lens_type("Meniscus Convex")
        r1, r2 = lens.radius_of_curvature_1, lens.radius_of_curvature_2
        self.assertGreater(r1, 0)
        self.assertGreater(r2, 0)
        self.assertGreater(lens.calculate_focal_length(), 0)

        lens.set_lens_type("Meniscus Concave")
        r1, r2 = lens.radius_of_curvature_1, lens.radius_of_curvature_2
        self.assertLess(r1, 0)
        self.assertLess(r2, 0)
        self.assertLess(lens.calculate_focal_length(), 0)


class TestLensSerialization(unittest.TestCase):
    """to_dict / from_dict round-trips"""

    def test_round_trip_preserves_geometry(self):
        """Dict round-trip keeps radii, thickness and identity"""
        lens = Lens(
            name="RoundTrip",
            radius_of_curvature_1=42.0,
            radius_of_curvature_2=-42.0,
            thickness=3.0,
        )
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
