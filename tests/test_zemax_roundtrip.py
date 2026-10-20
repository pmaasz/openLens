"""Tests for full-system Zemax export/import (todo item 7)."""

import math
import os
import tempfile
import unittest

from openlens.export_formats import (
    ZemaxExporter,
    ZemaxSystemExporter,
    ZemaxSystemImporter,
)
from openlens.lens import Lens
from openlens.optical_system import OpticalSystem


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
            self.assertIn("DIAM 10.0", content)  # stop 20 mm -> 10 mm semi-diameter
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


class TestZemaxSystemImportValidation(unittest.TestCase):
    """A .zmx file is untrusted input; impossible elements must not be imported."""

    @staticmethod
    def _import(text):
        tmp = tempfile.NamedTemporaryFile(suffix=".zmx", delete=False, mode="w")
        tmp.close()
        try:
            with open(tmp.name, "w") as f:
                f.write(text)
            return ZemaxSystemImporter.import_system(tmp.name)
        finally:
            os.unlink(tmp.name)

    @staticmethod
    def _zmx(front_curv="0.02", disz="5.0", front_diam="25.0", back_diam="25.0"):
        return (
            "VERS 200000\nMODE SEQ\nUNIT MM\n\n"
            "SURF 0\n  TYPE STANDARD\n  CURV 0.0\n  DISZ INFINITY\n\n"
            f"SURF 1\n  TYPE STANDARD\n  CURV {front_curv}\n  DISZ {disz}\n"
            f"  GLAS BK7\n  DIAM {front_diam}\n\n"
            f"SURF 2\n  TYPE STANDARD\n  CURV -0.02\n  DIAM {back_diam}\n  DISZ 50.0\n\n"
            "SURF 3\n  TYPE STANDARD\n  CURV 0.0\n  DISZ 0.0\n"
        )

    def test_negative_thickness_element_is_skipped(self):
        """DISZ -5.0 must not produce a negative-thickness lens."""
        rebuilt = self._import(self._zmx(disz="-5.0"))
        self.assertEqual(len(rebuilt.elements), 0)

    def test_clear_aperture_exceeding_diameter_is_skipped(self):
        """A CA1 larger than DIAM must be rejected, not imported."""
        rebuilt = self._import(self._zmx(front_diam="999.0", back_diam="1.0"))
        self.assertEqual(len(rebuilt.elements), 0)

    def test_non_positive_diameter_is_skipped(self):
        """A negative mechanical diameter must be rejected."""
        rebuilt = self._import(self._zmx(front_diam="-25.0"))
        self.assertEqual(len(rebuilt.elements), 0)

    def test_plano_surface_still_imports(self):
        """CURV 0.0 means a legitimate plano surface, not an invalid value."""
        rebuilt = self._import(self._zmx(front_curv="0.0"))
        self.assertEqual(len(rebuilt.elements), 1)
        self.assertEqual(rebuilt.elements[0].lens.radius_of_curvature_1, float("inf"))

    def test_valid_element_still_imports(self):
        """A well-formed element must survive the new validation."""
        rebuilt = self._import(self._zmx())
        self.assertEqual(len(rebuilt.elements), 1)
        lens = rebuilt.elements[0].lens
        self.assertAlmostEqual(lens.radius_of_curvature_1, 50.0, places=6)
        self.assertAlmostEqual(lens.thickness, 5.0)
        self.assertEqual(lens.material, "BK7")

    def test_one_bad_element_does_not_discard_the_good_one(self):
        """A rejected element must not take the rest of the system with it."""
        text = (
            "VERS 200000\nMODE SEQ\nUNIT MM\n\n"
            "SURF 0\n  TYPE STANDARD\n  CURV 0.0\n  DISZ INFINITY\n\n"
            "SURF 1\n  TYPE STANDARD\n  CURV 0.02\n  DISZ -5.0\n"
            "  GLAS BK7\n  DIAM 25.0\n\n"
            "SURF 2\n  TYPE STANDARD\n  CURV -0.02\n  DIAM 25.0\n  DISZ 50.0\n\n"
            "SURF 3\n  TYPE STANDARD\n  CURV 0.02\n  DISZ 4.0\n"
            "  GLAS BK7\n  DIAM 30.0\n\n"
            "SURF 4\n  TYPE STANDARD\n  CURV -0.02\n  DIAM 30.0\n  DISZ 0.0\n"
        )
        rebuilt = self._import(text)
        self.assertEqual(len(rebuilt.elements), 1)
        self.assertAlmostEqual(rebuilt.elements[0].lens.thickness, 4.0)


