"""Tests for tolerance grades, new operands, and compensators (item 6)."""

import math
import unittest

from src.lens import Lens
from src.optical_system import OpticalSystem
from src.tolerancing import (
    TOLERANCE_GRADES,
    MonteCarloAnalyzer,
    ToleranceOperand,
    ToleranceType,
    _apply_value,
    tolerances_for_system,
)


def _two_element_system():
    system = OpticalSystem(name="Tol System")
    system.add_lens(
        Lens(
            name="A",
            radius_of_curvature_1=100.0,
            radius_of_curvature_2=-100.0,
            thickness=5.0,
            diameter=25.0,
            material="BK7",
        )
    )
    system.add_lens(
        Lens(
            name="B",
            radius_of_curvature_1=80.0,
            radius_of_curvature_2=-80.0,
            thickness=4.0,
            diameter=25.0,
            material="BK7",
        ),
        air_gap_before=10.0,
    )
    return system


class TestToleranceGrades(unittest.TestCase):
    def test_grades_defined(self):
        """All three shop grades should exist with sane values."""
        for grade in ("Commercial", "Precision", "High Precision"):
            self.assertIn(grade, TOLERANCE_GRADES)
            g = TOLERANCE_GRADES[grade]
            self.assertGreater(g["radius"], 0)
            self.assertGreater(g["irregularity_fringes"], 0)
        self.assertGreater(
            TOLERANCE_GRADES["Commercial"]["radius"],
            TOLERANCE_GRADES["High Precision"]["radius"],
        )

    def test_builder_counts(self):
        """Two elements + one gap should yield 12*2 + 1 operands."""
        operands = tolerances_for_system(_two_element_system(), "Precision")
        self.assertEqual(len(operands), 25)
        types = {op.param_type for op in operands}
        for expected in (
            ToleranceType.RADIUS_1,
            ToleranceType.THICKNESS,
            ToleranceType.REFRACTIVE_INDEX,
            ToleranceType.DECENTER_Y,
            ToleranceType.TILT_X,
            ToleranceType.AIR_GAP,
            ToleranceType.IRREGULARITY,
            ToleranceType.WEDGE,
        ):
            self.assertIn(expected, types)

    def test_builder_values_match_grade(self):
        """Operand limits should equal the grade table entries."""
        operands = tolerances_for_system(_two_element_system(), "Commercial")
        radii = [op for op in operands if op.param_type == ToleranceType.RADIUS_1]
        self.assertEqual(radii[0].max_val, 0.5)
        tilts = [op for op in operands if op.param_type == ToleranceType.TILT_X]
        self.assertAlmostEqual(tilts[0].max_val, 3.0 / 60.0)

    def test_unknown_grade_raises(self):
        """Unknown grades should raise."""
        with self.assertRaises(ValueError):
            tolerances_for_system(_two_element_system(), "Kitchen Table")


