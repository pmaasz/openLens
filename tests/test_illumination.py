#!/usr/bin/env python3
"""Relative illumination and vignetting analysis (#790)."""

import inspect
import math
import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication

    PYSIDE_AVAILABLE = True
except ImportError:  # pragma: no cover - environment guard
    PYSIDE_AVAILABLE = False

from openlens.analysis.illumination import RelativeIlluminationAnalyzer
from openlens.constants import NM_TO_MM, WAVELENGTH_GREEN
from openlens.fields import launch_field_ray
from openlens.lens import Lens
from openlens.optical_system import OpticalSystem, as_system, create_doublet
from openlens.ray_tracer import SystemRayTracer3D


def _singlet(**overrides):
    values = dict(
        name="singlet",
        radius_of_curvature_1=100.0,
        radius_of_curvature_2=-100.0,
        thickness=5.0,
        diameter=50.0,
        refractive_index=1.5,
    )
    values.update(overrides)
    return Lens(**values)


def _stopped_assembly():
    """Stop behind a thick first element so off-axis bundles shift on it.

    The stop sits at the air gap, which starts at the first element's rear
    vertex; the 40 mm thickness is what puts it far enough from the entrance
    aperture for a field to visibly vignette.
    """
    system = OpticalSystem(name="stopped")
    system.add_lens(_singlet(thickness=40.0, diameter=120.0))
    system.add_lens(_singlet(radius_of_curvature_1=-300.0, diameter=120.0), air_gap_before=20.0)
    system.set_aperture_stop(0, 20.0)
    return system


class TestOnAxisNormalization(unittest.TestCase):
    def test_on_axis_is_one_hundred_percent_for_a_lens(self):
        result = RelativeIlluminationAnalyzer(_singlet()).analyze(
            fields=[0.0, 5.0], grid_size=8, entrance_pupil_mm=2.0
        )

        self.assertTrue(result.valid)
        self.assertEqual(result.on_axis_throughput, 1.0)
        self.assertEqual(result.fields[0].relative_illumination, 1.0)
        self.assertEqual(result.fields[0].geometric_throughput, 1.0)
        self.assertEqual(result.fields[0].natural_falloff, 1.0)
        self.assertEqual(result.fields[0].lost_fraction, 0.0)
        self.assertEqual(result.fields[0].image_height_mm, 0.0)

    def test_on_axis_is_one_hundred_percent_for_an_assembly(self):
        result = RelativeIlluminationAnalyzer(create_doublet()).analyze(
            fields=[0.0, 10.0], grid_size=8
        )

        self.assertEqual(result.fields[0].relative_illumination, 1.0)
        self.assertEqual(result.on_axis_throughput, 1.0)

    def test_the_default_pupil_is_the_axial_entrance_pupil(self):
        # create_doublet(diameter=50) is an f/2 cemented doublet. Its edge is
        # not usable, so the sampled pupil must stop short of the full 50 mm
        # rather than normalising against rays that cannot exist.
        result = RelativeIlluminationAnalyzer(create_doublet(diameter=50.0)).analyze(
            fields=[0.0, 10.0, 20.0], grid_size=8
        )

        self.assertGreater(result.entrance_pupil_mm, 0.0)
        self.assertLess(result.entrance_pupil_mm, 50.0)
        for entry in result.fields:
            self.assertLessEqual(entry.geometric_throughput, 1.0, entry)


