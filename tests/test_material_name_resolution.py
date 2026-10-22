"""Regression tests for #607: catalog material names must resolve.

The lens defaults and the UI speak display names - "Fused Silica" - while the
catalog is keyed by the glass name, "FUSEDSILICA". ``get_material`` only
uppercased, so a display name missed the catalog, and the miss was invisible:
``refractive_index_at`` returned the stored index for every wavelength (no
dispersion), while ``update_refractive_index`` stored the database's BK7
fallback and moved a fused-silica lens to 1.5168.
"""

import os
import tempfile
import unittest

from openlens.lens import Lens
from openlens.material_database import MaterialDatabase, MaterialProperties, get_material_database


def _temp_catalog(case: unittest.TestCase) -> MaterialDatabase:
    """A catalog with the built-in glasses, backed by a throwaway file."""
    handle, path = tempfile.mkstemp(suffix=".json")
    os.close(handle)
    # A missing file is the fresh-install case; an empty one is a parse error.
    os.unlink(path)
    case.addCleanup(lambda: os.path.exists(path) and os.unlink(path))
    return MaterialDatabase(db_path=path)


class TestCatalogNameResolution(unittest.TestCase):
    """The catalog finds a glass however its name is written."""

    def setUp(self):
        self.db = _temp_catalog(self)

    def test_display_name_resolves_to_the_catalog_entry(self):
        """'Fused Silica' is the catalog's FUSEDSILICA, not a miss."""
        display = self.db.get_material("Fused Silica")
        self.assertIsNotNone(display)
        canonical = self.db.get_material("FUSEDSILICA")
        self.assertIsNotNone(canonical)
        self.assertEqual(display.name, canonical.name)
        self.assertEqual(display.nd, canonical.nd)

    def test_lookup_ignores_case_spacing_and_punctuation(self):
        """A glass is found however the catalog punctuation is typed."""
        expected = self.db.get_material("N-BK7")
        self.assertIsNotNone(expected)
        for name in ("n-bk7", "N BK7", "NBK7", "n_bk7", "N.BK7"):
            with self.subTest(name=name):
                found = self.db.get_material(name)
                self.assertIsNotNone(found)
                self.assertEqual(found.nd, expected.nd)

    def test_unknown_name_is_still_a_miss(self):
        """Normalisation must not turn every name into some glass."""
        self.assertIsNone(self.db.get_material("NONEXISTENT"))
        self.assertFalse(self.db.has_material("NONEXISTENT"))

    def test_has_material_accepts_display_names(self):
        """has_material is the miss test callers need before a lookup."""
        self.assertTrue(self.db.has_material("BK7"))
        self.assertTrue(self.db.has_material("bk7"))
        self.assertTrue(self.db.has_material("Fused Silica"))

    def test_added_materials_are_reachable_by_normalised_name(self):
        """The normalised index must follow the catalog as it changes."""
        # Build the alias index against the catalog as it is now.
        self.assertIsNotNone(self.db.get_material("N BK7"))

        self.db.add_material(
            MaterialProperties(name="My Glass", catalog="Custom", nd=1.6, vd=40.0),
            save=False,
        )

        found = self.db.get_material("MYGLASS")
        self.assertIsNotNone(found)
        self.assertEqual(found.nd, 1.6)
        self.assertIsNotNone(self.db.get_material("my glass"))


class TestLensUsesTheResolvedMaterial(unittest.TestCase):
    """A lens named after a display-name glass behaves like that glass."""

    def test_display_name_lens_has_dispersion(self):
        """Fused silica must disperse, not sit at one index for all colours."""
        lens = Lens(material="Fused Silica", refractive_index=1.4585)

        n_blue = lens.refractive_index_at(486.1)
        n_red = lens.refractive_index_at(656.3)

        self.assertGreater(n_blue, n_red)
        self.assertNotAlmostEqual(n_blue, 1.4585, places=4)

    def test_update_refractive_index_does_not_replace_the_glass(self):
        """A wavelength change must not turn fused silica into BK7."""
        lens = Lens(material="Fused Silica", refractive_index=1.4585)
        expected = get_material_database().get_refractive_index("FUSEDSILICA", 486.1, 20.0)

        lens.update_refractive_index(486.1)

        self.assertAlmostEqual(lens.refractive_index, expected, places=9)
        self.assertNotAlmostEqual(lens.refractive_index, 1.5168, places=4)

    def test_unknown_material_keeps_its_stored_index(self):
        """Names the catalog lacks keep the index the lens already has."""
        for name in ("Unobtainium", "Sapphire", "Crown Glass", "Flint Glass"):
            with self.subTest(material=name):
                lens = Lens(material=name, refractive_index=1.77)
                lens.update_refractive_index(587.6)
                self.assertAlmostEqual(lens.refractive_index, 1.77, places=9)


if __name__ == "__main__":
    unittest.main()
