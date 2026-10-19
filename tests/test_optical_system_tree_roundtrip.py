"""Regression: saving a system must not flatten it.

``to_dict`` stored only the flattened element list. ``self.elements`` is what
``_rebuild_from_tree`` produces by walking the tree, so the hierarchy was
discarded - nesting, sub-assembly membership and parent-child relationships all
gone. ``from_dict`` then rebuilt a flat system with ``add_lens()``, so every
element ended up a direct child of the root.

A user who builds a doublet inside a sub-assembly, saves as JSON and reopens gets
a flat two-element system. The optical result may still be close, but the
structure is gone - and any edit that re-saves writes the flattened form back.

The flat ``elements`` key is kept. The database stores it, the GUI's Save As
writes it, and ``LensStorage`` reads it. The tree is written *alongside*.
"""

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.lens import Lens
from src.optical_node import OpticalAssembly, OpticalElement
from src.optical_system import OpticalSystem


def _lens(name="L", radius=50.0):
    return Lens(
        name=name,
        radius_of_curvature_1=radius,
        radius_of_curvature_2=-radius,
        thickness=5.0,
        diameter=25.0,
        material="N-BK7",
        refractive_index=1.5168,
    )


def _shape(node):
    """The nesting, as nested tuples - what a tree comparison actually needs.

    A flat (node, position) list cannot distinguish two different trees that
    happen to contain the same elements, which is the whole point. Takes any
    node, so it compares a system's root against a group's children.
    """
    children = getattr(node, "root", node).children
    return tuple((child.__class__.__name__, child.name, _shape(child)) for child in children)


def _names(node):
    return [child.name for child in node.children]


class _TreeFixture(unittest.TestCase):
    def _nested(self, depth=1, name="Rig"):
        """A chain of sub-assemblies with one element at the bottom."""
        system = OpticalSystem(name=name)
        parent = system.root
        for level in range(depth):
            assembly = OpticalAssembly(f"Group{level}")
            parent.add_child(assembly)
            parent = assembly
        parent.add_child(OpticalElement(_lens("DeepLens"), name="DeepLens"))
        system._rebuild_from_tree()
        return system


