"""Regression: encircled energy must not depend on where the plot stops.

``calculate_encircled_energy`` integrated the Airy pattern only up to
``max_radius_um`` and divided by the energy accumulated *there*. The final
sample was therefore forced to 1.0 whatever the true value was, and the
whole curve was rescaled by whatever fraction of the energy happened to fall
inside the plotting extent.

Repro: at the first Airy zero the method reported 0.86594, where the
analytic encircled energy is

    EE(v) = 1 - J0(v)^2 - J1(v)^2

and J0(3.8317) = -0.40276, giving 1 - 0.16222 = **0.83778**.

The extent is a plotting choice. It must not be a normalisation choice.
"""

import unittest

import numpy as np

from openlens.diffraction import DiffractionCalculator

FOCAL_LENGTH_MM = 100.0
APERTURE_MM = 25.0

#: j0 at the first Airy zero, which is the analytic encircled energy there.
J0_FIRST_ZERO = -0.4027593957
EXPECTED_AT_FIRST_ZERO = 1.0 - J0_FIRST_ZERO**2


class TestEncircledEnergySampling(unittest.TestCase):
    """#662: num_points controls the number of returned samples."""

    def setUp(self):
        self.calc = DiffractionCalculator()

    def test_num_points_controls_the_number_of_samples(self):
        for num_points in (10, 100, 1000):
            with self.subTest(num_points=num_points):
                radii, ee = self.calc.encircled_energy(
                    FOCAL_LENGTH_MM,
                    APERTURE_MM,
                    max_radius_um=50.0,
                    num_points=num_points,
                )

                self.assertEqual(len(radii), num_points)
                self.assertEqual(len(ee), num_points)


