"""Regression: a node's modifiers must survive a save/load cycle.

``OpticalNode.to_dict`` dropped ``modifiers`` entirely, with a ``# TODO:
Serialize modifiers`` that had been there since the node tree was introduced. Any
node carrying a modifier lost it on save.

**The modifiers are currently inert.** ``get_local_transform`` uses only
``position`` and ``rotation``, and nothing anywhere in the tree applies a
modifier, so today the loss does not move any element - contrary to what a
reading of the issue would suggest. What *is* true now is that ``to_dict`` is
lossy: it returns a dict that does not describe the node.

These tests therefore pin two things, and say which is which:

- the round trip is faithful (what is fixed now)
- global positions are unchanged by it, and the modifiers are demonstrably not
  applied (what is true, recorded so the day one *is* applied, the tests say so)

An unregistered modifier type is preserved as a generic one with a warning,
rather than dropped. Losing data silently is the failure this issue is about.
"""

import json
import logging
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.lens import Lens
from src.optical_node import (
    MODIFIER_REGISTRY,
    OpticalAssembly,
    OpticalElement,
    SurfaceModifier,
    modifier_from_dict,
    register_modifier,
)
from src.optical_system import OpticalSystem


def _lens(name="A"):
    return Lens(
        name=name,
        radius_of_curvature_1=50.0,
        radius_of_curvature_2=-50.0,
        thickness=5.0,
        diameter=25.0,
        material="N-BK7",
        refractive_index=1.5168,
    )


class _Asphere(SurfaceModifier):
    """A registered subclass, to prove the registry path."""

    def __init__(self, name="Asphere", curvature=0.0):
        super().__init__(name)
        self.curvature = curvature


register_modifier(_Asphere)


def _system_with_modifiers(monkey=None):
    system = OpticalSystem(name="Rig")
    group = OpticalAssembly("Group")
    system.root.add_child(group)
    element = OpticalElement(_lens(), name="A")
    for modifier in monkey or []:
        element.modifiers.append(modifier)
    group.add_child(element)
    system._rebuild_from_tree()
    return system, element


class TestModifiersAreSerialized(unittest.TestCase):
    def test_a_node_dict_has_a_modifiers_key(self):
        _, element = _system_with_modifiers([SurfaceModifier("Shift")])

        self.assertIn("modifiers", element.to_dict())

    def test_the_modifier_is_written(self):
        _, element = _system_with_modifiers([SurfaceModifier("Shift")])

        written = element.to_dict()["modifiers"]

        self.assertEqual(len(written), 1)
        self.assertEqual(written[0]["name"], "Shift")

    def test_the_base_type_is_recorded(self):
        _, element = _system_with_modifiers([SurfaceModifier("Shift")])

        self.assertEqual(element.to_dict()["modifiers"][0]["type"], "SurfaceModifier")

    def test_a_subclass_records_its_own_type_and_fields(self):
        _, element = _system_with_modifiers([_Asphere("Front", curvature=0.25)])

        written = element.to_dict()["modifiers"][0]

        self.assertEqual(written["type"], "_Asphere")
        self.assertEqual(written["curvature"], 0.25)

    def test_several_modifiers_keep_their_order(self):
        _, element = _system_with_modifiers(
            [SurfaceModifier("One"), _Asphere("Two"), SurfaceModifier("Three")]
        )

        names = [m["name"] for m in element.to_dict()["modifiers"]]

        self.assertEqual(names, ["One", "Two", "Three"])

    def test_a_node_without_modifiers_writes_an_empty_list(self):
        _, element = _system_with_modifiers()

        self.assertEqual(element.to_dict()["modifiers"], [])

    def test_the_dict_is_json_serializable(self):
        _, element = _system_with_modifiers([_Asphere("Front", curvature=0.25)])

        text = json.dumps(element.to_dict())

        self.assertIn("Front", text)

    def test_an_assembly_without_modifiers_is_unaffected(self):
        system, _ = _system_with_modifiers()

        self.assertEqual(system.root.children[0].to_dict()["modifiers"], [])


class TestModifiersSurviveARoundTrip(unittest.TestCase):
    def _round_trip(self, system):
        return OpticalSystem.from_dict(system.to_dict())

    def test_a_modifier_comes_back(self):
        system, _ = _system_with_modifiers([SurfaceModifier("Shift")])

        back = self._round_trip(system)

        leaf = back.root.children[0].children[0]
        self.assertEqual([m.name for m in leaf.modifiers], ["Shift"])

    def test_the_type_comes_back(self):
        system, _ = _system_with_modifiers([_Asphere("Front", curvature=0.25)])

        back = self._round_trip(system)

        leaf = back.root.children[0].children[0]
        self.assertIsInstance(leaf.modifiers[0], _Asphere)

    def test_a_subclasss_fields_come_back(self):
        system, _ = _system_with_modifiers([_Asphere("Front", curvature=0.25)])

        back = self._round_trip(system)

        self.assertAlmostEqual(back.root.children[0].children[0].modifiers[0].curvature, 0.25)

    def test_modifier_order_is_preserved(self):
        system, _ = _system_with_modifiers(
            [SurfaceModifier("One"), _Asphere("Two"), SurfaceModifier("Three")]
        )

        back = self._round_trip(system)

        leaf = back.root.children[0].children[0]
        self.assertEqual([m.name for m in leaf.modifiers], ["One", "Two", "Three"])

    def test_several_round_trips_are_stable(self):
        system, _ = _system_with_modifiers([_Asphere("Front", curvature=0.25)])

        once = self._round_trip(system)
        twice = self._round_trip(once)
        thrice = self._round_trip(twice)

        names = [m.name for m in thrice.root.children[0].children[0].modifiers]
        self.assertEqual(names, ["Front"])

    def test_a_node_without_modifiers_comes_back_without_them(self):
        system, _ = _system_with_modifiers()

        back = self._round_trip(system)

        self.assertEqual(back.root.children[0].children[0].modifiers, [])


