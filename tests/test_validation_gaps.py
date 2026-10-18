"""Regression: validation must reject what it says it rejects.

Four defects, found together:

1. ``validate_lens_parameters`` accepted ``clear_aperture_1/2``, documented them,
   and then neither validated nor returned them. A -5 mm front aperture or a
   1e9 mm rear one returned normally, so a caller asking for validation got
   neither an error nor the value.
2. ``_validate_number`` called ``math.isnan`` on a value that could not be a
   float yet, so a huge int raised ``OverflowError`` instead of
   ``ValidationError`` - the one exception type every caller of this module
   knows how to handle.
3. ``validate_lens_data_schema`` used ``isinstance(x, (int, float))``, and
   ``isinstance(True, int)`` is True - so a JSON ``true`` satisfied a radius or
   a thickness outright.
4. ``numpy.float32`` was rejected with "radius must be a number, got float32",
   even though it is a real number that every downstream calculation handles
   and that round-trips through JSON as a plain one.
"""

import unittest

from src.validation import (
    ValidationError,
    _validate_number,
    validate_clear_aperture,
    validate_lens_data_schema,
    validate_lens_parameters,
    validate_radius,
    validate_thickness,
)


def _lens_data(**overrides):
    data = {
        "name": "L",
        "radius_of_curvature_1": 50.0,
        "radius_of_curvature_2": -50.0,
        "thickness": 5.0,
        "diameter": 25.0,
        "material": "N-BK7",
        "refractive_index": 1.5168,
    }
    data.update(overrides)
    return data


class TestClearAperturesAreActuallyValidated(unittest.TestCase):
    """Issue 1: accepted, documented, ignored."""

    def _params(self, _diameter=25, **kwargs):
        args = {
            "radius1": 50,
            "radius2": -50,
            "thickness": 5,
            "diameter": _diameter,
            "refractive_index": 1.5,
        }
        return validate_lens_parameters(**args, **kwargs)

    def test_the_issue_repro(self):
        with self.assertRaises(ValidationError):
            self._params(clear_aperture_1=-5, clear_aperture_2=1e9)

    def test_a_negative_front_aperture_is_rejected(self):
        with self.assertRaises(ValidationError) as caught:
            self._params(clear_aperture_1=-5)

        self.assertIn("clear aperture 1", str(caught.exception))

    def test_an_oversized_rear_aperture_is_rejected(self):
        with self.assertRaises(ValidationError) as caught:
            self._params(clear_aperture_2=1e9)

        self.assertIn("clear aperture 2", str(caught.exception))

    def test_an_aperture_wider_than_the_lens_is_rejected(self):
        with self.assertRaises(ValidationError):
            self._params(clear_aperture_1=40)

    def test_the_apertures_are_returned(self):
        """Not just rejected when bad - present when good."""
        result = self._params(clear_aperture_1=20.0, clear_aperture_2=18.0)

        self.assertEqual(result["clear_aperture_1"], 20.0)
        self.assertEqual(result["clear_aperture_2"], 18.0)

    def test_absent_apertures_are_none(self):
        result = self._params()

        self.assertIsNone(result["clear_aperture_1"])
        self.assertIsNone(result["clear_aperture_2"])

    def test_the_key_is_always_present(self):
        """A caller reading the key must not get a KeyError on the happy path."""
        self.assertIn("clear_aperture_1", self._params())

    def test_each_surface_is_validated_independently(self):
        with self.assertRaises(ValidationError) as caught:
            self._params(clear_aperture_1=20.0, clear_aperture_2=-1)

        self.assertIn("clear aperture 2", str(caught.exception))

    def test_the_aperture_bound_uses_the_validated_diameter(self):
        """An aperture wider than the lens is rejected against the real diameter."""
        with self.assertRaises(ValidationError) as caught:
            self._params(clear_aperture_1=31, _diameter=30)

        self.assertIn("cannot exceed", str(caught.exception))

    def test_an_aperture_narrower_than_the_lens_is_fine(self):
        """The ceiling is the diameter, not a rule that forbids being smaller."""
        result = self._params(clear_aperture_1=29, _diameter=30)

        self.assertEqual(result["clear_aperture_1"], 29.0)

    def test_a_bad_diameter_is_reported_before_the_aperture(self):
        """Proves the aperture is checked against a validated diameter."""
        with self.assertRaises(ValidationError) as caught:
            self._params(clear_aperture_1=10, _diameter=0)

        self.assertIn("diameter", str(caught.exception))


