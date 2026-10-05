#!/usr/bin/env python3
"""
Aberration blur must be scaled by the pixel pitch, and use the real key names.

_apply_aberrations took the Seidel values from calculate_all_aberrations -
which are geometric (millimetres) - and passed them straight to
gaussian_filter's `sigma`, whose unit is **pixels**:

    sigma = coeff * 2.0

So the blur was completely independent of pixel_pitch_mm, and the `* 2.0` was
an unexplained magic scale. For a 5.38 mm spherical aberration at 0.01 mm
pitch the correct sigma is ~538 px; the old code produced 10.8.

Two further problems:

- The keys were read as "spherical" while the calculator's canonical name is
  "spherical_aberration". Both aliases exist today, so this is read defensively
  rather than assuming either.
- Astigmatism applied `gaussian_filter1d(..., axis=0)` only, leaving the
  orthogonal axis sharp. That is rank-deficient: astigmatism's signature is
  that the tangential and sagittal foci *differ*, so both meridians are blurred
  by different amounts.

`if coeff > 0` also became `max(0.0, ...)`, matching _apply_diffraction, so a
zero aberration is a genuine no-op and a None one is skipped rather than
raising abs(None).
"""

import unittest

import numpy as np

from src.image_simulator import ImageSimulator
from src.lens import Lens
from src.optical_system import OpticalSystem


def _simulator():
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
    return ImageSimulator(system)


def _delta(n=64):
    image = np.zeros((n, n))
    image[n // 2, n // 2] = 255.0
    return image


class TestSigmaScalesWithPixelPitch(unittest.TestCase):
    """Regression: sigma ignored pixel_pitch_mm entirely."""

    def setUp(self):
        self.sim = _simulator()
        self.sim._aberrations_for = lambda wl: {
            "spherical_aberration": 0.05,
            "coma": 0.0,
            "astigmatism": 0.0,
        }
        self.image = _delta()

    def _std(self, pitch):
        return float(
            self.sim._apply_aberrations(self.image, 1e6, 50.0, 550.0, pixel_pitch_mm=pitch).std()
        )

    def test_smaller_pitch_gives_a_larger_blur(self):
        wide = self._std(0.02)
        mid = self._std(0.01)
        narrow = self._std(0.005)
        self.assertGreater(wide, mid)
        self.assertGreater(mid, narrow)

    def test_peak_height_scales_as_one_over_sigma_squared(self):
        """A normalised Gaussian on a delta has a peak proportional to 1/sigma^2.

        Image-wide std does not scale simply with sigma, so the peak is the
        meaningful measure: halving the pitch doubles sigma, so the peak drops
        by a factor of four.
        """

        def peak(pitch):
            out = self.sim._apply_aberrations(self.image, 1e6, 50.0, 550.0, pixel_pitch_mm=pitch)
            return float(out.max())

        # sigma 5 px -> 10 px, so the peak ratio is 1/4.
        self.assertAlmostEqual(peak(0.01) / peak(0.005), 4.0, places=3)

    def test_same_image_different_pitch_gives_different_results(self):
        """The core regression: identical output regardless of pitch."""
        self.assertNotAlmostEqual(self._std(0.01), self._std(0.004), places=6)

    def test_zero_pitch_does_not_raise(self):
        self.assertEqual(
            self.sim._apply_aberrations(self.image, 1e6, 50.0, 550.0, pixel_pitch_mm=0.0).shape,
            self.image.shape,
        )

    def test_negative_pitch_does_not_raise(self):
        self.assertEqual(
            self.sim._apply_aberrations(self.image, 1e6, 50.0, 550.0, pixel_pitch_mm=-0.01).shape,
            self.image.shape,
        )


class TestKeyNames(unittest.TestCase):
    def setUp(self):
        self.sim = _simulator()
        self.image = _delta()

    def test_canonical_spherical_aberration_key_is_read(self):
        self.sim._aberrations_for = lambda wl: {"spherical_aberration": 0.05}
        blurred = self.sim._apply_aberrations(self.image, 1e6, 50.0, 550.0, pixel_pitch_mm=0.01)
        self.assertLess(float(blurred.std()), float(self.image.std()))

    def test_spherical_alias_is_also_read(self):
        """Both documented aliases exist, so either must work."""
        self.sim._aberrations_for = lambda wl: {"spherical": 0.05}
        blurred = self.sim._apply_aberrations(self.image, 1e6, 50.0, 550.0, pixel_pitch_mm=0.01)
        self.assertLess(float(blurred.std()), float(self.image.std()))

    def test_missing_keys_are_skipped(self):
        self.sim._aberrations_for = lambda wl: {}
        out = self.sim._apply_aberrations(self.image, 1e6, 50.0, 550.0, pixel_pitch_mm=0.01)
        np.testing.assert_array_equal(out, self.image)

    def test_none_coefficients_do_not_raise(self):
        """An unmeasurable aberration (see #342) must not crash the render."""
        self.sim._aberrations_for = lambda wl: {
            "spherical_aberration": None,
            "coma": None,
            "astigmatism": None,
        }
        out = self.sim._apply_aberrations(self.image, 1e6, 50.0, 550.0, pixel_pitch_mm=0.01)
        np.testing.assert_array_equal(out, self.image)

    def test_zero_coefficient_is_a_no_op(self):
        self.sim._aberrations_for = lambda wl: {
            "spherical_aberration": 0.0,
            "coma": 0.0,
            "astigmatism": 0.0,
        }
        out = self.sim._apply_aberrations(self.image, 1e6, 50.0, 550.0, pixel_pitch_mm=0.01)
        np.testing.assert_array_equal(out, self.image)


class TestAstigmatismIsTwoMeridians(unittest.TestCase):
    """Regression: only axis 0 was blurred, leaving the other sharp."""

    def setUp(self):
        self.sim = _simulator()
        self.sim._aberrations_for = lambda wl: {"astigmatism": 0.05}
        self.image = _delta()
        self.out = self.sim._apply_aberrations(self.image, 1e6, 50.0, 550.0, pixel_pitch_mm=0.01)

    def test_both_axes_are_blurred(self):
        row = self.out[self.out.shape[0] // 2]
        column = self.out[:, self.out.shape[1] // 2]
        self.assertGreater(float(row.std()), 0.0)
        self.assertGreater(float(column.std()), 0.0)

    def test_the_two_meridians_differ(self):
        """That difference is the signature of astigmatism."""
        row = self.out[self.out.shape[0] // 2]
        column = self.out[:, self.out.shape[1] // 2]
        self.assertNotAlmostEqual(float(row.std()), float(column.std()), places=3)

    def test_no_pixels_lost(self):
        self.assertEqual(self.out.shape, self.image.shape)


class TestDiffractionPathUnchanged(unittest.TestCase):
    """_apply_diffraction already scaled by pitch; it must stay that way."""

    def test_diffraction_still_scales_with_pitch(self):
        """Needs a small enough pitch to clear the max(0.1, sigma) floor.

        At f=50.85, D=25 the Airy sigma is 4.9e-4 mm, so at 0.01 mm pitch it is
        0.049 px - below the floor, and every pitch looks identical. At 0.5 um
        pitch it is 0.98 px and the scaling is visible.
        """
        sim = _simulator()
        image = _delta()
        coarse = float(sim._apply_diffraction(image, 550.0, pixel_pitch_mm=0.001).std())
        fine = float(sim._apply_diffraction(image, 550.0, pixel_pitch_mm=0.00025).std())
        self.assertGreater(coarse, fine)


if __name__ == "__main__":
    unittest.main()
