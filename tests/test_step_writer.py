#!/usr/bin/env python3
"""
Direct coverage for the low-level STEP writer (StepWriter).

test_step_export.py / test_step_export_multi.py only exercise
StepExporter; the ISO-10303-21 text assembly itself was untested.
"""

import os
import re
import tempfile
import unittest

from src.io.step_export import StepWriter


class TestStepWriter(unittest.TestCase):
    """Low-level STEP file assembly"""

    def setUp(self):
        self.writer = StepWriter()

    def _write_to_tmp(self):
        fd, path = tempfile.mkstemp(suffix=".step")
        os.close(fd)
        self.addCleanup(os.unlink, path)
        with open(path, "w") as f:
            f.write(self.writer.generate())
        return path

    def test_entity_ids_sequential_from_one(self):
        """add_entity returns monotonically increasing ids starting at 1"""
        ids = [
            self.writer.add_entity("CARTESIAN_POINT", ["'P'", (0.0, 0.0, 0.0)]) for _ in range(5)
        ]
        self.assertEqual(ids, [1, 2, 3, 4, 5])

    def test_written_file_contains_header_and_entities(self):
        """File has ISO-10303-21 header and one referenced line per entity"""
        self.writer.add_entity("CARTESIAN_POINT", ["'Origin'", (0.0, 0.0, 0.0)])
        path = self._write_to_tmp()
        with open(path) as f:
            content = f.read()
        self.assertIn("ISO-10303-21", content)
        self.assertIn("#1=CARTESIAN_POINT", content)

    def test_numeric_and_string_arguments_rendered(self):
        """Floats render unquoted, plain strings get quoted, refs pass through"""
        self.writer.add_entity("ADVANCED_FACE", ["'Name'", 1.5, "#12", ".T."])
        path = self._write_to_tmp()
        with open(path) as f:
            content = f.read()
        line = re.search(r"#1=ADVANCED_FACE\((.*)\);", content).group(1)
        args = [a.strip() for a in line.split(",")]
        self.assertEqual(args[0], "'Name'")
        self.assertTrue(args[1].startswith("1.5"))  # floats render 6-decimal
        self.assertEqual(args[2], "#12")
        self.assertEqual(args[3], ".T.")

    def test_special_tokens_pass_through(self):
        """'*' (derived), '$' (unset) are emitted verbatim"""
        self.writer.add_entity("SOMETHING", ["*", "$"])
        path = self._write_to_tmp()
        with open(path) as f:
            content = f.read()
        self.assertIn("#1=SOMETHING(*,$);", content)


if __name__ == "__main__":
    unittest.main()
