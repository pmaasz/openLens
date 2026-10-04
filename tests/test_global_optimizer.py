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


class TestOptimizerResultIntegrity(unittest.TestCase):
    """success, iterations and improvement must mean the same everywhere.

    Both global paths hardcoded success=True and reported initial_merit as
    merit_history[0] - the best of generation 0, after up to 50 random
    mutations, not the starting design - so improvement was measured against
    a fabricated baseline. The GA also reported generations * population_size
    evaluations as "iterations".
    """

    @staticmethod
    def _system():
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
        return system

    def _variables(self):
        # Fresh objects per call: the global paths assign
        # variables[i].current_value in place, so a shared list would let one
        # run move the next run's starting point.
        return [
            OptimizationVariable(
                name="th",
                element_index=0,
                parameter="thickness",
                current_value=5.0,
                min_value=1.0,
                max_value=9.0,
                step_size=0.5,
            )
        ]

    def _targets(self):
        return [OptimizationTarget("focal_length", 95.0, weight=1.0, target_type="target")]

    def _optimizer(self, system=None):
        # A fresh system per run too: merit evaluation touches the system's own
        # lenses (wavelength-dependent refractive indices), so reusing one
        # instance across algorithms would make the baseline drift.
        return GlobalOptimizer(
            system if system is not None else self._system(),
            self._variables(),
            self._targets(),
        )

    def _runs(self):
        return {
            "simplex": lambda o: o.optimize_simplex(max_iterations=40),
            "annealing": lambda o: o.optimize_simulated_annealing(max_iterations=40),
            "genetic": lambda o: o.optimize_genetic(generations=4, population_size=10),
        }

    def test_all_algorithms_report_the_real_starting_merit(self):
        self.assertGreater(self._optimizer()._evaluate_design([5.0]), 0.0)
        for name, run in self._runs().items():
            with self.subTest(algorithm=name):
                start = self._optimizer()._evaluate_design([5.0])
                result = run(self._optimizer())
                self.assertAlmostEqual(result.initial_merit, start, places=6)

    def test_genetic_iterations_count_generations_not_evaluations(self):
        """Was generations * population_size + local steps (4*10 + n)."""
        result = self._optimizer().optimize_genetic(generations=4, population_size=10)
        self.assertLess(result.iterations, 40)

    def test_out_of_bounds_design_never_reports_success(self):
        """The global paths used to hardcode success=True regardless."""
        for name, run in self._runs().items():
            with self.subTest(algorithm=name):
                result = run(self._optimizer())
                in_bounds = all(
                    var.is_valid(v) for var, v in zip(self._variables(), result.best_values)
                )
                if not in_bounds:
                    self.assertFalse(result.success)
                    self.assertIn("bounds", result.message)

    def test_every_algorithm_reports_the_settled_design(self):
        for name, run in self._runs().items():
            with self.subTest(algorithm=name):
                result = run(self._optimizer())
                self.assertEqual(len(result.best_values), len(self._variables()))

    def test_gradient_descent_result_has_best_values_field(self):
        from src.optimizer import LensOptimizer

        result = LensOptimizer(
            self._system(), self._variables(), self._targets()
        ).optimize_gradient_descent(max_iterations=5)
        self.assertTrue(hasattr(result, "best_values"))


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
