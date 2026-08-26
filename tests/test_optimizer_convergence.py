#!/usr/bin/env python3
"""
Convergence contracts for every optimizer algorithm.

Shared problem (well-posed, single variable):
    Lens: R1 = 100 fixed, thickness 5, n = 1.5
    Variable: R2 in [-150, -50], initial -100  ->  f_initial = 100.84 mm
    Target : focal_length = 80 mm              ->  R2*      = -65.556
    Initial quadratic merit                    = (100.84 - 80)^2 = 434.3

Every algorithm must satisfy BOTH:
    1. final_merit <= CONVERGENCE_RATIO * initial_merit   (this module)
    2. the physical endpoint: |f_final - 80| <= F_TOL_MM (derived from
       the merit definition: merit = (f - target)^2 * weight)
"""

import math
import unittest

from src.lens import Lens
from src.optical_system import OpticalSystem
from src.optimizer import (
    LensOptimizer, OptimizationTarget, OptimizationVariable,
)
from src.desensitization import DesensitizationOptimizer
from src.global_optimizer import GlobalOptimizer
from src.tolerancing import ToleranceOperand, ToleranceType

TARGET_F = 80.0
CONVERGENCE_RATIO = 0.5          # required improvement factor
F_TOL_MM = 1.5                   # |f_final - 80| budget after convergence
INITIAL_F = 100.84033613445378   # measured for the starting design


def _make_system(r2=-100.0):
    system = OpticalSystem(name="conv")
    system.add_lens(Lens(radius_of_curvature_1=100.0,
                         radius_of_curvature_2=r2,
                         thickness=5.0,
                         diameter=25.0,
                         refractive_index=1.5))
    return system


def _make_optimizer(system, optimizer_cls=LensOptimizer, **kwargs):
    variables = [OptimizationVariable("R2", 0, "radius_of_curvature_2",
                                      -100.0, -150.0, -50.0)]
    targets = [OptimizationTarget("focal_length", TARGET_F,
                                  weight=1.0, target_type="target")]
    return optimizer_cls(system, variables, targets, **kwargs)


class TestOptimizerConvergence(unittest.TestCase):
    """merit_after <= 0.5 * merit_before for every algorithm"""

    def _assert_converged(self, result):
        """Shared contract: ratio + physical endpoint"""
        initial_f = INITIAL_F
        initial_merit = (initial_f - TARGET_F) ** 2
        self.assertTrue(result.success)
        self.assertLessEqual(result.final_merit,
                             CONVERGENCE_RATIO * initial_merit,
                             "insufficient merit reduction")
        f_final = result.optimized_system.get_system_focal_length()
        self.assertAlmostEqual(f_final, TARGET_F, delta=F_TOL_MM,
                               msg="physical endpoint missed")

    def test_simplex_converges(self):
        """Deterministic Nelder-Mead via the high-level optimize() wrapper"""
        system = _make_system()
        optimizer = _make_optimizer(system)
        result = optimizer.optimize(max_iterations=200)
        self._assert_converged(result)

    def test_gradient_descent_converges(self):
        """Numerical-gradient descent (deterministic)"""
        system = _make_system()
        optimizer = _make_optimizer(system)
        result = optimizer.optimize_gradient_descent(
            max_iterations=300, learning_rate=0.05)
        self._assert_converged(result)

    def test_simulated_annealing_converges_seeded(self):
        """Seeded SA (random.seed(42)) meets the same contract"""
        system = _make_system()
        optimizer = _make_optimizer(system, GlobalOptimizer, seed=42)
        result = optimizer.optimize_simulated_annealing(
            max_iterations=400,
            initial_temperature=50.0,
            cooling_rate=0.9)
        self._assert_converged(result)

    def test_genetic_algorithm_converges_seeded(self):
        """Seeded GA (random.seed(123)) meets the same contract"""
        system = _make_system()
        optimizer = _make_optimizer(system, GlobalOptimizer, seed=123)
        result = optimizer.optimize_genetic(population_size=20,
                                            generations=25)
        self._assert_converged(result)

    def test_desensitization_converges_on_robust_merit(self):
        """Robust optimizer reduces its own (sensitivity-inclusive) merit.

        Ratio is looser because the robust objective also penalizes the
        toleranced geometry; endpoint still holds.
        """
        tolerances = [
            ToleranceOperand(element_index=0,
                             param_type=ToleranceType.RADIUS_1,
                             min_val=-0.5, max_val=0.5),
        ]
        system = _make_system()
        variables = [OptimizationVariable("R2", 0, "radius_of_curvature_2",
                                          -100.0, -150.0, -50.0)]
        targets = [OptimizationTarget("focal_length", TARGET_F,
                                      weight=1.0, target_type="target")]
        optimizer = DesensitizationOptimizer(system, variables, targets)
        result = optimizer.optimize_robust(tolerances=tolerances,
                                           max_iterations=30)

        initial_merit = (INITIAL_F - TARGET_F) ** 2
        self.assertTrue(result.success)
        self.assertLessEqual(result.final_merit,
                             0.8 * max(initial_merit, 1.0))
        f_final = result.optimized_system.get_system_focal_length()
        self.assertAlmostEqual(f_final, TARGET_F, delta=2 * F_TOL_MM)


if __name__ == "__main__":
    unittest.main()
