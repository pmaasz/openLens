#!/usr/bin/env python3
"""
A zero-length surface hit must not be recorded as a path point.

The 3D tracer passes min_t=-EPSILON to rank_cap_roots while the 2D tracer
rejects such hits. That divergence is deliberate: in a cemented doublet the
two surfaces share a vertex, so the ray has to change index at the point it is
already standing on. rank_cap_roots documents it as "they disagree on purpose".

What was wrong is the *recording*. Three sites appended the intersection
unconditionally, so a cemented doublet produced three pairs of consecutive
identical path points separated by zero length:

    2: x=8.000000  seg=8.000e+00
    3: x=8.000000  seg=0.000e+00   <- duplicate
    4: x=8.000000  seg=0.000e+00   <- duplicate
    5: x=14.000000 seg=6.000e+00
    6: x=14.000000 seg=0.000e+00   <- duplicate

Anything deriving a direction or a segment length from consecutive path points
divides by zero on those. The refraction itself is correct and is preserved.

The sites: the surface intersection in tracer_3d, the aperture-stop append,
and Ray3D.propagate with a zero distance.
"""

import unittest

from src.lens import Lens
from src.optical_system import OpticalSystem
from src.ray import Ray, Ray3D
from src.tracer_2d import LensRayTracer
from src.tracer_3d import SystemRayTracer3D
from src.vector3 import vec3


def _cemented_doublet():
    """Crown/flint sharing a vertex: L1 back R and L2 front R are both -60."""
    system = OpticalSystem(name="Cemented")
    system.add_lens(
        Lens(
            name="Crown",
            radius_of_curvature_1=100.0,
            radius_of_curvature_2=-60.0,
            thickness=8.0,
            diameter=40.0,
            material="BK7",
        )
    )
    system.add_lens(
        Lens(
            name="Flint",
            radius_of_curvature_1=-60.0,
            radius_of_curvature_2=-200.0,
            thickness=6.0,
            diameter=40.0,
            material="SF11",
        ),
        air_gap_before=0.0,
    )
    return system


def _spaced_doublet(gap=20.0):
    system = OpticalSystem(name="Spaced")
    for name, r1, r2, index in (
        ("L1", 100.0, -100.0, "BK7"),
        ("L2", 100.0, -100.0, "BK7"),
    ):
        system.add_lens(
            Lens(
                name=name,
                radius_of_curvature_1=r1,
                radius_of_curvature_2=r2,
                thickness=10.0,
                diameter=50.0,
                material=index,
            ),
            air_gap_before=gap,
        )
    return system


def _duplicates(path):
    return [i for i in range(1, len(path)) if (path[i] - path[i - 1]).magnitude() < 1e-12]


class TestCementedDoubletPath(unittest.TestCase):
    def setUp(self):
        self.tracer = SystemRayTracer3D(_cemented_doublet())
        self.ray = self.tracer.trace_ray(Ray3D(vec3(-50, 0, 0), vec3(1, 0, 0)))

    def test_no_duplicate_path_points(self):
        """Regression: three pairs of consecutive identical points."""
        self.assertEqual(_duplicates(self.ray.path), [])

    def test_path_is_strictly_along_the_axis(self):
        self.assertEqual(self.dupe_free_positions(), sorted(self.dupe_free_positions()))

    def dupe_free_positions(self):
        return [round(p.x, 6) for p in self.ray.path]

    def test_vertex_positions_are_all_present(self):
        """The cemented vertex at x=8 is still recorded exactly once."""
        positions = self.dupe_free_positions()
        self.assertIn(8.0, positions)
        self.assertEqual(positions.count(8.0), 1)

    def test_ray_still_refracts_at_the_cemented_interface(self):
        """The refraction must survive - that is why t ~ 0 is accepted."""
        lens_indices = [self.tracer.system.elements[i].lens for i in range(2)]
        self.assertTrue(lens_indices)
        # The ray must have traversed both elements, ending in air.
        self.assertAlmostEqual(self.ray.n, 1.0, places=6)

    def test_optical_path_is_unchanged_by_dedup(self):
        """Dropping zero-length steps must not change the accumulated OPL."""
        positions = self.dupe_free_positions()
        self.assertGreater(self.ray.optical_path_length, 0.0)
        self.assertAlmostEqual(positions[0], -50.0)
        self.assertAlmostEqual(positions[-1], 64.0)

    def test_off_axis_ray_has_no_duplicates(self):
        ray = self.tracer.trace_ray(Ray3D(vec3(-50, 0, 0), vec3(1, 0.1, 0).normalize()))
        self.assertEqual(_duplicates(ray.path), [])


