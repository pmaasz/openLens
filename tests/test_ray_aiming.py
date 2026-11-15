"""Tests for iterative ray aiming at the aperture stop (#800).

The paraxial entrance-pupil launch is not the bundle the stop passes: a
4 mm stop behind a 40 mm lens clips almost every ray. Aiming solves for the
launch point that crosses the stop at a requested coordinate, keeps the
paraxial launch as the initial guess and the fallback, and leaves the
default (aiming off) bundle untouched.
"""

import unittest

import numpy as np

from openlens.analysis.diffraction_psf import WavefrontSensor
from openlens.analysis.spot_diagram import SpotDiagram
from openlens.constants import NM_TO_MM, WAVELENGTH_GREEN
from openlens.fields import launch_field_ray
from openlens.lens import Lens
from openlens.optical_system import OpticalSystem
from openlens.ray_aiming import (
    DEFAULT_AIM_TOLERANCE_MM,
    RayAimer,
    get_stop_geometry,
    stop_plane_crossing,
)
from openlens.ray_tracer import SystemRayTracer3D

TOLERANCE_MM = 1e-6


def _aperture_system(decenter_y: float = 0.0) -> OpticalSystem:
    """A weak two-lens system whose 4 mm stop sits right after the first lens."""
    system = OpticalSystem(name="Ray-aiming stop")
    system.add_lens(
        Lens(
            name="L1",
            radius_of_curvature_1=200.0,
            radius_of_curvature_2=-200.0,
            thickness=5.0,
            diameter=40.0,
            material="BK7",
        )
    )
    system.add_lens(
        Lens(
            name="L2",
            radius_of_curvature_1=100.0,
            radius_of_curvature_2=-100.0,
            thickness=5.0,
            diameter=30.0,
            material="BK7",
        ),
        air_gap_before=20.0,
    )
    system.set_aperture_stop(0, 4.0)
    if decenter_y:
        system.set_element_alignment(0, decenter_y=decenter_y)
    return system


class TestRayAimer(unittest.TestCase):
    def test_aimed_ray_hits_the_requested_stop_coordinate(self):
        system = _aperture_system()
        stop = get_stop_geometry(system)
        aimer = RayAimer(system, angle_y_deg=10.0)

        for target_y, target_z in ((0.0, 0.0), (1.0, 0.5), (-1.5, -0.5)):
            with self.subTest(target=(target_y, target_z)):
                result = aimer.aim(target_y, target_z)

                self.assertTrue(result.converged)
                self.assertFalse(result.fallback)
                self.assertLessEqual(result.error_mm, DEFAULT_AIM_TOLERANCE_MM)
                hit = stop_plane_crossing(result.ray, stop.x_mm)
                self.assertIsNotNone(hit)
                self.assertAlmostEqual(hit[0], target_y, delta=TOLERANCE_MM)
                self.assertAlmostEqual(hit[1], target_z, delta=TOLERANCE_MM)

    def test_aim_returns_a_traced_ray(self):
        system = _aperture_system()
        result = RayAimer(system).aim(0.0, 0.0)

        self.assertFalse(result.ray.terminated)
        self.assertGreaterEqual(len(result.ray.path), 2)

    def test_non_convergent_aim_falls_back_to_the_paraxial_launch(self):
        system = _aperture_system()
        aimer = RayAimer(system, angle_y_deg=10.0, tolerance_mm=1e-12, max_iterations=1)

        result = aimer.aim(1.0, 0.0)

        self.assertFalse(result.converged)
        self.assertTrue(result.fallback)
        self.assertGreater(result.error_mm, 1e-12)
        self.assertGreaterEqual(len(result.ray.path), 2)

    def test_decentred_element_moves_the_paraxial_stop_hit(self):
        system = _aperture_system(decenter_y=2.0)
        stop = get_stop_geometry(system)
        tracer = SystemRayTracer3D(system)

        paraxial = launch_field_ray(system, angle_y_deg=0.0, pupil_y=0.0)
        tracer.trace_ray(paraxial)
        paraxial_hit = stop_plane_crossing(paraxial, stop.x_mm)

        self.assertIsNotNone(paraxial_hit)
        self.assertGreater(abs(paraxial_hit[0]), 0.01)

        aimed = RayAimer(system, tracer=tracer).aim(0.0, 0.0)

        self.assertTrue(aimed.converged)
        self.assertLessEqual(abs(aimed.stop_y_mm), TOLERANCE_MM)

    def test_system_without_a_stop_returns_the_paraxial_launch(self):
        system = _aperture_system()
        system.clear_aperture_stop()

        result = RayAimer(system, angle_y_deg=10.0).aim(1.0, 0.5)

        self.assertTrue(result.converged)
        self.assertTrue(result.fallback)
        self.assertGreaterEqual(len(result.ray.path), 2)

    def test_invalid_tolerance_raises(self):
        for tolerance in (0.0, -1.0, float("nan")):
            with self.subTest(tolerance=tolerance):
                with self.assertRaises(ValueError):
                    RayAimer(_aperture_system(), tolerance_mm=tolerance)

    def test_invalid_iteration_limit_raises(self):
        with self.assertRaises(ValueError):
            RayAimer(_aperture_system(), max_iterations=0)

    def test_untraced_ray_has_no_stop_crossing(self):
        system = _aperture_system()
        stop = get_stop_geometry(system)
        ray = launch_field_ray(system, angle_y_deg=10.0, pupil_y=2.0)

        self.assertIsNone(stop_plane_crossing(ray, stop.x_mm))


