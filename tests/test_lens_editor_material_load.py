"""Regression: the lens editor must show the material it is displaying.

``load_lens`` never touched the material combo, so opening an SF11 lens showed
**BK7** next to an index of 1.7847. And because ``currentTextChanged`` only fires
on a *change*, re-selecting the material the combo already displayed did nothing
to correct it - the only way to fix the display was to pick a different glass and
come back.

Two related defects: the index box was read-only, so "Custom" pinned n to 1.5 with
no way to state the index you wanted; and the style sheet named ``QSpinBox``,
which does not match a ``QDoubleSpinBox``, so it styled nothing.
"""

import unittest

from PySide6.QtWidgets import QApplication

from openlens.gui.widgets.lens_editor import CUSTOM_MATERIAL, LensEditorWidget
from openlens.lens import Lens

_APP = QApplication.instance() or QApplication([])


class _EditorFixture(unittest.TestCase):
    def setUp(self):
        self.editor = LensEditorWidget()

    def tearDown(self):
        self.editor.deleteLater()

    def _load(self, material, index):
        lens = Lens(name="Loaded", material=material, refractive_index=index)
        self.editor.load_lens(lens)
        return lens


class TestLoadingShowsTheRightMaterial(_EditorFixture):
    def test_a_catalogued_material_is_shown(self):
        self._load("SF11", 1.7847)

        self.assertEqual(
            self.editor._material_combo.currentText(),
            "SF11",
            msg="the combo still shows the material it was constructed with",
        )

    def test_the_shown_material_matches_the_model(self):
        lens = self._load("SF11", 1.7847)

        self.assertEqual(
            self.editor._material_combo.currentText(),
            lens.material,
            msg="the editor and the model disagree about the material",
        )

    def test_every_offered_material_round_trips(self):
        """Whatever the combo offers, loading that name must show that name."""
        for index in range(self.editor._material_combo.count()):
            name = self.editor._material_combo.itemText(index)
            with self.subTest(material=name):
                self._load(name, 1.5)
                self.assertEqual(self.editor._material_combo.currentText(), name)

    def test_the_index_is_not_clobbered_by_the_material(self):
        """The model is the authority for a loaded lens."""
        lens = self._load("SF11", 1.7847)

        self.assertAlmostEqual(lens.refractive_index, 1.7847, places=6)
        self.assertAlmostEqual(
            self.editor._n_input.value(),
            1.7847,
            places=6,
            msg="the index box was overwritten with the catalog value",
        )

    def test_an_uncatalogued_material_falls_back_to_custom(self):
        """setCurrentText is a no-op for a value not in the list."""
        self._load("Unobtainium", 2.1)

        self.assertEqual(
            self.editor._material_combo.currentText(),
            CUSTOM_MATERIAL,
            msg="an unknown material left the previous selection showing",
        )

    def test_an_uncatalogued_material_keeps_its_index(self):
        lens = self._load("Unobtainium", 2.1)

        self.assertAlmostEqual(lens.refractive_index, 2.1, places=6)

    def test_an_empty_material_falls_back_to_custom(self):
        self._load("", 1.6)

        self.assertEqual(self.editor._material_combo.currentText(), CUSTOM_MATERIAL)

    def test_loading_emits_no_modification(self):
        """A load is not an edit; it must not look like one to a saver."""
        seen = []
        self.editor.lens_modified.connect(lambda lens: seen.append(lens))

        self._load("SF11", 1.7847)

        self.assertEqual(seen, [], msg="loading a lens reported a modification")


class TestCustomAllowsAnIndex(_EditorFixture):
    def test_the_index_is_editable_for_custom(self):
        self.editor._material_combo.setCurrentText(CUSTOM_MATERIAL)

        self.assertFalse(
            self.editor._n_input.isReadOnly(),
            "the index is read-only, so a custom index cannot be stated",
        )

    def test_the_index_is_read_only_for_a_catalogued_glass(self):
        self.editor._material_combo.setCurrentText("BK7")

        self.assertTrue(
            self.editor._n_input.isReadOnly(),
            "a catalogued glass's index should not be editable",
        )

    def test_a_typed_custom_index_reaches_the_model(self):
        """The box had no valueChanged connection at all."""
        lens = self._load(CUSTOM_MATERIAL, 1.5)

        self.editor._n_input.setValue(1.77)

        self.assertAlmostEqual(lens.refractive_index, 1.77, places=6)

    def test_a_loaded_custom_lens_is_editable(self):
        self._load("Custom", 1.7)

        self.assertFalse(self.editor._n_input.isReadOnly())


class TestIndicesComeFromTheCatalog(_EditorFixture):
    def test_the_combo_is_populated(self):
        count = self.editor._material_combo.count()

        self.assertGreater(count, 1)
        self.assertEqual(
            self.editor._material_combo.itemText(count - 1),
            CUSTOM_MATERIAL,
            msg="Custom should be the last entry",
        )

    def test_no_hard_coded_index_dict_in_the_handler(self):
        """The editor and constants disagreed about Fused Silica."""
        import inspect

        source = inspect.getsource(LensEditorWidget._on_material_changed)

        self.assertNotIn(
            "1.4580",
            source,
            msg="the editor still carries its own index for Fused Silica, "
            "which constants puts at 1.4585",
        )

    def test_the_style_sheet_names_the_widget_it_styles(self):
        """QSpinBox does not match a QDoubleSpinBox, so the rule did nothing."""
        style = self.editor._n_input.styleSheet()

        self.assertIn("QDoubleSpinBox", style)
        self.assertNotIn("QSpinBox:", style)


if __name__ == "__main__":
    unittest.main()
