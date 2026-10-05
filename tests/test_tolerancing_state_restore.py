#!/usr/bin/env python3
"""
Monte Carlo must not contaminate its own nominal reference.

`_capture_state` folded the glass model into one "nd"/"vd" pair, keeping
`model_nd`/`model_vd` only when the element was already in model-glass mode.
A refractive-index tolerance, though, goes through `_ensure_model_glass`,
which flips a fixed-index lens into model-glass mode and perturbs
`model_nd`. The restore put `glass_mode` back to False but left `model_nd`
perturbed, then called `update_refractive_index()` - which takes the
material-database branch and does not reproduce the original fixed index.

So trial N+1 started from trial N's index: a monotone index walk that
contaminated the nominal reference, every percentile, and the reported
yield.
"""

import unittest

from src.lens import Lens
from src.optical_system import OpticalSystem
from src.tolerancing import (
    MonteCarloAnalyzer,
    ToleranceOperand,
    ToleranceType,
    _capture_state,
    _restore_state,
)


def _system(model_glass=False, index=1.5168):
    system = OpticalSystem(name="T")
    lens = Lens(
        name="L",
        radius_of_curvature_1=50.0,
        radius_of_curvature_2=-50.0,
        thickness=5.0,
        diameter=20.0,
        material="N-BK7",
        refractive_index=index,
        model_glass_mode=model_glass,
    )
    system.add_lens(lens)
    return system, lens


def _analyzer(*operands):
    system, lens = _system()
    return (
        MonteCarloAnalyzer(
            system,
            list(operands) or [ToleranceOperand(0, ToleranceType.REFRACTIVE_INDEX, -0.005, 0.005)],
        ),
        lens,
    )


class TestStateRestoreIsExact(unittest.TestCase):
    """The regression: restore must be a true inverse of perturb."""

    def test_fixed_index_lens_returns_to_its_exact_index(self):
        analyzer, lens = _analyzer()
        nominal = _capture_state(analyzer.nominal_system)
        analyzer._apply_tolerances(analyzer.nominal_system)
        _restore_state(analyzer.nominal_system, nominal)
        self.assertEqual(lens.refractive_index, 1.5168)

    def test_repeated_trials_do_not_walk_the_index(self):
        """The visible symptom: a monotone drift, one step per trial."""
        analyzer, lens = _analyzer()
        nominal = _capture_state(analyzer.nominal_system)
        indices = []
        for _ in range(25):
            analyzer._apply_tolerances(analyzer.nominal_system)
            _restore_state(analyzer.nominal_system, nominal)
            indices.append(lens.refractive_index)
        self.assertEqual(set(indices), {1.5168})

    def test_model_glass_attributes_are_restored(self):
        analyzer, lens = _analyzer()
        before = (lens.model_nd, lens.model_vd)
        nominal = _capture_state(analyzer.nominal_system)
        analyzer._apply_tolerances(analyzer.nominal_system)
        _restore_state(analyzer.nominal_system, nominal)
        self.assertEqual((lens.model_nd, lens.model_vd), before)

    def test_glass_mode_is_restored(self):
        analyzer, lens = _analyzer()
        nominal = _capture_state(analyzer.nominal_system)
        analyzer._apply_tolerances(analyzer.nominal_system)
        self.assertTrue(lens.model_glass_mode)  # perturb flips it on
        _restore_state(analyzer.nominal_system, nominal)
        self.assertFalse(lens.model_glass_mode)

    def test_abbe_number_tolerance_also_restores(self):
        """Perturbing vd alone took the same path through the glass mode."""
        analyzer, lens = _analyzer(ToleranceOperand(0, ToleranceType.ABBE_NUMBER, -1.0, 1.0))
        nominal = _capture_state(analyzer.nominal_system)
        before = (lens.refractive_index, lens.model_nd, lens.model_vd)
        for _ in range(5):
            analyzer._apply_tolerances(analyzer.nominal_system)
            _restore_state(analyzer.nominal_system, nominal)
        self.assertEqual((lens.refractive_index, lens.model_nd, lens.model_vd), before)

    def test_model_glass_lens_round_trips(self):
        """An element already in model-glass mode must restore too."""
        system, lens = _system(model_glass=True)
        analyzer = MonteCarloAnalyzer(
            system, [ToleranceOperand(0, ToleranceType.REFRACTIVE_INDEX, -0.005, 0.005)]
        )
        before = (lens.refractive_index, lens.model_nd, lens.model_vd)
        nominal = _capture_state(system)
        for _ in range(5):
            analyzer._apply_tolerances(system)
            _restore_state(system, nominal)
        self.assertEqual((lens.refractive_index, lens.model_nd, lens.model_vd), before)

    def test_geometry_is_still_restored(self):
        analyzer, lens = _analyzer(
            ToleranceOperand(0, ToleranceType.RADIUS_1, -0.5, 0.5),
            ToleranceOperand(0, ToleranceType.THICKNESS, -0.2, 0.2),
        )
        nominal = _capture_state(analyzer.nominal_system)
        before = (lens.radius_of_curvature_1, lens.radius_of_curvature_2, lens.thickness)
        analyzer._apply_tolerances(analyzer.nominal_system)
        _restore_state(analyzer.nominal_system, nominal)
        self.assertEqual(
            (lens.radius_of_curvature_1, lens.radius_of_curvature_2, lens.thickness),
            before,
        )

    def test_air_gaps_are_still_restored(self):
        system, lens = _system()
        system.air_gaps.append(type(system.air_gaps[0])(thickness=3.0)) if system.air_gaps else None
        analyzer = MonteCarloAnalyzer(
            system, [ToleranceOperand(0, ToleranceType.AIR_GAP, -0.5, 0.5)]
        )
        before = [g.thickness for g in system.air_gaps]
        nominal = _capture_state(system)
        analyzer._apply_tolerances(system)
        _restore_state(system, nominal)
        self.assertEqual([g.thickness for g in system.air_gaps], before)


class TestMonteCarloDeterminism(unittest.TestCase):
    def _run(self, seed):
        system, lens = _system()
        analyzer = MonteCarloAnalyzer(
            system,
            [ToleranceOperand(0, ToleranceType.REFRACTIVE_INDEX, -0.005, 0.005)],
            seed=seed,
        )
        results = analyzer.run(num_trials=12)
        return lens.refractive_index, results

    def test_same_seed_gives_identical_results_and_a_clean_nominal(self):
        index_a, results_a = self._run(42)
        index_b, results_b = self._run(42)
        self.assertEqual(results_a, results_b)
        # The nominal must survive the whole run untouched.
        self.assertEqual(index_a, 1.5168)
        self.assertEqual(index_b, 1.5168)

    def test_nominal_index_is_unchanged_after_a_full_run(self):
        index, _ = self._run(7)
        self.assertEqual(index, 1.5168)


if __name__ == "__main__":
    unittest.main()