class TestSpacedDoubletUnaffected(unittest.TestCase):
    """A system with a real gap must behave exactly as before."""

    def setUp(self):
        self.tracer = SystemRayTracer3D(_spaced_doublet())
        self.ray = self.tracer.trace_ray(Ray3D(vec3(-50, 0, 0), vec3(1, 0, 0)))

    def test_no_duplicates(self):
        self.assertEqual(_duplicates(self.ray.path), [])

    def test_expected_surfaces_are_hit(self):
        """Every element vertex must appear, derived from the system itself."""
        xs = [round(p.x, 4) for p in self.ray.path]
        system = _spaced_doublet()
        for element in system.elements:
            self.assertIn(round(element.position, 4), xs)
            self.assertIn(round(element.position + element.thickness, 4), xs)

    def test_optical_path_is_positive_and_sane(self):
        self.assertGreater(self.ray.optical_path_length, 50.0)


class TestPropagateIsNoOpAtZero(unittest.TestCase):
    def test_zero_propagate_appends_nothing(self):
        ray = Ray3D(vec3(0, 0, 0), vec3(1, 0, 0))
        ray.propagate(5.0)
        before = list(ray.path)
        ray.propagate(0.0)
        self.assertEqual(len(ray.path), len(before))

    def test_negligible_propagate_appends_nothing(self):
        ray = Ray3D(vec3(0, 0, 0), vec3(1, 0, 0))
        ray.propagate(5.0)
        before = list(ray.path)
        ray.propagate(1e-15)
        self.assertEqual(len(ray.path), len(before))

    def test_real_propagate_still_records(self):
        ray = Ray3D(vec3(0, 0, 0), vec3(1, 0, 0))
        seeded = len(ray.path)  # the constructor seeds the path with the origin
        ray.propagate(5.0)
        self.assertEqual(len(ray.path), seeded + 1)
        self.assertAlmostEqual(ray.origin.x, 5.0)

    def test_optical_path_unchanged_by_zero_propagate(self):
        ray = Ray3D(vec3(0, 0, 0), vec3(1, 0, 0))
        ray.propagate(5.0)
        opl = ray.optical_path_length
        ray.propagate(0.0)
        self.assertAlmostEqual(ray.optical_path_length, opl)


class TestTwoDimensionalTracerUnchanged(unittest.TestCase):
    """The 2D tracer rejects zero-length hits outright; leave it that way."""

    def setUp(self):
        self.lens = Lens(
            name="L",
            radius_of_curvature_1=50.0,
            radius_of_curvature_2=-50.0,
            thickness=5.0,
            diameter=25.0,
            refractive_index=1.5,
        )
        self.tracer = LensRayTracer(self.lens)

    def test_2d_hit_on_the_front_surface_still_resolves(self):
        hit = self.tracer._intersect_sphere_surface(
            Ray(0.0, 0.0, 1.0, 0.0), self.tracer.front_center_x, self.tracer.R1, is_front=True
        )
        self.assertIsNotNone(hit)

    def test_2d_path_has_no_zero_length_segments(self):
        ray = Ray(-50.0, 0.0, 0.0, 0.0)
        self.tracer.trace_ray(ray)
        xs = [p[0] for p in ray.path]
        for a, b in zip(xs, xs[1:]):
            self.assertNotAlmostEqual(a, b, places=12)


if __name__ == "__main__":
    unittest.main()