# NOTE: the preset-JSON validation added for #358 lived on
# PresetLensLibrary.import_custom_preset in openlens/preset_lenses.py, which this
# branch retires in favour of the typed PresetLibrary. The untrusted-JSON
# trust boundary it guarded no longer exists, so those tests went with it.
# The Zemax half of #358 (per-element validation in
# ZemaxSystemImporter) is unaffected and still covered above.


def _import_text(text):
    """Write a .zmx body to a temp file and import it."""
    tmp = tempfile.NamedTemporaryFile(suffix=".zmx", delete=False, mode="w")
    tmp.close()
    try:
        with open(tmp.name, "w") as f:
            f.write(text)
        return ZemaxSystemImporter.import_system(tmp.name)
    finally:
        os.unlink(tmp.name)


def _singlet_zmx(front_diam="25.0", back_diam="25.0", front_stop=False, back_stop=False):
    """A one-element FOREIGN .zmx body, with all parameters spelled out."""
    front = "  STOP\n" if front_stop else ""
    back = "  STOP\n" if back_stop else ""
    return (
        "VERS 200000\nMODE SEQ\nUNIT MM\n\n"
        "SURF 0\n  TYPE STANDARD\n  CURV 0.0\n  DISZ INFINITY\n\n"
        f"SURF 1\n  TYPE STANDARD\n{front}  CURV 0.02\n  DISZ 5.0\n"
        f"  DIAM {front_diam}\n  GLAS BK7\n\n"
        f"SURF 2\n  TYPE STANDARD\n{back}  CURV -0.02\n  DIAM {back_diam}\n  DISZ 50.0\n\n"
        "SURF 3\n  TYPE STANDARD\n  CURV 0.0\n  DISZ 0.0\n"
    )


class TestZemaxStopAndDiameter(unittest.TestCase):
    """#436: STOP is a surface flag, and DIAM is a semi-diameter."""

    def test_stop_on_the_front_surface_does_not_drop_the_element(self):
        """A front surface that is also the stop must still open an element."""
        rebuilt = _import_text(_singlet_zmx(front_stop=True))

        self.assertEqual(len(rebuilt.elements), 1)
        lens = rebuilt.elements[0].lens
        self.assertAlmostEqual(lens.radius_of_curvature_1, 50.0)
        self.assertAlmostEqual(lens.thickness, 5.0)
        self.assertEqual(lens.material, "BK7")

    def test_stop_on_the_back_surface_does_not_drop_the_element(self):
        """The same flag on the closing surface must not skip it either."""
        rebuilt = _import_text(_singlet_zmx(back_stop=True))

        self.assertEqual(len(rebuilt.elements), 1)
        self.assertAlmostEqual(rebuilt.elements[0].lens.radius_of_curvature_2, -50.0)

    def test_diam_is_read_as_a_semi_diameter(self):
        """A foreign DIAM 12.5 is a 25 mm aperture, not a 12.5 mm lens."""
        rebuilt = _import_text(_singlet_zmx(front_diam="12.5", back_diam="12.5"))

        lens = rebuilt.elements[0].lens
        self.assertEqual(lens.diameter, 25.0)
        self.assertEqual(lens.clear_aperture_1, 25.0)
        self.assertEqual(lens.clear_aperture_2, 25.0)

    def test_stop_diam_is_read_as_a_semi_diameter(self):
        """A STOP surface's DIAM 10 is a 20 mm stop."""
        text = (
            "VERS 200000\nMODE SEQ\nUNIT MM\n\n"
            "SURF 0\n  TYPE STANDARD\n  CURV 0.0\n  DISZ INFINITY\n\n"
            "SURF 1\n  TYPE STANDARD\n  CURV 0.02\n  DISZ 5.0\n"
            "  DIAM 12.5\n  GLAS BK7\n\n"
            "SURF 2\n  TYPE STANDARD\n  CURV -0.02\n  DIAM 12.5\n  DISZ 4.0\n\n"
            "SURF 3\n  TYPE STANDARD\n  STOP\n  CURV 0.0\n  DIAM 10.0\n  DISZ 2.0\n\n"
            "SURF 4\n  TYPE STANDARD\n  CURV 0.02\n  DISZ 4.0\n"
            "  DIAM 15.0\n  GLAS BK7\n\n"
            "SURF 5\n  TYPE STANDARD\n  CURV -0.02\n  DIAM 15.0\n  DISZ 10.0\n\n"
            "SURF 6\n  TYPE STANDARD\n"
        )

        rebuilt = _import_text(text)

        self.assertEqual(len(rebuilt.elements), 2)
        stop = rebuilt.get_aperture_stop()
        self.assertIsNotNone(stop)
        self.assertEqual(stop["diameter"], 20.0)

    def test_export_writes_diam_as_a_semi_diameter(self):
        """OpenLens stores full apertures; .zmx DIAM is half of them."""
        path = _export_path(_system())
        try:
            with open(path) as f:
                content = f.read()
        finally:
            os.unlink(path)

        self.assertIn("DIAM 18.0", content)  # element 0 front CA 36 / 2
        self.assertIn("DIAM 10.0", content)  # stop 20 / 2
        self.assertNotIn("DIAM 36.0", content)

    def test_single_lens_export_writes_diam_as_a_semi_diameter(self):
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
            with open(tmp.name) as f:
                content = f.read()
        finally:
            os.unlink(tmp.name)

        self.assertIn("DIAM 12.7", content)
        self.assertNotIn("DIAM 25.4", content)


