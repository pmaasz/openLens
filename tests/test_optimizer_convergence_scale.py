#!/usr/bin/env python3
"""
Simplex convergence must be scale-blind, and an empty variable list rejected.

Two defects:

1. `if merit_range < tolerance` with tolerance=1e-6 absolute. Geometry
   penalties reach 1e8, where the spacing between adjacent floats is already
   ~4e-8 - so an absolute 1e-6 spread is below the representation floor and the
   test can never fire while the merit is large. The test is now relative to
   the merit's own magnitude, with an absolute floor so a merit near zero still
   has a usable threshold.

   Measured on a design trapped in the penalty region (same result either way):
       before: 21 iterations
       after:   7 iterations

2. With len(self.variables) == 0 the simplex has one vertex, merit_range is
   identically 0, and the loop broke on iteration 1 having evaluated and
   changed nothing - reported as success:

       GlobalOptimizer(sys, [], [target]).optimize()
       -> success=True, "Converged after 1 iterations"

   That now raises ValueError up front.
"""

import unittest

from src.global_optimizer import GlobalOptimizer
from src.lens import Lens
from src.optical_system import OpticalSystem
from src.optimizer import LensOptimizer, OptimizationTarget, OptimizationVariable


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


def _thickness_variable(current, low, high):
    return [
        OptimizationVariable(
            name="t",
            element_index=0,
            parameter="thickness",
            current_value=current,
            min_value=low,
            max_value=high,
        )
    ]


def _targets():
    return [OptimizationTarget("rms_spot_radius", 0, weight=1.0, target_type="minimize")]


class TestConvergenceIsScaleBlind(unittest.TestCase):
    def test_order_one_merits_keep_the_old_semantics(self):
        """A spread of 1e-9 on merits near 1 was converged before, and still is."""
        self.assertTrue(LensOptimizer._merit_range_converged([0.9, 0.9], 1e-9, 1e-6))

    def test_a_real_spread_on_order_one_merits_is_not_converged(self):
        self.assertFalse(LensOptimizer._merit_range_converged([0.9, 0.92], 0.02, 1e-6))

    def test_large_merits_get_a_scaled_threshold(self):
        """The regression: 1e-6 absolute is below float resolution at 1e8."""
        self.assertTrue(LensOptimizer._merit_range_converged([2e8, 2e8], 50.0, 1e-6))

    def test_large_merits_still_reject_a_real_spread(self):
        self.assertFalse(LensOptimizer._merit_range_converged([2e8, 2e8], 5e5, 1e-6))

    def test_zero_merit_uses_the_absolute_floor(self):
        """Scale would underflow; the floor keeps the test usable."""
        self.assertTrue(LensOptimizer._merit_range_converged([0.0, 0.0], 0.0, 1e-6))
        self.assertFalse(LensOptimizer._merit_range_converged([0.0, 0.0], 1.0, 1e-6))

    def test_negative_merits_use_absolute_magnitude(self):
        self.assertTrue(LensOptimizer._merit_range_converged([-2e8, -2e8], 10.0, 1e-6))

    def test_penalised_run_wastes_fewer_iterations(self):
        """Trapped in the penalty region: same result, far fewer iterations."""
        system = _system(thickness=0.2)
        optimizer = LensOptimizer(system, _thickness_variable(0.2, 0.15, 0.30), _targets())
        result = optimizer.optimize_simplex(max_iterations=120, tolerance=1e-6)
        self.assertLessEqual(result.iterations, 12)


class TestEmptyVariableListRejected(unittest.TestCase):
    """Regression: success=True, 'Converged after 1 iterations', nothing done."""

    def test_simplex_with_no_variables_raises(self):
        optimizer = LensOptimizer(_system(), [], _targets())
        with self.assertRaises(ValueError) as ctx:
            optimizer.optimize_simplex()
        self.assertIn("at least one variable", str(ctx.exception))

    def test_global_optimize_with_no_variables_raises(self):
        optimizer = GlobalOptimizer(_system(), [], _targets())
        with self.assertRaises(ValueError):
            optimizer.optimize()

    def test_the_message_explains_why(self):
        optimizer = LensOptimizer(_system(), [], _targets())
        with self.assertRaises(ValueError) as ctx:
            optimizer.optimize_simplex()
        self.assertIn("not an optimisation problem", str(ctx.exception))

    def test_one_variable_is_still_fine(self):
        optimizer = LensOptimizer(_system(), _thickness_variable(5.0, 1.0, 10.0), _targets())
        result = optimizer.optimize_simplex(max_iterations=10)
        self.assertGreaterEqual(result.iterations, 1)


class TestOrdinaryOptimizationUnaffected(unittest.TestCase):
    def test_normal_run_still_converges(self):
        optimizer = LensOptimizer(_system(), _thickness_variable(5.0, 1.0, 10.0), _targets())
        result = optimizer.optimize_simplex(max_iterations=200, tolerance=1e-6)
        self.assertIn("Converged", result.message)
        self.assertLess(result.final_merit, result.initial_merit)

    def test_optimisation_still_improves_the_merit(self):
        optimizer = LensOptimizer(_system(), _thickness_variable(5.0, 1.0, 10.0), _targets())
        result = optimizer.optimize_simplex(max_iterations=200)
        self.assertLess(result.final_merit, result.initial_merit)

    def test_tolerance_is_honoured_when_tightened(self):
        optimizer = LensOptimizer(_system(), _thickness_variable(5.0, 1.0, 10.0), _targets())
        loose = optimizer.optimize_simplex(max_iterations=200, tolerance=1e-3)
        tight = optimizer.optimize_simplex(max_iterations=200, tolerance=1e-12)
        self.assertLessEqual(loose.iterations, tight.iterations + 5)


if __name__ == "__main__":
    unittest.main()
