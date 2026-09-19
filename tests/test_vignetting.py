"""Tests for physical vignetting: clear apertures, stops, alignment.

Covers the follow-up to todo items 1-2: rays clip at per-surface clear
apertures and at the aperture-stop plane, and decentered/tilted elements
trace through their local frames.

NOTE: exact on-axis (h=0) rays hit sphere vertices degenerately and
terminate even in centered systems -- a pre-existing tracer quirk. These
tests use off-axis heights only.
"""

import math
import unittest

from src.lens import Lens
from src.optical_system import OpticalSystem
from src.ray import Ray, Ray3D, RefractionResult
from src.tracer_2d import LensRayTracer, SystemRayTracer
from src.tracer_3d import LensRayTracer3D, SystemRayTracer3D
from src.vector3 import vec3


def _biconvex(diameter=25.0, **overrides):
    params = {
        "name": "Biconvex",
        "radius_of_curvature_1": 100.0,
        "radius_of_curvature_2": -100.0,
        "thickness": 5.0,
        "diameter": diameter,
        "material": "BK7",
    }
    params.update(overrides)
    return Lens(**params)


def _two_element_system(**lens_overrides):
    system = OpticalSystem(name="Two Element")
    system.add_lens(_biconvex(**lens_overrides))
    system.add_lens(_biconvex(**lens_overrides), air_gap_before=5.0)
    return system


class TestClearApertureTracing2D(unittest.TestCase):
    def test_front_aperture_clips(self):
        """Rays outside the front CA should miss; inside should pass."""
        tracer = LensRayTracer(_biconvex(diameter=40.0, clear_aperture_1=20.0))
        wide = Ray(-100.0, 15.0, 0.0)
        tracer.trace_ray(wide)
        self.assertTrue(wide.terminated)
        self.assertFalse(wide.hit)
        narrow = Ray(-100.0, 5.0, 0.0)
        tracer.trace_ray(narrow)
        self.assertFalse(narrow.terminated)
        self.assertTrue(narrow.hit)

    def test_back_aperture_clips_exiting_ray(self):
        """A ray exiting beyond the back CA should terminate."""
        tracer = LensRayTracer(_biconvex(diameter=40.0, clear_aperture_2=12.0))
        # Steep ray inside the glass, exiting beyond the 6 mm semi-aperture.
        steep = Ray(4.0, 9.0, math.radians(25))
        self.assertIsNone(tracer._intersect_back_surface(steep))
        full = LensRayTracer(_biconvex(diameter=40.0))
        same = Ray(4.0, 9.0, math.radians(25))
        self.assertIsNotNone(full._intersect_back_surface(same))

    def test_unset_aperture_matches_diameter(self):
        """Without CAs the tracer should behave exactly as before."""
        tracer = LensRayTracer(_biconvex(diameter=40.0))
        self.assertEqual(tracer.CA1, 40.0)
        self.assertEqual(tracer.CA2, 40.0)


class TestApertureStopTracing2D(unittest.TestCase):
    def test_stop_vignettes_rim_but_passes_center(self):
        """Rays wider than the stop should terminate at the stop plane."""
        system = _two_element_system()
        system.set_aperture_stop(0, 10.0)
        tracer = SystemRayTracer(system)
        rim = Ray(-100.0, 10.0, 0.0)
        tracer.trace_ray(rim)
        self.assertTrue(rim.terminated)
        # Last point is the stop plane (element 1 back vertex, x = 5).
        self.assertAlmostEqual(rim.path[-1][0], 5.0, places=6)
        core = Ray(-100.0, 2.5, 0.0)
        tracer.trace_ray(core)
        self.assertFalse(core.terminated)
        self.assertTrue(core.hit)

    def test_no_stop_passes_same_rays(self):
        """Without a stop the rim ray should complete the system."""
        system = _two_element_system()
        tracer = SystemRayTracer(system)
        rim = Ray(-100.0, 10.0, 0.0)
        tracer.trace_ray(rim)
        self.assertFalse(rim.terminated)

    def test_unspecified_diameter_does_not_clip(self):
        """A position-only stop (diameter None) should not vignette."""
        system = _two_element_system()
        system.set_aperture_stop(0, None)
        tracer = SystemRayTracer(system)
        rim = Ray(-100.0, 10.0, 0.0)
        tracer.trace_ray(rim)
        self.assertFalse(rim.terminated)