class TestNaturalFalloff(unittest.TestCase):
    def test_an_unclipped_field_follows_the_cosine_fourth_law(self):
        system = OpticalSystem(name="wide")
        system.add_lens(_singlet())
        result = RelativeIlluminationAnalyzer(system).analyze(
            fields=[0.0, 5.0, 10.0], grid_size=8, entrance_pupil_mm=2.0
        )

        # A 2 mm bundle on a 50 mm aperture passes untouched, so the whole
        # falloff is the natural cosine-fourth term of the traced chief ray.
        for entry in result.fields[1:]:
            self.assertEqual(entry.geometric_throughput, 1.0)
            self.assertEqual(entry.lost_fraction, 0.0)
            expected = _chief_direction_x(system, entry.field_angle_deg) ** 4
            self.assertAlmostEqual(entry.natural_falloff, expected, places=12)
            self.assertAlmostEqual(entry.relative_illumination, expected, places=12)
            self.assertLess(entry.relative_illumination, 1.0)

    def test_the_falloff_matches_cosine_fourth_within_a_percent(self):
        system = OpticalSystem(name="wide")
        system.add_lens(_singlet())
        result = RelativeIlluminationAnalyzer(system).analyze(
            fields=[10.0], grid_size=8, entrance_pupil_mm=2.0
        )

        angle = math.radians(result.fields[0].field_angle_deg)
        self.assertAlmostEqual(result.fields[0].natural_falloff, math.cos(angle) ** 4, delta=0.005)


class TestVignetting(unittest.TestCase):
    def test_a_field_clipped_by_the_stop_loses_throughput(self):
        result = RelativeIlluminationAnalyzer(_stopped_assembly()).analyze(
            fields=[0.0, 10.0, 20.0], grid_size=8
        )
        axis, ten, twenty = result.fields

        self.assertEqual(axis.relative_illumination, 1.0)
        self.assertFalse(axis.rays_through < axis.rays_launched)
        for entry in (ten, twenty):
            self.assertGreater(entry.lost_fraction, 0.0)
            self.assertLess(entry.geometric_throughput, 1.0)
            self.assertLess(entry.relative_illumination, entry.natural_falloff)
        self.assertLess(twenty.relative_illumination, ten.relative_illumination)

    def test_a_blocked_chief_ray_is_reported_as_unknown_not_zero(self):
        result = RelativeIlluminationAnalyzer(_stopped_assembly()).analyze(
            fields=[30.0], grid_size=8
        )

        entry = result.fields[0]
        self.assertIsNone(entry.natural_falloff)
        self.assertIsNone(entry.relative_illumination)
        self.assertIsNone(entry.image_height_mm)
        self.assertIsNotNone(entry.geometric_throughput)
        self.assertIsNotNone(entry.lost_fraction)

    def test_a_bundle_that_misses_the_optics_reports_undefined_illumination(self):
        # A 1 m requested pupil on a 50 mm lens with a two-point grid: every
        # sample lies outside the optics, so there is no axis to normalize to.
        result = RelativeIlluminationAnalyzer(_singlet()).analyze(
            fields=[0.0, 5.0], grid_size=2, entrance_pupil_mm=1000.0
        )

        self.assertFalse(result.valid)
        self.assertEqual(result.on_axis_throughput, 0.0)
        self.assertIn("blocked", result.warning)
        for entry in result.fields:
            self.assertIsNone(entry.geometric_throughput)
            self.assertIsNone(entry.relative_illumination)


