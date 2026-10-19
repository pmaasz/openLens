"""Regression: the STL exporter must produce a closed, correctly wound solid.

Three defects made every exported solid unusable in a slicer or mesh tool:

- `generate_edge_triangles` still contained a debug leftover,
  `triangles.append((p1, p3, p2))  # 1-3-2?`, ahead of the two correct
  triangles. It added one extra inverted triangle per edge segment, so the
  shell was not closed.
- `generate_surface_triangles` wound front and back surfaces the same way, so
  the front surface's normals pointed *into* the glass.
- a spherical sag that raised (|R| < D/2, no real surface at that radius) was
  caught and silently replaced with 0.0, flattening the geometry without
  telling anyone.

These tests use objective criteria rather than counting triangles: a closed
manifold has every undirected edge shared by exactly two triangles, and the
signed volume of a correctly wound solid is the lens's real volume. A stray
inverted triangle or a flipped cap changes both.
"""

import math
import os
import tempfile
import unittest
from collections import defaultdict

from openlens.stl_export import STLExporter


def _triangle_normal(tri):
    (x1, y1, z1), (x2, y2, z2), (x3, y3, z3) = tri
    ux, uy, uz = x2 - x1, y2 - y1, z2 - z1
    vx, vy, vz = x3 - x1, y3 - y1, z3 - z1
    nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
    length = math.sqrt(nx * nx + ny * ny + nz * nz)
    return (nx / length, ny / length, nz / length) if length else (0.0, 0.0, 0.0)


def _signed_volume(triangles):
    """Divergence-theorem volume. Positive means outward-facing winding."""
    total = 0.0
    for (x1, y1, z1), (x2, y2, z2), (x3, y3, z3) in triangles:
        total += x1 * (y2 * z3 - y3 * z2) - y1 * (x2 * z3 - x3 * z2) + z1 * (x2 * y3 - x3 * y2)
    return total / 6.0


def _undirected_edge_use(triangles):
    """Count how many triangles reference each undirected edge."""
    counts = defaultdict(int)
    for tri in triangles:
        for a, b in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
            counts[(a, b) if a <= b else (b, a)] += 1
    return counts


def _lens_triangles(r1=100.0, r2=-100.0, thickness=5.0, diameter=25.0, resolution=25):
    with tempfile.TemporaryDirectory() as folder:
        exporter = STLExporter()
        exporter.export_lens_to_stl(
            r1,
            r2,
            thickness,
            diameter,
            filename=os.path.join(folder, "lens.stl"),
            resolution=resolution,
        )
        return exporter.triangles


class TestShellIsClosed(unittest.TestCase):
    """A printable solid must have no open or over-shared edges."""

    def test_no_boundary_edges(self):
        """Every edge must be shared by exactly two triangles.

        An odd count means a hole in the shell - which is exactly what the
        stray debug triangle caused, since it referenced edges no other
        triangle closed.
        """
        triangles = _lens_triangles()

        counts = _undirected_edge_use(triangles)
        boundary = [edge for edge, n in counts.items() if n != 2]

        self.assertEqual(
            len(boundary),
            0,
            f"{len(boundary)} edges are not shared by exactly two triangles "
            f"(first: {boundary[0] if boundary else None})",
        )

    def test_every_directed_edge_is_paired_with_its_reverse(self):
        """A closed oriented shell traverses each edge once in each direction.

        This is what catches an inverted triangle: it reverses a directed edge
        that another triangle already owns, leaving the pair unmatched.
        """
        triangles = _lens_triangles()

        directed = defaultdict(int)
        for tri in triangles:
            for a, b in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
                directed[(a, b)] += 1

        unpaired = [
            edge
            for edge, n in directed.items()
            if n != 1 or directed.get((edge[1], edge[0]), 0) != 1
        ]

        self.assertEqual(
            len(unpaired),
            0,
            f"{len(unpaired)} directed edges are not paired with their reverse "
            f"(first: {unpaired[0] if unpaired else None})",
        )


