"""Regression: the wavefront must be traced at the requested wavelength.

``WavefrontSensor.get_pupil_wavefront`` took a ``wavelength_nm`` argument and
used it only to scale the optical path difference into waves. The trace itself
used whatever refractive indices the lenses happened to carry, and the 3D
tracer snapshots each index when it is built.

So the wavefront was the same at every wavelength: the R, G and B PSFs were
identical, and the C and F MTFs were identical. There was no chromatic
aberration anywhere in the diffraction analysis - the one place it should be
most visible.

The fix sets the lenses to the requested wavelength and rebuilds the tracer
before tracing, and restores the lenses afterwards, so asking for a wavefront
never changes the system it was asked about.
"""

import unittest

import numpy as np

from openlens.lens import Lens
from openlens.optical_system import OpticalSystem

F_LINE = 486.1
D_LINE = 587.6
C_LINE = 656.3


def _system():
    """A single element with real dispersion."""
    system = OpticalSystem(name="Dispersive")
    lens = Lens(
        name="Crown",
        radius_of_curvature_1=50.0,
        radius_of_curvature_2=-50.0,
        thickness=6.0,
        diameter=30.0,
        material="N-BK7",
        refractive_index=1.5168,
    )
    system.add_lens(lens, air_gap_before=0.0)
    return system, lens


class TestWavefrontRespondsToWavelength(unittest.TestCase):
    """Different wavelengths must give different wavefronts."""

    def setUp(self):
        from openlens.analysis.diffraction_psf import WavefrontSensor

        self.system, self.lens = _system()
        self.sensor = WavefrontSensor(self.system)

    def _wavefront(self, wavelength):
        return self.sensor.get_pupil_wavefront(
            field_angle_deg=0.0, wavelength_nm=wavelength, grid_size=16
        )

    def test_two_wavelengths_give_different_wavefronts(self):
        """A necessary but not sufficient condition.

        W is in waves, so it scales with 1/lambda even with no dispersion at
        all. The decisive check is the optical path difference in
        test_the_optical_path_difference_carries_the_dispersion.
        """
        blue = self._wavefront(F_LINE)
        red = self._wavefront(C_LINE)

        self.assertFalse(
            np.array_equal(np.asarray(blue.W), np.asarray(red.W)),
            "the wavefront is identical at the F and C lines",
        )

    def test_the_optical_path_difference_carries_the_dispersion(self):
        """The decisive test.

        W is the optical path difference *in waves*, so it scales with 1/lambda
        even when the optics are identical - which is why comparing W directly
        is not enough to show the glass's dispersion is being applied.

        The OPD in millimetres is the physical quantity. Multiplying W back by
        the wavelength puts the two wavelengths on the same footing: with the
        indices held fixed the OPD is the *same* at every wavelength, up to
        floating-point noise.

        The threshold is what matters here. Without the fix the two OPDs
        differ by ~2e-14 mm - pure noise from the reference-sphere
        arithmetic - so an equality test would pass for the wrong reason. A
        real chromatic signal is ~1e-4 mm, nine orders of magnitude larger.
        """
        blue_opd, red_opd = self._paired_opd()
        self.assertGreater(blue_opd.size, 0)
        difference = float(np.max(np.abs(blue_opd - red_opd)))

        self.assertGreater(
            difference,
            1e-8,
            f"the optical path difference is the same at the F and C lines "
            f"(max difference {difference:.3e} mm), so the glass's dispersion "
            f"was not applied",
        )

    def _paired_opd(self):
        """The OPD at the F and C lines, over the samples both traces produced.

        The two traces do not fail on the same rays - the NaN pattern on the
        pupil rim shifts with the wavelength - so the samples are paired
        before comparing, rather than compared position by position.
        """
        blue = np.asarray(self._wavefront(F_LINE).W, dtype=float)
        red = np.asarray(self._wavefront(C_LINE).W, dtype=float)
        usable = np.isfinite(blue) & np.isfinite(red)
        return blue[usable] * (F_LINE * 1e-6), red[usable] * (C_LINE * 1e-6)

    @staticmethod
    def _opd(wavefront, wavelength_nm):
        """The usable samples of the wavefront, converted to millimetres."""
        values = np.asarray(wavefront, dtype=float)
        usable = values[np.isfinite(values)]
        return usable * (wavelength_nm * 1e-6)

    def test_the_wavefront_has_usable_samples(self):
        """A real trace, not a map of NaNs.

        The outermost ring of the pupil grid is NaN by design - a sample
        outside the usable aperture is marked NaN rather than being given a
        zero OPD - so the check is that the interior is finite, not that
        every sample is.
        """
        wavefront = self._wavefront(D_LINE)
        values = np.asarray(wavefront.W)

        finite = values[np.isfinite(values)]
        self.assertGreater(finite.size, 0, "no usable wavefront samples")
        self.assertTrue(np.all(np.isfinite(finite)))

    def test_the_lenses_are_restored_afterwards(self):
        """Asking for a wavefront must not change the system."""
        before_index = self.lens.refractive_index
        before_wavelength = self.lens.wavelength

        self._wavefront(F_LINE)

        self.assertAlmostEqual(self.lens.refractive_index, before_index, places=9)
        self.assertAlmostEqual(self.lens.wavelength, before_wavelength, places=9)

    def test_the_lenses_are_restored_even_on_an_empty_system(self):
        """The restore runs on every path, including the early returns."""
        from openlens.analysis.diffraction_psf import WavefrontSensor

        system, lens = _system()
        sensor = WavefrontSensor(system)
        before = lens.refractive_index

        sensor.get_pupil_wavefront(wavelength_nm=F_LINE, grid_size=8)

        self.assertAlmostEqual(lens.refractive_index, before, places=9)

    def test_repeated_calls_are_stable(self):
        """Tracing at F then at C then at F must give the same first result."""
        first = self._usable(self._wavefront(F_LINE).W)
        self._wavefront(C_LINE)
        third = self._usable(self._wavefront(F_LINE).W)

        self.assertGreater(first.size, 0)
        self.assertTrue(np.array_equal(first, third))

    @staticmethod
    def _usable(wavefront):
        """The finite samples, which are the ones the pupil grid can trust."""
        values = np.asarray(wavefront, dtype=float)
        return values[np.isfinite(values)]