class TestTheTreeSurvivesARoundTrip(_TreeFixture):
    def test_a_doublet_in_a_sub_assembly_stays_nested(self):
        """The issue's scenario."""
        system = OpticalSystem(name="Rig")
        sub = OpticalAssembly("Doublet")
        system.root.add_child(sub)
        sub.add_child(OpticalElement(_lens("A", 60.0), name="A"))
        sub.add_child(OpticalElement(_lens("B", -40.0), name="B"))
        system._rebuild_from_tree()

        back = OpticalSystem.from_dict(system.to_dict())

        self.assertEqual(_shape(back), _shape(system))
        self.assertEqual(
            [c.name for c in back.root.children],
            ["Doublet"],
            msg="the sub-assembly came back flattened into the root",
        )
        self.assertEqual(_names(back.root.children[0]), ["A", "B"])

    def test_nesting_one_level_deep_round_trips(self):
        system = self._nested(depth=1)

        back = OpticalSystem.from_dict(system.to_dict())

        self.assertEqual(_shape(back), _shape(system))

    def test_three_levels_deep_round_trips(self):
        system = self._nested(depth=3)

        back = OpticalSystem.from_dict(system.to_dict())

        self.assertEqual(_shape(back), _shape(system))

    def test_parent_links_are_restored(self):
        """parent is not implied by containment - it is a stored reference."""
        system = self._nested(depth=2)

        back = OpticalSystem.from_dict(system.to_dict())

        for group in back.root.children:
            self.assertIs(group.parent, back.root, "a child's parent pointer is wrong")
            for inner in group.children:
                self.assertIs(inner.parent, group)
                for leaf in inner.children:
                    self.assertIs(leaf.parent, inner)

    def test_local_positions_are_restored(self):
        """Positions are relative to the parent, so nesting changes their meaning."""
        system = OpticalSystem(name="Rig")
        sub = OpticalAssembly("Group")
        system.root.add_child(sub)
        element = OpticalElement(_lens("A"), name="A")
        element.position = type(element.position)(2.0, 0.5, 0.25)
        sub.add_child(element)
        system._rebuild_from_tree()

        back = OpticalSystem.from_dict(system.to_dict())

        restored = back.root.children[0].children[0]
        self.assertAlmostEqual(restored.position.x, 2.0, places=6)
        self.assertAlmostEqual(restored.position.y, 0.5, places=6)
        self.assertAlmostEqual(restored.position.z, 0.25, places=6)

    def test_rotations_are_restored(self):
        system = OpticalSystem(name="Rig")
        sub = OpticalAssembly("Group")
        system.root.add_child(sub)
        element = OpticalElement(_lens("A"), name="A")
        element.rotation = type(element.rotation)(1.5, -2.5, 3.5)
        sub.add_child(element)
        system._rebuild_from_tree()

        back = OpticalSystem.from_dict(system.to_dict())

        restored = back.root.children[0].children[0]
        self.assertAlmostEqual(restored.rotation.x, 1.5, places=6)
        self.assertAlmostEqual(restored.rotation.y, -2.5, places=6)
        self.assertAlmostEqual(restored.rotation.z, 3.5, places=6)

    def test_global_positions_are_unchanged_by_the_round_trip(self):
        """The optics must not move just because the format changed."""
        system = OpticalSystem(name="Rig")
        sub = OpticalAssembly("Group")
        system.root.add_child(sub)
        element = OpticalElement(_lens("A"), name="A")
        element.position = type(element.position)(3.0, 0.0, 0.0)
        sub.add_child(element)
        system._rebuild_from_tree()

        before = [(n.name, tuple(p.to_tuple())) for n, p in system.root.get_flat_list()]
        back = OpticalSystem.from_dict(system.to_dict())
        after = [(n.name, tuple(p.to_tuple())) for n, p in back.root.get_flat_list()]

        self.assertEqual(after, before)

    def test_a_second_round_trip_is_stable(self):
        """Re-saving must not drift - the flattened form used to compound."""
        system = self._nested(depth=2)

        once = OpticalSystem.from_dict(system.to_dict())
        twice = OpticalSystem.from_dict(once.to_dict())

        self.assertEqual(_shape(twice), _shape(once))
        self.assertEqual(_shape(twice), _shape(system))

    def test_an_unknown_node_type_round_trips_as_a_group(self):
        """Losing a subtree silently is worse than not knowing its class."""
        system = OpticalSystem(name="Rig")
        odd = OpticalAssembly("Future")
        odd.position = type(odd.position)(1.0, 0.0, 0.0)
        system.root.add_child(odd)
        odd.add_child(OpticalElement(_lens("A"), name="A"))
        system._rebuild_from_tree()

        data = system.to_dict()
        data["node_tree"]["children"][0]["type"] = "SomethingFromTheFuture"

        back = OpticalSystem.from_dict(data)

        self.assertEqual(len(back.root.children), 1)
        node = back.root.children[0]
        self.assertIsInstance(
            node,
            OpticalAssembly,
            "an unrecognised node came back as something else, so its meaning "
            "changed rather than merely being unknown",
        )
        self.assertEqual(_names(node), ["A"])


