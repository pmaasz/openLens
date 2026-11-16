#!/usr/bin/env python3
"""Damped least-squares optimizer: convergence, bounds, penalties, GUI."""

import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication

    PYSIDE_AVAILABLE = True
except ImportError:  # pragma: no cover - environment guard
    PYSIDE_AVAILABLE = False

from openlens.lens import Lens
from openlens.optical_system import OpticalSystem, create_doublet
from openlens.optimizer import (
    LensOptimizer,
    OptimizationTarget,
    OptimizationVariable,
    create_doublet_optimizer,
)

TARGET_F = 80.0
DOUBLET_START = [70.0, -70.0, -120.0]


def _single_variable_optimizer(target_f=TARGET_F):
    """One R2 variable on a thin lens; the optimum for 80 mm is R2 = -66.67."""
    system = OpticalSystem(name="conv")
    system.add_lens(
        Lens(
            radius_of_curvature_1=100.0,
            radius_of_curvature_2=-100.0,
            thickness=5.0,
            diameter=25.0,
            refractive_index=1.5,
        )
    )
    variables = [OptimizationVariable("R2", 0, "radius_of_curvature_2", -100.0, -150.0, -50.0)]
    targets = [OptimizationTarget("focal_length", target_f, weight=1.0, target_type="target")]
    return LensOptimizer(system, variables, targets)


def _doublet_optimizer(start=DOUBLET_START):
    """A feasible doublet moved away from its design point."""
    optimizer = create_doublet_optimizer(create_doublet(diameter=25.0))
    for variable, value in zip(optimizer.variables, start):
        variable.current_value = value
    return optimizer


def _assert_merit_never_increases(test_case, result):
    for before, after in zip(result.merit_history, result.merit_history[1:]):
        test_case.assertLessEqual(after, before)


class TestDampedLeastSquaresConvergence(unittest.TestCase):
    def test_single_variable_reaches_the_target(self):
        result = _single_variable_optimizer().optimize_damped_least_squares(max_iterations=100)

        self.assertTrue(result.success)
        self.assertLessEqual(result.final_merit, 1e-6 * result.initial_merit)
        self.assertAlmostEqual(
            result.optimized_system.get_system_focal_length(), TARGET_F, delta=0.01
        )

    def test_perturbed_doublet_reduces_the_merit(self):
        result = _doublet_optimizer().optimize_damped_least_squares(max_iterations=20)

        self.assertTrue(result.success)
        self.assertLess(result.final_merit, 0.01 * result.initial_merit)
        self.assertGreater(result.improvement, 99.0)

    def test_matches_simplex_within_the_same_iteration_budget(self):
        dls = _doublet_optimizer().optimize_damped_least_squares(max_iterations=20)
        simplex = _doublet_optimizer().optimize_simplex(max_iterations=20)

        self.assertLessEqual(dls.final_merit, simplex.final_merit)

    def test_merit_history_and_callback_never_go_backwards(self):
        seen = []
        result = _doublet_optimizer().optimize_damped_least_squares(
            max_iterations=20, callback=lambda iteration, merit, values: seen.append(merit)
        )

        _assert_merit_never_increases(self, result)
        self.assertEqual(seen, result.merit_history[: len(seen)])
        self.assertEqual(result.iterations, len(seen))

    def test_result_reports_iterations_and_evaluations(self):
        result = _doublet_optimizer().optimize_damped_least_squares(max_iterations=20)

        self.assertGreater(result.iterations, 0)
        # One residual pass and one finite-difference pass per variable, plus
        # the initial merit, means evaluations always exceed iterations.
        self.assertGreater(result.evaluations, result.iterations)


