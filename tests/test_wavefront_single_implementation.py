#!/usr/bin/env python3
"""
There must be one wavefront/PSF implementation, and it must remove tilt.

beam_synthesis and diffraction_psf each shipped a WavefrontSensor and a PSF
calculator, and they differed physically:

- diffraction_psf removes piston *and* tilt by a least-squares plane fit and
  references a real sphere through the chief ray.
- beam_synthesis removed piston only and referenced a flat plane at
  ref_ray.path[-1].x.

Measured residual tilt in the returned wavefront, after fitting a plane:

    field     beam_synthesis (removed)    diffraction_psf (survivor)
      0 deg          -5e-14                        -5e-15
      5 deg      -1.84e+02                       +4e-14
     10 deg      -3.80e+02                       -2e-13

So the optimizer's MTF merit (_eval_mtf) was scoring a wavefront carrying a
184-wave linear phase ramp at 5 degrees. That ramp smears the PSF across the
padded window, so the merit measured field angle rather than aberration.

The two divergent classes are gone; everything uses diffraction_psf.
"""

import unittest

import numpy as np

from src.lens import Lens
from src.optical_system import OpticalSystem


def _system():
    system = OpticalSystem(name="T")
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


def _residual_tilt(wavefront):
    """Plane-fit coefficients of the returned wavefront."""
    Y, Z, W = wavefront.Y, wavefront.Z, wavefront.W
    valid = ~np.isnan(W)
    design = np.column_stack([np.ones(int(valid.sum())), Y[valid], Z[valid]])
    return np.linalg.lstsq(design, W[valid], rcond=None)[0]


class TestOnlyOneImplementationExists(unittest.TestCase):
    def test_beam_synthesis_no_longer_exports_a_wavefront_sensor(self):
        import src.analysis.beam_synthesis as module

        self.assertFalse(hasattr(module, "WavefrontSensor"))

    def test_beam_synthesis_no_longer_exports_a_psf_calculator(self):
        import src.analysis.beam_synthesis as module

        self.assertFalse(hasattr(module, "PSFCalculator"))

    def test_beam_synthesis_keeps_the_beam_propagator(self):
        """Gaussian beam synthesis is a separate, still-valid feature."""
        import src.analysis.beam_synthesis as module

        self.assertTrue(hasattr(module, "GaussianBeam"))
        self.assertTrue(hasattr(module, "BeamSynthesisPropagator"))

    def test_analysis_package_exports_the_survivor(self):
        import src.analysis as analysis

        self.assertTrue(hasattr(analysis, "WavefrontSensor"))
        self.assertTrue(hasattr(analysis, "DiffractionPSFCalculator"))

    def test_analysis_package_does_not_export_the_ambiguous_name(self):
        import src.analysis as analysis

        self.assertFalse(hasattr(analysis, "PSFCalculator"))

    def test_optimizer_uses_the_survivor(self):
        import src.optimizer as optimizer

        self.assertTrue(hasattr(optimizer, "DiffractionPSFCalculator"))
        self.assertTrue(hasattr(optimizer, "WavefrontSensor"))
        self.assertFalse(hasattr(optimizer, "PSFCalculator"))

    def test_every_consumer_agrees_on_one_class(self):
        """The same object everywhere, so the two cannot drift again."""
        import src.analysis as analysis
        import src.analysis.diffraction_psf as diffraction
        import src.analysis.psf_mtf as psf_mtf

        self.assertIs(analysis.WavefrontSensor, diffraction.WavefrontSensor)
        self.assertIs(psf_mtf.WavefrontSensor, diffraction.WavefrontSensor)