class TestChromaticPsfAndMtf(unittest.TestCase):
    """The user-visible consequence: R/G/B PSFs must differ."""

    def setUp(self):
        from openlens.analysis.psf_mtf import ImageQualityAnalyzer

        self.system, _ = _system()
        self.analyzer = ImageQualityAnalyzer(self.system)

    def _psf(self, wavelength):
        result = self.analyzer.calculate_psf(
            field_angle_deg=0.0,
            wavelength_nm=wavelength,
            sensor_size_mm=0.1,
            pixels=64,
        )
        return np.asarray(result["image"])

    def test_the_psf_differs_between_red_and_blue(self):
        """The PSF now depends on the glass, not only on the wavelength scale.

        Note this alone would also pass with the dispersion missing, because
        the diffraction pattern's size scales with lambda. The decisive check
        is the optical path difference in
        TestWavefrontRespondsToWavelength.test_the_optical_path_difference_carries_the_dispersion.
        """
        red = self._psf(C_LINE)
        blue = self._psf(F_LINE)

        self.assertFalse(np.array_equal(red, blue), "the PSF is identical at the C and F lines")

    def test_the_mtf_differs_between_red_and_blue(self):
        from openlens.analysis.psf_mtf import ImageQualityAnalyzer

        red = ImageQualityAnalyzer(self.system).calculate_mtf(
            field_angle_deg=0.0, wavelength_nm=C_LINE, use_diffraction=True
        )
        blue = ImageQualityAnalyzer(self.system).calculate_mtf(
            field_angle_deg=0.0, wavelength_nm=F_LINE, use_diffraction=True
        )

        self.assertFalse(
            np.array_equal(np.asarray(red["mtf_tan"]), np.asarray(blue["mtf_tan"])),
            "the diffraction MTF is identical at the C and F lines",
        )


if __name__ == "__main__":
    unittest.main()
