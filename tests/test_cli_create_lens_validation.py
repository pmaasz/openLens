"""#475: the interactive CLI must apply the same validators as the GUI.

``create_lens`` prompted for values, built a ``Lens`` and appended it without
``validate_lens_name`` or ``check_physical_feasibility`` - both of which the
GUI applies before it accepts the same parameters. A 101-character name or a
lens whose surfaces intersect inside the clear aperture was saved happily.
"""

import os
import tempfile
import unittest
from unittest import mock

from openlens.constants import MIN_EDGE_THICKNESS
from openlens.lens import Lens
from openlens.lens_editor import LensManager


class TestCreateLensValidation(unittest.TestCase):
    def setUp(self):
        handle, self.storage_file = tempfile.mkstemp(suffix=".json")
        os.close(handle)
        self.addCleanup(self._cleanup)
        self.manager = LensManager(storage_file=self.storage_file)

    def _cleanup(self):
        base = self.storage_file.replace(".json", ".db")
        for path in (base, base + "-shm", base + "-wal", self.storage_file):
            if os.path.exists(path):
                os.unlink(path)

    def _run_create(self, answers):
        with mock.patch("builtins.input", side_effect=answers):
            return self.manager.create_lens()

    def test_a_name_over_the_limit_is_rejected_and_not_saved(self):
        result = self._run_create(["x" * 101])

        self.assertIsNone(result)
        self.assertEqual(self.manager.lenses, [])

    def test_an_infeasible_lens_is_rejected_and_not_saved(self):
        result = self._run_create(["Bad", "50", "-50", "1", "100", "1.5168", "Biconvex", "BK7"])

        self.assertIsNone(result)
        self.assertEqual(self.manager.lenses, [])

    def test_the_prompt_defaults_create_a_feasible_lens(self):
        """#648: pressing Enter on every prompt must produce a valid lens."""
        lens = self._run_create(["demo", "", "", "", "", "", "", ""])

        self.assertIsInstance(lens, Lens)
        self.assertEqual(lens.name, "demo")
        self.assertEqual(len(self.manager.lenses), 1)
        self.assertGreaterEqual(lens.calculate_edge_thickness(), MIN_EDGE_THICKNESS)

    def test_a_feasible_lens_is_still_created(self):
        lens = self._run_create(["Good", "50", "-50", "5", "25", "1.5168", "Biconvex", "BK7"])

        self.assertIsInstance(lens, Lens)
        self.assertEqual(lens.name, "Good")
        self.assertEqual(len(self.manager.lenses), 1)


if __name__ == "__main__":
    unittest.main()
