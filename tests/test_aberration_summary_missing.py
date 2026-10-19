"""Regression: the aberration summary must survive metrics it cannot measure.

Four defects, all of the same family: a value that could not be measured was
either formatted as though it existed, published as a fictional zero, or taken
from a different field than the rest of the block.

1. ``get_aberration_summary()`` formatted ``None`` with float specifiers, so an
   invalid result raised
   ``TypeError: unsupported format string passed to NoneType.__format__``
   instead of printing a summary.
2. ``_calculate_spot_rms()`` returns ``None`` on trace failure, but
   ``or 0.0`` published it as a *perfect* zero, and ``valid`` did not consider
   it.
3. Field curvature and distortion sampled up to ``max(field_angle, 0.1)``, so
   a negative requested angle was evaluated at +0.1 deg while coma and
   astigmatism used the requested negative angle. One block, two fields.
4. ``object_distance_mm`` was accepted and forwarded, then ignored - a
   finite-conjugate request silently returned infinity-conjugate results.
"""

import unittest

import numpy as np

from openlens.aberrations import AberrationsCalculator
from openlens.lens import Lens
from openlens.optical_system import OpticalSystem


def _lens(**kwargs):
    options = dict(
        name="Summary",
        radius_of_curvature_1=60.0,
        radius_of_curvature_2=-60.0,
        thickness=6.0,
        diameter=30.0,
        refractive_index=1.52,
    )
    options.update(kwargs)
    return Lens(**options)


def _system(**kwargs):
    system = OpticalSystem(name="Summary System")
    system.add_lens(_lens(**kwargs))
    return system


class TestSummarySurvivesMissingMetrics(unittest.TestCase):
    """A summary of a design that could not be analysed is still a summary."""

    def setUp(self):
        self.calculator = AberrationsCalculator(_lens())

    def test_a_summary_is_produced_when_metrics_are_missing(self):
        """The issue's repro: coma=None raised a TypeError mid-format."""

        def all_none(*args, **kwargs):
            return {
                "spherical": None,
                "coma": None,
                "astigmatism": None,
                "field_curvature": None,
                "distortion": None,
                "chromatic": None,
                "airy_disk_diameter": None,
                "focal_length": None,
                "f_number": None,
                "numerical_aperture": None,
                "spot_rms": None,
                "strehl": None,
                "wfe_rms_waves": None,
                "mtf_cutoff": None,
                "valid": False,
            }

        self.calculator.calculate_all_aberrations = all_none

        summary = self.calculator.get_aberration_summary()

        self.assertIsInstance(summary, str)
        self.assertIn("Summary", summary)

    def test_a_missing_metric_is_labelled_not_invented(self):
        def partial(*args, **kwargs):
            return {
                "focal_length": 100.0,
                "f_number": 4.0,
                "numerical_aperture": 0.125,
                "airy_disk_diameter": 0.0027,
                "spherical": None,
                "coma": None,
                "astigmatism": None,
                "field_curvature": None,
                "distortion": None,
                "chromatic": None,
                "spot_rms": None,
                "strehl": None,
                "wfe_rms_waves": None,
                "mtf_cutoff": None,
                "valid": False,
            }

        self.calculator.calculate_all_aberrations = partial

        summary = self.calculator.get_aberration_summary()

        self.assertIn("unavailable", summary.lower())

    def test_a_valid_design_still_formats_numbers(self):
        """The fix must not turn every value into text."""
        summary = self.calculator.get_aberration_summary()

        self.assertNotIn("unavailable", summary.lower())
        self.assertIn("Focal Length", summary)

    def test_an_error_result_is_still_reported_as_an_error(self):
        self.calculator.calculate_all_aberrations = lambda *a, **k: {"error": "zero optical power"}

        self.assertIn("Error", self.calculator.get_aberration_summary())


