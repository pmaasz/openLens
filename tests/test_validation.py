"""
Tests for validation module
"""

import unittest
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from validation import *


class TestValidationFunctions(unittest.TestCase):
    """Test validation functions"""
    
    def test_validate_radius_positive(self):
        """Test radius validation with positive values"""
        result = validate_radius(100.0)
        self.assertEqual(result, 100.0)
        
        result = validate_radius(50.0, allow_negative=False)
        self.assertEqual(result, 50.0)
    
    def test_validate_radius_negative(self):
        """Test radius validation with negative values"""
        result = validate_radius(-100.0, allow_negative=True)
        self.assertEqual(result, -100.0)
        
        with self.assertRaises(ValidationError):
            validate_radius(-100.0, allow_negative=False)
    
    def test_validate_radius_zero(self):
        """Test radius validation rejects zero"""
        with self.assertRaises(ValidationError):
            validate_radius(0.0)
    
    def test_validate_radius_out_of_range(self):
        """Test radius validation enforces ranges"""
        with self.assertRaises(ValidationError):
            validate_radius(0.5)  # Too small
        
        with self.assertRaises(ValidationError):
            validate_radius(50000.0)  # Too large
    
    def test_validate_thickness(self):
        """Test thickness validation"""
        result = validate_thickness(5.0)
        self.assertEqual(result, 5.0)
        
        with self.assertRaises(ValidationError):
            validate_thickness(0.0)  # Must be positive
        
        with self.assertRaises(ValidationError):
            validate_thickness(-5.0)  # Must be positive
    
    def test_validate_diameter(self):
        """Test diameter validation"""
        result = validate_diameter(50.0)
        self.assertEqual(result, 50.0)
        
        with self.assertRaises(ValidationError):
            validate_diameter(0.0)
        
        with self.assertRaises(ValidationError):
            validate_diameter(-10.0)
    
    def test_validate_refractive_index(self):
        """Test refractive index validation"""
        result = validate_refractive_index(1.5168)
        self.assertEqual(result, 1.5168)
        
        result = validate_refractive_index(1.0)  # Air
        self.assertEqual(result, 1.0)
        
        with self.assertRaises(ValidationError):
            validate_refractive_index(0.5)  # Too low
        
        with self.assertRaises(ValidationError):
            validate_refractive_index(5.0)  # Too high
    
    def test_validate_wavelength(self):
        """Test wavelength validation"""
        result = validate_wavelength(587.6)
        self.assertEqual(result, 587.6)
        
        with self.assertRaises(ValidationError):
            validate_wavelength(0.0)
        
        with self.assertRaises(ValidationError):
            validate_wavelength(50.0)  # Below visible range
        
        with self.assertRaises(ValidationError):
            validate_wavelength(5000.0)  # Above IR range
    
    def test_validate_temperature(self):
        """Test temperature validation"""
        result = validate_temperature(20.0)
        self.assertEqual(result, 20.0)
        
        result = validate_temperature(0.0)  # Freezing point
        self.assertEqual(result, 0.0)
        
        with self.assertRaises(ValidationError):
            validate_temperature(-300.0)  # Below absolute zero
    
    def test_validate_positive_number(self):
        """Test positive number validation"""
        result = validate_positive_number(10.0)
        self.assertEqual(result, 10.0)
        
        with self.assertRaises(ValidationError):
            validate_positive_number(0.0)
        
        with self.assertRaises(ValidationError):
            validate_positive_number(-5.0)
    
    def test_validate_non_negative_number(self):
        """Test non-negative number validation"""
        result = validate_non_negative_number(10.0)
        self.assertEqual(result, 10.0)
        
        result = validate_non_negative_number(0.0)
        self.assertEqual(result, 0.0)
        
        with self.assertRaises(ValidationError):
            validate_non_negative_number(-1.0)
    
    def test_validate_range(self):
        """Test range validation"""
        result = validate_range(5.0, 0.0, 10.0)
        self.assertEqual(result, 5.0)
        
        result = validate_range(0.0, 0.0, 10.0)  # Min boundary
        self.assertEqual(result, 0.0)
        
        result = validate_range(10.0, 0.0, 10.0)  # Max boundary
        self.assertEqual(result, 10.0)
        
        with self.assertRaises(ValidationError):
            validate_range(-1.0, 0.0, 10.0)
        
        with self.assertRaises(ValidationError):
            validate_range(11.0, 0.0, 10.0)
    
    def test_validate_lens_name(self):
        """Test lens name validation"""
        result = validate_lens_name("My Lens")
        self.assertEqual(result, "My Lens")
        
        result = validate_lens_name("")  # Empty becomes "Untitled"
        self.assertEqual(result, "Untitled")
        
        result = validate_lens_name("  ")  # Whitespace becomes "Untitled"
        self.assertEqual(result, "Untitled")
        
        with self.assertRaises(ValidationError):
            validate_lens_name("a" * 200)  # Too long


