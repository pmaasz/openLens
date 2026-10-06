#!/usr/bin/env python3
"""
Edge thickness must be judged at the radius the lens is actually polished to.

calculate_edge_thickness documented itself as evaluating "at the clear
aperture" while using `h = self.diameter / 2` - the *mechanical* radius. Its
own first sentence contradicted its third.

A lens is never polished out to its blank, so judging material at
`diameter / 2` assesses a height the finished part does not reach. The failure
mode is a false rejection:

    R1=40, R2=-40, t=2.0, D=30, clear aperture 8

      at the mechanical h=15 : edge = -3.8380  -> "surfaces intersect", REJECTED
      at the real clear h=4  : edge = +1.5990  -> perfectly manufacturable

MIN_EDGE_THICKNESS validation inherited this, via validation.py's probe Lens.
LensGeometry._minimum_thickness had the same assumption in its radius set.

Note check_physical_feasibility owns that probe, not validate_lens_parameters.
"""

import math
import unittest

from src.lens import Lens
from src.validation import check_physical_feasibility, validate_lens_parameters


def _sag(radius, h):
    return h * h / (radius + math.copysign(math.sqrt(radius * radius - h * h), radius))


def _lens(r1=40.0, r2=-40.0, t=2.0, d=30.0, ca1=None, ca2=None):
    return Lens(
        name="L",
        radius_of_curvature_1=r1,
        radius_of_curvature_2=r2,
        thickness=t,
        diameter=d,
        refractive_index=1.5,
        clear_aperture_1=ca1,
        clear_aperture_2=ca2,
    )


class TestManufacturingRadius(unittest.TestCase):
    def test_no_clear_aperture_uses_the_mechanical_radius(self):
        self.assertAlmostEqual(_lens().get_manufacturing_radius(), 15.0)

    def test_smaller_clear_aperture_wins(self):
        self.assertAlmostEqual(_lens(ca1=8.0, ca2=8.0).get_manufacturing_radius(), 4.0)

    def test_the_smaller_of_the_two_clear_apertures_wins(self):
        self.assertAlmostEqual(_lens(ca1=20.0, ca2=8.0).get_manufacturing_radius(), 4.0)

    def test_clear_aperture_larger_than_mechanical_is_clamped(self):
        """The blank cannot be polished beyond its own diameter."""
        self.assertAlmostEqual(_lens(ca1=40.0, ca2=40.0).get_manufacturing_radius(), 15.0)

    def test_only_one_clear_aperture_set(self):
        self.assertAlmostEqual(_lens(ca1=8.0, ca2=None).get_manufacturing_radius(), 4.0)

    def test_non_positive_clear_aperture_is_ignored(self):
        self.assertAlmostEqual(_lens(ca1=0.0, ca2=-1.0).get_manufacturing_radius(), 15.0)


class TestEdgeThicknessUsesTheRealAperture(unittest.TestCase):
    def test_matches_a_hand_computed_edge(self):
        lens = _lens(ca1=8.0, ca2=8.0)
        h = 4.0
        expected = lens.thickness - _sag(40.0, h) + _sag(-40.0, h)
        self.assertAlmostEqual(lens.calculate_edge_thickness(), expected, places=9)

    def test_manufacturable_lens_is_not_judged_at_the_blank(self):
        """Regression: edge -3.84 at h=15, so the lens was rejected."""
        lens = _lens(ca1=8.0, ca2=8.0)
        self.assertGreater(lens.calculate_edge_thickness(), 0.0)

    def test_mechanical_evaluation_would_have_been_negative(self):
        """Pins that the test case actually exercises the bug."""
        lens = _lens(ca1=8.0, ca2=8.0)
        h = lens.diameter / 2
        at_blank = lens.thickness - _sag(40.0, h) + _sag(-40.0, h)
        self.assertLess(at_blank, 0.0)

    def test_no_clear_aperture_is_unchanged(self):
        lens = _lens(r1=100.0, r2=-100.0, t=8.0, d=25.0)
        h = 12.5
        expected = lens.thickness - _sag(100.0, h) + _sag(-100.0, h)
        self.assertAlmostEqual(lens.calculate_edge_thickness(), expected, places=9)

    def test_default_lens_still_has_positive_edge(self):
        self.assertGreater(Lens().calculate_edge_thickness(), 0.0)

    def test_none_when_the_aperture_overhangs_a_surface(self):
        """Undefined sag must still return None, not a number."""
        lens = _lens(r1=20.0, r2=-20.0, t=5.0, d=50.0)
        self.assertIsNone(lens.calculate_edge_thickness())


class TestFeasibilityHonoursTheClearAperture(unittest.TestCase):
    def test_false_rejection_is_fixed(self):
        feasible, message = check_physical_feasibility(
            40.0, -40.0, 2.0, 30.0, clear_aperture_1=8.0, clear_aperture_2=8.0
        )
        self.assertTrue(feasible)
        self.assertIsNone(message)

    def test_without_a_clear_aperture_it_is_still_rejected(self):
        """Same lens, judged at the blank - genuinely not manufacturable there."""
        feasible, message = check_physical_feasibility(40.0, -40.0, 2.0, 30.0)
        self.assertFalse(feasible)
        self.assertIn("intersect", message)

    def test_default_lens_remains_feasible(self):
        lens = Lens()
        feasible, message = check_physical_feasibility(
            lens.radius_of_curvature_1,
            lens.radius_of_curvature_2,
            lens.thickness,
            lens.diameter,
        )
        self.assertTrue(feasible)
        self.assertIsNone(message)

    def test_validate_lens_parameters_accepts_the_clear_apertures(self):
        result = validate_lens_parameters(
            40.0, -40.0, 2.0, 30.0, 1.5, clear_aperture_1=8.0, clear_aperture_2=8.0
        )
        self.assertIsInstance(result, dict)


class TestGeometryMinimumThickness(unittest.TestCase):
    def test_renders_and_reports_a_thickness(self):
        from src.geometry import LensGeometry

        lens = _lens(r1=100.0, r2=-100.0, t=8.0, d=25.0, ca1=10.0, ca2=10.0)
        thickness = LensGeometry._minimum_thickness(lens)
        self.assertIsNotNone(thickness)


if __name__ == "__main__":
    unittest.main()
