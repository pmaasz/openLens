import unittest
import math
import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.optical_system import OpticalSystem
from src.lens import Lens
from src.optimizer import LensOptimizer, OptimizationVariable, OptimizationTarget


class TestAdvancedOptimizer(unittest.TestCase):
    def setUp(self):
        # Create a simple singlet
        self.lens = Lens(
            radius_of_curvature_1=100.0,
            radius_of_curvature_2=-100.0,
            thickness=5.0,
            diameter=25.0,
            refractive_index=1.5168,  # BK7 approx
        )
        self.system = OpticalSystem()
        self.system.add_lens(self.lens)

        # Variables: R1, R2
        self.variables = [
            OptimizationVariable(
                name="R1",
                element_index=0,
                parameter="radius_of_curvature_1",
                current_value=100.0,
                min_value=50.0,
                max_value=200.0,
            ),
            OptimizationVariable(
                name="R2",
                element_index=0,
                parameter="radius_of_curvature_2",
                current_value=-100.0,
                min_value=-200.0,
                max_value=-50.0,
            ),
        ]

    def test_optimize_spot_size(self):
        """Test optimizing for RMS spot size"""
        targets = [
            OptimizationTarget("rms_spot_radius", 0.0, weight=100.0, target_type="minimize"),
            OptimizationTarget("focal_length", 96.8, weight=1.0, target_type="target"),
        ]

        optimizer = LensOptimizer(self.system, self.variables, targets)
        result = optimizer.optimize_simplex(max_iterations=20)

        self.assertTrue(result.success)
        self.assertLessEqual(result.final_merit, result.initial_merit)

        new_r1 = result.optimized_system.elements[0].lens.radius_of_curvature_1
        self.assertNotAlmostEqual(new_r1, 100.0, delta=0.1)

    def test_edge_thickness_penalty(self):
        """Test that invalid geometries (negative edge thickness) are penalized"""
        # Create an impossible lens: R=26, D=50. Sag approx 7.1mm per side. Total sag 14.2mm.
        # If center thickness is 5mm, edge thickness = 5 - 14.2 = -9.2mm (Impossible!)

        impossible_lens = Lens(
            radius_of_curvature_1=26.0,
            radius_of_curvature_2=-26.0,
            thickness=5.0,
            diameter=50.0,
            refractive_index=1.5,
        )
        sys_bad = OpticalSystem("Bad System")
        sys_bad.add_lens(impossible_lens)

        vars = [
            OptimizationVariable(
                name="R1",
                element_index=0,
                parameter="radius_of_curvature_1",
                current_value=26.0,
                min_value=10.0,
                max_value=100.0,
            )
        ]
        optimizer = LensOptimizer(sys_bad, vars, [])

        merit = optimizer.merit_function.evaluate(sys_bad)
        self.assertGreater(merit, 1000.0)

    def test_vertex_collapse_penalty(self):
        """Designs with crossed surfaces (edge <= 0) get a hard penalty."""
        crossed_lens = Lens(
            radius_of_curvature_1=86.63,
            radius_of_curvature_2=-109.97,
            thickness=5.0,
            diameter=50.0,
            refractive_index=1.5,
        )
        sys_crossed = OpticalSystem("Crossed System")
        sys_crossed.add_lens(crossed_lens)

        optimizer = LensOptimizer(sys_crossed, [], [])
        merit = optimizer.merit_function.evaluate(sys_crossed)
        self.assertGreaterEqual(merit, 1e8)

    def test_thin_center_penalty(self):
        """Designs with non-positive center thickness get a hard penalty."""
        flat_lens = Lens(
            radius_of_curvature_1=100.0,
            radius_of_curvature_2=-100.0,
            thickness=-2.0,
            diameter=25.0,
            refractive_index=1.5,
        )
        sys_flat = OpticalSystem("Flat System")
        sys_flat.add_lens(flat_lens)

        optimizer = LensOptimizer(sys_flat, [], [])
        merit = optimizer.merit_function.evaluate(sys_flat)
        self.assertGreaterEqual(merit, 1e8)

    def test_radius_variable_clears_parabolic_flag(self):
        """Radius variables take effect on parabolic surfaces (no silent no-op)."""
        lens = Lens(
            radius_of_curvature_1=100.0,
            radius_of_curvature_2=-100.0,
            thickness=5.0,
            diameter=25.0,
            refractive_index=1.5,
            is_parabolic_1=True,
            parabolic_sag_1=3.0,
        )
        system = OpticalSystem("Parabolic System")
        system.add_lens(lens)
        optimizer = LensOptimizer(system, [], [])
        f_before = system.elements[0].lens.calculate_focal_length()

        optimizer._apply_single_variable(system, 0, "radius_of_curvature_1", 60.0)

        applied = system.elements[0].lens
        self.assertFalse(applied.is_parabolic_1)
        self.assertEqual(applied.radius_of_curvature_1, 60.0)
        self.assertNotAlmostEqual(applied.calculate_focal_length(), f_before)

    def test_sag_variable_latches_parabolic_flag(self):
        """Sag variables switch the surface to parabolic."""
        optimizer = LensOptimizer(self.system, [], [])
        optimizer._apply_single_variable(self.system, 0, "parabolic_sag_1", 2.5)

        applied = self.system.elements[0].lens
        self.assertTrue(applied.is_parabolic_1)
        self.assertEqual(applied.parabolic_sag_1, 2.5)

    def test_coma_target(self):
        """Test that coma target can be evaluated"""
        targets = [
            OptimizationTarget(name="coma", target_value=0.0, weight=1.0, target_type="minimize")
        ]
        optimizer = LensOptimizer(self.system, self.variables, targets)
        merit = optimizer._evaluate_design([100.0, -100.0])
        self.assertIsInstance(merit, float)
        self.assertGreaterEqual(merit, 0.0)

    def test_astigmatism_target(self):
        """Test that astigmatism target can be evaluated"""
        targets = [
            OptimizationTarget(
                name="astigmatism", target_value=0.0, weight=1.0, target_type="minimize"
            )
        ]
        optimizer = LensOptimizer(self.system, self.variables, targets)
        merit = optimizer._evaluate_design([100.0, -100.0])
        self.assertIsInstance(merit, float)
        self.assertGreaterEqual(merit, 0.0)


if __name__ == "__main__":
    unittest.main()