class TestAlignmentTracing2D(unittest.TestCase):
    def test_zero_alignment_is_bit_identical(self):
        """Explicit zeros should trace exactly like an untouched system."""
        plain = _two_element_system()
        aligned = _two_element_system()
        aligned.set_element_alignment(0)
        aligned.set_element_alignment(1)
        paths_plain = [r.path for r in SystemRayTracer(plain).trace_parallel_rays(8)]
        paths_aligned = [r.path for r in SystemRayTracer(aligned).trace_parallel_rays(8)]
        self.assertEqual(paths_plain, paths_aligned)

    def test_decenter_shifts_aperture(self):
        """A decentered element should pass rays centered systems miss."""
        system = OpticalSystem(name="Decentered")
        system.add_lens(_biconvex())
        system.set_element_alignment(0, decenter_y=5.0)
        ray = Ray(-100.0, 14.0, 0.0)
        SystemRayTracer(system).trace_ray(ray)
        self.assertTrue(ray.hit)
        self.assertFalse(ray.terminated)

        centered = OpticalSystem(name="Centered")
        centered.add_lens(_biconvex())
        same = Ray(-100.0, 14.0, 0.0)
        SystemRayTracer(centered).trace_ray(same)
        self.assertTrue(same.terminated)

    def test_tilt_matches_3d_tracer(self):
        """2D tilt (y-meridian) should agree with the 3D transform path."""
        system2d = OpticalSystem(name="Tilt2D")
        system2d.add_lens(_biconvex())
        system2d.set_element_alignment(0, tilt_z=1.0)
        ray = Ray(-100.0, 5.0, 0.0)
        SystemRayTracer(system2d).trace_ray(ray)
        self.assertFalse(ray.terminated)

        system3d = OpticalSystem(name="Tilt3D")
        system3d.add_lens(_biconvex())
        system3d.set_element_alignment(0, tilt_z=1.0)
        ray3 = Ray3D(vec3(-50, 5, 0), vec3(1, 0, 0))
        SystemRayTracer3D(system3d).trace_ray(ray3)
        exit3d = math.degrees(math.atan2(ray3.direction.y, ray3.direction.x))
        self.assertAlmostEqual(math.degrees(ray.angle), exit3d, places=6)


class TestClearApertureTracing3D(unittest.TestCase):
    def test_front_aperture_clips(self):
        """Rays outside the front CA should miss in 3D as well."""
        lens = _biconvex(diameter=40.0, clear_aperture_1=20.0)
        tracer = LensRayTracer3D(lens, x_offset=0.0)
        wide = Ray3D(vec3(-50, 15, 0), vec3(1, 0, 0))
        self.assertIs(tracer.trace_surface(wide, "front", "refract"), RefractionResult.MISSED)
        narrow = Ray3D(vec3(-50, 5, 0), vec3(1, 0, 0))
        self.assertIs(tracer.trace_surface(narrow, "front", "refract"), RefractionResult.REFRACTED)


class TestApertureStopTracing3D(unittest.TestCase):
    def test_stop_vignettes_symmetrically(self):
        """Off-axis fan should lose the rim rays at the stop."""
        system = _two_element_system()
        system.set_aperture_stop(0, 10.0)
        rays = SystemRayTracer3D(system).trace_off_axis_rays(0.0, num_rays=10)
        terminated = [r for r in rays if r.terminated]
        self.assertEqual(len(terminated), 6)
        # Vignetting is symmetric about the axis.
        heights = sorted(round(r.path[0].y, 2) for r in terminated)
        self.assertEqual(heights, [-12.5, -9.72, -6.94, 6.94, 9.72, 12.5])
        # Vignetted rays end at the stop plane (x = 5).
        for ray in terminated:
            self.assertAlmostEqual(ray.path[-1].x, 5.0, places=6)

    def test_no_stop_passes_fan(self):
        """Without a stop the same fan should complete."""
        system = _two_element_system()
        rays = SystemRayTracer3D(system).trace_off_axis_rays(0.0, num_rays=10)
        self.assertFalse(any(r.terminated for r in rays))

    def test_decentered_element_passes_offset_ray(self):
        """Tree-transform alignment should shift the 3D aperture."""
        system = OpticalSystem(name="Decentered3D")
        system.add_lens(_biconvex())
        system.set_element_alignment(0, decenter_y=5.0)
        ray = Ray3D(vec3(-50, 14, 0), vec3(1, 0, 0))
        SystemRayTracer3D(system).trace_ray(ray)
        self.assertFalse(ray.terminated)


if __name__ == "__main__":
    unittest.main()