class TestSpotAiming(unittest.TestCase):
    def test_wide_angle_bundle_retains_rays_with_aiming(self):
        spot = SpotDiagram(_aperture_system())

        paraxial = spot.trace_spot(field_angle_y_deg=20.0, num_rings=3, aim_at_stop=False)
        aimed = spot.trace_spot(field_angle_y_deg=20.0, num_rings=3, aim_at_stop=True)

        self.assertLess(paraxial["valid_rays"], 2)
        self.assertGreater(aimed["valid_rays"], 20)
        self.assertGreater(aimed["valid_rays"], 10 * paraxial["valid_rays"])
        self.assertIn("aim_failures", aimed)

    def test_aim_failures_are_counted(self):
        spot = SpotDiagram(_aperture_system())

        result = spot.trace_spot(
            field_angle_y_deg=10.0,
            num_rings=3,
            aim_at_stop=True,
            aim_tolerance_mm=1e-12,
            aim_max_iterations=1,
        )

        self.assertGreater(result["aim_failures"], 0)
        self.assertLess(result["aim_failures"], 40)

    def test_default_off_reproduces_the_paraxial_bundle_exactly(self):
        system = _aperture_system()
        spot = SpotDiagram(system)
        field_angle = 20.0
        rings = 2

        result = spot.trace_spot(field_angle_y_deg=field_angle, num_rings=rings)

        states = []
        for element in system.elements:
            lens = element.lens
            states.append((lens, lens.wavelength, lens.refractive_index))
            lens.update_refractive_index(wavelength_nm=WAVELENGTH_GREEN)

        try:
            tracer = SystemRayTracer3D(system)
            expected = []
            for pupil_y, pupil_z in spot.generate_hexapolar_grid(rings=rings):
                ray = launch_field_ray(
                    system,
                    angle_y_deg=field_angle,
                    pupil_y=pupil_y,
                    pupil_z=pupil_z,
                    wavelength_mm=WAVELENGTH_GREEN * NM_TO_MM,
                )
                tracer.trace_ray(ray)
                if ray.terminated:
                    continue
                t = (result["image_plane_x"] - ray.origin.x) / ray.direction.x
                expected.append(
                    (
                        ray.origin.y + t * ray.direction.y,
                        ray.origin.z + t * ray.direction.z,
                    )
                )
        finally:
            for lens, wavelength, index in states:
                lens.wavelength = wavelength
                lens.refractive_index = index

        self.assertEqual(result["aim_failures"], 0)
        self.assertEqual(len(result["points"]), len(expected))
        for actual, wanted in zip(result["points"], expected):
            self.assertAlmostEqual(actual[0], wanted[0], places=12)
            self.assertAlmostEqual(actual[1], wanted[1], places=12)

    def test_chief_ray_default_matches_the_paraxial_centre_ray(self):
        system = _aperture_system()
        spot = SpotDiagram(system)

        default = spot.trace_chief_ray(field_angle_y_deg=15.0)
        explicit = spot.trace_chief_ray(field_angle_y_deg=15.0, aim_at_stop=False)

        self.assertEqual(default, explicit)

    def test_analysis_exposes_the_aim_failure_count(self):
        from openlens.analysis.psf_mtf import ImageQualityAnalyzer

        analyzer = ImageQualityAnalyzer(_aperture_system())

        analyzer.calculate_spot_diagram(
            field_angle_deg=10.0,
            num_rings=3,
            aim_at_stop=True,
            aim_tolerance_mm=1e-12,
            aim_max_iterations=1,
        )

        self.assertGreater(analyzer.aim_failures, 0)


class TestWavefrontAiming(unittest.TestCase):
    def test_pupil_grid_uses_the_stop_when_aiming(self):
        sensor = WavefrontSensor(_aperture_system())

        paraxial = sensor.get_pupil_wavefront(grid_size=8, aim_at_stop=False)
        aimed = sensor.get_pupil_wavefront(grid_size=8, aim_at_stop=True)

        paraxial_valid = int(np.count_nonzero(~np.isnan(paraxial.W)))
        aimed_valid = int(np.count_nonzero(~np.isnan(aimed.W)))

        self.assertEqual(paraxial_valid, 0)
        self.assertGreaterEqual(aimed_valid, 24)
        self.assertEqual(sensor.aim_failures, 0)

    def test_wavefront_reports_aim_failures(self):
        sensor = WavefrontSensor(_aperture_system())

        sensor.get_pupil_wavefront(
            grid_size=8,
            aim_at_stop=True,
            aim_tolerance_mm=1e-12,
            aim_max_iterations=1,
        )

        self.assertGreater(sensor.aim_failures, 0)


if __name__ == "__main__":
    unittest.main()
