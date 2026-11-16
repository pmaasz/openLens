#!/usr/bin/env python3
"""Zernike decomposition of the exit-pupil wavefront (#796)."""

import os
import tempfile
import unittest

try:
    import numpy as np

    HAS_NUMPY = True
except ImportError:
    np = None  # type: ignore[assignment]
    HAS_NUMPY = False

from openlens.analysis.diffraction_psf import WavefrontError
from openlens.analysis.zernike import (
    ZernikeFit,
    fit_zernike_wavefront,
    zernike_terms,
    zernike_value,
)

GRID = 96


def _grid(size=GRID):
    y = np.linspace(-1.0, 1.0, size)
    z = np.linspace(-1.0, 1.0, size)
    Y, Z = np.meshgrid(y, z)
    rho = np.sqrt(Y**2 + Z**2)
    return Y, Z, rho, np.arctan2(Z, Y)


def _wavefront(coefficients, size=GRID, inner_radius=0.0):
    """Build a synthetic wavefront from ``{noll_index: coefficient}``."""
    Y, Z, rho, theta = _grid(size)
    inside = (rho <= 1.0) & (rho >= inner_radius)
    W = np.full_like(Y, np.nan)
    terms = {term.index: term for term in zernike_terms(15)}
    W[inside] = sum(
        coefficient * zernike_value(terms[index], rho[inside], theta[inside])
        for index, coefficient in coefficients.items()
    )
    return WavefrontError(Y, Z, W)


@unittest.skipUnless(HAS_NUMPY, "numpy not available")
class TestZernikeTermSet(unittest.TestCase):
    def test_the_default_noll_set_is_the_first_fifteen_terms(self):
        terms = zernike_terms()
        self.assertEqual([term.index for term in terms], list(range(1, 16)))
        self.assertEqual(
            [(term.n, term.m) for term in terms[:6]],
            [
                (0, 0),
                (1, 1),
                (1, -1),
                (2, 0),
                (2, -2),
                (2, 2),
            ],
        )
        self.assertEqual(terms[3].name, "Defocus")
        self.assertEqual(terms[10].name, "Primary spherical")

    def test_osa_uses_its_own_order_but_the_same_modes(self):
        noll = {(term.n, term.m) for term in zernike_terms(15)}
        osa = zernike_terms(15, "osa")
        self.assertEqual([term.index for term in osa], list(range(1, 16)))
        self.assertEqual({(term.n, term.m) for term in osa}, noll)
        self.assertEqual((osa[1].n, osa[1].m), (1, -1))

    def test_an_unknown_indexing_is_rejected(self):
        with self.assertRaises(ValueError):
            zernike_terms(15, "fringe")

    def test_a_non_positive_term_count_is_rejected(self):
        with self.assertRaises(ValueError):
            zernike_terms(0)


@unittest.skipUnless(HAS_NUMPY, "numpy not available")
class TestSyntheticRecovery(unittest.TestCase):
    def test_each_low_order_mode_is_recovered(self):
        cases = (
            (4, 0.35),  # defocus
            (5, -0.22),  # astigmatism 45/135
            (6, 0.18),  # astigmatism 0/90
            (7, -0.14),  # coma
            (9, 0.11),  # trefoil
            (11, -0.07),  # primary spherical
        )
        for index, coefficient in cases:
            with self.subTest(index=index):
                fit = fit_zernike_wavefront(_wavefront({index: coefficient}))
                self.assertAlmostEqual(fit.coefficients[index - 1], coefficient, places=8)
                self.assertLess(fit.residual_rms, 1e-8)
                self.assertEqual(fit.fitted_fraction, 1.0)

    def test_a_mixed_wavefront_reports_the_expected_terms(self):
        input_coefficients = {4: 0.3, 5: 0.1, 8: -0.2, 11: 0.05}
        fit = fit_zernike_wavefront(_wavefront(input_coefficients))

        for index, coefficient in input_coefficients.items():
            self.assertAlmostEqual(fit.coefficients[index - 1], coefficient, places=8)
        self.assertLess(fit.residual_rms, 1e-8)

    def test_piston_and_tilt_are_removed_by_default(self):
        wavefront = _wavefront({1: 0.4, 2: 0.2, 3: -0.1})
        fit = fit_zernike_wavefront(wavefront)

        self.assertTrue(fit.piston_tilt_removed)
        self.assertAlmostEqual(fit.coefficients[0], 0.0, places=8)
        self.assertAlmostEqual(fit.coefficients[1], 0.0, places=8)
        self.assertAlmostEqual(fit.coefficients[2], 0.0, places=8)
        self.assertLess(fit.residual_rms, 1e-8)

    def test_piston_can_be_kept_when_requested(self):
        fit = fit_zernike_wavefront(_wavefront({1: 0.4}), remove_piston_tilt=False)

        self.assertFalse(fit.piston_tilt_removed)
        self.assertAlmostEqual(fit.coefficients[0], 0.4, places=8)

    def test_vignetted_pupil_has_no_nan_and_reports_its_fraction(self):
        fit = fit_zernike_wavefront(_wavefront({4: 0.3, 5: 0.1}, inner_radius=0.35))

        self.assertEqual(fit.indexing, "noll")
        self.assertTrue(all(np.isfinite(fit.coefficients)))
        self.assertTrue(all(np.isfinite(fit.rms)))
        self.assertTrue(np.isfinite(fit.residual_rms))
        self.assertAlmostEqual(fit.coefficients[3], 0.3, places=6)
        self.assertAlmostEqual(fit.coefficients[4], 0.1, places=6)
        self.assertGreater(fit.fitted_fraction, 0.8)
        self.assertLess(fit.fitted_fraction, 1.0)

    def test_a_fully_blocked_pupil_returns_zeros_not_nan(self):
        Y, Z, _, _ = _grid()
        fit = fit_zernike_wavefront(WavefrontError(Y, Z, np.full_like(Y, np.nan)))

        self.assertIsInstance(fit, ZernikeFit)
        self.assertEqual(fit.fitted_fraction, 0.0)
        self.assertEqual(fit.sample_count, 0)
        self.assertEqual(fit.residual_rms, 0.0)
        self.assertTrue(all(value == 0.0 for value in fit.coefficients))
        self.assertTrue(all(np.isfinite(value) for value in fit.coefficients))

    def test_an_empty_degraded_wavefront_returns_an_empty_fit(self):
        fit = fit_zernike_wavefront(WavefrontError([], [], []))

        self.assertEqual(fit.coefficients, [0.0] * 15)
        self.assertEqual(fit.fitted_fraction, 0.0)

    def test_fitting_does_not_change_the_wavefront(self):
        wavefront = _wavefront({4: 0.3})
        before = np.nan_to_num(wavefront.W, nan=-1.0).copy()

        fit = fit_zernike_wavefront(wavefront)

        np.testing.assert_array_equal(np.nan_to_num(wavefront.W, nan=-1.0), before)
        self.assertTrue(all(np.isfinite(fit.coefficients)))


