import unittest
import sys
import os
from typing import List

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.lens import Lens
from src.optical_system import OpticalSystem
from src.optimizer import LensOptimizer, OptimizationVariable, OptimizationTarget

class TestLensOptimizerAPI(unittest.TestCase):
    def setUp(self):
        # Create a simple system for testing
        self.lens = Lens(
            radius_of_curvature_1=50.0, 
            radius_of_curvature_2=-50.0, 
            thickness=10.0, 
            diameter=50.0, 
            refractive_index=1.5
        )
        self.system = OpticalSystem("Test System")
        self.system.add_lens(self.lens)
        
        # Setup variables
        self.variables = [
            OptimizationVariable(
                name="R1",
                element_index=0,
                parameter="radius_of_curvature_1",
                current_value=50.0,
                min_value=10.0,
                max_value=100.0
            )
        ]
        
        # Setup targets
        self.targets = [
            OptimizationTarget(
                name="focal_length",
                target_value=100.0,
                weight=1.0,
                target_type="target"
            )
        ]

    def test_optimize_method_exists_and_runs(self):
        """Test that the generic optimize method works"""
        optimizer = LensOptimizer(self.system, self.variables, self.targets)
        # Run with very few iterations just to check it runs without error
        result = optimizer.optimize(max_iterations=5)
        self.assertTrue(result.success)
        self.assertIsNotNone(result.optimized_system)

    def test_spherical_aberration_calculation_in_merit(self):
        """Test that spherical aberration calculation doesn't crash the merit function"""
        # Add spherical aberration target
        sa_target = OptimizationTarget(
            name="spherical_aberration",
            target_value=0.0,
            weight=1.0,
            target_type="minimize"
        )
        self.targets.append(sa_target)
        
        optimizer = LensOptimizer(self.system, self.variables, self.targets)
        
        # Manually evaluate merit to check for crash
        try:
            merit = optimizer._evaluate_design([50.0])
            self.assertIsInstance(merit, float)
        except Exception as e:
            self.fail(f"Merit evaluation failed with exception: {e}")

if __name__ == '__main__':
    unittest.main()
