#!/usr/bin/env python3
"""
ImageSimulator must work against a real OpticalSystem.

The simulator probed for ``effective_focal_length(wavelength)``,
``get_aberrations(wavelength)`` and ``aperture_diameter``. OpticalSystem has
**none** of them - it exposes ``get_system_focal_length``, and aberrations
come from ``AberrationsCalculator``. So all three probes failed and every
physical effect was silently skipped: only cos^4 vignetting survived, f/# was
ignored, and the reported magnification was always -1.0.

The only tests used a MockOpticalSystem that supplied ``aperture_diameter``,
which is why this went unnoticed.
"""

import unittest

import numpy as np

from src.lens import Lens
from src.optical_system import OpticalSystem
from src.image_simulator import ImageSimulator


def _system(r1=50.0, r2=-50.0, diameter=20.0, thickness=5.0, n=1.5):
    system = OpticalSystem(name="Sim")
    system.add_lens(
        Lens(
            name="L",
            radius_of_curvature_1=r1,
            radius_of_curvature_2=r2,
            thickness=thickness,
            diameter=diameter,
            refractive_index=n,
        )
    )
    return system


def _point(shape=(64, 64)):
    img = np.zeros(shape + (3,))
    img[shape[0] // 2, shape[1] // 2] = 1.0
    return img


class TestImageSimulatorRealAPI(unittest.TestCase):
    def setUp(self):
        self.system = _system()
        self.sim = ImageSimulator(self.system)

    def test_real_system_has_none_of_the_probed_attributes(self):
        """The premise: the probes could never succeed."""
        for attribute in (
            "effective_focal_length",
            "get_aberrations",
            "aperture_diameter",
        ):
            self.assertFalse(
                hasattr(self.system, attribute),
                f"OpticalSystem unexpectedly has {attribute}",
            )

    def test_focal_length_comes_from_the_real_api(self):
        self.assertAlmostEqual(
            self.sim._system_focal_length(),
            self.system.get_system_focal_length(),
            places=9,
        )

    def test_image_distance_uses_the_lens_equation(self):
        """It used to return object_distance unchanged, i.e. ignore f."""
        f = self.system.get_system_focal_length()
        object_distance = 1000.0
        expected = 1.0 / (1.0 / f - 1.0 / object_distance)
        self.assertAlmostEqual(
            self.sim._calculate_image_distance(object_distance, 587.6),
            expected,
            places=6,
        )
        # The old behaviour was to echo the object distance back.
        self.assertNotAlmostEqual(
            self.sim._calculate_image_distance(object_distance, 587.6),
            object_distance,
            places=3,
        )

    def test_magnification_is_not_always_minus_one(self):
        result = self.sim.simulate_image(np.random.rand(32, 32, 3), 1000.0)
        self.assertNotAlmostEqual(result["magnification"], -1.0, places=3)

    def test_entrance_pupil_uses_the_first_element(self):
        self.assertAlmostEqual(
            self.sim._entrance_pupil_diameter(),
            self.system.elements[0].lens.diameter,
            places=9,
        )

    def test_aberrations_are_retrieved(self):
        aberrations = self.sim._aberrations_for(587.6)
        self.assertIn("spherical", aberrations)
        self.assertIn("coma", aberrations)
        self.assertIn("astigmatism", aberrations)

    def test_aberration_blur_is_applied(self):
        img = _point()
        self.assertFalse(
            np.array_equal(self.sim._apply_aberrations(img, 100.0, 103.0, 587.6), img),
            "aberration blur was silently skipped",
        )

    def test_diffraction_spot_scales_with_f_number(self):
        """A high f-number system must produce a wider spot than a fast one."""
        fast = ImageSimulator(_system(r1=50.0, r2=-50.0, diameter=20.0))
        slow = ImageSimulator(_system(r1=200.0, r2=-1000.0, diameter=50.0))
        fast_f_number = fast._system_focal_length() / fast._entrance_pupil_diameter()
        slow_f_number = slow._system_focal_length() / slow._entrance_pupil_diameter()
        self.assertLess(fast_f_number, slow_f_number)

        img = _point()
        fast_spread = (fast._apply_diffraction(img, 587.6, 0.01) > 1e-9).sum()
        slow_spread = (slow._apply_diffraction(img, 587.6, 0.01) > 1e-9).sum()
        self.assertGreater(slow_spread, fast_spread)

    def test_chromatic_path_runs(self):
        img = _point()
        out = self.sim._apply_chromatic_aberration(img, 100.0, 103.0)
        self.assertEqual(out.shape, img.shape)

    def test_unsupported_target_fails_loudly(self):
        """Not via hasattr: an unsupported target must be an explicit error."""
        with self.assertRaises(TypeError):
            ImageSimulator(object())._system_focal_length()


if __name__ == "__main__":
    unittest.main()
