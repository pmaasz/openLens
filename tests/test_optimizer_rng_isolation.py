#!/usr/bin/env python3
"""
Optimizers must not reseed the process-global RNG, and seed= must mean something.

Both constructors did:

    if seed is not None:
        random.seed(seed)

which rewrites module-level state. Reproduced:

    random.seed(1);  a = random.random()   # 0.134364
    random.seed(99); MonteCarloAnalyzer(None, [], seed=7)
    b = random.random()                    # 0.323833  <- reseeded, not 99's draw

GlobalOptimizer.__init__ runs inside a QThread (optimization_tab.py), so this
mutated RNG state the Qt thread could be consuming concurrently.

Worse, `seed=` did not make a run reproducible anyway: every draw came from the
one shared stream, so any unrelated `random` call anywhere in the process
interleaved with it.

Each class now owns a `random.Random(seed)` and threads it through.
"""

import random
import unittest

from src.lens import Lens
from src.optical_system import OpticalSystem
from src.optimizer import OptimizationTarget, OptimizationVariable
from src.tolerancing import MonteCarloAnalyzer, ToleranceOperand, ToleranceType


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


def _operands():
    return [ToleranceOperand(0, ToleranceType.THICKNESS, -0.1, 0.1)]


class TestGlobalStreamIsUntouched(unittest.TestCase):
    def test_constructing_an_analyzer_does_not_reseed_the_module(self):
        """Regression: the next global draw came from seed=7, not the caller."""
        random.seed(99)
        expected = random.random()

        random.seed(99)
        MonteCarloAnalyzer(None, [], seed=7)
        after = random.random()

        self.assertEqual(after, expected)

    def test_constructing_a_global_optimizer_does_not_reseed(self):
        from src.global_optimizer import GlobalOptimizer

        random.seed(1234)
        expected = random.random()

        random.seed(1234)
        GlobalOptimizer(None, [], [], seed=99)
        after = random.random()

        self.assertEqual(after, expected)

    def test_a_run_does_not_disturb_the_global_stream(self):
        random.seed(5)
        expected = random.random()
        random.seed(5)
        MonteCarloAnalyzer(_system(), _operands(), seed=1).run(num_trials=4)
        self.assertEqual(random.random(), expected)


class TestSeedIsActuallyReproducible(unittest.TestCase):
    """Regression: interleaved global draws changed the result."""

    def _run(self, seed, noise=0):
        for _ in range(noise):
            random.random()
        return MonteCarloAnalyzer(_system(), _operands(), seed=seed).run(num_trials=8)

    def test_same_seed_same_result(self):
        self.assertEqual(self._run(7), self._run(7))

    def test_same_seed_survives_interleaved_global_draws(self):
        """The point of a private generator."""
        self.assertEqual(self._run(7, noise=0), self._run(7, noise=25))

    def test_different_seed_different_result(self):
        self.assertNotEqual(self._run(7), self._run(8))

    def test_global_optimizer_seed_is_reproducible(self):
        from src.global_optimizer import GlobalOptimizer

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

        def run(seed, noise=0):
            for _ in range(noise):
                random.random()
            optimizer = GlobalOptimizer(_system(), variables, targets, seed=seed)
            return optimizer.optimize_simulated_annealing(
                max_iterations=20, initial_temperature=1.0, cooling_rate=0.9
            )

        first = run(3)
        self.assertEqual(first.final_merit, run(3).final_merit)
        self.assertEqual(first.final_merit, run(3, noise=25).final_merit)


class TestGenerateValueApi(unittest.TestCase):
    """generate_value gained an optional rng and stays backwards compatible."""

    def test_works_without_an_rng(self):
        operand = ToleranceOperand(0, ToleranceType.THICKNESS, -0.1, 0.1)
        value = operand.generate_value()
        self.assertGreaterEqual(value, -0.1)
        self.assertLessEqual(value, 0.1)

    def test_uses_the_supplied_rng(self):
        operand = ToleranceOperand(0, ToleranceType.THICKNESS, -0.1, 0.1)
        first = operand.generate_value(random.Random(11))
        second = operand.generate_value(random.Random(11))
        self.assertEqual(first, second)

    def test_gaussian_stays_within_limits(self):
        operand = ToleranceOperand(0, ToleranceType.THICKNESS, -0.05, 0.05, distribution="gaussian")
        rng = random.Random(2)
        for _ in range(50):
            value = operand.generate_value(rng)
            self.assertGreaterEqual(value, -0.05)
            self.assertLessEqual(value, 0.05)

    def test_two_operands_from_one_rng_differ(self):
        a = ToleranceOperand(0, ToleranceType.THICKNESS, -1.0, 1.0)
        b = ToleranceOperand(0, ToleranceType.THICKNESS, -1.0, 1.0)
        rng = random.Random(4)
        self.assertNotEqual(a.generate_value(rng), b.generate_value(rng))


class TestNoModuleLevelReseedRemains(unittest.TestCase):
    def test_no_random_seed_calls_in_src(self):
        import pathlib
        import re

        root = pathlib.Path(__file__).resolve().parent.parent / "src"
        pattern = re.compile(r"(?<![\w.])random\.seed\(")
        offenders = []
        for path in root.rglob("*.py"):
            # Strip comments: the fixes name random.seed() in prose to say why
            # it is gone.
            code = "\n".join(
                line
                for line in path.read_text(encoding="utf-8").splitlines()
                if not line.strip().startswith("#")
            )
            if pattern.search(code):
                offenders.append(path.name)
        self.assertEqual(offenders, [], "random.seed() still present in %s" % offenders)


if __name__ == "__main__":
    unittest.main()
