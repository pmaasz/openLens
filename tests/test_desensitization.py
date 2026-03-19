import unittest
import math
import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.optical_system import OpticalSystem
from src.lens import Lens
from src.optimizer import OptimizationVariable, OptimizationTarget, LensOptimizer
from src.desensitization import DesensitizationOptimizer, RobustMeritFunction
from src.tolerancing import ToleranceOperand, ToleranceType

class TestDesensitization(unittest.TestCase):
    def setUp(self):
        # Create a simple system
        # Use a "Critical Angle" scenario where small change causes TIR or large aberration?
        # Or just a simple lens where we want to avoid very steep curves.
        
        self.lens = Lens(
            radius_of_curvature_1=50.0,
            radius_of_curvature_2=-50.0,
            thickness=5.0,
            diameter=25.0,
            refractive_index=1.5
        )
        self.system = OpticalSystem()
        self.system.add_lens(self.lens)
        
        self.variables = [
            OptimizationVariable("R1", 0, "radius_of_curvature_1", 50.0, 20.0, 100.0),
        ]
        
        # Target: Focal length 50mm
        self.targets = [
            OptimizationTarget("focal_length", 50.0, weight=1.0, target_type="target")
        ]
        
        # Tolerances to be insensitive to: R1 variation
        self.tolerances = [
            ToleranceOperand(0, ToleranceType.RADIUS_1, -0.1, 0.1)
        ]

    def test_robust_merit_function(self):
        """Test that RobustMeritFunction adds penalty for sensitivity"""
        # 1. Standard merit
        merit_func = RobustMeritFunction(self.system, self.targets, self.tolerances, sensitivity_weight=0.0)
        nominal_merit = merit_func.evaluate(self.system)
        
        # 2. Robust merit
        robust_func = RobustMeritFunction(self.system, self.targets, self.tolerances, sensitivity_weight=100.0)
        robust_merit = robust_func.evaluate(self.system)
        
        # Since R1 affects focal length, perturbing R1 changes merit.
        # So sensitivity > 0.
        # Therefore robust_merit > nominal_merit
        self.assertGreater(robust_merit, nominal_merit)

    def test_desensitization_optimization(self):
        """Test the DesensitizationOptimizer runs"""
        optimizer = DesensitizationOptimizer(self.system, self.variables, self.targets)
        
        # Run optimization
        result = optimizer.optimize_robust(self.tolerances, max_iterations=10)
        
        self.assertTrue(result.success)
        # It's hard to assert "it is more robust" without a complex setup, 
        # but we check it runs and produces valid system.
        f = result.optimized_system.get_system_focal_length()
        self.assertIsNotNone(f)

if __name__ == '__main__':
    unittest.main()
