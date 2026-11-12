"""#605: PSF/MTF analysis on an empty system must return a well-formed zero result."""

import unittest

import numpy as np

from openlens.analysis.diffraction_psf import WavefrontError
from openlens.analysis.psf_mtf import ImageQualityAnalyzer
from openlens.lens import Lens
from openlens.optical_system import OpticalSystem


class TestEmptySystemAnalysis(unittest.TestCase):
    def setUp(self):
        self.analyzer = ImageQualityAnalyzer(OpticalSystem())

    def test_psf_returns_the_full_key_set_and_a_zero_image(self):
        for use_diffraction in (False, True):
            with self.subTest(use_diffraction=use_diffraction):
                result = self.analyzer.calculate_psf(use_diffraction=use_diffraction, pixels=32)

                self.assertEqual(set(result), set(self.analyzer.PSF_KEYS))
                self.assertEqual(result["image"].shape, (32, 32))
                self.assertFalse(np.any(result["image"]))
                self.assertEqual(result["captured_fraction"], 0.0)
                self.assertEqual(result["raw_count"], 0)
                self.assertEqual(result["centroid"], (0.0, 0.0))
                self.assertEqual(len(result["y_axis"]), 32)
                self.assertEqual(len(result["z_axis"]), 32)

    def test_mtf_returns_empty_profiles_instead_of_raising(self):
        for use_diffraction in (False, True):
            with self.subTest(use_diffraction=use_diffraction):
                result = self.analyzer.calculate_mtf(use_diffraction=use_diffraction)

                self.assertEqual(set(result), {"freq", "mtf_tan", "mtf_sag"})
                self.assertEqual(len(result["freq"]), 0)
                self.assertEqual(len(result["mtf_tan"]), 0)
                self.assertEqual(len(result["mtf_sag"]), 0)

    def test_a_degenerate_wavefront_is_rejected_before_the_fft(self):
        """A non-empty system with an empty pupil must not reach np.fft."""
        system = OpticalSystem()
        system.add_lens(Lens())
        analyzer = ImageQualityAnalyzer(system)

        # Force the wavefront sensor to yield an empty pupil, as an empty
        # system does, without going through the empty-system early return.
        analyzer.wavefront_sensor.get_pupil_wavefront = lambda **kwargs: WavefrontError(
            Y=np.array([]), Z=np.array([]), W=np.array([])
        )

        result = analyzer.calculate_psf(use_diffraction=True, pixels=16)
        self.assertEqual(result["image"].shape, (16, 16))
        self.assertEqual(result["captured_fraction"], 0.0)


if __name__ == "__main__":
    unittest.main()
