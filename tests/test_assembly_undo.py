#!/usr/bin/env python3
"""Undo/redo for assembly edits (#586).

The lens editor snapshots one ``Lens``.  Assembly edits mutate a whole
``OpticalSystem``, so the assembly tab owns a parallel snapshot history and
the window switches its Edit-menu actions between the two stacks.
"""

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QWidget

from openlens.gui.tabs.assembly_tab import AssemblyTab
from openlens.lens import Lens
from openlens.optical_system import OpticalSystem


class _Parent(QWidget):
    """Minimal window surface used by AssemblyTab."""

    def __init__(self, lenses):
        super().__init__()
        self._lenses = list(lenses)
        self._current_assembly = None
        self._current_lens = None
        self.status = []

    def _update_status(self, message):
        self.status.append(message)


def _lens(name):
    return Lens(
        name=name,
        radius_of_curvature_1=50.0,
        radius_of_curvature_2=-50.0,
        thickness=5.0,
        diameter=20.0,
    )


class TestAssemblyUndo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests import ensure_qapp

        cls.app = ensure_qapp()

    def _tab(self, system=None):
        parent = _Parent([_lens("Front"), _lens("Back")])
        tab = AssemblyTab(parent)
        tab.load_system(system or OpticalSystem(name="Assembly"))
        self.addCleanup(self._dispose, tab, parent)
        return tab, parent

    @staticmethod
    def _dispose(tab, parent):
        from tests import flush_qt

        tab.close()
        tab.deleteLater()
        parent.close()
        parent.deleteLater()
        flush_qt()

    @staticmethod
    def _system_with_two_elements():
        system = OpticalSystem(name="Assembly")
        system.add_lens(_lens("Front"))
        system.add_lens(_lens("Back"), air_gap_before=5.0)
        return system

    def test_add_element_can_be_undone_and_redone(self):
        tab, _parent = self._tab()
        tab._assembly_lens_list.setCurrentRow(0)

        tab._on_add_lens_to_system()

        self.assertEqual(len(tab._optical_system.elements), 1)
        self.assertEqual(tab.undo_stack.count(), 1)
        self.assertTrue(tab.undo_stack.canUndo())

        tab.undo_stack.undo()

        self.assertEqual(tab._optical_system.elements, [])
        self.assertEqual(tab._system_list.count(), 0)
        self.assertTrue(tab.undo_stack.canRedo())

        tab.undo_stack.redo()

        self.assertEqual(len(tab._optical_system.elements), 1)
        self.assertEqual(tab._system_list.count(), 1)

    def test_remove_element_can_be_undone_and_redone(self):
        tab, _parent = self._tab(self._system_with_two_elements())
        tab._system_list.setCurrentRow(0)

        tab._on_remove_lens_from_system()

        self.assertEqual([element.lens.name for element in tab._optical_system.elements], ["Back"])
        tab.undo_stack.undo()

        self.assertEqual(
            [element.lens.name for element in tab._optical_system.elements],
            ["Front", "Back"],
        )
        self.assertEqual(tab._system_list.count(), 2)
        tab.undo_stack.redo()

        self.assertEqual([element.lens.name for element in tab._optical_system.elements], ["Back"])

    def test_reorder_can_be_undone_and_redone(self):
        tab, _parent = self._tab(self._system_with_two_elements())
        tab._system_list.setCurrentRow(1)

        tab._on_move_lens_up()

        self.assertEqual(
            [element.lens.name for element in tab._optical_system.elements],
            ["Back", "Front"],
        )
        tab.undo_stack.undo()
        self.assertEqual(
            [element.lens.name for element in tab._optical_system.elements],
            ["Front", "Back"],
        )
        tab.undo_stack.redo()
        self.assertEqual(
            [element.lens.name for element in tab._optical_system.elements],
            ["Back", "Front"],
        )

    def test_reorder_down_can_be_undone_and_redone(self):
        tab, _parent = self._tab(self._system_with_two_elements())
        tab._system_list.setCurrentRow(0)

        tab._on_move_lens_down()

        self.assertEqual(
            [element.lens.name for element in tab._optical_system.elements],
            ["Back", "Front"],
        )
        tab.undo_stack.undo()
        self.assertEqual(
            [element.lens.name for element in tab._optical_system.elements],
            ["Front", "Back"],
        )
        tab.undo_stack.redo()
        self.assertEqual(
            [element.lens.name for element in tab._optical_system.elements],
            ["Back", "Front"],
        )

    def test_air_gap_edit_can_be_undone_and_redone(self):
        tab, _parent = self._tab(self._system_with_two_elements())
        tab._system_list.setCurrentRow(1)

        tab._air_gap_input.setValue(12.5)
        tab._on_apply_gap_clicked()

        self.assertEqual(tab._optical_system.air_gaps[0].thickness, 12.5)
        tab.undo_stack.undo()

        self.assertEqual(tab._optical_system.air_gaps[0].thickness, 5.0)
        self.assertEqual(tab._air_gap_input.value(), 5.0)
        tab.undo_stack.redo()

        self.assertEqual(tab._optical_system.air_gaps[0].thickness, 12.5)
        self.assertEqual(tab._air_gap_input.value(), 12.5)

    def test_alignment_edit_can_be_undone_and_redone(self):
        tab, _parent = self._tab(self._system_with_two_elements())
        tab._system_list.setCurrentRow(0)

        tab._decenter_y_input.setValue(1.5)
        tab._tilt_inputs[2].setValue(0.25)
        tab._on_align_apply_clicked()

        element = tab._optical_system.elements[0]
        self.assertEqual(element.decenter_y, 1.5)
        self.assertEqual(element.tilt_z, 0.25)
        tab.undo_stack.undo()

        element = tab._optical_system.elements[0]
        self.assertEqual(element.decenter_y, 0.0)
        self.assertEqual(element.tilt_z, 0.0)
        self.assertEqual(tab._decenter_y_input.value(), 0.0)
        tab.undo_stack.redo()

        element = tab._optical_system.elements[0]
        self.assertEqual(element.decenter_y, 1.5)
        self.assertEqual(element.tilt_z, 0.25)

    def test_aperture_stop_can_be_undone_and_redone(self):
        tab, _parent = self._tab(self._system_with_two_elements())
        tab._stop_gap_combo.setCurrentIndex(tab._stop_gap_combo.findData(0))
        tab._stop_dia_input.setValue(12.0)

        tab._on_stop_set_clicked()

        self.assertEqual(tab._optical_system.get_aperture_stop()["diameter"], 12.0)
        tab.undo_stack.undo()

        self.assertIsNone(tab._optical_system.get_aperture_stop())
        self.assertEqual(tab._stop_dia_input.value(), 0.0)
        tab.undo_stack.redo()

        self.assertEqual(tab._optical_system.get_aperture_stop()["diameter"], 12.0)

    def test_clearing_an_absent_stop_does_not_grow_history(self):
        tab, _parent = self._tab(self._system_with_two_elements())

        tab._on_stop_clear_clicked()

        self.assertEqual(tab.undo_stack.count(), 0)
        self.assertIsNone(tab._optical_system.get_aperture_stop())

    def test_refresh_of_the_same_system_does_not_grow_history(self):
        tab, _parent = self._tab()
        tab._assembly_lens_list.setCurrentRow(0)
        tab._on_add_lens_to_system()
        count = tab.undo_stack.count()

        tab.refresh()

        self.assertEqual(tab.undo_stack.count(), count)
        self.assertTrue(tab.undo_stack.canUndo())

    def test_loading_a_different_system_clears_history_and_rejects_stale_command(self):
        tab, _parent = self._tab()
        tab._assembly_lens_list.setCurrentRow(0)
        tab._on_add_lens_to_system()
        stale = tab.undo_stack.command(0)

        replacement = self._system_with_two_elements()
        tab.load_system(replacement)

        self.assertIs(tab._optical_system, replacement)
        self.assertEqual(tab.undo_stack.count(), 0)
        self.assertEqual(len(replacement.elements), 2)

        stale.undo()

        self.assertIs(tab._optical_system, replacement)
        self.assertEqual(len(replacement.elements), 2)
