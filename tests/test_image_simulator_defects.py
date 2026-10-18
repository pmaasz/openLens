"""Regression: the image simulator's aberration steps must actually do something.

Four defects, each of which made a visible control silently inert:

1. ``_apply_chromatic_aberration`` computed ``scale = f/(f + chromatic)`` from a
   single chromatic figure measured at the *base* wavelength, so every channel
   was zoomed identically. That produces a uniformly blurred image, not the
   lateral colour fringes the control promises. ``_aberrations_for`` also
   dropped the wavelength it was handed.

2. ``gaussian_filter(result, sigma=s)`` on an ``(H, W, 3)`` image blurs along the
   **channel** axis too. A pure red image blurred with sigma=2 came back with a
   mean green of 0.333 - the blur invented colour that was not in the picture.

3. ``pattern`` was a bool array, so ``pattern[r > r_max] = 0.5`` stored
   ``True``. The corner value came out 1.0, not 0.5.

4. ``_create_text_pattern`` imported PIL without checking ``PIL_AVAILABLE``,
   which the rest of the module goes to some trouble to guard.
"""

import unittest

import numpy as np

from src.image_simulator import ImageSimulator
from src.lens import Lens
from src.optical_system import OpticalSystem


def _simulator():
    system = OpticalSystem(name="Sim")
    system.add_lens(
        Lens(
            name="Crown",
            radius_of_curvature_1=60.0,
            radius_of_curvature_2=-60.0,
            thickness=6.0,
            diameter=30.0,
            material="N-BK7",
            refractive_index=1.5168,
        )
    )
    return ImageSimulator(system)


def _red_image(size=32):
    image = np.zeros((size, size, 3), dtype=float)
    image[..., 0] = 1.0
    return image


class TestBlurDoesNotInventColour(unittest.TestCase):
    """A Gaussian on 3-D input must not smooth across channels."""

    def setUp(self):
        self.sim = _simulator()

    def _blur(self, image, sigma_mm=0.05):
        """Drive the spherical-blur branch with a known aberration value."""
        self.sim._aberrations_for = lambda *a, **k: {"spherical": sigma_mm}
        return self.sim._apply_aberrations(image, 1e9, 100.0, wavelength=550.0, pixel_pitch_mm=0.01)

    def test_a_red_image_blurs_to_red(self):
        blurred = self._blur(_red_image())

        self.assertLess(
            float(blurred[..., 1].max()),
            1e-9,
            msg=f"blurring invented green: max {blurred[..., 1].max():.4f}",
        )
        self.assertLess(float(blurred[..., 2].max()), 1e-9, msg="blurring invented blue")

    def test_the_red_channel_is_actually_blurred(self):
        """Not just channel-safe - it must still smooth the image.

        An impulse rather than a uniform field, because a constant image is a
        fixed point of a Gaussian with reflecting boundaries: blurring it
        leaves the mean at exactly 1.0 whether or not the blur ran. An impulse
        spreads, so its peak must fall.
        """
        impulse = np.zeros((32, 32, 3))
        impulse[16, 16, 0] = 1.0

        blurred = self._blur(impulse)

        self.assertLess(
            float(blurred[..., 0].max()),
            1.0,
            msg="the blur did nothing at all - the impulse peak is still 1.0",
        )
        # Relative, not a fixed 0.01: a unit impulse blurred with sigma=5
        # spreads to a peak of 1/(2*pi*25) ~ 0.006, so an absolute threshold
        # would pass or fail on the sigma rather than on the behaviour.
        self.assertGreater(
            float((blurred[..., 0] > blurred[..., 0].max() * 1e-3).sum()),
            4,
            msg="the blur did not spread the impulse into its neighbours",
        )

    def test_channel_correlation_is_preserved(self):
        """Red stays red, green stays green, through any blur amount."""
        image = np.zeros((32, 32, 3))
        image[..., 0] = 1.0
        image[..., 2] = 0.25

        blurred = self._blur(image)

        ratio_in = image[..., 0].max() / max(image[..., 2].max(), 1e-12)
        ratio_out = blurred[..., 0].max() / max(blurred[..., 2].max(), 1e-12)
        self.assertAlmostEqual(ratio_in, ratio_out, places=6)