class TestZemaxParabolicSurfaces(unittest.TestCase):
    """#436: a parabola needs both its vertex radius and CONI -1."""

    @staticmethod
    def _parabolic_lens():
        return Lens(
            name="Parabolic",
            radius_of_curvature_1=100.0,
            radius_of_curvature_2=-100.0,
            thickness=5.0,
            diameter=20.0,
            material="BK7",
            is_parabolic_1=True,
            # Sag at the 10 mm semi-diameter. Vertex R = 10² / (2·1.25) = 40.
            parabolic_sag_1=1.25,
        )

    def test_parabolic_surface_exports_vertex_radius_and_conic(self):
        tmp = tempfile.NamedTemporaryFile(suffix=".zmx", delete=False, mode="w")
        tmp.close()
        try:
            ZemaxExporter.export_lens(self._parabolic_lens(), tmp.name)
            with open(tmp.name) as f:
                content = f.read()
        finally:
            os.unlink(tmp.name)

        self.assertIn("CURV 0.025", content)
        self.assertIn("CONI -1", content)

    def test_spherical_surface_exports_no_conic(self):
        lens = self._parabolic_lens()
        lens.is_parabolic_1 = False
        tmp = tempfile.NamedTemporaryFile(suffix=".zmx", delete=False, mode="w")
        tmp.close()
        try:
            ZemaxExporter.export_lens(lens, tmp.name)
            with open(tmp.name) as f:
                content = f.read()
        finally:
            os.unlink(tmp.name)

        self.assertNotIn("CONI", content)

    def test_parabolic_surface_round_trips(self):
        """Exporting CONI -1 is only half the job; import must restore it."""
        tmp = tempfile.NamedTemporaryFile(suffix=".zmx", delete=False, mode="w")
        tmp.close()
        try:
            ZemaxExporter.export_lens(self._parabolic_lens(), tmp.name)
            rebuilt = ZemaxSystemImporter.import_system(tmp.name)
        finally:
            os.unlink(tmp.name)

        lens = rebuilt.elements[0].lens
        self.assertTrue(lens.is_parabolic_1)
        self.assertAlmostEqual(lens.parabolic_sag_1, 1.25)
        self.assertAlmostEqual(lens.get_effective_radius_1(), 40.0)


