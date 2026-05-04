import unittest
import math
import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.optical_system import OpticalSystem
from src.lens import Lens
from src.optimizer import OptimizationVariable, OptimizationTarget
from src.global_optimizer import GlobalOptimizer

class TestGlobalOptimizer(unittest.TestCase):
    def setUp(self):
        # Create a simple system that has a local minimum? 
        # Or just a standard test case.
        self.lens = Lens(
            radius_of_curvature_1=100.0,
            radius_of_curvature_2=-100.0,
            thickness=5.0,
            diameter=25.0,
            refractive_index=1.5
        )
        self.system = OpticalSystem()
        self.system.add_lens(self.lens)
        
        self.variables = [
            OptimizationVariable("R1", 0, "radius_of_curvature_1", 100.0, 50.0, 150.0),
        ]
        
        # Target: specific focal length
        self.targets = [
            OptimizationTarget("focal_length", 80.0, weight=1.0, target_type="target")
        ]

    def test_simulated_annealing(self):
        """Test Simulated Annealing convergence"""
        optimizer = GlobalOptimizer(self.system, self.variables, self.targets, seed=42)
        
        # Run SA
        result = optimizer.optimize_simulated_annealing(
            max_iterations=100,
            initial_temperature=10.0,
            cooling_rate=0.8
        )
        
        self.assertTrue(result.success)
        self.assertLess(result.final_merit, result.initial_merit)
        
        # Check result
        f = result.optimized_system.get_system_focal_length()
        self.assertAlmostEqual(f, 80.0, delta=1.0) # SA is stochastic, allow loose delta

    # def test_genetic_algorithm(self):
    #     """Test Genetic Algorithm convergence"""
    #     optimizer = GlobalOptimizer(self.system, self.variables, self.targets)
        
    #     # Run GA
    #     result = optimizer.optimize_genetic(
    #         population_size=10,
    #         generations=5
    #     )
        
    #     self.assertTrue(result.success)
    #     self.assertLess(result.final_merit, result.initial_merit)

if __name__ == '__main__':
    unittest.main()
