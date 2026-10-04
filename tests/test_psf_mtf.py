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
class TestSimulateImageInputs(unittest.TestCase):
    """simulate_image must accept the shapes and dtypes callers pass it.

    np.zeros_like(image_array) inherited the input dtype, so a uint8 image
    truncated every float result to 0/1 before np.clip(0, 1), and indexing
    image_array[:, :, i] raised IndexError on a 2-D grayscale array.
    """

    def setUp(self):
        if not NUMPY_AVAILABLE:
            self.skipTest("Numpy not available")
        from src.lens import Lens
        from src.optical_system import OpticalSystem
        from src.analysis.psf_mtf import ImageQualityAnalyzer

        system = OpticalSystem()
        system.add_lens(
            Lens(
                radius_of_curvature_1=50.0,
                radius_of_curvature_2=-50.0,
                thickness=5.0,
                diameter=25.0,
                refractive_index=1.5,
            )
        )
        self.analyzer = ImageQualityAnalyzer(system)
        np.random.seed(1234)

    def test_two_d_input_does_not_raise(self):
        """Regression: 'too many indices for array: array is 2-dimensional'."""
        out = self.analyzer.simulate_image(np.random.rand(24, 24), pixel_size_mm=0.01)
        self.assertEqual(out.shape, (24, 24))

    def test_uint8_input_is_not_truncated_to_binary(self):
        """Regression: every pixel collapsed to 0 or 1."""
        image = (np.random.rand(24, 24, 3) * 255).astype(np.uint8)
        out = self.analyzer.simulate_image(image, pixel_size_mm=0.01)
        self.assertGreater(len(np.unique(out)), 2)
        self.assertEqual(out.dtype, np.float64)

    def test_output_dtype_is_float64_whatever_the_input(self):
        for image in (
            np.random.rand(16, 16),
            np.random.rand(16, 16, 3),
            (np.random.rand(16, 16, 3) * 255).astype(np.uint8),
            (np.random.rand(16, 16) * 255).astype(np.uint8),
        ):
            with self.subTest(dtype=image.dtype, ndim=image.ndim):
                out = self.analyzer.simulate_image(image, pixel_size_mm=0.01)
                self.assertEqual(out.dtype, np.float64)
                self.assertEqual(out.shape, image.shape)

    def test_output_is_normalized(self):
        image = (np.random.rand(16, 16, 3) * 255).astype(np.uint8)
        out = self.analyzer.simulate_image(image, pixel_size_mm=0.01)
        self.assertGreaterEqual(out.min(), 0.0)
        self.assertLessEqual(out.max(), 1.0)

    def test_uint8_and_float_paths_agree(self):
        """An integer image must mean the same intensities as its float twin."""
        base = np.random.rand(16, 16, 3)
        from_float = self.analyzer.simulate_image(base, pixel_size_mm=0.01)
        from_uint8 = self.analyzer.simulate_image((base * 255).astype(np.uint8), pixel_size_mm=0.01)
        self.assertLess(np.abs(from_float - from_uint8).max(), 0.01)

    def test_wrong_channel_count_is_rejected(self):
        with self.assertRaises(ValueError):
            self.analyzer.simulate_image(np.random.rand(8, 8, 2), pixel_size_mm=0.01)

    def test_wrong_dimensionality_is_rejected(self):
        with self.assertRaises(ValueError):
            self.analyzer.simulate_image(np.random.rand(4, 4, 4, 4), pixel_size_mm=0.01)


if __name__ == "__main__":
    unittest.main()
