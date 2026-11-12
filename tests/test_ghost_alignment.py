#!/usr/bin/env python3
"""Ghost paths must follow the element's decenter and tilt.

``GhostAnalyzer._interact`` built each surface tracer as
``LensRayTracer3D(lens, x_offset=element.position)`` and dropped the element's
lateral offset and rotation. Ghost paths for a decentered or tilted system
were therefore traced as if every element were on-axis, while the rest of the
3D tracer honours the node transform.
"""

import unittest

from openlens.analysis.ghost import GhostAnalyzer
from openlens.lens import Lens
from openlens.optical_system import OpticalSystem


def _system(decenter_y: float = 0.0, decenter_z: float = 0.0, tilt_z: float = 0.0):
    system = OpticalSystem()
    system.add_lens(
        Lens(
            radius_of_curvature_1=100.0,
            radius_of_curvature_2=-100.0,
            refractive_index=1.5168,
            thickness=5.0,
            diameter=25.0,
        )
    )
    # The tree is the authority for the alignment; this updates it and the
    # flat records together.
    system.set_element_alignment(0, decenter_y=decenter_y, decenter_z=decenter_z, tilt_z=tilt_z)
    return system


def _signature(system):
    return [
        (
            path.reflection_1_index,
            path.reflection_2_index,
            round(path.intensity, 8),
            [
                (round(point.x, 4), round(point.y, 4), round(point.z, 4))
                for ray in path.rays
                for point in ray.path
            ],
        )
        for path in GhostAnalyzer(system).trace_ghosts(num_rays=3)
    ]


class TestGhostAlignment(unittest.TestCase):
    def test_decentring_the_element_moves_the_ghost_paths(self):
        centered = _signature(_system())
        decentered = _signature(_system(decenter_y=10.0))

        self.assertTrue(centered)
        self.assertNotEqual(centered, decentered)

    def test_tilting_the_element_moves_the_ghost_paths(self):
        centered = _signature(_system())
        tilted = _signature(_system(tilt_z=2.0))

        self.assertTrue(centered)
        self.assertNotEqual(centered, tilted)

    def test_a_decentred_element_reflects_at_its_own_height(self):
        """The axial ray leaves the ghost path away from the axis."""
        centered = GhostAnalyzer(_system()).trace_ghosts(num_rays=3)[0]
        decentered = GhostAnalyzer(_system(decenter_y=10.0)).trace_ghosts(num_rays=3)[0]

        # rays[1] is the central (on-axis source) ray.
        self.assertAlmostEqual(centered.rays[1].path[-1].y, 0.0, places=6)
        self.assertGreater(abs(decentered.rays[1].path[-1].y), 1.0)

    def test_a_centered_system_is_still_traced_symmetrically(self):
        """The fix must not perturb the on-axis result."""
        path = GhostAnalyzer(_system()).trace_ghosts(num_rays=3)[0]
        heights = [ray.path[-1].y for ray in path.rays]

        self.assertAlmostEqual(heights[0], -heights[-1], places=6)
        self.assertAlmostEqual(heights[1], 0.0, places=6)


if __name__ == "__main__":
    unittest.main()
