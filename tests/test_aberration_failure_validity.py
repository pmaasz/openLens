#!/usr/bin/env python3
"""
A failed ray trace must not be published as a perfect design.

aberrations._calculate_field_estimators wrapped its whole body in

    except Exception as e:
        logger.warning("Field estimators ray trace failed: %s", e)
        return 0.0, 0.0

so a failure reported coma = 0.0 and astigmatism = 0.0 - indistinguishable
from a perfect off-axis design, and better than diffraction limited - for
exactly the geometries whose trace failed. This is a live path: the 2D tracer
returns MISSED rather than raising, so it was reached in practice.

The estimators now return None, calculate_all_aberrations reports a
`valid` flag derived from every metric, and the GUI renders a missing value
as N/A instead of formatting None.

The other three broad-except sites named in the issue (calculate_field_metrics,
calculate_spot_rms, _calculate_spherical_aberration) already returned None
and are unchanged.
"""

import unittest

from src.aberrations import AberrationsCalculator, _all_valid
from src.lens import Lens
from src.optical_system import OpticalSystem


def _biconvex():
    return Lens(
        name="B",
        radius_of_curvature_1=50.0,
        radius_of_curvature_2=-50.0,
        thickness=5.0,
        diameter=25.0,
        refractive_index=1.5,
    )


def _boom(calc, method="calculate_ray_fan"):
    def raiser(*args, **kwargs):
        raise RuntimeError("simulated trace failure")

    setattr(calc, method, raiser)


class TestAllValidHelper(unittest.TestCase):
    def test_all_present_is_valid(self):
        self.assertTrue(_all_valid(1.0, 2.0, 3.0))

    def test_any_none_is_invalid(self):
        self.assertFalse(_all_valid(1.0, None, 3.0))

    def test_zero_is_still_valid(self):
        """A real measurement of zero must not be treated as missing."""
        self.assertTrue(_all_valid(0.0, 0.0))

    def test_dict_values_are_checked(self):
        self.assertTrue(_all_valid({"coma": 0.1, "astigmatism": 0.2}))
        self.assertFalse(_all_valid({"coma": None, "astigmatism": 0.2}))


class TestEstimatorsReportFailure(unittest.TestCase):
    def setUp(self):
        self.calc = AberrationsCalculator(_biconvex())

    def test_failed_trace_returns_none_not_zero(self):
        """Regression: returned (0.0, 0.0)."""
        _boom(self.calc)
        self.assertIsNone(self.calc._calculate_field_estimators(5.0, 550.0))

    def test_singlet_wrapper_propagates_none(self):
        _boom(self.calc)
        self.assertIsNone(self.calc._calculate_singlet_field_estimators(5.0, 550.0))

    def test_on_axis_zero_is_genuine_not_a_failure(self):
        """There is no coma on axis; that is a measurement, not a gap."""
        self.assertEqual(self.calc._calculate_singlet_field_estimators(0.0, 550.0), (0.0, 0.0))

    def test_healthy_lens_reports_numbers(self):
        result = self.calc._calculate_field_estimators(5.0, 550.0)
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 2)


class TestValidFlagOnSinglet(unittest.TestCase):
    def setUp(self):
        self.calc = AberrationsCalculator(_biconvex())

    def test_healthy_lens_is_valid(self):
        self.assertIs(self.calc.calculate_all_aberrations(field_angle_deg=5.0)["valid"], True)

    def test_failed_trace_is_invalid_and_none(self):
        _boom(self.calc)
        result = self.calc.calculate_all_aberrations(field_angle_deg=5.0)
        self.assertIs(result["valid"], False)
        self.assertIsNone(result["coma"])
        self.assertIsNone(result["astigmatism"])

    def test_on_axis_lens_is_valid_with_zero_coma(self):
        result = self.calc.calculate_all_aberrations(field_angle_deg=0.0)
        self.assertIs(result["valid"], True)
        self.assertEqual(result["coma"], 0.0)

    def test_zero_power_lens_is_invalid(self):
        """The zero-power branch publishes placeholders, so it says so."""
        flat = Lens(
            name="Flat",
            radius_of_curvature_1=float("inf"),
            radius_of_curvature_2=float("inf"),
            thickness=2.0,
            diameter=25.0,
            refractive_index=1.0,
        )
        result = AberrationsCalculator(flat).calculate_all_aberrations()
        self.assertIs(result["valid"], False)
        self.assertIn("error", result)


class TestValidFlagOnSystem(unittest.TestCase):
    def _system(self):
        system = OpticalSystem(name="S")
        system.add_lens(_biconvex())
        return system

    def test_healthy_system_is_valid(self):
        calc = AberrationsCalculator(self._system())
        self.assertIs(calc.calculate_all_aberrations(field_angle_deg=5.0)["valid"], True)

    def test_failed_system_trace_is_invalid(self):
        calc = AberrationsCalculator(self._system())
        _boom(calc)
        result = calc.calculate_all_aberrations(field_angle_deg=5.0)
        self.assertIs(result["valid"], False)
        self.assertIsNone(result["coma"])

    def test_system_failure_does_not_fabricate_zeros(self):
        """Regression: a None field_data became a block of 0.0."""
        calc = AberrationsCalculator(self._system())
        _boom(calc)
        result = calc.calculate_all_aberrations(field_angle_deg=5.0)
        for key in ("coma", "astigmatism", "field_curvature", "distortion"):
            self.assertIsNone(result[key], key)


class TestReportFormatting(unittest.TestCase):
    """The report formats with :.4f, so a None must not reach it."""

    def _fmt(self, value, spec=".4f", scale=1.0):
        from src.gui.tabs.performance_tab import _fmt

        return _fmt(value, spec, scale)

    def test_number_formats_normally(self):
        self.assertEqual(self._fmt(1.23456), "1.2346")

    def test_none_renders_as_na(self):
        self.assertEqual(self._fmt(None), "N/A")

    def test_zero_still_renders_as_zero(self):
        self.assertEqual(self._fmt(0.0), "0.0000")

    def test_scale_is_applied(self):
        self.assertEqual(self._fmt(1.5, ".2f", 1000.0), "1500.00")

    def test_scaled_none_renders_as_na(self):
        self.assertEqual(self._fmt(None, ".2f", 1000.0), "N/A")

    def test_non_numeric_input_renders_as_na(self):
        self.assertEqual(self._fmt("oops"), "N/A")


class TestNoFabricatedZerosAnywhere(unittest.TestCase):
    def test_failure_never_yields_a_better_than_diffraction_number(self):
        calc = AberrationsCalculator(_biconvex())
        _boom(calc)
        result = calc.calculate_all_aberrations(field_angle_deg=5.0)
        self.assertNotEqual(result["coma"], 0.0)
        self.assertNotEqual(result["astigmatism"], 0.0)
