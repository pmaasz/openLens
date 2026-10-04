#!/usr/bin/env python3
"""
A vignetted design must never look like a perfect one.

trace_spot reported "no rays reached the plane" as rms_radius 0.0. That 0.0
was then read as a real measurement by the optimizer (a default of 0.0) and by
Monte Carlo (0.0 <= criterion_limit), so a 99%-vignetted system outscored every
physically real design and reported 100% production yield.
"""

import math
import sys
import os
import unittest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.analysis import SpotDiagram
from src.optical_system import OpticalSystem
from src.lens import Lens
from src.optimizer import MeritFunction, OptimizationTarget, INFEASIBLE_MERIT
from src.tolerancing import (
    InverseSensitivityAnalyzer,
    MonteCarloAnalyzer,
    ToleranceOperand,
    ToleranceType,
)


def _lens(r1, r2, t, d=20.0, n=1.5, name="L"):
    return Lens(
        name=name,
        radius_of_curvature_1=r1,
        radius_of_curvature_2=r2,
        thickness=t,
        diameter=d,
        refractive_index=n,
    )


def _vignetted_system():
    """Two elements behind a 1 mm stop: about 1 of 127 rays survives."""
    system = OpticalSystem(name="Vignetted")
    system.add_lens(_lens(50.0, -50.0, 5.0, name="Front"))
    system.add_lens(_lens(-60.0, 100.0, 4.0, n=1.6, name="Rear"), air_gap_before=2.0)
    system.set_aperture_stop(0, 1.0)
    return system


def _healthy_system():
    system = OpticalSystem(name="Healthy")
    system.add_lens(_lens(50.0, -50.0, 5.0, name="Front"))
    return system


def _operands():
    return [ToleranceOperand(0, ToleranceType.RADIUS_1, -0.01, 0.01)]


class TestVignettedSpotIsNotPerfect(unittest.TestCase):
    def test_spot_reports_none_below_two_rays(self):
        result = SpotDiagram(_vignetted_system()).trace_spot()
        self.assertLess(result["valid_rays"], 2)
        self.assertIsNone(result["rms_radius"])
        self.assertIn("error", result)

    def test_healthy_system_still_reports_a_real_radius(self):
        result = SpotDiagram(_healthy_system()).trace_spot()
        self.assertGreaterEqual(result["valid_rays"], 2)
        self.assertIsInstance(result["rms_radius"], float)
        self.assertGreater(result["rms_radius"], 0.0)
        self.assertNotIn("error", result)

    def test_single_surviving_ray_is_not_zero_radius(self):
        """The whole defect: one ray sits on its own centroid, giving 0.0."""
        result = SpotDiagram(_vignetted_system()).trace_spot()
        self.assertNotEqual(result["rms_radius"], 0.0)


class TestOptimizerRejectsVignettedDesign(unittest.TestCase):
    def test_rms_spot_merit_is_infeasible(self):
        merit = MeritFunction(
            _vignetted_system(), [OptimizationTarget("rms_spot_radius", 0.0)]
        ).evaluate(_vignetted_system())
        self.assertGreaterEqual(merit, INFEASIBLE_MERIT)

    def test_vignetted_design_scores_worse_than_a_healthy_one(self):
        target = [OptimizationTarget("rms_spot_radius", 0.0)]
        vignetted = _vignetted_system()
        healthy = _healthy_system()
        vignetted_merit = MeritFunction(vignetted, target).evaluate(vignetted)
        healthy_merit = MeritFunction(healthy, target).evaluate(healthy)
        self.assertLess(healthy_merit, vignetted_merit)


class TestMonteCarloFailsVignettedTrials(unittest.TestCase):
    def test_yield_is_not_100_percent(self):
        """The headline symptom: 100% yield on an unmanufacturable design."""
        stats = MonteCarloAnalyzer(_vignetted_system(), _operands()).run(
            num_trials=5, criterion_limit=0.05
        )
        self.assertLess(stats["yield"], 100.0)

    def test_statistics_survive_non_finite_values(self):
        """inf values must not crash mean/stdev, which cannot reduce them."""
        stats = MonteCarloAnalyzer(_vignetted_system(), _operands()).run(
            num_trials=5, criterion_limit=0.05
        )
        self.assertEqual(stats["vignetted_trials"], 5)
        self.assertEqual(stats["max"], float("inf"))

    def test_healthy_system_reports_finite_statistics(self):
        stats = MonteCarloAnalyzer(_healthy_system(), _operands()).run(
            num_trials=5, criterion_limit=0.05
        )
        self.assertTrue(math.isfinite(stats["mean"]))
        self.assertEqual(stats["vignetted_trials"], 0)


class TestInverseSensitivityHandlesVignetting(unittest.TestCase):
    def test_vignetted_system_does_not_crash(self):
        rows = InverseSensitivityAnalyzer(
            _vignetted_system(), _operands()
        ).calculate_sensitivities()
        self.assertEqual(len(rows), 1)
        # Undefined, and NaN says so rather than implying a real slope.
        self.assertTrue(math.isnan(rows[0]["sensitivity"]))

    def test_healthy_system_sensitivity_is_finite(self):
        rows = InverseSensitivityAnalyzer(_healthy_system(), _operands()).calculate_sensitivities()
        self.assertTrue(math.isfinite(rows[0]["sensitivity"]))


if __name__ == "__main__":
    unittest.main()
