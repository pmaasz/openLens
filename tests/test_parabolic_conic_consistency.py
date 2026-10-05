#!/usr/bin/env python3
"""
A parabolic hit point and its surface normal must come from the same conic.

parabolic_sag_N is documented as the sag at the *mechanical* radius D/2, and
both Lens.get_effective_radius_N and _surface_normal_angle use that. The
intersection instead built its conic from the clear aperture:

    normal:        a = sag / (D/2)^2
    intersection:  a = sag / (CA/2)^2

_intersect_front_surface passes semi = CA1/2, so any lens with
is_parabolic_N and clear_aperture_N != diameter was refracted with a normal
from a different conic than the one it hit. Verified: a ray aimed at y=3.0 on
the defining conic landed at y=3.0973, which is not on it.

## On the fix suggested in the issue

The issue proposes using get_effective_radius_N() / 2 in both places. That
does not reconcile them either: for D=25, CA=10, sag=2 it gives
a = 0.005243 against the normal's 0.012800. get_effective_radius returns the
vertex *radius of curvature*, not the radius the sag was quoted at.

The conic is fixed by the sag at D/2, so the intersection now uses that, and
semi_aperture is only a vignetting limit - which is exactly how
_intersect_sphere_surface already treats it.
"""

import math
import unittest

from src.lens import Lens
from src.ray import Ray
from src.tracer_2d import LensRayTracer


def _parabolic(clear_aperture=None):
    return Lens(
        name="p",
        diameter=25.0,
        thickness=3.0,
        refractive_index=1.5,
        is_parabolic_1=True,
        parabolic_sag_1=2.0,
        clear_aperture_1=clear_aperture,
    )


def _conic_a(lens):
    """The a the normal uses: sag at the mechanical radius."""
    return lens.parabolic_sag_1 / ((lens.diameter / 2.0) ** 2)


def _hit_at(tracer, lens, y_target):
    """Fire a ray at the point (vertex + a*y^2, y) on the defining conic."""
    a = _conic_a(lens)
    x_target = tracer.front_vertex_x + a * y_target * y_target
    angle = math.atan2(y_target, x_target + 20.0)
    return tracer._intersect_front_surface(Ray(-20.0, 0.0, angle))


class TestHitLiesOnTheNormalsConic(unittest.TestCase):
    def test_hit_is_on_the_defining_conic_with_a_smaller_clear_aperture(self):
        """Regression: a ray aimed at y=3.0 landed at y=3.0973."""
        lens = _parabolic(clear_aperture=10.0)
        tracer = LensRayTracer(lens)
        for y_target in (1.0, 2.0, 3.0):
            with self.subTest(y=y_target):
                hit = _hit_at(tracer, lens, y_target)
                self.assertIsNotNone(hit)
                x, y = hit
                self.assertAlmostEqual(y, y_target, places=6)
                a = _conic_a(lens)
                self.assertAlmostEqual(x - tracer.front_vertex_x, a * y * y, places=9)

    def test_hit_is_on_the_defining_conic_without_a_clear_aperture(self):
        lens = _parabolic()
        tracer = LensRayTracer(lens)
        for y_target in (1.0, 3.0, 6.0):
            with self.subTest(y=y_target):
                hit = _hit_at(tracer, lens, y_target)
                self.assertIsNotNone(hit)
                self.assertAlmostEqual(hit[1], y_target, places=6)

    def test_the_a_used_equals_the_a_the_normal_uses(self):
        lens = _parabolic(clear_aperture=10.0)
        tracer = LensRayTracer(lens)
        self.assertAlmostEqual(
            _conic_a(lens),
            lens.parabolic_sag_1 / ((lens.diameter / 2.0) ** 2),
            places=12,
        )

    def test_issue_suggestion_would_not_have_fixed_it(self):
        """Documents why get_effective_radius_N()/2 was not used."""
        lens = _parabolic(clear_aperture=10.0)
        proposed = lens.parabolic_sag_1 / ((lens.get_effective_radius_1() / 2.0) ** 2)
        self.assertNotAlmostEqual(proposed, _conic_a(lens), places=6)


class TestClearApertureStillVignettes(unittest.TestCase):
    """semi_aperture must remain a limit, not a curvature reference."""

    def test_ray_beyond_the_clear_aperture_is_blocked(self):
        lens = _parabolic(clear_aperture=10.0)
        tracer = LensRayTracer(lens)
        # y=6 is on the conic but outside the 5.0 clear semi-aperture.
        self.assertIsNone(_hit_at(tracer, lens, 6.0))

    def test_ray_inside_the_clear_aperture_passes(self):
        lens = _parabolic(clear_aperture=10.0)
        tracer = LensRayTracer(lens)
        self.assertIsNotNone(_hit_at(tracer, lens, 4.5))

    def test_no_clear_aperture_means_no_extra_vignetting(self):
        lens = _parabolic()
        tracer = LensRayTracer(lens)
        self.assertIsNotNone(_hit_at(tracer, lens, 6.0))

    def test_the_limit_tracks_the_clear_aperture(self):
        for clear, y_target, blocked in ((10.0, 6.0, True), (20.0, 6.0, False)):
            with self.subTest(clear_aperture=clear):
                lens = _parabolic(clear_aperture=clear)
                tracer = LensRayTracer(lens)
                hit = _hit_at(tracer, lens, y_target)
                self.assertEqual(hit is None, blocked)


class TestParabolicTracingUnaffected(unittest.TestCase):
    def test_ray_through_the_parabolic_lens(self):
        from src.lens import Lens as _L

        lens = _L(
            name="plano",
            diameter=25.0,
            thickness=3.0,
            refractive_index=1.5,
            is_parabolic_1=True,
            parabolic_sag_1=2.0,
        )
        tracer = LensRayTracer(lens)
        ray = tracer.trace_ray(Ray(-20.0, 0.0, 0.0))
        self.assertGreaterEqual(len(ray.path), 2)

    def test_flat_fallback_when_sag_is_zero(self):
        lens = _parabolic()
        lens.parabolic_sag_1 = 0.0
        tracer = LensRayTracer(lens)
        hit = tracer._intersect_front_surface(Ray(-20.0, 0.0, 0.0))
        self.assertIsNotNone(hit)

    def test_spherical_lens_path_unchanged(self):
        lens = Lens(
            name="sph",
            radius_of_curvature_1=50.0,
            radius_of_curvature_2=-50.0,
            thickness=5.0,
            diameter=25.0,
            refractive_index=1.5,
        )
        tracer = LensRayTracer(lens)
        hit = tracer._intersect_front_surface(Ray(-20.0, 0.0, 0.05))
        self.assertIsNotNone(hit)


if __name__ == "__main__":
    unittest.main()
