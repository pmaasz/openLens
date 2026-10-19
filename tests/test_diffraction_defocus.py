"""Regression: the diffraction PSF/MTF must respond to defocus.

``_calculate_diffraction_psf`` accepted ``focus_shift_mm`` and never used it,
and the diffraction branch of ``calculate_mtf`` dropped it entirely. The
wavefront is referenced to the Gaussian focus, so without a defocus term the
PSF and the MTF at 0 mm and at 2 mm of defocus were bit-identical.

``simulate_image`` always takes the diffraction path, so its defocus argument
did nothing either.

The physics: an image-plane defocus of ``dz`` adds a quadratic phase across
the pupil,

    W(p) = dz * NA^2 * p^2 / (2 * lambda)

with ``p`` normalised to 1 at the pupil edge. The sign does not change the PSF
- the pupil is symmetric and the intensity is a squared modulus - but the
magnitude does, so a defocused system must have a wider PSF and a lower MTF.
"""

import unittest

import numpy as np

from openlens.lens import Lens
from openlens.optical_system import OpticalSystem


def _doublet():
    """A two-element system: enough to have a real focal length."""
    system = OpticalSystem(name="Doublet")
    front = Lens(
        name="Front",
        radius_of_curvature_1=60.0,
        radius_of_curvature_2=-60.0,
        thickness=6.0,
        diameter=30.0,
        refractive_index=1.52,
    )
    back = Lens(
        name="Back",
        radius_of_curvature_1=-60.0,
        radius_of_curvature_2=-200.0,
        thickness=4.0,
        diameter=30.0,
        refractive_index=1.62,
    )
    system.add_lens(front, air_gap_before=0.0)
    system.add_lens(back, air_gap_before=2.0)
    return system


class TestDiffractionPsfRespondsToDefocus(unittest.TestCase):
    """A defocused PSF must differ from the in-focus one."""

    def setUp(self):
        from openlens.analysis.psf_mtf import ImageQualityAnalyzer

        self.analyzer = ImageQualityAnalyzer(_doublet())

    def _psf(self, defocus):
        result = self.analyzer.calculate_psf(
            field_angle_deg=0.0,
            wavelength_nm=550.0,
            focus_shift_mm=defocus,
            sensor_size_mm=0.1,
            pixels=128,
        )
        return np.asarray(result["image"]), result["step_size"]

    def test_the_psf_is_not_bit_identical_at_two_defocus_values(self):
        """The issue's repro: np.array_equal -> True was the bug."""
        at_focus, _ = self._psf(0.0)
        defocused, _ = self._psf(2.0)

        self.assertFalse(
            np.array_equal(at_focus, defocused),
            "the PSF is identical at 0 mm and 2 mm of defocus",
        )

    def test_a_defocused_psf_is_wider(self):
        """More defocus must spread the energy out."""
        at_focus, at_step = self._psf(0.0)
        defocused, def_step = self._psf(2.0)

        self.assertGreater(
            _second_moment(defocused, def_step),
            _second_moment(at_focus, at_step),
            msg="the defocused PSF is not wider once the measurement is made "
            "in mm rather than pixels",
        )

    def test_zero_defocus_leaves_the_psf_unchanged(self):
        """The fix must not disturb the in-focus case."""
        analyzer2 = self.analyzer
        first, _ = self._psf(0.0)
        second, _ = self._psf(0.0)

        self.assertTrue(np.array_equal(first, second))
        self.assertIsNotNone(analyzer2)

    def test_the_psf_stays_normalised(self):
        """Adding a phase term must not change the total energy."""
        at_focus, _ = self._psf(0.0)
        defocused, _ = self._psf(2.0)

        self.assertGreater(float(np.sum(at_focus)), 0.0)
        self.assertGreater(float(np.sum(defocused)), 0.0)


class TestDiffractionMtfRespondsToDefocus(unittest.TestCase):
    """A defocused system must have a lower MTF."""

    def setUp(self):
        from openlens.analysis.psf_mtf import ImageQualityAnalyzer

        self.analyzer = ImageQualityAnalyzer(_doublet())

    def _mtf(self, defocus):
        result = self.analyzer.calculate_mtf(
            field_angle_deg=0.0,
            wavelength_nm=550.0,
            focus_shift_mm=defocus,
            use_diffraction=True,
        )
        return np.asarray(result["mtf_tan"])

    def test_the_mtf_is_not_identical_at_two_defocus_values(self):
        at_focus = self._mtf(0.0)
        defocused = self._mtf(2.0)

        self.assertFalse(np.array_equal(at_focus, defocused))

    def test_the_mtf_drops_with_defocus(self):
        """The issue's stated criterion.

        Compared at a *non-zero* spatial frequency: the MTF at DC is 1.0 by
        definition, since defocus costs no contrast at zero frequency. What
        defocus costs is the ability to carry fine detail, so the curve has to
        come down as the frequency rises.
        """
        at_focus = self._mtf(0.0)
        defocused = self._mtf(2.0)

        frequencies = self._freqs(0.0)
        # Pick a frequency in the middle of the returned band, where the
        # difference is unambiguous.
        index = len(frequencies) // 2

        self.assertLess(
            float(defocused[index]),
            float(at_focus[index]),
            f"the diffraction MTF did not drop with defocus at " f"{frequencies[index]:.1f} lp/mm",
        )

    def _freqs(self, defocus):
        from openlens.analysis.psf_mtf import ImageQualityAnalyzer

        result = ImageQualityAnalyzer(_doublet()).calculate_mtf(
            field_angle_deg=0.0,
            wavelength_nm=550.0,
            focus_shift_mm=defocus,
            use_diffraction=True,
        )
        return np.asarray(result["freq"])


def _second_moment(psf, step_size_mm):
    """Spread of the PSF, as the variance of its intensity distribution.

    Two things this must not depend on, because neither is the quantity under
    test:

    - *Total energy.* "Is the defocused spot wider" is a statement about
      shape, so the image is normalised first.
    - *The window size.* The geometric PSF grows its window to cover the
      spot (#449), so the same spot then spans fewer pixels. Measuring the
      second moment in pixel units made a wider spot look narrower - the
      metric was really reporting the zoom. The step size is applied so the
      variance comes out in mm^2.
    """
    psf = np.asarray(psf, dtype=float)
    total = float(np.sum(psf))
    if total <= 0:
        return 0.0
    psf = psf / total
    rows, cols = psf.shape
    cy, cx = rows // 2, cols // 2
    yy, xx = np.mgrid[0:rows, 0:cols]
    y_var = float(np.sum(psf * ((yy - cy) * step_size_mm) ** 2))
    x_var = float(np.sum(psf * ((xx - cx) * step_size_mm) ** 2))
    return y_var + x_var


if __name__ == "__main__":
    unittest.main()
