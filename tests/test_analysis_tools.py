import unittest
import math
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    np = None

from src.optical_system import OpticalSystem
from src.lens import Lens
from src.analysis.geometric import GeometricTraceAnalysis
# ImageQualityAnalyzer depends on numpy, but importing it should now be safe
try:
    from src.analysis.psf_mtf import ImageQualityAnalyzer
except ImportError:
    ImageQualityAnalyzer = None

class TestAnalysisTools(unittest.TestCase):
    def setUp(self):
        # Create a simple biconvex lens system
        self.system = OpticalSystem()
        self.lens = Lens(radius_of_curvature_1=50.0, 
                         radius_of_curvature_2=-50.0, 
                         thickness=5.0, 
                         diameter=25.0, 
                         refractive_index=1.5)
        self.system.add_lens(self.lens)
        
    def test_ray_fan(self):
        analyzer = GeometricTraceAnalysis(self.system)
        
        # Test Tangential Fan
        fan_data = analyzer.calculate_ray_fan(field_angle_deg=0.0, pupil_axis='y')
        self.assertIn('pupil_coords', fan_data)
        self.assertIn('ray_errors', fan_data)
        self.assertEqual(len(fan_data['pupil_coords']), len(fan_data['ray_errors']))
        
        # On-axis spherical aberration should be symmetric (odd function of pupil coord)
        errors = fan_data['ray_errors']
        # Check first and last are roughly opposite
        # Note: Sign convention might make them equal if plotting H vs y^2, but this is H vs y.
        # Spherical aberration: dy ~ y^3.
        # So error(-y) = -error(y).
        if len(errors) > 0:
            self.assertAlmostEqual(errors[0], -errors[-1], delta=1.0)
        
    def test_field_curvature_distortion(self):
        analyzer = GeometricTraceAnalysis(self.system)
        data = analyzer.calculate_field_curvature_distortion(max_field_angle=5.0)
        
        self.assertIn('tan_focus_shift', data)
        self.assertIn('sag_focus_shift', data)
        self.assertIn('distortion_pct', data)
        
        # Distortion should be small for this simple lens at 5 degrees
        if len(data['distortion_pct']) > 0:
            self.assertTrue(abs(data['distortion_pct'][-1]) < 5.0)
        
    @unittest.skipUnless(HAS_NUMPY, "Numpy required for PSF/MTF analysis")
    def test_psf_mtf_fallback(self):
        if ImageQualityAnalyzer is None:
            self.skipTest("ImageQualityAnalyzer not imported")
            
        analyzer = ImageQualityAnalyzer(self.system)
        
        # Test simulate_image fallback
        input_image = np.zeros((64, 64, 3))
        input_image[30:34, 30:34, :] = 1.0 # White square
        
        # This should run without scipy (using my fallback)
        output_image = analyzer.simulate_image(input_image, pixel_size=0.01)
        
        self.assertEqual(output_image.shape, input_image.shape)
        # Check that it's somewhat blurred (center pixel less than 1)
        self.assertLess(output_image[32, 32, 0], 1.0)
        
    @unittest.skipUnless(HAS_NUMPY, "Numpy required for PSF/MTF analysis")
    def test_mtf_calculation(self):
        if ImageQualityAnalyzer is None:
            self.skipTest("ImageQualityAnalyzer not imported")

        analyzer = ImageQualityAnalyzer(self.system)
        mtf_data = analyzer.calculate_mtf(field_angle=0.0, max_freq=50.0)
        
        self.assertIn('mtf_tan', mtf_data)
        self.assertIn('freq', mtf_data)
        # MTF at DC should be 1.0
        if len(mtf_data['mtf_tan']) > 0:
            self.assertAlmostEqual(mtf_data['mtf_tan'][0], 1.0, places=1)

if __name__ == '__main__':
    unittest.main()
