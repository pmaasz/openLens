#!/usr/bin/env python3
"""
Comprehensive functional tests for preset library and performance metrics
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src'))

from preset_library import PresetLibrary, LensPreset, get_preset_library
from performance_metrics import PerformanceMetrics
from lens_editor import Lens
from optical_system import create_doublet


class TestPresetLibrary(unittest.TestCase):
    """Test preset lens library"""
    
    def test_create_library(self):
        """Test creating preset library"""
        lib = PresetLibrary()
        self.assertIsNotNone(lib)
    
    def test_default_presets_loaded(self):
        """Test that default presets are loaded"""
        lib = PresetLibrary()
        self.assertGreater(len(lib.presets), 0)
    
    def test_get_preset_library_singleton(self):
        """Test singleton pattern"""
        lib1 = get_preset_library()
        lib2 = get_preset_library()
        self.assertIs(lib1, lib2)
    
    def test_list_presets(self):
        """Test listing all presets"""
        lib = PresetLibrary()
        presets = lib.list_presets()
        
        self.assertIsInstance(presets, list)
        self.assertGreater(len(presets), 0)
        self.assertIsInstance(presets[0], LensPreset)
    
    def test_list_categories(self):
        """Test listing categories"""
        lib = PresetLibrary()
        categories = lib.list_categories()
        
        self.assertIsInstance(categories, list)
        self.assertGreater(len(categories), 0)
        self.assertIn('Simple Lenses', categories)
    
    def test_list_presets_by_category(self):
        """Test filtering presets by category"""
        lib = PresetLibrary()
        simple_lenses = lib.list_presets(category='Simple Lenses')
        
        self.assertGreater(len(simple_lenses), 0)
        for preset in simple_lenses:
            self.assertEqual(preset.category, 'Simple Lenses')
    
    def test_get_preset_by_name(self):
        """Test getting specific preset"""
        lib = PresetLibrary()
        preset = lib.get_preset('50mm Biconvex')
        
        self.assertIsNotNone(preset)
        self.assertEqual(preset.name, '50mm Biconvex')
        self.assertIsInstance(preset.lens, Lens)
    
    def test_get_nonexistent_preset(self):
        """Test getting preset that doesn't exist"""
        lib = PresetLibrary()
        preset = lib.get_preset('Nonexistent Lens')
        
        self.assertIsNone(preset)
    
    def test_search_presets(self):
        """Test searching presets"""
        lib = PresetLibrary()
        results = lib.search_presets('biconvex')
        
        self.assertGreater(len(results), 0)
        for result in results:
            text = (result.name + result.description).lower()
            self.assertIn('biconvex', text)
    
    def test_search_case_insensitive(self):
        """Test search is case-insensitive"""
        lib = PresetLibrary()
        results1 = lib.search_presets('BICONVEX')
        results2 = lib.search_presets('biconvex')
        
        self.assertEqual(len(results1), len(results2))
    
    def test_add_custom_preset(self):
        """Test adding custom preset"""
        lib = PresetLibrary()
        initial_count = len(lib.presets)
        
        lens = Lens(name="Custom", radius_of_curvature_1=100,
                   radius_of_curvature_2=-100, thickness=5, diameter=25)
        preset = LensPreset(
            name="Custom Lens",
            category="Custom",
            description="Test custom preset",
            lens=lens
        )
        
        lib.add_preset(preset)
        
        self.assertEqual(len(lib.presets), initial_count + 1)
        self.assertIsNotNone(lib.get_preset('Custom Lens'))
    
    def test_get_lens_copy(self):
        """Test getting lens copy from preset"""
        lib = PresetLibrary()
        lens_copy = lib.get_lens_copy('50mm Biconvex')
        
        self.assertIsNotNone(lens_copy)
        self.assertIsInstance(lens_copy, Lens)
        
        # Should be a new object
        original_preset = lib.get_preset('50mm Biconvex')
        self.assertIsNot(lens_copy, original_preset.lens)
    
    def test_preset_has_all_fields(self):
        """Test that preset has all expected fields"""
        lib = PresetLibrary()
        preset = lib.get_preset('50mm Biconvex')
        
        self.assertIsNotNone(preset.name)
        self.assertIsNotNone(preset.category)
        self.assertIsNotNone(preset.description)
        self.assertIsNotNone(preset.lens)
    
    def test_preset_lens_is_valid(self):
        """Test that preset lens has valid parameters"""
        lib = PresetLibrary()
        preset = lib.get_preset('50mm Biconvex')
        lens = preset.lens
        
        self.assertGreater(lens.diameter, 0)
        self.assertGreater(lens.thickness, 0)
        self.assertIsNotNone(lens.material)
        
        # Should calculate focal length
        f = lens.calculate_focal_length()
        self.assertIsNotNone(f)


