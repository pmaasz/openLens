#!/usr/bin/env python3
"""
Tests for the shared lens outline (src/geometry.py).

Lens.get_sag_1/2 is the single source of truth for every sag evaluation
(optimizer, validation, renderers, exporters); LensGeometry.lens_outline
assembles the shared 2D cross-section from those methods. These tests pin
the math and the render/export agreement.
"""

import math
import unittest

from src.constants import (
    COLOR_LENS_BAD,
    COLOR_LENS_FILL,
    COLOR_LENS_R1,
    COLOR_LENS_R2,
    COLOR_LENS_RIM,
)
from src.geometry import LensGeometry
from src.lens import Lens

try:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from src.analysis.plots import draw_system_outline
    from src.optical_system import OpticalSystem

    HAS_MPL = True
except ImportError:
    HAS_MPL = False


def make_lens(**kwargs):
    """Build a BK7-ish test lens with sane defaults."""
    params = {
        "radius_of_curvature_1": 100.0,
        "radius_of_curvature_2": -100.0,
        "thickness": 5.0,
        "diameter": 40.0,
        "refractive_index": 1.5,
    }
    params.update(kwargs)
    return Lens(**params)


class TestSurfaceSag(unittest.TestCase):
    """Unit tests for the single source of truth (Lens.get_sag_1/2)."""

    def test_convex_sag_positive(self):
        """Convex radius gives positive (into-glass) sag."""
        lens = make_lens(radius_of_curvature_1=60.0)
        self.assertAlmostEqual(lens.get_sag_1(20.0), 60.0 - math.sqrt(3600.0 - 400.0), places=9)

    def test_concave_sag_negative(self):
        """Flipping a radius sign mirrors the sag on the same surface."""
        convex = make_lens(radius_of_curvature_1=60.0)
        concave = make_lens(radius_of_curvature_1=-60.0)
        self.assertAlmostEqual(concave.get_sag_1(20.0), -convex.get_sag_1(20.0), places=12)
        # Both surfaces share the sign rule (bulge toward +x is positive).
        back = make_lens(radius_of_curvature_2=60.0)
        self.assertAlmostEqual(back.get_sag_2(20.0), convex.get_sag_1(20.0), places=12)

    def test_flat_sag_zero(self):
        """Zero and infinite radii are flat (sag 0, never NaN)."""
        for flat in (0.0, float("inf"), float("-inf")):
            lens = make_lens(radius_of_curvature_1=flat)
            self.assertEqual(lens.get_sag_1(20.0), 0.0)

    def test_parabolic_sag_quadratic(self):
        """Parabolic sag scales with (y / half_d)^2."""
        lens = make_lens(is_parabolic_1=True, parabolic_sag_1=2.0)
        self.assertAlmostEqual(lens.get_sag_1(20.0), 2.0)
        self.assertAlmostEqual(lens.get_sag_1(10.0), 0.5)

    def test_overhang_clamps_to_hemisphere(self):
        """Aperture beyond |R| clamps instead of producing NaN/sentinel."""
        lens = make_lens(radius_of_curvature_1=20.0, radius_of_curvature_2=-20.0, diameter=50.0)
        sag = lens.get_sag_1(25.0)
        self.assertTrue(math.isfinite(sag))
        self.assertAlmostEqual(sag, 20.0, places=9)
        # ...while the edge is still reported as undefined.
        self.assertIsNone(lens.calculate_edge_thickness())


