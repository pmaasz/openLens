import unittest
import math
import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.optical_system import OpticalSystem
from src.lens import Lens
from src.optimizer import LensOptimizer, OptimizationVariable, OptimizationTarget

class TestAdvancedOptimizer(unittest.TestCase):
    def setUp(self):
        # Create a simple singlet
        self.lens = Lens(
            radius_of_curvature_1=100.0,
            radius_of_curvature_2=-100.0,
            thickness=5.0,
            diameter=25.0,
            refractive_index=1.5168 # BK7 approx
        )
        self.system = OpticalSystem()
        self.system.add_lens(self.lens)
        
        # Variables: R1, R2
        self.variables = [
            OptimizationVariable("R1", 0, "radius_of_curvature_1", 100.0, 50.0, 200.0),
            OptimizationVariable("R2", 0, "radius_of_curvature_2", -100.0, -200.0, -50.0)
        ]

    def test_optimize_spot_size(self):
        """Test optimizing for RMS spot size"""
        # Target: Minimize RMS spot size
        # We start with a symmetric biconvex lens.
        # Ideally, for infinite conjugate, best shape is convex-plano or similar (depending on index).
        # Optimization should move R1 and R2 to reduce spherical aberration (RMS spot).
        
        targets = [
            OptimizationTarget("rms_spot_radius", 0.0, weight=100.0, target_type="minimize"),
            # Constrain focal length to avoid drifting too far
            OptimizationTarget("focal_length", 96.8, weight=1.0, target_type="target")
        ]
        
        optimizer = LensOptimizer(self.system, self.variables, targets)
        result = optimizer.optimize_simplex(max_iterations=20)
        
        self.assertTrue(result.success)
        # Check if merit improved
        self.assertLessEqual(result.final_merit, result.initial_merit)
        
        # Check if R1 changed (it should, to minimize spherical aberration)
        new_r1 = result.optimized_system.elements[0].lens.radius_of_curvature_1
        self.assertNotAlmostEqual(new_r1, 100.0, delta=0.1)

    def test_optimize_mtf(self):
        """Test optimizing for MTF"""
        # This test might be skipped if numpy not available
        try:
            import numpy
            from src.analysis.beam_synthesis import NUMPY_AVAILABLE
            if not NUMPY_AVAILABLE:
                self.skipTest("Numpy not available (internal check)")
        except ImportError:
            self.skipTest("Numpy not available")

        # Target: Maximize MTF volume
        targets = [
            OptimizationTarget("mtf", 0.0, weight=10.0, target_type="maximize"),
            OptimizationTarget("focal_length", 96.8, weight=1.0, target_type="target")
        ]
        
        optimizer = LensOptimizer(self.system, self.variables, targets)
        result = optimizer.optimize_simplex(max_iterations=5) # Very fast test, FFT is slow
        
        self.assertTrue(result.success)

if __name__ == '__main__':
    unittest.main()
