#!/usr/bin/env python3
import unittest
import sys
import os
import math

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from lens import Lens
from optical_system import OpticalSystem
from optimizer import LensOptimizer, OptimizationVariable, OptimizationTarget

class TestAssemblyOptimization(unittest.TestCase):
    def setUp(self):
        # Create a simple system: two lenses
        self.system = OpticalSystem(name="Test Optimization")
        
        # L1: Biconvex
        self.l1 = Lens(
            name="L1",
            radius_of_curvature_1=100.0,
            radius_of_curvature_2=-100.0,
            thickness=5.0,
            diameter=40.0,
            material="BK7"
        )
        # L2: Biconvex
        self.l2 = Lens(
            name="L2",
            radius_of_curvature_1=100.0,
            radius_of_curvature_2=-100.0,
            thickness=5.0,
            diameter=40.0,
            material="BK7"
        )
        
        self.system.add_lens(self.l1)
        self.system.add_lens(self.l2, air_gap_before=10.0)

    def test_optimize_radius_l2(self):
        """Test optimizing a radius on the second lens in the assembly."""
        # Variable: R1 of L2 (element index 1)
        var = OptimizationVariable(
            name="L2 R1",
            element_index=1,
            parameter="radius_of_curvature_1",
            current_value=100.0,
            min_value=50.0,
            max_value=200.0
        )
        
        # Target: Focal length of 40mm
        # Combined system focal length is roughly 1/(1/50 + 1/50 - 10/2500) = 1/(0.04 - 0.004) = 1/0.036 ≈ 27.7mm
        # Targeting 40mm should drive L2 R1 to a larger (flatter) value or even concave.
        target = OptimizationTarget(
            name="focal_length",
            target_value=40.0,
            weight=1.0,
            target_type="target"
        )
        
        optimizer = LensOptimizer(self.system, [var], [target])
        result = optimizer.optimize(max_iterations=20)
        
        self.assertTrue(result.success)
        self.assertLess(result.final_merit, result.initial_merit)
        
        # Verify optimized system has updated value
        optimized_r1_l2 = result.optimized_system.elements[1].lens.radius_of_curvature_1
        self.assertNotEqual(optimized_r1_l2, 100.0)
        print(f"Optimized L2 R1: {optimized_r1_l2:.2f}")

    def test_optimize_air_gap(self):
        """Test optimizing the air gap between elements."""
        # Variable: Air gap 0 (between L1 and L2)
        var = OptimizationVariable(
            name="Gap 1",
            element_index=0,
            parameter="air_gap",
            current_value=10.0,
            min_value=1.0,
            max_value=50.0
        )
        
        # Target: System focal length of 30mm
        target = OptimizationTarget(
            name="focal_length",
            target_value=30.0,
            weight=1.0,
            target_type="target"
        )
        
        optimizer = LensOptimizer(self.system, [var], [target])
        result = optimizer.optimize(max_iterations=20)
        
        self.assertTrue(result.success)
        # Verify air gap was updated
        optimized_gap = result.optimized_system.air_gaps[0].thickness
        self.assertNotEqual(optimized_gap, 10.0)
        print(f"Optimized Air Gap: {optimized_gap:.2f}")

if __name__ == '__main__':
    unittest.main()
