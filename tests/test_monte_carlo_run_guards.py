#!/usr/bin/env python3
"""
MonteCarloAnalyzer.run must not divide by zero, echo a fake criterion, or
lose a whole run to one tracer error.

Three separate defects in run():

1. `yield_pct = (pass_count / num_trials) * 100` raised ZeroDivisionError for
   num_trials=0.
2. `criterion` was accepted, echoed into the results dict, and never used -
   run(criterion="something_else") returned unchanged RMS statistics under
   that label.
3. The trial loop called `spot.trace_spot()` directly, while `_spot_rms` -
   which already wraps the trace and maps a vignetted result or any exception
   to inf - sat unused. One TIR aborted the run and every accumulated
   self.results entry was lost.

The nominal trace had the same unguarded shape.
"""

import unittest

from src.lens import Lens
from src.optical_system import OpticalSystem
from src.tolerancing import (
    MonteCarloAnalyzer,
    ToleranceOperand,
    ToleranceType,
)


def _system():
    system = OpticalSystem(name="T")
    system.add_lens(
        Lens(
            name="L",
            radius_of_curvature_1=50.0,
            radius_of_curvature_2=-50.0,
            thickness=5.0,
            diameter=20.0,
            refractive_index=1.5,
        )
    )
    return system


def _ops():
    return [ToleranceOperand(0, ToleranceType.THICKNESS, -0.1, 0.1)]


class _BoomSpotDiagram:
    """Raises after `fail_after` constructions, to simulate a TIR."""

    calls = 0
    fail_after = 0
    original = None

    @classmethod
    def install(cls, fail_after, test):
        import src.tolerancing as module

        cls.calls = 0
        cls.fail_after = fail_after
        cls.original = module.SpotDiagram
        module.SpotDiagram = cls
        test.addCleanup(setattr, module, "SpotDiagram", cls.original)

    def __init__(self, system):
        pass

    def trace_spot(self, **kwargs):
        type(self).calls += 1
        if type(self).calls > type(self).fail_after:
            raise RuntimeError("simulated total internal reflection")
        return type(self).original(_system()).trace_spot(**kwargs)


class TestNumTrialsGuard(unittest.TestCase):
    def test_zero_trials_raises_value_error(self):
        """Regression: ZeroDivisionError escaped run()."""
        analyzer = MonteCarloAnalyzer(_system(), _ops())
        with self.assertRaises(ValueError) as ctx:
            analyzer.run(num_trials=0)
        self.assertIn("num_trials", str(ctx.exception))

    def test_negative_trials_raises_value_error(self):
        analyzer = MonteCarloAnalyzer(_system(), _ops())
        with self.assertRaises(ValueError):
            analyzer.run(num_trials=-3)

    def test_one_trial_is_allowed(self):
        stats = MonteCarloAnalyzer(_system(), _ops(), seed=1).run(num_trials=1)
        self.assertEqual(stats["trials"], 1)


class TestCriterionIsNotDecorative(unittest.TestCase):
    def test_supported_criterion_is_accepted(self):
        stats = MonteCarloAnalyzer(_system(), _ops(), seed=1).run(num_trials=3)
        self.assertEqual(stats["criterion"], "rms_spot_radius")

    def test_unknown_criterion_raises_value_error(self):
        """Regression: it was echoed back while RMS was computed regardless."""
        analyzer = MonteCarloAnalyzer(_system(), _ops(), seed=1)
        with self.assertRaises(ValueError) as ctx:
            analyzer.run(num_trials=3, criterion="something_else")
        self.assertIn("something_else", str(ctx.exception))

    def test_error_names_the_supported_criterion(self):
        analyzer = MonteCarloAnalyzer(_system(), _ops(), seed=1)
        with self.assertRaises(ValueError) as ctx:
            analyzer.run(num_trials=3, criterion="mtf")
        self.assertIn("rms_spot_radius", str(ctx.exception))

    def test_supported_criteria_is_a_class_attribute(self):
        self.assertEqual(MonteCarloAnalyzer.SUPPORTED_CRITERIA, "rms_spot_radius")


class TestTraceFailureDoesNotAbortTheRun(unittest.TestCase):
    def test_trial_trace_error_is_counted_as_a_failure(self):
        """Regression: one TIR killed the run and lost every result."""
        _BoomSpotDiagram.install(fail_after=1, test=self)
        analyzer = MonteCarloAnalyzer(_system(), _ops(), seed=1)
        stats = analyzer.run(num_trials=5)
        self.assertEqual(len(analyzer.results), 5)
        self.assertEqual(stats["trials"], 5)
        self.assertEqual(stats["yield"], 0.0)

    def test_nominal_trace_error_is_contained(self):
        """The nominal trace had the same unguarded shape."""
        _BoomSpotDiagram.install(fail_after=0, test=self)
        analyzer = MonteCarloAnalyzer(_system(), _ops(), seed=1)
        stats = analyzer.run(num_trials=3)
        self.assertEqual(stats["nominal"], float("inf"))

    def test_results_are_never_vacuously_perfect(self):
        _BoomSpotDiagram.install(fail_after=1, test=self)
        analyzer = MonteCarloAnalyzer(_system(), _ops(), seed=1)
        stats = analyzer.run(num_trials=4)
        for result in analyzer.results:
            self.assertFalse(result["passed"])

    def test_partial_failure_still_reports_real_trials(self):
        """Trials that succeeded must survive alongside the failures."""
        _BoomSpotDiagram.install(fail_after=3, test=self)
        analyzer = MonteCarloAnalyzer(_system(), _ops(), seed=1)
        analyzer.run(num_trials=5)
        finite = [r for r in analyzer.results if r["value"] != float("inf")]
        self.assertGreater(len(finite), 0)

    def test_normal_run_is_unaffected(self):
        analyzer = MonteCarloAnalyzer(_system(), _ops(), seed=7)
        stats = analyzer.run(num_trials=6)
        self.assertEqual(stats["vignetted_trials"], 0)
        self.assertTrue(stats["std_dev"] >= 0.0)
        self.assertTrue(0.0 <= stats["yield"] <= 100.0)


if __name__ == "__main__":
    unittest.main()
