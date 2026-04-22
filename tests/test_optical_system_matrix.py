"""Thick-lens ABCD matrix regression tests for OpticalSystem.

These lock in the surface-by-surface thick-lens implementation of
``OpticalSystem._calculate_system_matrix`` (promoted from previously
unreachable code) against the analytic lensmaker's equation implemented
on ``Lens`` itself.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.lens import Lens
from src.optical_system import (
    OpticalSystem,
    create_doublet,
    AchromaticDoubletDesigner,
)


class TestThickLensMatrix(unittest.TestCase):
    """The ABCD matrix must agree with Lens.* for the single-lens case."""

    def _single_lens_system(self, **kwargs):
        lens = Lens(**kwargs)
        system = OpticalSystem(name='single')
        system.add_lens(lens)
        return system, lens

    def test_biconvex_focal_length_matches_lensmaker(self):
        system, lens = self._single_lens_system(
            radius_of_curvature_1=100.0,
            radius_of_curvature_2=-100.0,
            thickness=5.0,
            diameter=25.0,
            refractive_index=1.5168,
        )
        self.assertAlmostEqual(
            system.get_system_focal_length(),
            lens.calculate_focal_length(),
            places=6,
        )

    def test_biconvex_bfl_matches_lens_bfl(self):
        system, lens = self._single_lens_system(
            radius_of_curvature_1=100.0,
            radius_of_curvature_2=-100.0,
            thickness=5.0,
            diameter=25.0,
            refractive_index=1.5168,
        )
        self.assertAlmostEqual(
            system.calculate_back_focal_length(),
            lens.calculate_back_focal_length(),
            places=6,
        )

    def test_matrix_is_unimodular(self):
        """For a system surrounded by the same medium (air) det(M) must be 1."""
        system, _ = self._single_lens_system(
            radius_of_curvature_1=50.0,
            radius_of_curvature_2=-75.0,
            thickness=4.0,
            diameter=20.0,
            refractive_index=1.5168,
        )
        A, B, C, D = system._calculate_system_matrix()
        self.assertAlmostEqual(A * D - B * C, 1.0, places=9)


class TestDoublet(unittest.TestCase):
    """Doublet results that would have regressed silently before the fix."""

    def test_cemented_doublet_has_positive_bfl(self):
        system = create_doublet(focal_length=100.0, diameter=25.0)
        bfl = system.calculate_back_focal_length()
        self.assertIsNotNone(bfl)
        self.assertGreater(bfl, 0.0,
                           'Back focal length of a positive doublet must be > 0; '
                           'got {!r}'.format(bfl))

    def test_cemented_doublet_focal_length_near_target(self):
        target = 100.0
        system = AchromaticDoubletDesigner.design_cemented_doublet(
            focal_length=target, diameter=25.0,
        )
        efl = system.get_system_focal_length()
        self.assertIsNotNone(efl)
        # Equiconvex-crown approximation is imperfect; 10% is plenty.
        self.assertLess(abs(efl - target) / target, 0.10)

    def test_roundtrip_preserves_focal_length(self):
        system = create_doublet(focal_length=100.0, diameter=25.0)
        restored = OpticalSystem.from_dict(system.to_dict())
        self.assertAlmostEqual(
            system.get_system_focal_length(),
            restored.get_system_focal_length(),
            places=6,
        )


if __name__ == '__main__':
    unittest.main()
