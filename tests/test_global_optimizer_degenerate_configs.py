#!/usr/bin/env python3
"""
Degenerate configurations must not raise from the global optimizers.

Three unguarded spots, all reproduced:

    initial_temperature = 0  -> ZeroDivisionError: float division by zero
    max_iterations = 0       -> UnboundLocalError: cannot access local variable
                                 'iteration' where it is not associated with a
                                 value
    population_size < 3      -> ValueError: Sample larger than population
                                 (k=3 is the default tournament size, and the
                                  GUI was one config change away from this)

After the fix all of them run, and the search still reaches the same optimum.
"""

import unittest

from src.global_optimizer import GlobalOptimizer
from src.lens import Lens
from src.optical_system import OpticalSystem
from src.optimizer import OptimizationTarget, OptimizationVariable


def _system():
    system = OpticalSystem(name="T")
    system.add_lens(
        Lens(
            name="L",
            radius_of_curvature_1=50.0,
            radius_of_curvature_2=-50.0,
            thickness=5.0,
            diameter=25.0,
            refractive_index=1.5,
        )
    )
    return system


def _variables():
    return [
        OptimizationVariable(
            name="r1",
            element_index=0,
            parameter="radius_of_curvature_1",
            current_value=50.0,
            min_value=40.0,
            max_value=60.0,
        )
    ]


def _targets():
    return [OptimizationTarget("rms_spot_radius", 0, weight=1.0, target_type="minimize")]


def _sa(**kwargs):
    return GlobalOptimizer(_system(), _variables(), _targets()).optimize_simulated_annealing(
        **kwargs
    )


def _ga(**kwargs):
    return GlobalOptimizer(_system(), _variables(), _targets()).optimize_genetic(**kwargs)


class TestTemperatureGuard(unittest.TestCase):
    """Regression: ZeroDivisionError on the first iteration."""

    def test_zero_initial_temperature_runs(self):
        result = _sa(initial_temperature=0.0, max_iterations=5)
        self.assertGreaterEqual(result.iterations, 1)

    def test_negative_initial_temperature_runs(self):
        result = _sa(initial_temperature=-5.0, max_iterations=5)
        self.assertGreaterEqual(result.iterations, 1)

    def test_tiny_initial_temperature_runs(self):
        self.assertGreaterEqual(_sa(initial_temperature=1e-12, max_iterations=5).iterations, 1)

    def test_normal_temperature_is_unchanged(self):
        result = _sa(initial_temperature=1.0, max_iterations=25, cooling_rate=0.9)
        self.assertLess(result.final_merit, result.initial_merit)


class TestZeroIterationsGuard(unittest.TestCase):
    """Regression: UnboundLocalError on `iteration`."""

    def test_zero_iterations_runs(self):
        result = _sa(max_iterations=0)
        self.assertGreaterEqual(result.iterations, 1)

    def test_zero_iterations_leaves_the_result_well_formed(self):
        """No annealing happens, but the local refinement still runs."""
        result = _sa(max_iterations=0)
        self.assertLessEqual(result.final_merit, result.initial_merit)
        self.assertIsInstance(result.merit_history, list)
        self.assertIsInstance(result.variable_history, list)

    def test_negative_iterations_runs(self):
        self.assertGreaterEqual(_sa(max_iterations=-5).iterations, 1)

    def test_result_is_still_well_formed(self):
        result = _sa(max_iterations=0)
        self.assertIsInstance(result.message, str)
        self.assertIsInstance(result.success, bool)
        self.assertIsNotNone(result.optimized_system)


class TestTournamentSampleGuard(unittest.TestCase):
    """Regression: 'Sample larger than population' for population_size < 3."""

    def test_population_of_two_runs(self):
        result = _ga(population_size=2, generations=2)
        self.assertIsInstance(result.final_merit, float)

    def test_population_of_one_runs(self):
        self.assertIsInstance(_ga(population_size=1, generations=1).final_merit, float)

    def test_tournament_clamps_k(self):
        optimizer = GlobalOptimizer(_system(), _variables(), _targets())
        population = [[50.0], [51.0], [52.0]]
        merits = [3.0, 1.0, 2.0]
        for size in (1, 2, 3, 10):
            with self.subTest(population=len(population), k=size):
                chosen = optimizer._tournament_select(population, merits, k=size)
                self.assertIn(chosen, population)

    def test_tournament_picks_the_best_of_the_sample(self):
        optimizer = GlobalOptimizer(_system(), _variables(), _targets())
        population = [[10.0], [20.0], [30.0]]
        merits = [5.0, 1.0, 3.0]
        # k >= len(population) samples everyone, so the best must win.
        self.assertEqual(optimizer._tournament_select(population, merits, k=99), [20.0])

    def test_tournament_on_empty_population_raises_clearly(self):
        optimizer = GlobalOptimizer(_system(), _variables(), _targets())
        with self.assertRaises(ValueError):
            optimizer._tournament_select([], [])

    def test_normal_population_still_optimises(self):
        result = _ga(population_size=10, generations=3, mutation_rate=0.2)
        self.assertLess(result.final_merit, result.initial_merit)


class TestSearchQualityUnaffected(unittest.TestCase):
    def test_small_population_still_finds_the_optimum(self):
        """The guard must not degrade the search, only stop it crashing."""
        result = _ga(population_size=2, generations=4, mutation_rate=0.3)
        self.assertLess(result.final_merit, result.initial_merit)

    def test_annealing_with_zero_iterations_leaves_variables_alone(self):
        """Consistent with #350: no caller mutation on any path."""
        variables = _variables()
        before = [v.current_value for v in variables]
        GlobalOptimizer(_system(), variables, _targets()).optimize_simulated_annealing(
            max_iterations=0
        )
        self.assertEqual([v.current_value for v in variables], before)


if __name__ == "__main__":
    unittest.main()
