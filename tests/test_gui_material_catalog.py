"""#650: the editor must populate its material combo from the glass catalog.

``_materials_with_indices`` imported ``MATERIAL_DB_AVAILABLE`` from
``material_database``, where it does not exist. The import always raised and
the surrounding ``except Exception`` silently fell back to the static table,
so the combo offered six names (three of them not catalog glasses at all) while
the catalog held the real ones. The catalog entries were also read as dicts
although ``list_materials()`` returns strings.
"""

import unittest

from PySide6.QtWidgets import QApplication

from openlens.constants import WAVELENGTH_D_LINE
from openlens.gui.widgets.lens_editor import (
    CUSTOM_MATERIAL,
    LensEditorWidget,
    _materials_with_indices,
)
from openlens.lens import Lens
from openlens.material_database import get_material_database

_APP = QApplication.instance() or QApplication([])


class TestEditorOffersTheCatalog(unittest.TestCase):
    def test_every_catalog_material_is_offered(self):
        offered = {name for name, _ in _materials_with_indices()}
        catalog = set(get_material_database().list_materials())

        self.assertTrue(
            catalog <= offered,
            f"the editor is missing catalog glasses: {sorted(catalog - offered)}",
        )
        self.assertIn(CUSTOM_MATERIAL, offered)

    def test_indices_come_from_the_catalog(self):
        pairs = dict(_materials_with_indices())
        database = get_material_database()

        for name in database.list_materials():
            with self.subTest(material=name):
                self.assertAlmostEqual(
                    pairs[name],
                    database.get_refractive_index(name, WAVELENGTH_D_LINE),
                    places=9,
                )

        # SF11 carried 1.78 in the static table; the catalog says 1.78472.
        self.assertAlmostEqual(
            pairs["SF11"], database.get_refractive_index("SF11", WAVELENGTH_D_LINE), places=6
        )

    def test_the_fictional_static_materials_are_not_offered(self):
        offered = {name for name, _ in _materials_with_indices()}

        for name in ("Crown Glass", "Flint Glass", "Sapphire"):
            self.assertNotIn(
                name,
                offered,
                msg=f"{name!r} is in the static table but is not a catalog glass",
            )


class TestLoadingResolvesCatalogAliases(unittest.TestCase):
    def setUp(self):
        self.editor = LensEditorWidget()
        self.addCleanup(self.editor.deleteLater)

    def test_a_static_display_name_loads_as_the_catalog_entry(self):
        lens = Lens(name="old", material="Fused Silica", refractive_index=1.4585)

        self.editor.load_lens(lens)

        self.assertEqual(self.editor._material_combo.currentText(), "FUSEDSILICA")
        self.assertEqual(lens.material, "FUSEDSILICA")
        self.assertTrue(self.editor._n_input.isReadOnly())

    def test_a_genuinely_unknown_material_still_falls_back_to_custom(self):
        lens = Lens(name="odd", material="Unobtainium", refractive_index=2.1)

        self.editor.load_lens(lens)

        self.assertEqual(self.editor._material_combo.currentText(), CUSTOM_MATERIAL)
        self.assertFalse(self.editor._n_input.isReadOnly())


if __name__ == "__main__":
    unittest.main()