class TestSafeConversion(unittest.TestCase):
    """Test safe float conversion"""
    
    def test_safe_float_from_number(self):
        """Test conversion from numbers"""
        success, value = safe_float_conversion(10)
        self.assertTrue(success)
        self.assertEqual(value, 10.0)
        
        success, value = safe_float_conversion(5.5)
        self.assertTrue(success)
        self.assertEqual(value, 5.5)
    
    def test_safe_float_from_string(self):
        """Test conversion from valid strings"""
        success, value = safe_float_conversion("10.5")
        self.assertTrue(success)
        self.assertEqual(value, 10.5)
        
        success, value = safe_float_conversion("100")
        self.assertTrue(success)
        self.assertEqual(value, 100.0)
    
    def test_safe_float_from_invalid_string(self):
        """Test conversion from invalid strings"""
        success, value = safe_float_conversion("abc")
        self.assertFalse(success)
        self.assertEqual(value, 0.0)
        
        success, value = safe_float_conversion("abc", default=99.9)
        self.assertFalse(success)
        self.assertEqual(value, 99.9)


class TestLensValidation(unittest.TestCase):
    """Test lens parameter validation"""
    
    def test_validate_lens_parameters_valid(self):
        """Test validation of valid lens parameters"""
        result = validate_lens_parameters(
            radius1=100.0,
            radius2=-100.0,
            thickness=5.0,
            diameter=50.0,
            refractive_index=1.5168
        )
        
        self.assertIsInstance(result, dict)
        self.assertEqual(result['radius1'], 100.0)
        self.assertEqual(result['radius2'], -100.0)
        self.assertEqual(result['thickness'], 5.0)
        self.assertEqual(result['diameter'], 50.0)
        self.assertEqual(result['refractive_index'], 1.5168)
    
    def test_validate_lens_parameters_invalid(self):
        """Test validation rejects invalid parameters"""
        with self.assertRaises(ValidationError):
            validate_lens_parameters(
                radius1=0.0,  # Invalid
                radius2=-100.0,
                thickness=5.0,
                diameter=50.0,
                refractive_index=1.5168
            )


class TestPhysicalFeasibility(unittest.TestCase):
    """Test physical feasibility checks"""
    
    def test_check_feasible_lens(self):
        """Test that reasonable lens parameters pass"""
        feasible, message = check_physical_feasibility(
            radius1=100.0,
            radius2=-100.0,
            thickness=5.0,
            diameter=20.0
        )
        self.assertTrue(feasible)
        self.assertIsNone(message)
    
    def test_check_thick_lens(self):
        """Test warning for very thick lens"""
        feasible, message = check_physical_feasibility(
            radius1=50.0,
            radius2=-50.0,
            thickness=30.0,  # Very thick
            diameter=20.0
        )
        self.assertFalse(feasible)
        self.assertIsNotNone(message)
        self.assertIn("thick", message.lower())
    
    def test_check_thin_lens(self):
        """Test warning for very thin lens"""
        feasible, message = check_physical_feasibility(
            radius1=100.0,
            radius2=-100.0,
            thickness=0.5,  # Very thin
            diameter=50.0
        )
        self.assertFalse(feasible)
        self.assertIsNotNone(message)
        self.assertIn("thin", message.lower())


class TestValidationErrors(unittest.TestCase):
    """Test ValidationError exception"""
    
    def test_validation_error_message(self):
        """Test ValidationError carries message"""
        try:
            raise ValidationError("Test error message")
        except ValidationError as e:
            self.assertEqual(str(e), "Test error message")
    
    def test_validation_error_is_exception(self):
        """Test ValidationError is an Exception"""
        self.assertTrue(issubclass(ValidationError, Exception))


if __name__ == '__main__':
    unittest.main()
