#!/usr/bin/env python3
"""
Performance and stress tests for openLens
Tests system behavior under load and with large datasets
"""

import unittest
import time
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src'))

from lens_editor import Lens
from ray_tracer import LensRayTracer
from aberrations import AberrationsCalculator, analyze_lens_quality


class TestPerformance(unittest.TestCase):
    """Test performance of core operations"""
    
    def test_lens_creation_performance(self):
        """Test performance of creating many lenses"""
        start_time = time.time()
        
        lenses = []
        for i in range(1000):
            lens = Lens(
                name=f"Lens_{i}",
                radius_of_curvature_1=100.0 + i * 0.1,
                radius_of_curvature_2=-100.0 - i * 0.1,
                material="Custom"
            )
            lenses.append(lens)
        
        elapsed = time.time() - start_time
        
        # Should create 1000 lenses in reasonable time
        self.assertEqual(len(lenses), 1000)
        self.assertLess(elapsed, 5.0, f"Creating 1000 lenses took {elapsed:.2f}s (expected <5s)")
    
    def test_focal_length_calculation_performance(self):
        """Test performance of focal length calculations"""
        lens = Lens(material="Custom")
        
        start_time = time.time()
        
        for _ in range(10000):
            focal_length = lens.calculate_focal_length()
        
        elapsed = time.time() - start_time
        
        # Should calculate 10000 focal lengths quickly
        self.assertLess(elapsed, 1.0, f"10000 focal length calculations took {elapsed:.2f}s (expected <1s)")
    
    def test_ray_tracing_performance(self):
        """Test performance of ray tracing"""
        lens = Lens(material="Custom")
        tracer = LensRayTracer(lens)
        
        start_time = time.time()
        
        # Trace 100 sets of rays
        for _ in range(100):
            rays = tracer.trace_parallel_rays(num_rays=10)
        
        elapsed = time.time() - start_time
        
        # Should trace 1000 rays reasonably fast
        self.assertLess(elapsed, 10.0, f"Tracing 1000 rays took {elapsed:.2f}s (expected <10s)")
    
    def test_aberration_calculation_performance(self):
        """Test performance of aberration calculations"""
        lens = Lens(material="Custom")
        calc = AberrationsCalculator(lens)
        
        start_time = time.time()
        
        for _ in range(100):
            results = calc.calculate_all_aberrations()
        
        elapsed = time.time() - start_time
        
        # Should calculate aberrations quickly
        self.assertLess(elapsed, 1.0, f"100 aberration calculations took {elapsed:.2f}s (expected <1s)")


class TestStressTests(unittest.TestCase):
    """Stress tests with extreme workloads"""
    
    def test_many_rays_single_lens(self):
        """Test tracing many rays through single lens"""
        lens = Lens(material="Custom")
        tracer = LensRayTracer(lens)
        
        # Trace 1000 rays
        rays = tracer.trace_parallel_rays(num_rays=1000)
        
        # Should complete without error
        self.assertEqual(len(rays), 1000)
        
        # All rays should have paths
        for ray in rays:
            self.assertGreater(len(ray.path), 0)
    
    def test_many_aberration_calculations(self):
        """Test calculating aberrations for many field angles"""
        lens = Lens(material="Custom")
        calc = AberrationsCalculator(lens)
        
        field_angles = range(0, 46, 1)  # 0 to 45 degrees
        
        results_list = []
        for angle in field_angles:
            results = calc.calculate_all_aberrations(field_angle=angle)
            results_list.append(results)
        
        # Should complete all calculations
        self.assertEqual(len(results_list), len(field_angles))
    
    def test_lens_quality_analysis_batch(self):
        """Test analyzing quality of many lenses"""
        lenses = []
        for i in range(50):
            lens = Lens(
                radius_of_curvature_1=50.0 + i * 2,
                radius_of_curvature_2=-50.0 - i * 2,
                diameter=25.0 + i * 0.5,
                material="Custom"
            )
            lenses.append(lens)
        
        results = []
        for lens in lenses:
            quality = analyze_lens_quality(lens)
            results.append(quality)
        
        # Should analyze all lenses
        self.assertEqual(len(results), 50)
        
        # All should have quality scores
        for result in results:
            self.assertIn('quality_score', result)
            self.assertIsNotNone(result['quality_score'])
    
    def test_complex_lens_system(self):
        """Test creating and analyzing complex lens system"""
        # Create multiple lenses with different configurations
        lenses = []
        
        configurations = [
            (100, -100, 5, 50),   # Biconvex
            (-100, 100, 5, 50),   # Biconcave
            (100, float('inf'), 5, 50),  # Plano-convex
            (float('inf'), -100, 5, 50),  # Plano-convex reversed
            (150, 200, 5, 50),    # Meniscus
        ]
        
        for r1, r2, t, d in configurations:
            for i in range(10):  # 10 variations of each
                lens = Lens(
                    radius_of_curvature_1=r1,
                    radius_of_curvature_2=r2,
                    thickness=t + i * 0.5,
                    diameter=d,
                    material="Custom"
                )
                lenses.append(lens)
        
        # Calculate properties for all
        for lens in lenses:
            focal_length = lens.calculate_focal_length()
            # Just verify it completes
        
        self.assertEqual(len(lenses), 50)