class TestZemaxMaterialsWithSpaces(unittest.TestCase):
    """#436: 'Fused Silica' must not become 'Fused'."""

    def test_foreign_material_name_keeps_every_word(self):
        text = _singlet_zmx().replace("GLAS BK7", "GLAS Fused Silica")

        rebuilt = _import_text(text)

        lens = rebuilt.elements[0].lens
        self.assertEqual(lens.material, "Fused Silica")
        self.assertAlmostEqual(lens.refractive_index, 1.4585)

    def test_material_name_lookup_ignores_case(self):
        """Preserving case must not cost the catalog lookup."""
        text = _singlet_zmx().replace("GLAS BK7", "GLAS fused silica")

        rebuilt = _import_text(text)

        lens = rebuilt.elements[0].lens
        self.assertEqual(lens.material, "fused silica")
        self.assertAlmostEqual(lens.refractive_index, 1.4585)

    def test_export_quotes_a_material_name_with_spaces(self):
        lens = Lens(
            name="Silica",
            radius_of_curvature_1=100.0,
            radius_of_curvature_2=-100.0,
            thickness=5.0,
            diameter=20.0,
            material="Fused Silica",
        )
        tmp = tempfile.NamedTemporaryFile(suffix=".zmx", delete=False, mode="w")
        tmp.close()
        try:
            ZemaxExporter.export_lens(lens, tmp.name)
            with open(tmp.name) as f:
                content = f.read()
        finally:
            os.unlink(tmp.name)

        self.assertIn('GLAS "Fused Silica"', content)

    def test_quoted_material_name_round_trips(self):
        lens = Lens(
            name="Silica",
            radius_of_curvature_1=100.0,
            radius_of_curvature_2=-100.0,
            thickness=5.0,
            diameter=20.0,
            material="Fused Silica",
        )
        tmp = tempfile.NamedTemporaryFile(suffix=".zmx", delete=False, mode="w")
        tmp.close()
        try:
            ZemaxExporter.export_lens(lens, tmp.name)
            rebuilt = ZemaxSystemImporter.import_system(tmp.name)
        finally:
            os.unlink(tmp.name)

        imported = rebuilt.elements[0].lens
        self.assertEqual(imported.material, "Fused Silica")
        self.assertAlmostEqual(imported.refractive_index, 1.4585)


if __name__ == "__main__":
    unittest.main()


class TestZemaxConicSurfaces(unittest.TestCase):
    """#74: non-parabolic CONI values must survive an import/export round-trip."""

    def test_import_preserves_a_non_parabolic_conic_constant(self):
        text = _singlet_zmx().replace(
            "  CURV 0.02\n  DISZ 5.0\n", "  CURV 0.02\n  CONI -0.5\n  DISZ 5.0\n"
        )
        rebuilt = _import_text(text)
        lens = rebuilt.elements[0].lens

        self.assertFalse(lens.is_parabolic_1)
        self.assertAlmostEqual(lens.conic_constant_1, -0.5)
        expected = 2.0 / (1.0 + math.sqrt(1.0 - 0.5 * (0.02 * 10.0) ** 2))
        self.assertAlmostEqual(lens.get_sag_1(10.0), expected, places=4)

    def test_export_writes_a_non_parabolic_conic_constant(self):
        lens = Lens(
            radius_of_curvature_1=50.0,
            radius_of_curvature_2=-50.0,
            thickness=5.0,
            diameter=20.0,
            conic_constant_1=-0.5,
        )
        tmp = tempfile.NamedTemporaryFile(suffix=".zmx", delete=False, mode="w")
        tmp.close()
        try:
            ZemaxExporter.export_lens(lens, tmp.name)
            with open(tmp.name) as f:
                content = f.read()
        finally:
            os.unlink(tmp.name)

        self.assertIn("CONI -0.5", content)

    def test_system_export_writes_conic_constants(self):
        system = OpticalSystem(name="Conic system")
        system.add_lens(
            Lens(
                radius_of_curvature_1=50.0,
                radius_of_curvature_2=-50.0,
                thickness=5.0,
                diameter=20.0,
                conic_constant_1=-0.5,
                conic_constant_2=0.25,
            )
        )
        path = _export_path(system)
        try:
            with open(path) as f:
                content = f.read()
        finally:
            os.unlink(path)

        self.assertIn("CONI -0.5", content)
        self.assertIn("CONI 0.25", content)

    def test_conic_round_trips_through_zemax(self):
        lens = Lens(
            radius_of_curvature_1=50.0,
            radius_of_curvature_2=-50.0,
            thickness=5.0,
            diameter=20.0,
            conic_constant_1=-0.5,
            conic_constant_2=1.0,
        )
        tmp = tempfile.NamedTemporaryFile(suffix=".zmx", delete=False, mode="w")
        tmp.close()
        try:
            ZemaxExporter.export_lens(lens, tmp.name)
            rebuilt = ZemaxSystemImporter.import_system(tmp.name)
        finally:
            os.unlink(tmp.name)

        rebuilt_lens = rebuilt.elements[0].lens
        self.assertAlmostEqual(rebuilt_lens.conic_constant_1, -0.5)
        self.assertAlmostEqual(rebuilt_lens.conic_constant_2, 1.0)
