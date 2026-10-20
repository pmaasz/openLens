#!/usr/bin/env python3
"""
Functional tests for Performance Metrics Dashboard
"""

import sys

import unittest
from openlens.lens import Lens
from openlens.optical_system import OpticalSystem
from openlens.performance_metrics import PerformanceMetrics


class TestPerformanceMetrics(unittest.TestCase):
    """Test performance metrics calculations"""

    def setUp(self):
        """Create test lens"""
        self.lens = Lens(
            name="Test Lens",
            radius_of_curvature_1=50.0,
            radius_of_curvature_2=-50.0,
            thickness=5.0,
            diameter=25.0,
            refractive_index=1.5168,
            lens_type="Biconvex",
            material="BK7",
        )

    def test_f_number_calculation(self):
        """Test f-number calculation"""
        calc = PerformanceMetrics(self.lens)
        f_num = calc.calculate_f_number()

        self.assertIsNotNone(f_num)
        self.assertGreater(f_num, 0)
        print(f"✓ F-number: f/{f_num:.2f}")

    def test_back_focal_length(self):
        """Test back focal length calculation"""
        calc = PerformanceMetrics(self.lens)
        bfl = calc.calculate_back_focal_length()

        self.assertIsNotNone(bfl)
        print(f"✓ Back focal length: {bfl:.3f} mm")

    def test_numerical_aperture(self):
        """Test numerical aperture calculation"""
        calc = PerformanceMetrics(self.lens)
        na = calc.calculate_numerical_aperture(half_angle_deg=15.0)

        self.assertIsNotNone(na)
        self.assertGreater(na, 0)
        self.assertLess(na, 1.0)
        print(f"✓ Numerical aperture: {na:.4f}")

    def test_resolution_estimate(self):
        """Test resolution estimation"""
        calc = PerformanceMetrics(self.lens)
        f_num = calc.calculate_f_number()
        resolution = calc.estimate_resolution_rayleigh(wavelength=550.0, f_number=f_num)

        self.assertIsNotNone(resolution)
        self.assertGreater(resolution, 0)
        print(f"✓ Resolution (Rayleigh): {resolution:.3f} μm")

    def test_angular_rayleigh_resolution_absolute_value(self):
        """Angular Rayleigh limit must equal 1.22*lambda/D (guards nm->mm units)."""
        calc = PerformanceMetrics(self.lens)
        res_urad = calc.calculate_resolution_rayleigh()

        self.assertIsNotNone(res_urad)
        expected_urad = 1.22 * (self.lens.wavelength * 1e-6) / self.lens.diameter * 1e6
        self.assertAlmostEqual(res_urad, expected_urad, places=3)
        # Order-of-magnitude guard: the old /1000 bug inflated this 1000x
        # (~29000 urad instead of ~29 urad for this lens).
        self.assertLess(res_urad, 1000.0)
        print(f"✓ Angular Rayleigh limit: {res_urad:.3f} μrad")

    def test_mtf_cutoff(self):
        """Test MTF cutoff frequency"""
        calc = PerformanceMetrics(self.lens)
        f_num = calc.calculate_f_number()
        mtf = calc.estimate_mtf_cutoff(wavelength=550.0, f_number=f_num)

        self.assertIsNotNone(mtf)
        self.assertGreater(mtf, 0)
        print(f"✓ MTF cutoff: {mtf:.1f} lp/mm")

    def test_airy_disk(self):
        """Test Airy disk radius calculation"""
        calc = PerformanceMetrics(self.lens)
        airy_radius = calc.calculate_airy_disk_radius()

        self.assertIsNotNone(airy_radius)
        self.assertGreater(airy_radius, 0)
        # Convert radius to diameter for display
        airy_diameter = airy_radius * 2 * 1000  # Convert mm to μm
        print(f"✓ Airy disk diameter: {airy_diameter:.3f} μm")

    def test_depth_of_field(self):
        """Test depth of field calculation"""
        calc = PerformanceMetrics(self.lens)
        dof_result = calc.calculate_depth_of_field(object_distance=1000.0, circle_of_confusion=0.03)

        self.assertIsNotNone(dof_result)
        self.assertIn("near", dof_result)
        self.assertIn("far", dof_result)

        dof_near = dof_result["near"]
        dof_far = dof_result["far"]

        self.assertIsNotNone(dof_near)
        self.assertGreater(dof_near, 0)
        print(
            f"✓ Depth of field: {dof_near:.1f} mm to {dof_far if dof_far != float('inf') else '∞'}"
        )

    def test_field_of_view(self):
        """Test field of view calculation"""
        calc = PerformanceMetrics(self.lens)
        fov = calc.calculate_field_of_view(sensor_size=36.0)

        self.assertIsNotNone(fov)
        self.assertGreater(fov, 0)
        self.assertLess(fov, 180)
        print(f"✓ Field of view: {fov:.2f}°")

    def test_get_all_metrics(self):
        """Test getting all metrics at once"""
        calc = PerformanceMetrics(self.lens)
        metrics = calc.get_all_metrics(
            entrance_pupil_diameter=10.0,
            wavelength=550.0,
            object_distance=1000.0,
            sensor_size=36.0,
        )

        self.assertIsInstance(metrics, dict)
        self.assertIn("effective_focal_length", metrics)
        self.assertIn("f_number", metrics)
        self.assertIn("back_focal_length", metrics)
        self.assertIn("resolution_um", metrics)
        self.assertIn("mtf_cutoff_lpmm", metrics)
        self.assertIn("field_of_view_deg", metrics)

        print("✓ All metrics calculated successfully")
        print(f"  - Focal length: {metrics['effective_focal_length']:.2f} mm")
        print(f"  - F-number: f/{metrics['f_number']:.2f}")
        print(f"  - Resolution: {metrics['resolution_um']:.3f} μm")
        print(f"  - Field of view: {metrics['field_of_view_deg']:.2f}°")

    def test_format_metrics_report(self):
        """Test metrics report formatting"""
        calc = PerformanceMetrics(self.lens)
        metrics = calc.get_all_metrics()
        report = calc.format_metrics_report(metrics)

        self.assertIsInstance(report, str)
        self.assertIn("PERFORMANCE METRICS DASHBOARD", report)
        self.assertIn("Effective Focal Length", report)
        self.assertIn("F-Number", report)
        self.assertIn("Resolution", report)

        print("✓ Metrics report formatted successfully")
        print(report)