class TestLensOutline(unittest.TestCase):
    """Tests for the shared vertex-frame outline."""

    def test_vertex_frame(self):
        """Front vertex at 0, back vertex at center thickness."""
        outline = LensGeometry.lens_outline(make_lens())
        self.assertEqual(outline["x1_vertex"], 0.0)
        self.assertEqual(outline["x2_vertex"], 5.0)
        self.assertEqual(len(outline["front"]), 51)
        self.assertEqual(len(outline["back"]), 51)

    def test_rim_matches_vertex_plus_sag(self):
        """Rim points sit exactly on their vertices plus edge sag."""
        lens = make_lens()
        outline = LensGeometry.lens_outline(lens)
        h = lens.diameter / 2
        self.assertAlmostEqual(outline["x1_edge"], lens.get_sag_1(h), places=9)
        self.assertAlmostEqual(outline["x2_edge"], lens.thickness + lens.get_sag_2(h), places=9)

    def test_polyline_is_shared_outline(self):
        """Export polyline is the render outline (single source, exact)."""
        battery = [
            {},
            {"radius_of_curvature_1": -100.0, "radius_of_curvature_2": 100.0},
            {"radius_of_curvature_1": 50.0, "radius_of_curvature_2": 100.0, "diameter": 30.0},
            {"is_parabolic_1": True, "parabolic_sag_1": 2.0},
        ]
        for kwargs in battery:
            with self.subTest(**kwargs):
                lens = make_lens(**kwargs)
                outline = LensGeometry.lens_outline(lens)
                poly = LensGeometry.get_lens_polyline(lens)
                self.assertEqual(poly, outline["front"] + outline["back"])

    def test_polyline_rim_gap_equals_edge(self):
        """Closed loop seals at the rim with exactly the edge thickness."""
        lens = make_lens()
        poly = LensGeometry.get_lens_polyline(lens)
        self.assertEqual(len(poly), 2 * 51)
        # First point (front top rim) and last point (back top rim).
        (x_front, y_front), (x_back, y_back) = poly[0], poly[-1]
        self.assertAlmostEqual(y_front, y_back, places=12)
        self.assertAlmostEqual(x_back - x_front, lens.calculate_edge_thickness(), places=9)

    def test_flat_back_is_straight_wall(self):
        """Plano back surface draws every point at x = thickness."""
        lens = make_lens(radius_of_curvature_2=float("inf"))
        outline = LensGeometry.lens_outline(lens)
        for x, y in outline["back"]:
            self.assertAlmostEqual(x, lens.thickness, places=9)
            self.assertLessEqual(abs(y), lens.diameter / 2)
        self.assertTrue(outline["feasible"])

    def test_infeasible_still_finite(self):
        """Crossed/overhung geometry is flagged but always drawable."""
        crossed = make_lens(
            radius_of_curvature_1=86.63, radius_of_curvature_2=-109.97, diameter=50.0
        )
        outline = LensGeometry.lens_outline(crossed)
        self.assertFalse(outline["feasible"])
        self.assertLess(outline["edge_thickness"], 0)
        overhung = make_lens(radius_of_curvature_1=20.0, radius_of_curvature_2=-20.0, diameter=50.0)
        outline = LensGeometry.lens_outline(overhung)
        self.assertFalse(outline["feasible"])
        self.assertIsNone(outline["edge_thickness"])
        for outline in (
            LensGeometry.lens_outline(crossed),
            LensGeometry.lens_outline(overhung),
        ):
            for x, y in outline["front"] + outline["back"]:
                self.assertTrue(math.isfinite(x))
                self.assertTrue(math.isfinite(y))

    def test_palette_constants_valid(self):
        """Shared palette entries are usable hex colors."""
        for color in (
            COLOR_LENS_FILL,
            COLOR_LENS_R1,
            COLOR_LENS_R2,
            COLOR_LENS_RIM,
            COLOR_LENS_BAD,
        ):
            self.assertRegex(color, r"^#[0-9a-fA-F]{6}$")


@unittest.skipUnless(HAS_MPL, "matplotlib not available")
class TestPlotsAgreement(unittest.TestCase):
    """The ghost/analysis dialog must draw the shared outline exactly."""

    def test_draw_system_outline_matches_helper(self):
        """Line2D data equals lens_outline shifted to the element position."""
        lens = make_lens()
        system = OpticalSystem("t")
        system.add_lens(lens)
        fig, ax = plt.subplots()
        try:
            draw_system_outline(ax, system)
            outline = LensGeometry.lens_outline(lens)
            drawn_x = list(ax.lines[0].get_xdata())
            expected_x = [x for x, _ in outline["front"]]
            self.assertEqual(len(drawn_x), len(expected_x))
            for actual, expected in zip(drawn_x, expected_x):
                self.assertEqual(actual, expected)
        finally:
            plt.close(fig)


if __name__ == "__main__":
    unittest.main()
