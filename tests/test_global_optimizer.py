import unittest
import math
import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

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
            refractive_index=1.5,
        )
        self.system = OpticalSystem()
        self.system.add_lens(self.lens)

        self.variables = [
            OptimizationVariable("R1", 0, "radius_of_curvature_1", 100.0, 50.0, 150.0),
        ]

        # Target: specific focal length
        self.targets = [OptimizationTarget("focal_length", 80.0, weight=1.0, target_type="target")]

    def test_simulated_annealing(self):
        """Test Simulated Annealing convergence"""
        optimizer = GlobalOptimizer(self.system, self.variables, self.targets, seed=42)

        # Run SA
        result = optimizer.optimize_simulated_annealing(
            max_iterations=100, initial_temperature=10.0, cooling_rate=0.8
        )

        self.assertTrue(result.success)
        self.assertLess(result.final_merit, result.initial_merit)

        # Check result
        f = result.optimized_system.get_system_focal_length()
        self.assertAlmostEqual(f, 80.0, delta=1.0)  # SA is stochastic, allow loose delta

    def test_genetic_algorithm_seeded(self):
        """Seeded GA improves merit on the focal-length target"""
        optimizer = GlobalOptimizer(self.system, self.variables, self.targets, seed=123)

        result = optimizer.optimize_genetic(population_size=12, generations=8)

        self.assertTrue(result.success)
        self.assertLessEqual(result.final_merit, result.initial_merit)
        # Optimized radius must stay inside the declared variable bounds
        r1 = result.optimized_system.elements[0].lens.radius_of_curvature_1
        self.assertGreaterEqual(r1, 50.0 - 1e-6)
        self.assertLessEqual(r1, 150.0 + 1e-6)


class TestGeneticNoFiniteMerit(unittest.TestCase):
    """optimize_genetic must survive when nothing beats infinity.

    best_overall_design started as None and was only replaced once some
    design beat inf, so a merit that never did - NaN, or generations=0 -
    left it None and the elitism copy raised
    TypeError: 'NoneType' object is not iterable.
    """

    def setUp(self):
        system = OpticalSystem()
        system.add_lens(
            Lens(
                radius_of_curvature_1=50.0,
                radius_of_curvature_2=-50.0,
                thickness=5.0,
                diameter=20.0,
                refractive_index=1.5,
            )
        )
        self.system = system
        self.variables = [
            OptimizationVariable(
                name="r1",
                element_index=0,
                parameter="radius_of_curvature_1",
                current_value=50.0,
                min_value=40.0,
                max_value=60.0,
            )
        ]
        self.targets = [OptimizationTarget("focal_length", 100.0, weight=1.0, target_type="target")]

    def _optimizer(self):
        return GlobalOptimizer(self.system, self.variables, self.targets)

    def test_zero_generations_does_not_crash(self):
        """Regression: TypeError from the None elite copy."""
        result = self._optimizer().optimize_genetic(generations=0, population_size=6)
        self.assertEqual(result.merit_history, [])

    def test_zero_generations_reports_a_finite_baseline(self):
        """history_merit is empty, so indexing [0] must be avoided too."""
        result = self._optimizer().optimize_genetic(generations=0, population_size=6)
        self.assertTrue(math.isfinite(result.initial_merit))

    def test_nan_merit_does_not_crash(self):
        """A NaN-scored run is a failure, not an exception."""
        optimizer = self._optimizer()
        optimizer.merit_function.evaluate = lambda system: float("nan")
        result = optimizer.optimize_genetic(generations=2, population_size=6)
        self.assertTrue(math.isfinite(result.initial_merit))
        self.assertTrue(math.isfinite(result.final_merit))

    def test_nan_merit_normalises_to_infeasible(self):
        from src.optimizer import INFEASIBLE_MERIT

        optimizer = self._optimizer()
        optimizer.merit_function.evaluate = lambda system: float("nan")
        self.assertEqual(optimizer._evaluate_design([55.0]), INFEASIBLE_MERIT)

    def test_normal_runs_still_improve(self):
        """Guard: the seeding must not stop the search working."""
        result = self._optimizer().optimize_genetic(generations=3, population_size=8)
        self.assertEqual(len(result.merit_history), 3)
        self.assertTrue(math.isfinite(result.final_merit))
        self.assertLessEqual(result.final_merit, result.initial_merit)

    def test_simulated_annealing_unaffected(self):
        result = self._optimizer().optimize_simulated_annealing(max_iterations=20)
        self.assertTrue(math.isfinite(result.final_merit))


if __name__ == "__main__":
    unittest.main()