class TestPerformanceMetricsWithSystem(unittest.TestCase):
    """Test performance metrics with optical systems"""

    def test_optical_system_metrics(self):
        """Test metrics for optical system"""
        lens1 = Lens(
            name="Element 1",
            radius_of_curvature_1=50.0,
            radius_of_curvature_2=-50.0,
            thickness=5.0,
            diameter=25.0,
            refractive_index=1.5168,
        )

        system = OpticalSystem(name="Test System")
        system.add_lens(lens1, air_gap_before=0.0)

        calc = PerformanceMetrics(system)
        f_num = calc.calculate_f_number()

        self.assertIsNotNone(f_num)
        print(f"✓ System F-number: f/{f_num:.2f}")


class TestBackFocalLengthForSystem(unittest.TestCase):
    """BFL must be the distance from the last surface, not the EFL.

    The system branch returned get_system_focal_length() verbatim, so every
    reported back focal distance was too long by the whole distance from the
    last surface to focus (typically 10-50 mm).
    """

    def setUp(self):
        self.system = OpticalSystem(name="BFL")
        self.system.add_lens(
            Lens(
                name="Front",
                radius_of_curvature_1=50.0,
                radius_of_curvature_2=-50.0,
                thickness=5.0,
                diameter=20.0,
                refractive_index=1.5,
            )
        )
        self.system.add_lens(
            Lens(
                name="Rear",
                radius_of_curvature_1=-60.0,
                radius_of_curvature_2=100.0,
                thickness=4.0,
                diameter=20.0,
                refractive_index=1.6,
            ),
            air_gap_before=2.0,
        )

    def test_bfl_matches_optical_system(self):
        bfl = PerformanceMetrics(self.system).calculate_back_focal_length()
        self.assertAlmostEqual(bfl, self.system.calculate_back_focal_length(), places=9)

    def test_bfl_is_not_the_efl(self):
        efl = self.system.get_system_focal_length()
        bfl = PerformanceMetrics(self.system).calculate_back_focal_length()
        self.assertNotAlmostEqual(bfl, efl, places=3)
        # The error was the whole back focal distance.
        self.assertGreater(abs(efl - bfl), 1.0)

    def test_bfl_is_measured_from_the_last_surface(self):
        """BFL shorter than EFL by more than the system length is plausible."""
        bfl = PerformanceMetrics(self.system).calculate_back_focal_length()
        length = self.system.get_total_length()
        self.assertLess(bfl, self.system.get_system_focal_length())
        self.assertGreater(bfl, 0.0)
        self.assertLess(length, self.system.get_system_focal_length())

    def test_empty_system_returns_none(self):
        empty = OpticalSystem(name="Empty")
        self.assertIsNone(PerformanceMetrics(empty).calculate_back_focal_length())

    def test_single_lens_bfl_uses_the_thick_lens_model(self):
        lens = Lens(
            radius_of_curvature_1=50.0,
            radius_of_curvature_2=-50.0,
            thickness=5.0,
            diameter=20.0,
            refractive_index=1.5,
        )
        bfl = PerformanceMetrics(lens).calculate_back_focal_length()
        self.assertAlmostEqual(bfl, lens.calculate_back_focal_length(), places=9)


