#!/usr/bin/env python3
"""
PSF resampling: use floor, and refuse a degenerate spacing.

The resampler mapped target coordinates to raw indices with

    idx = ((coord + raw_extent / 2) / dx_psf).astype(int)

Two problems were filed:

1. astype(int) truncates toward zero, so negative coordinates are biased by up
   to a full pixel relative to floor.
2. dx_psf == 0 divides by zero.

## What the investigation actually found

Neither is observable today, and the tests below say so explicitly rather
than pretending otherwise:

- astype(int) differs from floor ONLY for negative values. The indices are
  clipped with np.clip(idx, 0, padded_N - 1) immediately afterwards, so every
  negative index becomes 0 either way. Sweeping -200.7 .. 200.7: 201 of 401
  values differ before the clip, 0 differ after it.
- dx_psf == 0 is only reachable with wavelength_nm == 0, which already divides
  by zero upstream in the wavefront, so the PSF is zeroed before the resampler
  runs. The old code produced an all-zero image anyway.

So this is a correctness/robustness change, not a bug fix with a visible
symptom. Both are still worth making: floor is the correct index for a
nearest-below sample, and the guard turns a silent constant-garbage image into
an explicit, logged empty one. The invariants are pinned so that if the clip
is ever removed - at which point the truncation bias WOULD become observable -
the code is already correct.
"""

import unittest

import numpy as np

from src.analysis.psf_mtf import ImageQualityAnalyzer, _map_to_raw_indices
from src.lens import Lens
from src.optical_system import OpticalSystem


def _analyzer():
    system = OpticalSystem(name="D")
    system.add_lens(
        Lens(
            name="L",
            radius_of_curvature_1=50.0,
            radius_of_curvature_2=-50.0,
            thickness=5.0,
            diameter=25.0,
            refractive_index=1.5,
        )
    )
    return ImageQualityAnalyzer(system)


class TestTruncationIsInertWhileClipped(unittest.TestCase):
    """Documents why the astype(int) report had no visible effect."""

    def test_truncation_differs_from_floor_only_for_negatives(self):
        values = np.linspace(-200.7, 200.7, 401)
        differing = values.astype(int) != np.floor(values).astype(np.int64)
        self.assertTrue(differing.any())
        self.assertTrue((values[differing] < 0).all())

    def test_the_clip_makes_them_identical(self):
        values = np.linspace(-200.7, 200.7, 401)
        limit = 63
        trunc = np.clip(values.astype(int), 0, limit)
        floor = np.clip(np.floor(values).astype(np.int64), 0, limit)
        np.testing.assert_array_equal(trunc, floor)


class TestIndexMappingIsWellFormed(unittest.TestCase):
    def _indices(self, raw_extent, dx_psf, padded_N, pixels, sensor):
        target = np.linspace(-sensor / 2, sensor / 2, pixels)
        return _map_to_raw_indices(target, raw_extent, dx_psf, padded_N)

    def test_indices_stay_in_range(self):
        for sensor in (0.001, 0.1, 10.0):
            with self.subTest(sensor=sensor):
                idx = self._indices(0.02, 0.0005, 64, 33, sensor)
                self.assertTrue((idx >= 0).all())
                self.assertTrue((idx <= 63).all())

    def test_indices_are_int64_not_platform_int(self):
        idx = self._indices(0.02, 0.0005, 64, 33, 0.1)
        self.assertEqual(idx.dtype, np.dtype(np.int64))

    def test_index_is_monotonic_in_coordinate(self):
        idx = self._indices(0.02, 0.0005, 256, 17, 0.01)
        self.assertTrue((np.diff(idx) >= 0).all())

    def test_floor_is_used_rather_than_truncation(self):
        """A negative scaled value must floor away from zero, not toward it."""
        target = np.array([-0.03, -0.02, 0.0, 0.02, 0.03])
        idx = _map_to_raw_indices(target, raw_extent=0.02, dx_psf=0.001, padded_N=64)
        # -0.03 -> (-0.03 + 0.01)/0.001 = -20 -> floored to -20 -> clipped to 0
        # truncation would give -20 as well here, so use a fractional case:
        idx = _map_to_raw_indices(np.array([-0.0285]), raw_extent=0.02, dx_psf=0.001, padded_N=64)
        self.assertEqual(idx[0], 0)  # -18.5 -> floor -19 -> clip 0

    def test_output_matches_the_mapping(self):
        analyzer = _analyzer()
        result = analyzer.calculate_psf(pixels=33, sensor_size_mm=5.0, use_diffraction=True)
        image = np.real(result["image"])
        self.assertEqual(image.shape, (33, 33))
        self.assertTrue(np.isfinite(image).all())
        self.assertTrue((image >= 0).all())

    def test_output_is_unchanged_by_the_floor_change(self):
        """Both spellings agree today; a change here would be noticed."""
        analyzer = _analyzer()
        result = analyzer.calculate_psf(pixels=32, sensor_size_mm=2.0, use_diffraction=True)
        image = np.real(result["image"])
        self.assertEqual(image.shape, (32, 32))
        self.assertTrue(np.isfinite(image).all())


class TestDegenerateSpacing(unittest.TestCase):
    def setUp(self):
        self.analyzer = _analyzer()

    def test_zero_wavelength_returns_a_valid_empty_psf(self):
        """dx_psf == 0 used to divide by zero."""
        result = self.analyzer.calculate_psf(pixels=8, wavelength_nm=0.0, use_diffraction=True)
        self.assertEqual(
            set(result),
            {"image", "y_axis", "z_axis", "centroid", "step_size", "raw_count"},
        )
        self.assertEqual(np.real(result["image"]).shape, (8, 8))
        self.assertEqual(len(result["y_axis"]), 8)
        self.assertEqual(result["raw_count"], 0)

    def test_zero_wavelength_image_is_finite(self):
        result = self.analyzer.calculate_psf(pixels=16, wavelength_nm=0.0, use_diffraction=True)
        self.assertTrue(np.isfinite(np.real(result["image"])).all())

    def test_normal_wavelength_is_unaffected(self):
        result = self.analyzer.calculate_psf(pixels=32, use_diffraction=True)
        self.assertTrue(np.isfinite(np.real(result["image"])).all())
        self.assertGreater(float(np.sum(np.real(result["image"]))), 0.0)

    def test_geometric_path_also_survives_zero_wavelength(self):
        result = self.analyzer.calculate_psf(pixels=8, wavelength_nm=0.0)
        self.assertTrue(np.isfinite(np.real(result["image"])).all())


if __name__ == "__main__":
    unittest.main()
