#!/usr/bin/env python3
"""
The robust merit must measure every tolerance the Monte Carlo can randomise.

``RobustMeritFunction`` only understood RADIUS_1/2, THICKNESS and
REFRACTIVE_INDEX; every other operand type was skipped, so a tolerance set
full of air gaps, decenters and tilts contributed exactly zero sensitivity.
The index perturbation was written straight into ``lens.refractive_index``,
which the spot analysis then overwrote.
"""

import copy
import unittest

from openlens.desensitization import RobustMeritFunction
from openlens.lens import Lens
from openlens.optical_system import OpticalSystem
from openlens.optimizer import MeritFunction, OptimizationTarget
from openlens.tolerancing import ToleranceOperand, ToleranceType


def _system():
    system = OpticalSystem(name="two element")
    system.add_lens(
        Lens(
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
            radius_of_curvature_1=80.0,
            radius_of_curvature_2=-120.0,
            thickness=5.0,
            diameter=25.0,
            refractive_index=1.5168,
        ),
        air_gap_before=10.0,
    )
    return system


TARGETS = [
    OptimizationTarget("focal_length", 100.0, 1.0, "target"),
    OptimizationTarget("rms_spot_radius", 0.0, 100.0, "minimize"),
]


class TestRobustMeritCoversTheToleranceTypes(unittest.TestCase):
    """The sensitivity must reflect the tolerances that are configured."""

    def _nominal(self):
        return MeritFunction(_system(), TARGETS).evaluate(_system())

    def test_an_air_gap_tolerance_contributes(self):
        """An air gap changes the merit, so it must be in the sensitivity"""
        system = _system()
        nominal = MeritFunction(system, TARGETS).evaluate(system)

        perturbed = copy.deepcopy(system)
        perturbed.air_gaps[0].thickness += 0.5
        perturbed._update_positions()
        true_change = abs(MeritFunction(perturbed, TARGETS).evaluate(perturbed) - nominal)

        self.assertGreater(true_change, 0.1, "the test case does not change the merit")

        robust = RobustMeritFunction(
            _system(),
            TARGETS,
            [ToleranceOperand(0, ToleranceType.AIR_GAP, -0.5, 0.5)],
            sensitivity_weight=1.0,
        )
        contribution = robust.evaluate(_system()) - nominal

        self.assertAlmostEqual(
            contribution,
            true_change,
            places=6,
            msg="the air gap tolerance was not measured",
        )

    def test_a_decenter_tolerance_contributes(self):
        """A decenter is a tolerance the Monte Carlo randomises too"""
        system = _system()
        nominal = MeritFunction(system, TARGETS).evaluate(system)

        robust = RobustMeritFunction(
            _system(),
            TARGETS,
            [ToleranceOperand(0, ToleranceType.DECENTER_Y, -0.05, 0.05)],
            sensitivity_weight=1.0,
        )
        contribution = robust.evaluate(_system()) - nominal

        self.assertNotEqual(
            contribution,
            0.0,
            msg="a decenter tolerance contributed nothing to the sensitivity",
        )

    def test_the_design_is_restored_after_the_evaluation(self):
        """The perturbation must be undone exactly"""
        system = _system()
        before = [
            (element.lens.radius_of_curvature_1, element.lens.thickness, element.position)
            for element in system.elements
        ]
        gaps_before = [gap.thickness for gap in system.air_gaps]

        robust = RobustMeritFunction(
            system,
            TARGETS,
            [
                ToleranceOperand(0, ToleranceType.RADIUS_1, -0.5, 0.5),
                ToleranceOperand(0, ToleranceType.THICKNESS, -0.1, 0.1),
                ToleranceOperand(0, ToleranceType.AIR_GAP, -0.5, 0.5),
            ],
            sensitivity_weight=1.0,
        )
        robust.evaluate(system)

        after = [
            (element.lens.radius_of_curvature_1, element.lens.thickness, element.position)
            for element in system.elements
        ]
        self.assertEqual(after, before, "the evaluation left the design perturbed")
        self.assertEqual([gap.thickness for gap in system.air_gaps], gaps_before)

    def test_an_index_tolerance_is_measured(self):
        """The index perturbation must reach the glass the trace uses"""
        system = _system()
        nominal = MeritFunction(system, TARGETS).evaluate(system)

        robust = RobustMeritFunction(
            _system(),
            TARGETS,
            [ToleranceOperand(0, ToleranceType.REFRACTIVE_INDEX, -0.05, 0.05)],
            sensitivity_weight=1.0,
        )
        contribution = robust.evaluate(_system()) - nominal

        self.assertNotEqual(
            contribution,
            0.0,
            msg="the index tolerance was overwritten before the merit was read",
        )


if __name__ == "__main__":
    unittest.main()