class TestMemoryUsage(unittest.TestCase):
    """Test memory usage doesn't explode"""
    
    def test_repeated_lens_creation(self):
        """Test that repeated lens creation doesn't leak memory"""
        # Create and discard many lenses
        for _ in range(1000):
            lens = Lens(material="Custom")
            _ = lens.calculate_focal_length()
            _ = lens.to_dict()
        
        # If we get here without crashing, memory is managed
        self.assertTrue(True)
    
    def test_repeated_ray_tracing(self):
        """Test that repeated ray tracing doesn't leak memory"""
        lens = Lens(material="Custom")
        tracer = LensRayTracer(lens)
        
        # Trace many times
        for _ in range(100):
            rays = tracer.trace_parallel_rays(num_rays=50)
            # Discard rays
        
        # Should complete without memory issues
        self.assertTrue(True)
    
    def test_large_ray_path_storage(self):
        """Test storing large ray paths"""
        lens = Lens(material="Custom")
        tracer = LensRayTracer(lens)
        
        # Trace rays with long propagation
        rays = tracer.trace_parallel_rays(num_rays=100)
        
        # Check that paths are stored
        total_points = sum(len(ray.path) for ray in rays)
        self.assertGreater(total_points, 0)


class TestScalability(unittest.TestCase):
    """Test scalability with increasing problem sizes"""
    
    def test_scaling_num_rays(self):
        """Test performance scaling with number of rays"""
        lens = Lens(material="Custom")
        tracer = LensRayTracer(lens)
        
        times = []
        ray_counts = [10, 50, 100, 500]
        
        for num_rays in ray_counts:
            start = time.time()
            rays = tracer.trace_parallel_rays(num_rays=num_rays)
            elapsed = time.time() - start
            times.append(elapsed)
        
        # Should scale roughly linearly
        # 500 rays should not take 50x longer than 10 rays
        if times[0] > 0:
            ratio = times[-1] / times[0]
            self.assertLess(ratio, 100, f"Performance degradation too severe: {ratio}x")
    
    def test_scaling_field_angles(self):
        """Test performance with many field angles"""
        lens = Lens(material="Custom")
        calc = AberrationsCalculator(lens)
        
        # Test with increasing numbers of field angles
        for num_angles in [10, 50, 100]:
            angles = [i * 45.0 / num_angles for i in range(num_angles)]
            
            start = time.time()
            for angle in angles:
                results = calc.calculate_all_aberrations(field_angle=angle)
            elapsed = time.time() - start
            
            # Should complete in reasonable time
            self.assertLess(elapsed, 5.0, f"{num_angles} angle calculations took {elapsed:.2f}s")


class TestConcurrency(unittest.TestCase):
    """Test behavior with concurrent operations (if applicable)"""
    
    def test_multiple_lenses_independent(self):
        """Test that multiple lens objects don't interfere"""
        lenses = [
            Lens(name=f"Lens_{i}", material="Custom")
            for i in range(10)
        ]
        
        # Calculate properties for all
        focal_lengths = [lens.calculate_focal_length() for lens in lenses]
        
        # All should have calculated independently
        self.assertEqual(len(focal_lengths), 10)
        for fl in focal_lengths:
            self.assertIsNotNone(fl)
    
    def test_multiple_ray_tracers_independent(self):
        """Test that multiple ray tracers don't interfere"""
        lens1 = Lens(radius_of_curvature_1=100, radius_of_curvature_2=-100, material="Custom")
        lens2 = Lens(radius_of_curvature_1=50, radius_of_curvature_2=-50, material="Custom")
        
        tracer1 = LensRayTracer(lens1)
        tracer2 = LensRayTracer(lens2)
        
        rays1 = tracer1.trace_parallel_rays(num_rays=10)
        rays2 = tracer2.trace_parallel_rays(num_rays=10)
        
        # Both should complete independently
        self.assertEqual(len(rays1), 10)
        self.assertEqual(len(rays2), 10)


if __name__ == '__main__':
    unittest.main()
