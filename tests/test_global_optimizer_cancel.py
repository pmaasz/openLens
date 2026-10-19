#!/usr/bin/env python3
"""Regression: the global optimisers must honour cancellation.

The GUI drives simulated annealing and the genetic algorithm with a
cooperative callback that raises ``OptimizationCancelled`` when Stop is
pressed. Three things stopped that from working:

- After annealing, ``optimize_simplex(max_iterations=50, start=...)`` was
  called *without* the callback, so up to 50 local iterations ran
  uninterruptibly.
- The GA checked the callback once per generation - 30 evaluations between
  checks, which at the MTF merit's ~2.4 s per evaluation is over a minute.
- With the default T0 = 100 and cooling 0.95, annealing hit its temperature
  floor at about 360 iterations, so the GUI's ``max_iterations=500`` was
  never reached and the run always stopped early.

The callback is the *only* way the GUI can stop a global run, so it has to be
consulted often enough to be responsive and threaded through every phase.
"""

import unittest

from openlens.global_optimizer import GlobalOptimizer
from openlens.lens import Lens
from openlens.optical_system import OpticalSystem
from openlens.optimizer import OptimizationTarget, OptimizationVariable


class Cancelled(Exception):
    """Stands in for OptimizationCancelled, which the GUI's callback raises."""


class _Stopper:
    """Records callback visits, and raises once asked to.

    Both phases call the same callback with their own ``iteration`` numbering:
    the annealing loop, then the local refinement that polishes its result.
    A drop in ``iteration`` means a new phase started, so the first phase's
    progress is recorded separately and frozen once the second begins -
    otherwise the refinement's numbering hides how far annealing actually got.
    """

    def __init__(self, stop_after=None):
        self.visits = 0
        self.last_iteration = -1
        self.stop_after = stop_after
        # Progress within the *first* phase only (the annealing loop).
        self.first_phase_visits = 0
        self.first_phase_max_iteration = -1
        self._in_first_phase = True
        self._previous_iteration = -1

    def __call__(self, iteration, merit, values):
        self.visits += 1
        self.last_iteration = iteration
        if self._in_first_phase:
            if iteration < self._previous_iteration:
                # The numbering went backwards: a new phase started.
                self._in_first_phase = False
            else:
                self.first_phase_visits += 1
                self.first_phase_max_iteration = max(self.first_phase_max_iteration, iteration)
        self._previous_iteration = iteration
        if self.stop_after is not None and self.visits > self.stop_after:
            raise Cancelled("cancelled")


def _optimizer():
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
    variables = [OptimizationVariable("R1", 0, "radius_of_curvature_1", 100.0, 50.0, 150.0)]
    targets = [OptimizationTarget("focal_length", 80.0, weight=1.0, target_type="target")]
    return GlobalOptimizer(system, variables, targets, seed=7)


class TestAnnealingHonoursMaxIterations(unittest.TestCase):
    """The run must last as long as the caller asked for."""

    def test_the_run_is_not_cut_short_by_the_temperature_floor(self):
        """It stopped at ~360 iterations, so max_iterations=500 was unreachable."""
        optimizer = _optimizer()
        callback = _Stopper()

        optimizer.optimize_simulated_annealing(max_iterations=500, callback=callback)

        self.assertGreaterEqual(
            callback.first_phase_max_iteration,
            499,
            f"annealing stopped at iteration {callback.first_phase_max_iteration} "
            f"instead of running the requested 500",
        )

    def test_the_callback_is_consulted_once_per_iteration(self):
        optimizer = _optimizer()
        callback = _Stopper()

        optimizer.optimize_simulated_annealing(max_iterations=120, callback=callback)

        self.assertEqual(
            callback.first_phase_visits,
            120,
            "the callback is not being called every annealing iteration",
        )

    def test_a_short_run_is_still_short(self):
        """Deriving the schedule must not force a minimum length."""
        optimizer = _optimizer()
        callback = _Stopper()

        optimizer.optimize_simulated_annealing(max_iterations=20, callback=callback)

        self.assertEqual(callback.first_phase_visits, 20)

    def test_an_explicit_cooling_rate_is_still_honoured(self):
        """An explicit schedule is the caller's choice and is not overridden."""
        optimizer = _optimizer()
        callback = _Stopper()

        optimizer.optimize_simulated_annealing(
            max_iterations=500,
            initial_temperature=100.0,
            cooling_rate=0.5,
            callback=callback,
        )

        # 100 * 0.5**n < 1e-6 at n = 24.
        self.assertLess(callback.last_iteration, 100)


