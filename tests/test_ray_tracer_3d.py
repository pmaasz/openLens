import unittest
import math
import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.lens import Lens
from src.ray_tracer import Ray, LensRayTracer, Ray3D, LensRayTracer3D, SystemRayTracer3D
from src.vector3 import Vector3, vec3

class TestRayTracer3D(unittest.TestCase):
    def setUp(self):
        # Create a standard biconvex lens
        # f ~= 100mm
        self.lens = Lens(
            radius_of_curvature_1=100.0,
            radius_of_curvature_2=-100.0,
            thickness=10.0,
            diameter=50.0,
            refractive_index=1.5
        )
        self.tracer2d = LensRayTracer(self.lens)
        self.tracer3d = LensRayTracer3D(self.lens)

    def test_on_axis_ray_agreement(self):
        # 2D Trace
        ray2d = Ray(x_mm=-20, y_mm=0, angle_rad=0)
        self.tracer2d.trace_ray(ray2d)
        
        # 3D Trace
        ray3d = Ray3D(origin=vec3(-20, 0, 0), direction=vec3(1, 0, 0))
        self.tracer3d.trace_ray(ray3d)
        
        # Compare final positions (after propagation)
        last2d = ray2d.path[-1]
        last3d = ray3d.path[-1]
        
        # x coordinates should match
        self.assertAlmostEqual(last2d[0], last3d.x, places=4)
        # y coordinates should match (0)
        self.assertAlmostEqual(last2d[1], last3d.y, places=4)
        self.assertAlmostEqual(0, last3d.z, places=4)
        
        # Check angle/direction
        # 2D angle should match 3D direction angle
        # 3D direction is (cos(theta), sin(theta), 0)
        self.assertAlmostEqual(math.cos(ray2d.angle_rad), ray3d.direction.x, places=4)
        self.assertAlmostEqual(math.sin(ray2d.angle_rad), ray3d.direction.y, places=4)

    def test_off_axis_meridional_ray(self):
        # Ray at height 10mm
        h = 10.0
        
        # 2D Trace
        ray2d = Ray(x_mm=-20, y_mm=h, angle_rad=0)
        self.tracer2d.trace_ray(ray2d)
        
        # 3D Trace
        ray3d = Ray3D(origin=vec3(-20, h, 0), direction=vec3(1, 0, 0))
        self.tracer3d.trace_ray(ray3d)
        
        last2d = ray2d.path[-1]
        last3d = ray3d.path[-1]
        
        self.assertAlmostEqual(last2d[0], last3d.x, places=4)
        self.assertAlmostEqual(last2d[1], last3d.y, places=4)
        self.assertAlmostEqual(0, last3d.z, places=4)
        
        # Check exit direction
        self.assertAlmostEqual(math.cos(ray2d.angle_rad), ray3d.direction.x, places=4)
        self.assertAlmostEqual(math.sin(ray2d.angle_rad), ray3d.direction.y, places=4)

    def test_skew_ray_symmetry(self):
        # Trace two rays symmetric about the optical axis in the YZ plane
        # Ray 1: y=5, z=5
        # Ray 2: y=-5, z=-5
        # They should behave symmetrically
        
        ray1 = Ray3D(origin=vec3(-20, 5, 5), direction=vec3(1, 0, 0))
        ray2 = Ray3D(origin=vec3(-20, -5, -5), direction=vec3(1, 0, 0))
        
        self.tracer3d.trace_ray(ray1)
        self.tracer3d.trace_ray(ray2)
        
        end1 = ray1.path[-1]
        end2 = ray2.path[-1]
        
        # X should be same
        self.assertAlmostEqual(end1.x, end2.x, places=4)
        # Y and Z should be opposite
        self.assertAlmostEqual(end1.y, -end2.y, places=4)
        self.assertAlmostEqual(end1.z, -end2.z, places=4)
        
        # Directions should be symmetric
        self.assertAlmostEqual(ray1.direction.x, ray2.direction.x, places=4)
        self.assertAlmostEqual(ray1.direction.y, -ray2.direction.y, places=4)
        self.assertAlmostEqual(ray1.direction.z, -ray2.direction.z, places=4)

    def test_system_tracer(self):
        # Mock system object
        class MockSystem:
            def __init__(self, lens):
                self.elements = [MockElement(lens, 0), MockElement(lens, 50)]
        
        class MockElement:
            def __init__(self, lens, pos):
                self.lens = lens
                self.position = pos
        
        system = MockSystem(self.lens)
        tracer = SystemRayTracer3D(system)
        
        # Trace on-axis ray
        ray = Ray3D(origin=vec3(-20, 0, 0), direction=vec3(1, 0, 0))
        tracer.trace_ray(ray)
        
        # Should pass through two lenses
        # Path should have: Origin -> L1_Front -> L1_Back -> L2_Front -> L2_Back -> End
        # Length >= 6
        self.assertGreaterEqual(len(ray.path), 6)
        self.assertFalse(ray.terminated)

    def test_trace_edge_ray_crossed(self):
        # Create a lens with crossed surfaces at the edge
        # R=100, D=50, Th=5. Sag at D/2=25 is ~3.2mm. TotalSag ~6.4 > 5.0.
        # This creates a lens where surfaces cross near the edge.
        crossed_lens = Lens(
            radius_of_curvature_1=100.0,
            radius_of_curvature_2=-100.0,
            thickness=5.0,
            diameter=50.0,
            refractive_index=1.5
        )
        tracer = LensRayTracer3D(crossed_lens)
        
        # Ray at edge y=24
        # At y=24, sag is large enough to cross
        ray = Ray3D(vec3(-50, 24, 0), vec3(1, 0, 0))
        
        tracer.trace_ray(ray)
        
        # Should not terminate inside (should pass through or exit immediately)
        self.assertFalse(ray.terminated, "Ray terminated inside crossed lens region")

    def test_cemented_doublet_trace(self):
        """Test tracing through a cemented doublet (surfaces touching)."""
        # Create two lenses that touch
        # Lens 1: Biconvex
        lens1 = Lens(
            radius_of_curvature_1=50.0,
            radius_of_curvature_2=-50.0, 
            thickness=5.0,
            diameter=20.0,
            refractive_index=1.5
        )
        
        # Lens 2: Matches lens1 back curvature
        lens2 = Lens(
            radius_of_curvature_1=-50.0, # Matches lens1 back
            radius_of_curvature_2=50.0,
            thickness=5.0,
            diameter=20.0,
            refractive_index=1.6
        )
        
        class MockElement:
            def __init__(self, lens, pos):
                self.lens = lens
                self.position = pos

        class MockSystem:
            def __init__(self):
                # Lens 1 at 0. Ends at 5.
                # Lens 2 at 5. Ends at 10.
                self.elements = [MockElement(lens1, 0), MockElement(lens2, 5.0)]
        
        system = MockSystem()
        tracer = SystemRayTracer3D(system)
        
        # Trace on-axis ray
        ray = Ray3D(origin=vec3(-10, 0, 0), direction=vec3(1, 0, 0))
        tracer.trace_ray(ray)
        
        self.assertFalse(ray.terminated, "Ray terminated in cemented doublet")
        # Path: Start(-10), L1F(0), L1B/L2F(5), L2B(10), End(60)
        # Should have at least 5 points
        self.assertGreaterEqual(len(ray.path), 5)

if __name__ == '__main__':
    unittest.main()
