#!/usr/bin/env python3
"""
calculate_psf must return one key set from every branch.

The empty-points branch returned x_axis and no z_axis, while the geometric and
diffraction branches returned y_axis/z_axis/raw_count. `plot_psf` reads
`z_axis`, so it raised:

    KeyError: 'z_axis'

openlens.py calls calculate_psf and plot_psf back to back, so any fully
blocked design turned the PSF dialog into "Failed to calculate PSF: 'z_axis'".

The contract is now asserted in one place (PSF_KEYS / _psf_result) rather
than restated in three return statements.
"""

import unittest

import numpy as np

from src.analysis.psf_mtf import ImageQualityAnalyzer
from src.lens import Lens
from src.optical_system import OpticalSystem


def _analyzer():
    system = OpticalSystem(name="Test")
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


class TestPSFKeyContract(unittest.TestCase):
    def setUp(self):
        self.analyzer = _analyzer()

    def _assert_valid(self, psf, pixels):
        self.assertEqual(set(psf), set(ImageQualityAnalyzer.PSF_KEYS))
        self.assertEqual(psf["image"].shape, (pixels, pixels))
        self.assertEqual(len(psf["y_axis"]), pixels)
        self.assertEqual(len(psf["z_axis"]), pixels)
        self.assertIsInstance(psf["step_size"], float)
        self.assertEqual(len(psf["centroid"]), 2)
        self.assertIsInstance(psf["raw_count"], int)

    def test_empty_branch_returns_the_full_key_set(self):
        """Regression: returned x_axis and no z_axis."""
        self.analyzer.spot_analyzer.trace_spot = lambda **kwargs: {"points": []}
        self._assert_valid(self.analyzer.calculate_psf(pixels=8), 8)

    def test_geometric_branch_returns_the_full_key_set(self):
        self._assert_valid(self.analyzer.calculate_psf(pixels=16), 16)

    def test_diffraction_branch_returns_the_full_key_set(self):
        self._assert_valid(self.analyzer.calculate_psf(pixels=16, use_diffraction=True), 16)

    def test_all_three_branches_agree_exactly(self):
        self.analyzer.spot_analyzer.trace_spot = lambda **kwargs: {"points": []}
        empty = set(self.analyzer.calculate_psf(pixels=8))
        geometric = set(self.analyzer.calculate_psf(pixels=8))
        diffraction = set(self.analyzer.calculate_psf(pixels=8, use_diffraction=True))
        self.assertEqual(empty, geometric)
        self.assertEqual(empty, diffraction)

    def test_no_x_axis_key_remains(self):
        self.analyzer.spot_analyzer.trace_spot = lambda **kwargs: {"points": []}
        self.assertNotIn("x_axis", self.analyzer.calculate_psf(pixels=8))

    def test_result_helper_rejects_an_incomplete_payload(self):
        with self.assertRaises(AssertionError):
            self.analyzer._psf_result(image=np.zeros((4, 4)))

    def test_empty_axes_are_bin_centers_like_the_normal_branch(self):
        """Extent must match what a populated PSF of the same size reports."""
        empty = self.analyzer.calculate_psf(pixels=16, sensor_size_mm=0.1)
        populated = self.analyzer.calculate_psf(pixels=16, sensor_size_mm=0.1)
        self.assertEqual(round(empty["y_axis"][0], 12), round(populated["y_axis"][0], 12))
        self.assertEqual(round(empty["y_axis"][-1], 12), round(populated["y_axis"][-1], 12))

    def test_empty_image_is_all_zeros(self):
        self.analyzer.spot_analyzer.trace_spot = lambda **kwargs: {"points": []}
        psf = self.analyzer.calculate_psf(pixels=8)
        self.assertEqual(float(np.sum(psf["image"])), 0.0)
        self.assertEqual(psf["raw_count"], 0)


class TestPlotPSFConsumesEveryBranch(unittest.TestCase):
    """plot_psf is the consumer that raised; drive all three paths."""

    def setUp(self):
        try:
            import matplotlib

            matplotlib.use("Agg")
        except ImportError:
            self.skipTest("matplotlib not available")
        self.analyzer = _analyzer()

    def _plot(self, psf):
        import matplotlib.pyplot as plt

        from src.analysis.plots import plot_psf

        fig, ax = plt.subplots()
        try:
            plot_psf(ax, psf)
        finally:
            plt.close(fig)

    def test_plot_psf_accepts_an_empty_psf(self):
        """Regression: KeyError 'z_axis'."""
        self.analyzer.spot_analyzer.trace_spot = lambda **kwargs: {"points": []}
        self._plot(self.analyzer.calculate_psf(pixels=8))

    def test_plot_psf_accepts_a_geometric_psf(self):
        self._plot(self.analyzer.calculate_psf(pixels=16))

    def test_plot_psf_accepts_a_diffraction_psf(self):
        self._plot(self.analyzer.calculate_psf(pixels=16, use_diffraction=True))


if __name__ == "__main__":
    unittest.main()