class TestDepthOfFieldBeyondHyperfocal(unittest.TestCase):
    """#459: the near limit stays on the lens formula at and beyond H.

    The old code returned ``H / 2`` for every object distance at or beyond
    the hyperfocal distance. That is exact only at ``s == H``; beyond it the
    near limit keeps moving away, and ``s(H-f)/(H+s-2f)`` is still the
    correct expression.
    """

    def setUp(self):
        self.lens = Lens(
            name="DOF Lens",
            radius_of_curvature_1=50.0,
            radius_of_curvature_2=-50.0,
            thickness=5.0,
            diameter=25.0,
            refractive_index=1.5168,
        )
        self.calc = PerformanceMetrics(self.lens)

    def _hyperfocal(self):
        f = self.lens.calculate_focal_length()
        f_number = self.calc.calculate_f_number()
        return f, f**2 / (f_number * 0.03) + f

    def _near(self, distance):
        dof = self.calc.calculate_depth_of_field(object_distance=distance)
        self.assertIsNotNone(dof)
        return dof["near"]

    def test_near_limit_beyond_hyperfocal_uses_the_formula_not_half_h(self):
        f, H = self._hyperfocal()
        distance = 5.0 * H

        expected = distance * (H - f) / (H + distance - 2.0 * f)

        self.assertAlmostEqual(self._near(distance), expected, places=6)
        # The old branch reported H/2 here.
        self.assertGreater(self._near(distance), H / 2.0 * 1.1)

    def test_the_formula_holds_at_and_on_both_sides_of_h(self):
        f, H = self._hyperfocal()

        for factor in (0.5, 1.0, 5.0):
            distance = factor * H
            expected = distance * (H - f) / (H + distance - 2.0 * f)
            with self.subTest(object_distance=f"{factor} H"):
                self.assertAlmostEqual(self._near(distance), expected, places=6)

    def test_near_limit_keeps_receding_beyond_the_hyperfocal_distance(self):
        _, H = self._hyperfocal()

        near_at_5h = self._near(5.0 * H)
        near_at_10h = self._near(10.0 * H)

        self.assertGreater(near_at_10h, near_at_5h)

    def test_far_limit_is_infinite_only_at_or_beyond_hyperfocal(self):
        _, H = self._hyperfocal()

        self.assertNotEqual(
            self.calc.calculate_depth_of_field(object_distance=0.999 * H)["far"],
            float("inf"),
        )
        self.assertEqual(
            self.calc.calculate_depth_of_field(object_distance=H)["far"],
            float("inf"),
        )
        self.assertEqual(
            self.calc.calculate_depth_of_field(object_distance=5.0 * H)["far"],
            float("inf"),
        )


def run_tests():
    """Run all performance metrics tests"""
    print("=" * 70)
    print("TESTING: Performance Metrics Dashboard")
    print("=" * 70)

    suite = unittest.TestLoader().loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "=" * 70)
    if result.wasSuccessful():
        print("✓ All performance metrics tests passed!")
    else:
        print("✗ Some tests failed")
    print("=" * 70)

    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
