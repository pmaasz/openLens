#!/usr/bin/env python3
"""
Desensitization module: RobustMeritFunction penalties and a smoke run
of DesensitizationOptimizer.optimize_robust.
"""

import unittest

from src.lens import Lens
from src.optical_system import OpticalSystem
from src.optimizer import OptimizationTarget, OptimizationVariable
from src.desensitization import DesensitizationOptimizer, RobustMeritFunction
from src.tolerancing import ToleranceOperand, ToleranceType


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
        self.assertGreaterEqual(
            weighted.evaluate(_make_system()), nominal.evaluate(_make_system())
        )


class TestDesensitizationOptimizer(unittest.TestCase):
    """optimize_robust end-to-end smoke"""

    def test_optimize_robust_returns_result_and_keeps_geometry_valid(self):
        variables = [
            OptimizationVariable("R1", 0, "radius_of_curvature_1", 100.0, 80.0, 120.0)
        ]
        targets = [OptimizationTarget("focal_length", 100.0, target_type="target")]
        optimizer = DesensitizationOptimizer(_make_system(), variables, targets)
        result = optimizer.optimize_robust(
            tolerances=_make_tolerances(), max_iterations=10
        )

        self.assertTrue(result.success)
        self.assertTrue(result.final_merit >= 0.0)
        r1 = result.optimized_system.elements[0].lens.radius_of_curvature_1
        self.assertGreaterEqual(r1, 79.999)
        self.assertLessEqual(r1, 120.001)


if __name__ == "__main__":
    unittest.main()