class TestTheFlatFormStillWorks(_TreeFixture):
    """The tree is written alongside, not instead of. Every consumer still reads it."""

    def test_the_flat_elements_key_is_still_present(self):
        system = self._nested(depth=2)

        data = system.to_dict()

        self.assertIn("elements", data, "the database and the GUI read this key")
        self.assertEqual(len(data["elements"]), 1)

    def test_the_flat_elements_have_the_fields_consumers_use(self):
        system = OpticalSystem(name="S")
        system.add_lens(_lens("A", 60.0))
        system.add_lens(_lens("B", -40.0), air_gap_before=5.0)

        data = system.to_dict()
        first = data["elements"][0]

        for key in ("lens", "lens_id", "position", "decenter_y", "decenter_z"):
            self.assertIn(key, first, f"consumers read {key}")
        self.assertEqual(data["air_gaps"][0]["thickness"], 5.0)

    def test_flattening_is_json_serializable(self):
        system = self._nested(depth=2)

        data = json.loads(json.dumps(system.to_dict()))

        self.assertIn("node_tree", data)

    def test_a_file_without_a_tree_still_loads(self):
        """An older export, and the case that must not regress."""
        system = OpticalSystem(name="Old")
        system.add_lens(_lens("A", 60.0))
        system.add_lens(_lens("B", -40.0), air_gap_before=5.0)

        legacy = {k: v for k, v in system.to_dict().items() if k != "node_tree"}

        back = OpticalSystem.from_dict(legacy)

        self.assertEqual([e.lens.name for e in back.elements], ["A", "B"])

    def test_a_file_without_a_tree_keeps_its_saved_positions(self):
        """#438's fix must survive this one."""
        system = OpticalSystem(name="Old")
        system.add_lens(_lens("A", 60.0))
        system.root.children[0].position = type(system.root.children[0].position)(15.0, 0.0, 0.0)
        system._rebuild_from_tree()

        data = system.to_dict()
        data.pop("node_tree", None)
        legacy = data

        back = OpticalSystem.from_dict(legacy)

        positions = [p.to_tuple()[0] for _, p in back.root.get_flat_list()]
        self.assertAlmostEqual(positions[0], 15.0, places=6)

    def test_the_node_tree_does_not_leak_into_user_metadata(self):
        """It is ours, not the user's settings."""
        system = self._nested(depth=1)
        system.metadata["my_note"] = "keep me"

        back = OpticalSystem.from_dict(system.to_dict())

        self.assertNotIn("node_tree", back.metadata)
        self.assertEqual(back.metadata.get("my_note"), "keep me")

    def test_a_node_tree_inside_the_metadata_blob_is_stripped(self):
        """The case _SYSTEM_SERIALIZED_KEYS exists for.

        A metadata blob built by merging a previous to_dict() output carries
        serialized keys inside it, and they are not user settings. My first test
        put node_tree at the top level, where it never had any effect - so it
        passed whether or not the guard existed.
        """
        system = self._nested(depth=1)

        data = system.to_dict()
        data["metadata"] = dict(data["metadata"])
        data["metadata"]["node_tree"] = {"type": "OpticalAssembly", "children": []}
        data["metadata"]["elements"] = ["stale"]

        back = OpticalSystem.from_dict(data)

        self.assertNotIn("node_tree", back.metadata)
        self.assertNotIn(
            "elements", back.metadata, "a stale serialized blob leaked into the metadata"
        )

    def test_a_shared_lens_lookup_is_used_through_the_tree(self):
        """LensStorage passes a lookup so elements share one Lens instance.

        Keyed by the id the tree actually carries - which is what the database
        does, since it looks the lens up by the id stored alongside the element.
        """
        system = self._nested(depth=1)
        original = system.elements[0].lens
        shared = _lens("DeepLens")
        # The lookup must be keyed by the id in the file, not by a fresh one.
        shared.id = original.id

        back = OpticalSystem.from_dict(system.to_dict(), lens_lookup={original.id: shared})

        leaf = back.root.children[0].children[0]
        self.assertIs(leaf.element_model, shared, "the shared instance was not reused")


class TestTheSystemStillBehavesLikeASystem(_TreeFixture):
    """Structural fidelity is only worth anything if the optics are unchanged."""

    def test_a_flat_system_round_trips_unchanged(self):
        system = OpticalSystem(name="Doublet")
        system.add_lens(_lens("A", 60.0))
        system.add_lens(_lens("B", -40.0), air_gap_before=5.0)

        back = OpticalSystem.from_dict(system.to_dict())

        self.assertEqual(len(back.elements), 2)
        self.assertEqual(_shape(back), _shape(system))

    def test_ray_tracing_agrees_before_and_after(self):
        system = OpticalSystem(name="Doublet")
        system.add_lens(_lens("A", 60.0))
        system.add_lens(_lens("B", -40.0), air_gap_before=5.0)

        back = OpticalSystem.from_dict(system.to_dict())

        from src.ray_tracer import SystemRayTracer
        from src.ray import Ray

        def trace(target):
            tracer = SystemRayTracer(target)
            ray = Ray(-100.0, 5.0)
            tracer.trace_ray(ray)
            return tuple(ray.path[-1])

        for before, after in zip(trace(system), trace(back)):
            self.assertAlmostEqual(before, after, places=9)

    def test_element_count_matches_the_tree(self):
        system = self._nested(depth=2)

        back = OpticalSystem.from_dict(system.to_dict())

        self.assertEqual(len(back.elements), len(system.elements))


if __name__ == "__main__":
    unittest.main()
