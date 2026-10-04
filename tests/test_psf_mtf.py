import unittest
import sys
import os

try:
    import numpy as np

    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

# Only attempt imports if numpy is available to avoid crash
if NUMPY_AVAILABLE:
    try:
        from src.lens import Lens
        from src.optical_system import OpticalSystem
        from src.analysis.psf_mtf import ImageQualityAnalyzer
    except ImportError:
        sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
        from src.lens import Lens
        from src.optical_system import OpticalSystem
        from src.analysis.psf_mtf import ImageQualityAnalyzer


class TestImageQualityAnalyzer(unittest.TestCase):
    def setUp(self):
        if not NUMPY_AVAILABLE:
            self.skipTest("Numpy not available")

        # Create a simple singlet
        self.lens = Lens(
            radius_of_curvature_1=50.0,
            radius_of_curvature_2=-50.0,
            thickness=5.0,
            refractive_index=1.5,
        )
        self.system = OpticalSystem()
        self.system.add_lens(self.lens)
        self.analyzer = ImageQualityAnalyzer(self.system)

    def test_psf_structure(self):
        """Test that calculate_psf returns correct structure and shape."""
        pixels = 32
        res = self.analyzer.calculate_psf(pixels=pixels)

        self.assertIn("image", res)
        self.assertIn("y_axis", res)
        self.assertIn("z_axis", res)
        self.assertIn("centroid", res)
        self.assertIn("step_size", res)

        self.assertEqual(res["image"].shape, (pixels, pixels))

        # Check normalization (sum approx 1)
        total_energy = np.sum(res["image"])
        # If no rays trace, it might be 0
        if res["raw_count"] > 0:
            self.assertAlmostEqual(total_energy, 1.0, places=5)
        else:
            self.assertEqual(total_energy, 0.0)

    def test_mtf_structure(self):
        """Test that calculate_mtf returns correct structure."""
        res = self.analyzer.calculate_mtf(max_freq=50)

        self.assertIn("freq", res)
        self.assertIn("mtf_tan", res)
        self.assertIn("mtf_sag", res)

        # Check shapes match
        n = len(res["freq"])
        self.assertEqual(len(res["mtf_tan"]), n)
        self.assertEqual(len(res["mtf_sag"]), n)

        # Check DC component
        if n > 0:
            idx_0 = np.where(res["freq"] == 0)[0]
            if len(idx_0) > 0:
                self.assertAlmostEqual(res["mtf_tan"][idx_0[0]], 1.0, places=5)
                self.assertAlmostEqual(res["mtf_sag"][idx_0[0]], 1.0, places=5)

    def test_off_axis(self):
        """Test off-axis calculation runs without error."""
        res = self.analyzer.calculate_psf(field_angle_deg=5.0, pixels=32)
        self.assertEqual(res["image"].shape, (32, 32))


@unittest.skipUnless(NUMPY_AVAILABLE, "numpy not installed")
class TestDiffractionFrequencyScale(unittest.TestCase):
    """The diffraction MTF frequency axis must be the sample spacing.

    The pupil grid is np.linspace(-max_r, max_r, N): N samples spanning
    2*max_r in N-1 intervals. Dividing the pupil width by N understated the
    spacing by N/(N-1) and reported every frequency low by that factor
    (1.6% at grid_size 64).
    """

    def setUp(self):
        if not NUMPY_AVAILABLE:
            self.skipTest("Numpy not available")
        from src.lens import Lens
        from src.optical_system import OpticalSystem
        from src.analysis.psf_mtf import ImageQualityAnalyzer

        self.system = OpticalSystem()
        self.system.add_lens(
            Lens(
                radius_of_curvature_1=50.0,
                radius_of_curvature_2=-50.0,
                thickness=5.0,
                diameter=25.0,
                refractive_index=1.5,
            )
        )
        self.analyzer = ImageQualityAnalyzer(self.system)

    def _expected_df(self, grid_size=64, wavelength_nm=550.0):
        ep_diam = self.system.elements[0].lens.diameter
        efl = self.system.get_system_focal_length()
        return (ep_diam / (grid_size - 1)) / (wavelength_nm * 1e-6 * efl)

    def test_frequency_step_matches_sample_spacing(self):
        mtf = self.analyzer.calculate_mtf(use_diffraction=True, max_freq=100.0)
        freqs = np.asarray(mtf["freq"])
        step = freqs[1] - freqs[0]
        self.assertAlmostEqual(step, self._expected_df(), places=9)

    def test_frequency_step_is_not_the_n_not_n_minus_1_value(self):
        """Regression: the old value was low by exactly N/(N-1)."""
        mtf = self.analyzer.calculate_mtf(use_diffraction=True, max_freq=100.0)
        freqs = np.asarray(mtf["freq"])
        step = freqs[1] - freqs[0]
        ep_diam = self.system.elements[0].lens.diameter
        efl = self.system.get_system_focal_length()
        wrong = (ep_diam / 64) / (550e-6 * efl)
        self.assertNotAlmostEqual(step, wrong, places=6)

    def test_frequency_axis_is_uniform_and_starts_at_zero(self):
        mtf = self.analyzer.calculate_mtf(use_diffraction=True, max_freq=100.0)
        freqs = np.asarray(mtf["freq"])
        self.assertAlmostEqual(freqs[0], 0.0, places=9)
        diffs = np.diff(freqs)
        self.assertTrue(np.allclose(diffs, diffs[0]))

    def test_step_matches_the_sensors_actual_grid(self):
        """Pin the formula to the grid the sensor really builds.

        calculate_mtf passes pupil_grid_size=64 internally, so the closed
        form must use that same N - the sampling is not caller-tunable.
        """
        wavefront = self.analyzer.wavefront_sensor.get_pupil_wavefront(grid_size=64)
        grid_size = wavefront.W.shape[0]
        self.assertEqual(grid_size, 64)

        mtf = self.analyzer.calculate_mtf(use_diffraction=True, max_freq=100.0)
        freqs = np.asarray(mtf["freq"])
        self.assertAlmostEqual(freqs[1] - freqs[0], self._expected_df(grid_size), places=9)


if __name__ == "__main__":
    unittest.main()