class TestInputs(unittest.TestCase):
    def test_a_lens_and_its_wrapper_give_the_same_result(self):
        lens = _singlet()
        from_lens = RelativeIlluminationAnalyzer(lens).analyze(
            fields=[0.0, 10.0], grid_size=6, entrance_pupil_mm=2.0
        )
        from_system = RelativeIlluminationAnalyzer(as_system(lens)).analyze(
            fields=[0.0, 10.0], grid_size=6, entrance_pupil_mm=2.0
        )

        self.assertEqual(
            [entry.relative_illumination for entry in from_lens.fields],
            [entry.relative_illumination for entry in from_system.fields],
        )
        self.assertEqual(from_lens.entrance_pupil_mm, from_system.entrance_pupil_mm)

    def test_the_wavelength_and_index_are_restored(self):
        lens = _singlet(radius_of_curvature_1=60.0, radius_of_curvature_2=-200.0)
        before = (lens.wavelength, lens.refractive_index)

        RelativeIlluminationAnalyzer(lens).analyze(
            fields=[0.0, 5.0], wavelength_nm=656.3, grid_size=4, entrance_pupil_mm=2.0
        )

        self.assertEqual((lens.wavelength, lens.refractive_index), before)

    def test_the_model_fields_are_used_by_default(self):
        system = OpticalSystem(name="fields")
        system.add_lens(_singlet())
        system.fields = [0.0, 2.0, 4.0]

        result = RelativeIlluminationAnalyzer(system).analyze(grid_size=4, entrance_pupil_mm=2.0)

        self.assertEqual([entry.field_angle_deg for entry in result.fields], [0.0, 2.0, 4.0])

    def test_no_fields_means_the_axis(self):
        result = RelativeIlluminationAnalyzer(_singlet()).analyze(
            grid_size=4, entrance_pupil_mm=2.0
        )

        self.assertEqual(len(result.fields), 1)
        self.assertEqual(result.fields[0].relative_illumination, 1.0)

    def test_an_empty_system_is_rejected(self):
        with self.assertRaises(ValueError):
            RelativeIlluminationAnalyzer(OpticalSystem()).analyze()

    def test_a_too_small_grid_is_rejected(self):
        with self.assertRaises(ValueError):
            RelativeIlluminationAnalyzer(_singlet()).analyze(grid_size=1)

    def test_an_invalid_entrance_pupil_is_rejected(self):
        for value in (0.0, -2.0, float("nan"), "wide"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    RelativeIlluminationAnalyzer(_singlet()).analyze(entrance_pupil_mm=value)


class TestReport(unittest.TestCase):
    def test_the_table_lists_every_field_in_percent(self):
        result = RelativeIlluminationAnalyzer(_singlet()).analyze(
            fields=[0.0, 10.0], grid_size=6, entrance_pupil_mm=2.0
        )

        text = result.format_table()

        self.assertIn("Relative Illumination", text)
        self.assertIn("Angle (deg)", text)
        self.assertIn("100.0%", text)
        self.assertIn("Image plane:", text)
        self.assertEqual(len(result.rows()), 2)

    def test_the_table_says_na_for_a_blocked_chief_ray(self):
        result = RelativeIlluminationAnalyzer(_stopped_assembly()).analyze(
            fields=[30.0], grid_size=6
        )

        self.assertIn("N/A", result.format_table())

    def test_the_metrics_report_carries_the_table(self):
        from openlens.gui.tabs.performance_tab import PerformanceTab

        source = inspect.getsource(PerformanceTab._on_calculate_performance_metrics)
        self.assertIn("_relative_illumination_text", source)


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 not available")
class TestGuiReport(unittest.TestCase):
    def setUp(self):
        from openlens.gui.tabs.performance_tab import PerformanceTab

        self.app = QApplication.instance() or QApplication(sys.argv)
        self.tab = PerformanceTab()

    def tearDown(self):
        self.tab.deleteLater()

    def test_the_tab_formats_a_lens_and_an_assembly(self):
        lens_text = self.tab._relative_illumination_text(_singlet(), WAVELENGTH_GREEN)
        assembly_text = self.tab._relative_illumination_text(_stopped_assembly(), WAVELENGTH_GREEN)

        self.assertIn("Relative Illumination", lens_text)
        self.assertIn("100.0%", lens_text)
        self.assertIn("Angle (deg)", assembly_text)


def _chief_direction_x(system, angle_deg: float) -> float:
    """Image-space direction cosine of the traced chief ray."""
    for element in system.elements:
        element.lens.update_refractive_index(wavelength_nm=WAVELENGTH_GREEN)
    tracer = SystemRayTracer3D(system)
    ray = launch_field_ray(
        system,
        angle_y_deg=angle_deg,
        wavelength_mm=WAVELENGTH_GREEN * NM_TO_MM,
    )
    tracer.trace_ray(ray)
    return ray.direction.x


if __name__ == "__main__":
    unittest.main()
