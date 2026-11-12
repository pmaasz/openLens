#!/usr/bin/env python3
"""The aberration calculator must evaluate the aperture it is asked for.

The Performance tab shows an "Entrance Pupil" value and passes it nowhere: the
calculator always measured the first element's physical diameter, so the
displayed parameter described no calculation. ``AberrationsCalculator`` now
takes an optional entrance pupil, clamped to the clear aperture - the glass
cannot pass more light - and reports the value it actually used.
"""

import unittest

from openlens.aberrations import AberrationsCalculator
from openlens.lens import Lens
from openlens.optical_system import OpticalSystem


def _lens(diameter: float = 25.0) -> Lens:
    return Lens(
        name="Singlet",
        radius_of_curvature_1=100.0,
        radius_of_curvature_2=-100.0,
        thickness=5.0,
        diameter=diameter,
        refractive_index=1.5168,
        material="BK7",
    )


class TestEntrancePupilOverride(unittest.TestCase):
    def setUp(self):
        self.lens = _lens()
        self.full = AberrationsCalculator(self.lens).calculate_all_aberrations()
        self.stopped = AberrationsCalculator(
            self.lens, entrance_pupil_mm=10.0
        ).calculate_all_aberrations()

    def test_the_default_is_the_physical_clear_aperture(self):
        self.assertEqual(self.full["entrance_pupil"], 25.0)

    def test_the_result_reports_the_effective_pupil(self):
        self.assertEqual(self.stopped["entrance_pupil"], 10.0)

    def test_the_f_number_follows_the_entrance_pupil(self):
        self.assertAlmostEqual(self.stopped["f_number"], self.full["f_number"] * 2.5, places=9)

    def test_the_numerical_aperture_follows_the_entrance_pupil(self):
        self.assertAlmostEqual(
            self.stopped["numerical_aperture"],
            self.full["numerical_aperture"] * 0.4,
            places=9,
        )

    def test_the_airy_disk_follows_the_entrance_pupil(self):
        self.assertAlmostEqual(
            self.stopped["airy_disk_diameter"],
            self.full["airy_disk_diameter"] * 2.5,
            places=9,
        )

    def test_the_spherical_aberration_shrinks_with_the_pupil(self):
        """The singlet trace samples the marginal ray at the pupil radius."""
        self.assertLess(abs(self.stopped["spherical"]), abs(self.full["spherical"]))

    def test_a_pupil_wider_than_the_lens_is_clamped(self):
        wide = AberrationsCalculator(self.lens, entrance_pupil_mm=100.0).calculate_all_aberrations()

        self.assertEqual(wide["entrance_pupil"], 25.0)
        self.assertAlmostEqual(wide["f_number"], self.full["f_number"], places=9)

    def test_a_system_target_honours_the_entrance_pupil(self):
        system = OpticalSystem("singlet")
        system.add_lens(_lens())

        stopped = AberrationsCalculator(system, entrance_pupil_mm=5.0).calculate_all_aberrations()

        self.assertEqual(stopped["entrance_pupil"], 5.0)
        self.assertAlmostEqual(
            stopped["f_number"],
            abs(stopped["focal_length"]) / 5.0,
            places=9,
        )

    def test_a_pupil_as_large_as_the_lens_changes_nothing(self):
        same = AberrationsCalculator(self.lens, entrance_pupil_mm=25.0).calculate_all_aberrations()

        self.assertAlmostEqual(same["f_number"], self.full["f_number"], places=9)
        self.assertAlmostEqual(
            same["airy_disk_diameter"], self.full["airy_disk_diameter"], places=9
        )


class TestInvalidEntrancePupil(unittest.TestCase):
    def test_a_non_positive_pupil_raises(self):
        for value in (0.0, -5.0):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    AberrationsCalculator(_lens(), entrance_pupil_mm=value)

    def test_a_non_finite_pupil_raises(self):
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    AberrationsCalculator(_lens(), entrance_pupil_mm=value)

    def test_a_non_numeric_pupil_raises(self):
        with self.assertRaises(ValueError):
            AberrationsCalculator(_lens(), entrance_pupil_mm="wide")


if __name__ == "__main__":
    unittest.main()
