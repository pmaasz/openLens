#!/usr/bin/env python3
"""
A silently-missing STEP part must be reported, not logged at DEBUG.

Three skip paths in StepExporter logged at logger.debug, which is invisible at
default verbosity:

    logger.debug("STEP housing part skipped: %s", e)
    logger.debug("STEP solid export skipped: %s", e)
    logger.debug("STEP tube export skipped (bad dims): %s", name)

So a malformed spacer/barrel dict produced a mechanical STEP drawing with
parts quietly absent - and for an assembly drawing that is a part you cannot
assemble.

Skips are now logged at WARNING with the part name (and, for bad dimensions,
the values), and export() returns a summary dict. It previously returned None,
so every existing caller - which ignores the result - is unaffected.
"""

import logging
import os
import tempfile
import unittest

from src.io.step_export import StepExporter
from src.lens import Lens
from src.optical_system import OpticalSystem


def _system():
    system = OpticalSystem(name="S")
    system.add_lens(
        Lens(
            name="L1",
            radius_of_curvature_1=50.0,
            radius_of_curvature_2=-50.0,
            thickness=5.0,
            diameter=25.0,
            refractive_index=1.5,
        )
    )
    return system


GOOD = {"name": "barrel", "z0": 0.0, "z1": 30.0, "r_inner": 10.0, "r_outer": 14.0}
SPACER = {"name": "spacer", "z0": 5.0, "z1": 8.0, "r_inner": 6.0, "r_outer": 9.0}
BAD_DIMS = {"name": "bad_dims", "z0": 5.0, "z1": 1.0, "r_inner": 10.0, "r_outer": 8.0}


class _ExportFixture(unittest.TestCase):
    def _export(self, housing=None):
        handle, path = tempfile.mkstemp(suffix=".step")
        os.close(handle)
        self.addCleanup(os.unlink, path)
        result = StepExporter(_system()).export(path, housing=housing)
        with open(path, encoding="utf-8") as f:
            return result, f.read()

    def _capture(self, level=logging.WARNING):
        """Run an export with logging captured at `level`."""
        records = []

        class Handler(logging.Handler):
            def emit(self, record):
                records.append(record)

        logger = logging.getLogger("src.io.step_export")
        handler = Handler()
        handler.setLevel(level)
        logger.addHandler(handler)
        old_level = logger.level
        logger.setLevel(level)
        try:
            result, text = self._export(housing=self.housing)
        finally:
            logger.removeHandler(handler)
            logger.setLevel(old_level)
        return result, text, records

    def _messages(self, records):
        return " ".join(r.getMessage() for r in records)


class TestExportSummary(_ExportFixture):
    def test_returns_a_summary_dict(self):
        result, _ = self._export(housing=[GOOD, SPACER])
        self.assertEqual(set(result), {"shapes", "skipped", "skipped_parts"})
        self.assertEqual(result["skipped"], 0)
        self.assertEqual(result["skipped_parts"], [])

    def test_counts_written_solids(self):
        result, text = self._export(housing=[GOOD, SPACER])
        self.assertEqual(result["shapes"], 3)  # one lens + two tubes
        self.assertIn("MANIFOLD_SOLID_BREP", text)

    def test_counts_skipped_parts(self):
        result, _ = self._export(housing=[GOOD, {"name": "MISSING_KEYS"}, BAD_DIMS])
        self.assertEqual(result["skipped"], 2)
        self.assertEqual(result["skipped_parts"], ["MISSING_KEYS", "bad_dims"])

    def test_no_housing_reports_no_skips(self):
        result, _ = self._export()
        self.assertEqual(result["skipped"], 0)

    def test_file_is_still_written_when_parts_are_skipped(self):
        result, text = self._export(housing=[{"name": "MISSING_KEYS"}])
        self.assertTrue(text.strip())
        self.assertIn("ISO-10303-21", text)


class TestSkipLogging(_ExportFixture):
    def setUp(self):
        self.housing = [GOOD, {"name": "MISSING_KEYS"}, BAD_DIMS, SPACER]

    def test_malformed_part_is_logged_at_warning(self):
        """Regression: logger.debug, invisible at default verbosity."""
        _, _, records = self._capture(logging.WARNING)
        warnings = [r for r in records if r.levelno >= logging.WARNING]
        self.assertTrue(warnings)
        self.assertIn("MISSING_KEYS", self._messages(warnings))

    def test_bad_dimensions_are_logged_at_warning(self):
        _, _, records = self._capture(logging.WARNING)
        warnings = [r for r in records if r.levelno >= logging.WARNING]
        self.assertIn("bad_dims", self._messages(warnings))

    def test_bad_dimension_message_includes_the_values(self):
        _, _, records = self._capture(logging.WARNING)
        message = self._messages(records)
        self.assertIn("r_inner=10.0", message)
        self.assertIn("r_outer=8.0", message)

    def test_summary_line_names_every_skipped_part(self):
        _, _, records = self._capture(logging.WARNING)
        self.assertIn("skipped 2 part", self._messages(records))

    def test_nothing_is_logged_when_all_parts_are_good(self):
        self.housing = [GOOD, SPACER]
        _, _, records = self._capture(logging.WARNING)
        warnings = [r for r in records if r.levelno >= logging.WARNING]
        self.assertEqual([r.getMessage() for r in warnings], [])

    def test_debug_level_is_no_longer_the_only_report(self):
        """The old code logged at DEBUG; assert it is now at WARNING or above."""
        _, _, records = self._capture(logging.DEBUG)
        skips = [
            r for r in records if "MISSING_KEYS" in r.getMessage() or "bad_dims" in r.getMessage()
        ]
        self.assertTrue(skips)
        for record in skips:
            self.assertGreaterEqual(record.levelno, logging.WARNING)


class TestUsableObjectWithoutAttributes(unittest.TestCase):
    def test_unsupported_object_is_reported(self):
        handle, path = tempfile.mkstemp(suffix=".step")
        os.close(handle)
        self.addCleanup(os.unlink, path)

        records = []

        class Handler(logging.Handler):
            def emit(self, record):
                records.append(record)

        logger = logging.getLogger("src.io.step_export")
        handler = Handler()
        logger.addHandler(handler)
        try:
            result = StepExporter(object()).export(path)
        finally:
            logger.removeHandler(handler)

        self.assertEqual(result["skipped"], 1)
        self.assertTrue(any(r.levelno >= logging.WARNING for r in records), "no warning emitted")


if __name__ == "__main__":
    unittest.main()
