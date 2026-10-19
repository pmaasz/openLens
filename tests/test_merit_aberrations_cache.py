"""#544: one merit evaluation must not compute the same aberrations twice.

MeritFunction sends spherical aberration, coma and astigmatism to three
evaluators, and each used to run a full ``calculate_all_aberrations`` pass
from scratch - coma and astigmatism with the identical 5 degree field. The
shared per-evaluation cache (thread local, because gradient descent
evaluates perturbed designs in parallel on one MeritFunction) removes the
duplicate without letting results outlive the evaluation they belong to.
"""

import unittest
from unittest import mock

from openlens.aberrations import AberrationsCalculator
from openlens.lens import Lens
from openlens.optimizer import MeritFunction, OptimizationTarget
from openlens.optical_system import OpticalSystem


def _biconvex(**kwargs):
    options = dict(
        name="Merit cache",
        radius_of_curvature_1=60.0,
        radius_of_curvature_2=-60.0,
        thickness=6.0,
        diameter=20.0,
        refractive_index=1.5168,
    )
    options.update(kwargs)
    return Lens(**options)


def _target(name):
    return OptimizationTarget(name=name, target_value=0.0, weight=1.0, target_type="minimize")


class _CountingAberrations:
    """Patch calculate_all_aberrations, recording the field angle per call."""

    def __init__(self):
        self.angles = []
        self._original = AberrationsCalculator.calculate_all_aberrations
        self._patcher = None

    def __enter__(self):
        def counting(calculator, *args, **kwargs):
            self.angles.append(kwargs.get("field_angle_deg", 0.0))
            return self._original(calculator, *args, **kwargs)

        self._patcher = mock.patch.object(
            AberrationsCalculator, "calculate_all_aberrations", counting
        )
        self._patcher.start()
        return self

    def __exit__(self, *exc):
        self._patcher.stop()
        return False


class TestMeritSharesTheAberrationPass(unittest.TestCase):
    def setUp(self):
        self.system = OpticalSystem(name="merit-cache")
        self.system.add_lens(_biconvex())
        self.targets = [
            _target("spherical_aberration"),
            _target("coma"),
            _target("astigmatism"),
        ]
        self.merit = MeritFunction(self.system, self.targets)

    def test_one_evaluation_computes_two_aberration_passes(self):
        """0 degrees once, 5 degrees once - not the 5 degree pass twice."""
        with _CountingAberrations() as counting:
            value = self.merit.evaluate(self.system)

        self.assertIsInstance(value, float)
        self.assertEqual(len(counting.angles), 2, counting.angles)
        self.assertEqual(sorted(counting.angles), [0.0, 5.0])

    def test_every_evaluation_gets_a_fresh_cache(self):
        """The shared pass must not outlive the evaluation it belongs to."""
        with _CountingAberrations() as counting:
            self.merit.evaluate(self.system)
            self.merit.evaluate(self.system)

        self.assertEqual(counting.angles, [0.0, 5.0, 0.0, 5.0])

    def test_a_mutation_between_evaluations_is_seen(self):
        """A cached 5 degree result must not mask an edited design."""
        before = self.merit.evaluate(self.system)
        self.system.elements[0].lens.radius_of_curvature_1 = 45.0
        after = self.merit.evaluate(self.system)

        self.assertNotEqual(before, after)

    def test_direct_handler_calls_are_never_cached(self):
        """Outside evaluate() a mutated system must always be re-measured."""
        target = self.targets[1]
        with _CountingAberrations() as counting:
            self.merit._eval_coma(self.system, target)
            self.system.elements[0].lens.radius_of_curvature_1 = 45.0
            self.merit._eval_coma(self.system, target)

        self.assertEqual(len(counting.angles), 2)


if __name__ == "__main__":
    unittest.main()
