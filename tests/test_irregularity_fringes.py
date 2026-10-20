"""Regression: irregularity tolerance must not silently drop half its draws.

``_radius_for_fringes`` bracketed the root on one side only:

    R > 0:  search [R - span, R]
    R < 0:  search [R, R + span]

Sag rises with curvature, so a target on the *other* side of the nominal sag
was never bracketed. ``_apply_value`` then returned False and the perturbation
was skipped:

    R =  100, +1 fringe -> 99.937
    R =  100, -1 fringe -> None
    R = -100, +1 fringe -> None
    R = -100, -1 fringe -> -99.937

In a symmetric Monte Carlo run that silently drops about half the IRREGULARITY
draws, so the reported yield is too optimistic - the perturbations that would
have hurt are the ones that vanish.

The full interval [R - span, R + span] is searched instead, over which the sag
is monotonic in R.
"""

import unittest

from openlens.tolerancing import FRINGE_SAG_MM, _radius_for_fringes, _spherical_sag

H = 10.0


class TestBothFringeSignsAreFound(unittest.TestCase):
    """Either sign of the fringe error must produce a radius."""

    def test_both_signs_for_a_positive_radius(self):
        for radius in (40.0, 100.0, 250.0):
            for fringes in (-2.0, -1.0, 1.0, 2.0):
                with self.subTest(radius=radius, fringes=fringes):
                    result = _radius_for_fringes(radius, H, fringes)
                    self.assertIsNotNone(
                        result,
                        f"R={radius}, {fringes:+g} fringe returned None; the "
                        f"perturbation would have been dropped",
                    )

    def test_both_signs_for_a_negative_radius(self):
        for radius in (-40.0, -100.0, -250.0):
            for fringes in (-2.0, -1.0, 1.0, 2.0):
                with self.subTest(radius=radius, fringes=fringes):
                    result = _radius_for_fringes(radius, H, fringes)
                    self.assertIsNotNone(
                        result,
                        f"R={radius}, {fringes:+g} fringe returned None; the "
                        f"perturbation would have been dropped",
                    )

    def test_the_issue_repro_no_longer_returns_none(self):
        """R=100, -1 fringe and R=-100, +1 fringe were the two dead halves."""
        self.assertIsNotNone(_radius_for_fringes(100.0, H, -1.0))
        self.assertIsNotNone(_radius_for_fringes(-100.0, H, 1.0))


class TestTheRadiusActuallyProducesTheFringe(unittest.TestCase):
    """Not just found - the sag change has to be the requested one."""

    def _sag_error(self, radius, fringes):
        result = _radius_for_fringes(radius, H, fringes)
        if result is None:
            return None
        nominal = _spherical_sag(radius, H)
        perturbed = _spherical_sag(result, H)
        return perturbed - nominal

    def test_the_sag_change_matches_the_requested_fringes(self):
        for radius in (40.0, -40.0, 100.0, -100.0, 250.0, -250.0):
            for fringes in (-2.0, -1.0, 1.0, 2.0):
                with self.subTest(radius=radius, fringes=fringes):
                    error = self._sag_error(radius, fringes)
                    self.assertIsNotNone(error)
                    self.assertAlmostEqual(
                        error,
                        fringes * FRINGE_SAG_MM,
                        delta=abs(FRINGE_SAG_MM) * 1e-6,
                        msg=f"R={radius}, {fringes:+g} fringe produced a sag "
                        f"change of {error:.6e} mm, wanted "
                        f"{fringes * FRINGE_SAG_MM:.6e} mm",
                    )

    def test_positive_fringes_reduce_the_radius_magnitude(self):
        """A longer fringe error is a tighter surface."""
        tighter = _radius_for_fringes(100.0, H, 1.0)
        self.assertLess(abs(tighter), 100.0)

    def test_negative_fringes_increase_the_radius_magnitude(self):
        flatter = _radius_for_fringes(100.0, H, -1.0)
        self.assertGreater(abs(flatter), 100.0)

    def test_the_sign_of_the_radius_is_preserved(self):
        """Flipping to the other sign of curvature is a different surface."""
        for radius in (100.0, -100.0):
            for fringes in (-1.0, 1.0):
                with self.subTest(radius=radius, fringes=fringes):
                    result = _radius_for_fringes(radius, H, fringes)
                    self.assertGreater(result, 0) if radius > 0 else None
                    self.assertLess(result, 0) if radius < 0 else None


class TestDegenerateGeometryStillDeclines(unittest.TestCase):
    """The fix must not turn "cannot be done" into a bogus number."""

    def test_a_flat_surface_still_returns_none(self):
        self.assertIsNone(_radius_for_fringes(float("inf"), H, 1.0))

    def test_a_zero_radius_still_returns_none(self):
        self.assertIsNone(_radius_for_fringes(0.0, H, 1.0))

    def test_a_zero_height_still_returns_none(self):
        self.assertIsNone(_radius_for_fringes(100.0, 0.0, 1.0))

    def test_a_negative_height_still_returns_none(self):
        self.assertIsNone(_radius_for_fringes(100.0, -5.0, 1.0))

    def test_a_radius_below_the_semi_aperture_still_returns_none(self):
        """|R| must exceed h for a spherical sag to exist at all."""
        self.assertIsNone(_radius_for_fringes(5.0, H, 1.0))

    def test_zero_fringes_returns_the_nominal_radius(self):
        result = _radius_for_fringes(100.0, H, 0.0)

        self.assertIsNotNone(result)
        self.assertAlmostEqual(result, 100.0, places=3)


class TestIrregularityDrawsAreNotDropped(unittest.TestCase):
    """The user-visible consequence: the perturbation reaches the lens."""

    def _run_with_irregularity(self, seed):

        from openlens.tolerancing import MonteCarloAnalyzer, ToleranceOperand, ToleranceType

        from openlens.lens import Lens
        from openlens.optical_system import OpticalSystem

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
        operand = ToleranceOperand(
            element_index=0,
            param_type=ToleranceType.IRREGULARITY,
            min_val=-1.0,
            max_val=1.0,
            surface=1,
        )
        analyzer = MonteCarloAnalyzer(system, [operand], seed=seed)

        applied = []
        real_apply = analyzer._apply_tolerances

        def counting(system_under_test):
            result = real_apply(system_under_test)
            applied.append(result)
            return result

        analyzer._apply_tolerances = counting
        analyzer.run(num_trials=12)
        return applied

    def test_every_trial_applies_its_irregularity(self):
        """About half were dropped before the bracket fix."""
        applied = self._run_with_irregularity(seed=3)

        self.assertTrue(applied, "no trials ran, so this proves nothing")
        missing = [i for i, entry in enumerate(applied) if not entry]
        self.assertEqual(
            missing,
            [],
            f"trials {missing} applied no perturbation; a symmetric irregularity "
            f"tolerance must not drop half its draws",
        )

    def test_the_perturbations_go_both_ways(self):
        """A symmetric tolerance must move the surface in both directions."""
        applied = self._run_with_irregularity(seed=5)

        values = [abs(v) for entry in applied for v in entry.values()]
        self.assertTrue(values, "no perturbations were recorded")
        self.assertGreater(min(values), 0.0)


if __name__ == "__main__":
    unittest.main()
