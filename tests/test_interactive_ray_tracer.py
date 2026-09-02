#!/usr/bin/env python3
"""
InteractiveRayTracer: ray bookkeeping and tracing through a system.
"""

import unittest

from src.lens import Lens
from src.optical_system import OpticalSystem
from src.interactive_ray_tracer import InteractiveRayTracer


class TestInteractiveRayTracer(unittest.TestCase):
    def setUp(self):
        self.system = OpticalSystem(name="irt")
        self.system.add_lens(
            Lens(
                radius_of_curvature_1=100.0,
                radius_of_curvature_2=-100.0,
                thickness=5.0,
                diameter=30.0,
                refractive_index=1.5,
            )
        )
        self.tracer = InteractiveRayTracer(self.system)

    def test_add_ray_traces_at_least_one_segment(self):
        ray = self.tracer.add_ray((-20.0, 0.0, 0.0), (1.0, 0.0, 0.0))
        info = self.tracer.get_ray_info(ray)
        self.assertEqual(info["num_segments"], len(ray.path_segments))
        self.assertGreaterEqual(info["num_segments"], 1)
        self.assertIsNotNone(info["final_position"])

    def test_wavelength_in_nm_converted_to_mm(self):
        ray = self.tracer.add_ray((-20.0, 0.0, 0.0), (1.0, 0.0, 0.0), wavelength=587.6)
        self.assertAlmostEqual(ray.wavelength, 587.6e-6, places=12)

    def test_update_ray_angle_changes_direction(self):
        ray = self.tracer.add_ray((-20.0, 0.0, 0.0), (1.0, 0.0, 0.0))
        before = (
            tuple(ray.direction)
            if not hasattr(ray.direction, "tolist")
            else tuple(ray.direction.tolist())
        )
        self.tracer.update_ray_angle(ray, 10.0)
        after = (
            tuple(ray.direction)
            if not hasattr(ray.direction, "tolist")
            else tuple(ray.direction.tolist())
        )
        self.assertNotEqual(before, after)

    def test_remove_ray_and_clear(self):
        r1 = self.tracer.add_ray((-20.0, 1.0, 0.0), (1.0, 0.0, 0.0))
        self.tracer.add_ray((-20.0, -1.0, 0.0), (1.0, 0.0, 0.0))
        self.assertEqual(len(self.tracer.interactive_rays), 2)
        self.tracer.remove_ray(r1)
        self.assertEqual(len(self.tracer.interactive_rays), 1)
        self.tracer.clear_rays()
        self.assertEqual(len(self.tracer.interactive_rays), 0)
        self.assertEqual(self.tracer.get_all_rays_data(), [])


if __name__ == "__main__":
    unittest.main()
