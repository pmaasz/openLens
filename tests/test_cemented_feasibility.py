#!/usr/bin/env python3
"""
A cemented interface must be a feasible geometry.

A cemented doublet shares a surface between its elements, which the model
represents as an air gap of zero. The merit function treated every gap as an
air space, so the cemented interface collected a soft penalty for the missing
air and a hard 1e8 for an edge clearance of exactly zero - making the
application's own doublet optimizer permanently infeasible.
"""

import unittest

from openlens.lens import Lens
from openlens.optical_system import OpticalSystem, create_doublet
from openlens.optimizer import MeritFunction, create_doublet_optimizer


def _cemented_doublet():
    """Two elements sharing a surface: the second's front radius matches the
    first's back radius, as a cemented doublet must."""
    system = OpticalSystem(name="Cemented")
    system.add_lens(
        Lens(
            name="Crown",
            radius_of_curvature_1=50.0,
            radius_of_curvature_2=-50.0,
            thickness=8.0,
            diameter=25.0,
            material="N-BK7",
            refractive_index=1.5168,
        ),
        air_gap_before=0.0,
    )
    system.add_lens(
        Lens(
            name="Flint",
            radius_of_curvature_1=-50.0,
            radius_of_curvature_2=-100.0,
            thickness=5.0,
            diameter=25.0,
            material="SF11",
            refractive_index=1.78472,
        ),
        air_gap_before=0.0,
    )
    return system


class TestCementedInterfaceIsFeasible(unittest.TestCase):
    """A cemented interface is a manufacturable geometry."""

    def test_a_cemented_doublet_has_no_physical_penalty(self):
        """The zero gap must not be read as a missing air space"""
        system = _cemented_doublet()
        self.assertEqual([g.thickness for g in system.air_gaps], [0.0])

        penalty = MeritFunction(system, [])._penalty_physical(system)

        self.assertEqual(
            penalty,
            0.0,
            msg="a cemented doublet was scored as physically infeasible",
        )

    def test_the_built_in_doublet_optimizer_converges(self):
        """The shipped optimizer must reach a merit far below the hard penalty"""
        optimizer = create_doublet_optimizer(create_doublet(100.0, 50.0), 100.0)
        result = optimizer.optimize(max_iterations=100)

        self.assertLess(
            result.final_merit,
            1e6,
            msg="the doublet optimizer never left the hard-penalty range",
        )
        self.assertLess(
            optimizer.merit_function._penalty_physical(result.optimized_system),
            1e6,
            msg="the optimized doublet is still physically infeasible",
        )

    def test_a_real_air_gap_is_still_penalised(self):
        """A gap that is too small must still be reported"""
        system = OpticalSystem(name="Air")
        system.add_lens(
            Lens(
                name="L1",
                radius_of_curvature_1=50.0,
                radius_of_curvature_2=-50.0,
                thickness=8.0,
                diameter=25.0,
                refractive_index=1.5168,
            )
        )
        system.add_lens(
            Lens(
                name="L2",
                radius_of_curvature_1=-50.0,
                radius_of_curvature_2=-100.0,
                thickness=5.0,
                diameter=25.0,
                refractive_index=1.5168,
            ),
            air_gap_before=0.01,
        )

        penalty = MeritFunction(system, [])._penalty_physical(system)

        self.assertGreater(penalty, 0.0, "a 0.01 mm air gap was accepted")


if __name__ == "__main__":
    unittest.main()
