"""Regression: the 3D paraboloid intersection must be solved at the right vertex.

`_to_local_point` claims to return "the surface-local frame (vertex at
origin)", but its two branches disagree about the origin:

    if self._inv is not None:
        return self._inv.multiply_point(point)   # lens-frame origin
    return point - vertex                        # vertex origin

`_intersect_paraboloid` then solves `x = (y^2 + z^2) / (2R)`, which is only
correct when the vertex really is at x = 0. With a transform set it is not,
so the back surface of a thick lens was solved at the **front** vertex - a
whole thickness too early. The repro: a 5 mm thick plano/parabolic lens exits
at x = 4.99 in 2D, while the equivalent 3D trace stops at the front surface.

The same mismatch made the aperture check use lens-frame y/z rather than
vertex-relative y/z, which is wrong for a decentered lens.

These tests compare against the 2D tracer, which solves the same geometry in
its own frame and is already correct, rather than against hard-coded numbers.
"""

import math
import unittest

from openlens.lens import Lens
from openlens.ray_tracer import Ray, LensRayTracer, Ray3D, LensRayTracer3D
from openlens.transform import Matrix4x4
from openlens.vector3 import vec3


def _parabolic_lens(front=False, back=True, thickness=5.0):
    """A lens whose front or back surface is a paraboloid, the other flat."""
    return Lens(
        radius_of_curvature_1=None if front else math.inf,
        radius_of_curvature_2=None if back else math.inf,
        is_parabolic_1=front,
        parabolic_sag_1=50.0 if front else 0.0,
        is_parabolic_2=back,
        parabolic_sag_2=50.0 if back else 0.0,
        thickness=thickness,
        diameter=40.0,
        refractive_index=1.5,
    )


class TestParaboloidVertexFrame(unittest.TestCase):
    """A thick lens must not solve its back paraboloid at the front vertex."""

    def _trace_2d(self, lens, height):
        tracer = LensRayTracer(lens)
        ray = Ray(x=-50.0, y=height, angle_rad=0.0)
        tracer.trace_ray(ray)
        return ray

    def _trace_3d(self, lens, height):
        tracer = LensRayTracer3D(lens)
        ray = Ray3D(origin=vec3(-50.0, height, 0.0), direction=vec3(1.0, 0.0, 0.0))
        tracer.trace_ray(ray)
        return ray

    def test_thick_lens_with_a_parabolic_back_reaches_the_back_surface(self):
        """The 3D trace must survive a thick lens, as the 2D trace does."""
        lens = _parabolic_lens(front=False, back=True, thickness=5.0)

        ray2d = self._trace_2d(lens, 1.0)
        ray3d = self._trace_3d(lens, 1.0)

        exit_2d = ray2d.path[-1]
        exit_3d = ray3d.path[-1]

        self.assertGreater(exit_2d[0], 4.0, "the 2D trace itself failed; the fixture is wrong")
        self.assertAlmostEqual(
            exit_3d.x,
            exit_2d[0],
            delta=0.05,
            msg=f"3D exited at x={exit_3d.x:.4f}, 2D at {exit_2d[0]:.4f}",
        )

    def test_2d_and_3d_agree_on_a_parabolic_front(self):
        lens = _parabolic_lens(front=True, back=False, thickness=5.0)

        exit_2d = self._trace_2d(lens, 2.0).path[-1]
        exit_3d = self._trace_3d(lens, 2.0).path[-1]

        self.assertAlmostEqual(exit_3d.x, exit_2d[0], delta=0.05)
        self.assertAlmostEqual(exit_3d.y, exit_2d[1], delta=0.05)

    def test_2d_and_3d_agree_on_both_parabolic_surfaces(self):
        lens = _parabolic_lens(front=True, back=True, thickness=8.0)

        exit_2d = self._trace_2d(lens, 1.5).path[-1]
        exit_3d = self._trace_3d(lens, 1.5).path[-1]

        self.assertAlmostEqual(exit_3d.x, exit_2d[0], delta=0.05)
        self.assertAlmostEqual(exit_3d.y, exit_2d[1], delta=0.05)

    def test_exit_height_agrees_over_several_ray_heights(self):
        """Not just on-axis-near: the error scales with the offset."""
        lens = _parabolic_lens(front=False, back=True, thickness=5.0)

        for height in (0.5, 2.0, 5.0, 8.0):
            with self.subTest(height=height):
                exit_2d = self._trace_2d(lens, height).path[-1]
                exit_3d = self._trace_3d(lens, height).path[-1]
                self.assertAlmostEqual(exit_3d.x, exit_2d[0], delta=0.05)


class TestApertureIsVertexRelative(unittest.TestCase):
    """A decentered lens must clip against its own vertex, not the lens origin."""

    def test_decentered_parabolic_back_is_not_clipped_by_the_wrong_aperture(self):
        """With the vertex off-axis, a lens-frame aperture check is wrong."""
        lens = _parabolic_lens(front=False, back=True, thickness=5.0)
        # The transform has to go through the constructor: _calculate_geometry
        # caches the inverse transform there, and it never changes afterwards.
        tracer = LensRayTracer3D(lens, transform=Matrix4x4.from_translation(2.0, 3.0, 0.0))

        ray = Ray3D(origin=vec3(-48.0, 5.0, 0.0), direction=vec3(1.0, 0.0, 0.0))
        tracer.trace_ray(ray)

        exit_point = ray.path[-1]
        self.assertGreater(
            exit_point.x, 4.0, "the ray was lost; the aperture check used the wrong frame"
        )

    def test_ray_outside_the_clear_aperture_is_still_blocked(self):
        """Fixing the frame must not turn the aperture check off entirely."""
        lens = _parabolic_lens(front=False, back=True, thickness=5.0)
        lens.clear_aperture_2 = 2.0  # 2 mm radius at the rim
        tracer = LensRayTracer3D(lens)

        ray = Ray3D(origin=vec3(-50.0, 10.0, 0.0), direction=vec3(1.0, 0.0, 0.0))
        tracer.trace_ray(ray)

        self.assertLessEqual(
            ray.path[-1].x, 4.0, "a ray far outside the clear aperture still got through"
        )


if __name__ == "__main__":
    unittest.main()
