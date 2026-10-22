#!/usr/bin/env python3
"""
A thickness variable must move the elements that follow it.

``_apply_variables`` wrote ``lens.thickness`` and then called
``_update_positions()``, which advances by the element's cached thickness
wrapper - a copy of the lens value taken at construction. The wrapper was
stale, so the element did not move, the air gap the positions implied no
longer matched ``air_gaps``, and the ABCD model and the tracer analysed two
different systems.
"""

import unittest

from openlens.analysis.paraxial import find_paraxial_focus
from openlens.lens import Lens
from openlens.optical_system import OpticalSystem
from openlens.optimizer import LensOptimizer, OptimizationVariable


def _system():
    system = OpticalSystem(name="two element")
    for name, radius in (("L1", 70.0), ("L2", 80.0)):
        system.add_lens(
            Lens(
                name=name,
                radius_of_curvature_1=radius,
                radius_of_curvature_2=-100.0,
                thickness=5.0,
                diameter=20.0,
                refractive_index=1.5168,
            ),
            air_gap_before=0.0 if name == "L1" else 10.0,
        )
    return system


def _optimizer():
    return LensOptimizer(
        _system(), [OptimizationVariable("T1", 0, "thickness", 5.0, 1.0, 20.0)], []
    )


class TestThicknessVariableMovesTheGeometry(unittest.TestCase):
    """The applied design must be the one the model describes."""

    def test_the_element_moves_with_its_thickness(self):
        """The second element must follow the thicker first one"""
        applied = _optimizer()._apply_variables([9.0])

        self.assertEqual(applied.elements[0].lens.thickness, 9.0)
        self.assertEqual(
            applied.elements[1].position,
            19.0,
            msg="the second element did not move with the thickness",
        )

    def test_the_air_gap_is_preserved(self):
        """The positions must imply the gap the model declares"""
        applied = _optimizer()._apply_variables([9.0])

        gap = applied.elements[1].position - (
            applied.elements[0].position + applied.elements[0].lens.thickness
        )
        self.assertAlmostEqual(gap, applied.air_gaps[0].thickness, places=9)

    def test_the_abc_and_the_tracer_see_the_same_system(self):
        """The two models must not disagree about where the focus is.

        The ABCD matrix and the paraxial trace are different models, so they
        never agree exactly; what matters is that the applied design is not
        *less* consistent than the nominal one.
        """
        nominal = _system()
        nominal_last = nominal.elements[-1].position + nominal.elements[-1].lens.thickness
        nominal_gap = nominal.calculate_back_focal_length() - (
            find_paraxial_focus(nominal) - nominal_last
        )

        applied = _optimizer()._apply_variables([9.0])
        last_vertex = applied.elements[-1].position + applied.elements[-1].lens.thickness
        applied_gap = applied.calculate_back_focal_length() - (
            find_paraxial_focus(applied) - last_vertex
        )

        self.assertAlmostEqual(
            applied_gap,
            nominal_gap,
            places=2,
            msg="the ABCD model and the tracer analysed different systems",
        )

    def test_a_thick_lens_does_not_pass_through_its_neighbour(self):
        """The neighbour must move, not stay where the lens now reaches"""
        applied = _optimizer()._apply_variables([17.0])

        rear_vertex = applied.elements[0].position + applied.elements[0].lens.thickness
        self.assertGreaterEqual(
            applied.elements[1].position,
            rear_vertex,
            msg="the second element stayed inside the first one",
        )
