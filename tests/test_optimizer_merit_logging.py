#!/usr/bin/env python3
"""
The merit function must not reach its dependencies through globals().

Both evaluator helpers looked their dependencies up in globals():

    if "SpotDiagram" in globals():
        spot = globals()["SpotDiagram"](system)
    ...
    except Exception:
        pass

Two problems:

1. The names are imported unconditionally at module scope (SpotDiagram at the
   top of optimizer.py, PSFCalculator/WavefrontSensor/NUMPY_AVAILABLE from
   analysis.beam_synthesis), so every `"X" in globals()` test was dead weight
   that hid the dependency from readers and from linters alike.
2. The bare `except Exception: pass` discarded the exception entirely. A
   KeyError from a malformed spot result and a genuine geometry failure both
   collapsed to the same INFEASIBLE_MERIT with no trace at all - you could not
   tell a broken evaluator from a legitimately infeasible design.

The names are now used directly and every caught exception is logged.
"""

import logging
import unittest

from src.optimizer import INFEASIBLE_MERIT, MeritFunction, OptimizationTarget
import src.optimizer as optimizer_module


def _system():
    from src.lens import Lens
    from src.optical_system import OpticalSystem

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


def _target(kind):
    return OptimizationTarget(kind, 0, weight=1.0, target_type="minimize")


class TestNoGlobalsLookup(unittest.TestCase):
    def test_no_runtime_globals_calls_remain(self):
        """The only occurrence left is inside an explanatory comment."""
        import inspect
        import re

        source = inspect.getsource(optimizer_module)
        # Strip comments before looking for a real call.
        code = "\n".join(line for line in source.splitlines() if not line.strip().startswith("#"))
        self.assertNotIn("globals()", code)

    def test_dependencies_are_module_level_names(self):
        # PSFCalculator was renamed DiffractionPSFCalculator when the
        # wavefront/PSF pair was consolidated onto analysis.diffraction_psf.
        # The point of the test is that these are plain module-level imports,
        # not runtime globals() lookups - the name change does not affect it.
        for name in (
            "SpotDiagram",
            "DiffractionPSFCalculator",
            "WavefrontSensor",
            "NUMPY_AVAILABLE",
        ):
            with self.subTest(name=name):
                self.assertTrue(hasattr(optimizer_module, name))

    def test_evaluator_source_names_its_dependency_directly(self):
        import inspect

        for method in (MeritFunction._eval_rms_spot, MeritFunction._eval_mtf):
            source = inspect.getsource(method)
            code = "\n".join(
                line for line in source.splitlines() if not line.strip().startswith("#")
            )
            self.assertNotIn("globals()", code)


