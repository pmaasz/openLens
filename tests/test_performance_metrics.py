#!/usr/bin/env python3
"""
Functional tests for Performance Metrics Dashboard
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import unittest
from lens_editor import Lens
from optical_system import OpticalSystem
from performance_metrics import PerformanceMetrics


class TestPerformanceMetrics(unittest.TestCase):
    """Test performance metrics calculations"""
    
    def setUp(self):
        """Create test lens"""
        self.lens = Lens(
            name="Test Lens",
            radius_of_curvature_1=50.0,
            radius_of_curvature_2=-50.0,
            thickness=5.0,
            diameter=25.0,
            refractive_index=1.5168,
            lens_type="Biconvex",
            material="BK7"
        )
    
    def test_f_number_calculation(self):
        """Test f-number calculation"""
        calc = PerformanceMetrics(self.lens)
        f_num = calc.calculate_f_number()
        
        self.assertIsNotNone(f_num)
        self.assertGreater(f_num, 0)
        print(f"✓ F-number: f/{f_num:.2f}")
    
    def test_back_focal_length(self):
        """Test back focal length calculation"""
        calc = PerformanceMetrics(self.lens)
        bfl = calc.calculate_back_focal_length()
        
        self.assertIsNotNone(bfl)
        print(f"✓ Back focal length: {bfl:.3f} mm")
    
    def test_numerical_aperture(self):
        """Test numerical aperture calculation"""
        calc = PerformanceMetrics(self.lens)
        na = calc.calculate_numerical_aperture(half_angle_deg=15.0)
        
        self.assertIsNotNone(na)
        self.assertGreater(na, 0)
        self.assertLess(na, 1.0)
        print(f"✓ Numerical aperture: {na:.4f}")
    
    def test_resolution_estimate(self):
        """Test resolution estimation"""
        calc = PerformanceMetrics(self.lens)
        f_num = calc.calculate_f_number()
        resolution = calc.estimate_resolution_rayleigh(wavelength=550.0, f_number=f_num)
        
        self.assertIsNotNone(resolution)
        self.assertGreater(resolution, 0)
        print(f"✓ Resolution (Rayleigh): {resolution:.3f} μm")
    
    def test_mtf_cutoff(self):
        """Test MTF cutoff frequency"""
        calc = PerformanceMetrics(self.lens)
        f_num = calc.calculate_f_number()
        mtf = calc.estimate_mtf_cutoff(wavelength=550.0, f_number=f_num)
        
        self.assertIsNotNone(mtf)
        self.assertGreater(mtf, 0)
        print(f"✓ MTF cutoff: {mtf:.1f} lp/mm")
    
    def test_airy_disk(self):
        """Test Airy disk diameter calculation"""
        calc = PerformanceMetrics(self.lens)
        f_num = calc.calculate_f_number()
        airy = calc.calculate_airy_disk_diameter(wavelength=550.0, f_number=f_num)
        
        self.assertIsNotNone(airy)
        self.assertGreater(airy, 0)
        print(f"✓ Airy disk diameter: {airy:.3f} μm")
    
    def test_depth_of_field(self):
        """Test depth of field calculation"""
        calc = PerformanceMetrics(self.lens)
        f_num = calc.calculate_f_number()
        dof_near, dof_far = calc.calculate_depth_of_field(
            f_number=f_num,
            circle_of_confusion=0.03,
            object_distance=1000.0
        )
        
        self.assertIsNotNone(dof_near)
        self.assertGreater(dof_near, 0)
        print(f"✓ Depth of field: {dof_near:.1f} mm to {dof_far if dof_far != float('inf') else '∞'}")
    
    def test_field_of_view(self):
        """Test field of view calculation"""
        calc = PerformanceMetrics(self.lens)
        fov = calc.calculate_field_of_view(sensor_size=36.0)
        
        self.assertIsNotNone(fov)
        self.assertGreater(fov, 0)
        self.assertLess(fov, 180)
        print(f"✓ Field of view: {fov:.2f}°")
    
    def test_get_all_metrics(self):
        """Test getting all metrics at once"""
        calc = PerformanceMetrics(self.lens)
        metrics = calc.get_all_metrics(
            entrance_pupil_diameter=10.0,
            wavelength=550.0,
            object_distance=1000.0,
            sensor_size=36.0
        )
        
        self.assertIsInstance(metrics, dict)
        self.assertIn('effective_focal_length', metrics)
        self.assertIn('f_number', metrics)
        self.assertIn('back_focal_length', metrics)
        self.assertIn('resolution_um', metrics)
        self.assertIn('mtf_cutoff_lpmm', metrics)
        self.assertIn('field_of_view_deg', metrics)
        
        print(f"✓ All metrics calculated successfully")
        print(f"  - Focal length: {metrics['effective_focal_length']:.2f} mm")
        print(f"  - F-number: f/{metrics['f_number']:.2f}")
        print(f"  - Resolution: {metrics['resolution_um']:.3f} μm")
        print(f"  - Field of view: {metrics['field_of_view_deg']:.2f}°")
    
    def test_format_metrics_report(self):
        """Test metrics report formatting"""
        calc = PerformanceMetrics(self.lens)
        metrics = calc.get_all_metrics()
        report = calc.format_metrics_report(metrics)
        
        self.assertIsInstance(report, str)
        self.assertIn('PERFORMANCE METRICS DASHBOARD', report)
        self.assertIn('Effective Focal Length', report)
        self.assertIn('F-Number', report)
        self.assertIn('Resolution', report)
        
        print(f"✓ Metrics report formatted successfully")
        print(report)


class TestPerformanceMetricsWithSystem(unittest.TestCase):
    """Test performance metrics with optical systems"""
    
    def test_optical_system_metrics(self):
        """Test metrics for optical system"""
        lens1 = Lens(
            name="Element 1",
            radius_of_curvature_1=50.0,
            radius_of_curvature_2=-50.0,
            thickness=5.0,
            diameter=25.0,
            refractive_index=1.5168
        )
        
        system = OpticalSystem(name="Test System")
        system.add_element(lens1, position=0.0)
        
        calc = PerformanceMetrics(system)
        f_num = calc.calculate_f_number()
        
        self.assertIsNotNone(f_num)
        print(f"✓ System F-number: f/{f_num:.2f}")


def run_tests():
    """Run all performance metrics tests"""
    print("="*70)
    print("TESTING: Performance Metrics Dashboard")
    print("="*70)
    
    suite = unittest.TestLoader().loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print("\n" + "="*70)
    if result.wasSuccessful():
        print("✓ All performance metrics tests passed!")
    else:
        print("✗ Some tests failed")
    print("="*70)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
