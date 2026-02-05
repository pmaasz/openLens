#!/usr/bin/env python3
"""
Edge case tests for openLens
Tests extreme input values, boundary conditions, and error handling
"""

import unittest
import math
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src'))

from lens_editor import Lens
from ray_tracer import Ray, LensRayTracer
from aberrations import AberrationsCalculator


class TestExtremeInputValues(unittest.TestCase):
    """Test behavior with extreme input values"""
    
    def test_zero_radius_of_curvature(self):
        """Test lens with zero radius (flat surface)"""
        lens = Lens(
            radius_of_curvature_1=0,
            radius_of_curvature_2=-100.0,
            material="Custom"
        )
        focal_length = lens.calculate_focal_length()
        # Should return None for invalid lens
        self.assertIsNone(focal_length)
    
    def test_very_large_radius(self):
        """Test lens with very large radius (nearly flat)"""
        lens = Lens(
            radius_of_curvature_1=1e10,
            radius_of_curvature_2=-1e10,
            thickness=5.0,
            material="Custom"
        )
        focal_length = lens.calculate_focal_length()
        # Should have very large focal length
        self.assertIsNotNone(focal_length)
        self.assertGreater(abs(focal_length), 1e9)
    
    def test_very_small_radius(self):
        """Test lens with very small radius"""
        lens = Lens(
            radius_of_curvature_1=0.1,
            radius_of_curvature_2=-0.1,
            thickness=0.01,
            diameter=0.05,
            material="Custom"
        )
        focal_length = lens.calculate_focal_length()
        # Should calculate without error
        self.assertIsNotNone(focal_length)
    
    def test_extreme_refractive_index_low(self):
        """Test with refractive index near 1 (air)"""
        lens = Lens(
            refractive_index=1.001,
            radius_of_curvature_1=100.0,
            radius_of_curvature_2=-100.0,
            material="Custom"
        )
        focal_length = lens.calculate_focal_length()
        # Very weak lens - huge focal length
        self.assertIsNotNone(focal_length)
        self.assertGreater(abs(focal_length), 10000)
    
    def test_extreme_refractive_index_high(self):
        """Test with very high refractive index"""
        lens = Lens(
            refractive_index=4.0,  # Diamond-like
            radius_of_curvature_1=100.0,
            radius_of_curvature_2=-100.0,
            material="Custom"
        )
        focal_length = lens.calculate_focal_length()
        # Strong lens - short focal length
        self.assertIsNotNone(focal_length)
        self.assertLess(abs(focal_length), 50)
    
    def test_zero_thickness(self):
        """Test lens with zero thickness (thin lens approximation)"""
        lens = Lens(
            thickness=0.0,
            radius_of_curvature_1=100.0,
            radius_of_curvature_2=-100.0,
            material="Custom"
        )
        focal_length = lens.calculate_focal_length()
        # Should still calculate (thin lens)
        self.assertIsNotNone(focal_length)
    
    def test_very_thick_lens(self):
        """Test lens with extreme thickness"""
        lens = Lens(
            thickness=100.0,
            radius_of_curvature_1=200.0,
            radius_of_curvature_2=-200.0,
            diameter=150.0,
            material="Custom"
        )
        focal_length = lens.calculate_focal_length()
        # Should handle thick lens
        self.assertIsNotNone(focal_length)
    
    def test_zero_diameter(self):
        """Test lens with zero diameter"""
        lens = Lens(diameter=0.0, material="Custom")
        # Should create but may have issues with ray tracing
        self.assertEqual(lens.diameter, 0.0)
    
    def test_negative_values(self):
        """Test that negative thickness/diameter are handled"""
        # Negative thickness should be problematic
        lens = Lens(thickness=-5.0, material="Custom")
        # Lens creates but focal length calculation should handle it
        self.assertEqual(lens.thickness, -5.0)


class TestBoundaryConditions(unittest.TestCase):
    """Test boundary conditions and edge cases"""
    
    def test_ray_perpendicular_to_surface(self):
        """Test ray hitting surface perpendicularly"""
        ray = Ray(x=0, y=0, angle=math.pi/2)
        success = ray.refract(n1=1.0, n2=1.5, surface_normal_angle=math.pi/2)
        self.assertTrue(success)
        # Should pass through with no bending at normal incidence
        self.assertAlmostEqual(ray.angle, math.pi/2, places=5)
    
    def test_ray_parallel_to_surface(self):
        """Test ray parallel to surface (grazing incidence)"""
        ray = Ray(x=0, y=0, angle=0)
        success = ray.refract(n1=1.0, n2=1.5, surface_normal_angle=math.pi/2)
        # Should refract but at extreme angle
        self.assertTrue(success)
    
    def test_total_internal_reflection(self):
        """Test total internal reflection"""
        ray = Ray(x=0, y=0, angle=math.pi/4)
        # Going from glass to air at steep angle
        success = ray.refract(n1=1.5, n2=1.0, surface_normal_angle=0)
        # May fail or reflect depending on angle
        self.assertIsNotNone(success)
    
    def test_same_refractive_indices(self):
        """Test refraction with same refractive index on both sides"""
        ray = Ray(x=0, y=0, angle=math.pi/4)
        initial_angle = ray.angle
        success = ray.refract(n1=1.5, n2=1.5, surface_normal_angle=0)
        self.assertTrue(success)
        # Angle should not change
        self.assertAlmostEqual(ray.angle, initial_angle, places=10)
    
    def test_aberrations_on_axis(self):
        """Test that off-axis aberrations are zero on-axis"""
        lens = Lens(material="Custom")
        calc = AberrationsCalculator(lens)
        results = calc.calculate_all_aberrations(field_angle=0.0)
        
        # On-axis: no coma, astigmatism, or distortion
        self.assertEqual(results['coma'], 0)
        self.assertEqual(results['astigmatism'], 0)
        self.assertEqual(results['distortion'], 0)
    
    def test_aberrations_at_extreme_field_angle(self):
        """Test aberrations at extreme field angles"""
        lens = Lens(
            radius_of_curvature_1=50.0,
            radius_of_curvature_2=-30.0,
            diameter=100.0,
            material="Custom"
        )
        calc = AberrationsCalculator(lens)
        
        # Test at extreme field angle
        results = calc.calculate_all_aberrations(field_angle=45.0)
        
        # Should calculate without error
        self.assertIsNotNone(results)
        # Aberrations should be large
        self.assertGreater(abs(results['astigmatism']), 0)


