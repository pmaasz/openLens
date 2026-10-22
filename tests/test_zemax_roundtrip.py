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
    def _zmx(
        front_curv="0.02",
        disz="5.0",
        front_diam="25.0",
        back_diam="25.0",
        back_curv="-0.02",
    ):
        return (
            "VERS 200000\nMODE SEQ\nUNIT MM\n\n"
            "SURF 0\n  TYPE STANDARD\n  CURV 0.0\n  DISZ INFINITY\n\n"
            f"SURF 1\n  TYPE STANDARD\n  CURV {front_curv}\n  DISZ {disz}\n"
            f"  GLAS BK7\n  DIAM {front_diam}\n\n"
            f"SURF 2\n  TYPE STANDARD\n  CURV {back_curv}\n  DIAM {back_diam}\n  DISZ 50.0\n\n"
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

    def test_non_finite_front_curvature_is_rejected(self):
        """NaN/inf CURV must be dropped, not injected as NaN geometry."""
        for curv in ("nan", "inf", "-inf"):
            with self.subTest(curv=curv):
                with self.assertLogs("openlens.export_formats", level="WARNING") as captured:
                    rebuilt = self._import(self._zmx(front_curv=curv))

                self.assertEqual(len(rebuilt.elements), 0)
                self.assertTrue(
                    any("finite" in message for message in captured.output),
                    f"no warning explained the dropped element: {captured.output}",
                )

    def test_non_finite_back_curvature_is_rejected(self):
        """A bad CURV on the closing surface drops the element too."""
        for curv in ("nan", "inf", "-inf"):
            with self.subTest(curv=curv):
                rebuilt = self._import(self._zmx(back_curv=curv))
                self.assertEqual(len(rebuilt.elements), 0)

    def test_a_non_finite_element_does_not_discard_the_next(self):
        """The import continues with the remaining surfaces."""
        text = (
            "VERS 200000\nMODE SEQ\nUNIT MM\n\n"
            "SURF 0\n  TYPE STANDARD\n  CURV 0.0\n  DISZ INFINITY\n\n"
            "SURF 1\n  TYPE STANDARD\n  CURV nan\n  DISZ 5.0\n"
            "  GLAS BK7\n  DIAM 25.0\n\n"
            "SURF 2\n  TYPE STANDARD\n  CURV -0.02\n  DIAM 25.0\n  DISZ 50.0\n\n"
            "SURF 3\n  TYPE STANDARD\n  CURV 0.02\n  DISZ 4.0\n"
            "  GLAS BK7\n  DIAM 30.0\n\n"
            "SURF 4\n  TYPE STANDARD\n  CURV -0.02\n  DIAM 30.0\n  DISZ 0.0\n"
        )
        rebuilt = self._import(text)
        self.assertEqual(len(rebuilt.elements), 1)
        self.assertAlmostEqual(rebuilt.elements[0].lens.thickness, 4.0)

    def test_the_explicit_infinity_token_still_means_plano(self):
        """``CURV INFINITY`` is the format's plano spelling, not corrupt input."""
        rebuilt = self._import(self._zmx(front_curv="INFINITY"))
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
        # The catalog's Sellmeier fit (1.45846) rather than the rounded
        # static table (1.4585), so the stored index agrees with the
        # dispersion (see test_zemax_material_index.py).
        self.assertAlmostEqual(lens.refractive_index, 1.4585, places=3)

    def test_material_name_lookup_ignores_case(self):
        """Preserving case must not cost the catalog lookup."""
        text = _singlet_zmx().replace("GLAS BK7", "GLAS fused silica")

        rebuilt = _import_text(text)

        lens = rebuilt.elements[0].lens
        self.assertEqual(lens.material, "fused silica")
        self.assertAlmostEqual(lens.refractive_index, 1.4585, places=3)

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
        self.assertAlmostEqual(imported.refractive_index, 1.4585, places=3)


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


class TestZemaxUnits(unittest.TestCase):
    """The UNIT header decides the file's length unit; values import in mm."""

    @staticmethod
    def _inch_system():
        return (
            "VERS 200000\nMODE SEQ\nUNIT INCH\n\n"
            "SURF 0\n  TYPE STANDARD\n  CURV 0.0\n  DISZ INFINITY\n\n"
            "SURF 1\n  TYPE STANDARD\n  CURV 0.5\n  DISZ 1.0\n"
            "  GLAS BK7\n  DIAM 0.25\n\n"
            "SURF 2\n  TYPE STANDARD\n  CURV -0.5\n  DIAM 0.25\n  DISZ 4.0\n\n"
            "SURF 3\n  TYPE STANDARD\n  CURV 0.5\n  DISZ 0.5\n"
            "  GLAS BK7\n  DIAM 0.5\n\n"
            "SURF 4\n  TYPE STANDARD\n  CURV -0.5\n  DIAM 0.5\n  DISZ 0.0\n"
        )

    @staticmethod
    def _millimetre_system(unit_line="UNIT MM\n"):
        return (
            "VERS 200000\nMODE SEQ\n" + unit_line + "\n"
            "SURF 0\n  TYPE STANDARD\n  CURV 0.0\n  DISZ INFINITY\n\n"
            "SURF 1\n  TYPE STANDARD\n  CURV 0.02\n  DISZ 5.0\n"
            "  GLAS BK7\n  DIAM 25.0\n\n"
            "SURF 2\n  TYPE STANDARD\n  CURV -0.02\n  DIAM 25.0\n  DISZ 0.0\n"
        )

    def test_inch_lengths_are_converted_to_millimetres(self):
        rebuilt = _import_text(self._inch_system())

        self.assertEqual(len(rebuilt.elements), 2)
        first, second = [element.lens for element in rebuilt.elements]
        # CURV 0.5 is a 2 inch radius; lengths scale by 25.4, curvature by
        # the inverse factor.
        self.assertAlmostEqual(first.radius_of_curvature_1, 50.8, places=6)
        self.assertAlmostEqual(first.radius_of_curvature_2, -50.8, places=6)
        self.assertAlmostEqual(first.thickness, 25.4, places=6)
        # DIAM is a semi-diameter: 0.25 in radius -> 0.5 in = 12.7 mm.
        self.assertAlmostEqual(first.diameter, 12.7, places=6)
        self.assertAlmostEqual(second.thickness, 12.7, places=6)
        self.assertAlmostEqual(second.diameter, 25.4, places=6)

    def test_the_gap_between_elements_is_converted(self):
        rebuilt = _import_text(self._inch_system())

        self.assertEqual(len(rebuilt.air_gaps), 1)
        self.assertAlmostEqual(rebuilt.air_gaps[0].thickness, 101.6, places=6)

    def test_the_inch_spellings_are_recognised(self):
        for unit in ("UNIT INCH", "UNIT IN", "unit inch"):
            with self.subTest(unit=unit):
                text = self._inch_system().replace("UNIT INCH", unit)
                rebuilt = _import_text(text)
                self.assertAlmostEqual(rebuilt.elements[0].lens.thickness, 25.4, places=6)

    def test_a_millimetre_file_is_unchanged(self):
        rebuilt = _import_text(self._millimetre_system())

        lens = rebuilt.elements[0].lens
        self.assertAlmostEqual(lens.radius_of_curvature_1, 50.0, places=6)
        self.assertAlmostEqual(lens.thickness, 5.0, places=6)
        self.assertAlmostEqual(lens.diameter, 50.0, places=6)

    def test_a_missing_unit_line_keeps_millimetres(self):
        rebuilt = _import_text(self._millimetre_system(unit_line=""))

        self.assertAlmostEqual(rebuilt.elements[0].lens.thickness, 5.0, places=6)

    def test_unknown_unit_warns_and_assumes_millimetres(self):
        text = self._millimetre_system(unit_line="UNIT FURLONG\n")

        with self.assertLogs("openlens.export_formats", level="WARNING") as captured:
            rebuilt = _import_text(text)

        self.assertTrue(
            any("unit" in message.lower() for message in captured.output),
            f"no warning named the unknown unit: {captured.output}",
        )
        self.assertAlmostEqual(rebuilt.elements[0].lens.thickness, 5.0, places=6)

    def test_a_decentred_element_is_scaled_with_the_rest_of_the_file(self):
        """DECE is a length in the file's unit; TILT is degrees and stays."""
        front = "  CURV 0.5\n  DISZ 1.0\n"
        text = self._inch_system().replace(front, front + "  DECE 0.5 0.25\n  TILT 3 -2 1\n")

        rebuilt = _import_text(text)

        element = rebuilt.elements[0]
        self.assertAlmostEqual(element.decenter_y, 12.7, places=6)
        self.assertAlmostEqual(element.decenter_z, 6.35, places=6)
        self.assertAlmostEqual(element.tilt_x, 3.0, places=6)
        self.assertAlmostEqual(element.tilt_y, -2.0, places=6)
        self.assertAlmostEqual(element.tilt_z, 1.0, places=6)


class TestZemaxAlignmentAndWavelength(unittest.TestCase):
    """A round trip must keep the element transform and the design wavelength."""

    def _round_trip(self, system):
        tmp = tempfile.NamedTemporaryFile(suffix=".zmx", delete=False, mode="w")
        tmp.close()
        try:
            ZemaxSystemExporter.export_system(system, tmp.name)
            with open(tmp.name) as handle:
                text = handle.read()
            return text, ZemaxSystemImporter.import_system(tmp.name)
        finally:
            os.unlink(tmp.name)

    @staticmethod
    def _aligned_system():
        system = OpticalSystem(name="Aligned")
        system.add_lens(
            Lens(
                radius_of_curvature_1=50.0,
                radius_of_curvature_2=-50.0,
                thickness=5.0,
                diameter=25.0,
                wavelength=532.0,
            )
        )
        system.set_element_alignment(
            0, decenter_y=5.0, decenter_z=2.0, tilt_x=3.0, tilt_y=-2.0, tilt_z=1.5
        )
        return system

    def test_the_file_declares_alignment_and_wavelength(self):
        text, _ = self._round_trip(self._aligned_system())

        self.assertIn("WAVE 532", text)
        self.assertIn("DECE 5 2", text)
        self.assertIn("TILT 3 -2 1.5", text)

    def test_round_trip_preserves_the_element_transform(self):
        _, rebuilt = self._round_trip(self._aligned_system())

        element = rebuilt.elements[0]
        self.assertAlmostEqual(element.decenter_y, 5.0, places=6)
        self.assertAlmostEqual(element.decenter_z, 2.0, places=6)
        self.assertAlmostEqual(element.tilt_x, 3.0, places=6)
        self.assertAlmostEqual(element.tilt_y, -2.0, places=6)
        self.assertAlmostEqual(element.tilt_z, 1.5, places=6)

    def test_round_trip_preserves_the_design_wavelength(self):
        _, rebuilt = self._round_trip(self._aligned_system())

        self.assertAlmostEqual(rebuilt.elements[0].lens.wavelength, 532.0, places=6)

    def test_round_trip_keeps_the_axial_positions_with_alignment(self):
        system = OpticalSystem(name="Two elements")
        system.add_lens(Lens(thickness=5.0, diameter=25.0))
        system.add_lens(Lens(thickness=4.0, diameter=20.0), air_gap_before=10.0)
        system.set_element_alignment(1, decenter_y=-3.0, tilt_z=2.0)

        _, rebuilt = self._round_trip(system)

        self.assertEqual(len(rebuilt.elements), 2)
        self.assertAlmostEqual(rebuilt.elements[0].position, 0.0, places=6)
        self.assertAlmostEqual(rebuilt.elements[1].position, 15.0, places=6)
        self.assertAlmostEqual(rebuilt.elements[1].decenter_y, -3.0, places=6)
        self.assertAlmostEqual(rebuilt.air_gaps[0].thickness, 10.0, places=6)

    def test_a_single_lens_export_keeps_its_wavelength(self):
        tmp = tempfile.NamedTemporaryFile(suffix=".zmx", delete=False, mode="w")
        tmp.close()
        try:
            ZemaxExporter.export_lens(Lens(wavelength=532.0), tmp.name)
            rebuilt = ZemaxSystemImporter.import_system(tmp.name)
        finally:
            os.unlink(tmp.name)

        self.assertAlmostEqual(rebuilt.elements[0].lens.wavelength, 532.0, places=6)

    def test_an_invalid_wavelength_falls_back_to_the_default(self):
        system = OpticalSystem(name="Bad wavelength")
        system.add_lens(Lens(wavelength=532.0))
        text, _ = self._round_trip(system)
        bad = text.replace("WAVE 532", "WAVE nan")

        tmp = tempfile.NamedTemporaryFile(suffix=".zmx", delete=False, mode="w")
        tmp.close()
        try:
            with open(tmp.name, "w") as handle:
                handle.write(bad)
            with self.assertLogs("openlens.export_formats", level="WARNING") as captured:
                rebuilt = ZemaxSystemImporter.import_system(tmp.name)
        finally:
            os.unlink(tmp.name)

        self.assertTrue(any("wavelength" in message.lower() for message in captured.output))
        self.assertAlmostEqual(rebuilt.elements[0].lens.wavelength, 587.6, places=6)
