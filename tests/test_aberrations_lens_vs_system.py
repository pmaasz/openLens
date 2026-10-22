#!/usr/bin/env python3
"""
A lens and the one-element system that holds it must report the same numbers.

``AberrationsCalculator`` reported ``field_curvature`` and ``distortion`` in
different quantities depending on how it was constructed: the lens path
returned the Petzval *radius* (n * f) and a distortion of exactly zero "by
construction", while the system path returned the traced tangential focus
shift and the traced distortion. The same optics, a hundred-fold different
numbers, and a GUI label that only fitted the analytic one.
"""

import unittest

from openlens.aberrations import AberrationsCalculator
from openlens.lens import Lens
from openlens.optical_system import OpticalSystem


def _lens():
    return Lens(
        name="Test",
        radius_of_curvature_1=100.0,
        radius_of_curvature_2=-100.0,
        refractive_index=1.5168,
        thickness=5.0,
        diameter=25.0,
        material="BK7",
    )


class TestLensAndSystemAgree(unittest.TestCase):
    """The same optics must give the same numbers."""

    def _both(self, field_angle_deg=5.0):
        lens = _lens()
        system = OpticalSystem(name="One element")
        system.add_lens(_lens())
        return (
            AberrationsCalculator(lens).calculate_all_aberrations(field_angle_deg=field_angle_deg),
            AberrationsCalculator(system).calculate_all_aberrations(
                field_angle_deg=field_angle_deg
            ),
        )

    def test_the_field_curvature_agrees(self):
        """The lens path must report the traced focus shift, not a radius"""
        lens_data, system_data = self._both()

        self.assertAlmostEqual(
            lens_data["field_curvature"],
            system_data["field_curvature"],
            places=9,
            msg="the lens and the one-element system disagree on the field curvature",
        )

    def test_the_distortion_agrees(self):
        """The lens path must report the traced distortion"""
        lens_data, system_data = self._both()

        self.assertAlmostEqual(
            lens_data["distortion"],
            system_data["distortion"],
            places=9,
            msg="the lens and the one-element system disagree on the distortion",
        )

    def test_the_field_curvature_is_a_focus_shift(self):
        """The reported value is millimetres of focus shift, not a radius"""
        lens_data, _system_data = self._both()

        # A 100 mm lens at 5 degrees: the tangential focus moves by a fraction
        # of a millimetre. The Petzval radius would be ~150 mm.
        self.assertLess(abs(lens_data["field_curvature"]), 10.0)

    def test_the_analytic_helpers_keep_their_own_names(self):
        """The Petzval radius and the third-order distortion are separate"""
        lens = _lens()
        calc = AberrationsCalculator(lens)
        focal_length = lens.calculate_focal_length()

        self.assertAlmostEqual(
            calc._calculate_petzval_radius(focal_length),
            lens.refractive_index * focal_length,
            places=6,
        )
        self.assertEqual(
            calc._calculate_third_order_distortion(focal_length, field_angle_deg=10.0),
            0.0,
        )


if __name__ == "__main__":
    unittest.main()
