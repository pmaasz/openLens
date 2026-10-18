"""Regression: a shifted lens must still receive the requested ray heights.

``trace_parallel_rays`` built its bundle against a hard-coded ``lens_x = 0.0``
and a start plane at ``-RAY_START_OFFSET_MM``, whatever the tracer's
``x_offset`` was. The back-projection that puts a ray at its requested height
at the front surface therefore used the wrong reference plane, so a lens away
from the origin received its fan at the wrong heights.

Repro: a 0-height 5 degree ray for a flat lens at ``x_offset=50`` arrives at
``y = 4.3744 mm`` instead of ``y = 0``.

The system tracer already does this correctly (``start_x = first_pos -
RAY_START_OFFSET_MM``); this brings the single-lens tracer in line.
"""

import math
import unittest

from src.lens import Lens
from src.tracer_2d import LensRayTracer


def _flat_lens():
    return Lens(
        name="Flat",
        radius_of_curvature_1=1e9,
        radius_of_curvature_2=-1e9,
        thickness=5.0,
        diameter=25.0,
        refractive_index=1.5,
    )


def _positive_lens():
    return Lens(
        name="Biconvex",
        radius_of_curvature_1=50.0,
        radius_of_curvature_2=-50.0,
        thickness=5.0,
        diameter=25.0,
        refractive_index=1.5,
    )


class TestParallelRaysArriveAtTheRequestedHeight(unittest.TestCase):
    """The height asked for is the height the ray must reach the lens at."""

    def _arrival_height(self, lens, x_offset, angle_deg, ray_height, **kwargs):
        tracer = LensRayTracer(lens, x_offset=x_offset)
        rays = tracer.trace_parallel_rays(
            angle_deg=angle_deg,
            num_rays=2,
            ray_height_range=(ray_height, ray_height),
            **kwargs,
        )
        ray = rays[0]
        # The bundle is referenced to the vertex plane, so the height is
        # measured there: the ray actually strikes a curved front surface at
        # its sag, and back-projecting to the vertex plane is what "arrives
        # at height h" means. path[1] is the first surface intersection.
        hit_x, hit_y = ray.path[1] if len(ray.path) > 1 else ray.path[0]
        sag = hit_x - tracer.front_vertex_x
        return hit_y - sag * math.tan(math.radians(angle_deg))

    def test_a_zero_height_ray_is_on_axis_for_a_shifted_lens(self):
        """The issue's repro: y = 4.3744 mm instead of y = 0."""
        arrived = self._arrival_height(_flat_lens(), x_offset=50.0, angle_deg=5.0, ray_height=0.0)

        self.assertAlmostEqual(
            arrived,
            0.0,
            places=6,
            msg=f"a 0-height ray arrived at y={arrived:.4f} mm instead of on axis",
        )

    def test_a_zero_height_ray_is_on_axis_at_the_origin_too(self):
        """The unshifted case must keep working."""
        arrived = self._arrival_height(_flat_lens(), x_offset=0.0, angle_deg=5.0, ray_height=0.0)

        self.assertAlmostEqual(arrived, 0.0, places=6)

    def test_every_requested_height_lands_where_asked(self):
        # num_rays=2 rather than 1: with a single ray trace_parallel_rays
        # forces height 0 and ignores ray_height_range entirely.
        for x_offset in (0.0, 25.0, 50.0, -30.0):
            for ray_height in (-10.0, -4.0, 0.0, 4.0, 10.0):
                with self.subTest(x_offset=x_offset, ray_height=ray_height):
                    arrived = self._arrival_height(
                        _positive_lens(),
                        x_offset=x_offset,
                        angle_deg=7.0,
                        ray_height=ray_height,
                    )
                    self.assertAlmostEqual(
                        arrived, ray_height, places=6, msg="the ray missed its height"
                    )

    def test_the_result_does_not_depend_on_the_offset(self):
        """The same design, placed anywhere, must trace identically."""
        heights = []
        for x_offset in (0.0, 50.0):
            tracer = LensRayTracer(_positive_lens(), x_offset=x_offset)
            rays = tracer.trace_parallel_rays(angle_deg=5.0, num_rays=5)
            heights.append([ray.angle_rad for ray in rays])

        self.assertEqual(
            heights[0],
            heights[1],
            msg="moving the lens along the axis changed the traced directions",
        )

    def test_a_curved_lens_shifted_along_the_axis_matches_the_unshifted_one(self):
        """A rigid translation along the optical axis changes nothing."""
        base = LensRayTracer(_positive_lens(), x_offset=0.0)
        shifted = LensRayTracer(_positive_lens(), x_offset=75.0)

        base_rays = base.trace_parallel_rays(angle_deg=5.0, num_rays=7)
        shifted_rays = shifted.trace_parallel_rays(angle_deg=5.0, num_rays=7)

        for index, (a, b) in enumerate(zip(base_rays, shifted_rays)):
            with self.subTest(ray=index):
                self.assertAlmostEqual(a.angle_rad, b.angle_rad, places=9)

    def test_rays_still_start_in_front_of_the_lens(self):
        """A start plane inside the lens would trace backwards."""
        tracer = LensRayTracer(_positive_lens(), x_offset=50.0)

        rays = tracer.trace_parallel_rays(angle_deg=5.0, num_rays=3)

        for index, ray in enumerate(rays):
            with self.subTest(ray=index):
                self.assertLess(
                    ray.path[0][0],
                    tracer.front_vertex_x,
                    msg="the ray starts at or behind the front vertex",
                )

    def test_a_negative_offset_still_starts_in_front(self):
        tracer = LensRayTracer(_positive_lens(), x_offset=-40.0)

        rays = tracer.trace_parallel_rays(angle_deg=5.0, num_rays=3)

        for index, ray in enumerate(rays):
            with self.subTest(ray=index):
                self.assertLess(ray.path[0][0], tracer.front_vertex_x)


class TestSystemTracerAgreement(unittest.TestCase):
    """The system tracer already did this right; keep the two consistent."""

    def test_a_single_element_system_matches_the_lens_tracer(self):
        from src.optical_system import OpticalSystem

        system = OpticalSystem(name="One")
        system.add_lens(_positive_lens(), air_gap_before=40.0)

        element = system.elements[0]
        lens_tracer = LensRayTracer(element.lens, x_offset=element.position)

        lens_rays = lens_tracer.trace_parallel_rays(angle_deg=5.0, num_rays=5)
        system_rays = LensRayTracer(element.lens, x_offset=0.0).trace_parallel_rays(
            angle_deg=5.0, num_rays=5
        )

        # Same lens, so the traced directions must agree regardless of where
        # the element sits; only the start plane differs.
        for index, (a, b) in enumerate(zip(lens_rays, system_rays)):
            with self.subTest(ray=index):
                self.assertAlmostEqual(a.angle_rad, b.angle_rad, places=9)


if __name__ == "__main__":
    unittest.main()
