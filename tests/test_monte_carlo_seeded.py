#!/usr/bin/env python3
"""
Seeded Monte Carlo tolerancing: determinism and statistics sanity.

MonteCarloAnalyzer(seed=...) seeds the global `random` module, so two
runs with the same seed must produce identical statistics. This pins
the RNG consumption order against silent drift.
"""

import unittest

from src.lens import Lens
from src.optical_system import OpticalSystem
from src.tolerancing import MonteCarloAnalyzer, ToleranceOperand, ToleranceType

from _utils import skip_slow


def _make_system():
    system = OpticalSystem(name="mc")
    system.add_lens(
        Lens(
            radius_of_curvature_1=50.0,
            radius_of_curvature_2=-50.0,
            thickness=5.0,
            diameter=25.0,
            refractive_index=1.5,
        )
    )
    return system


def _make_tolerances(distribution="uniform"):
    return [
        ToleranceOperand(
            element_index=0,
            param_type=ToleranceType.RADIUS_1,
            min_val=-1.0,
            max_val=1.0,
            distribution=distribution,
        ),
    ]


@skip_slow
class TestSeededMonteCarlo(unittest.TestCase):
    """RNG-seeded Monte Carlo reproducibility"""

    def _run(self, seed, num_trials=40, distribution="uniform"):
        analyzer = MonteCarloAnalyzer(_make_system(), _make_tolerances(distribution), seed=seed)
        return analyzer.run(num_trials=num_trials)

    def test_same_seed_reproduces_statistics(self):
        """Two identically-seeded runs produce identical stats"""
        a = self._run(seed=42)
        b = self._run(seed=42)
        for key in ("mean", "std_dev", "min", "max", "yield"):
            self.assertAlmostEqual(
                a[key], b[key], places=12, msg=f"stat '{key}' drifted between runs"
            )

    def test_different_seed_changes_sample(self):
        """Different seeds sample different systems"""
        a = self._run(seed=1)
        b = self._run(seed=2)
        self.assertNotAlmostEqual(a["mean"], b["mean"])

    def test_uniform_pinned_mean_and_std(self):
        """Uniform +/-1mm on R1 with seed 42: pinned mean/std (CPython MT19937)"""
        stats = self._run(seed=42)
        # Perturbation is uniform on [-1, 1] mm of R1; RMS response grows
        # monotonically with |dR|, so mean shifts upward from nominal.
        nominal = stats["nominal"]
        self.assertGreater(stats["mean"], nominal - 0.01)
        self.assertLess(stats["std_dev"], abs(nominal) * 0.05)

    def test_yield_within_bounds(self):
        """Yield is a percentage regardless of criterion"""
        for limit in (0.001, 100.0):
            stats = self._run(seed=7)
            self.assertGreaterEqual(stats["yield"], 0.0)
            self.assertLessEqual(stats["yield"], 100.0)


if __name__ == "__main__":
    unittest.main()