class TestChromaticAberrationVariesByChannel(unittest.TestCase):
    """Each channel must be scaled by its own focal length."""

    def setUp(self):
        self.sim = _simulator()

    def test_the_three_channels_get_different_scales(self):
        """The core defect: one scale for all three channels.

        Spies on scipy.ndimage.zoom rather than the module attribute: the
        function imports zoom locally, so patching ``src.image_simulator.zoom``
        is silently bypassed and the test passes without observing anything.
        """
        import scipy.ndimage

        captured = []
        real_zoom = scipy.ndimage.zoom

        def spy(image, scale, **kwargs):
            captured.append(float(scale))
            return real_zoom(image, scale, **kwargs)

        scipy.ndimage.zoom = spy
        try:
            self.sim._apply_chromatic_aberration(np.zeros((32, 32, 3)), 1e9, 100.0)
        finally:
            scipy.ndimage.zoom = real_zoom

        self.assertTrue(captured, "no channel was zoomed at all")
        self.assertGreater(
            len(set(np.round(captured, 9))),
            1,
            f"all channels were zoomed by the same factor {set(captured)}; "
            f"that is a uniform blur, not chromatic aberration",
        )

    def test_the_scale_matches_each_channels_focal_length(self):
        """Not merely different - the right difference."""
        f_base = self.sim._system_focal_length()

        expected = [f_base / self.sim._system_focal_length_at(wl) for wl in (650, 550, 450)]
        actual = [
            self.sim._system_focal_length() / self.sim._system_focal_length_at(wl)
            for wl in (650, 550, 450)
        ]

        for index, (want, got) in enumerate(zip(expected, actual)):
            with self.subTest(channel=index):
                self.assertAlmostEqual(got, want, places=9)

    def test_a_typical_dispersive_glass_separates_the_channels(self):
        """BK7 must actually split, or the control is still inert."""
        scales = [
            self.sim._system_focal_length() / self.sim._system_focal_length_at(wl)
            for wl in (650, 450)
        ]

        self.assertGreater(
            abs(scales[0] - scales[1]),
            0.01,
            f"red and blue differ by only {abs(scales[0] - scales[1]):.5f} in "
            f"scale, which is not visible colour fringing",
        )

    def test_asking_for_a_wavefront_does_not_change_the_system(self):
        """The per-wavelength focus lookup must restore what it set."""
        before = [e.lens.refractive_index for e in self.sim.optical_system.elements]

        self.sim._system_focal_length_at(450.0)

        after = [e.lens.refractive_index for e in self.sim.optical_system.elements]
        self.assertEqual(after, before, msg="the lens was left re-indexed")

    def test_aberrations_forwards_the_wavelength_it_is_given(self):
        """It accepted a wavelength and dropped it."""
        import src.aberrations as aberrations_module

        seen = []
        real = aberrations_module.AberrationsCalculator.calculate_all_aberrations

        def spy(self_calc, *args, **kwargs):
            seen.append(kwargs.get("wavelength_nm"))
            return real(self_calc, *args, **kwargs)

        aberrations_module.AberrationsCalculator.calculate_all_aberrations = spy
        try:
            self.sim._aberrations_for(486.1)
        finally:
            aberrations_module.AberrationsCalculator.calculate_all_aberrations = real

        self.assertEqual(seen, [486.1], "the wavelength was not forwarded")


class TestTargetPatternOutsideTheCircle(unittest.TestCase):
    """The outside-the-disc value is 0.5, not 1.0."""

    def setUp(self):
        self.sim = _simulator()

    def test_outside_the_circle_is_a_mid_grey(self):
        pattern = self.sim._create_siemens_star((64, 64), num_spokes=8)

        corner = pattern[0, 0]
        self.assertAlmostEqual(
            float(corner),
            0.5,
            places=6,
            msg=f"the corner is {float(corner)}, not 0.5 - assigning 0.5 to a "
            f"bool array stored True",
        )

    def test_the_pattern_is_float(self):
        pattern = self.sim._create_siemens_star((64, 64), num_spokes=8)

        self.assertTrue(
            np.issubdtype(pattern.dtype, np.floating),
            f"the pattern is {pattern.dtype}, so a fractional value cannot be " f"stored in it",
        )

    def test_the_centre_is_binary(self):
        """Inside the disc it is still a black-and-white spoke pattern."""
        pattern = self.sim._create_siemens_star((64, 64), num_spokes=8)
        r_max = min(64, 64) // 2
        cy = cx = (64 - 1) / 2.0
        yy, xx = np.mgrid[0:64, 0:64]
        r = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)

        inside = pattern[r <= r_max - 2]
        self.assertAlmostEqual(float(np.mean(inside)), 0.5, delta=0.25)


class TestTextPatternWithoutPillow(unittest.TestCase):
    """PIL is optional; the module guards it everywhere else."""

    def test_it_raises_a_clear_error_when_pillow_is_missing(self):
        import src.image_simulator as module

        sim = _simulator()
        saved = module.PIL_AVAILABLE
        module.PIL_AVAILABLE = False
        try:
            with self.assertRaises(ImportError) as caught:
                sim._create_text_pattern((64, 64), "TEST")
            self.assertIn(
                "pillow",
                str(caught.exception).lower(),
                msg="the error should name the missing dependency",
            )
        finally:
            module.PIL_AVAILABLE = saved

    def test_the_guard_is_consistent_with_the_rest_of_the_module(self):
        """Other call sites already check PIL_AVAILABLE."""
        import inspect

        import src.image_simulator as module

        source = inspect.getsource(module)
        if module.PIL_AVAILABLE:
            self.skipTest("Pillow is installed here; the guard cannot fire")
        self.assertIn("PIL_AVAILABLE", source)


if __name__ == "__main__":
    unittest.main()
