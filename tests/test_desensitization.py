#!/usr/bin/env python3
"""
Desensitization module: RobustMeritFunction penalties and a smoke run
of DesensitizationOptimizer.optimize_robust.
"""

import unittest

from openlens.lens import Lens
from openlens.optical_system import OpticalSystem
from openlens.optimizer import OptimizationTarget, OptimizationVariable
from openlens.desensitization import DesensitizationOptimizer, RobustMeritFunction
from openlens.tolerancing import ToleranceOperand, ToleranceType


def _make_system(r2=-100.0):
    system = OpticalSystem(name="desense")
    system.add_lens(
        Lens(
            radius_of_curvature_1=100.0,
            radius_of_curvature_2=r2,
            thickness=5.0,
            diameter=25.0,
            refractive_index=1.5,
        )
    )
    return system


def _make_tolerances():
    return [
        ToleranceOperand(
            element_index=0,
            param_type=ToleranceType.RADIUS_1,
            min_val=-0.5,
            max_val=0.5,
        ),
        ToleranceOperand(
            element_index=0,
            param_type=ToleranceType.THICKNESS,
            min_val=-0.1,
            max_val=0.1,
        ),
    ]


class TestRobustMeritFunction(unittest.TestCase):
    """Merit = nominal merit + sensitivity penalty"""

    def setUp(self):
        self.targets = [OptimizationTarget("focal_length", 100.0, target_type="target")]
        self.tolerances = _make_tolerances()

    def test_evaluate_returns_finite_positive_merit(self):
        rmf = RobustMeritFunction(_make_system(), self.targets, self.tolerances)
        merit = rmf.evaluate(_make_system())
        self.assertGreater(merit, 0.0)
        self.assertTrue(merit == merit)  # not NaN

    def test_sensitivity_weight_inflates_merit(self):
        """Higher sensitivity weight never lowers the robust merit"""
        nominal = RobustMeritFunction(
            _make_system(), self.targets, self.tolerances, sensitivity_weight=0.0
        )
        weighted = RobustMeritFunction(
            _make_system(), self.targets, self.tolerances, sensitivity_weight=5.0
        )
        self.assertGreaterEqual(weighted.evaluate(_make_system()), nominal.evaluate(_make_system()))


class TestRobustMeritDoesNotMutateTheSystem(unittest.TestCase):
    """Every perturbation is undone, including the model-glass switch (#772)."""

    def _custom_system(self):
        system = OpticalSystem(name="custom")
        system.add_lens(
            Lens(
                name="Fixed index",
                radius_of_curvature_1=50.0,
                radius_of_curvature_2=-50.0,
                thickness=5.0,
                diameter=20.0,
                refractive_index=1.6,
                material="Custom",
            )
        )
        return system

    def test_evaluate_leaves_a_fixed_index_lens_unchanged(self):
        system = self._custom_system()
        lens = system.elements[0].lens
        merit = RobustMeritFunction(
            system,
            [OptimizationTarget("focal_length", 50.0)],
            [ToleranceOperand(0, ToleranceType.REFRACTIVE_INDEX, -0.001, 0.001)],
        )

        merit.evaluate(system)

        self.assertFalse(lens.model_glass_mode)
        self.assertEqual(lens.refractive_index, 1.6)
        self.assertEqual(lens.model_vd, 64.17)

    def test_merit_is_independent_of_the_tolerance_order(self):
        def build():
            system = OpticalSystem(name="Chromatic")
            system.add_lens(
                Lens(
                    name="L1",
                    radius_of_curvature_1=60.0,
                    radius_of_curvature_2=-60.0,
                    thickness=5.0,
                    diameter=20.0,
                    refractive_index=1.6,
                    material="Custom",
                )
            )
            system.add_lens(
                Lens(
                    name="L2",
                    radius_of_curvature_1=80.0,
                    radius_of_curvature_2=-80.0,
                    thickness=4.0,
                    diameter=20.0,
                    refractive_index=1.55,
                    material="Custom",
                ),
                air_gap_before=5.0,
            )
            return system

        tolerances = [
            ToleranceOperand(0, ToleranceType.REFRACTIVE_INDEX, -0.01, 0.01),
            ToleranceOperand(0, ToleranceType.THICKNESS, -0.05, 0.05),
        ]
        target = [OptimizationTarget("chromatic_aberration", 0.0)]

        system = build()
        forward = RobustMeritFunction(system, target, tolerances).evaluate(system)
        system = build()
        reverse = RobustMeritFunction(system, target, list(reversed(tolerances))).evaluate(system)

        self.assertAlmostEqual(forward, reverse, places=12)


