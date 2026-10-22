"""#647: the CLI modify path must enforce the same feasibility rule as create.

``create_lens`` refuses a lens whose surfaces intersect inside the clear
aperture. ``modify_lens`` validated each field on its own, wrote them into the
lens as they were read, and saved: the same geometry could be updated into the
database and the user was told "Lens updated successfully!". The edit must be
checked as a whole and applied atomically.
"""

import os
import tempfile
import unittest
from unittest import mock

from openlens.lens import Lens
from openlens.lens_editor import LensManager


class TestModifyLensValidation(unittest.TestCase):
    def setUp(self):
        handle, self.storage_file = tempfile.mkstemp(suffix=".json")
        os.close(handle)
        self.addCleanup(self._cleanup)
        self.manager = LensManager(storage_file=self.storage_file)
        self.lens = Lens(
            name="demo",
            radius_of_curvature_1=100.0,
            radius_of_curvature_2=-100.0,
            thickness=5.0,
            diameter=50.0,
            refractive_index=1.5168,
            material="BK7",
        )
        self.manager.lenses = [self.lens]

    def _cleanup(self):
        base = self.storage_file.replace(".json", ".db")
        for path in (base, base + "-shm", base + "-wal", self.storage_file):
            if os.path.exists(path):
                os.unlink(path)

    def _run_modify(self, answers):
        with mock.patch("builtins.input", side_effect=answers):
            with mock.patch.object(self.manager, "save_lenses") as save:
                self.manager.modify_lens()
        return save

    def test_an_infeasible_edit_is_refused_and_nothing_is_applied(self):
        answers = ["1", "changed", "20", "-20", "5", "40", "1.6", "Biconcave", "Fused Silica"]

        save = self._run_modify(answers)

        self.assertEqual(self.lens.name, "demo")
        self.assertEqual(self.lens.radius_of_curvature_1, 100.0)
        self.assertEqual(self.lens.radius_of_curvature_2, -100.0)
        self.assertEqual(self.lens.thickness, 5.0)
        self.assertEqual(self.lens.diameter, 50.0)
        self.assertEqual(self.lens.refractive_index, 1.5168)
        self.assertEqual(self.lens.lens_type, "Biconvex")
        self.assertEqual(self.lens.material, "BK7")
        save.assert_not_called()

    def test_a_feasible_edit_is_applied_and_saved(self):
        answers = ["1", "renamed", "80", "-80", "6", "40", "1.6", "Biconcave", "Fused Silica"]

        save = self._run_modify(answers)

        self.assertEqual(self.lens.name, "renamed")
        self.assertEqual(self.lens.radius_of_curvature_1, 80.0)
        self.assertEqual(self.lens.radius_of_curvature_2, -80.0)
        self.assertEqual(self.lens.thickness, 6.0)
        self.assertEqual(self.lens.diameter, 40.0)
        self.assertEqual(self.lens.refractive_index, 1.6)
        self.assertEqual(self.lens.lens_type, "Biconcave")
        self.assertEqual(self.lens.material, "Fused Silica")
        save.assert_called_once()

    def test_an_invalid_single_field_keeps_the_current_value(self):
        answers = ["1", "", "not-a-number", "-80", "6", "40", "", "", ""]

        save = self._run_modify(answers)

        self.assertEqual(self.lens.radius_of_curvature_1, 100.0)
        self.assertEqual(self.lens.radius_of_curvature_2, -80.0)
        self.assertEqual(self.lens.thickness, 6.0)
        self.assertEqual(self.lens.diameter, 40.0)
        save.assert_called_once()


if __name__ == "__main__":
    unittest.main()
