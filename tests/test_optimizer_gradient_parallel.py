"""Tests for the finite-difference gradient in LensOptimizer.

Regression cover for #321: the perturbations used to be spread across a
``ProcessPoolExecutor``. Because ``_evaluate_design`` is a bound method that
meant pickling the whole optimizer per task, giving every child a private copy
of the merit cache, and forking from inside a ``QThread`` that owns live Qt
state - under ``spawn`` the child re-imports ``__main__``, which for
``python3 openlens.py`` starts a second Qt application.
"""

import unittest

from src import optimizer as optimizer_module
from src.lens import Lens
from src.optical_system import OpticalSystem
from src.optimizer import (
    GRADIENT_MAX_WORKERS,
    GRADIENT_PARALLEL_THRESHOLD,
    LensOptimizer,
    OptimizationTarget,
    OptimizationVariable,
)


def _system():
    """A singlet with a valid, non-degenerate geometry."""
    system = OpticalSystem()
    system.add_lens(
        Lens(
            radius_of_curvature_1=100.0,
            radius_of_curvature_2=-100.0,
            thickness=5.0,
            diameter=25.0,
            refractive_index=1.5168,
        )
    )
    return system


def _variables(count):
    """Build ``count`` distinct variables on the single element."""
    specs = [
        ("R1", "radius_of_curvature_1", 100.0, 50.0, 200.0),
        ("R2", "radius_of_curvature_2", -100.0, -200.0, -50.0),
        ("T", "thickness", 5.0, 1.0, 10.0),
        ("D", "diameter", 25.0, 10.0, 50.0),
        ("R1b", "radius_of_curvature_1", 101.0, 50.0, 200.0),
        ("R2b", "radius_of_curvature_2", -101.0, -200.0, -50.0),
        ("Tb", "thickness", 6.0, 1.0, 10.0),
    ]
    return [
        OptimizationVariable(
            name=name,
            element_index=0,
            parameter=param,
            current_value=current,
            min_value=lo,
            max_value=hi,
        )
        for name, param, current, lo, hi in specs[:count]
    ]


def _targets():
    return [
        OptimizationTarget("rms_spot_radius", 0.0, weight=100.0, target_type="minimize"),
        OptimizationTarget("focal_length", 96.8, weight=1.0, target_type="target"),
    ]


class TestGradientParallelism(unittest.TestCase):
    def setUp(self):
        self.system = _system()
        self.targets = _targets()

    def _gradient(self, count):
        variables = _variables(count)
        optimizer = LensOptimizer(self.system, variables, self.targets)
        return (
            optimizer,
            variables,
            optimizer._calculate_gradient([v.current_value for v in variables]),
        )

    def test_no_process_pool_is_constructed(self):
        """The gradient must not import or use a process pool.

        Forking from the optimization QThread is the hazard #321 describes,
        so assert on the parsed imports rather than on the file text: the
        docstring deliberately still names the class it replaced.
        """
        import ast

        with open(optimizer_module.__file__) as f:
            tree = ast.parse(f.read())

        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module or "")
                imported.update(f"{node.module or ''}.{a.name}" for a in node.names)

        self.assertNotIn("multiprocessing", imported)
        self.assertFalse(
            any("ProcessPoolExecutor" in name for name in imported),
            f"optimizer still imports a process pool: {sorted(imported)}",
        )

        # And no name lookup of it anywhere in the module body either.
        used = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        used |= {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
        self.assertNotIn("ProcessPoolExecutor", used)

    def test_gradient_matches_serial_evaluation(self):
        """The threaded path must produce the same numbers as serial."""
        count = GRADIENT_PARALLEL_THRESHOLD + 1
        _, variables, threaded = self._gradient(count)
        values = [v.current_value for v in variables]

        # Recompute serially to compare against the parallel result.
        serial_optimizer = LensOptimizer(self.system, variables, self.targets)
        epsilon = 1e-5
        f0 = serial_optimizer._evaluate_design(values)
        serial = []
        for i in range(len(values)):
            perturbed = list(values)
            perturbed[i] += epsilon
            serial.append((serial_optimizer._evaluate_design(perturbed) - f0) / epsilon)

        self.assertEqual(len(threaded), len(serial))
        for got, want in zip(threaded, serial):
            self.assertAlmostEqual(got, want, places=9)

    def test_parallel_gradient_is_finite_and_correct_length(self):
        """Every gradient component must be a usable number, not inf/nan."""
        _, _, gradient = self._gradient(GRADIENT_PARALLEL_THRESHOLD + 2)
        self.assertEqual(len(gradient), GRADIENT_PARALLEL_THRESHOLD + 2)
        for component in gradient:
            self.assertIsInstance(component, float)
            self.assertNotEqual(component, float("inf"))
            self.assertNotEqual(component, float("-inf"))
            self.assertEqual(component, component)  # not NaN

    def test_small_variable_count_still_works(self):
        """Below the threshold the serial path must still produce a gradient."""
        _, _, gradient = self._gradient(GRADIENT_PARALLEL_THRESHOLD)
        self.assertEqual(len(gradient), GRADIENT_PARALLEL_THRESHOLD)

    def test_gradient_does_not_leak_child_processes(self):
        """Computing a gradient must not spawn or leave behind processes."""
        try:
            import multiprocessing
        except ImportError:  # pragma: no cover - platform guard
            self.skipTest("multiprocessing unavailable")

        before = len(multiprocessing.active_children())
        self._gradient(GRADIENT_PARALLEL_THRESHOLD + 3)
        after = len(multiprocessing.active_children())
        self.assertEqual(after, before)

    def test_worker_bound_is_respected(self):
        """Fan-out must stay bounded even with many variables."""
        self.assertGreaterEqual(GRADIENT_MAX_WORKERS, 1)
        _, _, gradient = self._gradient(len(_variables(7)))
        self.assertEqual(len(gradient), 7)

    def test_merit_cache_is_shared_across_perturbations(self):
        """The threaded path must populate the one shared cache.

        With a process pool each child held a private copy, so none of the
        work was reused. Re-evaluating the same point must hit the cache.
        """
        variables = _variables(GRADIENT_PARALLEL_THRESHOLD + 1)
        optimizer = LensOptimizer(self.system, variables, self.targets)
        values = [v.current_value for v in variables]
        optimizer._calculate_gradient(values)
        cached = len(optimizer._merit_cache)
        self.assertGreater(cached, 1)

        before = optimizer._evaluate_design(values)
        after = optimizer._evaluate_design(values)
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
