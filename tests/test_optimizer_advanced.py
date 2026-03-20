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
            OptimizationVariable(
                name="R1",
                element_index=0,
                parameter="radius_of_curvature_1",
                current_value=100.0,
                min_value=50.0,
                max_value=200.0
            ),
            OptimizationVariable(
                name="R2",
                element_index=0,
                parameter="radius_of_curvature_2",
                current_value=-100.0,
                min_value=-200.0,
                max_value=-50.0
            )
        ]

    def test_optimize_spot_size(self):
        """Test optimizing for RMS spot size"""
        targets = [
            OptimizationTarget("rms_spot_radius", 0.0, weight=100.0, target_type="minimize"),
            OptimizationTarget("focal_length", 96.8, weight=1.0, target_type="target")
        ]
        
        optimizer = LensOptimizer(self.system, self.variables, targets)
        result = optimizer.optimize_simplex(max_iterations=20)
        
        self.assertTrue(result.success)
        self.assertLessEqual(result.final_merit, result.initial_merit)
        
        new_r1 = result.optimized_system.elements[0].lens.radius_of_curvature_1
        self.assertNotAlmostEqual(new_r1, 100.0, delta=0.1)

    def test_edge_thickness_penalty(self):
        """Test that invalid geometries (negative edge thickness) are penalized"""
        # Create an impossible lens: R=26, D=50. Sag approx 7.1mm per side. Total sag 14.2mm.
        # If center thickness is 5mm, edge thickness = 5 - 14.2 = -9.2mm (Impossible!)
        
        impossible_lens = Lens(
            radius_of_curvature_1=26.0, 
            radius_of_curvature_2=-26.0, 
            thickness=5.0, 
            diameter=50.0, 
            refractive_index=1.5
        )
        sys_bad = OpticalSystem("Bad System")
        sys_bad.add_lens(impossible_lens)
        
        vars = [
            OptimizationVariable(
                name="R1",
                element_index=0,
                parameter="radius_of_curvature_1",
                current_value=26.0,
                min_value=10.0,
                max_value=100.0
            )
        ]
        optimizer = LensOptimizer(sys_bad, vars, []) 
        
        merit = optimizer.merit_function.evaluate(sys_bad)
        self.assertGreater(merit, 1000.0)

    def test_coma_target(self):
        """Test that coma target can be evaluated"""
        targets = [
            OptimizationTarget(
                name="coma",
                target_value=0.0,
                weight=1.0,
                target_type="minimize"
            )
        ]
        optimizer = LensOptimizer(self.system, self.variables, targets)
        merit = optimizer._evaluate_design([100.0, -100.0])
        self.assertIsInstance(merit, float)
        self.assertGreaterEqual(merit, 0.0)

    def test_astigmatism_target(self):
        """Test that astigmatism target can be evaluated"""
        targets = [
            OptimizationTarget(
                name="astigmatism",
                target_value=0.0,
                weight=1.0,
                target_type="minimize"
            )
        ]
        optimizer = LensOptimizer(self.system, self.variables, targets)
        merit = optimizer._evaluate_design([100.0, -100.0])
        self.assertIsInstance(merit, float)
        self.assertGreaterEqual(merit, 0.0)

if __name__ == '__main__':
    unittest.main()
