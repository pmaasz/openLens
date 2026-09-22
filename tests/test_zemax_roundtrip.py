"""Tests for full-system Zemax export/import (todo item 7)."""

import os
import tempfile
import unittest

from src.export_formats import (
    ZemaxExporter,
    ZemaxSystemExporter,
    ZemaxSystemImporter,
)
from src.lens import Lens
from src.optical_system import OpticalSystem


def _system():
    system = OpticalSystem(name="Zemax RT")
    system.add_lens(
        Lens(
            name="A",
            radius_of_curvature_1=100.0,
            radius_of_curvature_2=-100.0,
            thickness=5.0,
            diameter=40.0,
            material="BK7",
            clear_aperture_1=36.0,
        )
    )
    system.add_lens(
        Lens(
            name="B",
            radius_of_curvature_1=80.0,
            radius_of_curvature_2=-80.0,
            thickness=4.0,
            diameter=30.0,
            material="BK7",
        ),
        air_gap_before=10.0,
    )
    system.set_aperture_stop(0, 20.0)
    return system


def _export_path(system):
    tmp = tempfile.NamedTemporaryFile(suffix=".zmx", delete=False, mode="w")
    tmp.close()
    ZemaxSystemExporter.export_system(system, tmp.name)
    return tmp.name


class TestZemaxSystemExport(unittest.TestCase):
    def test_file_structure(self):
        """Export should list OBJ, element surfaces, STOP, and image."""
        path = _export_path(_system())
        try:
            with open(path) as f:
                content = f.read()
            self.assertIn("MODE SEQ", content)
            self.assertIn("STOP", content)
            self.assertIn("DIAM 20.0", content)
            self.assertIn("GLAS BK7", content)
            # Two elements -> OBJ + 2x2 surfaces + STOP + image = 7 SURF blocks.
            self.assertEqual(content.count("SURF "), 7)
        finally:
            os.unlink(path)

    def test_stopless_system_has_no_stop_surface(self):
        """Systems without a stop should export no STOP block."""
        system = _system()
        system.clear_aperture_stop()
        path = _export_path(system)
        try:
            with open(path) as f:
                content = f.read()
            self.assertNotIn("STOP", content)
        finally:
            os.unlink(path)


class TestZemaxSystemImport(unittest.TestCase):
    def test_round_trip_preserves_system(self):
        """Export->import should preserve geometry, gaps, CA, and stop."""
        original = _system()
        path = _export_path(original)
        try:
            rebuilt = ZemaxSystemImporter.import_system(path)
        finally:
            os.unlink(path)
        self.assertEqual(len(rebuilt.elements), 2)
        self.assertEqual(len(rebuilt.air_gaps), 1)
        self.assertAlmostEqual(rebuilt.air_gaps[0].thickness, 10.0)
        front = rebuilt.elements[0].lens
        self.assertAlmostEqual(front.radius_of_curvature_1, 100.0)
        self.assertAlmostEqual(front.radius_of_curvature_2, -100.0)
        self.assertAlmostEqual(front.thickness, 5.0)
        self.assertEqual(front.material, "BK7")
        self.assertEqual(front.clear_aperture_1, 36.0)
        stop = rebuilt.get_aperture_stop()
        self.assertIsNotNone(stop)
        self.assertEqual(stop["gap_index"], 0)
        self.assertEqual(stop["diameter"], 20.0)
        self.assertAlmostEqual(
            rebuilt.get_system_focal_length(),
            original.get_system_focal_length(),
            places=3,
        )

    def test_single_lens_file_imports(self):
        """Single-lens exports should import as one-element systems."""
        lens = Lens(
            name="Single",
            radius_of_curvature_1=51.5,
            radius_of_curvature_2=-51.5,
            thickness=5.0,
            diameter=25.4,
            material="BK7",
        )
        tmp = tempfile.NamedTemporaryFile(suffix=".zmx", delete=False, mode="w")
        tmp.close()
        try:
            ZemaxExporter.export_lens(lens, tmp.name)
            rebuilt = ZemaxSystemImporter.import_system(tmp.name)
        finally:
            os.unlink(tmp.name)
        self.assertEqual(len(rebuilt.elements), 1)
        self.assertAlmostEqual(rebuilt.elements[0].lens.radius_of_curvature_1, 51.5, places=6)

    def test_foreign_keywords_ignored(self):
        """Unknown keywords and comments should not break the import."""
        tmp = tempfile.NamedTemporaryFile(suffix=".zmx", delete=False, mode="w")
        tmp.close()
        try:
            with open(tmp.name, "w") as f:
                f.write(
                    "! foreign file\nVERS 200000\nMODE SEQ\n\n"
                    "SURF 0\n  TYPE STANDARD\n  CURV 0.0\n  DISZ INFINITY\n"
                    "  COMM some comment line\n\n"
                    "SURF 1\n  TYPE STANDARD\n  CURV 0.02\n  DISZ 4.0\n"
                    "  DIAM 25.0\n  GLAS BK7\n  MAZH made-up keyword\n\n"
                    "SURF 2\n  TYPE STANDARD\n  CURV -0.02\n  DIAM 25.0\n"
                    "  DISZ 100.0\n\n"
                    "SURF 3\n  TYPE STANDARD\n"
                )
            rebuilt = ZemaxSystemImporter.import_system(tmp.name)
        finally:
            os.unlink(tmp.name)
        self.assertEqual(len(rebuilt.elements), 1)
        self.assertAlmostEqual(rebuilt.elements[0].lens.radius_of_curvature_1, 50.0)


if __name__ == "__main__":
    unittest.main()