class TestCancellationReachesEveryPhase(unittest.TestCase):
    """A cancel must not be swallowed by a phase that forgot the callback."""

    def test_cancelling_during_the_annealing_loop_stops_the_run(self):
        optimizer = _optimizer()
        callback = _Stopper(stop_after=5)

        with self.assertRaises(Cancelled):
            optimizer.optimize_simulated_annealing(max_iterations=500, callback=callback)

        self.assertLessEqual(
            callback.visits,
            6,
            "the run kept going after the callback asked to stop",
        )

    def test_cancelling_reaches_the_final_local_refinement(self):
        """The simplex polish was called without the callback.

        The polishing simplex runs up to 50 iterations after annealing ends.
        With the callback threaded through it, a Stop is honoured there too,
        rather than costing up to 50 uninterruptible evaluations.

        max_iterations=2 means the annealing loop calls the callback exactly
        twice, so raising on the third visit can only come from the polish -
        which is what isolates this test from the loop.
        """
        optimizer = _optimizer()
        callback = _Stopper(stop_after=2)

        with self.assertRaises(Cancelled):
            optimizer.optimize_simulated_annealing(max_iterations=2, callback=callback)

        self.assertEqual(
            callback.visits,
            3,
            "the refinement phase never consulted the callback, so a Stop "
            "pressed there was ignored for up to 50 iterations",
        )

    def test_cancelling_during_the_genetic_population_stops_the_run(self):
        optimizer = _optimizer()
        callback = _Stopper(stop_after=3)

        with self.assertRaises(Cancelled):
            optimizer.optimize_genetic(population_size=20, generations=5, callback=callback)

        self.assertLessEqual(
            callback.first_phase_visits,
            4,
            "the GA kept going for a whole generation after the callback " "asked to stop",
        )


class TestGeneticCallbackIsFrequentEnough(unittest.TestCase):
    """Once per generation is once per population_size evaluations."""

    def test_the_callback_runs_inside_the_population_loop(self):
        optimizer = _optimizer()
        callback = _Stopper()

        optimizer.optimize_genetic(population_size=20, generations=5, callback=callback)

        self.assertGreaterEqual(
            callback.first_phase_visits,
            100,
            f"the callback was consulted {callback.first_phase_visits} times for "
            f"5 generations of 20 individuals - it is only being checked once "
            f"per generation, so a cancel waits for a whole population",
        )

    def test_a_cancel_lands_within_a_few_evaluations(self):
        """The issue: ~2.4 s per evaluation times 30 is over a minute.

        Counts the merit evaluations that happen before the callback asks to
        stop. Checking only per generation means the whole population is
        evaluated first, so this count comes out at population_size.
        """
        optimizer = _optimizer()
        callback = _Stopper(stop_after=2)
        evaluations = []
        inner = optimizer._evaluate_design

        def counting(values):
            evaluations.append(1)
            return inner(values)

        optimizer._evaluate_design = counting

        with self.assertRaises(Cancelled):
            optimizer.optimize_genetic(population_size=30, generations=30, callback=callback)

        self.assertLessEqual(
            len(evaluations),
            5,
            f"{len(evaluations)} merit evaluations ran after the cancel was "
            f"requested - the callback is only consulted once per generation",
        )


class TestCancellationIsNotSwallowed(unittest.TestCase):
    """An exception from the callback must reach the caller, not be absorbed."""

    def test_the_annealing_callback_exception_propagates(self):
        optimizer = _optimizer()

        def boom(iteration, merit, values):
            raise Cancelled("stop now")

        with self.assertRaises(Cancelled):
            optimizer.optimize_simulated_annealing(max_iterations=500, callback=boom)

    def test_the_genetic_callback_exception_propagates(self):
        optimizer = _optimizer()

        def boom(iteration, merit, values):
            raise Cancelled("stop now")

        with self.assertRaises(Cancelled):
            optimizer.optimize_genetic(population_size=10, generations=5, callback=boom)


if __name__ == "__main__":
    unittest.main()
