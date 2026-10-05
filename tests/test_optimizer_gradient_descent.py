#!/usr/bin/env python3
"""
Gradient descent must reject steps that make the merit worse.

optimize_gradient_descent accepted every step unconditionally:

    new_values = [val - learning_rate * grad ...]
    new_merit = self._evaluate_design(new_values)
    improvement = initial_merit - new_merit      # shadowed, never used
    if abs(new_merit - merit_history[-1]) < tolerance:
        break
    current_values = new_values                  # accepted regardless

On a merit carrying large geometry penalties the trajectory diverges.
Verified on a design starting at 0.2 mm thickness (merit ~2e8):

    before: merit 2.00e+08 -> 3.06e+30, improvement -1.5e+27 %
    after:  merit 2.00e+08 -> 2.00e+08, improvement      0.00 %

Also removed: a duplicated `last_iteration = iteration`, and a convergence
test reading merit_history[-1] rather than the merit of the design actually
being iterated on.
"""

import unittest

from src.lens import Lens
from src.optical_system import OpticalSystem
from src.optimizer import (
    LensOptimizer,
    OptimizationTarget,
    OptimizationVariable,
)


def _system(thickness=5.0):
    system = OpticalSystem(name="T")
    system.add_lens(
        Lens(
            name="L",
            radius_of_curvature_1=50.0,
            radius_of_curvature_2=-50.0,
            thickness=thickness,
            diameter=25.0,
            refractive_index=1.5,
        )
    )
    return system


def _radius_run(learning_rate=5.0, max_iterations=60, tolerance=1e-9):
    system = _system()
    variables = [
        OptimizationVariable(
            name="r1",
            element_index=0,
            parameter="radius_of_curvature_1",
            current_value=50.0,
            min_value=40.0,
            max_value=60.0,
        )
    ]
    targets = [OptimizationTarget("rms_spot_radius", 0, weight=1.0, target_type="minimize")]
    return LensOptimizer(system, variables, targets).optimize_gradient_descent(
        max_iterations=max_iterations,
        learning_rate=learning_rate,
        tolerance=tolerance,
    )


def _penalised_run(max_iterations=40, learning_rate=1.0):
    """Starting point whose merit is dominated by a geometry penalty."""
    system = _system(thickness=0.2)
    variables = [
        OptimizationVariable(
            name="t",
            element_index=0,
            parameter="thickness",
            current_value=0.2,
            min_value=0.5,
            max_value=10.0,
        )
    ]
    targets = [OptimizationTarget("rms_spot_radius", 0, weight=1.0, target_type="minimize")]
    return LensOptimizer(system, variables, targets).optimize_gradient_descent(
        max_iterations=max_iterations, learning_rate=learning_rate, tolerance=1e-12
    )


class TestMeritNeverIncreases(unittest.TestCase):
    def test_history_is_monotonically_non_increasing(self):
        history = _radius_run().merit_history
        for previous, current in zip(history, history[1:]):
            self.assertLessEqual(current, previous + 1e-12)

    def test_aggressive_learning_rate_still_converges(self):
        """lr=5.0 would previously overshoot on the first step."""
        result = _radius_run(learning_rate=5.0)
        self.assertLessEqual(result.final_merit, result.initial_merit)
        self.assertGreater(result.final_merit, 0.0)

    def test_huge_learning_rate_still_converges(self):
        result = _radius_run(learning_rate=500.0)
        self.assertLessEqual(result.final_merit, result.initial_merit)

    def test_penalised_start_does_not_diverge(self):
        """Regression: merit reached 3e30, reporting -1.5e27 % improvement."""
        result = _penalised_run()
        self.assertLessEqual(result.final_merit, result.initial_merit * (1 + 1e-9))
        self.assertGreaterEqual(result.improvement, 0.0)

    def test_penalised_history_never_exceeds_the_start(self):
        result = _penalised_run()
        self.assertLessEqual(max(result.merit_history), result.initial_merit * (1 + 1e-9))

    def test_improvement_is_never_absurdly_negative(self):
        for runner in (_radius_run, _penalised_run):
            with self.subTest(runner=runner.__name__):
                result = runner()
                self.assertGreaterEqual(result.improvement, -1e-6)


class TestResultConsistency(unittest.TestCase):
    """final_merit must describe the design actually returned."""

    def test_final_merit_matches_the_last_history_entry(self):
        result = _radius_run()
        self.assertAlmostEqual(result.final_merit, result.merit_history[-1], places=12)

    def test_final_merit_matches_on_a_stalled_run(self):
        """The history is only appended for accepted steps."""
        result = _penalised_run()
        self.assertAlmostEqual(result.final_merit, result.merit_history[-1], places=12)

    def test_history_has_one_entry_per_accepted_step(self):
        result = _radius_run()
        self.assertEqual(len(result.merit_history), len(result.variable_history))
        self.assertGreaterEqual(len(result.merit_history), 2)

    def test_iterations_is_at_least_one(self):
        self.assertGreaterEqual(_radius_run().iterations, 1)

    def test_bounds_are_still_reported_not_clamped(self):
        """Bounds stay penalties; validity is reported in the result."""
        result = _radius_run(learning_rate=500.0)
        self.assertIsInstance(result.success, bool)


class TestDeadCodeRemoved(unittest.TestCase):
    def test_no_duplicated_last_iteration_assignment(self):
        import inspect
        import re

        from src.optimizer import LensOptimizer

        source = inspect.getsource(LensOptimizer.optimize_gradient_descent)
        assignments = re.findall(r"^(\s*)last_iteration = iteration$", source, re.M)
        self.assertLessEqual(len(assignments), 1, "duplicated `last_iteration = iteration` is back")

    def test_no_shadowed_improvement_assignment(self):
        """The loop-local `improvement` was overwritten without being read."""
        import inspect

        from src.optimizer import LensOptimizer

        source = inspect.getsource(LensOptimizer.optimize_gradient_descent)
        body = source.split('logger.debug(\n            "Gradient descent:')[0]
        self.assertNotIn("improvement = initial_merit - new_merit", body)

    def test_convergence_uses_the_current_merit_not_the_history(self):
        import inspect

        from src.optimizer import LensOptimizer

        source = inspect.getsource(LensOptimizer.optimize_gradient_descent)
        self.assertNotIn("merit_history[-1] <", source)
        self.assertIn("current_merit", source)


class TestBacktrackingConstants(unittest.TestCase):
    def test_constants_are_sane(self):
        self.assertGreater(LensOptimizer.MAX_BACKTRACKING_STEPS, 1)
        self.assertGreater(LensOptimizer.MIN_LEARNING_RATE, 0.0)

    def test_zero_learning_rate_makes_no_progress_without_error(self):
        result = _radius_run(learning_rate=0.0, max_iterations=5)
        self.assertAlmostEqual(result.final_merit, result.initial_merit, places=9)


if __name__ == "__main__":
    unittest.main()