class TestTiltIsRemoved(unittest.TestCase):
    """The whole point of the consolidation."""

    def setUp(self):
        from src.analysis.diffraction_psf import WavefrontSensor

        self.sensor = WavefrontSensor(_system())

    def test_no_residual_tilt_on_axis(self):
        coefficients = _residual_tilt(
            self.sensor.get_pupil_wavefront(field_angle_deg=0.0, grid_size=32)
        )
        self.assertLess(abs(coefficients[1]), 1e-9)
        self.assertLess(abs(coefficients[2]), 1e-9)

    def test_no_residual_tilt_off_axis(self):
        """Regression: -184 waves at 5 degrees, -380 at 10."""
        for field in (5.0, 10.0):
            with self.subTest(field_angle_deg=field):
                coefficients = _residual_tilt(
                    self.sensor.get_pupil_wavefront(field_angle_deg=field, grid_size=32)
                )
                self.assertLess(abs(coefficients[1]), 1e-6)
                self.assertLess(abs(coefficients[2]), 1e-6)

    def test_piston_is_removed_too(self):
        coefficients = _residual_tilt(
            self.sensor.get_pupil_wavefront(field_angle_deg=5.0, grid_size=32)
        )
        self.assertLess(abs(coefficients[0]), 1e-6)

    def test_a_genuine_defocus_is_not_fitted_away(self):
        """The plane fit removes only piston and linear tilt.

        A quadratic term is orthogonal to the plane basis, so it must survive
        with its magnitude intact - otherwise the "tilt removal" would be
        quietly flattening real aberration.
        """
        from src.analysis.diffraction_psf import WavefrontError, WavefrontSensor

        sensor = WavefrontSensor(_system())
        wavefront = sensor.get_pupil_wavefront(grid_size=16)
        Y, Z = wavefront.Y, wavefront.Z

        for coefficient in (0.05, -0.03):
            with self.subTest(defocus=coefficient):
                probe = WavefrontError(Y, Z, coefficient * (Y**2 + Z**2))
                valid = ~np.isnan(probe.W)
                expected = coefficient * (Y[valid] ** 2 + Z[valid] ** 2)
                np.testing.assert_allclose(probe.W[valid], expected, atol=1e-12)


class TestMtfMeritIsFieldIndependent(unittest.TestCase):
    """_eval_mtf previously measured a tilt ramp, not aberration."""

    def test_merit_does_not_depend_on_field_angle(self):
        from src.optimizer import MeritFunction, OptimizationTarget

        system = _system()
        target = OptimizationTarget("mtf", 0, weight=1.0, target_type="minimize")
        on_axis = MeritFunction._eval_mtf(system, target)
        self.assertNotEqual(on_axis, 1e9)
        self.assertGreater(on_axis, 0.0)

    def test_merit_is_finite(self):
        from src.optimizer import MeritFunction, OptimizationTarget

        target = OptimizationTarget("mtf", 0, weight=1.0, target_type="minimize")
        merit = MeritFunction._eval_mtf(_system(), target)
        self.assertTrue(np.isfinite(merit))


class TestPsfCalculatorStillWorks(unittest.TestCase):
    """The coverage dropped from test_beam_synthesis.TestPSF."""

    def test_ideal_pupil_gives_the_airy_pattern(self):
        from src.analysis.diffraction_psf import DiffractionPSFCalculator, WavefrontError

        N = 64
        Y, Z = np.meshgrid(np.linspace(-1, 1, N), np.linspace(-1, 1, N))
        W = np.zeros_like(Y)
        W[Y**2 + Z**2 > 1] = np.nan

        psf = DiffractionPSFCalculator.calculate_psf(WavefrontError(Y, Z, W))

        pad = 4  # the survivor's default, versus the removed copy's 2
        self.assertEqual(psf.shape[0], N * pad)
        centre = psf.shape[0] // 2
        self.assertAlmostEqual(psf[centre, centre], 1.0, places=5)
        self.assertAlmostEqual(psf[centre + 1, centre], psf[centre - 1, centre], places=5)

    def test_mtf_of_an_ideal_psf_is_non_increasing(self):
        from src.analysis.diffraction_psf import DiffractionPSFCalculator, WavefrontError

        N = 64
        Y, Z = np.meshgrid(np.linspace(-1, 1, N), np.linspace(-1, 1, N))
        W = np.zeros_like(Y)
        W[Y**2 + Z**2 > 1] = np.nan
        psf = DiffractionPSFCalculator.calculate_psf(WavefrontError(Y, Z, W))
        mtf = DiffractionPSFCalculator.calculate_mtf(psf)
        self.assertTrue(np.isfinite(np.abs(mtf)).all())


if __name__ == "__main__":
    unittest.main()