class TestDesensitizationOptimizer(unittest.TestCase):
    """optimize_robust end-to-end smoke"""

    def test_optimize_robust_returns_result_and_keeps_geometry_valid(self):
        variables = [OptimizationVariable("R1", 0, "radius_of_curvature_1", 100.0, 80.0, 120.0)]
        targets = [OptimizationTarget("focal_length", 100.0, target_type="target")]
        optimizer = DesensitizationOptimizer(_make_system(), variables, targets)
        result = optimizer.optimize_robust(tolerances=_make_tolerances(), max_iterations=10)

        self.assertTrue(result.success)
        self.assertTrue(result.final_merit >= 0.0)
        r1 = result.optimized_system.elements[0].lens.radius_of_curvature_1
        self.assertGreaterEqual(r1, 79.999)
        self.assertLessEqual(r1, 120.001)


class TestRobustRunState(unittest.TestCase):
    """Each robust run must be independent of the one before it."""

    def setUp(self):
        self.system = OpticalSystem(name="desense")
        self.system.add_lens(
            Lens(
                radius_of_curvature_1=70.0,
                radius_of_curvature_2=-100.0,
                thickness=5.0,
                diameter=25.0,
                refractive_index=1.5168,
            )
        )
        self.variables = [
            OptimizationVariable("R1", 0, "radius_of_curvature_1", 70.0, 60.0, 200.0, 5.0)
        ]
        self.targets = [OptimizationTarget("focal_length", 100.0, target_type="target")]
        self.tolerances = [
            ToleranceOperand(0, ToleranceType.RADIUS_1, -0.5, 0.5),
            ToleranceOperand(0, ToleranceType.THICKNESS, -0.1, 0.1),
        ]

    def _optimizer(self):
        return DesensitizationOptimizer(self.system, self.variables, self.targets)

    def test_a_second_run_does_not_reuse_the_first_ones_merit(self):
        """The merit cache is keyed by the design, not by the merit function"""
        optimizer = self._optimizer()
        first = optimizer.optimize_robust(
            self.tolerances, sensitivity_weight=0.0, max_iterations=15
        )
        second = optimizer.optimize_robust(
            self.tolerances, sensitivity_weight=200.0, max_iterations=15
        )

        self.assertNotEqual(
            second.final_merit,
            first.final_merit,
            msg="the second run reused the first run's cached merit",
        )

    def test_a_second_run_matches_a_fresh_optimizer(self):
        """The result must not depend on what the instance did before"""
        reused = self._optimizer()
        reused.optimize_robust(self.tolerances, sensitivity_weight=0.0, max_iterations=15)
        after = reused.optimize_robust(self.tolerances, sensitivity_weight=200.0, max_iterations=15)

        fresh = self._optimizer()
        reference = fresh.optimize_robust(
            self.tolerances, sensitivity_weight=200.0, max_iterations=15
        )

        self.assertAlmostEqual(after.final_merit, reference.final_merit, places=9)
        self.assertAlmostEqual(
            after.best_values[0] if after.best_values else 0.0,
            reference.best_values[0] if reference.best_values else 0.0,
            places=9,
        )

    def test_a_cancelled_run_restores_the_merit_function(self):
        """A cancelled run must not leave the robust merit installed"""
        optimizer = self._optimizer()
        original = optimizer.merit_function

        class Cancelled(Exception):
            pass

        def cancel(iteration, merit, values):
            if iteration == 2:
                raise Cancelled("user pressed Stop")

        with self.assertRaises(Cancelled):
            optimizer.optimize_robust(self.tolerances, max_iterations=10, callback=cancel)

        self.assertIs(optimizer.merit_function, original)
        self.assertNotIsInstance(optimizer.merit_function, RobustMeritFunction)


if __name__ == "__main__":
    unittest.main()