class TestFailuresAreDistinguishable(unittest.TestCase):
    """Regression: both failure modes returned a silent 1e9."""

    def setUp(self):
        self.system = _system()
        self.target = _target("rms_spot_radius")
        self.original = optimizer_module.SpotDiagram
        self.addCleanup(setattr, optimizer_module, "SpotDiagram", self.original)

    def _capture(self, level=logging.WARNING):
        records = []

        class Handler(logging.Handler):
            def emit(self, record):
                records.append(record)

        logger = logging.getLogger("src.optimizer")
        handler = Handler()
        logger.addHandler(handler)
        old = logger.level
        logger.setLevel(level)
        try:
            merit = MeritFunction._eval_rms_spot(self.system, self.target)
        finally:
            logger.removeHandler(handler)
            logger.setLevel(old)
        return merit, " ".join(r.getMessage() for r in records)

    def test_malformed_result_is_infeasible_and_logged(self):
        class Malformed:
            def __init__(self, system):
                pass

            def trace_spot(self, **kwargs):
                return {}  # no rms_radius at all

        optimizer_module.SpotDiagram = Malformed
        merit, message = self._capture(level=logging.DEBUG)
        self.assertEqual(merit, INFEASIBLE_MERIT)
        self.assertIn("no usable spot", message)

    def test_genuine_exception_is_infeasible_and_logged_with_the_reason(self):
        class Boom:
            def __init__(self, system):
                pass

            def trace_spot(self, **kwargs):
                raise RuntimeError("geometry blew up")

        optimizer_module.SpotDiagram = Boom
        merit, message = self._capture()
        self.assertEqual(merit, INFEASIBLE_MERIT)
        self.assertIn("geometry blew up", message)

    def test_the_two_failures_are_told_apart_by_the_log(self):
        """The point of the fix: same merit, different explanation."""
        messages = []
        for exc in (None, RuntimeError("geometry blew up")):

            class Fake:
                def __init__(self, system):
                    pass

                def trace_spot(self, **kwargs):
                    if exc is None:
                        return {}
                    raise exc

            optimizer_module.SpotDiagram = Fake
            messages.append(self._capture(level=logging.DEBUG)[1])

        self.assertNotEqual(messages[0], messages[1])
        self.assertIn("no usable spot", messages[0])
        self.assertIn("geometry blew up", messages[1])

    def test_mtf_failure_is_also_logged(self):
        original = optimizer_module.WavefrontSensor
        self.addCleanup(setattr, optimizer_module, "WavefrontSensor", original)

        class Boom:
            def __init__(self, system):
                pass

            def get_pupil_wavefront(self, *args, **kwargs):
                raise ValueError("no pupil")

        optimizer_module.WavefrontSensor = Boom
        records = []

        class Handler(logging.Handler):
            def emit(self, record):
                records.append(record)

        logger = logging.getLogger("src.optimizer")
        handler = Handler()
        logger.addHandler(handler)
        try:
            merit = MeritFunction._eval_mtf(self.system, _target("mtf"))
        finally:
            logger.removeHandler(handler)
        self.assertEqual(merit, INFEASIBLE_MERIT)
        self.assertIn("no pupil", " ".join(r.getMessage() for r in records))


class TestHealthyEvaluationUnchanged(unittest.TestCase):
    def setUp(self):
        self.system = _system()

    def test_rms_spot_merit_is_finite_and_positive(self):
        merit = MeritFunction._eval_rms_spot(self.system, _target("rms_spot_radius"))
        self.assertNotEqual(merit, INFEASIBLE_MERIT)
        self.assertGreater(merit, 0.0)

    def test_mtf_merit_is_finite(self):
        merit = MeritFunction._eval_mtf(self.system, _target("mtf"))
        self.assertNotEqual(merit, INFEASIBLE_MERIT)

    def test_dispatch_covers_every_documented_metric(self):
        expected = {
            "spherical_aberration",
            "coma",
            "astigmatism",
            "chromatic_aberration",
            "focal_length",
            "system_length",
            "rms_spot_radius",
            "mtf",
        }
        self.assertEqual(set(MeritFunction._TARGET_DISPATCH), expected)
        for kind, evaluator in MeritFunction._TARGET_DISPATCH.items():
            with self.subTest(metric=kind):
                self.assertTrue(callable(evaluator))

    def test_rms_and_mtf_dispatch_entries_still_run(self):
        for kind in ("rms_spot_radius", "mtf"):
            with self.subTest(metric=kind):
                merit = MeritFunction._TARGET_DISPATCH[kind](self.system, _target(kind))
                self.assertIsInstance(merit, float)
                self.assertNotEqual(merit, INFEASIBLE_MERIT)

    def test_numpy_guard_is_consulted_for_mtf(self):
        """NUMPY_AVAILABLE is read directly now, not via globals()."""
        original = optimizer_module.NUMPY_AVAILABLE
        optimizer_module.NUMPY_AVAILABLE = False
        try:
            merit = MeritFunction._eval_mtf(self.system, _target("mtf"))
        finally:
            optimizer_module.NUMPY_AVAILABLE = original
        self.assertEqual(merit, INFEASIBLE_MERIT)


if __name__ == "__main__":
    unittest.main()
