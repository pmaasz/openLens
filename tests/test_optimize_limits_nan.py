"""Regression: a NaN sensitivity must not become a NaN tolerance.

``calculate_sensitivities`` deliberately reports NaN for a vignetted operand -
"could not be measured" rather than "insensitive". ``optimize_limits`` then did:

    s = abs(nan)              # nan
    if s < 1e-9:              # False - nan comparisons are always False
        new_limit = original
    else:
        new_limit = budget / s  # nan

so the operand came back with ``min_val = max_val = nan``. A NaN tolerance is not
a tight or a loose one - it is a number that silently propagates into every
downstream trace, comparison and report.

The same test pins the degenerate cases that must still hold: a genuinely
insensitive operand keeps its original limit, and a usable sensitivity still
divides the budget.
"""

import ast as ast_module
import inspect
import math
import textwrap
import unittest

from openlens.lens import Lens
from openlens.optical_system import OpticalSystem
from openlens.tolerancing import InverseSensitivityAnalyzer, ToleranceOperand, ToleranceType


def _system():
    system = OpticalSystem()
    system.add_lens(
        Lens(
            radius_of_curvature_1=100.0,
            radius_of_curvature_2=-100.0,
            thickness=5.0,
            diameter=25.0,
            refractive_index=1.5,
        )
    )
    return system


def _definitions_by_name(cls):
    """How many times each method is defined in *cls*'s source."""
    source = textwrap.dedent(inspect.getsource(cls))
    tree = ast_module.parse(source)
    counts = {}
    for node in ast_module.walk(tree):
        if isinstance(node, ast_module.FunctionDef):
            counts[node.name] = counts.get(node.name, 0) + 1
    return counts


def _operand(max_val=1.0):
    return ToleranceOperand(
        element_index=0,
        param_type=ToleranceType.THICKNESS,
        min_val=-max_val,
        max_val=max_val,
    )


def _analyzer(operands, sensitivities):
    analyzer = InverseSensitivityAnalyzer(_system(), operands)
    analyzer.calculate_sensitivities = lambda *a, **k: sensitivities
    return analyzer


class TestNaNSensitivityKeepsTheOriginalTolerance(unittest.TestCase):
    """A measurement that failed must not become a number."""

    def setUp(self):
        self.originals = [_operand(1.0), _operand(2.0)]
        self.sensitivities = [
            {"sensitivity": 0.01},
            {"sensitivity": float("nan")},
        ]
        self.limits = _analyzer(self.originals, self.sensitivities).optimize_limits(
            target_yield_criterion=0.01, method="rss"
        )

    def test_no_operand_gets_a_nan_limit(self):
        for index, tol in enumerate(self.limits):
            with self.subTest(operand=index):
                self.assertTrue(
                    math.isfinite(tol.max_val),
                    f"operand {index} came back with max_val={tol.max_val}",
                )
                self.assertTrue(
                    math.isfinite(tol.min_val),
                    f"operand {index} came back with min_val={tol.min_val}",
                )

    def test_the_vignetted_operand_keeps_its_original_limit(self):
        tol = self.limits[1]

        self.assertAlmostEqual(
            tol.max_val,
            self.originals[1].max_val,
            places=9,
            msg="the operand whose sensitivity could not be measured was "
            "re-budgeted from a NaN instead of being left alone",
        )
        self.assertAlmostEqual(tol.min_val, -self.originals[1].max_val, places=9)

    def test_the_measurable_operand_is_still_re_budgeted(self):
        """The fix must not blanket-keep everything."""
        usable = self.sensitivities[0]["sensitivity"]
        budget = 0.01 / math.sqrt(2)
        expected = budget / abs(usable)

        self.assertAlmostEqual(
            self.limits[0].max_val, expected, places=9, msg="the usable operand was not re-budgeted"
        )

    def test_the_two_operands_differ(self):
        """Keeping one and budgeting the other is the whole point."""
        self.assertNotAlmostEqual(self.limits[0].max_val, self.limits[1].max_val, places=6)

    def test_the_originals_are_not_mutated(self):
        """The analyzer deep-copies each operand before editing it."""
        self.assertAlmostEqual(self.originals[1].max_val, 2.0, places=9)
        self.assertAlmostEqual(self.originals[1].min_val, -2.0, places=9)