class TestDampedLeastSquaresConstraints(unittest.TestCase):
    def test_steps_stay_inside_the_variable_bounds(self):
        # The optimum for 300 mm sits past the R2 = -50 bound, so the solver
        # must stop on the box rather than step through it.
        optimizer = _single_variable_optimizer(target_f=300.0)
        result = optimizer.optimize_damped_least_squares(max_iterations=100)

        self.assertLessEqual(result.final_merit, result.initial_merit)
        for history in result.variable_history:
            self.assertTrue(-150.0 <= history["R2"] <= -50.0, history)
        for value in result.best_values:
            self.assertTrue(-150.0 <= value <= -50.0, value)

    def test_a_variable_parked_on_a_bound_still_moves_inward(self):
        # R2 = -50 is the upper bound; the 80 mm optimum is at -66.67.
        optimizer = _single_variable_optimizer()
        optimizer.variables[0].current_value = -50.0
        result = optimizer.optimize_damped_least_squares(max_iterations=50)

        self.assertTrue(result.success)
        self.assertLess(result.best_values[0], -55.0)
        self.assertAlmostEqual(
            result.optimized_system.get_system_focal_length(), TARGET_F, delta=0.1
        )

    def test_a_failed_step_restores_the_previous_design(self):
        class FlatMerit(LensOptimizer):
            """Every design scores the same, so no step is ever accepted."""

            def _evaluate_design(self, values):
                return 1.0

        optimizer = FlatMerit(
            _single_variable_optimizer().system,
            [OptimizationVariable("R2", 0, "radius_of_curvature_2", -100.0, -150.0, -50.0)],
            [OptimizationTarget("focal_length", TARGET_F, weight=1.0, target_type="target")],
        )
        result = optimizer.optimize_damped_least_squares(max_iterations=10)

        self.assertEqual(result.initial_merit, result.final_merit)
        self.assertEqual(result.best_values, [-100.0])
        self.assertEqual(len(result.variable_history), 1)
        self.assertEqual(len(result.merit_history), 1)
        self.assertEqual(result.optimized_system.elements[0].lens.radius_of_curvature_2, -100.0)

    def test_a_design_that_cannot_be_made_is_reported_as_failure(self):
        system = OpticalSystem(name="thin")
        system.add_lens(
            Lens(
                radius_of_curvature_1=50.0,
                radius_of_curvature_2=-50.0,
                thickness=0.1,
                diameter=50.0,
                refractive_index=1.5,
            )
        )
        optimizer = LensOptimizer(
            system,
            [OptimizationVariable("R2", 0, "radius_of_curvature_2", -50.0, -500.0, -20.0)],
            [OptimizationTarget("focal_length", TARGET_F, weight=1.0, target_type="target")],
        )
        result = optimizer.optimize_damped_least_squares(max_iterations=10)

        self.assertFalse(result.success)
        self.assertIn("physical constraint", result.message)
        self.assertLessEqual(result.final_merit, result.initial_merit)
        self.assertTrue(
            optimizer.merit_function.has_hard_violation(result.optimized_system),
            "this start cannot be rescued by R2 alone",
        )


class TestDampedLeastSquaresApi(unittest.TestCase):
    def test_optimize_dispatches_to_damped_least_squares(self):
        result = _single_variable_optimizer().optimize(max_iterations=100, algorithm="dls")

        self.assertTrue(result.success)
        self.assertIn("damped least-squares", result.message)

    def test_optimize_accepts_the_long_algorithm_name(self):
        result = _single_variable_optimizer().optimize(
            max_iterations=100, algorithm="damped_least_squares"
        )

        self.assertTrue(result.success)

    def test_an_unknown_algorithm_raises(self):
        with self.assertRaises(ValueError):
            _single_variable_optimizer().optimize(algorithm="annealing")

    def test_zero_variables_raises(self):
        optimizer = LensOptimizer(OpticalSystem(), [], [])
        with self.assertRaises(ValueError):
            optimizer.optimize_damped_least_squares()

    def test_start_with_the_wrong_length_raises(self):
        with self.assertRaises(ValueError):
            _single_variable_optimizer().optimize_damped_least_squares(start=[-100.0, -100.0])


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 not available")
class TestDampedLeastSquaresGui(unittest.TestCase):
    def setUp(self):
        from openlens.gui.tabs.optimization_tab import OptimizationTab

        self.app = QApplication.instance() or QApplication(sys.argv)
        self.tab = OptimizationTab()

    def tearDown(self):
        self.tab.deleteLater()

    def test_the_algorithm_can_be_selected(self):
        algorithms = [
            self.tab._opt_algorithm.itemText(i) for i in range(self.tab._opt_algorithm.count())
        ]

        self.assertIn("Local (Damped Least Squares)", algorithms)

    def test_the_result_reports_iterations_and_evaluations(self):
        optimizer = _single_variable_optimizer()
        result = optimizer.optimize_damped_least_squares(max_iterations=100)

        self.tab._on_optimization_finished(result, optimizer.variables)
        text = self.tab._opt_results_text.toPlainText()

        self.assertIn("Iterations:", text)
        self.assertIn("Evaluations:", text)


if __name__ == "__main__":
    unittest.main()
