#!/usr/bin/env python3
"""
A thickness tolerance must move the elements, not the air gap.

``_apply_value`` wrote ``lens.thickness`` and then called
``_update_positions()``, which advanced by the element's *copy* of the lens
value. The copy was stale, so the element did not move and the gap to the
next element absorbed the change: a +2 mm thickness tolerance turned a 10 mm
air gap into an 8 mm one.
"""

import unittest

from openlens.lens import Lens
from openlens.optical_system import OpticalSystem
from openlens.tolerancing import ToleranceType, _apply_value


def _system():
    system = OpticalSystem("two element")
    system.add_lens(
        Lens(
            name="L1",
            radius_of_curvature_1=70.0,
            radius_of_curvature_2=-100.0,
            thickness=5.0,
            diameter=25.0,
            refractive_index=1.5168,
        ),
        air_gap_before=0.0,
    )
    system.add_lens(
        Lens(
            name="L2",
            radius_of_curvature_1=80.0,
            radius_of_curvature_2=-120.0,
            thickness=5.0,
            diameter=25.0,
            refractive_index=1.5168,
        ),
        air_gap_before=10.0,
    )
    return system


class TestThicknessToleranceMovesTheElements(unittest.TestCase):
    """The perturbed design must be the one the tolerance describes."""

    def test_the_element_moves_with_its_thickness(self):
        """The second element must follow the thicker first one"""
        system = _system()

        applied = _apply_value(system, ToleranceType.THICKNESS, 0, 2.0)

        self.assertTrue(applied)
        self.assertEqual(system.elements[0].lens.thickness, 7.0)
        self.assertEqual(
            system.elements[1].position,
            17.0,
            msg="the second element did not move with the thickness",
        )

    def test_the_air_gap_is_unchanged(self):
        """The gap is a mechanical dimension, not the tolerance's business"""
        system = _system()

        _apply_value(system, ToleranceType.THICKNESS, 0, 2.0)

        gap = system.elements[1].position - (
            system.elements[0].position + system.elements[0].lens.thickness
        )
        self.assertAlmostEqual(gap, 10.0, places=9)
        self.assertEqual([g.thickness for g in system.air_gaps], [10.0])

    def test_the_element_and_its_lens_never_disagree(self):
        """The element's thickness is the lens's, not a copy of it"""
        system = _system()

        system.elements[0].lens.thickness = 9.0

        self.assertEqual(system.elements[0].thickness, 9.0)
        self._assert_positions_follow(system)

    def _assert_positions_follow(self, system):
        system._update_positions()
        gap = system.elements[1].position - (
            system.elements[0].position + system.elements[0].lens.thickness
        )
        self.assertAlmostEqual(gap, 10.0, places=9)


if __name__ == "__main__":
    unittest.main()