class TestDegenerateSensitivitiesAreAllSafe(unittest.TestCase):
    """Whatever the sensitivity, the result must be a usable number."""

    def _limits_for(self, sensitivity, method="rss"):
        return _analyzer([_operand(3.0)], [{"sensitivity": sensitivity}]).optimize_limits(
            target_yield_criterion=0.01, method=method
        )[0]

    def test_zero_sensitivity_keeps_the_original(self):
        tol = self._limits_for(0.0)
        self.assertAlmostEqual(tol.max_val, 3.0, places=9)

    def test_tiny_sensitivity_keeps_the_original(self):
        tol = self._limits_for(1e-12)
        self.assertAlmostEqual(tol.max_val, 3.0, places=9)

    def test_infinite_sensitivity_keeps_the_original(self):
        tol = self._limits_for(float("inf"))

        self.assertTrue(math.isfinite(tol.max_val))
        self.assertAlmostEqual(
            tol.max_val,
            3.0,
            places=9,
            msg="an infinite sensitivity must not produce an infinite budget",
        )

    def test_negative_sensitivity_is_handled_by_magnitude(self):
        """Sensitivity is a slope; its sign should not change the budget."""
        positive = self._limits_for(0.02)
        negative = self._limits_for(-0.02)

        self.assertAlmostEqual(positive.max_val, negative.max_val, places=9)
        self.assertTrue(math.isfinite(negative.max_val))

    def test_every_method_produces_finite_limits(self):
        for method in ("rss", "worst_case"):
            with self.subTest(method=method):
                tol = self._limits_for(float("nan"), method=method)
                self.assertTrue(math.isfinite(tol.max_val))
                self.assertTrue(math.isfinite(tol.min_val))

    def test_all_nan_sensitivities_are_all_safe(self):
        analyzer = _analyzer(
            [_operand(1.0), _operand(2.0), _operand(4.0)],
            [{"sensitivity": float("nan")}] * 3,
        )
        limits = analyzer.optimize_limits(target_yield_criterion=0.01)

        self.assertEqual([t.max_val for t in limits], [1.0, 2.0, 4.0])


class TestNoDuplicateMethodDefinitions(unittest.TestCase):
    """_get_system_state was defined twice; the second silently won."""

    def test_state_helpers_are_defined_once(self):
        names = _definitions_by_name(InverseSensitivityAnalyzer)

        for helper in ("_get_system_state", "_set_system_state"):
            with self.subTest(helper=helper):
                self.assertEqual(
                    names.get(helper, 0),
                    1,
                    f"{helper} is defined {names.get(helper)} times; the last "
                    f"definition silently overrides the earlier one",
                )

    def test_the_duplicate_definitions_were_identical(self):
        """If they differed, removing one would have changed behaviour."""
        source = textwrap.dedent(inspect.getsource(InverseSensitivityAnalyzer))
        tree = ast_module.parse(source)

        bodies = {}
        for node in ast_module.walk(tree):
            if isinstance(node, ast_module.FunctionDef) and node.name in (
                "_get_system_state",
                "_set_system_state",
            ):
                bodies.setdefault(node.name, []).append(
                    ast_module.dump(ast_module.Module(body=node.body, type_ignores=[]))
                )

        for name, dumps in bodies.items():
            with self.subTest(helper=name):
                self.assertEqual(
                    len(set(dumps)),
                    1,
                    f"{name} has {len(set(dumps))} different bodies; deleting "
                    f"one would change behaviour",
                )


if __name__ == "__main__":
    unittest.main()
