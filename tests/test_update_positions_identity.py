#!/usr/bin/env python3
"""
_update_positions must not confuse the flat element list with the node tree.

`elements` is flattened (assemblies expanded) while `root.children` may hold
OpticalAssembly nodes, so element *i* is not child *i*. Writing node
positions by flat index therefore moved unrelated nodes: a standalone lens
was rewritten with a nested element's position, leaving the flat list and the
tree disagreeing - and since the 2D/ABCD tracer and the 3D tracer read
different ones of the two, they analysed different geometry.

The method is called from refresh_references, design_air_spaced_doublet,
tolerancing, desensitization, the optimizer and environmental analysis, so
any of those silently changed assembly-based systems.

Nodes are now matched to elements by identity of the lens model they wrap,
and only direct children of root take their axial position from the flat
layout.
"""

import unittest

from src.lens import Lens
from src.optical_node import OpticalAssembly, OpticalElement, vec3
from src.optical_system import OpticalSystem


def _lens(name, thickness=2.0):
    return Lens(
        name=name,
        radius_of_curvature_1=30.0,
        radius_of_curvature_2=-30.0,
        thickness=thickness,
        diameter=10.0,
        refractive_index=1.5,
    )


def _element(name, thickness=2.0, position=0.0):
    node = OpticalElement(element_model=_lens(name, thickness), name=name)
    node.position = vec3(position, 0, 0)
    return node


def _nested_system():
    """Assembly (holding A0, A1) followed by a standalone lens L."""
    assembly = OpticalAssembly(name="Asm")
    assembly.add_child(_element("A0", 1.0, 0.0))
    assembly.add_child(_element("A1", 1.0, 1.0))

    system = OpticalSystem(name="Sys")
    system.add_assembly(assembly)
    system.add_lens(_lens("L", 5.0))
    return system


def _flat_positions(system):
    return [node.name for node, _ in system.root.get_flat_list()]


def _tree_x(system):
    return {node.name: round(pos.x, 6) for node, pos in system.root.get_flat_list()}


def _flat_x(system):
    return {e.lens.name: round(e.position, 6) for e in system.elements}


class TestNestedSystem(unittest.TestCase):
    def setUp(self):
        self.system = _nested_system()

    def test_update_does_not_move_an_unrelated_root_child(self):
        """Regression: L was rewritten with A1's position."""
        self.system._update_positions()
        self.assertEqual(_tree_x(self.system)["L"], 2.0)

    def test_flat_list_and_tree_stay_in_agreement(self):
        """The tracer disagreement the bug produced."""
        self.system._update_positions()
        self.assertEqual(_flat_x(self.system), _tree_x(self.system))

    def test_agreement_holds_across_repeated_updates(self):
        for _ in range(5):
            self.system._update_positions()
            self.assertEqual(_flat_x(self.system), _tree_x(self.system))

    def test_nested_nodes_keep_their_own_positions(self):
        before = _tree_x(self.system)
        self.system._update_positions()
        after = _tree_x(self.system)
        self.assertEqual(after["A0"], before["A0"])
        self.assertEqual(after["A1"], before["A1"])

    def test_flat_order_is_the_whole_tree(self):
        self.assertEqual(_flat_positions(self.system), ["A0", "A1", "L"])

    def test_root_child_thickness_change_propagates(self):
        """A root child's thickness must move what follows it, in both views."""
        self.system.add_lens(_lens("M", 1.0))  # trailing root child to observe
        self.system._update_positions()
        before = _tree_x(self.system)["M"]
        self.system.elements[2].thickness = 7.0  # L, a root child: 5.0 -> 7.0
        self.system._update_positions()
        self.assertEqual(_flat_x(self.system), _tree_x(self.system))
        self.assertEqual(_tree_x(self.system)["M"], before + 2.0)

    def test_nested_thickness_change_does_not_move_a_root_child(self):
        """A nested element is not re-laid-out, and must not drag L along.

        The flat running sum cannot express nesting, so a nested thickness
        change is not representable in the tree - a pre-existing limit of this
        method. What matters here is that the unrelated root child keeps its
        own identity-derived position instead of being handed a nested
        element's number.
        """
        self.system.elements[0].thickness = 6.0  # A0, inside the assembly
        self.system._update_positions()
        self.assertEqual(_tree_x(self.system)["A1"], 1.0)
        self.assertEqual(_tree_x(self.system)["L"], 7.0)

    def test_decenter_on_a_root_child_is_preserved(self):
        self.system.root.children[-1].position = vec3(0.0, 0.4, -0.2)
        self.system._update_positions()
        node = self.system.root.children[-1]
        self.assertAlmostEqual(node.position.y, 0.4)
        self.assertAlmostEqual(node.position.z, -0.2)


class TestFlatSystemStillUpdates(unittest.TestCase):
    """A flat system is 1:1, so it must keep behaving exactly as before."""

    def setUp(self):
        self.system = OpticalSystem(name="Flat")
        self.system.add_lens(_lens("E0", 2.0))
        self.system.add_lens(_lens("E1", 3.0), air_gap_before=1.5)
        self.system.add_lens(_lens("E2", 1.0))

    def test_nodes_receive_axial_positions(self):
        self.system._update_positions()
        self.assertEqual(_tree_x(self.system), {"E0": 0.0, "E1": 3.5, "E2": 6.5})

    def test_flat_and_tree_agree(self):
        self.system._update_positions()
        self.assertEqual(_flat_x(self.system), _tree_x(self.system))

    def test_positions_follow_a_thickness_change(self):
        self.system.elements[0].thickness = 8.0
        self.system._update_positions()
        self.assertEqual(_flat_x(self.system), _tree_x(self.system))
        self.assertEqual(_tree_x(self.system)["E1"], 9.5)

    def test_decenter_is_preserved(self):
        self.system.add_lens(_lens("E3", 1.0), decenter_y=0.7, decenter_z=-0.3)
        self.system._update_positions()
        node = self.system.root.children[-1]
        self.assertAlmostEqual(node.position.y, 0.7)
        self.assertAlmostEqual(node.position.z, -0.3)

    def test_air_gap_positions_are_set(self):
        self.system._update_positions()
        # One gap per consecutive pair: after E0 (2.0 thick) and after E1.
        self.assertEqual([round(g.position, 6) for g in self.system.air_gaps], [2.0, 6.5])

    def test_empty_system_is_a_no_op(self):
        empty = OpticalSystem(name="Empty")
        empty._update_positions()
        self.assertEqual(empty.elements, [])


if __name__ == "__main__":
    unittest.main()
