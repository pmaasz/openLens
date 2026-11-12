#!/usr/bin/env python3
"""
InteractiveRayTracer: ray bookkeeping and tracing through a system.
"""

import unittest

from openlens.lens import Lens
from openlens.optical_system import OpticalSystem
from openlens.interactive_ray_tracer import InteractiveRay, InteractiveRayTracer


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
        ray = self.tracer.add_ray((-20.0, 0.0, 0.0), (1.0, 0.0, 0.0), wavelength_nm=587.6)
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

    def test_wavelength_is_explicit_nanometres(self):
        """#665: 1.5 um (1500 nm) used to be stored as 1.5 nm."""
        ray = self.tracer.add_ray((-20.0, 0.0, 0.0), (1.0, 0.0, 0.0), wavelength_nm=1500.0)

        self.assertAlmostEqual(ray.wavelength, 0.0015, places=12)

    def test_a_sub_millimetre_wavelength_is_not_rescaled(self):
        """0.55 used to mean 0.55 mm; the unit is now unambiguous."""
        ray = self.tracer.add_ray((-20.0, 0.0, 0.0), (1.0, 0.0, 0.0), wavelength_nm=0.55)

        self.assertAlmostEqual(ray.wavelength, 0.55e-6, places=18)

    def test_zero_direction_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "direction"):
            self.tracer.add_ray((-20.0, 0.0, 0.0), (0.0, 0.0, 0.0))

    def test_update_direction_rejects_zero_and_keeps_the_previous_direction(self):
        ray = self.tracer.add_ray((-20.0, 0.0, 0.0), (1.0, 0.0, 0.0))
        before = tuple(ray.direction)

        with self.assertRaisesRegex(ValueError, "direction"):
            self.tracer.update_ray_direction(ray, (0.0, 0.0, 0.0))

        self.assertEqual(tuple(ray.direction), before)

    def test_direct_ray_with_zero_direction_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "direction"):
            InteractiveRay(
                origin=(-20.0, 0.0, 0.0),
                direction=(0.0, 0.0, 0.0),
                wavelength=0.0005876,
                color="red",
                path_segments=[],
            )

    def test_non_positive_wavelength_is_rejected(self):
        for value in (0.0, -587.6, float("nan"), float("inf")):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "wavelength_nm"):
                    self.tracer.add_ray(
                        (-20.0, 0.0, 0.0),
                        (1.0, 0.0, 0.0),
                        wavelength_nm=value,
                    )

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
