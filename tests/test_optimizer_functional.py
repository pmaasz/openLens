#!/usr/bin/env python3
"""
Comprehensive functional tests for optimization engine
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src'))

from optimizer import (
    OptimizationVariable, OptimizationTarget, MeritFunction,
    LensOptimizer, create_doublet_optimizer, OptimizationResult
)
from optical_system import OpticalSystem, create_doublet
from lens_editor import Lens


class TestOptimizationVariable(unittest.TestCase):
    """Test OptimizationVariable class"""
    
    def test_create_variable(self):
        """Test creating optimization variable"""
        var = OptimizationVariable(
            name="Test Var",
            element_index=0,
            parameter="radius_of_curvature_1",
            current_value=100.0,
            min_value=50.0,
            max_value=200.0
        )
        
        self.assertEqual(var.name, "Test Var")
        self.assertEqual(var.current_value, 100.0)
    
    def test_is_valid(self):
        """Test value validation"""
        var = OptimizationVariable("Test", 0, "radius_of_curvature_1",
                                   100.0, 50.0, 200.0)
        
        self.assertTrue(var.is_valid(100.0))
        self.assertTrue(var.is_valid(50.0))
        self.assertTrue(var.is_valid(200.0))
        self.assertFalse(var.is_valid(49.9))
        self.assertFalse(var.is_valid(200.1))
    
    def test_clamp(self):
        """Test value clamping"""
        var = OptimizationVariable("Test", 0, "radius_of_curvature_1",
                                   100.0, 50.0, 200.0)
        
        self.assertEqual(var.clamp(100.0), 100.0)
        self.assertEqual(var.clamp(49.0), 50.0)
        self.assertEqual(var.clamp(250.0), 200.0)
        self.assertEqual(var.clamp(75.0), 75.0)


class TestOptimizationTarget(unittest.TestCase):
    """Test OptimizationTarget class"""
    
    def test_create_target(self):
        """Test creating optimization target"""
        target = OptimizationTarget(
            name="focal_length",
            target_value=100.0,
            weight=1.0,
            target_type="target"
        )
        
        self.assertEqual(target.name, "focal_length")
        self.assertEqual(target.target_value, 100.0)
        self.assertEqual(target.weight, 1.0)
        self.assertEqual(target.target_type, "target")
    
    def test_target_types(self):
        """Test different target types"""
        minimize = OptimizationTarget("test", 0, 1.0, "minimize")
        maximize = OptimizationTarget("test", 0, 1.0, "maximize")
        target = OptimizationTarget("test", 100, 1.0, "target")
        
        self.assertEqual(minimize.target_type, "minimize")
        self.assertEqual(maximize.target_type, "maximize")
        self.assertEqual(target.target_type, "target")


class TestMeritFunction(unittest.TestCase):
    """Test merit function evaluation"""
    
    def test_evaluate_simple_lens(self):
        """Test merit function on simple lens"""
        lens = Lens(radius_of_curvature_1=100, radius_of_curvature_2=-100,
                   thickness=10, diameter=50)
        system = OpticalSystem()
        system.add_lens(lens)
        
        targets = [
            OptimizationTarget("focal_length", 100.0, 1.0, "target")
        ]
        
        merit_func = MeritFunction(system, targets)
        merit = merit_func.evaluate(system)
        
        self.assertIsNotNone(merit)
        self.assertGreater(merit, 0)
    
    def test_chromatic_aberration_target(self):
        """Test chromatic aberration in merit function"""
        doublet = create_doublet(focal_length=100, diameter=50)
        
        targets = [
            OptimizationTarget("chromatic_aberration", 0.0, 1.0, "minimize")
        ]
        
        merit_func = MeritFunction(doublet, targets)
        merit = merit_func.evaluate(doublet)
        
        self.assertIsNotNone(merit)
        self.assertGreaterEqual(merit, 0)


class TestLensOptimizer(unittest.TestCase):
    """Test LensOptimizer class"""
    
    def test_create_optimizer(self):
        """Test creating optimizer"""
        lens = Lens(radius_of_curvature_1=100, radius_of_curvature_2=-100,
                   thickness=10, diameter=50)
        system = OpticalSystem()
        system.add_lens(lens)
        
        variables = [
            OptimizationVariable("R1", 0, "radius_of_curvature_1",
                               100.0, 50.0, 200.0)
        ]
        
        targets = [
            OptimizationTarget("focal_length", 100.0, 1.0, "target")
        ]
        
        optimizer = LensOptimizer(system, variables, targets)
        
        self.assertIsNotNone(optimizer)
        self.assertEqual(len(optimizer.variables), 1)
        self.assertEqual(len(optimizer.targets), 1)
    
    def test_simplex_optimization_runs(self):
        """Test that simplex optimization runs without errors"""
        lens = Lens(radius_of_curvature_1=100, radius_of_curvature_2=-100,
                   thickness=10, diameter=50)
        system = OpticalSystem()
        system.add_lens(lens)
        
        variables = [
            OptimizationVariable("R1", 0, "radius_of_curvature_1",
                               100.0, 50.0, 200.0)
        ]
        
        targets = [
            OptimizationTarget("focal_length", 100.0, 1.0, "target")
        ]
        
        optimizer = LensOptimizer(system, variables, targets)
        result = optimizer.optimize_simplex(max_iterations=10)
        
        self.assertIsNotNone(result)
        self.assertIsInstance(result, OptimizationResult)
        self.assertTrue(result.success)
        self.assertGreater(result.iterations, 0)
        self.assertLessEqual(result.iterations, 10)
    
    def test_gradient_descent_runs(self):
        """Test that gradient descent runs without errors"""
        lens = Lens(radius_of_curvature_1=100, radius_of_curvature_2=-100,
                   thickness=10, diameter=50)
        system = OpticalSystem()
        system.add_lens(lens)
        
        variables = [
            OptimizationVariable("R1", 0, "radius_of_curvature_1",
                               100.0, 50.0, 200.0)
        ]
        
        targets = [
            OptimizationTarget("focal_length", 100.0, 1.0, "target")
        ]
        
        optimizer = LensOptimizer(system, variables, targets)
        result = optimizer.optimize_gradient_descent(max_iterations=10)
        
        self.assertIsNotNone(result)
        self.assertIsInstance(result, OptimizationResult)
        self.assertTrue(result.success)
    
    def test_optimization_improves_merit(self):
        """Test that optimization reduces merit function"""
        lens = Lens(radius_of_curvature_1=80, radius_of_curvature_2=-120,
                   thickness=10, diameter=50)
        system = OpticalSystem()
        system.add_lens(lens)
        
        variables = [
            OptimizationVariable("R1", 0, "radius_of_curvature_1",
                               80.0, 50.0, 150.0),
            OptimizationVariable("R2", 0, "radius_of_curvature_2",
                               -120.0, -150.0, -50.0)
        ]
        
        targets = [
            OptimizationTarget("focal_length", 100.0, 1.0, "target")
        ]
        
        optimizer = LensOptimizer(system, variables, targets)
        result = optimizer.optimize_simplex(max_iterations=20)
        
        # Merit should improve (decrease)
        self.assertLess(result.final_merit, result.initial_merit)
    
    def test_optimization_result_structure(self):
        """Test optimization result has all expected fields"""
        lens = Lens(radius_of_curvature_1=100, radius_of_curvature_2=-100,
                   thickness=10, diameter=50)
        system = OpticalSystem()
        system.add_lens(lens)
        
        variables = [
            OptimizationVariable("R1", 0, "radius_of_curvature_1",
                               100.0, 50.0, 200.0)
        ]
        
        targets = [
            OptimizationTarget("focal_length", 100.0, 1.0, "target")
        ]
        
        optimizer = LensOptimizer(system, variables, targets)
        result = optimizer.optimize_simplex(max_iterations=5)
        
        self.assertIsNotNone(result.success)
        self.assertIsNotNone(result.iterations)
        self.assertIsNotNone(result.initial_merit)
        self.assertIsNotNone(result.final_merit)
        self.assertIsNotNone(result.improvement)
        self.assertIsNotNone(result.optimized_system)
        self.assertIsNotNone(result.variable_history)
        self.assertIsNotNone(result.merit_history)
        self.assertIsNotNone(result.message)
    
    def test_history_tracking(self):
        """Test that optimization tracks history"""
        lens = Lens(radius_of_curvature_1=100, radius_of_curvature_2=-100,
                   thickness=10, diameter=50)
        system = OpticalSystem()
        system.add_lens(lens)
        
        variables = [
            OptimizationVariable("R1", 0, "radius_of_curvature_1",
                               100.0, 50.0, 200.0)
        ]
        
        targets = [
            OptimizationTarget("focal_length", 100.0, 1.0, "target")
        ]
        
        optimizer = LensOptimizer(system, variables, targets)
        result = optimizer.optimize_simplex(max_iterations=10)
        
        # Should have history entries
        self.assertGreater(len(result.merit_history), 0)
        self.assertGreater(len(result.variable_history), 0)
        
        # History lengths should match
        self.assertEqual(len(result.merit_history), len(result.variable_history))


class TestDoubletOptimizer(unittest.TestCase):
    """Test doublet-specific optimizer"""
    
    def test_create_doublet_optimizer(self):
        """Test creating doublet optimizer"""
        doublet = create_doublet(focal_length=100, diameter=50)
        optimizer = create_doublet_optimizer(doublet, target_focal_length=100.0)
        
        self.assertIsNotNone(optimizer)
        self.assertEqual(len(optimizer.variables), 4)  # 4 radii
        self.assertEqual(len(optimizer.targets), 2)  # chromatic + focal length
    
    def test_doublet_optimizer_variables(self):
        """Test doublet optimizer has correct variables"""
        doublet = create_doublet(focal_length=100, diameter=50)
        optimizer = create_doublet_optimizer(doublet, target_focal_length=100.0)
        
        var_names = [v.name for v in optimizer.variables]
        self.assertIn("R1 Crown", var_names)
        self.assertIn("R2 Crown", var_names)
        self.assertIn("R1 Flint", var_names)
        self.assertIn("R2 Flint", var_names)
    
    def test_doublet_optimizer_targets(self):
        """Test doublet optimizer has correct targets"""
        doublet = create_doublet(focal_length=100, diameter=50)
        optimizer = create_doublet_optimizer(doublet, target_focal_length=100.0)
        
        target_names = [t.name for t in optimizer.targets]
        self.assertIn("chromatic_aberration", target_names)
        self.assertIn("focal_length", target_names)
    
    def test_doublet_optimization_runs(self):
        """Test that doublet optimization completes"""
        doublet = create_doublet(focal_length=100, diameter=50)
        optimizer = create_doublet_optimizer(doublet, target_focal_length=100.0)
        
        result = optimizer.optimize_simplex(max_iterations=10)
        
        self.assertTrue(result.success)
        self.assertIsNotNone(result.optimized_system)
        self.assertEqual(len(result.optimized_system.elements), 2)


class TestOptimizationConvergence(unittest.TestCase):
    """Test optimization convergence behavior"""
    
    def test_convergence_tolerance(self):
        """Test that optimization stops at tolerance"""
        lens = Lens(radius_of_curvature_1=100, radius_of_curvature_2=-100,
                   thickness=10, diameter=50)
        system = OpticalSystem()
        system.add_lens(lens)
        
        variables = [
            OptimizationVariable("R1", 0, "radius_of_curvature_1",
                               100.0, 95.0, 105.0)  # Narrow range
        ]
        
        targets = [
            OptimizationTarget("focal_length", 100.0, 1.0, "target")
        ]
        
        optimizer = LensOptimizer(system, variables, targets)
        result = optimizer.optimize_simplex(max_iterations=100, tolerance=1e-3)
        
        # Should converge before max iterations with loose tolerance
        self.assertLess(result.iterations, 100)
    
    def test_max_iterations_limit(self):
        """Test that optimization respects max iterations"""
        lens = Lens(radius_of_curvature_1=100, radius_of_curvature_2=-100,
                   thickness=10, diameter=50)
        system = OpticalSystem()
        system.add_lens(lens)
        
        variables = [
            OptimizationVariable("R1", 0, "radius_of_curvature_1",
                               100.0, 50.0, 200.0)
        ]
        
        targets = [
            OptimizationTarget("focal_length", 100.0, 1.0, "target")
        ]
        
        max_iter = 5
        optimizer = LensOptimizer(system, variables, targets)
        result = optimizer.optimize_simplex(max_iterations=max_iter, tolerance=1e-10)
        
        # Should not exceed max iterations
        self.assertLessEqual(result.iterations, max_iter)


def run_tests():
    """Run all tests"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    suite.addTests(loader.loadTestsFromTestCase(TestOptimizationVariable))
    suite.addTests(loader.loadTestsFromTestCase(TestOptimizationTarget))
    suite.addTests(loader.loadTestsFromTestCase(TestMeritFunction))
    suite.addTests(loader.loadTestsFromTestCase(TestLensOptimizer))
    suite.addTests(loader.loadTestsFromTestCase(TestDoubletOptimizer))
    suite.addTests(loader.loadTestsFromTestCase(TestOptimizationConvergence))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(run_tests())
