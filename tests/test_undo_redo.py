#!/usr/bin/env python3
"""Undo/redo for lens property edits (#566).

The editor owns one QUndoStack. Every user edit takes a snapshot of the lens
state before the handler runs and pushes a command; programmatic
``load_lens()`` refreshes must not add commands, and loading a different lens
starts a fresh history.
"""

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from openlens.coating_designer import COATING_PRESETS
from openlens.gui.widgets.lens_editor import LensEditorWidget
from openlens.lens import Lens


class TestLensEditorUndo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests import ensure_qapp

        cls.app = ensure_qapp()

    def setUp(self):
        self.editor = LensEditorWidget()
        self.lens = Lens(
            name="Original",
            radius_of_curvature_1=100.0,
            radius_of_curvature_2=-100.0,
            thickness=5.0,
            diameter=50.0,
        )
        self.editor.load_lens(self.lens)
        self.modified = []
        self.editor.lens_modified.connect(self.modified.append)

    def tearDown(self):
        self.editor.close()
        self.editor.deleteLater()
        from tests import flush_qt

        flush_qt()

    def test_a_radius_edit_can_be_undone_and_redone(self):
        self.editor._r1_input.setValue(150.0)

        self.assertEqual(self.lens.radius_of_curvature_1, 150.0)
        self.assertEqual(self.editor.undo_stack.count(), 1)
        self.assertTrue(self.editor.undo_stack.canUndo())

        self.editor.undo_stack.undo()

        self.assertEqual(self.lens.radius_of_curvature_1, 100.0)
        self.assertEqual(self.editor._r1_input.value(), 100.0)

        self.editor.undo_stack.redo()

        self.assertEqual(self.lens.radius_of_curvature_1, 150.0)
        self.assertEqual(self.editor._r1_input.value(), 150.0)

    def test_consecutive_name_edits_merge_into_one_command(self):
        self.editor._name_input.setText("N")
        self.editor._name_input.setText("Ne")
        self.editor._name_input.setText("New")

        self.assertEqual(self.lens.name, "New")
        self.assertEqual(self.editor.undo_stack.count(), 1)

        self.editor.undo_stack.undo()

        self.assertEqual(self.lens.name, "Original")
        self.assertEqual(self.editor._name_input.text(), "Original")

        self.editor.undo_stack.redo()

        self.assertEqual(self.lens.name, "New")
        self.assertEqual(self.editor._name_input.text(), "New")

    def test_undo_and_redo_emit_lens_modified_for_autosave(self):
        self.editor._thickness_input.setValue(8.0)
        self.modified.clear()

        self.editor.undo_stack.undo()
        self.assertEqual(self.modified, [self.lens])

        self.modified.clear()
        self.editor.undo_stack.redo()
        self.assertEqual(self.modified, [self.lens])

    def test_load_lens_refresh_does_not_grow_the_history(self):
        self.editor._r1_input.setValue(120.0)
        count = self.editor.undo_stack.count()

        # A refresh of the same model (open/save/optimizer paths) must not
        # record the act of displaying the lens as an edit.
        self.editor.load_lens(self.lens)

        self.assertEqual(self.editor.undo_stack.count(), count)
        self.assertTrue(self.editor.undo_stack.canUndo())

        # Nor may a programmatic model change followed by a refresh.
        self.lens.radius_of_curvature_1 = 222.0
        self.editor.load_lens(self.lens)
        self.assertEqual(self.editor.undo_stack.count(), count)

    def test_loading_a_different_lens_clears_the_history(self):
        self.editor._r1_input.setValue(120.0)
        self.assertTrue(self.editor.undo_stack.canUndo())

        other = Lens(name="Other")
        self.editor.load_lens(other)

        self.assertEqual(self.editor.undo_stack.count(), 0)
        self.assertFalse(self.editor.undo_stack.canUndo())
        self.assertFalse(self.editor.undo_stack.canRedo())

    def test_material_change_undoes_material_and_index_together(self):
        index = self.editor._material_combo.findText("SF11")
        self.assertGreaterEqual(index, 0, "SF11 missing from the material list")

        self.editor._material_combo.setCurrentIndex(index)
        self.assertEqual(self.lens.material, "SF11")
        self.assertEqual(self.editor.undo_stack.count(), 1)

        self.editor.undo_stack.undo()

        self.assertEqual(self.lens.material, "BK7")
        self.assertEqual(self.editor._material_combo.currentText(), "BK7")

    def test_parabolic_toggle_can_be_undone(self):
        self.editor._para1_check.setChecked(True)

        self.assertTrue(self.lens.is_parabolic_1)
        self.assertEqual(self.editor.undo_stack.count(), 1)

        self.editor.undo_stack.undo()

        self.assertFalse(self.lens.is_parabolic_1)
        self.assertFalse(self.editor._para1_check.isChecked())

    def test_interactive_drag_can_be_undone(self):
        # The 2D view emits property_changed; the editor routes it through the
        # spinbox, so the normal property handler records the command.
        self.editor._on_interactive_property_changed("thickness", 7.5)

        self.assertEqual(self.lens.thickness, 7.5)
        self.assertEqual(self.editor.undo_stack.count(), 1)

        self.editor.undo_stack.undo()

        self.assertEqual(self.lens.thickness, 5.0)
        self.assertEqual(self.editor._thickness_input.value(), 5.0)

    def test_coating_apply_can_be_undone(self):
        preset = next(name for name in COATING_PRESETS if name != "Uncoated")
        self.editor._coat_combos[0].setCurrentText(preset)

        self.editor._on_coating_apply(1)
        self.assertTrue(self.lens.get_coating_1())
        self.assertEqual(self.editor.undo_stack.count(), 1)

        self.editor.undo_stack.undo()

        self.assertFalse(self.lens.get_coating_1())

        self.editor.undo_stack.redo()

        self.assertTrue(self.lens.get_coating_1())

    def test_an_unchanged_property_does_not_add_a_command(self):
        self.editor._r1_input.setValue(100.0)
        self.assertEqual(self.editor.undo_stack.count(), 0)

        # _on_save() calls this to sync the widgets before persisting. With no
        # real change, it must not create a command (only modified_at moves).
        self.editor._on_property_changed()
        self.assertEqual(self.editor.undo_stack.count(), 0)

    def test_different_properties_do_not_merge(self):
        self.editor._name_input.setText("Renamed")
        self.editor._r1_input.setValue(140.0)

        self.assertEqual(self.editor.undo_stack.count(), 2)

        self.editor.undo_stack.undo()
        self.assertEqual(self.lens.radius_of_curvature_1, 100.0)
        self.assertEqual(self.lens.name, "Renamed")

        self.editor.undo_stack.undo()
        self.assertEqual(self.lens.name, "Original")


if __name__ == "__main__":
    unittest.main()
