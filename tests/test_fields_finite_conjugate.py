import math
import unittest

from openlens.aberrations import AberrationsCalculator
from openlens.analysis.spot_diagram import SpotDiagram
from openlens.fields import FieldPoint, normalize_fields
from openlens.lens import Lens
from openlens.optical_system import OpticalSystem, as_system
from openlens.optimizer import MeritFunction, OptimizationTarget
from openlens.tolerancing import MonteCarloAnalyzer

from openlens.constants import WAVELENGTH_GREEN

try:
    import numpy as np

    NUMPY_AVAILABLE = True
except ImportError:  # pragma: no cover - numpy is a recommended dependency
    NUMPY_AVAILABLE = False


def _singlet() -> OpticalSystem:
    """A fast, well-behaved positive singlet as an analysis system."""
    lens = Lens(
        radius_of_curvature_1=100.0,
        radius_of_curvature_2=-100.0,
        thickness=5.0,
        diameter=20.0,
        refractive_index=1.5168,
    )
    return as_system(lens)


class TestFieldPoint(unittest.TestCase):
    def test_default_field_is_on_axis(self):
        field = FieldPoint()
        self.assertEqual(field.angle_deg, 0.0)
        self.assertEqual(field.weight, 1.0)
        self.assertIsNone(field.height_mm)

    def test_zero_weight_raises(self):
        with self.assertRaises(ValueError):
            FieldPoint(5.0, weight=0.0)

    def test_angle_and_height_together_raise(self):
        with self.assertRaises(ValueError):
            FieldPoint(5.0, height_mm=1.0)

    def test_height_needs_a_finite_object_distance(self):
        field = FieldPoint(height_mm=5.0)
        with self.assertRaises(ValueError):
            field.resolve_angle_deg(None)

    def test_height_converts_to_the_matching_angle(self):
        field = FieldPoint(height_mm=10.0)
        angle = field.resolve_angle_deg(200.0)
        self.assertAlmostEqual(angle, -math.degrees(math.atan2(10.0, 200.0)), places=9)

    def test_normalize_accepts_dicts_and_bare_angles(self):
        fields = normalize_fields([{"angle_deg": 5.0, "weight": 2.0}, 10.0])
        self.assertEqual([f.angle_deg for f in fields], [5.0, 10.0])
        self.assertEqual(fields[0].weight, 2.0)

    def test_to_dict_round_trip(self):
        field = FieldPoint(4.0, weight=0.5)
        self.assertEqual(FieldPoint.from_dict(field.to_dict()), field)


class TestModelPersistence(unittest.TestCase):
    def test_system_round_trip_keeps_fields_and_conjugate(self):
        system = _singlet()
        system.fields = [FieldPoint(0.0), FieldPoint(5.0, weight=3.0)]
        system.object_distance_mm = 250.0

        restored = OpticalSystem.from_dict(system.to_dict())

        self.assertEqual([f.angle_deg for f in restored.fields], [0.0, 5.0])
        self.assertEqual(restored.fields[1].weight, 3.0)
        self.assertEqual(restored.object_distance_mm, 250.0)

    def test_lens_round_trip_keeps_fields_and_conjugate(self):
        lens = Lens(fields=[FieldPoint(2.0, weight=2.0)], object_distance_mm=150.0)
        restored = Lens.from_dict(lens.to_dict())
        self.assertEqual([f.angle_deg for f in restored.fields], [2.0])
        self.assertEqual(restored.fields[0].weight, 2.0)
        self.assertEqual(restored.object_distance_mm, 150.0)

    def test_wrapping_a_lens_carries_the_analysis_settings(self):
        lens = Lens(fields=[FieldPoint(3.0)], object_distance_mm=120.0)
        system = as_system(lens)
        self.assertEqual([f.angle_deg for f in system.fields], [3.0])
        self.assertEqual(system.object_distance_mm, 120.0)

    def test_default_is_still_collimated_and_single_field(self):
        system = _singlet()
        self.assertEqual(system.fields, [])
        self.assertIsNone(system.object_distance_mm)


class TestFiniteConjugateChangesResults(unittest.TestCase):
    def setUp(self):
        self.system = _singlet()

    def test_spot_plane_and_rms_change_at_a_finite_distance(self):
        spot = SpotDiagram(self.system)
        infinity = spot.trace_spot()
        finite = spot.trace_spot(object_distance_mm=250.0)

        self.assertGreater(finite["image_plane_x"], infinity["image_plane_x"])
        self.assertIsNotNone(finite["rms_radius"])
        self.assertNotAlmostEqual(finite["rms_radius"], infinity["rms_radius"], places=4)

    def test_aberration_values_change_not_just_the_label(self):
        calc = AberrationsCalculator(self.system)
        infinity = calc.calculate_all_aberrations()
        finite = calc.calculate_all_aberrations(object_distance_mm=250.0)

        self.assertTrue(finite["valid"])
        self.assertNotAlmostEqual(finite["spherical"], infinity["spherical"], places=3)
        self.assertNotAlmostEqual(finite["spot_rms"], infinity["spot_rms"], places=1)

    def test_ray_fan_is_traced_from_the_object_point(self):
        calc = AberrationsCalculator(self.system)
        infinity = calc.calculate_ray_fan(5.0)
        finite = calc.calculate_ray_fan(5.0, object_distance_mm=250.0)

        self.assertTrue(infinity["ray_errors_mm"])
        self.assertTrue(finite["ray_errors_mm"])
        self.assertNotAlmostEqual(
            finite["ray_errors_mm"][-1], infinity["ray_errors_mm"][-1], places=4
        )

    def test_model_object_distance_reaches_the_calculator(self):
        calc = AberrationsCalculator(self.system)
        infinity = calc.calculate_all_aberrations()
        self.system.object_distance_mm = 250.0
        from_model = calc.calculate_all_aberrations()
        explicit = calc.calculate_all_aberrations(object_distance_mm=250.0)
        self.assertAlmostEqual(from_model["spherical"], explicit["spherical"], places=9)
        self.assertNotAlmostEqual(from_model["spherical"], infinity["spherical"], places=3)

    @unittest.skipUnless(NUMPY_AVAILABLE, "numpy is needed for the wavefront")
    def test_wavefront_uses_the_finite_conjugate(self):
        from openlens.analysis.diffraction_psf import WavefrontSensor

        sensor = WavefrontSensor(self.system)
        infinity = sensor.get_pupil_wavefront(grid_size=8)
        self.system.object_distance_mm = 250.0
        finite = sensor.get_pupil_wavefront(grid_size=8)

        self.assertTrue(np.any(np.isfinite(finite.W)))
        self.assertFalse(np.allclose(infinity.W, finite.W, equal_nan=True))


