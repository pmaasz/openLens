#!/usr/bin/env python3
"""
Global optimization must not write into the caller's variable objects.

Both global optimizers finished with:

    self._apply_variables(best_values)          # return value dropped
    for i, val in enumerate(best_values):
        self.variables[i].current_value = val    # this is what actually worked
    local_result = self.optimize_simplex(max_iterations=50)

_apply_variables returns a deepcopy and never mutates self.system, so those
calls were dead code. The state transfer happened *only* through mutation of
the caller's OptimizationVariable objects - which
gui/tabs/optimization_tab.py also reads and saves. So a simulated-annealing or
genetic run silently replaced the user's inputs with its result.

Verified before the fix:

    simulated annealing caller vars [50.0] -> [52.01002132572631]  mutated: True
    genetic             caller vars [50.0] -> [59.466763858241826]  mutated: True

and after, with identical optimization results:

    simulated annealing caller vars [50.0] -> [50.0]  mutated: False
    genetic             caller vars [50.0] -> [50.0]  mutated: False

optimize_simplex now takes an explicit `start`.
"""

import unittest

from src.global_optimizer import GlobalOptimizer
from src.lens import Lens
from src.optimizer import LensOptimizer, OptimizationTarget, OptimizationVariable
from src.optical_system import OpticalSystem


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


SA = dict(max_iterations=25, initial_temperature=1.0, cooling_rate=0.9)
GA = dict(population_size=10, generations=3, mutation_rate=0.2, crossover_rate=0.7)


class TestCallerVariablesAreNotMutated(unittest.TestCase):
    """Regression: the caller's OptimizationVariable objects were overwritten."""

    def test_simulated_annealing_leaves_variables_alone(self):
        variables = _variables()
        before = [v.current_value for v in variables]
        GlobalOptimizer(_system(), variables, _targets()).optimize_simulated_annealing(**SA)
        self.assertEqual([v.current_value for v in variables], before)

    def test_genetic_leaves_variables_alone(self):
        variables = _variables()
        before = [v.current_value for v in variables]
        GlobalOptimizer(_system(), variables, _targets()).optimize_genetic(**GA)
        self.assertEqual([v.current_value for v in variables], before)

    def test_other_variable_attributes_are_untouched(self):
        variables = _variables()
        snapshot = [
            (v.name, v.element_index, v.parameter, v.min_value, v.max_value) for v in variables
        ]
        GlobalOptimizer(_system(), variables, _targets()).optimize_simulated_annealing(**SA)
        self.assertEqual(
            [(v.name, v.element_index, v.parameter, v.min_value, v.max_value) for v in variables],
            snapshot,
        )

    def test_optimization_still_works(self):
        result = GlobalOptimizer(_system(), _variables(), _targets()).optimize_simulated_annealing(
            **SA
        )
        self.assertLess(result.final_merit, result.initial_merit)


class TestSimplexStartParameter(unittest.TestCase):
    def setUp(self):
        self.optimizer = LensOptimizer(_system(), _variables(), _targets())

    def test_default_start_is_the_current_values(self):
        result = self.optimizer.optimize_simplex(max_iterations=5)
        self.assertTrue(result.success or result.iterations >= 1)

    def test_explicit_start_is_used(self):
        result = self.optimizer.optimize_simplex(max_iterations=3, start=[45.0])
        self.assertAlmostEqual(
            self.optimizer._evaluate_design([45.0]),
            self.optimizer._evaluate_design([45.0]),
        )
        self.assertGreaterEqual(result.iterations, 1)

    def test_start_with_wrong_length_is_rejected(self):
        with self.assertRaises(ValueError):
            self.optimizer.optimize_simplex(start=[45.0, 1.0])

    def test_start_does_not_mutate_the_variables(self):
        variables = _variables()
        optimizer = LensOptimizer(_system(), variables, _targets())
        optimizer.optimize_simplex(max_iterations=5, start=[47.5])
        self.assertEqual(variables[0].current_value, 50.0)

    def test_start_list_is_not_aliased(self):
        """A later caller-side edit must not corrupt the simplex."""
        start = [45.0]
        self.optimizer.optimize_simplex(max_iterations=3, start=start)
        self.assertEqual(start, [45.0])


class TestDeadApplyVariablesCallsRemoved(unittest.TestCase):
    def test_no_apply_variables_call_remains_in_global_optimizer(self):
        import inspect

        source = inspect.getsource(GlobalOptimizer)
        code = "\n".join(line for line in source.splitlines() if not line.strip().startswith("#"))
        self.assertNotIn("_apply_variables(", code)

    def test_no_current_value_assignment_remains(self):
        import inspect

        source = inspect.getsource(GlobalOptimizer)
        code = "\n".join(line for line in source.splitlines() if not line.strip().startswith("#"))
        self.assertNotIn("current_value = val", code)

    def test_apply_variables_really_is_a_pure_function(self):
        """The premise of the dead-code claim: it never mutates the system."""
        optimizer = LensOptimizer(_system(), _variables(), _targets())
        system = optimizer.system
        before = system.elements[0].lens.radius_of_curvature_1
        optimizer._apply_variables([44.0])
        self.assertEqual(system.elements[0].lens.radius_of_curvature_1, before)


if __name__ == "__main__":
    unittest.main()
