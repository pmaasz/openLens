"""Tests for STEP assembly export (todo item 5)."""

import os
import tempfile
import unittest

from src.io.step_export import StepExporter
from src.io.step_reader import read_step_solids
from src.lens import Lens
from src.mechanical_designer import MechanicalDesigner
from src.optical_system import OpticalSystem


def _two_element_system():
    system = OpticalSystem(name="Housed System")
    system.add_lens(
        Lens(
            name="Front",
            radius_of_curvature_1=100.0,
            radius_of_curvature_2=-100.0,
            thickness=5.0,
            diameter=40.0,
            material="BK7",
        )
    )
    system.add_lens(Lens(name="Rear", diameter=25.0), air_gap_before=5.0)
    return system


class TestSuggestHousing(unittest.TestCase):
    def test_spacer_plus_barrel(self):
        """A two-lens system should suggest one spacer and one barrel."""
        parts = MechanicalDesigner(_two_element_system()).suggest_housing()
        self.assertEqual(len(parts), 2)
        spacer, barrel = parts
        self.assertIn("Spacer", spacer["name"])
        self.assertAlmostEqual(spacer["z0"], 5.0)
        self.assertAlmostEqual(spacer["z1"], 10.0)
        # Spacer bore clears the smaller neighbor; barrel bore the max OD.
        self.assertLessEqual(spacer["r_inner"] * 2, 25.0)
        self.assertGreaterEqual(spacer["r_outer"] * 2, 40.0)
        self.assertIn("Barrel", barrel["name"])
        self.assertAlmostEqual(barrel["z0"], -2.0)
        self.assertAlmostEqual(barrel["z1"], 15.0 + 2.0)

    def test_mount_thread_recorded(self):
        """A mount string should land in the barrel name as a thread spec."""
        parts = MechanicalDesigner(_two_element_system()).suggest_housing(
            mount="M42x1.0"
        )
        barrel = parts[-1]
        self.assertIn("M42x1.0", barrel["name"])

    def test_empty_system_suggests_nothing(self):
        """No elements means no housing parts."""
        self.assertEqual(MechanicalDesigner(OpticalSystem()).suggest_housing(), [])


class TestStepAssemblyRoundTrip(unittest.TestCase):
    def _export(self, system, housing):
        tmp = tempfile.NamedTemporaryFile(suffix=".step", delete=False, mode="w")
        tmp.close()
        StepExporter(system).export(tmp.name, housing=housing)
        return tmp.name

    def test_solids_round_trip(self):
        """Exported lenses + housing should read back with names and slabs."""
        system = _two_element_system()
        housing = MechanicalDesigner(system).suggest_housing()
        path = self._export(system, housing)
        try:
            solids = read_step_solids(path)
            names = [s["name"] for s in solids]
            self.assertEqual(len(solids), 2 + len(housing))
            self.assertIn("Front", names)
            self.assertIn("Rear", names)
            spacer = next(s for s in solids if s["name"].startswith("Spacer"))
            self.assertAlmostEqual(spacer["z_min"], 5.0, places=3)
            self.assertAlmostEqual(spacer["z_max"], 10.0, places=3)
            barrel = next(s for s in solids if s["name"].startswith("Barrel"))
            self.assertAlmostEqual(barrel["z_min"], -2.0, places=3)
            self.assertAlmostEqual(barrel["z_max"], 17.0, places=3)
        finally:
            os.unlink(path)

    def test_lens_only_export_still_reads(self):
        """Housing=None must keep the legacy lens-only behavior."""
        system = _two_element_system()
        path = self._export(system, None)
        try:
            solids = read_step_solids(path)
            self.assertEqual(len(solids), 2)
            self.assertEqual(solids[0]["name"], "Front")
        finally:
            os.unlink(path)

    def test_bad_tube_dims_skipped(self):
        """Degenerate housing parts should be skipped, not crash."""
        system = _two_element_system()
        housing = [
            {"name": "Bad", "z0": 5.0, "z1": 5.0, "r_inner": 10.0, "r_outer": 5.0}
        ]
        path = self._export(system, housing)
        try:
            solids = read_step_solids(path)
            self.assertEqual(len(solids), 2)
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
