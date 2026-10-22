"""Regression tests for #609: flat positions must survive an assembly offset.

``_update_positions()`` laid the flat ``elements`` list out from x=0 using
only element thicknesses. For a system whose first element lives inside an
assembly inserted at 50 mm, that moved the flat list back over the top of the
assembly while the node tree kept its global positions: the 2D/ABCD tracer
read the flat list and the 3D tracer read the tree, so they analysed
different geometry.

The assembly's offset is part of the system, so the layout has to start where
the first element stands - and the nodes have to follow the new layout, or
the two views drift apart again at the next thickness edit.
"""

import unittest

from openlens.lens import Lens
from openlens.optical_node import OpticalAssembly, OpticalElement, vec3
from openlens.optical_system import OpticalSystem


def _lens(name, thickness):
    return Lens(
        name=name,
        radius_of_curvature_1=50.0,
        radius_of_curvature_2=-50.0,
        thickness=thickness,
        diameter=20.0,
        refractive_index=1.5,
    )


def _assembly_element(name, thickness, position):
    node = OpticalElement(element_model=_lens(name, thickness), name=name)
    node.position = vec3(position, 0.0, 0.0)
    return node


def _system_with_assembly(assembly_x=50.0):
    """Assembly (A0 at 0, A1 at 20) inserted at *assembly_x*."""
    assembly = OpticalAssembly(name="Doublet")
    assembly.add_child(_assembly_element("A0", 5.0, 0.0))
    assembly.add_child(_assembly_element("A1", 4.0, 20.0))

    system = OpticalSystem(name="Nested")
    system.add_assembly(assembly, position=assembly_x)
    return system


def _flat_x(system):
    return {element.lens.name: round(element.position, 9) for element in system.elements}


def _tree_x(system):
    return {
        node.name: round(position.x, 9)
        for node, position in system.root.get_flat_list()
        if getattr(node, "is_element", False)
    }


class TestAssemblyOffsetSurvives(unittest.TestCase):
    """The flat list keeps the assembly's global placement."""

    def setUp(self):
        self.system = _system_with_assembly(50.0)

    def test_the_flat_positions_include_the_offset(self):
        """Regression: the flat list was re-laid out from zero."""
        self.system._update_positions()

        self.assertEqual(_flat_x(self.system), {"A0": 50.0, "A1": 70.0})

    def test_the_flat_list_and_the_tree_agree(self):
        """The 2D tracer and the 3D tracer must see one geometry."""
        self.system._update_positions()

        self.assertEqual(_flat_x(self.system), _tree_x(self.system))

    def test_an_element_inside_an_assembly_is_not_moved_to_zero(self):
        """The 2D tracer uses element.position directly."""
        self.system._update_positions()

        self.assertNotEqual(self.system.elements[0].position, 0.0)
        self.assertAlmostEqual(self.system.elements[0].position, 50.0, places=9)

    def test_template_positions_survive_an_assembly_at_zero(self):
        """The offset does not change the behaviour it already had at zero."""
        system = _system_with_assembly(0.0)

        system._update_positions()

        self.assertEqual(_flat_x(system), {"A0": 0.0, "A1": 20.0})


class TestEditsKeepTheTwoViewsTogether(unittest.TestCase):
    """A flat-side edit re-lays out both views."""

    def setUp(self):
        self.system = _system_with_assembly(50.0)
        self.system._update_positions()

    def test_a_nested_thickness_change_moves_the_following_element(self):
        """A thicker first element pushes the second one along."""
        self.system.elements[0].thickness = 8.0

        self.system._update_positions()

        self.assertEqual(_flat_x(self.system), _tree_x(self.system))
        self.assertEqual(_flat_x(self.system)["A1"], 70.0 + 3.0)

    def test_a_gap_change_moves_the_following_element(self):
        """The assembly's internal gap is an ordinary air gap in the layout."""
        self.system.air_gaps[0].thickness = 22.0  # was 15 mm: 20 - 5

        self.system._update_positions()

        self.assertEqual(_flat_x(self.system), _tree_x(self.system))
        self.assertEqual(_flat_x(self.system)["A1"], 50.0 + 5.0 + 22.0)

    def test_repeated_updates_are_stable(self):
        """Every update must be a fixed point, not a drift."""
        for _ in range(5):
            self.system._update_positions()
            self.assertEqual(_flat_x(self.system), {"A0": 50.0, "A1": 70.0})

    def test_a_root_child_after_the_assembly_keeps_its_distance(self):
        """The offset is not redistributed to what follows the assembly."""
        self.system.add_lens(_lens("L", 3.0), air_gap_before=2.0)
        self.system._update_positions()

        self.assertEqual(_flat_x(self.system), _tree_x(self.system))
        self.assertEqual(_flat_x(self.system)["L"], 76.0)


class TestFlatSystemsAreUnchanged(unittest.TestCase):
    """A system without assemblies lays out exactly as before."""

    def test_a_flat_system_still_starts_at_zero(self):
        system = OpticalSystem(name="Flat")
        system.add_lens(_lens("E0", 2.0))
        system.add_lens(_lens("E1", 3.0), air_gap_before=1.5)

        system._update_positions()

        self.assertEqual(_flat_x(system), {"E0": 0.0, "E1": 3.5})

    def test_a_thickness_change_still_moves_the_next_element(self):
        system = OpticalSystem(name="Flat")
        system.add_lens(_lens("E0", 2.0))
        system.add_lens(_lens("E1", 3.0), air_gap_before=1.5)

        system.elements[0].thickness = 5.0
        system._update_positions()

        self.assertEqual(_flat_x(system), {"E0": 0.0, "E1": 6.5})


if __name__ == "__main__":
    unittest.main()
