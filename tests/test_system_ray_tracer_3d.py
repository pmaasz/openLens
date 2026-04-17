#!/usr/bin/env python3
import unittest
import sys
import os
import math

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from lens import Lens
from optical_system import OpticalSystem
from ray_tracer import Ray3D, SystemRayTracer3D, Vector3, vec3, Matrix4x4

class TestSystemRayTracer3D(unittest.TestCase):
    def setUp(self):
        # Create a simple doublet-like system
        self.system = OpticalSystem(name="Test System")
        
        # Lens 1: Biconvex
        self.l1 = Lens(
            name="L1",
            radius_of_curvature_1=100.0,
            radius_of_curvature_2=-100.0,
            thickness=10.0,
            diameter=50.0,
            material="BK7"
        )
        # Lens 2: Biconvex
        self.l2 = Lens(
            name="L2",
            radius_of_curvature_1=100.0,
            radius_of_curvature_2=-100.0,
            thickness=10.0,
            diameter=50.0,
            material="BK7"
        )
        
        self.system.add_lens(self.l1)
        self.system.add_lens(self.l2, air_gap_before=20.0)
        
        self.tracer = SystemRayTracer3D(self.system)

    def test_on_axis_ray_3d(self):
        """Test that an on-axis ray stays on the optical axis in 3D."""
        origin = vec3(-50, 0, 0)
        direction = vec3(1, 0, 0)
        ray = Ray3D(origin, direction)
        
        self.tracer.trace_ray(ray)
        
        for p in ray.path:
            self.assertAlmostEqual(p.y, 0, places=5)
            self.assertAlmostEqual(p.z, 0, places=5)
        
        self.assertFalse(ray.terminated)
        self.assertGreater(len(ray.path), 1)

    def test_off_axis_ray_3d(self):
        """Test an off-axis ray through the system."""
        origin = vec3(-50, 5, 0)
        direction = vec3(1, 0, 0)
        ray = Ray3D(origin, direction)
        
        self.tracer.trace_ray(ray)
        
        # Ray should be bent toward axis by biconvex lenses
        self.assertGreater(len(ray.path), 4) # Should hit 4 surfaces
        
        # Final direction should have negative Y component (converging)
        self.assertLess(ray.direction.y, 0)

    def test_system_with_offsets(self):
        """Test if the tracer correctly uses element positions."""
        # Check positions in system
        # L1 at 0
        # L2 at L1.thick (10) + gap (20) = 30
        self.assertEqual(self.system.elements[0].position, 0.0)
        self.assertEqual(self.system.elements[1].position, 30.0)
        
        origin = vec3(-10, 5, 0)
        direction = vec3(1, 0, 0)
        ray = Ray3D(origin, direction)
        
        self.tracer.trace_ray(ray)
        
        # Ray should hit L1 (front vertex at 0) and L2 (front vertex at 30)
        # Path should contain intersections at roughly x=0, x=10, x=30, x=40
        x_coords = [p.x for p in ray.path]
        
        # Verify it passed through both lenses
        has_l1_front = any(abs(x - 0) < 1.0 for x in x_coords)
        has_l1_back = any(abs(x - 10) < 1.0 for x in x_coords)
        has_l2_front = any(abs(x - 30) < 1.0 for x in x_coords)
        has_l2_back = any(abs(x - 40) < 1.0 for x in x_coords)
        
        self.assertTrue(has_l1_front, f"Missed L1 front: {x_coords}")
        self.assertTrue(has_l1_back, f"Missed L1 back: {x_coords}")
        self.assertTrue(has_l2_front, f"Missed L2 front: {x_coords}")
        self.assertTrue(has_l2_back, f"Missed L2 back: {x_coords}")

if __name__ == '__main__':
    unittest.main()
