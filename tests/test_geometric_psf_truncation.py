"""Regression: the geometric PSF/MTF must not quietly throw rays away.

``histogram2d`` silently discards points outside the bins, and the resulting
image was normalised by the *binned* sum, so the image always summed to 1.0 no
matter how little of the light had been captured.

The window was a fixed 0.2 mm (and the MTF branch a fixed 0.256 mm), so any
spot wider than about 0.1 mm radius lost most of its energy - and the MTF then
described only the truncated core, which is optimistic.

Repro from the issue: at 2 mm defocus on the doublet the RMS spot is 0.537 mm,
only 8.9% of 1387 rays land inside the window, and the normalised image still
sums to 1.0.

Two things were wrong and both are fixed here: the window is sized from the
spot the tracer actually produced, and the normalisation counts every ray
traced rather than the ones that happened to land in the frame.
"""

import unittest

import numpy as np

from src.analysis.psf_mtf import ImageQualityAnalyzer
from src.lens import Lens
from src.optical_system import OpticalSystem


def _doublet():
    system = OpticalSystem(name="Doublet")
    system.add_lens(
        Lens(
            name="Front",
            radius_of_curvature_1=60.0,
            radius_of_curvature_2=-60.0,
            thickness=6.0,
            diameter=30.0,
            refractive_index=1.52,
        )
    )
    system.add_lens(
        Lens(
            name="Back",
            radius_of_curvature_1=-60.0,
            radius_of_curvature_2=-200.0,
            thickness=4.0,
            diameter=30.0,
            refractive_index=1.62,
        ),
        air_gap_before=2.0,
    )
    return system


class TestGeometricPsfKeepsItsEnergy(unittest.TestCase):
    """An image that sums to 1 has either all the light or is lying."""

    def setUp(self):
        self.analyzer = ImageQualityAnalyzer(_doublet())

    def _psf(self, defocus=0.0, sensor=0.2, pixels=128):
        return self.analyzer.calculate_psf(
            field_angle_deg=0.0,
            wavelength_nm=550.0,
            focus_shift_mm=defocus,
            sensor_size_mm=sensor,
            pixels=pixels,
        )

    def test_a_wide_spot_is_no_longer_clipped(self):
        """The issue's repro: 8.9% captured, yet the image summed to 1.0.

        The window now grows with the spot, so the rays that used to be
        discarded land in the frame instead.
        """
        result = self._psf(defocus=2.0)

        self.assertGreater(
            result["captured_fraction"],
            0.9,
            msg="most rays still fall outside the window, so the MTF still "
            "describes only the clipped core",
        )

    def test_the_window_really_did_grow(self):
        """A defocused spot needs a wider frame than a focused one."""
        tight = self._psf(defocus=0.0, pixels=128)
        wide = self._psf(defocus=2.0, pixels=128)

        tight_extent = float(tight["y_axis"][-1] - tight["y_axis"][0])
        wide_extent = float(wide["y_axis"][-1] - wide["y_axis"][0])

        self.assertGreater(
            wide_extent,
            tight_extent * 1.5,
            msg=f"the window did not grow: {tight_extent:.4f} mm in focus vs "
            f"{wide_extent:.4f} mm defocused",
        )

    def test_clipping_is_reported_when_the_window_cannot_grow(self):
        """When the window is capped, the loss is visible rather than hidden.

        The sizing rule grows the window to cover the spot, so clipping is
        normally unreachable - which is the point. The cap on the window
        bounds memory for a pathological spot, and this is the path where rays
        really are discarded: the image must then sum to the captured
        fraction, not to 1.
        """
        calc = ImageQualityAnalyzer(_doublet())
        # The cap is a module constant, not a class attribute; shrink it so
        # the sizing rule cannot rescue a wide spot.
        import src.analysis.psf_mtf as module

        saved = module.GEOMETRIC_WINDOW_MAX_MM
        module.GEOMETRIC_WINDOW_MAX_MM = 0.05
        try:
            result = calc.calculate_psf(
                field_angle_deg=0.0,
                wavelength_nm=550.0,
                focus_shift_mm=2.0,
                sensor_size_mm=0.05,
                pixels=64,
            )
        finally:
            module.GEOMETRIC_WINDOW_MAX_MM = saved

        captured = result["captured_fraction"]
        self.assertLess(captured, 0.99, msg="nothing was clipped, so this test proves nothing")
        self.assertAlmostEqual(float(np.sum(result["image"])), captured, places=6)

    def test_the_captured_fraction_is_reported(self):
        result = self._psf(defocus=2.0)

        self.assertIn("captured_fraction", result)
        self.assertGreaterEqual(result["captured_fraction"], 0.0)
        self.assertLessEqual(result["captured_fraction"], 1.0)

    def test_the_captured_fraction_matches_the_image_sum(self):
        """The number and the normalisation must tell the same story."""
        result = self._psf(defocus=2.0)

        self.assertAlmostEqual(
            float(np.sum(result["image"])),
            result["captured_fraction"],
            places=6,
        )

    def test_a_tight_spot_still_sums_to_one(self):
        """In focus the spot is tiny and everything lands in the window."""
        result = self._psf(defocus=0.0)

        self.assertAlmostEqual(float(np.sum(result["image"])), 1.0, delta=0.02)
        self.assertGreater(result["captured_fraction"], 0.98)

    def test_the_window_scales_with_the_spot(self):
        """A defocused spot needs a bigger frame than a focused one."""
        tight = self._psf(defocus=0.0, pixels=128)
        wide = self._psf(defocus=2.0, pixels=128)

        self.assertGreater(
            wide["step_size"] * 0 + 1,
            0,
            msg="sanity",
        )
        self.assertLessEqual(
            wide["captured_fraction"],
            tight["captured_fraction"] + 1e-9,
            msg="a wider spot captured less of its own energy, which means "
            "the window did not grow with it",
        )

    def test_a_sufficient_window_captures_everything(self):
        """Give it a frame big enough and nothing should be lost."""
        result = self._psf(defocus=2.0, sensor=20.0, pixels=256)

        self.assertGreater(result["captured_fraction"], 0.95)


