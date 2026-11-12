#!/usr/bin/env python3
"""Inverse tolerance budgeting must honour its criterion argument.

``InverseSensitivityAnalyzer.calculate_sensitivities(criterion=...)`` accepted
a criterion and never read it: every caller - including ``optimize_limits`` -
received RMS spot radius sensitivities regardless of what was asked for,
while ``MonteCarloAnalyzer`` rejects an unimplemented metric.
"""

import unittest
from unittest import mock

from openlens.lens import Lens
from openlens.optical_system import OpticalSystem
from openlens.tolerancing import (
    InverseSensitivityAnalyzer,
    MonteCarloAnalyzer,
    ToleranceOperand,
    ToleranceType,
)


def _system():
    system = OpticalSystem("Test System")
    system.add_lens(
        Lens(
            "L1",
            radius_of_curvature_1=50.0,
            radius_of_curvature_2=-50.0,
            thickness=5.0,
            diameter=25.0,
            material="BK7",
            wavelength_nm=587.6,
        )
    )
    return system


def _operands():
    return [ToleranceOperand(0, ToleranceType.RADIUS_1, -1.0, 1.0)]


class TestInverseSensitivityCriterion(unittest.TestCase):
    def setUp(self):
        self.system = _system()
        self.analyzer = InverseSensitivityAnalyzer(self.system, _operands())

    def test_the_supported_criterion_is_measured(self):
        rows = self.analyzer.calculate_sensitivities("rms_spot_radius")

        self.assertEqual(len(rows), 1)
        self.assertIn("sensitivity", rows[0])

    def test_an_unsupported_criterion_raises(self):
        with self.assertRaises(ValueError) as caught:
            self.analyzer.calculate_sensitivities("mtf")

        self.assertIn("rms_spot_radius", str(caught.exception))

    def test_an_unsupported_criterion_does_not_trace(self):
        with mock.patch("openlens.tolerancing.SpotDiagram") as spot:
            with self.assertRaises(ValueError):
                self.analyzer.calculate_sensitivities("wavefront_rms")

        spot.assert_not_called()

    def test_the_supported_set_is_the_monte_carlo_set(self):
        self.assertEqual(
            InverseSensitivityAnalyzer.SUPPORTED_CRITERIA,
            MonteCarloAnalyzer.SUPPORTED_CRITERIA,
        )

    def test_a_rejected_criterion_leaves_the_design_alone(self):
        lens = self.system.elements[0].lens
        before = (lens.radius_of_curvature_1, lens.thickness)

        with self.assertRaises(ValueError):
            self.analyzer.calculate_sensitivities("mtf")

        self.assertEqual((lens.radius_of_curvature_1, lens.thickness), before)


if __name__ == "__main__":
    unittest.main()
