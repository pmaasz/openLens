"""Regression: a tolerance run must not touch the user's live design.

``MonteCarloAnalyzer`` applies random tolerance changes **in place** on the
system it is given, from a QThread, while the main thread keeps drawing,
refreshing and saving the same object.

``_as_system`` handed it the *live* assembly, so:

- an edit saved during a run could write a perturbed design to SQLite;
- the restore was a plain call rather than a ``try/finally``, so an exception
  from ``_apply_value`` or from the unguarded ``trace_spot`` left the design
  perturbed and the next save persisted that.

The optimisation worker already deep-copied; the tolerancing workers did not.

These tests check the property that matters: the caller's design is bit-for-bit
unchanged by a run, and unchanged even when the run hits an error.
"""

import unittest

from openlens.lens import Lens
from openlens.optical_system import OpticalSystem


def _assembly():
    """A small two-element assembly with alignment worth preserving."""
    system = OpticalSystem(name="Live Assembly")
    crown = Lens(
        name="Crown",
        radius_of_curvature_1=60.0,
        radius_of_curvature_2=-60.0,
        thickness=6.0,
        diameter=30.0,
        refractive_index=1.52,
    )
    flint = Lens(
        name="Flint",
        radius_of_curvature_1=-60.0,
        radius_of_curvature_2=-200.0,
        thickness=4.0,
        diameter=30.0,
        refractive_index=1.62,
    )
    system.add_lens(crown, air_gap_before=0.0)
    system.add_lens(flint, air_gap_before=2.0)
    return system


def _radii(system):
    return [
        (element.lens.radius_of_curvature_1, element.lens.radius_of_curvature_2)
        for element in system.elements
    ]


class TestAsSystemCopiesTheTarget(unittest.TestCase):
    """_as_system must hand the worker its own design."""

    def test_an_assembly_is_copied(self):
        from openlens.gui.tabs.tolerancing_tab import _as_system

        original = _assembly()
        before = _radii(original)

        copied = _as_system(original)

        self.assertIsNot(copied, original, "the live assembly was handed over")
        self.assertEqual(_radii(copied), before)

    def test_a_copy_is_independent(self):
        """Perturbing the copy must not move the original."""
        from openlens.gui.tabs.tolerancing_tab import _as_system

        original = _assembly()
        copied = _as_system(original)

        copied.elements[0].lens.radius_of_curvature_1 = 999.0

        self.assertNotEqual(
            _radii(original)[0][0], 999.0, "the copy shares state with the original"
        )

    def test_a_bare_lens_is_copied(self):
        from openlens.gui.tabs.tolerancing_tab import _as_system

        lens = Lens(name="Solo", radius_of_curvature_1=50.0)

        system = _as_system(lens)

        self.assertIsNot(system.elements[0].lens, lens)

    def test_the_copy_keeps_the_tree_and_flat_list_in_step(self):
        """refresh_references pairs nodes to elements by lens identity."""
        from openlens.gui.tabs.tolerancing_tab import _as_system

        copied = _as_system(_assembly())

        for element, node in zip(copied.elements, copied.root.children):
            self.assertIs(
                element.lens,
                node.element_model,
                "the copy broke the tree/flat-list identity",
            )


class TestMonteCarloLeavesTheDesignAlone(unittest.TestCase):
    """The caller's design must survive a run untouched."""

    def setUp(self):
        from openlens.tolerancing import MonteCarloAnalyzer, ToleranceOperand, ToleranceType

        self.system = _assembly()
        self.before = _radii(self.system)
        self.tolerances = [
            ToleranceOperand(
                param_type=ToleranceType.RADIUS_1,
                element_index=0,
                min_val=-1.0,
                max_val=1.0,
                distribution="uniform",
            )
        ]
        self.analyzer = MonteCarloAnalyzer(self.system, self.tolerances, seed=1)

    def test_a_run_does_not_change_the_system_it_was_given(self):
        self.analyzer.run(num_trials=3)

        self.assertEqual(_radii(self.system), self.before)

    def test_a_failing_trial_does_not_leave_the_design_perturbed(self):
        """The restore has to be in a finally block."""
        from openlens.tolerancing import MonteCarloAnalyzer

        analyzer = MonteCarloAnalyzer(self.system, self.tolerances, seed=1)

        calls = []

        def explode(*args, **kwargs):
            # The nominal evaluation happens before the trial loop; only the
            # trials should blow up.
            calls.append(1)
            if len(calls) > 1:
                raise RuntimeError("the trace blew up")
            return 0.0

        analyzer._spot_rms = explode

        analyzer.run(num_trials=2)

        self.assertEqual(
            _radii(self.system),
            self.before,
            "a failed trial left the design perturbed",
        )


class TestInverseSensitivityLeavesTheDesignAlone(unittest.TestCase):
    """The same guarantee for the inverse-sensitivity worker."""

    def setUp(self):
        from openlens.tolerancing import InverseSensitivityAnalyzer, ToleranceOperand, ToleranceType

        self.system = _assembly()
        self.before = _radii(self.system)
        self.tolerances = [
            ToleranceOperand(
                param_type=ToleranceType.RADIUS_1,
                element_index=0,
                min_val=-1.0,
                max_val=1.0,
                distribution="uniform",
            )
        ]
        self.analyzer = InverseSensitivityAnalyzer(self.system, self.tolerances)

    def test_a_run_does_not_change_the_system_it_was_given(self):
        self.analyzer.calculate_sensitivities()

        self.assertEqual(_radii(self.system), self.before)

    def test_a_failing_trial_does_not_leave_the_design_perturbed(self):
        import openlens.tolerancing as tolerancing_module

        analyzer = self.analyzer

        built = []

        class ExplodingSpotDiagram:
            def __init__(self, *args, **kwargs):
                # The nominal evaluation happens before the trial loop; only
                # the trials should blow up.
                built.append(1)

            def trace_spot(self):
                if len(built) > 1:
                    raise RuntimeError("the trace blew up")
                return {"rms_radius": 0.0}

        original = tolerancing_module.SpotDiagram
        tolerancing_module.SpotDiagram = ExplodingSpotDiagram
        try:
            analyzer.calculate_sensitivities()
        finally:
            tolerancing_module.SpotDiagram = original

        self.assertEqual(
            _radii(self.system),
            self.before,
            "a failed trial left the design perturbed",
        )


if __name__ == "__main__":
    unittest.main()
