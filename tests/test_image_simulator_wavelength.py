#!/usr/bin/env python3
"""The simulated image plane must follow the wavelength.

``_calculate_image_distance`` accepted a wavelength and then used the design
index, so the C line and the F line produced the same image plane for a
dispersive singlet. The Nyquist ratio divided the ring energy by the DC bin,
so a blank image returned ``nan`` with a ``RuntimeWarning``.
"""

import unittest
import warnings

import numpy as np

from openlens.constants import WAVELENGTH_C_LINE, WAVELENGTH_F_LINE, WAVELENGTH_GREEN
from openlens.image_simulator import ImageSimulator
from openlens.lens import Lens
from openlens.optical_system import OpticalSystem

OBJECT_DISTANCE = 500.0


def _singlet() -> OpticalSystem:
    system = OpticalSystem("singlet")
    system.add_lens(
        Lens(
            radius_of_curvature_1=100.0,
            radius_of_curvature_2=-100.0,
            refractive_index=1.5168,
            thickness=5.0,
            diameter=25.0,
            material="BK7",
        )
    )
    return system


class TestChromaticImageDistance(unittest.TestCase):
    def setUp(self):
        self.simulator = ImageSimulator(_singlet())

    def _lens_equation(self, wavelength: float) -> float:
        f = self.simulator._system_focal_length_at(wavelength)
        return abs(1.0 / (1.0 / f - 1.0 / OBJECT_DISTANCE))

    def test_the_red_and_blue_image_planes_differ(self):
        """A BK7 singlet focuses C and F at different distances."""
        red = self.simulator._calculate_image_distance(OBJECT_DISTANCE, WAVELENGTH_C_LINE)
        blue = self.simulator._calculate_image_distance(OBJECT_DISTANCE, WAVELENGTH_F_LINE)

        self.assertNotAlmostEqual(red, blue, places=3)
        self.assertGreater(red, blue)

    def test_the_image_distance_is_the_lens_equation_at_that_wavelength(self):
        for wavelength in (WAVELENGTH_C_LINE, WAVELENGTH_GREEN, WAVELENGTH_F_LINE):
            with self.subTest(wavelength=wavelength):
                actual = self.simulator._calculate_image_distance(OBJECT_DISTANCE, wavelength)
                self.assertAlmostEqual(actual, self._lens_equation(wavelength), places=6)

    def test_the_design_index_is_restored_after_the_measurement(self):
        before = [e.lens.refractive_index for e in self.simulator.optical_system.elements]

        self.simulator._calculate_image_distance(OBJECT_DISTANCE, WAVELENGTH_F_LINE)

        after = [e.lens.refractive_index for e in self.simulator.optical_system.elements]
        self.assertEqual(before, after)

    def test_simulate_image_reports_the_chromatic_plane(self):
        image = np.zeros((32, 32))

        red = self.simulator.simulate_image(image, OBJECT_DISTANCE, wavelength=WAVELENGTH_C_LINE)
        blue = self.simulator.simulate_image(image, OBJECT_DISTANCE, wavelength=WAVELENGTH_F_LINE)

        self.assertNotAlmostEqual(red["image_distance"], blue["image_distance"], places=3)
        self.assertAlmostEqual(red["magnification"], -red["image_distance"] / OBJECT_DISTANCE)


class TestBlankImageNyquist(unittest.TestCase):
    def setUp(self):
        self.simulator = ImageSimulator(_singlet())

    def test_a_blank_image_scores_zero_without_a_warning(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            ratio = self.simulator._calculate_nyquist_spectral_ratio(np.zeros((64, 64)))

        self.assertEqual(ratio, 0.0)
        runtime = [w for w in caught if issubclass(w.category, RuntimeWarning)]
        self.assertEqual(runtime, [])

    def test_a_delta_image_still_scores_above_zero(self):
        image = np.zeros((64, 64))
        image[32, 32] = 1.0

        self.assertGreater(self.simulator._calculate_nyquist_spectral_ratio(image), 0.0)


if __name__ == "__main__":
    unittest.main()