@unittest.skipUnless(HAS_NUMPY, "numpy not available")
class TestRealWavefront(unittest.TestCase):
    def test_a_traced_doublet_gives_a_finite_decomposition(self):
        from openlens.analysis.diffraction_psf import WavefrontSensor
        from openlens.optical_system import create_doublet

        wavefront = WavefrontSensor(create_doublet()).get_pupil_wavefront(grid_size=24)
        fit = fit_zernike_wavefront(wavefront)

        self.assertGreater(fit.sample_count, 0)
        self.assertGreater(fit.fitted_fraction, 0.5)
        self.assertTrue(all(np.isfinite(fit.coefficients)))
        self.assertTrue(np.isfinite(fit.residual_rms))


class TestZernikePlots(unittest.TestCase):
    @unittest.skipUnless(HAS_NUMPY, "numpy not available")
    def test_bar_chart_and_table_paint_the_fit(self):
        try:
            import matplotlib

            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
        except ImportError:
            self.skipTest("matplotlib not available")

        from openlens.analysis.plots import plot_zernike_bars, plot_zernike_table

        fit = fit_zernike_wavefront(_wavefront({4: 0.3, 5: 0.1}))
        figure, (bars, table) = plt.subplots(1, 2)
        try:
            plot_zernike_bars(bars, fit)
            plot_zernike_table(table, fit)

            self.assertEqual(len(bars.patches), 15)
            self.assertEqual(len(table.tables), 1)
        finally:
            plt.close(figure)


class TestZernikeReport(unittest.TestCase):
    @unittest.skipUnless(HAS_NUMPY, "numpy not available")
    def test_the_report_includes_the_coefficient_table(self):
        from openlens.gui.services.export_service import ExportService
        from openlens.optical_system import create_doublet

        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "report.txt")
            result = ExportService().export_report(
                create_doublet(focal_length=100.0, diameter=25.0), path
            )
            self.assertTrue(result.ok, result.error)
            with open(path) as handle:
                text = handle.read()

        self.assertIn("Zernike Decomposition (waves)", text)
        self.assertIn("Piston/tilt: removed", text)
        self.assertIn("Defocus", text)
        self.assertIn("Primary spherical", text)
        self.assertIn("Residual RMS:", text)


class TestWavefrontDialogWiring(unittest.TestCase):
    @unittest.skipUnless(HAS_NUMPY, "numpy not available")
    def test_the_dialog_draws_the_map_bars_and_table(self):
        try:
            import matplotlib

            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            from openlens.__main__ import OpenLensWindow
        except ImportError as exc:
            self.skipTest(f"GUI plotting unavailable: {exc}")

        from openlens.optical_system import create_doublet

        class Window:
            _perf_tab = None
            captured = None

            def _active_target(self):
                return create_doublet(focal_length=100.0, diameter=25.0)

            def _ensure_system(self, target):
                return target

            def _open_analysis_dialog(self, title, compute, plot, columns=1):
                self.captured = (title, compute, plot, columns)

        window = Window()
        OpenLensWindow._on_show_wavefront(window)
        title, compute, plot, columns = window.captured

        self.assertEqual(title, "Wavefront Analysis")
        self.assertEqual(columns, 3)
        wavefront, fit = compute()
        self.assertIsNotNone(fit)

        figure, axes = plt.subplots(1, 3)
        try:
            plot(tuple(axes), (wavefront, fit))
            self.assertTrue(axes[0].images)
            self.assertEqual(len(axes[1].patches), len(fit.terms))
            self.assertEqual(len(axes[2].tables), 1)
        finally:
            plt.close(figure)


if __name__ == "__main__":
    unittest.main()