class TestPerformanceMetrics(unittest.TestCase):
    """Test performance metrics calculator"""
    
    def setUp(self):
        """Create test lens"""
        self.lens = Lens(
            radius_of_curvature_1=50,
            radius_of_curvature_2=-50,
            thickness=5,
            diameter=25.4
        )
    
    def test_create_metrics_with_lens(self):
        """Test creating metrics with lens"""
        metrics = PerformanceMetrics(self.lens)
        self.assertIsNotNone(metrics)
        self.assertIsNotNone(metrics.lens)
    
    def test_create_metrics_with_system(self):
        """Test creating metrics with optical system"""
        system = create_doublet(focal_length=100, diameter=50)
        metrics = PerformanceMetrics(system)
        
        self.assertIsNotNone(metrics)
        self.assertIsNotNone(metrics.system)
    
    def test_calculate_f_number(self):
        """Test f-number calculation"""
        metrics = PerformanceMetrics(self.lens)
        f_num = metrics.calculate_f_number()
        
        self.assertIsNotNone(f_num)
        self.assertGreater(f_num, 0)
    
    def test_calculate_numerical_aperture(self):
        """Test numerical aperture calculation"""
        metrics = PerformanceMetrics(self.lens)
        na = metrics.calculate_numerical_aperture()
        
        self.assertIsNotNone(na)
        self.assertGreater(na, 0)
        self.assertLessEqual(na, 1.0)  # Can't exceed 1.0 in air
    
    def test_calculate_back_focal_length(self):
        """Test back focal length calculation"""
        metrics = PerformanceMetrics(self.lens)
        bfl = metrics.calculate_back_focal_length()
        
        self.assertIsNotNone(bfl)
    
    def test_calculate_working_distance(self):
        """Test working distance calculation"""
        metrics = PerformanceMetrics(self.lens)
        wd = metrics.calculate_working_distance(magnification=1.0)
        
        self.assertIsNotNone(wd)
        self.assertGreater(wd, 0)
    
    def test_calculate_magnification(self):
        """Test magnification calculation"""
        metrics = PerformanceMetrics(self.lens)
        mag = metrics.calculate_magnification(object_distance=100)
        
        self.assertIsNotNone(mag)
    
    def test_calculate_resolution_rayleigh(self):
        """Test Rayleigh resolution limit"""
        metrics = PerformanceMetrics(self.lens)
        res = metrics.calculate_resolution_rayleigh()
        
        self.assertIsNotNone(res)
        self.assertGreater(res, 0)
    
    def test_calculate_airy_disk_radius(self):
        """Test Airy disk radius calculation"""
        metrics = PerformanceMetrics(self.lens)
        airy = metrics.calculate_airy_disk_radius()
        
        self.assertIsNotNone(airy)
        self.assertGreater(airy, 0)
    
    def test_calculate_depth_of_field(self):
        """Test depth of field calculation"""
        metrics = PerformanceMetrics(self.lens)
        dof = metrics.calculate_depth_of_field(object_distance=500)
        
        self.assertIsNotNone(dof)
        self.assertIsInstance(dof, dict)
        self.assertIn('near', dof)
        self.assertIn('far', dof)
        self.assertIn('total', dof)
        self.assertIn('hyperfocal', dof)
    
    def test_depth_of_field_ordering(self):
        """Test that DOF near < far"""
        metrics = PerformanceMetrics(self.lens)
        dof = metrics.calculate_depth_of_field(object_distance=500)
        
        if dof['far'] != float('inf'):
            self.assertLess(dof['near'], dof['far'])
    
    def test_get_all_metrics(self):
        """Test getting all metrics at once"""
        metrics = PerformanceMetrics(self.lens)
        all_metrics = metrics.get_all_metrics()
        
        self.assertIsInstance(all_metrics, dict)
        self.assertIn('f_number', all_metrics)
        self.assertIn('numerical_aperture', all_metrics)
        self.assertIn('focal_length', all_metrics)
    
    def test_metrics_with_different_diameters(self):
        """Test that metrics change with diameter"""
        lens1 = Lens(radius_of_curvature_1=50, radius_of_curvature_2=-50,
                    thickness=5, diameter=25)
        lens2 = Lens(radius_of_curvature_1=50, radius_of_curvature_2=-50,
                    thickness=5, diameter=50)
        
        metrics1 = PerformanceMetrics(lens1)
        metrics2 = PerformanceMetrics(lens2)
        
        f_num1 = metrics1.calculate_f_number()
        f_num2 = metrics2.calculate_f_number()
        
        # Larger diameter should have smaller f-number
        self.assertGreater(f_num1, f_num2)
    
    def test_metrics_for_system(self):
        """Test metrics calculation for optical system"""
        system = create_doublet(focal_length=100, diameter=50)
        metrics = PerformanceMetrics(system)
        
        all_metrics = metrics.get_all_metrics()
        
        self.assertIn('system_length', all_metrics)
        self.assertGreater(all_metrics['system_length'], 0)


class TestPerformanceMetricsEdgeCases(unittest.TestCase):
    """Test edge cases for performance metrics"""
    
    def test_metrics_with_flat_surface(self):
        """Test metrics with plano lens"""
        lens = Lens(radius_of_curvature_1=50, radius_of_curvature_2=1e10,
                   thickness=5, diameter=25.4)
        metrics = PerformanceMetrics(lens)
        
        f_num = metrics.calculate_f_number()
        self.assertIsNotNone(f_num)
    
    def test_metrics_with_negative_lens(self):
        """Test metrics with diverging lens"""
        lens = Lens(radius_of_curvature_1=-50, radius_of_curvature_2=50,
                   thickness=3, diameter=25.4)
        metrics = PerformanceMetrics(lens)
        
        # Should still calculate metrics
        all_metrics = metrics.get_all_metrics()
        self.assertIsNotNone(all_metrics['f_number'])


def run_tests():
    """Run all tests"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    suite.addTests(loader.loadTestsFromTestCase(TestPresetLibrary))
    suite.addTests(loader.loadTestsFromTestCase(TestPerformanceMetrics))
    suite.addTests(loader.loadTestsFromTestCase(TestPerformanceMetricsEdgeCases))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(run_tests())