class TestGlobalPositionsAreUnchanged(unittest.TestCase):
    """The issue asks for this comparison, and for a reason worth recording.

    It passes today - but not because the round trip is careful. It passes
    because no modifier is applied to anything. If one ever is, this test starts
    failing, which is the point of pinning it now.
    """

    def test_positions_match_across_a_round_trip(self):
        system, _ = _system_with_modifiers([_Asphere("Front", curvature=0.25)])

        back = OpticalSystem.from_dict(system.to_dict())

        before = [(n.name, tuple(p.to_tuple())) for n, p in system.root.get_flat_list()]
        after = [(n.name, tuple(p.to_tuple())) for n, p in back.root.get_flat_list()]
        self.assertEqual(after, before)

    def test_a_modifier_does_not_move_anything_today(self):
        """Records the current truth, so it cannot be mistaken for the fix."""
        system, element = _system_with_modifiers()
        before = tuple(element.get_global_position().to_tuple())

        element.modifiers.append(_Asphere("Front", curvature=0.25))
        after = tuple(element.get_global_position().to_tuple())

        self.assertEqual(
            before,
            after,
            "a modifier now moves the element - good, but the docstrings and "
            "tests that say modifiers are inert must be updated with it",
        )


class TestUnknownModifiersArePreservedNotDropped(unittest.TestCase):
    def _capture(self):
        records = []

        class _Capture(logging.Handler):
            def emit(self, record):
                records.append(record)

        logger = logging.getLogger("src.optical_node")
        previous = logger.level
        logger.setLevel(logging.WARNING)
        handler = _Capture()
        logger.addHandler(handler)
        self.addCleanup(logger.removeHandler, handler)
        self.addCleanup(logger.setLevel, previous)
        return records

    def test_an_unregistered_type_keeps_its_name(self):
        modifier = modifier_from_dict({"name": "Mystery", "type": "FromTheFuture"})

        self.assertEqual(modifier.name, "Mystery")

    def test_an_unregistered_type_records_what_it_was(self):
        modifier = modifier_from_dict({"name": "Mystery", "type": "FromTheFuture"})

        self.assertEqual(
            modifier.original_type,
            "FromTheFuture",
            "without this the file loses all trace of what the modifier was",
        )

    def test_an_unregistered_type_is_warned_about(self):
        records = self._capture()

        modifier_from_dict({"name": "Mystery", "type": "FromTheFuture"})

        self.assertTrue(
            any("not registered" in r.getMessage() for r in records),
            "an unrestorable modifier was restored without saying so",
        )

    def test_the_base_type_does_not_warn(self):
        records = self._capture()

        modifier_from_dict({"name": "Plain", "type": "SurfaceModifier"})

        self.assertEqual(records, [], "warned about a modifier type it can restore")

    def test_a_registered_type_does_not_warn(self):
        records = self._capture()

        modifier_from_dict({"name": "A", "type": "_Asphere", "curvature": 0.1})

        self.assertEqual(records, [])

    def test_an_unknown_modifier_survives_a_system_round_trip(self):
        data = {
            "name": "Rig",
            "node_tree": {
                "name": "Root",
                "type": "OpticalAssembly",
                "position": [0, 0, 0],
                "rotation": [0, 0, 0],
                "children": [
                    {
                        "name": "A",
                        "type": "OpticalElement",
                        "position": [0, 0, 0],
                        "rotation": [0, 0, 0],
                        "modifiers": [{"name": "Mystery", "type": "FromTheFuture"}],
                        "element_model": _lens().to_dict(),
                        "children": [],
                    }
                ],
            },
        }

        back = OpticalSystem.from_dict(data)

        leaf = back.root.children[0]
        self.assertEqual([m.name for m in leaf.modifiers], ["Mystery"])

    def test_the_registry_is_reversible(self):
        """Tests must not leak state into each other."""
        self.addCleanup(MODIFIER_REGISTRY.pop, "Temporary", None)
        MODIFIER_REGISTRY["Temporary"] = SurfaceModifier

        modifier = modifier_from_dict({"name": "T", "type": "Temporary"})

        self.assertEqual(modifier.name, "T")


class TestTheStaleTodoIsGone(unittest.TestCase):
    def test_no_todo_remains(self):
        source = (Path(__file__).resolve().parent.parent / "src" / "optical_node.py").read_text()

        self.assertNotIn(
            "TODO: Serialize modifiers",
            source,
            "the marker is still there, so the next reader cannot tell whether " "this is done",
        )


if __name__ == "__main__":
    unittest.main()
