#!/usr/bin/env python3
"""
An optimization that cannot be made is not a success.

``OptimizationResult.success`` only checked that the variable values were
inside their bounds. A design with a hard geometry penalty - a negative edge
thickness, vertices that cross - was returned as ``success=True`` with the
message "Converged", and the GUI showed "Optimization Successful!".
"""

import unittest

from openlens.lens import Lens
from openlens.optical_system import OpticalSystem
from openlens.optimizer import (
    LensOptimizer,
    OptimizationTarget,
    OptimizationVariable,
)


def _system(r1, r2, thickness, diameter):
    system = OpticalSystem("singlet")
    system.add_lens(
        Lens(
            radius_of_curvature_1=r1,
            radius_of_curvature_2=r2,
            thickness=thickness,
            diameter=diameter,
            refractive_index=1.5168,
        )
    )
    return system


class TestSuccessRequiresAFeasibleDesign(unittest.TestCase):
    """The success flag must mean the design can be made."""

    def test_an_impossible_design_is_not_a_success(self):
        """A negative edge thickness cannot be reported as converged"""
        # R = 20 mm with a 40 mm diameter: the surfaces cross inside the
        # clear aperture, and no variable can repair that.
        system = _system(20.0, -20.0, 5.0, 40.0)
        variables = [OptimizationVariable("n", 0, "refractive_index", 1.5168, 1.40, 1.60, 0.01)]
        targets = [OptimizationTarget("focal_length", 100.0, weight=1.0, target_type="target")]

        optimizer = LensOptimizer(system, variables, targets)
        result = optimizer.optimize_simplex(max_iterations=60)

        self.assertFalse(result.success, "an impossible design was reported as a success")
        self.assertIn("physical constraint", result.message)
        self.assertLess(
            result.optimized_system.elements[0].lens.calculate_edge_thickness(),
            0.0,
        )

    def test_a_feasible_design_is_still_a_success(self):
        """The ordinary case must keep reporting success"""
        system = _system(100.0, -100.0, 5.0, 25.0)
        variables = [
            OptimizationVariable("R1", 0, "radius_of_curvature_1", 100.0, 60.0, 200.0, 5.0)
        ]
        targets = [OptimizationTarget("focal_length", 100.0, weight=1.0, target_type="target")]

        optimizer = LensOptimizer(system, variables, targets)
        result = optimizer.optimize_simplex(max_iterations=60)

        self.assertTrue(result.success, result.message)
        self.assertIn("Converged", result.message)

    def test_a_design_outside_the_variable_box_is_still_reported_as_such(self):
        """The bounds message must survive the feasibility check"""
        system = _system(100.0, -100.0, 5.0, 25.0)
        # A start far outside the box, with a step so small that the simplex
        # cannot get back in: the result stays outside the bounds.
        variables = [
            OptimizationVariable("R1", 0, "radius_of_curvature_1", 100.0, 20.0, 30.0, 1e-15)
        ]
        targets = [OptimizationTarget("focal_length", 100.0, weight=1.0, target_type="target")]

        optimizer = LensOptimizer(system, variables, targets)
        result = optimizer.optimize_simplex(max_iterations=50)

        self.assertFalse(result.success)
        self.assertIn("bounds", result.message)


if __name__ == "__main__":
    unittest.main()