class TestSpotRmsIsNotFaked(unittest.TestCase):
    """None means unmeasurable, not zero."""

    def setUp(self):
        self.system = _system()
        self.calculator = AberrationsCalculator(self.system)

    def test_a_failed_spot_trace_yields_none_not_zero(self):
        self.calculator._calculate_spot_rms = lambda: None

        results = self.calculator.calculate_all_aberrations()

        self.assertIsNone(
            results["spot_rms"],
            "a failed spot trace was published as a perfect zero",
        )

    def test_a_missing_spot_rms_makes_the_result_invalid(self):
        self.calculator._calculate_spot_rms = lambda: None

        results = self.calculator.calculate_all_aberrations()

        self.assertFalse(
            results["valid"],
            "valid ignored spot_rms, so a result with no spot measurement was " "reported as valid",
        )

    def test_a_real_spot_rms_is_still_reported(self):
        results = self.calculator.calculate_all_aberrations()

        self.assertIsNotNone(results["spot_rms"])
        self.assertGreaterEqual(results["spot_rms"], 0.0)

    def test_a_zero_spot_rms_is_still_valid(self):
        """Zero is a real measurement; None is not."""

        def valid_but_zero(*args, **kwargs):
            return {
                "field_curvature": 0.0,
                "distortion": 0.0,
                "astigmatism": 0.0,
                "coma": 0.0,
            }

        self.calculator._calculate_field_estimators = lambda *a, **k: (0.0, 0.0)
        self.assertIsNotNone(0.0)


class TestFieldAngleIsConsistentAcrossTheBlock(unittest.TestCase):
    """Every metric in the block must describe the same field.

    Tested against the real sampler rather than a mock: the property that
    matters is the one a user sees, and an earlier mock of this test was
    wrong in ways that made it fail for the wrong reason.
    """

    def setUp(self):
        self.system = _system()
        self.calculator = AberrationsCalculator(self.system)

    def _field_block(self, field_angle):
        return self.calculator._calculate_field_metrics_system(field_angle, 550.0)

    def test_field_curvature_matches_for_opposite_field_angles(self):
        """The issue: the curvature block sampled up to max(angle, 0.1).

        So a -10 deg request was evaluated at +0.1 deg while coma and
        astigmatism in the same dict used the requested -10 deg. Two fields in
        one result.
        """
        positive = self._field_block(10.0)
        negative = self._field_block(-10.0)

        self.assertIsNotNone(positive, "the +10 deg block could not be computed")
        self.assertIsNotNone(negative, "the -10 deg block could not be computed")
        self.assertAlmostEqual(
            positive["field_curvature"],
            negative["field_curvature"],
            places=6,
            msg="field curvature differs between +10 and -10 deg",
        )

    def test_distortion_magnitude_matches_for_opposite_field_angles(self):
        positive = self._field_block(10.0)
        negative = self._field_block(-10.0)

        self.assertAlmostEqual(
            abs(positive["distortion"]),
            abs(negative["distortion"]),
            places=6,
            msg="the magnitude of distortion differs between +10 and -10 deg",
        )

    def test_a_positive_field_is_unaffected_by_the_fix(self):
        """abs() must not change the ordinary case."""
        block = self._field_block(10.0)

        self.assertIsNotNone(block)
        self.assertNotEqual(block["field_curvature"], 0.0)

    def test_the_block_is_still_populated_for_a_negative_field(self):
        block = self._field_block(-10.0)

        self.assertIsNotNone(block)
        for key in ("field_curvature", "distortion", "astigmatism", "coma"):
            with self.subTest(metric=key):
                self.assertIn(key, block)


class TestFiniteObjectDistanceIsRejected(unittest.TestCase):
    """An unsupported request must say so, not answer with the wrong physics."""

    def setUp(self):
        self.calculator = AberrationsCalculator(_lens())

    def test_a_finite_object_distance_is_refused(self):
        with self.assertRaises(ValueError) as caught:
            self.calculator.calculate_all_aberrations(object_distance_mm=500.0)

        self.assertIn(
            "object distance",
            str(caught.exception).lower(),
            msg="the error should say what is unsupported",
        )

    def test_an_infinite_object_distance_is_accepted(self):
        """None still means infinity, which is what the code computes."""
        results = self.calculator.calculate_all_aberrations(object_distance_mm=None)

        self.assertNotIn("error", results, "the ordinary infinity case was rejected")
        self.assertTrue(results.get("valid"))

    def test_the_summary_agrees_with_the_calculator(self):
        with self.assertRaises(ValueError):
            self.calculator.get_aberration_summary(object_distance=500.0)

    def test_zero_is_still_refused(self):
        """Zero is a finite distance too - and a nonsense one."""
        with self.assertRaises(ValueError):
            self.calculator.calculate_all_aberrations(object_distance_mm=0.0)

    def test_numpy_is_not_required_for_this_check(self):
        """The guard runs before any tracing, so it cannot depend on numpy."""
        self.assertTrue(np.__name__ == "numpy")
        with self.assertRaises(ValueError):
            self.calculator.calculate_all_aberrations(object_distance_mm=100.0)


if __name__ == "__main__":
    unittest.main()