class TestWindingAndVolume(unittest.TestCase):
    """Winding must be consistent, and the volume must be the real one."""

    def test_signed_volume_is_positive(self):
        """A consistently outward-wound solid encloses positive volume."""
        volume = _signed_volume(_lens_triangles())

        self.assertGreater(volume, 0.0, "the solid is wound inside-out")

    def test_signed_volume_matches_the_analytic_lens_volume(self):
        """r=100/-100, t=5, D=25 is ~2070 mm^3.

        The exact solid of revolution is not a simple sphere cap, so this
        checks the exported mesh against a reference computed from the same
        profile - close enough that a stray or inverted triangle, which is
        roughly a whole segment's worth of volume, cannot hide in the noise.
        """
        triangles = _lens_triangles()
        volume = _signed_volume(triangles)

        # Reference: revolve the same profile numerically.
        exporter = STLExporter()
        steps = 2000
        reference = _revolved_volume(exporter, 100.0, -100.0, 5.0, 25.0, steps)

        self.assertAlmostEqual(
            volume,
            reference,
            delta=abs(reference) * 0.02,
            msg=f"exported volume {volume:.1f} mm^3 vs reference {reference:.1f} mm^3",
        )

    def test_front_surface_normals_point_away_from_the_glass(self):
        """The front cap must face -Z, not into the body."""
        triangles = _lens_triangles()

        # Front cap triangles are the ones lying entirely in the z ~ 0 region,
        # near the front vertex.
        front = [tri for tri in triangles if max(abs(p[2] - 0.0) for p in tri) < 1.0]
        self.assertTrue(front, "no front-surface triangles were found")

        wrong = [tri for tri in front if _triangle_normal(tri)[2] > 0]

        self.assertEqual(
            len(wrong),
            0,
            f"{len(wrong)} of {len(front)} front-surface triangles face +Z " "(into the glass)",
        )

    def test_back_surface_normals_point_away_from_the_glass(self):
        """The back cap must face +Z."""
        triangles = _lens_triangles()
        back_z = max(max(p[2] for p in tri) for tri in triangles)

        back = [tri for tri in triangles if min(p[2] for p in tri) > back_z - 1.0]
        self.assertTrue(back, "no back-surface triangles were found")

        wrong = [tri for tri in back if _triangle_normal(tri)[2] < 0]

        self.assertEqual(
            len(wrong), 0, f"{len(wrong)} of {len(back)} back-surface triangles face -Z"
        )


class TestImpossibleSagIsNotSilentlyFlattened(unittest.TestCase):
    """A surface with no real radius at the requested diameter must say so."""

    def test_raises_when_the_diameter_exceeds_the_radius(self):
        """|R| < D/2 has no spherical surface at that rim.

        The sag formula raises here, and the old code swallowed it and used
        0.0, silently exporting a flat disc where a lens surface should be.
        """
        with self.assertRaises(ValueError):
            _lens_triangles(r1=10.0, r2=-10.0, diameter=25.0, resolution=10)

    def test_a_flat_surface_is_still_allowed(self):
        """A genuinely flat surface is |R| ~ 0, not an error."""
        triangles = _lens_triangles(r1=0.0, r2=0.0, diameter=25.0, resolution=10)

        self.assertTrue(triangles)


def _revolved_volume(exporter, r1, r2, thickness, diameter, steps):
    """Exact volume of the lens by revolution: int 2*pi*y*(z_back - z_front) dy.

    The reference is taken from the same analytic profile the exporter uses, so
    it checks the triangulation and winding rather than the sag formula. For
    r=100/-100, t=5, D=25 this is ~2070 mm^3.
    """
    front = exporter.calculate_surface_profile(r1, diameter, is_front=True, resolution=steps)
    back = exporter.calculate_surface_profile(r2, diameter, is_front=False, resolution=steps)

    total = 0.0
    for index in range(steps):
        y0, zf0 = front[index]
        y1, zf1 = front[index + 1]
        _, zb0 = back[index]
        _, zb1 = back[index + 1]

        # Thickness between the two surfaces at each end of the radial step,
        # then integrate the shell of revolution by Simpson's rule.
        t0 = (thickness + zb0) - zf0
        t1 = (thickness + zb1) - zf1
        total += 2 * math.pi * (y0 + y1) / 2.0 * (y1 - y0) * (t0 + t1) / 2.0

    return total


if __name__ == "__main__":
    unittest.main()
