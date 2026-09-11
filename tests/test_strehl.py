#!/usr/bin/env python3
"""Tests for the wavefront-based Strehl ratio.

The Strehl ratio is S = |<exp(i * 2 * pi * W)>|^2 over the exit pupil
(Born & Wolf), reducing to the Marechal approximation exp(-(2*pi*sigma)^2)
for small RMS wavefront error sigma in waves. These tests guard against
regression to placeholder (e.g. Airy/spot-area or hardcoded) estimates.
"""

import math
import unittest

from src.aberrations import AberrationsCalculator
from src.constants import WAVELENGTH_GREEN
from src.lens import Lens
from src.optical_system import OpticalSystem


def _biconvex(diameter: float) -> Lens:
    return Lens(
        name=f"Biconvex D={diameter}",
        radius_of_curvature_1=100.0,
        radius_of_curvature_2=-100.0,
        thickness=5.0,
        diameter=diameter,
        refractive_index=1.5168,
        material="BK7",
    )


class TestStrehlRatio(unittest.TestCase):
    def test_strehl_in_physical_range_singlet(self):
        """Strehl ratio must lie in [0, 1] for a singlet."""
        results = AberrationsCalculator(_biconvex(20.0)).calculate_all_aberrations()
        self.assertGreaterEqual(results["strehl"], 0.0)
        self.assertLessEqual(results["strehl"], 1.0)

    def test_strehl_in_physical_range_system(self):
        """Strehl ratio must lie in [0, 1] for a system."""
        system = OpticalSystem(name="singlet-system")
        system.add_lens(_biconvex(20.0))
        results = AberrationsCalculator(system).calculate_all_aberrations()
        self.assertGreaterEqual(results["strehl"], 0.0)
        self.assertLessEqual(results["strehl"], 1.0)

    def test_wfe_rms_waves_reported(self):
        """RMS wavefront error in waves is reported and non-negative."""
        results = AberrationsCalculator(_biconvex(10.0)).calculate_all_aberrations()
        self.assertIn("wfe_rms_waves", results)
        self.assertGreaterEqual(results["wfe_rms_waves"], 0.0)

    def test_slow_lens_near_diffraction_limited(self):
        """Slow (f/20) singlet should be near diffraction-limited."""
        results = AberrationsCalculator(_biconvex(5.0)).calculate_all_aberrations()
        self.assertGreater(results["strehl"], 0.9)
        self.assertLess(results["wfe_rms_waves"], 0.07)

    def test_strehl_decreases_with_aperture(self):
        """Larger aperture (more spherical aberration) lowers Strehl."""
        strehl = [
            AberrationsCalculator(_biconvex(d)).calculate_all_aberrations()["strehl"]
            for d in (5.0, 10.0, 20.0)
        ]
        self.assertGreater(strehl[0], strehl[1])
        self.assertGreater(strehl[1], strehl[2])

    def test_no_hardcoded_singlet_value(self):
        """Two different singlets must not share one placeholder value."""
        s_small = AberrationsCalculator(_biconvex(5.0)).calculate_all_aberrations()["strehl"]
        s_large = AberrationsCalculator(_biconvex(40.0)).calculate_all_aberrations()["strehl"]
        self.assertNotAlmostEqual(s_small, s_large, places=3)

    def test_spherical_wavefront_scales_with_aperture_fourth_power(self):
        """Third-order spherical wavefront error scales as y^4."""
        wfe_5 = AberrationsCalculator(_biconvex(5.0)).calculate_all_aberrations()["wfe_rms_waves"]
        wfe_10 = AberrationsCalculator(_biconvex(10.0)).calculate_all_aberrations()["wfe_rms_waves"]
        ratio = wfe_10 / wfe_5
        self.assertGreater(ratio, 12.0)
        self.assertLess(ratio, 20.0)

    def test_short_focus_lens_gets_real_strehl(self):
        """BFL shorter than the exit propagation must still reference."""
        short = Lens(
            name="Short fast singlet",
            radius_of_curvature_1=50.0,
            radius_of_curvature_2=-50.0,
            thickness=6.0,
            diameter=25.0,
            refractive_index=1.5168,
            material="BK7",
        )
        results = AberrationsCalculator(short).calculate_all_aberrations()

        # Fast uncorrected singlet: huge but finite wavefront error, and a
        # defined (near-zero) Strehl rather than a computation bail-out.
        self.assertGreater(results["wfe_rms_waves"], 1.0)
        self.assertGreaterEqual(results["strehl"], 0.0)
        self.assertLessEqual(results["strehl"], 1.0)

    def test_marechal_consistency_for_small_aberration(self):
        """Exact pupil average must match Marechal for sigma << 1 wave."""
        results = AberrationsCalculator(_biconvex(5.0)).calculate_all_aberrations()
        marechal = math.exp(-((2.0 * math.pi * results["wfe_rms_waves"]) ** 2))
        self.assertAlmostEqual(results["strehl"], marechal, delta=0.05)

    def test_mtf_cutoff_scales_inversely_with_wavelength(self):
        """Diffraction cutoff fc = 1/(lambda * f/#) follows wavelength."""
        calc = AberrationsCalculator(_biconvex(10.0))
        blue = calc.calculate_all_aberrations(wavelength_nm=486.1)["mtf_cutoff"]
        green = calc.calculate_all_aberrations()["mtf_cutoff"]
        red = calc.calculate_all_aberrations(wavelength_nm=656.3)["mtf_cutoff"]
        self.assertGreater(blue, green)
        self.assertGreater(green, red)
        self.assertAlmostEqual(blue / green, 550.0 / 486.1, delta=0.01)


class TestWavefrontSensor(unittest.TestCase):
    def test_reference_sphere_wavefront_small_for_slow_lens(self):
        """Chief-referenced exit-pupil map of a slow lens is sub-wave."""
        import numpy as np

        from src.analysis.diffraction_psf import WavefrontSensor

        system = OpticalSystem(name="slow")
        system.add_lens(_biconvex(10.0))
        wf = WavefrontSensor(system).get_pupil_wavefront(
            field_angle_deg=0.0, wavelength_nm=WAVELENGTH_GREEN, grid_size=16
        )
        valid = wf.W[np.isfinite(wf.W)]
        self.assertGreater(valid.size, 10)
        # Piston + tilt removed: mean residual ~ 0
        self.assertAlmostEqual(float(np.mean(valid)), 0.0, delta=1e-6)
        self.assertLess(float(np.sqrt(np.mean(valid**2))), 1.0)


if __name__ == "__main__":
    unittest.main()
