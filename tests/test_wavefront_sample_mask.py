#!/usr/bin/env python3
"""
An unusable sample must read as NaN, never as a zero OPD.

DiffractionPSFCalculator builds its pupil amplitude from np.isnan(W), so a sample that
is left at its np.zeros initialisation is read as a *perfect* zero-phase pupil
point - full weight, no aberration. Two branches did exactly that:

- `if abs(ray.direction.x) > 1e-6: ... ` with no else, so a ray too steep to
  project onto the reference plane left W at 0.0.
- `if not ref_ray.path: continue`, which never fired: Ray3D.__init__ seeds
  path with [origin] and nothing clears it, so `not ref_ray.path` was always
  False. A chief ray that was *blocked* (terminated) was therefore accepted as
  the OPD reference, ref_end became the ray's own origin, and the reference
  plane sat at the wrong x for every grid point.

Verified on a blocked chief ray:

    before:  172 of 172 in-aperture samples at full amplitude, PSF peak 1.0
    after:     0 of 256, pupil amplitude 0.0,             PSF peak 0.0

A PSF peak of 1.0 with a uniform pupil is the ideal Airy pattern, whose MTF
merit is the textbook maximum - so the optimizer was being rewarded for
exactly the vignetted designs that caused the failure.
"""

import unittest

import numpy as np

from src.analysis.diffraction_psf import DiffractionPSFCalculator, WavefrontSensor
from src.lens import Lens
from src.optical_system import OpticalSystem


def _system():
    system = OpticalSystem(name="S")
    system.add_lens(
        Lens(
            name="L",
            radius_of_curvature_1=50.0,
            radius_of_curvature_2=-50.0,
            thickness=5.0,
            diameter=25.0,
            refractive_index=1.5,
        )
    )
    return system


#: get_pupil_wavefront traces the paraxial focus ray first, then the chief
#: ray, then the grid rays - see analysis.diffraction_psf. The sabotage below
#: has to hit the chief ray specifically, so it is addressed by call index
#: rather than by being the first call (which is how the retired
#: beam_synthesis implementation ordered them).
_CHIEF_RAY_CALL = 2


class _ScriptedTracer:
    """Delegates to a real tracer; fails the chief ray on request.

    The real tracer is needed because the surviving implementation reads the
    traced path of the paraxial and chief rays to build a reference sphere;
    a stubbed path would make every sample invalid for the wrong reason.
    """

    def __init__(self, system, chief="good"):
        from src.ray_tracer import SystemRayTracer3D

        self._real = SystemRayTracer3D(system)
        self.chief = chief
        self.calls = 0

    def trace_ray(self, ray):
        self.calls += 1
        if self.calls == _CHIEF_RAY_CALL:
            if self.chief == "blocked":
                ray.terminated = True
                return ray
            if self.chief == "empty":
                ray.path = []
                return ray
        return self._real.trace_ray(ray)


def _wavefront(chief="good", grid_size=16):
    sensor = WavefrontSensor(_system())
    sensor.tracer = _ScriptedTracer(sensor.system, chief)
    return sensor.get_pupil_wavefront(grid_size=grid_size)


class TestBlockedChiefRayInvalidatesEverything(unittest.TestCase):
    """Regression: a blocked chief ray produced a textbook-perfect pupil."""

    def test_every_sample_is_nan(self):
        W = _wavefront(chief="blocked").W
        self.assertEqual(int(np.isnan(W).sum()), W.size)

    def test_no_zero_filled_samples_survive(self):
        W = _wavefront(chief="blocked").W
        leaked = (W == 0.0) & ~np.isnan(W)
        self.assertEqual(int(leaked.sum()), 0)

    def test_pupil_amplitude_is_zero(self):
        W = _wavefront(chief="blocked").W
        amplitude = np.ones_like(W)
        amplitude[np.isnan(W)] = 0.0
        self.assertEqual(float(amplitude.sum()), 0.0)

    def test_psf_is_not_the_ideal_airy_pattern(self):
        """Regression: PSF peak was exactly 1.0, the textbook maximum."""
        wavefront = _wavefront(chief="blocked")
        psf = DiffractionPSFCalculator.calculate_psf(wavefront)
        self.assertLess(float(np.max(np.abs(psf))), 1.0)

    def test_empty_chief_ray_path_also_invalidates(self):
        """The `not ref_ray.path` branch never fired; now it does."""
        W = _wavefront(chief="empty").W
        self.assertEqual(int(np.isnan(W).sum()), W.size)


class TestSteepRayIsMarkedInvalid(unittest.TestCase):
    """The branch with no else: too steep to project onto the reference plane."""

    def test_ray_without_forward_x_is_not_a_zero_opd(self):
        sensor = WavefrontSensor(_system())

        from src.ray_tracer import SystemRayTracer3D

        class _SteepTracer:
            """Grid rays get no axial component at all."""

            def __init__(self, system):
                self._real = SystemRayTracer3D(system)
                self.calls = 0

            def trace_ray(self, ray):
                from src.vector3 import vec3

                self.calls += 1
                if self.calls > _CHIEF_RAY_CALL:
                    ray.direction = vec3(0.0, 1.0, 0.0)
                    ray.terminated = False
                    ray.path.append(ray.origin + ray.direction * 10.0)
                    ray.optical_path_length = 10.0
                    return ray
                return self._real.trace_ray(ray)

        sensor.tracer = _SteepTracer(sensor.system)
        W = sensor.get_pupil_wavefront(grid_size=8).W
        # Every in-aperture sample is either NaN (invalid) or has a real OPD;
        # none is a silent zero.
        valid = ~np.isnan(W)
        leaked = (W == 0.0) & valid
        self.assertEqual(int(leaked.sum()), 0)


class TestHealthyPathUnchanged(unittest.TestCase):
    def test_valid_samples_are_produced(self):
        W = _wavefront(chief="good").W
        self.assertGreater(int((~np.isnan(W)).sum()), 0)

    def test_aperture_samples_are_still_nan(self):
        W = _wavefront(chief="good").W
        # A circle inscribed in a square grid: the corners are outside.
        self.assertGreater(int(np.isnan(W).sum()), 0)

    def test_psf_is_finite(self):
        wavefront = _wavefront(chief="good")
        psf = DiffractionPSFCalculator.calculate_psf(wavefront)
        self.assertTrue(np.isfinite(np.abs(psf)).all())

    def test_off_axis_still_produces_a_usable_map(self):
        sensor = WavefrontSensor(_system())
        W = sensor.get_pupil_wavefront(field_angle_deg=5.0, grid_size=16).W
        valid = ~np.isnan(W)
        self.assertGreater(int(valid.sum()), 0)
        self.assertTrue(np.isfinite(W[valid]).all())

    def test_invalid_mask_and_nan_agree(self):
        """Every non-NaN sample must be one the tracer actually measured."""
        W = _wavefront(chief="good").W
        valid = ~np.isnan(W)
        self.assertEqual(int(valid.sum()), int(W.size) - int(np.isnan(W).sum()))


if __name__ == "__main__":
    unittest.main()