class TestEncircledEnergyIsAnalytic(unittest.TestCase):
    """The curve is the analytic Airy encircled energy, not a rescaled integral."""

    def setUp(self):
        self.calc = DiffractionCalculator()

    def _value_at_first_zero(self, max_radius_um):
        airy_r = self.calc.airy_disk_radius_um(FOCAL_LENGTH_MM, APERTURE_MM)
        radii, ee = self.calc.encircled_energy(
            FOCAL_LENGTH_MM,
            APERTURE_MM,
            max_radius_um=max_radius_um,
        )
        index = int(np.argmin(np.abs(radii - airy_r)))
        return float(ee[index]), airy_r

    def test_the_value_at_the_first_zero_is_analytic(self):
        """The issue's repro: 0.86594 where the answer is 0.83778."""
        airy_r = self.calc.airy_disk_radius_um(FOCAL_LENGTH_MM, APERTURE_MM)
        value, _ = self._value_at_first_zero(6 * airy_r)

        self.assertAlmostEqual(
            value,
            EXPECTED_AT_FIRST_ZERO,
            delta=1e-3,
            msg=f"EE at the first Airy zero was {value:.5f}, expected "
            f"{EXPECTED_AT_FIRST_ZERO:.5f}",
        )

    def test_the_curve_does_not_depend_on_the_plotting_extent(self):
        """The defect: the answer changed with max_radius_um."""
        airy_r = self.calc.airy_disk_radius_um(FOCAL_LENGTH_MM, APERTURE_MM)
        radii_ref, ee_ref = self.calc.encircled_energy(
            FOCAL_LENGTH_MM, APERTURE_MM, max_radius_um=2 * airy_r, num_points=1000
        )
        radii_wide, ee_wide = self.calc.encircled_energy(
            FOCAL_LENGTH_MM, APERTURE_MM, max_radius_um=20 * airy_r, num_points=1000
        )

        # Compare the overlapping range: where both curves are defined, the
        # encircled energy must agree.
        overlap = radii_wide <= radii_ref[-1]
        self.assertGreater(overlap.sum(), 10, "the ranges barely overlap")

        reference = np.interp(radii_ref[overlap], radii_wide[overlap], ee_wide[overlap])
        self.assertAlmostEqual(
            float(ee_ref[overlap][-1]),
            float(reference[-1]),
            delta=5e-3,
            msg="the encircled energy at a given radius changed with the " "plotting extent",
        )

    def test_the_last_sample_is_not_forced_to_one(self):
        """The old code divided by the energy at max_radius_um."""
        airy_r = self.calc.airy_disk_radius_um(FOCAL_LENGTH_MM, APERTURE_MM)

        radii, ee = self.calc.encircled_energy(FOCAL_LENGTH_MM, APERTURE_MM, max_radius_um=airy_r)

        self.assertLess(
            float(ee[-1]),
            0.999,
            msg="the curve is still forced to 1.0 at the plotting edge",
        )

    def test_the_curve_is_monotonic(self):
        airy_r = self.calc.airy_disk_radius_um(FOCAL_LENGTH_MM, APERTURE_MM)

        radii, ee = self.calc.encircled_energy(
            FOCAL_LENGTH_MM, APERTURE_MM, max_radius_um=10 * airy_r
        )

        self.assertTrue(
            np.all(np.diff(ee) >= -1e-9),
            msg="encircled energy went backwards, which cannot happen",
        )

    def test_it_starts_at_zero(self):
        airy_r = self.calc.airy_disk_radius_um(FOCAL_LENGTH_MM, APERTURE_MM)

        radii, ee = self.calc.encircled_energy(
            FOCAL_LENGTH_MM, APERTURE_MM, max_radius_um=5 * airy_r
        )

        self.assertAlmostEqual(float(ee[0]), 0.0, delta=1e-3)

    def test_it_approaches_one_far_out(self):
        """Encircled energy climbs towards 1, slowly.

        The Airy pattern has wide wings: J ~ sqrt(2/(pi v)), so the fraction
        still outside falls like 1/v. At 30 Airy radii EE is about 0.994, not
        0.999 - asserting 0.999 here would be asserting physics that is false.
        """
        airy_r = self.calc.airy_disk_radius_um(FOCAL_LENGTH_MM, APERTURE_MM)

        _, near = self.calc.encircled_energy(FOCAL_LENGTH_MM, APERTURE_MM, max_radius_um=2 * airy_r)
        _, far = self.calc.encircled_energy(FOCAL_LENGTH_MM, APERTURE_MM, max_radius_um=30 * airy_r)

        self.assertGreater(float(far[-1]), float(near[-1]) + 0.01)
        self.assertGreater(float(far[-1]), 0.99)

    def test_the_default_extent_still_returns_a_usable_curve(self):
        airy_r = self.calc.airy_disk_radius_um(FOCAL_LENGTH_MM, APERTURE_MM)

        radii, ee = self.calc.encircled_energy(FOCAL_LENGTH_MM, APERTURE_MM)

        self.assertAlmostEqual(float(radii[-1]), 5 * airy_r, places=6)
        self.assertEqual(len(radii), len(ee))
        # The documented default is 100 samples; the old code always returned
        # 1000 and ignored the parameter.
        self.assertEqual(len(radii), 100)


class TestEncircledEnergyTracksAperture(unittest.TestCase):
    """A smaller aperture spreads the same energy over a wider disc."""

    def setUp(self):
        self.calc = DiffractionCalculator()

    def test_the_analytic_form_matches_the_airy_disk_convention(self):
        """EE at the first zero is 0.83778 regardless of aperture."""
        for aperture in (10.0, 25.0, 50.0):
            with self.subTest(aperture=aperture):
                airy_r = self.calc.airy_disk_radius_um(FOCAL_LENGTH_MM, aperture)
                radii, ee = self.calc.encircled_energy(
                    FOCAL_LENGTH_MM, aperture, max_radius_um=6 * airy_r
                )
                index = int(np.argmin(np.abs(radii - airy_r)))
                self.assertAlmostEqual(
                    float(ee[index]),
                    EXPECTED_AT_FIRST_ZERO,
                    delta=1e-3,
                    msg=f"aperture {aperture} mm gave "
                    f"{float(ee[index]):.5f} at its first Airy zero",
                )

    def test_a_larger_aperture_has_a_smaller_airy_disk(self):
        airy_small = self.calc.airy_disk_radius_um(FOCAL_LENGTH_MM, 10.0)
        airy_large = self.calc.airy_disk_radius_um(FOCAL_LENGTH_MM, 50.0)

        self.assertLess(airy_large, airy_small)


if __name__ == "__main__":
    unittest.main()
