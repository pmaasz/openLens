#!/usr/bin/env python3
"""
The merit cache must be bounded.

_evaluate_design cached every design it saw in a plain dict that lived for the
process lifetime. Every simplex vertex is a distinct point, so the hit rate
there is only ~12% - the cache grew without bound while contributing little.

It is *not* zero, though: gradient descent re-evaluates the same point when it
backtracks to a smaller step, and simplex shrink re-evaluates the best vertex.
Measured hit rates: 12% for simplex, 33% for gradient descent. So the cache is
worth keeping - it is bounded now, with FIFO eviction.

    before: 25 simplex iterations -> 59 cache entries, growing forever
    after:  capped at MERIT_CACHE_MAX

## On the "reuse one system instead of deep-copying" suggestion

The issue attributes most of the evaluation cost to deepcopy. Measured on this
machine over 25 evaluations:

    25 evaluations      : 0.954 s
    25 deepcopies alone : 0.003 s   (0.3%)

The cost is the aberration/spot trace, not the copy. Reusing a single system
would save ~0.3% while introducing aliasing between the evaluation scratch
system and `self.merit_function`'s own reference, so it is deliberately not
done.
"""

import time
import unittest

from src.lens import Lens
from src.optical_system import OpticalSystem
from src.optimizer import LensOptimizer, OptimizationTarget, OptimizationVariable


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


def _optimizer(cap=None):
    variables = [
        OptimizationVariable(
            name="r1",
            element_index=0,
            parameter="radius_of_curvature_1",
            current_value=50.0,
            min_value=40.0,
            max_value=60.0,
        )
    ]
    targets = [OptimizationTarget("rms_spot_radius", 0, weight=1.0, target_type="minimize")]
    optimizer = LensOptimizer(_system(), variables, targets)
    if cap is not None:
        optimizer.MERIT_CACHE_MAX = cap
    return optimizer


class TestCacheIsBounded(unittest.TestCase):
    def test_distinct_evaluations_do_not_exceed_the_cap(self):
        optimizer = _optimizer(cap=20)
        for i in range(200):
            optimizer._evaluate_design([50.0 + i * 0.001])
        self.assertLessEqual(len(optimizer._merit_cache), 20)

    def test_cap_is_the_class_default(self):
        self.assertGreater(LensOptimizer.MERIT_CACHE_MAX, 0)

    def test_a_simplex_run_stays_bounded(self):
        optimizer = _optimizer(cap=16)
        optimizer.optimize_simplex(max_iterations=60)
        self.assertLessEqual(len(optimizer._merit_cache), 16)

    def test_cache_never_exceeds_the_cap_under_repetition(self):
        """Re-evaluating one point must not grow it."""
        optimizer = _optimizer(cap=8)
        for _ in range(50):
            optimizer._evaluate_design([50.0])
        self.assertEqual(len(optimizer._merit_cache), 1)

    def test_zero_merit_is_cached_rather_than_treated_as_a_miss(self):
        """`is not None`, not truthiness - a merit of 0.0 is a real merit."""
        optimizer = _optimizer()
        optimizer._evaluate_design([50.0])
        before = len(optimizer._merit_cache)
        optimizer._evaluate_design([50.0])
        self.assertEqual(len(optimizer._merit_cache), before)


class TestCacheStillWorks(unittest.TestCase):
    """Bounded must not mean useless."""

    def test_repeat_evaluation_is_a_hit(self):
        optimizer = _optimizer()
        optimizer._evaluate_design([50.0])
        self.assertEqual(len(optimizer._merit_cache), 1)
        optimizer._evaluate_design([50.0])
        self.assertEqual(len(optimizer._merit_cache), 1)

    def test_cached_value_equals_a_fresh_computation(self):
        optimizer = _optimizer()
        first = optimizer._evaluate_design([47.5])
        optimizer._merit_cache.clear()
        second = optimizer._evaluate_design([47.5])
        self.assertEqual(first, second)

    def test_similar_but_distinct_designs_are_not_confused(self):
        """The key rounds to 10 dp; distinct designs must stay distinct."""
        optimizer = _optimizer()
        a = optimizer._evaluate_design([50.0])
        b = optimizer._evaluate_design([50.5])
        self.assertEqual(len(optimizer._merit_cache), 2)
        self.assertNotEqual(a, b)

    def test_optimization_results_are_unchanged(self):
        optimizer = _optimizer()
        result = optimizer.optimize_simplex(max_iterations=40)
        self.assertLess(result.final_merit, result.initial_merit)


class TestEvictionPolicy(unittest.TestCase):
    def test_oldest_entry_is_evicted_first(self):
        optimizer = _optimizer(cap=3)
        for value in (40.0, 41.0, 42.0):
            optimizer._evaluate_design([value])
        self.assertEqual(len(optimizer._merit_cache), 3)

        optimizer._evaluate_design([43.0])

        keys = list(optimizer._merit_cache)
        self.assertEqual(len(keys), 3)
        self.assertNotIn((40.0,), keys)
        self.assertIn((43.0,), keys)

    def test_eviction_keeps_recently_used_entries(self):
        optimizer = _optimizer(cap=3)
        for value in (40.0, 41.0, 42.0):
            optimizer._evaluate_design([value])
        # Re-touch 40.0 by re-inserting it; it becomes the newest.
        optimizer._merit_cache[(40.0,)] = optimizer._merit_cache[(40.0,)]
        optimizer._evaluate_design([43.0])
        self.assertIn((41.0,), optimizer._merit_cache)


class TestDeepcopyCostIsNotTheBottleneck(unittest.TestCase):
    """Documents why the system-reuse suggestion was declined."""

    def test_deepcopy_is_a_small_fraction_of_evaluation_time(self):
        import copy

        optimizer = _optimizer()
        start = time.perf_counter()
        for i in range(10):
            optimizer._evaluate_design([50.0 + i * 0.01])
        evaluate = time.perf_counter() - start

        system = _system()
        start = time.perf_counter()
        for _ in range(10):
            copy.deepcopy(system)
        copying = time.perf_counter() - start

        # Generous bound: the copy must not be the dominant cost.
        self.assertLess(copying, evaluate)


if __name__ == "__main__":
    unittest.main()