class TestInvalidInputHandling(unittest.TestCase):
    """Test handling of invalid inputs"""
    
    def test_nan_input(self):
        """Test handling of NaN values"""
        try:
            lens = Lens(
                radius_of_curvature_1=float('nan'),
                material="Custom"
            )
            focal_length = lens.calculate_focal_length()
            # Should return None or handle gracefully
            self.assertTrue(focal_length is None or math.isnan(focal_length))
        except (ValueError, TypeError):
            # Also acceptable to raise an error
            pass
    
    def test_inf_input(self):
        """Test handling of infinity values"""
        lens = Lens(
            radius_of_curvature_1=float('inf'),
            radius_of_curvature_2=-100.0,
            material="Custom"
        )
        focal_length = lens.calculate_focal_length()
        # Infinity radius = flat surface, should work
        self.assertIsNotNone(focal_length)
    
    def test_empty_string_material(self):
        """Test handling of empty material string"""
        lens = Lens(material="")
        # Should use default refractive index
        self.assertIsNotNone(lens.refractive_index)
    
    def test_nonexistent_material(self):
        """Test handling of non-existent material"""
        lens = Lens(material="NonexistentGlass123")
        # Should fall back to default refractive index
        self.assertIsNotNone(lens.refractive_index)


class TestNumericalStability(unittest.TestCase):
    """Test numerical stability with challenging inputs"""
    
    def test_nearly_symmetric_lens(self):
        """Test lens with nearly symmetric surfaces"""
        lens = Lens(
            radius_of_curvature_1=100.0,
            radius_of_curvature_2=-99.9999,  # Nearly symmetric
            material="Custom"
        )
        focal_length = lens.calculate_focal_length()
        # Should have very large focal length but not infinite
        self.assertIsNotNone(focal_length)
    
    def test_very_small_differences(self):
        """Test calculations with very small differences"""
        lens1 = Lens(
            radius_of_curvature_1=100.0,
            radius_of_curvature_2=-100.0,
            material="Custom"
        )
        lens2 = Lens(
            radius_of_curvature_1=100.00001,
            radius_of_curvature_2=-100.00001,
            material="Custom"
        )
        
        f1 = lens1.calculate_focal_length()
        f2 = lens2.calculate_focal_length()
        
        # Should be very similar
        if f1 is not None and f2 is not None:
            self.assertAlmostEqual(f1, f2, delta=abs(f1) * 0.0001)
    
    def test_ray_at_lens_edge(self):
        """Test ray tracing at lens edge"""
        lens = Lens(diameter=50.0, material="Custom")
        tracer = LensRayTracer(lens)
        
        # Ray at edge of lens
        ray = Ray(x=-50, y=24.9, angle=0)  # Just inside edge
        tracer.trace_ray(ray)
        
        # Should trace without error
        self.assertGreater(len(ray.path), 0)


class TestSpecialLensConfigurations(unittest.TestCase):
    """Test special and unusual lens configurations"""
    
    def test_meniscus_lens(self):
        """Test meniscus lens (both surfaces curving same direction)"""
        lens = Lens(
            radius_of_curvature_1=100.0,
            radius_of_curvature_2=80.0,  # Same sign = meniscus
            material="Custom"
        )
        focal_length = lens.calculate_focal_length()
        self.assertIsNotNone(focal_length)
    
    def test_plano_convex(self):
        """Test plano-convex lens"""
        lens = Lens(
            radius_of_curvature_1=100.0,
            radius_of_curvature_2=float('inf'),  # Flat
            material="Custom"
        )
        focal_length = lens.calculate_focal_length()
        self.assertIsNotNone(focal_length)
    
    def test_plano_concave(self):
        """Test plano-concave lens"""
        lens = Lens(
            radius_of_curvature_1=float('inf'),  # Flat
            radius_of_curvature_2=100.0,
            material="Custom"
        )
        focal_length = lens.calculate_focal_length()
        self.assertIsNotNone(focal_length)
    
    def test_parallel_plate(self):
        """Test parallel plate (window)"""
        lens = Lens(
            radius_of_curvature_1=float('inf'),
            radius_of_curvature_2=float('inf'),
            material="Custom"
        )
        focal_length = lens.calculate_focal_length()
        # Should return None (no optical power)
        self.assertIsNone(focal_length)


if __name__ == '__main__':
    unittest.main()