class TestNewOperandApplication(unittest.TestCase):
    def test_tilt_y(self):
        """TILT_Y should rotate about y."""
        system = _two_element_system()
        self.assertTrue(_apply_value(system, ToleranceType.TILT_Y, 0, 0.5))
        node = system.root.get_flat_list()[0][0]
        self.assertEqual(node.rotation.y, 0.5)

    def test_decenter_z(self):
        """DECENTER_Z should offset laterally."""
        system = _two_element_system()
        self.assertTrue(_apply_value(system, ToleranceType.DECENTER_Z, 1, 0.1))
        node = system.root.get_flat_list()[1][0]
        self.assertEqual(node.position.z, 0.1)

    def test_decenter_x_moves_gap(self):
        """Axial despace should land on the gap before the element."""
        system = _two_element_system()
        self.assertTrue(_apply_value(system, ToleranceType.DECENTER_X, 1, 0.05))
        self.assertAlmostEqual(system.air_gaps[0].thickness, 10.05)
        # Element 0 is the datum: nothing to despace against.
        self.assertFalse(_apply_value(system, ToleranceType.DECENTER_X, 0, 0.05))

    def test_air_gap(self):
        """AIR_GAP should thicken the gap after the element."""
        system = _two_element_system()
        self.assertTrue(_apply_value(system, ToleranceType.AIR_GAP, 0, 0.1))
        self.assertAlmostEqual(system.air_gaps[0].thickness, 10.1)
        self.assertFalse(_apply_value(system, ToleranceType.AIR_GAP, 5, 0.1))

    def test_wedge_is_half_tilt(self):
        """Wedge (arcmin) should tilt by half the angle in degrees."""
        system = _two_element_system()
        self.assertTrue(_apply_value(system, ToleranceType.WEDGE, 0, 6.0))
        node = system.root.get_flat_list()[0][0]
        self.assertAlmostEqual(node.rotation.x, 0.05)

    def test_irregularity_matches_fringe_sag(self):
        """0.5 fringes should add half-fringe sag at the semi-aperture."""
        system = _two_element_system()
        lens = system.elements[0].lens
        r0, h = 100.0, 12.5
        sag0 = abs(r0) - math.sqrt(r0 * r0 - h * h)
        self.assertTrue(
            _apply_value(system, ToleranceType.IRREGULARITY, 0, 0.5, surface=1)
        )
        r1 = lens.radius_of_curvature_1
        sag1 = abs(r1) - math.sqrt(r1 * r1 - h * h)
        self.assertAlmostEqual(sag1 - sag0, 0.5 * 632.8e-6 / 2, places=6)

    def test_irregularity_flat_skipped(self):
        """Flat surfaces cannot take a power-equivalent fringe bend."""
        system = OpticalSystem(name="Flat")
        system.add_lens(
            Lens(
                name="P",
                radius_of_curvature_1=100.0,
                radius_of_curvature_2=float("inf"),
                thickness=5.0,
                diameter=25.0,
                material="BK7",
            )
        )
        self.assertFalse(
            _apply_value(system, ToleranceType.IRREGULARITY, 0, 0.5, surface=2)
        )


class TestCompensators(unittest.TestCase):
    def test_focus_compensator_recovers_defocus(self):
        """Refocus should beat the uncompensated trial mean."""
        from src.analysis.spot_diagram import SpotDiagram

        def build():
            system = OpticalSystem(name="Focus")
            system.add_lens(
                Lens(
                    name="A",
                    radius_of_curvature_1=51.5,
                    radius_of_curvature_2=-51.5,
                    thickness=5.0,
                    diameter=25.4,
                    material="BK7",
                )
            )
            return system

        perturbed = build()
        perturbed.elements[0].lens.thickness = 7.0
        perturbed._update_positions()
        plain_rms = SpotDiagram(perturbed).trace_spot()["rms_radius"]

        analyzer = MonteCarloAnalyzer(
            perturbed,
            [],
            compensators=[ToleranceOperand(0, ToleranceType.FOCUS, -10.0, 10.0)],
        )
        values = analyzer._optimize_compensators()
        comp_rms = SpotDiagram(perturbed).trace_spot(
            focus_shift_mm=values["focus_shift_mm"]
        )["rms_radius"]
        self.assertLess(comp_rms, plain_rms)

    def test_run_records_compensator_values(self):
        """Trials should record their compensator settings."""
        system = _two_element_system()
        analyzer = MonteCarloAnalyzer(
            system,
            [ToleranceOperand(0, ToleranceType.THICKNESS, -0.1, 0.1)],
            seed=7,
            compensators=[ToleranceOperand(0, ToleranceType.FOCUS, -5.0, 5.0)],
        )
        stats = analyzer.run(num_trials=3, criterion_limit=5.0)
        self.assertEqual(stats["trials"], 3)
        for result in analyzer.results:
            self.assertIn("compensators", result)
            self.assertIn("focus_shift_mm", result["compensators"])


if __name__ == "__main__":
    unittest.main()
