"""
Tests for constants module
"""

import unittest
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from constants import *


class TestConstants(unittest.TestCase):
    """Test constants module values and categories"""
    
    def test_optical_constants_exist(self):
        """Test that optical constants are defined"""
        self.assertIsInstance(WAVELENGTH_D_LINE, float)
        self.assertIsInstance(WAVELENGTH_C_LINE, float)
        self.assertIsInstance(WAVELENGTH_F_LINE, float)
        self.assertIsInstance(REFRACTIVE_INDEX_AIR, (int, float))
        self.assertIsInstance(REFRACTIVE_INDEX_BK7, float)
        
    def test_wavelength_values(self):
        """Test wavelength values are reasonable"""
        self.assertGreater(WAVELENGTH_D_LINE, 500)
        self.assertLess(WAVELENGTH_D_LINE, 700)
        self.assertGreater(WAVELENGTH_C_LINE, WAVELENGTH_D_LINE)
        self.assertLess(WAVELENGTH_F_LINE, WAVELENGTH_D_LINE)
    
    def test_default_parameters(self):
        """Test default lens parameters"""
        self.assertIsInstance(DEFAULT_RADIUS_1, float)
        self.assertIsInstance(DEFAULT_RADIUS_2, float)
        self.assertIsInstance(DEFAULT_THICKNESS, float)
        self.assertIsInstance(DEFAULT_DIAMETER, float)
        
        self.assertGreater(DEFAULT_THICKNESS, 0)
        self.assertGreater(DEFAULT_DIAMETER, 0)
    
    def test_gui_constants(self):
        """Test GUI constants"""
        self.assertIsInstance(COLOR_BG_DARK, str)
        self.assertTrue(COLOR_BG_DARK.startswith('#'))
        self.assertEqual(len(COLOR_BG_DARK), 7)  # #RRGGBB
        
        self.assertIsInstance(FONT_SIZE_NORMAL, int)
        self.assertGreater(FONT_SIZE_NORMAL, 0)
        self.assertLess(FONT_SIZE_NORMAL, 50)
        
        self.assertIsInstance(PADDING_MEDIUM, int)
        self.assertGreaterEqual(PADDING_MEDIUM, 0)
    
    def test_validation_constants(self):
        """Test validation range constants"""
        self.assertIsInstance(MIN_RADIUS_OF_CURVATURE, float)
        self.assertIsInstance(MAX_RADIUS_OF_CURVATURE, float)
        self.assertLess(MIN_RADIUS_OF_CURVATURE, MAX_RADIUS_OF_CURVATURE)
        
        self.assertIsInstance(MIN_THICKNESS, float)
        self.assertIsInstance(MAX_THICKNESS, float)
        self.assertLess(MIN_THICKNESS, MAX_THICKNESS)
        
        self.assertGreater(MIN_REFRACTIVE_INDEX, 0)
        self.assertLess(MAX_REFRACTIVE_INDEX, 5)
    
    def test_aberration_thresholds(self):
        """Test aberration quality thresholds"""
        self.assertIsInstance(SPHERICAL_ABERRATION_EXCELLENT, float)
        self.assertIsInstance(SPHERICAL_ABERRATION_GOOD, float)
        self.assertIsInstance(SPHERICAL_ABERRATION_POOR, float)
        
        # Check ordering
        self.assertLess(SPHERICAL_ABERRATION_EXCELLENT, SPHERICAL_ABERRATION_GOOD)
        self.assertLess(SPHERICAL_ABERRATION_GOOD, SPHERICAL_ABERRATION_POOR)
    
    def test_unit_conversions(self):
        """Test unit conversion factors"""
        self.assertEqual(MM_TO_METERS, 0.001)
        self.assertEqual(METERS_TO_MM, 1000.0)
        self.assertEqual(MM_TO_METERS * METERS_TO_MM, 1.0)
    
    def test_lens_types(self):
        """Test lens type constants"""
        self.assertIsInstance(ALL_LENS_TYPES, list)
        self.assertIn(LENS_TYPE_BICONVEX, ALL_LENS_TYPES)
        self.assertIn(LENS_TYPE_PLANO_CONVEX, ALL_LENS_TYPES)
        self.assertEqual(len(ALL_LENS_TYPES), 6)
    
    def test_no_conflicts(self):
        """Test that constants don't have conflicting values"""
        # Ensure padding values are ordered
        self.assertLess(PADDING_SMALL, PADDING_MEDIUM)
        self.assertLess(PADDING_MEDIUM, PADDING_LARGE)
        
        # Ensure font sizes are ordered
        self.assertLessEqual(FONT_SIZE_NORMAL, FONT_SIZE_LARGE)


class TestConstantsUsage(unittest.TestCase):
    """Test that constants can be used as expected"""
    
    def test_constants_are_immutable_types(self):
        """Test constants use immutable types"""
        # Numbers should be int or float
        self.assertIsInstance(DEFAULT_RADIUS_1, (int, float))
        self.assertIsInstance(WAVELENGTH_D_LINE, (int, float))
        
        # Strings should be str
        self.assertIsInstance(COLOR_BG_DARK, str)
        self.assertIsInstance(LENS_TYPE_BICONVEX, str)
    
    def test_can_use_in_calculations(self):
        """Test constants can be used in calculations"""
        # Should not raise errors
        power1 = (1.5 - 1) / DEFAULT_RADIUS_1
        power2 = -(1.5 - 1) / DEFAULT_RADIUS_2
        self.assertIsInstance(power1, float)
        self.assertIsInstance(power2, float)
        
        wavelength_mm = WAVELENGTH_D_LINE * NM_TO_MM
        self.assertGreater(wavelength_mm, 0)
        self.assertLess(wavelength_mm, 0.001)
    
    def test_quality_thresholds_make_sense(self):
        """Test quality threshold relationships"""
        # Better quality = lower aberration
        self.assertLess(SPHERICAL_ABERRATION_EXCELLENT, SPHERICAL_ABERRATION_POOR)
        self.assertLess(COMA_EXCELLENT, COMA_POOR)
        
        # Quality scores
        self.assertGreater(QUALITY_EXCELLENT_THRESHOLD, QUALITY_GOOD_THRESHOLD)
        self.assertGreater(QUALITY_GOOD_THRESHOLD, QUALITY_FAIR_THRESHOLD)


if __name__ == '__main__':
    unittest.main()