class TestHugeIntegersRaiseValidationError(unittest.TestCase):
    """Issue 2: OverflowError escaped instead of ValidationError."""

    def test_a_huge_int_does_not_raise_overflow_error(self):
        with self.assertRaises(ValidationError):
            _validate_number(10**400)

    def test_validate_radius_reports_it_as_a_validation_error(self):
        with self.assertRaises(ValidationError):
            validate_radius(10**400)

    def test_validate_thickness_reports_it_as_a_validation_error(self):
        with self.assertRaises(ValidationError):
            validate_thickness(10**400)

    def test_validate_lens_parameters_reports_it_as_a_validation_error(self):
        with self.assertRaises(ValidationError):
            validate_lens_parameters(10**400, -50, 5, 25, 1.5)

    def test_the_message_explains_the_value_is_too_large(self):
        with self.assertRaises(ValidationError) as caught:
            _validate_number(10**400)

        self.assertIn(
            "too large",
            str(caught.exception),
            "the message should say why, not just that it is invalid",
        )

    def test_a_large_but_representable_int_still_works(self):
        """The guard must not reject values that are merely big."""
        self.assertEqual(_validate_number(10**300), float(10**300))

    def test_overflow_error_is_never_leaked(self):
        """Every entry point, checked for the specific leak."""
        for call in (
            lambda: _validate_number(10**400),
            lambda: validate_radius(10**400),
            lambda: validate_thickness(10**400),
            lambda: validate_clear_aperture(10**400, 25.0),
        ):
            with self.subTest(call=call):
                with self.assertRaises(ValidationError):
                    call()


class TestBooleansAreNotNumbers(unittest.TestCase):
    """Issue 3: isinstance(True, int) is True."""

    NUMERIC_FIELDS = (
        "radius_of_curvature_1",
        "radius_of_curvature_2",
        "thickness",
        "diameter",
        "refractive_index",
    )

    def test_a_boolean_radius_is_rejected(self):
        with self.assertRaises(ValidationError) as caught:
            validate_lens_data_schema(_lens_data(radius_of_curvature_1=True))

        self.assertIn("bool", str(caught.exception))

    def test_every_numeric_field_rejects_a_boolean(self):
        for field in self.NUMERIC_FIELDS:
            with self.subTest(field=field):
                with self.assertRaises(ValidationError):
                    validate_lens_data_schema(_lens_data(**{field: True}))
                with self.assertRaises(ValidationError):
                    validate_lens_data_schema(_lens_data(**{field: False}))

    def test_optional_numeric_fields_reject_a_boolean_too(self):
        for field in ("wavelength", "temperature"):
            with self.subTest(field=field):
                with self.assertRaises(ValidationError):
                    validate_lens_data_schema(_lens_data(**{field: True}))

    def test_a_string_field_still_accepts_its_string(self):
        """The guard is scoped to numeric fields; name must not break."""
        self.assertEqual(validate_lens_data_schema(_lens_data())["name"], "L")

    def test_the_direct_validator_rejects_a_boolean(self):
        with self.assertRaises(ValidationError) as caught:
            _validate_number(True)

        self.assertIn("bool", str(caught.exception))

    def test_valid_numbers_still_pass(self):
        data = _lens_data(radius_of_curvature_1=50, thickness=5)
        self.assertEqual(validate_lens_data_schema(data)["thickness"], 5)


class TestRealNumbersAreAccepted(unittest.TestCase):
    """Issue 4: numpy.float32 is a number."""

    @staticmethod
    def _float32():
        try:
            import numpy as np
        except ImportError:  # pragma: no cover - numpy is a hard requirement
            raise unittest.SkipTest("numpy not available")
        return np.float32(50.0)

    def test_a_float32_radius_is_accepted(self):
        radius = validate_radius(self._float32())

        self.assertAlmostEqual(radius, 50.0, places=4)
        self.assertIsInstance(radius, float)

    def test_the_error_is_gone(self):
        """The reported symptom, asserted directly."""
        validate_radius(self._float32())  # must not raise

    def test_a_float32_passes_through_validate_lens_parameters(self):
        result = validate_lens_parameters(self._float32(), -50.0, 5.0, 25.0, 1.5168)

        self.assertAlmostEqual(result["radius1"], 50.0, places=4)

    def test_a_float32_thickness_is_accepted(self):
        self.assertAlmostEqual(validate_thickness(self._float32()), 50.0, places=4)

    def test_strings_are_still_rejected(self):
        """Widening to numbers.Real must not open the door to str."""
        with self.assertRaises(ValidationError):
            validate_radius("50")

    def test_none_is_still_rejected(self):
        with self.assertRaises(ValidationError):
            validate_radius(None)

    def test_complex_numbers_are_still_rejected(self):
        with self.assertRaises(ValidationError):
            validate_radius(1 + 2j)

    def test_decimal_is_still_rejected(self):
        """Decimal is numbers.Number but NOT numbers.Real, so it stays out.

        Checked because widening to Real could plausibly have taken Number
        instead, which would have silently accepted it.
        """
        from decimal import Decimal

        with self.assertRaises(ValidationError):
            validate_radius(Decimal("50.5"))


class TestTheSharedFirstStageStaysShared(unittest.TestCase):
    """Everything numeric goes through _validate_number; keep its contract."""

    def test_infinity_and_nan_are_still_rejected(self):
        for bad in (float("inf"), float("-inf"), float("nan")):
            with self.subTest(value=bad):
                with self.assertRaises(ValidationError):
                    _validate_number(bad)

    def test_the_return_value_is_a_plain_float(self):
        self.assertIsInstance(_validate_number(5), float)


if __name__ == "__main__":
    unittest.main()
