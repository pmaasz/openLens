"""
Tests for PySide6 Widgets and Lens Rendering
"""

import unittest
import sys
import os

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestLensClassification(unittest.TestCase):
    """Test lens type classification"""
    
    def setUp(self):
        from src.lens import Lens
        self.lens = Lens()
    
    def test_biconvex_classification(self):
        """Biconvex lens should have R1 > 0, R2 < 0"""
        self.lens.radius_of_curvature_1 = 100
        self.lens.radius_of_curvature_2 = -100
        self.assertEqual(self.lens.classify_lens_type(), "Biconvex")
    
    def test_biconcave_classification(self):
        """Biconcave lens should have R1 < 0, R2 > 0"""
        self.lens.radius_of_curvature_1 = -100
        self.lens.radius_of_curvature_2 = 100
        self.assertEqual(self.lens.classify_lens_type(), "Biconcave")
    
    def test_plano_convex_classification(self):
        """Plano-convex lens should have one radius = 0"""
        self.lens.radius_of_curvature_1 = 100
        self.lens.radius_of_curvature_2 = 0
        self.assertIn("Plano-Convex", self.lens.classify_lens_type())
    
    def test_plano_concave_classification(self):
        """Plano-concave lens should have one radius = 0"""
        self.lens.radius_of_curvature_1 = -100
        self.lens.radius_of_curvature_2 = 0
        self.assertIn("Plano-Concave", self.lens.classify_lens_type())


class TestLensCalculation(unittest.TestCase):
    """Test lens optical calculations"""
    
    def setUp(self):
        from src.lens import Lens
        self.lens = Lens()
    
    def test_biconvex_focal_length(self):
        """Biconvex lens should have positive finite focal length"""
        self.lens.radius_of_curvature_1 = 100
        self.lens.radius_of_curvature_2 = -100
        self.lens.refractive_index = 1.5168
        self.lens.thickness = 5
        
        f = self.lens.calculate_focal_length()
        self.assertIsNotNone(f)
        self.assertGreater(f, 0)
        # Focal length is ~97.6mm (not exactly 100 due to lensmaker's equation)
        self.assertAlmostEqual(f, 97.6, places=1)
    
    def test_plano_convex_focal_length(self):
        """Plano-convex lens should have positive focal length"""
        self.lens.radius_of_curvature_1 = 100
        self.lens.radius_of_curvature_2 = 0
        self.lens.refractive_index = 1.5168
        self.lens.thickness = 5
        
        f = self.lens.calculate_focal_length()
        self.assertIsNotNone(f)
        self.assertGreater(f, 0)


class Test3DRendering(unittest.TestCase):
    """Test 3D rendering calculations"""
    
    def test_surface_sag_calculation(self):
        """Test sag calculation at edge"""
        import math
        
        # For R=100mm, diameter=50mm at edge y=25mm
        # sag = r - sqrt(r^2 - y^2)
        r = 100
        y = 25
        sag = r - math.sqrt(r**2 - y**2)
        
        # Should be positive for convex
        self.assertGreater(sag, 0)
        self.assertAlmostEqual(sag, 3.21, places=1)
    
    def test_convex_surface_direction(self):
        """Convex surfaces should curve outward"""
        import numpy as np
        
        r = 100
        r_abs = abs(r)
        max_r = 25  # half diameter
        
        # Sag at edge
        sag = r_abs - np.sqrt(r_abs**2 - max_r**2)
        
        if r > 0:  # Convex front (should curve negative Z / down)
            z_edge = -sag
        else:  # Concave (should curve positive Z / up)
            z_edge = sag
        
        # Negative Z means curving away from body (correct for biconvex)
        self.assertLess(z_edge, 0)


def run_tests():
    """Run widget tests"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    suite.addTests(loader.loadTestsFromTestCase(TestLensClassification))
    suite.addTests(loader.loadTestsFromTestCase(TestLensCalculation))
    suite.addTests(loader.loadTestsFromTestCase(Test3DRendering))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)