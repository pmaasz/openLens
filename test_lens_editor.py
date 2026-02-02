#!/usr/bin/env python3
"""
Functional tests for OpenLense application
Tests the Lens class and LensManager functionality
"""

import unittest
import json
import os
import tempfile
from datetime import datetime
import sys

# Import the modules to test
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lens_editor import Lens, LensManager


class TestLens(unittest.TestCase):
    """Test cases for the Lens class"""
    
    def test_lens_creation_with_defaults(self):
        """Test creating a lens with default parameters"""
        lens = Lens()
        self.assertEqual(lens.name, "Untitled")
        self.assertEqual(lens.radius_of_curvature_1, 100.0)
        self.assertEqual(lens.radius_of_curvature_2, -100.0)
        self.assertEqual(lens.thickness, 5.0)
        self.assertEqual(lens.diameter, 50.0)
        self.assertEqual(lens.refractive_index, 1.5168)
        self.assertEqual(lens.lens_type, "Biconvex")
        self.assertEqual(lens.material, "BK7")
        self.assertIsNotNone(lens.id)
        self.assertIsNotNone(lens.created_at)
        self.assertIsNotNone(lens.modified_at)
    
    def test_lens_creation_with_custom_parameters(self):
        """Test creating a lens with custom parameters"""
        lens = Lens(
            name="Test Lens",
            radius_of_curvature_1=50.0,
            radius_of_curvature_2=-75.0,
            thickness=3.0,
            diameter=25.0,
            refractive_index=1.52,
            lens_type="Plano-Convex",
            material="Crown Glass"
        )
        self.assertEqual(lens.name, "Test Lens")
        self.assertEqual(lens.radius_of_curvature_1, 50.0)
        self.assertEqual(lens.radius_of_curvature_2, -75.0)
        self.assertEqual(lens.thickness, 3.0)
        self.assertEqual(lens.diameter, 25.0)
        self.assertEqual(lens.refractive_index, 1.52)
        self.assertEqual(lens.lens_type, "Plano-Convex")
        self.assertEqual(lens.material, "Crown Glass")
    
    def test_lens_to_dict(self):
        """Test converting lens to dictionary"""
        lens = Lens(name="Test", radius_of_curvature_1=100.0)
        lens_dict = lens.to_dict()
        
        self.assertIsInstance(lens_dict, dict)
        self.assertEqual(lens_dict["name"], "Test")
        self.assertEqual(lens_dict["radius_of_curvature_1"], 100.0)
        self.assertEqual(lens_dict["radius_of_curvature_2"], -100.0)
        self.assertIn("id", lens_dict)
        self.assertIn("created_at", lens_dict)
        self.assertIn("modified_at", lens_dict)
    
    def test_lens_from_dict(self):
        """Test creating lens from dictionary"""
        data = {
            "id": "20260202123456",
            "name": "Test Lens",
            "radius_of_curvature_1": 80.0,
            "radius_of_curvature_2": -60.0,
            "thickness": 4.0,
            "diameter": 30.0,
            "refractive_index": 1.6,
            "type": "Biconcave",
            "material": "Flint Glass",
            "created_at": "2026-02-02T12:00:00",
            "modified_at": "2026-02-02T12:30:00"
        }
        
        lens = Lens.from_dict(data)
        self.assertEqual(lens.id, "20260202123456")
        self.assertEqual(lens.name, "Test Lens")
        self.assertEqual(lens.radius_of_curvature_1, 80.0)
        self.assertEqual(lens.radius_of_curvature_2, -60.0)
        self.assertEqual(lens.thickness, 4.0)
        self.assertEqual(lens.diameter, 30.0)
        self.assertEqual(lens.refractive_index, 1.6)
        self.assertEqual(lens.lens_type, "Biconcave")
        self.assertEqual(lens.material, "Flint Glass")
    
    def test_focal_length_calculation_biconvex(self):
        """Test focal length calculation for a biconvex lens"""
        lens = Lens(
            radius_of_curvature_1=100.0,
            radius_of_curvature_2=-100.0,
            thickness=5.0,
            refractive_index=1.5168
        )
        focal_length = lens.calculate_focal_length()
        self.assertIsNotNone(focal_length)
        # Expected approximately 97.5mm for this lens configuration
        self.assertAlmostEqual(focal_length, 97.58, places=1)
    
    def test_focal_length_calculation_plano_convex(self):
        """Test focal length calculation for a plano-convex lens"""
        lens = Lens(
            radius_of_curvature_1=100.0,
            radius_of_curvature_2=float('inf'),  # Flat surface
            thickness=5.0,
            refractive_index=1.5168
        )
        focal_length = lens.calculate_focal_length()
        self.assertIsNotNone(focal_length)
        # Should be approximately 193.5mm for plano-convex
        self.assertGreater(focal_length, 0)
    
    def test_focal_length_with_zero_radius(self):
        """Test focal length returns None when radius is zero"""
        lens = Lens(
            radius_of_curvature_1=0.0,
            radius_of_curvature_2=-100.0
        )
        focal_length = lens.calculate_focal_length()
        self.assertIsNone(focal_length)
    
    def test_focal_length_with_no_power(self):
        """Test focal length returns None when lens has no optical power"""
        lens = Lens(
            radius_of_curvature_1=100.0,
            radius_of_curvature_2=100.0,  # Same curvature = no power
            thickness=0.0,
            refractive_index=1.5168
        )
        focal_length = lens.calculate_focal_length()
        self.assertIsNone(focal_length)
    
    def test_lens_string_representation(self):
        """Test lens string representation"""
        lens = Lens(name="Test Lens")
        lens_str = str(lens)
        self.assertIn("Test Lens", lens_str)
        self.assertIn("Optical Lens Details", lens_str)
        self.assertIn("Refractive Index", lens_str)


