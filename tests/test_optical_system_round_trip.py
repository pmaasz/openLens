"""Regression: OpticalSystem.to_dict/from_dict must not lose positions.

``to_dict`` saves each element's absolute ``position``, but ``from_dict``
never read it back: it rebuilt the system from the air gaps alone, so every
element landed wherever the gaps put it.

Two concrete losses:

- an assembly at x = 20 came back as a root-level element at x = 0;
- a standalone first element saved at x = 15 loaded at x = 0.

The saved ``position`` was simply ignored data.

This format is flat - it stores a list of elements and cannot represent a
nested assembly tree - so the tree shape is out of scope here. What is in
scope is that everything the format *does* store comes back: absolute
positions, per-surface alignment, and the optical result the system
produces.
"""

import unittest

from openlens.lens import Lens
from openlens.optical_system import OpticalSystem
from openlens.vector3 import vec3


def _system():
    """A three-element system with non-trivial absolute positions."""
    system = OpticalSystem(name="Round Trip")
    system.add_lens(Lens(name="First", thickness=4.0), air_gap_before=0.0)
    system.add_lens(Lens(name="Second", thickness=6.0), air_gap_before=2.0)
    system.add_lens(Lens(name="Third", thickness=3.0), air_gap_before=1.0)
    return system


class TestPositionsSurviveARoundTrip(unittest.TestCase):
    """Everything to_dict stores has to come back."""

    def test_element_positions_are_preserved(self):
        system = _system()
        before = [element.position for element in system.elements]

        restored = OpticalSystem.from_dict(system.to_dict())

        self.assertEqual(
            [element.position for element in restored.elements],
            before,
            "the element positions changed across the round trip",
        )

    def test_the_first_element_offset_is_preserved(self):
        """A first element that does not start at x = 0 must stay put."""
        system = OpticalSystem(name="Offset")
        system.add_lens(Lens(name="Only", thickness=5.0))
        # Push the single element away from the origin.
        system.root.children[0].position = vec3(15.0, 0.0, 0.0)
        system._rebuild_from_tree()

        restored = OpticalSystem.from_dict(system.to_dict())

        self.assertAlmostEqual(restored.elements[0].position, 15.0, places=6)

    def test_air_gaps_are_preserved(self):
        system = _system()
        before = [gap.thickness for gap in system.air_gaps]

        restored = OpticalSystem.from_dict(system.to_dict())

        self.assertEqual([gap.thickness for gap in restored.air_gaps], before)

    def test_per_surface_alignment_is_preserved(self):
        system = OpticalSystem(name="Tilted")
        system.add_lens(
            Lens(name="Skewed", thickness=5.0),
            decenter_y=0.25,
            decenter_z=-0.5,
            tilt_x=0.01,
            tilt_y=0.02,
            tilt_z=0.03,
        )

        restored = OpticalSystem.from_dict(system.to_dict())
        element = restored.elements[0]

        self.assertAlmostEqual(element.decenter_y, 0.25, places=6)
        self.assertAlmostEqual(element.decenter_z, -0.5, places=6)
        self.assertAlmostEqual(element.tilt_x, 0.01, places=6)
        self.assertAlmostEqual(element.tilt_y, 0.02, places=6)
        self.assertAlmostEqual(element.tilt_z, 0.03, places=6)

    def test_the_optical_result_is_preserved(self):
        """The property that matters: the system still images the same way."""
        system = _system()

        restored = OpticalSystem.from_dict(system.to_dict())

        before = system.calculate_back_focal_length()
        after = restored.calculate_back_focal_length()

        self.assertIsNotNone(before)
        self.assertIsNotNone(after)
        self.assertAlmostEqual(before, after, places=6)


class TestLosslessFormatWhereItClaimsToBe(unittest.TestCase):
    """Guards against the format quietly losing something else."""

    def test_element_count_and_names_are_preserved(self):
        system = _system()

        restored = OpticalSystem.from_dict(system.to_dict())

        self.assertEqual(
            [element.lens.name for element in restored.elements],
            [element.lens.name for element in system.elements],
        )

    def test_system_name_and_stop_are_preserved(self):
        system = _system()
        system.aperture_stop_gap = 1
        system.aperture_stop_diameter = 12.0

        restored = OpticalSystem.from_dict(system.to_dict())

        self.assertEqual(restored.name, system.name)
        self.assertEqual(restored.aperture_stop_gap, 1)
        self.assertAlmostEqual(restored.aperture_stop_diameter, 12.0, places=6)

    def test_a_system_saved_and_loaded_from_json_keeps_positions(self):
        """The same thing through the file path the GUI's Save As uses."""
        import json
        import os
        import tempfile

        system = _system()
        before = [element.position for element in system.elements]

        handle = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        try:
            json.dump(system.to_dict(), handle)
            handle.close()

            with open(handle.name) as source:
                restored = OpticalSystem.from_dict(json.load(source))
        finally:
            os.unlink(handle.name)

        self.assertEqual([element.position for element in restored.elements], before)


if __name__ == "__main__":
    unittest.main()
