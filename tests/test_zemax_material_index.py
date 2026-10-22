"""Regression tests for #610: Zemax import must resolve the glass, not guess BK7.

``ZemaxSystemImporter`` built its name -> index map from
``DEFAULT_MATERIAL_INDICES``, a six-glass table, and stored BK7 for every
other glass. A lens imported with ``GLAS F2`` therefore kept the name F2 -
so ``refractive_index_at()`` dispersed like F2 - while its stored
``refractive_index`` was BK7's:

    material: F2 | stored n: 1.5168 | n@486.1: 1.6321

The paraxial properties came from one glass and the traced ones from
another. The importer now asks the material catalog first and only falls
back to the static table, then BK7.
"""

import os
import tempfile
import unittest

from openlens.constants import REFRACTIVE_INDEX_BK7, WAVELENGTH_D_LINE
from openlens.export_formats import ZemaxSystemExporter, ZemaxSystemImporter
from openlens.lens import Lens
from openlens.material_database import get_material_database
from openlens.optical_system import OpticalSystem


class TestZemaxMaterialIndex(unittest.TestCase):
    """The stored index must be the glass the file names."""

    def setUp(self):
        handle, self.path = tempfile.mkstemp(suffix=".zmx")
        os.close(handle)
        self.addCleanup(lambda: os.path.exists(self.path) and os.unlink(self.path))

    def round_trip(self, material, refractive_index=1.5):
        """Export one lens with *material* and import it again."""
        system = OpticalSystem(name="Round trip")
        system.add_lens(
            Lens(
                radius_of_curvature_1=50.0,
                radius_of_curvature_2=-50.0,
                thickness=5.0,
                diameter=25.0,
                material=material,
                refractive_index=refractive_index,
            )
        )
        ZemaxSystemExporter.export_system(system, self.path)
        return ZemaxSystemImporter.import_system(self.path).elements[0].lens

    def test_a_catalog_glass_keeps_its_index(self):
        """F2 is not in DEFAULT_MATERIAL_INDICES; it must still arrive as F2."""
        lens = self.round_trip("F2")

        expected = get_material_database().get_refractive_index("F2", WAVELENGTH_D_LINE)

        self.assertEqual(lens.material, "F2")
        self.assertAlmostEqual(lens.refractive_index, expected, places=9)
        self.assertNotAlmostEqual(lens.refractive_index, REFRACTIVE_INDEX_BK7, places=3)

    def test_the_stored_index_agrees_with_the_dispersion(self):
        """The paraxial index and refractive_index_at() must be one glass."""
        lens = self.round_trip("F2")

        self.assertAlmostEqual(
            lens.refractive_index,
            lens.refractive_index_at(WAVELENGTH_D_LINE),
            places=9,
        )

    def test_another_non_default_glass_round_trips(self):
        lens = self.round_trip("SF11")

        self.assertAlmostEqual(lens.refractive_index, 1.7847, places=3)

    def test_a_display_name_glass_round_trips(self):
        """'Fused Silica' has whitespace and a display name, not a key."""
        lens = self.round_trip("Fused Silica")

        self.assertAlmostEqual(lens.refractive_index, 1.4585, places=3)

    def test_an_unknown_glass_falls_back_to_bk7(self):
        """Nothing better is known about a custom glass; keep the old default."""
        lens = self.round_trip("UNOBTAINIUM", refractive_index=1.7)

        self.assertEqual(lens.material, "UNOBTAINIUM")
        self.assertAlmostEqual(lens.refractive_index, REFRACTIVE_INDEX_BK7, places=4)


if __name__ == "__main__":
    unittest.main()
