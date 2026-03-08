import unittest
import math
import sys
import os

# Add src to path
# Use reliable path relative to project root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src')))

from optical_system import OpticalSystem
from lens import Lens
from ray_tracer import SystemRayTracer, Ray

class TestSystemRayTracer(unittest.TestCase):
    def setUp(self):
        # Create two lenses
        self.lens1 = Lens(name="Lens 1", radius_of_curvature_1=100, radius_of_curvature_2=-100, thickness=10, diameter=50)
        self.lens2 = Lens(name="Lens 2", radius_of_curvature_1=100, radius_of_curvature_2=-100, thickness=10, diameter=50)
        
        # Create system
        self.system = OpticalSystem(name="Test System")
        self.system.add_lens(self.lens1, air_gap_before=0)
        self.system.add_lens(self.lens2, air_gap_before=20) # 20mm gap
        
        self.tracer = SystemRayTracer(self.system)

    def test_system_structure(self):
        """Verify system structure"""
        self.assertEqual(len(self.system.elements), 2)
        self.assertEqual(len(self.system.air_gaps), 1)
        self.assertEqual(self.system.air_gaps[0].thickness, 20.0)
        
        # Check positions
        # Lens 1 at 0.0, thickness 10.0
        # Gap starts at 10.0, thickness 20.0
        # Lens 2 starts at 30.0
        self.assertEqual(self.system.elements[0].position, 0.0)
        self.assertEqual(self.system.elements[1].position, 30.0)

    def test_trace_parallel_rays(self):
        """Test tracing parallel rays through system"""
        rays = self.tracer.trace_parallel_rays(num_rays=3, angle=0.0)
        
        self.assertEqual(len(rays), 3)
        
        for ray in rays:
            # Ray should have multiple points in path
            self.assertGreater(len(ray.path), 2)
            
            # Final x should be beyond the last lens
            # Last lens ends at 30 + 10 = 40
            # Ray propagates 100mm after
            final_x = ray.path[-1][0]
            self.assertGreater(final_x, 40.0)

if __name__ == '__main__':
    unittest.main()
