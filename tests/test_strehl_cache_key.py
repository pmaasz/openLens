"""Regression: the Strehl cache must not outlive the state it was computed for.

``_strehl_state_key`` enumerated a hand-picked subset of the lens: radii,
thickness, diameter, index. Everything else was invisible to it, so a change
that demonstrably alters the pupil trace still returned the previous answer:

    lens.clear_aperture_1 = 5.0
    _strehl_state_key(550, 32)   # unchanged

Clear apertures, parabolic flags and sags, per-surface alignment and the
aperture stop were all missing. Any future field added to Lens would be
missing too, because the key is a list of attributes rather than a snapshot.

The key is now built from the serialized lens state, minus the fields that do
not describe the optics, so new fields are covered without anyone remembering
to add them.
"""

import unittest

from openlens.aberrations import AberrationsCalculator
from openlens.lens import Lens
from openlens.optical_system import OpticalSystem


def _lens(**kwargs):
    options = dict(
        name="Strehl",
        radius_of_curvature_1=60.0,
        radius_of_curvature_2=-60.0,
        thickness=6.0,
        diameter=30.0,
        refractive_index=1.52,
    )
    options.update(kwargs)
    return Lens(**options)


def _system(**kwargs):
    system = OpticalSystem(name="Strehl System")
    system.add_lens(_lens(**kwargs))
    return system


class TestStrehlKeySeesTraceRelevantChanges(unittest.TestCase):
    """Anything that changes the trace has to change the key."""

    def _lens_key(self, lens):
        calculator = AberrationsCalculator(lens)
        return calculator._strehl_state_key(550.0, 32)

    def _system_key(self, system):
        calculator = AberrationsCalculator(system)
        return calculator._strehl_state_key(550.0, 32)

    def test_a_clear_aperture_change_is_seen(self):
        """The issue's repro: clear_aperture_1 = 5 left the key unchanged."""
        lens = _lens()
        before = self._lens_key(lens)

        lens.clear_aperture_1 = 5.0

        self.assertNotEqual(
            before,
            self._lens_key(lens),
            msg="a clear aperture change did not invalidate the Strehl cache",
        )

    def test_a_second_clear_aperture_change_is_seen(self):
        lens = _lens(clear_aperture_2=5.0)
        before = self._lens_key(lens)

        lens.clear_aperture_2 = 4.0

        self.assertNotEqual(before, self._lens_key(lens))

    def test_a_parabolic_flag_change_is_seen(self):
        lens = _lens()
        before = self._lens_key(lens)

        lens.is_parabolic_1 = True
        lens.parabolic_sag_1 = 4.0

        self.assertNotEqual(
            before,
            self._lens_key(lens),
            msg="turning a surface into a paraboloid did not invalidate the cache",
        )

    def test_a_parabolic_sag_change_is_seen(self):
        lens = _lens(is_parabolic_1=True, parabolic_sag_1=4.0)
        before = self._lens_key(lens)

        lens.parabolic_sag_1 = 2.0

        self.assertNotEqual(before, self._lens_key(lens))

    def test_an_alignment_change_is_seen_on_a_system(self):
        system = _system()
        before = self._system_key(system)

        system.elements[0].decenter_y = 0.25

        self.assertNotEqual(
            before,
            self._system_key(system),
            msg="decentering an element did not invalidate the Strehl cache",
        )

    def test_an_aperture_stop_change_is_seen(self):
        system = _system()
        before = self._system_key(system)

        system.aperture_stop_gap = 0
        system.aperture_stop_diameter = 12.0

        self.assertNotEqual(
            before,
            self._system_key(system),
            msg="changing the aperture stop did not invalidate the Strehl cache",
        )

    def test_a_fresnel_change_is_seen(self):
        lens = _lens()
        before = self._lens_key(lens)

        lens.is_fresnel = True

        self.assertNotEqual(before, self._lens_key(lens))

    def test_a_model_glass_change_is_seen(self):
        lens = _lens(model_glass_mode=True, model_nd=1.70)
        before = self._lens_key(lens)

        lens.model_nd = 1.80

        self.assertNotEqual(before, self._lens_key(lens))


class TestStrehlKeyIgnoresNonOpticalChanges(unittest.TestCase):
    """A key that churns on every save is a key that never hits."""

    def _lens_key(self, lens):
        return AberrationsCalculator(lens)._strehl_state_key(550.0, 32)

    def test_renaming_a_lens_does_not_invalidate(self):
        """Renaming changes nothing about the optics."""
        lens = _lens()
        before = self._lens_key(lens)

        lens.name = "Renamed"

        self.assertEqual(
            before,
            self._lens_key(lens),
            msg="renaming a lens invalidated the cache for no optical reason",
        )

    def test_the_key_is_stable_across_identical_construction(self):
        """Two lenses with identical optics must share a cache entry."""
        self.assertEqual(self._lens_key(_lens()), self._lens_key(_lens()))

    def test_the_key_is_stable_when_recomputed(self):
        lens = _lens()
        first = self._lens_key(lens)

        for _ in range(3):
            self.assertEqual(first, self._lens_key(lens))

    def test_different_wavelengths_still_differ(self):
        calculator = AberrationsCalculator(_lens())

        self.assertNotEqual(
            calculator._strehl_state_key(486.1, 32),
            calculator._strehl_state_key(656.3, 32),
        )

    def test_different_grid_sizes_still_differ(self):
        calculator = AberrationsCalculator(_lens())

        self.assertNotEqual(
            calculator._strehl_state_key(550.0, 16),
            calculator._strehl_state_key(550.0, 64),
        )

    def test_a_system_key_is_not_a_lens_key(self):
        """The two must not collide even for the same optics."""
        lens_key = self._lens_key(_lens())
        system_key = AberrationsCalculator(_system())._strehl_state_key(550.0, 32)

        self.assertNotEqual(lens_key, system_key)


class TestStrehlCacheReturnsFreshResults(unittest.TestCase):
    """The user-visible consequence, not just the key."""

    def _strehl(self, calculator):
        lens = getattr(calculator, "lens", None)
        focal_length = lens.calculate_focal_length() if lens is not None else 100.0
        return calculator._calculate_strehl_ratio(
            focal_length or 100.0, wavelength_nm=550.0, grid_size=24
        )

    def test_vignetting_changes_the_reported_strehl(self):
        lens = _lens()
        calculator = AberrationsCalculator(lens)

        open_strehl = self._strehl(calculator)
        lens.clear_aperture_1 = 3.0
        pinched = self._strehl(calculator)

        self.assertNotEqual(
            open_strehl,
            pinched,
            msg="pinching the clear aperture returned the previous Strehl result",
        )

    def test_the_cache_actually_serves_a_repeat_call(self):
        """A key that churns would make the cache useless rather than wrong."""
        lens = _lens()
        calculator = AberrationsCalculator(lens)

        first = self._strehl(calculator)
        second = self._strehl(calculator)

        self.assertEqual(first, second)
        self.assertEqual(len(calculator._strehl_cache), 1)

    def test_a_cache_hit_is_the_same_object(self):
        """Proves the second call came from the cache, not a coincidental retrace."""
        lens = _lens()
        calculator = AberrationsCalculator(lens)

        self._strehl(calculator)
        cached = next(iter(calculator._strehl_cache.values()))

        self.assertIs(self._strehl(calculator), cached)


if __name__ == "__main__":
    unittest.main()