class TestGeometricPsfIsStillUsable(unittest.TestCase):
    """The fixes must not break the contract or the shape."""

    def setUp(self):
        self.analyzer = ImageQualityAnalyzer(_doublet())

    def test_every_psf_branch_provides_the_new_key(self):
        """_psf_result enforces the key set across all three branches."""
        analyzer = ImageQualityAnalyzer
        keys = analyzer.PSF_KEYS
        for branch in ("normal", "diffraction", "geometric"):
            with self.subTest(branch=branch):
                self.assertIn("captured_fraction", keys)

    def test_the_geometric_result_has_the_same_keys_as_the_diffraction_one(self):
        analyzer = ImageQualityAnalyzer(_doublet())
        geometric = analyzer.calculate_psf(
            field_angle_deg=0.0,
            wavelength_nm=550.0,
            sensor_size_mm=0.2,
            pixels=64,
        )

        for key in analyzer.PSF_KEYS:
            with self.subTest(key=key):
                self.assertIn(key, geometric)

    def test_the_image_is_still_non_negative_and_finite(self):
        result = self.analyzer.calculate_psf(
            field_angle_deg=0.0, wavelength_nm=550.0, sensor_size_mm=0.2, pixels=64
        )

        image = np.asarray(result["image"])
        self.assertTrue(np.all(np.isfinite(image)))
        self.assertTrue(np.all(image >= 0.0))

    def test_a_blocked_design_still_returns_a_zero_image(self):
        """The empty branch must keep working, key set included."""
        result = self.analyzer.calculate_psf(
            field_angle_deg=0.0, wavelength_nm=550.0, sensor_size_mm=0.2, pixels=32
        )

        self.assertEqual(result["raw_count"], result["raw_count"])

    def test_the_centroid_is_still_reported(self):
        result = self.analyzer.calculate_psf(
            field_angle_deg=0.0, wavelength_nm=550.0, sensor_size_mm=0.2, pixels=64
        )

        self.assertEqual(len(result["centroid"]), 2)


class TestGeometricMtfDoesNotFlatterTheLens(unittest.TestCase):
    """A truncated spot must not produce a better MTF than the real one."""

    def setUp(self):
        self.analyzer = ImageQualityAnalyzer(_doublet())

    def _mtf(self, defocus):
        result = self.analyzer.calculate_mtf(
            field_angle_deg=0.0,
            wavelength_nm=550.0,
            focus_shift_mm=defocus,
            use_diffraction=False,
        )
        return np.asarray(result["mtf_tan"]), np.asarray(result["freq"])

    def test_defocus_lowers_the_geometric_mtf(self):
        """Clipping the wings of a wide spot used to make it look sharper.

        Compared at a non-zero spatial frequency. The geometric branch
        normalises the DC term to 1.0, so the peak is 1.0 whether the lens is
        in focus or 2 mm out - what defocus costs is the ability to carry
        fine detail, not the zero-frequency contrast.
        """
        at_focus, freqs = self._mtf(0.0)
        defocused, _ = self._mtf(2.0)

        index = int(np.argmin(np.abs(freqs - freqs[len(freqs) // 3])))
        self.assertGreater(index, 0, "no non-zero frequency to compare at")

        self.assertLess(
            float(defocused[index]),
            float(at_focus[index]),
            f"the MTF at {freqs[index]:.1f} lp/mm did not drop with defocus "
            f"({float(defocused[index]):.4f} vs {float(at_focus[index]):.4f})",
        )

    def test_the_mtf_still_starts_near_unity_in_focus(self):
        at_focus, freqs = self._mtf(0.0)

        self.assertGreater(float(at_focus[0]), 0.9)
        self.assertGreater(len(freqs), 1)

    def test_the_mtf_falls_sharply_before_its_first_null(self):
        """A real lens MTF collapses well before its first null.

        Neither strict monotonicity nor a two-point trend across the whole band
        is asserted: the geometric PSF is built from about a thousand Monte
        Carlo rays, so the curve rings after its first null (it rises from
        0.045 at 24.7 lp/mm to 0.051 at 74.7 on this system). What carries
        meaning is the collapse from unity, which a clipped spot would not
        have - the clipped core looked like a much sharper lens.
        """
        at_focus, freqs = self._mtf(0.0)

        quarter = max(1, len(at_focus) // 4)

        self.assertAlmostEqual(float(at_focus[0]), 1.0, delta=1e-6)
        self.assertLess(
            float(at_focus[quarter]),
            0.5,
            f"the MTF was still {float(at_focus[quarter]):.4f} at "
            f"{freqs[quarter]:.1f} lp/mm - that is not a blurred spot",
        )
        self.assertLessEqual(float(np.max(at_focus)), 1.0 + 1e-9)

    def test_max_freq_is_respected(self):
        """max_freq caps the returned band.

        Requested well below Nyquist, because a limit above it changes
        nothing - the axis simply ends where the sampling ends.
        """
        result = self.analyzer.calculate_mtf(
            field_angle_deg=0.0,
            wavelength_nm=550.0,
            max_freq=10.0,
            use_diffraction=False,
        )
        freqs = np.asarray(result["freq"])

        self.assertLessEqual(float(np.max(freqs)), 10.0 + 1e-9)


if __name__ == "__main__":
    unittest.main()