class TestLensManager(unittest.TestCase):
    """Test cases for the LensManager class"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create a temporary file for testing
        self.temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')
        self.temp_file.close()
        self.storage_file = self.temp_file.name
        self.manager = LensManager(storage_file=self.storage_file)
    
    def tearDown(self):
        """Clean up test fixtures"""
        if os.path.exists(self.storage_file):
            os.unlink(self.storage_file)
    
    def test_manager_initialization(self):
        """Test LensManager initialization"""
        self.assertIsNotNone(self.manager)
        self.assertEqual(self.manager.storage_file, self.storage_file)
        self.assertIsInstance(self.manager.lenses, list)
    
    def test_save_and_load_lenses(self):
        """Test saving and loading lenses"""
        # Create and add lenses
        lens1 = Lens(name="Lens 1", material="BK7")
        lens2 = Lens(name="Lens 2", material="Fused Silica")
        
        self.manager.lenses = [lens1, lens2]
        self.manager.save_lenses()
        
        # Create new manager and load
        new_manager = LensManager(storage_file=self.storage_file)
        self.assertEqual(len(new_manager.lenses), 2)
        self.assertEqual(new_manager.lenses[0].name, "Lens 1")
        self.assertEqual(new_manager.lenses[1].name, "Lens 2")
        self.assertEqual(new_manager.lenses[0].material, "BK7")
    
    def test_load_from_nonexistent_file(self):
        """Test loading from non-existent file"""
        manager = LensManager(storage_file="nonexistent_file.json")
        self.assertEqual(len(manager.lenses), 0)
    
    def test_load_from_corrupt_file(self):
        """Test loading from corrupt JSON file"""
        with open(self.storage_file, 'w') as f:
            f.write("This is not valid JSON {{{")
        
        manager = LensManager(storage_file=self.storage_file)
        self.assertEqual(len(manager.lenses), 0)
    
    def test_get_lens_by_index(self):
        """Test getting lens by index"""
        lens1 = Lens(name="Lens 1")
        lens2 = Lens(name="Lens 2")
        self.manager.lenses = [lens1, lens2]
        
        retrieved_lens = self.manager.get_lens_by_index(1)
        self.assertIsNotNone(retrieved_lens)
        self.assertEqual(retrieved_lens.name, "Lens 1")
        
        retrieved_lens = self.manager.get_lens_by_index(2)
        self.assertIsNotNone(retrieved_lens)
        self.assertEqual(retrieved_lens.name, "Lens 2")
        
        # Test out of bounds
        self.assertIsNone(self.manager.get_lens_by_index(0))
        self.assertIsNone(self.manager.get_lens_by_index(3))
    
    def test_multiple_lenses_persistence(self):
        """Test that multiple lenses persist correctly"""
        lenses_data = []
        for i in range(5):
            lens = Lens(
                name=f"Lens {i}",
                radius_of_curvature_1=100.0 + i * 10,
                radius_of_curvature_2=-100.0 - i * 10,
                material=f"Material {i}"
            )
            lenses_data.append(lens)
        
        self.manager.lenses = lenses_data
        self.manager.save_lenses()
        
        # Load and verify
        new_manager = LensManager(storage_file=self.storage_file)
        self.assertEqual(len(new_manager.lenses), 5)
        
        for i, lens in enumerate(new_manager.lenses):
            self.assertEqual(lens.name, f"Lens {i}")
            self.assertEqual(lens.radius_of_curvature_1, 100.0 + i * 10)
            self.assertEqual(lens.material, f"Material {i}")


class TestLensCalculations(unittest.TestCase):
    """Test cases for optical calculations"""
    
    def test_symmetric_biconvex_focal_length(self):
        """Test focal length of symmetric biconvex lens"""
        lens = Lens(
            radius_of_curvature_1=100.0,
            radius_of_curvature_2=-100.0,
            thickness=5.0,
            refractive_index=1.5
        )
        focal_length = lens.calculate_focal_length()
        # For thin lens approximation: f ≈ R/(2(n-1)) = 100/(2*0.5) = 100mm
        # With thickness correction it will be slightly different
        self.assertIsNotNone(focal_length)
        self.assertGreater(focal_length, 90)
        self.assertLess(focal_length, 110)
    
    def test_high_index_material(self):
        """Test lens with high refractive index"""
        lens = Lens(
            radius_of_curvature_1=100.0,
            radius_of_curvature_2=-100.0,
            thickness=5.0,
            refractive_index=1.9  # High index glass
        )
        focal_length = lens.calculate_focal_length()
        self.assertIsNotNone(focal_length)
        # Higher index should give shorter focal length
        self.assertLess(focal_length, 60)
    
    def test_converging_vs_diverging(self):
        """Test that converging lens has positive focal length"""
        converging_lens = Lens(
            radius_of_curvature_1=100.0,
            radius_of_curvature_2=-100.0,  # Biconvex
            thickness=5.0,
            refractive_index=1.5168
        )
        focal_length = converging_lens.calculate_focal_length()
        self.assertGreater(focal_length, 0)  # Positive for converging
    
    def test_different_curvatures(self):
        """Test lens with different front and back curvatures"""
        lens = Lens(
            radius_of_curvature_1=50.0,   # Stronger curvature
            radius_of_curvature_2=-150.0,  # Weaker curvature
            thickness=5.0,
            refractive_index=1.5168
        )
        focal_length = lens.calculate_focal_length()
        self.assertIsNotNone(focal_length)
        self.assertGreater(focal_length, 0)


class TestDataIntegrity(unittest.TestCase):
    """Test cases for data integrity and edge cases"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')
        self.temp_file.close()
        self.storage_file = self.temp_file.name
    
    def tearDown(self):
        """Clean up test fixtures"""
        if os.path.exists(self.storage_file):
            os.unlink(self.storage_file)
    
    def test_unique_lens_ids(self):
        """Test that each lens gets a unique ID"""
        import time
        
        lens1 = Lens()
        time.sleep(0.001)  # Small delay to ensure different timestamp
        lens2 = Lens()
        time.sleep(0.001)
        lens3 = Lens()
        
        self.assertNotEqual(lens1.id, lens2.id)
        self.assertNotEqual(lens2.id, lens3.id)
        self.assertNotEqual(lens1.id, lens3.id)
    
    def test_timestamps_are_valid(self):
        """Test that timestamps are valid ISO format"""
        lens = Lens()
        
        # Should be able to parse timestamps
        try:
            datetime.fromisoformat(lens.created_at)
            datetime.fromisoformat(lens.modified_at)
        except ValueError:
            self.fail("Timestamps are not in valid ISO format")
    
    def test_lens_with_extreme_values(self):
        """Test lens with extreme but valid values"""
        lens = Lens(
            radius_of_curvature_1=1000.0,
            radius_of_curvature_2=-0.1,
            thickness=100.0,
            diameter=1000.0,
            refractive_index=2.5
        )
        
        # Should not crash
        focal_length = lens.calculate_focal_length()
        lens_dict = lens.to_dict()
        lens_str = str(lens)
        
        self.assertIsNotNone(lens)
    
    def test_json_serialization_completeness(self):
        """Test that all lens properties are serialized"""
        lens = Lens(
            name="Complete Test",
            radius_of_curvature_1=75.0,
            radius_of_curvature_2=-125.0,
            thickness=6.5,
            diameter=45.0,
            refractive_index=1.6,
            lens_type="Meniscus Convex",
            material="SF11"
        )
        
        lens_dict = lens.to_dict()
        
        required_keys = [
            "id", "name", "radius_of_curvature_1", "radius_of_curvature_2",
            "thickness", "diameter", "refractive_index", "type", "material",
            "created_at", "modified_at"
        ]
        
        for key in required_keys:
            self.assertIn(key, lens_dict, f"Key '{key}' missing from serialized lens")
    
    def test_deserialization_with_missing_fields(self):
        """Test that lens can be created from incomplete data"""
        incomplete_data = {
            "name": "Incomplete Lens",
            "material": "BK7"
        }
        
        lens = Lens.from_dict(incomplete_data)
        
        # Should use defaults for missing fields
        self.assertEqual(lens.name, "Incomplete Lens")
        self.assertEqual(lens.material, "BK7")
        self.assertEqual(lens.radius_of_curvature_1, 100.0)  # Default
        self.assertEqual(lens.refractive_index, 1.5168)  # Default


def run_tests():
    """Run all tests and return results"""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test cases
    suite.addTests(loader.loadTestsFromTestCase(TestLens))
    suite.addTests(loader.loadTestsFromTestCase(TestLensManager))
    suite.addTests(loader.loadTestsFromTestCase(TestLensCalculations))
    suite.addTests(loader.loadTestsFromTestCase(TestDataIntegrity))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result


if __name__ == "__main__":
    print("=" * 70)
    print("OpenLense Functional Tests")
    print("=" * 70)
    print()
    
    result = run_tests()
    
    print()
    print("=" * 70)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped)}")
    
    if result.wasSuccessful():
        print("\n✓ ALL TESTS PASSED!")
        sys.exit(0)
    else:
        print("\n✗ SOME TESTS FAILED!")
        sys.exit(1)
