#!/usr/bin/env python3
"""The physical penalty must judge a lens where it is actually polished.

``MeritFunction._penalty_physical`` evaluated the interior thickness at
``lens.diameter / 2`` and the inter-element clearance at the mechanical
semi-diameter, although ``Lens.calculate_edge_thickness`` deliberately uses
``get_manufacturing_radius`` (the clear aperture when it is smaller than the
blank). A mounted lens with a small clear aperture in a large blank was
therefore scored hard-infeasible even though its real edge thickness is
positive - and no optical variable inside the clear aperture could repair a
collision that only exists in the blank's rim.
"""

import unittest

from openlens.lens import Lens
from openlens.optimizer import MeritFunction, OptimizationTarget
from openlens.optical_system import OpticalSystem


def _mounted_singlet(**overrides):
    params = dict(
        radius_of_curvature_1=40.0,
        radius_of_curvature_2=-40.0,
        thickness=2.0,
        diameter=30.0,
        refractive_index=1.5168,
        clear_aperture_1=8.0,
        clear_aperture_2=8.0,
    )
    params.update(overrides)
    system = OpticalSystem("mounted")
    system.add_lens(Lens(**params))
    return system


def _merit(system):
    targets = [OptimizationTarget("focal_length", 100.0, 1.0, "target")]
    return MeritFunction(system, targets)


class TestClearAperturePhysicalPenalty(unittest.TestCase):
    def test_a_mounted_lens_with_positive_edge_thickness_has_no_penalty(self):
        """R=40, t=2, D=30, CA=8: the real rim at h=4 is 1.60 mm thick."""
        system = _mounted_singlet()
        lens = system.elements[0].lens

        self.assertAlmostEqual(lens.get_manufacturing_radius(), 4.0, places=6)
        self.assertGreater(lens.calculate_edge_thickness(), 0.0)
        self.assertEqual(_merit(system)._penalty_physical(system), 0.0)

    def test_the_same_lens_without_a_clear_aperture_is_still_infeasible(self):
        """At the 15 mm blank radius the surfaces genuinely cross."""
        system = _mounted_singlet(clear_aperture_1=None, clear_aperture_2=None)
        lens = system.elements[0].lens

        self.assertLess(lens.calculate_edge_thickness(), 0.0)
        self.assertGreaterEqual(_merit(system)._penalty_physical(system), 1e8)

    def test_inter_element_clearance_is_judged_at_the_clear_aperture(self):
        """Curved neighbours clear at h=4 but would collide at h=15."""
        system = OpticalSystem("pair")
        system.add_lens(
            Lens(
                radius_of_curvature_1=100.0,
                radius_of_curvature_2=200.0,
                thickness=2.0,
                diameter=30.0,
                clear_aperture_1=8.0,
                clear_aperture_2=8.0,
            )
        )
        system.add_lens(
            Lens(
                radius_of_curvature_1=-200.0,
                radius_of_curvature_2=-100.0,
                thickness=2.0,
                diameter=30.0,
                clear_aperture_1=8.0,
                clear_aperture_2=8.0,
            ),
            air_gap_before=0.2,
        )

        self.assertEqual(_merit(system)._penalty_physical(system), 0.0)
        # The same assembly without clear apertures meets at the blank rim.
        for element in system.elements:
            element.lens.clear_aperture_1 = None
            element.lens.clear_aperture_2 = None
        self.assertGreaterEqual(_merit(system)._penalty_physical(system), 1e8)


if __name__ == "__main__":
    unittest.main()
