"""Through-focus MTF and RMS-spot sweeps."""

import csv
import math
import os
import tempfile
import unittest

from openlens.analysis.through_focus import (
    ThroughFocusAnalyzer,
    _defocus_values,
    _validate_frequencies,
)
from openlens.fields import normalize_fields
from openlens.lens import Lens
from openlens.optical_system import OpticalSystem

try:
    from matplotlib.figure import Figure

    MATPLOTLIB_AVAILABLE = True
except ImportError:  # pragma: no cover - environment guard
    MATPLOTLIB_AVAILABLE = False


def _slow_singlet() -> OpticalSystem:
    """A small-aperture singlet, so the spot minimum sits at paraxial focus."""
    system = OpticalSystem(name="Through-focus singlet")
    system.add_lens(
        Lens(
            radius_of_curvature_1=103.0,
            radius_of_curvature_2=-103.0,
            thickness=5.0,
            diameter=1.0,
            material="BK7",
        )
    )
    return system


class TestDefocusGrid(unittest.TestCase):
    def test_grid_is_inclusive_and_ordered(self):
        values = _defocus_values(-0.2, 0.2, 0.05)

        self.assertEqual(values[0], -0.2)
        self.assertEqual(values[-1], 0.2)
        self.assertEqual(len(values), 9)

    def test_reversed_endpoints_are_sorted(self):
        values = _defocus_values(0.2, -0.2, 0.1)

        self.assertEqual(values, [-0.2, -0.1, 0.0, 0.1, 0.2])

    def test_partial_last_step_keeps_the_requested_stop(self):
        values = _defocus_values(-0.2, 0.15, 0.1)

        self.assertEqual(values, [-0.2, -0.1, 0.0, 0.1, 0.15])

    def test_non_positive_step_raises(self):
        for step in (0.0, -0.01):
            with self.subTest(step=step):
                with self.assertRaises(ValueError):
                    _defocus_values(-0.1, 0.1, step)

    def test_non_finite_step_raises(self):
        with self.assertRaises(ValueError):
            _defocus_values(-0.1, 0.1, float("nan"))


class TestFrequencyValidation(unittest.TestCase):
    def test_duplicates_are_removed(self):
        values = _validate_frequencies([10.0, 10.0, 20.0])

        self.assertEqual(values, (10.0, 20.0))

    def test_empty_list_raises(self):
        with self.assertRaises(ValueError):
            _validate_frequencies([])

    def test_non_positive_frequency_raises(self):
        for frequency in (0.0, -5.0):
            with self.subTest(frequency=frequency):
                with self.assertRaises(ValueError):
                    _validate_frequencies([frequency])

    def test_non_finite_frequency_raises(self):
        with self.assertRaises(ValueError):
            _validate_frequencies([float("inf")])


