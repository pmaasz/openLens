"""#661: read_step_solids() must report the solid's extent, not its curvature centres."""

import os
import tempfile
import unittest

from openlens.io.step_export import StepExporter
from openlens.io.step_reader import read_step_solids
from openlens.lens import Lens
from openlens.optical_system import OpticalSystem


class TestStepReaderLensExtent(unittest.TestCase):
    def test_a_lens_solid_reports_its_axial_extent(self):
        system = OpticalSystem()
        system.add_lens(
            Lens(
                name="Front",
                radius_of_curvature_1=50.0,
                radius_of_curvature_2=-50.0,
                thickness=5.0,
                diameter=25.0,
            )
        )

        tmp = tempfile.NamedTemporaryFile(suffix=".step", delete=False, mode="w")
        tmp.close()
        try:
            StepExporter(system).export(tmp.name)
            solids = read_step_solids(tmp.name)
            self.assertEqual(len(solids), 1)
            lens = solids[0]
            self.assertEqual(lens["name"], "Front")
            self.assertAlmostEqual(lens["z_min"], 0.0, places=6)
            self.assertAlmostEqual(lens["z_max"], 5.0, places=6)
        finally:
            os.unlink(tmp.name)

    def test_sphere_centre_points_are_excluded_from_the_point_cloud(self):
        system = OpticalSystem()
        system.add_lens(
            Lens(
                name="Front",
                radius_of_curvature_1=50.0,
                radius_of_curvature_2=-50.0,
                thickness=5.0,
                diameter=25.0,
            )
        )

        tmp = tempfile.NamedTemporaryFile(suffix=".step", delete=False, mode="w")
        tmp.close()
        try:
            StepExporter(system).export(tmp.name)
            solids = read_step_solids(tmp.name)
            zs = [p[2] for p in solids[0]["points"]]
            self.assertTrue(all(-1e-9 <= z <= 5.0 + 1e-9 for z in zs))
        finally:
            os.unlink(tmp.name)


if __name__ == "__main__":
    unittest.main()