class TestFieldAggregation(unittest.TestCase):
    def test_two_fields_have_separate_metrics_and_a_weighted_aggregate(self):
        system = _singlet()
        system.fields = [FieldPoint(0.0, weight=1.0), FieldPoint(5.0, weight=3.0)]
        calc = AberrationsCalculator(system)

        result = calc.calculate_fields(wavelength_nm=WAVELENGTH_GREEN)

        self.assertEqual(len(result["fields"]), 2)
        self.assertEqual([entry["angle_deg"] for entry in result["fields"]], [0.0, 5.0])
        on_axis, off_axis = result["fields"]
        self.assertAlmostEqual(on_axis["metrics"]["coma"], 0.0, places=9)
        self.assertGreater(abs(off_axis["metrics"]["coma"]), 0.0)

        expected = (
            1.0 * abs(on_axis["metrics"]["coma"]) + 3.0 * abs(off_axis["metrics"]["coma"])
        ) / 4
        self.assertAlmostEqual(result["aggregate"]["coma"], expected, places=9)

    def test_a_height_field_is_evaluated_at_its_angle(self):
        system = _singlet()
        system.object_distance_mm = 250.0
        system.fields = [FieldPoint(height_mm=10.0, weight=1.0)]
        result = AberrationsCalculator(system).calculate_fields()
        expected = -math.degrees(math.atan2(10.0, 250.0))
        self.assertAlmostEqual(result["fields"][0]["angle_deg"], expected, places=9)
        self.assertEqual(result["fields"][0]["height_mm"], 10.0)

    def test_empty_fields_fall_back_to_one_on_axis_field(self):
        result = AberrationsCalculator(_singlet()).calculate_fields()
        self.assertEqual(len(result["fields"]), 1)
        self.assertEqual(result["fields"][0]["angle_deg"], 0.0)


class TestOptimizerAndTolerancingUseTheFieldList(unittest.TestCase):
    def test_coma_merit_is_weighted_over_the_field_list(self):
        system = _singlet()
        system.fields = [FieldPoint(0.0, weight=1.0), FieldPoint(5.0, weight=3.0)]
        merit_function = MeritFunction(system, [])
        target = OptimizationTarget("coma", 0.0, weight=1.0, target_type="minimize")

        merit = merit_function._eval_coma(system, target)

        calc = AberrationsCalculator(system)
        on_axis = calc.calculate_all_aberrations(field_angle_deg=0.0)["coma"]
        off_axis = calc.calculate_all_aberrations(field_angle_deg=5.0)["coma"]
        expected = (1.0 * abs(on_axis) + 3.0 * abs(off_axis)) / 4.0
        self.assertAlmostEqual(merit, expected, places=9)

    def test_optimizer_honours_the_model_conjugate(self):
        system = _singlet()
        system.fields = [FieldPoint(0.0)]
        merit_function = MeritFunction(system, [])
        target = OptimizationTarget("rms_spot_radius", 0.0, weight=1.0, target_type="minimize")
        infinity = merit_function._eval_rms_spot(system, target)
        system.object_distance_mm = 250.0
        finite = merit_function._eval_rms_spot(system, target)
        self.assertNotAlmostEqual(infinity, finite, places=5)

    def test_tolerancing_spot_is_weighted_over_the_field_list(self):
        system = _singlet()
        system.fields = [FieldPoint(0.0, weight=1.0), FieldPoint(5.0, weight=3.0)]
        analyzer = MonteCarloAnalyzer(system, [])
        weighted = analyzer._spot_rms()

        spot = SpotDiagram(system)
        on_axis = spot.trace_spot(field_angle_y_deg=0.0)["rms_radius"]
        off_axis = spot.trace_spot(field_angle_y_deg=5.0)["rms_radius"]
        self.assertIsNotNone(on_axis)
        self.assertIsNotNone(off_axis)
        expected = math.sqrt((1.0 * on_axis**2 + 3.0 * off_axis**2) / 4.0)
        self.assertAlmostEqual(weighted, expected, places=9)


if __name__ == "__main__":
    unittest.main()
