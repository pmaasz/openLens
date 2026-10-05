#!/usr/bin/env python3
"""
STL surface profiles must not invert a negative radius.

The sag formula already carries the sign - copysign makes the denominator
negative for a negative radius, so z_sag is +sag for R > 0 and -sag for
R < 0. That was followed by

    if is_front:
        if radius < 0: z = -z_sag
    else:
        if radius < 0: z = -z_sag

whose two branches were byte-identical. So is_front had no effect at all, and
the negation simply inverted every negative radius.

Verified for r1=+50, r2=-50, t=5, D=25: the back rim came out at 6.588
instead of 3.412, and because both surfaces then came out identical the
"biconvex" solid was a straight cylinder of constant 5 mm - the 3D-printing
path.
"""

import math
import os
import struct
import tempfile
import unittest

from src.stl_export import STLExporter


def _sag(radius, y):
    """Reference sag, straight from the textbook formula."""
    return (y**2) / (radius + math.copysign(math.sqrt(radius**2 - y**2), radius))


class TestProfileSign(unittest.TestCase):
    def setUp(self):
        self.exporter = STLExporter()

    def test_back_rim_matches_the_expected_sag(self):
        """Regression: 6.588 instead of 3.412."""
        profile = self.exporter.calculate_surface_profile(-50.0, 25.0, is_front=False)
        thickness = 5.0
        self.assertAlmostEqual(profile[-1][1] + thickness, 3.4123, places=3)

    def test_negative_radius_gives_negative_sag(self):
        profile = self.exporter.calculate_surface_profile(-50.0, 25.0)
        self.assertLess(profile[-1][1], 0.0)

    def test_positive_radius_gives_positive_sag(self):
        profile = self.exporter.calculate_surface_profile(50.0, 25.0)
        self.assertGreater(profile[-1][1], 0.0)

    def test_profile_matches_the_closed_form_at_every_step(self):
        for radius in (50.0, -50.0, 120.0, -120.0):
            with self.subTest(radius=radius):
                profile = self.exporter.calculate_surface_profile(radius, 25.0, resolution=8)
                for y, z in profile:
                    self.assertAlmostEqual(z, _sag(radius, y), places=9)

    def test_magnitudes_are_mirror_symmetric(self):
        """A symmetric biconvex needs sag(+R) == -sag(-R)."""
        front = self.exporter.calculate_surface_profile(50.0, 25.0)
        back = self.exporter.calculate_surface_profile(-50.0, 25.0)
        for (y1, z1), (y2, z2) in zip(front, back):
            self.assertAlmostEqual(y1, y2, places=12)
            self.assertAlmostEqual(z1, -z2, places=12)


class TestIsFrontIsInert(unittest.TestCase):
    def setUp(self):
        self.exporter = STLExporter()

    def test_is_front_makes_no_difference(self):
        """The two branches were byte-identical duplicates."""
        for radius in (50.0, -50.0):
            with self.subTest(radius=radius):
                self.assertEqual(
                    self.exporter.calculate_surface_profile(radius, 25.0, is_front=True),
                    self.exporter.calculate_surface_profile(radius, 25.0, is_front=False),
                )

    def test_positional_call_still_works(self):
        """The parameter is kept for API compatibility."""
        self.assertIsNotNone(self.exporter.calculate_surface_profile(50.0, 25.0, True, 10))


class TestEdgeGeometry(unittest.TestCase):
    """The defining property: a biconvex is thinner at the edge than the centre."""

    def setUp(self):
        self.exporter = STLExporter()

    def _rims(self, r1, r2, thickness, diameter=25.0):
        front = self.exporter.calculate_surface_profile(r1, diameter)[-1][1]
        back = self.exporter.calculate_surface_profile(r2, diameter)[-1][1] + thickness
        return front, back

    def test_biconvex_is_thinner_at_the_edge(self):
        front, back = self._rims(50.0, -50.0, 5.0)
        self.assertLess(back - front, 5.0)

    def test_edge_thickness_is_positive(self):
        """The solid must not self-intersect."""
        front, back = self._rims(50.0, -50.0, 5.0)
        self.assertGreater(back - front, 0.0)

    def test_biconcave_is_thicker_at_the_edge(self):
        front, back = self._rims(-50.0, 50.0, 5.0)
        self.assertGreater(back - front, 5.0)

    def test_plano_convex_keeps_full_thickness_at_the_axis(self):
        """A flat front has no sag, so only the back curves."""
        front, back = self._rims(float("inf"), -50.0, 5.0)
        self.assertAlmostEqual(front, 0.0)
        self.assertLess(back - front, 5.0)

    def test_flat_radii_produce_zero_sag(self):
        for radius in (0.0, 1e-12):
            with self.subTest(radius=radius):
                profile = self.exporter.calculate_surface_profile(radius, 25.0)
                self.assertTrue(all(z == 0.0 for _, z in profile))


class TestExportedSolid(unittest.TestCase):
    def _export(self, r1=50.0, r2=-50.0, thickness=5.0, diameter=25.0):
        handle, path = tempfile.mkstemp(suffix=".stl")
        os.close(handle)
        self.addCleanup(os.unlink, path)
        count = STLExporter().export_lens_to_stl(r1, r2, thickness, diameter, path)
        with open(path, "rb") as f:
            return count, f.read()

    def test_still_writes_a_valid_triangle_count(self):
        count, data = self._export()
        self.assertEqual(struct.unpack("<I", data[80:84])[0], count)
        self.assertEqual(len(data), 84 + count * 50)

    def test_solid_spans_the_lens_thickness(self):
        _, data = self._export()
        count = struct.unpack("<I", data[80:84])[0]
        zs = []
        for i in range(count):
            off = 84 + i * 50
            for v in range(3):
                base = off + 12 + v * 12
                zs.append(struct.unpack("<f", data[base + 8 : base + 12])[0])
        self.assertAlmostEqual(min(zs), 0.0, places=4)
        self.assertAlmostEqual(max(zs), 5.0, places=4)

    def test_biconvex_solid_is_not_a_cylinder(self):
        """Regression: constant thickness everywhere meant a straight tube."""
        handle, path = tempfile.mkstemp(suffix=".stl")
        os.close(handle)
        self.addCleanup(os.unlink, path)
        exporter = STLExporter()
        exporter.export_lens_to_stl(50.0, -50.0, 5.0, 25.0, path)

        # Widest radius as a function of z. A cylinder is flat in z; a
        # biconvex peaks at its equator and falls to ~0 at both vertices.
        bins = {}
        for tri in exporter.triangles:
            for x, y, z in tri:
                key = round(z, 1)
                radius = math.hypot(x, y)
                bins[key] = max(bins.get(key, 0.0), radius)

        widest = max(bins.values())
        at_vertices = max(bins.get(round(z, 1), 0.0) for z in (0.0, 5.0))
        self.assertAlmostEqual(widest, 12.5, places=1)
        self.assertLess(at_vertices, widest * 0.5)


if __name__ == "__main__":
    unittest.main()
