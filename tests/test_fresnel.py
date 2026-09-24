import math
import unittest

from src.geometry import LensGeometry
from src.lens import Lens
from src.ray_tracer import LensRayTracer, LensRayTracer3D, Ray, Ray3D
from src.vector3 import vec3


class TestFresnelGeometry(unittest.TestCase):
    def setUp(self):
        self.lens = Lens(
            radius_of_curvature_1=100.0,
            radius_of_curvature_2=-100.0,
            thickness=5.0,
            diameter=20.0,
            refractive_index=1.5,
            is_fresnel=True,
            groove_pitch=2.0,
        )

    def test_facets_follow_radial_pitch(self):
        facets = LensGeometry.fresnel_facets(self.lens, 1)
        self.assertEqual(len(facets), 5)
        self.assertEqual(facets[0].r_start, 0.0)
        self.assertEqual(facets[-1].r_end, 10.0)
        self.assertTrue(all(facet.z_start == 0.0 for facet in facets))

    def test_outline_contains_visible_steps(self):
        profile = LensGeometry.surface_profile(self.lens, 1)
        steps = [
            (first[1], second[1], first[0], second[0])
            for first, second in zip(profile, profile[1:])
            if abs(first[1] - second[1]) < 1e-9
        ]
        self.assertGreaterEqual(len(steps), 4)
        self.assertTrue(any(abs(first_z - second_z) > 1e-6 for _, _, first_z, second_z in steps))

        outline = LensGeometry.lens_outline(self.lens)
        self.assertGreater(len(outline["front"]), 51)
        self.assertTrue(outline["feasible"])

    def test_partial_final_zone_is_retained(self):
        lens = Lens(
            radius_of_curvature_1=100.0,
            radius_of_curvature_2=-100.0,
            thickness=5.0,
            diameter=20.0,
            refractive_index=1.5,
            is_fresnel=True,
            groove_pitch=3.0,
        )
        facets = LensGeometry.fresnel_facets(lens, 1)
        self.assertEqual(len(facets), 4)
        self.assertAlmostEqual(facets[-1].r_start, 9.0)
        self.assertAlmostEqual(facets[-1].r_end, 10.0)


class TestFresnelTracing(unittest.TestCase):
    def setUp(self):
        self.lens = Lens(
            radius_of_curvature_1=100.0,
            radius_of_curvature_2=-100.0,
            thickness=5.0,
            diameter=40.0,
            refractive_index=1.5,
            is_fresnel=True,
            groove_pitch=0.5,
        )
        self.tracer_2d = LensRayTracer(self.lens)
        self.tracer_3d = LensRayTracer3D(self.lens)

    def test_2d_and_3d_faceted_traces_agree(self):
        for height in (0.0, 5.0, 10.0, 19.0):
            with self.subTest(height=height):
                ray_2d = Ray(-50.0, height, 0.0)
                ray_3d = Ray3D(vec3(-50.0, height, 0.0), vec3(1.0, 0.0, 0.0))
                self.tracer_2d.trace_ray(ray_2d)
                self.tracer_3d.trace_ray(ray_3d)

                self.assertFalse(ray_2d.terminated)
                self.assertFalse(ray_3d.terminated)
                self.assertAlmostEqual(ray_2d.x, ray_3d.origin.x, places=7)
                self.assertAlmostEqual(ray_2d.y, ray_3d.origin.y, places=7)
                self.assertAlmostEqual(math.cos(ray_2d.angle), ray_3d.direction.x, places=7)
                self.assertAlmostEqual(math.sin(ray_2d.angle), ray_3d.direction.y, places=7)

    def test_2d_and_3d_agree_on_concave_boundary_facets(self):
        lens = Lens(
            radius_of_curvature_1=-100.0,
            radius_of_curvature_2=100.0,
            thickness=5.0,
            diameter=30.0,
            refractive_index=1.5,
            is_fresnel=True,
            groove_pitch=0.5,
        )
        tracer_2d = LensRayTracer(lens)
        tracer_3d = LensRayTracer3D(lens)
        for height in (-5.0, 5.0):
            with self.subTest(height=height):
                ray_2d = Ray(-50.0, height)
                ray_3d = Ray3D(vec3(-50.0, height, 0.0), vec3(1.0, 0.0, 0.0))
                tracer_2d.trace_ray(ray_2d)
                tracer_3d.trace_ray(ray_3d)
                self.assertAlmostEqual(ray_2d.x, ray_3d.origin.x, places=7)
                self.assertAlmostEqual(ray_2d.y, ray_3d.origin.y, places=7)

    def test_parallel_rays_remain_traceable_and_focus(self):
        rays = self.tracer_2d.trace_parallel_rays(num_rays=9)
        self.assertTrue(all(not ray.terminated for ray in rays))
        focus = self.tracer_2d.find_focal_point(rays)
        self.assertIsNotNone(focus)
        self.assertTrue(math.isfinite(focus[0]))
        self.assertGreater(focus[0], 0.0)

    def test_optical_path_includes_faceted_glass_segment(self):
        ray = Ray(-50.0, 10.0, 0.0)
        self.tracer_2d.trace_ray(ray)
        self.assertGreater(ray.optical_path_length, 0.0)
        self.assertTrue(all(math.isfinite(value) for value in (ray.x, ray.y, ray.angle)))


if __name__ == "__main__":
    unittest.main()
