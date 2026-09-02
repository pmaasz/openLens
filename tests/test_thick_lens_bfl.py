#!/usr/bin/env python3
"""
Thick-lens paraxial BFL/EFL for a two-element system.

Independent hand-derived reference (surface-by-surface ABCD, reduced
thickness d/n, matching src/optical_system._calculate_system_matrix):

  L1: R1=100, R2=-100, t=10, n=1.5
  gap = 5
  L2: R1=50, R2=-50, t=5, n=1.5

  M1 (L1): [[0.9666667, 6.6666667], [-0.00983333, 0.9666667]]
  +gap5 :  [[0.9175000, 11.5000000], [-0.00983333, 0.9666667]]
  M2 (L2): [[0.8541389, 14.3388889], [-0.02754970, 0.7082778]]

  BFL = -A/C = 31.0035 mm
  EFL = -1/C = 36.2994 mm
"""

import unittest

from src.lens import Lens
from src.optical_system import OpticalSystem


class TestDoubletBFL(unittest.TestCase):
    """Locks the thick-lens matrix BFL for a known doublet"""

    def setUp(self):
        self.system = OpticalSystem(name="doublet")
        self.system.add_lens(
            Lens(
                radius_of_curvature_1=100.0,
                radius_of_curvature_2=-100.0,
                thickness=10.0,
                diameter=25.0,
                refractive_index=1.5,
            ),
            air_gap_before=0.0,
        )
        self.system.add_lens(
            Lens(
                radius_of_curvature_1=50.0,
                radius_of_curvature_2=-50.0,
                thickness=5.0,
                diameter=25.0,
                refractive_index=1.5,
            ),
            air_gap_before=5.0,
        )

    def test_back_focal_length_known_value(self):
        """BFL of the doublet matches the hand-computed -A/C"""
        bfl = self.system.calculate_back_focal_length()
        self.assertIsNotNone(bfl)
        self.assertAlmostEqual(bfl, 31.0035, delta=0.01)

    def test_effective_focal_length_known_value(self):
        """Matrix EFL (-1/C) matches the hand-computed power"""
        A, B, C, D = self.system._calculate_system_matrix()
        self.assertAlmostEqual(-1.0 / C, 36.2980, delta=0.01)

    def test_system_focal_length_is_thin_lens_estimate_for_doublets(self):
        """Documented behaviour: get_system_focal_length() uses the thin-lens
        combination 1/f = 1/f1 + 1/f2 - d/(f1*f2) for two elements, so it
        deviates from the exact matrix EFL for thick lenses."""
        f = self.system.get_system_focal_length()
        self.assertAlmostEqual(f, 35.0470, delta=0.01)
        A, B, C, D = self.system._calculate_system_matrix()
        self.assertNotAlmostEqual(f, -1.0 / C, places=2)

    def test_bfl_changes_with_air_gap(self):
        """Increasing the air gap moves the focus (matrix is gap-sensitive)"""
        bfl_before = self.system.calculate_back_focal_length()
        self.system.air_gaps[0].thickness = 15.0
        self.system._update_positions()
        bfl_after = self.system.calculate_back_focal_length()
        self.assertNotAlmostEqual(bfl_before, bfl_after, places=2)


if __name__ == "__main__":
    unittest.main()
