#!/usr/bin/env python3
"""
Functional tests for Lens Comparison Mode
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import unittest
from lens_editor import Lens
from lens_comparator import LensComparator, ComparisonResult


class TestLensComparator(unittest.TestCase):
    """Test lens comparison functionality"""
    
    def setUp(self):
        """Create test lenses"""
        self.lens1 = Lens(
            name="Lens A",
            radius_of_curvature_1=50.0,
            radius_of_curvature_2=-50.0,
            thickness=5.0,
            diameter=25.0,
            refractive_index=1.5168,
            lens_type="Biconvex",
            material="BK7"
        )
        
        self.lens2 = Lens(
            name="Lens B",
            radius_of_curvature_1=100.0,
            radius_of_curvature_2=-100.0,
            thickness=3.0,
            diameter=30.0,
            refractive_index=1.6,
            lens_type="Biconvex",
            material="SF11"
        )
        
        self.lens3 = Lens(
            name="Lens C",
            radius_of_curvature_1=75.0,
            radius_of_curvature_2=-80.0,
            thickness=4.0,
            diameter=20.0,
            refractive_index=1.45,
            lens_type="Meniscus Convex",
            material="Fused Silica"
        )
    
    def test_add_lens(self):
        """Test adding lenses to comparator"""
        comparator = LensComparator()
        comparator.add_lens(self.lens1)
        comparator.add_lens(self.lens2)
        
        self.assertEqual(len(comparator.lenses), 2)
        print("✓ Added 2 lenses to comparator")
    
    def test_compare_two_lenses(self):
        """Test comparing two lenses"""
        comparator = LensComparator()
        comparator.add_lens(self.lens1)
        comparator.add_lens(self.lens2)
        
        results = comparator.compare()
        
        self.assertEqual(len(results), 2)
        self.assertIsInstance(results[0], ComparisonResult)
        self.assertIsInstance(results[1], ComparisonResult)
        
        print("✓ Compared 2 lenses successfully")
        print(f"  Lens A focal length: {results[0].focal_length:.2f} mm")
        print(f"  Lens B focal length: {results[1].focal_length:.2f} mm")
    
    def test_compare_multiple_lenses(self):
        """Test comparing multiple lenses"""
        comparator = LensComparator()
        comparator.add_lens(self.lens1)
        comparator.add_lens(self.lens2)
        comparator.add_lens(self.lens3)
        
        results = comparator.compare()
        
        self.assertEqual(len(results), 3)
        print("✓ Compared 3 lenses successfully")
    
    def test_comparison_table(self):
        """Test generating comparison table"""
        comparator = LensComparator()
        comparator.add_lens(self.lens1)
        comparator.add_lens(self.lens2)
        comparator.add_lens(self.lens3)
        
        table = comparator.get_comparison_table()
        
        self.assertIsInstance(table, str)
        self.assertIn("LENS COMPARISON", table)
        self.assertIn("Lens A", table)
        self.assertIn("Lens B", table)
        self.assertIn("Lens C", table)
        self.assertIn("Focal Length", table)
        self.assertIn("F-Number", table)
        
        print("✓ Generated comparison table successfully")
        print("\n" + table)
    
    def test_clear_comparator(self):
        """Test clearing comparator"""
        comparator = LensComparator()
        comparator.add_lens(self.lens1)
        comparator.add_lens(self.lens2)
        
        self.assertEqual(len(comparator.lenses), 2)
        
        comparator.clear()
        self.assertEqual(len(comparator.lenses), 0)
        
        print("✓ Cleared comparator successfully")
    
    def test_comparison_result_to_dict(self):
        """Test converting comparison result to dictionary"""
        comparator = LensComparator()
        comparator.add_lens(self.lens1)
        
        results = comparator.compare()
        result_dict = results[0].to_dict()
        
        self.assertIsInstance(result_dict, dict)
        self.assertIn('name', result_dict)
        self.assertIn('focal_length', result_dict)
        self.assertIn('f_number', result_dict)
        self.assertIn('diameter', result_dict)
        
        print("✓ Converted comparison result to dictionary")
        print(f"  Keys: {', '.join(result_dict.keys())}")
    
    def test_find_best_lens(self):
        """Test finding best lens by criterion"""
        comparator = LensComparator()
        comparator.add_lens(self.lens1)
        comparator.add_lens(self.lens2)
        comparator.add_lens(self.lens3)
        
        # Find shortest focal length
        best = comparator.find_best('focal_length', minimize=True)
        self.assertIsNotNone(best)
        
        print(f"✓ Found best lens: {best.name}")
        print(f"  Criterion: shortest focal length = {best.focal_length:.2f} mm")
    
    def test_highlight_differences(self):
        """Test highlighting significant differences"""
        comparator = LensComparator()
        comparator.add_lens(self.lens1)
        comparator.add_lens(self.lens2)
        
        differences = comparator.highlight_differences(threshold_percent=10.0)
        
        self.assertIsInstance(differences, dict)
        print("✓ Highlighted differences successfully")
        
        if differences:
            print(f"  Significant differences found:")
            for param, info in differences.items():
                print(f"    - {param}: {info}")


class TestComparisonEdgeCases(unittest.TestCase):
    """Test edge cases in lens comparison"""
    
    def test_empty_comparator(self):
        """Test comparison with no lenses"""
        comparator = LensComparator()
        results = comparator.compare()
        
        self.assertEqual(len(results), 0)
        print("✓ Handled empty comparator correctly")
    
    def test_single_lens_comparison(self):
        """Test comparison with single lens"""
        lens = Lens(
            name="Solo Lens",
            radius_of_curvature_1=50.0,
            radius_of_curvature_2=-50.0,
            thickness=5.0,
            diameter=25.0,
            refractive_index=1.5168
        )
        
        comparator = LensComparator()
        comparator.add_lens(lens)
        
        results = comparator.compare()
        self.assertEqual(len(results), 1)
        
        print("✓ Handled single lens comparison correctly")
    
    def test_identical_lenses(self):
        """Test comparing identical lenses"""
        lens1 = Lens(
            name="Twin A",
            radius_of_curvature_1=50.0,
            radius_of_curvature_2=-50.0,
            thickness=5.0,
            diameter=25.0,
            refractive_index=1.5168
        )
        
        lens2 = Lens(
            name="Twin B",
            radius_of_curvature_1=50.0,
            radius_of_curvature_2=-50.0,
            thickness=5.0,
            diameter=25.0,
            refractive_index=1.5168
        )
        
        comparator = LensComparator()
        comparator.add_lens(lens1)
        comparator.add_lens(lens2)
        
        differences = comparator.highlight_differences(threshold_percent=1.0)
        
        # Should have no differences except name
        self.assertLessEqual(len(differences), 1)
        
        print("✓ Correctly identified identical lenses")


def run_tests():
    """Run all lens comparator tests"""
    print("="*70)
    print("TESTING: Lens Comparison Mode")
    print("="*70)
    
    suite = unittest.TestLoader().loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print("\n" + "="*70)
    if result.wasSuccessful():
        print("✓ All lens comparison tests passed!")
    else:
        print("✗ Some tests failed")
    print("="*70)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
