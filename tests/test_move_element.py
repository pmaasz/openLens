#!/usr/bin/env python3
"""
Reordering an assembly must move the element in the tree, not only in the
flat list.

The assembly tab swapped two entries of ``OpticalSystem.elements`` - the
*flat* list - and nothing else. The tree kept the old order, so the
tree-based tracer, the visualisation and the flat-list analyses disagreed
about the system, and the element positions no longer increased along the
axis.
"""

import unittest

from openlens.analysis.paraxial import find_paraxial_focus
from openlens.lens import Lens
from openlens.optical_node import OpticalAssembly, OpticalElement, vec3
from openlens.optical_system import OpticalSystem


def _lens(name, radius):
    return Lens(
        name=name,
        radius_of_curvature_1=radius,
        radius_of_curvature_2=-100.0,
        thickness=5.0,
        diameter=20.0,
        refractive_index=1.5168,
    )


def _system():
    system = OpticalSystem("three element")
    system.add_lens(_lens("L1", 60.0), air_gap_before=0.0)
    system.add_lens(_lens("L2", -80.0), air_gap_before=10.0)
    system.add_lens(_lens("L3", 100.0), air_gap_before=10.0)
    return system


def _tree_order(system):
    return [
        node.element_model.name
        for node, _pos in system.root.get_flat_list()
        if getattr(node, "is_element", False)
    ]


def _nested_system():
    """Two elements inside an assembly inserted at 50 mm."""
    assembly = OpticalAssembly(name="Doublet")
    for name, position in (("A0", 0.0), ("A1", 20.0)):
        node = OpticalElement(element_model=_lens(name, 60.0), name=name)
        node.position = vec3(position, 0.0, 0.0)
        assembly.add_child(node)

    system = OpticalSystem("nested")
    system.add_assembly(assembly, position=50.0)
    return system


class TestMoveElement(unittest.TestCase):
    """The model must move the element in the tree."""

    def test_the_flat_list_and_the_tree_agree_after_a_move(self):
        """The two views must describe the same system"""
        system = _system()

        self.assertTrue(system.move_element(1, -1))

        self.assertEqual([e.lens.name for e in system.elements], ["L2", "L1", "L3"])
        self.assertEqual(_tree_order(system), ["L2", "L1", "L3"])

    def test_the_positions_still_increase_along_the_axis(self):
        """The elements must stay in axial order"""
        system = _system()

        system.move_element(1, -1)

        positions = [e.position for e in system.elements]
        self.assertEqual(positions, sorted(positions))
        self.assertEqual(positions, [0.0, 15.0, 30.0])

    def test_the_air_gaps_are_preserved(self):
        """The spacing between the stations is the user's, not the move's"""
        system = _system()

        system.move_element(1, -1)

        self.assertEqual([g.thickness for g in system.air_gaps], [10.0, 10.0])

    def test_the_alignment_follows_the_element(self):
        """A tilted element keeps its tilt when it moves"""
        system = _system()
        system.set_element_alignment(1, tilt_z=1.5)

        system.move_element(1, -1)

        moved = next(e for e in system.elements if e.lens.name == "L2")
        self.assertAlmostEqual(moved.tilt_z, 1.5)

    def test_the_first_element_cannot_move_up(self):
        """There is nothing before it"""
        system = _system()

        self.assertFalse(system.move_element(0, -1))
        self.assertEqual([e.lens.name for e in system.elements], ["L1", "L2", "L3"])

    def test_the_last_element_cannot_move_down(self):
        """Nor after the last one"""
        system = _system()

        self.assertFalse(system.move_element(2, 1))
        self.assertEqual([e.lens.name for e in system.elements], ["L1", "L2", "L3"])

    def test_moving_down_keeps_the_positions_increasing(self):
        """The down button is the same move, the other way."""
        system = _system()

        self.assertTrue(system.move_element(0, 1))

        self.assertEqual([e.lens.name for e in system.elements], ["L2", "L1", "L3"])
        self.assertEqual([e.position for e in system.elements], [0.0, 15.0, 30.0])
        self.assertEqual([g.thickness for g in system.air_gaps], [10.0, 10.0])

    def test_the_paraxial_focus_survives_the_move(self):
        """The reported symptom: the focus search returned None."""
        system = _system()
        self.assertIsNotNone(find_paraxial_focus(system))

        system.move_element(1, -1)

        self.assertIsNotNone(find_paraxial_focus(system))

    def test_nested_siblings_swap_inside_their_assembly(self):
        """A move inside an assembly keeps that assembly where it is."""
        system = _nested_system()
        assembly = system.root.children[0]
        assembly_x = assembly.get_global_position().x

        self.assertTrue(system.move_element(1, -1))

        self.assertEqual([e.lens.name for e in system.elements], ["A1", "A0"])
        self.assertEqual(_tree_order(system), ["A1", "A0"])
        self.assertEqual([e.position for e in system.elements], [50.0, 70.0])
        self.assertAlmostEqual(assembly.get_global_position().x, assembly_x)

    def test_a_move_across_an_assembly_is_refused(self):
        """Reparenting is not a reorder; refuse instead of guessing."""
        assembly = OpticalAssembly(name="Group")
        node = OpticalElement(element_model=_lens("A", 60.0), name="A")
        assembly.add_child(node)

        system = OpticalSystem("mixed")
        system.add_lens(_lens("L1", 60.0))
        system.add_assembly(assembly, position=100.0)

        self.assertFalse(system.move_element(1, -1))
        self.assertEqual([e.lens.name for e in system.elements], ["L1", "A"])
        self.assertEqual(_tree_order(system), ["L1", "A"])


if __name__ == "__main__":
    unittest.main()