class TestThroughFocusSweep(unittest.TestCase):
    def test_sweep_returns_one_value_per_step_and_frequency(self):
        result = ThroughFocusAnalyzer(_slow_singlet()).sweep(
            defocus_start_mm=-0.1,
            defocus_stop_mm=0.1,
            defocus_step_mm=0.05,
            frequencies_lp_per_mm=(10.0, 20.0),
            field_angles_deg=[0.0],
        )

        self.assertEqual(result.defocus_mm, [-0.1, -0.05, 0.0, 0.05, 0.1])
        field = result.fields[0]
        self.assertEqual(field.field_angle_deg, 0.0)
        for frequency in (10.0, 20.0):
            self.assertEqual(len(field.mtf_tangential[frequency]), 5)
            self.assertEqual(len(field.mtf_sagittal[frequency]), 5)
        self.assertEqual(len(field.spot_rms_um), 5)

    def test_best_focus_agrees_with_paraxial_focus(self):
        result = ThroughFocusAnalyzer(_slow_singlet()).sweep(
            defocus_start_mm=-0.2,
            defocus_stop_mm=0.2,
            defocus_step_mm=0.05,
            frequencies_lp_per_mm=(20.0,),
            field_angles_deg=[0.0],
        )

        self.assertIsNotNone(result.best_focus_mm)
        self.assertLessEqual(abs(result.best_focus_mm), 0.05)

    def test_the_spot_grows_away_from_best_focus(self):
        result = ThroughFocusAnalyzer(_slow_singlet()).sweep(
            defocus_start_mm=-0.2,
            defocus_stop_mm=0.2,
            defocus_step_mm=0.05,
            frequencies_lp_per_mm=(20.0,),
            field_angles_deg=[0.0],
        )

        spot = result.fields[0].spot_rms_um
        self.assertLess(spot[4], spot[0])
        self.assertLess(spot[4], spot[-1])

    def test_model_fields_are_used_when_none_are_given(self):
        system = _slow_singlet()
        system.fields = normalize_fields([0.0, 2.0])

        result = ThroughFocusAnalyzer(system).sweep(
            defocus_start_mm=-0.05,
            defocus_stop_mm=0.05,
            defocus_step_mm=0.05,
            frequencies_lp_per_mm=(10.0,),
        )

        self.assertEqual([field.field_angle_deg for field in result.fields], [0.0, 2.0])

    def test_empty_frequencies_raise(self):
        with self.assertRaises(ValueError):
            ThroughFocusAnalyzer(_slow_singlet()).sweep(
                frequencies_lp_per_mm=(),
                field_angles_deg=[0.0],
            )

    def test_the_sweep_does_not_modify_the_plane_analyses(self):
        system = _slow_singlet()
        before_wavelength = system.elements[0].lens.wavelength
        before_index = system.elements[0].lens.refractive_index

        ThroughFocusAnalyzer(system).sweep(
            defocus_start_mm=-0.05,
            defocus_stop_mm=0.05,
            defocus_step_mm=0.05,
            frequencies_lp_per_mm=(10.0,),
            field_angles_deg=[0.0],
        )

        self.assertEqual(system.elements[0].lens.wavelength, before_wavelength)
        self.assertEqual(system.elements[0].lens.refractive_index, before_index)


class TestThroughFocusCsv(unittest.TestCase):
    def setUp(self):
        self.result = ThroughFocusAnalyzer(_slow_singlet()).sweep(
            defocus_start_mm=-0.1,
            defocus_stop_mm=0.1,
            defocus_step_mm=0.05,
            frequencies_lp_per_mm=(10.0, 20.0),
            field_angles_deg=[0.0, 1.0],
        )
        handle, self.path = tempfile.mkstemp(suffix=".csv")
        os.close(handle)

    def tearDown(self):
        if os.path.exists(self.path):
            os.unlink(self.path)

    def test_rows_cover_every_field_step_and_frequency(self):
        rows = self.result.rows()

        self.assertEqual(len(rows), 2 * 5 * 2)
        self.assertEqual(
            set(rows[0]),
            {
                "field_angle_deg",
                "defocus_mm",
                "wavelength_nm",
                "frequency_lp_per_mm",
                "mtf_tangential",
                "mtf_sagittal",
                "spot_rms_um",
            },
        )

    def test_csv_contains_the_flattened_rows(self):
        self.result.to_csv(self.path)

        with open(self.path, newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))

        self.assertEqual(len(rows), len(self.result.rows()))
        self.assertEqual(float(rows[0]["defocus_mm"]), -0.1)
        self.assertEqual(float(rows[0]["frequency_lp_per_mm"]), 10.0)
        self.assertTrue(math.isfinite(float(rows[0]["mtf_tangential"])))


@unittest.skipUnless(MATPLOTLIB_AVAILABLE, "matplotlib not available")
class TestThroughFocusPlot(unittest.TestCase):
    def test_plot_draws_mtf_and_spot_panels(self):
        from openlens.analysis.plots import plot_through_focus

        result = ThroughFocusAnalyzer(_slow_singlet()).sweep(
            defocus_start_mm=-0.1,
            defocus_stop_mm=0.1,
            defocus_step_mm=0.05,
            frequencies_lp_per_mm=(10.0,),
            field_angles_deg=[0.0],
        )
        figure = Figure()
        axes = (figure.add_subplot(121), figure.add_subplot(122))

        plot_through_focus(axes, result)

        self.assertEqual(axes[0].get_title(), "MTF vs defocus")
        self.assertEqual(axes[1].get_title(), "RMS spot vs defocus")
        self.assertGreater(len(axes[0].lines), 0)
        self.assertGreater(len(axes[1].lines), 0)


if __name__ == "__main__":
    unittest.main()
