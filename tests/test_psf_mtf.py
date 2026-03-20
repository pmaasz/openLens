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
        sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
        from src.lens import Lens
        from src.optical_system import OpticalSystem
        from src.analysis.psf_mtf import ImageQualityAnalyzer

class TestImageQualityAnalyzer(unittest.TestCase):
    def setUp(self):
        if not NUMPY_AVAILABLE:
            self.skipTest("Numpy not available")
            
        # Create a simple singlet
        self.lens = Lens(radius_of_curvature_1=50.0, radius_of_curvature_2=-50.0, thickness=5.0, refractive_index=1.5)
        self.system = OpticalSystem()
        self.system.add_lens(self.lens)
        self.analyzer = ImageQualityAnalyzer(self.system)

    def test_psf_structure(self):
        """Test that calculate_psf returns correct structure and shape."""
        pixels = 32
        res = self.analyzer.calculate_psf(pixels=pixels)
        
        self.assertIn('image', res)
        self.assertIn('y_axis', res)
        self.assertIn('z_axis', res)
        self.assertIn('centroid', res)
        self.assertIn('step_size', res)
        
        self.assertEqual(res['image'].shape, (pixels, pixels))
        
        # Check normalization (sum approx 1)
        total_energy = np.sum(res['image'])
        # If no rays trace, it might be 0
        if res['raw_count'] > 0:
            self.assertAlmostEqual(total_energy, 1.0, places=5)
        else:
            self.assertEqual(total_energy, 0.0)

    def test_mtf_structure(self):
        """Test that calculate_mtf returns correct structure."""
        res = self.analyzer.calculate_mtf(max_freq=50)
        
        self.assertIn('freq', res)
        self.assertIn('mtf_tan', res)
        self.assertIn('mtf_sag', res)
        
        # Check shapes match
        n = len(res['freq'])
        self.assertEqual(len(res['mtf_tan']), n)
        self.assertEqual(len(res['mtf_sag']), n)
        
        # Check DC component
        if n > 0:
            idx_0 = np.where(res['freq'] == 0)[0]
            if len(idx_0) > 0:
                self.assertAlmostEqual(res['mtf_tan'][idx_0[0]], 1.0, places=5)
                self.assertAlmostEqual(res['mtf_sag'][idx_0[0]], 1.0, places=5)

    def test_off_axis(self):
        """Test off-axis calculation runs without error."""
        res = self.analyzer.calculate_psf(field_angle=5.0, pixels=32)
        self.assertEqual(res['image'].shape, (32, 32))

if __name__ == '__main__':
    unittest.main()
