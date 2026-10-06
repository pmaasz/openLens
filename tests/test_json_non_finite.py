#!/usr/bin/env python3
"""
Parsed JSON must not smuggle NaN or Infinity into the model.

Python's json.load accepts the bare NaN, Infinity and -Infinity literals -
they are not valid JSON, but they parse. validate_lens_data_schema checked
only isinstance, so they passed and propagated:

    validate_lens_data_schema ACCEPTED NaN radius and inf thickness
    Lens.from_dict -> radius_of_curvature_1 = nan, thickness = inf
    focal length   -> nan

A NaN focal length compares false against every threshold, so it slips past
every downstream sanity check silently.

_validate_number already did the right finiteness test; numeric schema fields
now route through the same rule. A recursive sweep covers nested payloads
(an assembly's elements), which no schema validator here handles, and the
startup import - the only JSON import in the application - now validates the
path and the payload before constructing anything.
"""

import json
import unittest

from src.lens import Lens
from src.validation import (
    ValidationError,
    reject_non_finite_numbers,
    validate_lens_data_schema,
)

CLEAN = {
    "name": "X",
    "radius_of_curvature_1": 50.0,
    "radius_of_curvature_2": -50.0,
    "thickness": 5.0,
    "diameter": 25.0,
    "refractive_index": 1.5,
}

NAN = float("nan")
INF = float("inf")


def _with(field, value):
    data = dict(CLEAN)
    data[field] = value
    return data


class TestSchemaRejectsNonFinite(unittest.TestCase):
    def test_clean_data_is_accepted(self):
        self.assertEqual(validate_lens_data_schema(dict(CLEAN)), CLEAN)

    def test_nan_radius_is_rejected(self):
        with self.assertRaises(ValidationError) as ctx:
            validate_lens_data_schema(_with("radius_of_curvature_1", NAN))
        self.assertIn("finite", str(ctx.exception))

    def test_nan_radius_2_is_rejected(self):
        with self.assertRaises(ValidationError):
            validate_lens_data_schema(_with("radius_of_curvature_2", NAN))

    def test_infinite_thickness_is_rejected(self):
        with self.assertRaises(ValidationError):
            validate_lens_data_schema(_with("thickness", INF))

    def test_negative_infinite_refractive_index_is_rejected(self):
        with self.assertRaises(ValidationError):
            validate_lens_data_schema(_with("refractive_index", -INF))

    def test_nan_optional_field_is_rejected(self):
        """Optional fields get the same treatment."""
        with self.assertRaises(ValidationError):
            validate_lens_data_schema(_with("wavelength", NAN))

    def test_error_names_the_field_and_the_value(self):
        with self.assertRaises(ValidationError) as ctx:
            validate_lens_data_schema(_with("thickness", INF))
        message = str(ctx.exception)
        self.assertIn("thickness", message)
        self.assertIn("inf", message)

    def test_type_errors_are_still_reported_as_before(self):
        with self.assertRaises(ValidationError) as ctx:
            validate_lens_data_schema(_with("thickness", "thick"))
        self.assertIn("must be number", str(ctx.exception))

    def test_missing_field_is_still_reported(self):
        data = dict(CLEAN)
        del data["diameter"]
        with self.assertRaises(ValidationError) as ctx:
            validate_lens_data_schema(data)
        self.assertIn("Missing required field", str(ctx.exception))

    def test_the_nan_really_does_propagate_without_validation(self):
        """Pins why this matters: the NaN reaches the focal length."""
        data = _with("radius_of_curvature_1", NAN)
        lens = Lens.from_dict(data)
        focal = lens.calculate_focal_length()
        self.assertNotEqual(focal, focal)  # NaN != NaN
        self.assertNotEqual(focal, 0.0)

    def test_json_loads_the_nan_literal(self):
        """The premise: the bare literal parses."""
        self.assertNotEqual(json.loads('{"x": NaN}')["x"], json.loads('{"x": NaN}')["x"])
        self.assertEqual(json.loads('{"x": Infinity}')["x"], INF)


class TestRecursiveSweep(unittest.TestCase):
    def test_nan_at_the_top_level_is_rejected(self):
        with self.assertRaises(ValidationError):
            reject_non_finite_numbers({"a": NAN})

    def test_nan_nested_in_a_list_is_rejected(self):
        with self.assertRaises(ValidationError):
            reject_non_finite_numbers({"a": [1, 2, {"b": NAN}]})

    def test_infinite_deep_in_an_assembly_is_rejected(self):
        payload = {
            "elements": [{"lens": {"radius_of_curvature_1": 50.0}}, {"lens": {"thickness": INF}}]
        }
        with self.assertRaises(ValidationError):
            reject_non_finite_numbers(payload, "imported file")

    def test_error_reports_the_path(self):
        with self.assertRaises(ValidationError) as ctx:
            reject_non_finite_numbers({"elements": [{"lens": {"thickness": INF}}]})
        self.assertIn("elements", str(ctx.exception))
        self.assertIn("thickness", str(ctx.exception))

    def test_clean_nested_payload_passes(self):
        payload = {"elements": [{"lens": {"thickness": 5.0}}], "name": "S"}
        self.assertEqual(reject_non_finite_numbers(payload), payload)

    def test_booleans_are_not_treated_as_numbers(self):
        """bool is an int subclass; True must not be read as 1.0."""
        self.assertEqual(reject_non_finite_numbers({"flag": True}), {"flag": True})

    def test_strings_and_none_pass_through(self):
        payload = {"a": "text", "b": None, "c": [1, "x", None]}
        self.assertEqual(reject_non_finite_numbers(payload), payload)

    def test_integers_are_untouched(self):
        self.assertEqual(reject_non_finite_numbers({"a": 10**400}), {"a": 10**400})

    def test_returns_the_data_unchanged(self):
        payload = {"a": 1.5}
        self.assertIs(reject_non_finite_numbers(payload), payload)

    def test_empty_containers_pass(self):
        self.assertEqual(reject_non_finite_numbers({}), {})
        self.assertEqual(reject_non_finite_numbers([]), [])


class TestImportPathValidates(unittest.TestCase):
    """startup._on_import is the only JSON import in the application."""

    def _startup_source(self):
        import inspect

        from src.gui.dialogs.startup import StartupDialog

        return inspect.getsource(StartupDialog)

    def test_import_calls_the_finite_sweep(self):
        self.assertIn("reject_non_finite_numbers", self._startup_source())

    def test_import_validates_the_file_path(self):
        self.assertIn("validate_json_file_path", self._startup_source())

    def test_import_validates_the_lens_schema(self):
        self.assertIn("validate_lens_data_schema", self._startup_source())

    def test_a_nan_payload_would_now_be_refused(self):
        """End to end: what the import used to accept."""
        payload = json.dumps(_with("radius_of_curvature_1", NAN))
        decoded = json.loads(payload)
        with self.assertRaises(ValidationError):
            reject_non_finite_numbers(decoded, "imported file")
        with self.assertRaises(ValidationError):
            validate_lens_data_schema(decoded)


if __name__ == "__main__":
    unittest.main()
