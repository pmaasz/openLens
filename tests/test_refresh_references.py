"""Regression: refresh_references must update the tree, not just the flat list.

``refresh_references`` replaced the lens in each flat ``LensElement`` wrapper
but left the tree's ``OpticalElement.element_model`` pointing at the old Lens:

    s.elements[0].lens is b            -> True
    s.root.children[0].element_model is b -> False

Two things follow from that. The flat/2D calculations and the tree-based 3D
tracer analysed *different optics* - the same system, two different lenses.
And ``_update_positions`` matches nodes to elements by the identity of the
lens model they wrap, so a stale model breaks the pairing that keeps the flat
list and the tree in step.
"""

import unittest

from src.lens import Lens
from src.optical_system import OpticalSystem


class TestRefreshReferencesUpdatesTheTree(unittest.TestCase):
    """The tree and the flat list must never disagree about the lens."""

    def setUp(self):
        self.system = OpticalSystem(name="Refreshed")
        self.system.add_lens(Lens(name="Original", thickness=5.0))

    def test_the_tree_node_gets_the_new_lens(self):
        replacement = Lens(name="Replacement", thickness=7.0)
        lookup = {self.system.elements[0].lens_id: replacement}

        self.system.refresh_references(lookup)

        self.assertIs(
            self.system.root.children[0].element_model,
            replacement,
            "the tree still points at the old lens",
        )

    def test_the_flat_list_and_the_tree_agree(self):
        replacement = Lens(name="Replacement", thickness=7.0)
        lookup = {self.system.elements[0].lens_id: replacement}

        self.system.refresh_references(lookup)

        self.assertIs(
            self.system.elements[0].lens,
            self.system.root.children[0].element_model,
            "the flat list and the tree hold different lenses",
        )

    def test_the_replacement_thickness_is_used(self):
        """The new lens's own thickness, not the one it replaced."""
        replacement = Lens(name="Replacement", thickness=7.0)
        lookup = {self.system.elements[0].lens_id: replacement}

        self.system.refresh_references(lookup)

        self.assertAlmostEqual(self.system.elements[0].thickness, 7.0, places=6)

    def test_positions_are_still_consistent_after_a_refresh(self):
        """_update_positions matches nodes to elements by lens identity.

        A stale element_model breaks that match, so a refresh must leave the
        flat list and the tree agreeing on position as well as on lens. The
        replacement keeps the original thickness, so the positions should not
        move at all - a different thickness would legitimately shift the
        elements that follow.
        """
        self.system.add_lens(Lens(name="Second", thickness=4.0), air_gap_before=2.0)
        before = [element.position for element in self.system.elements]

        replacement = Lens(name="Replacement", thickness=5.0)
        lookup = {self.system.elements[0].lens_id: replacement}
        self.system.refresh_references(lookup)

        self.assertEqual(
            [element.position for element in self.system.elements],
            before,
            "the positions changed when only the lens references were refreshed",
        )

    def test_a_multi_element_system_refreshes_every_node(self):
        system = OpticalSystem(name="Several")
        system.add_lens(Lens(name="A", thickness=4.0))
        system.add_lens(Lens(name="B", thickness=6.0), air_gap_before=1.0)

        replacement_a = Lens(name="A2", thickness=4.0)
        replacement_b = Lens(name="B2", thickness=6.0)
        lookup = {
            system.elements[0].lens_id: replacement_a,
            system.elements[1].lens_id: replacement_b,
        }

        system.refresh_references(lookup)

        models = [node.element_model for node in system.root.children]
        self.assertEqual(models, [replacement_a, replacement_b])


if __name__ == "__main__":
    unittest.main()
