#!/usr/bin/env python3
"""
Comprehensive functional tests for lens comparator and coating designer
"""

import os
import unittest
import tempfile

from src.lens import Lens
from src.lens_comparator import LensComparator, ComparisonResult
from src.coating_designer import CoatingDesigner, CoatingLayer


class TestLensComparator(unittest.TestCase):
    """Test lens comparison functionality"""

    def setUp(self):
        """Create test lenses"""
        self.lens1 = Lens(
            name="Test Lens 1",
            radius_of_curvature_1=50,
            radius_of_curvature_2=-50,
            thickness=5,
            diameter=25.4,
        )

        self.lens2 = Lens(
            name="Test Lens 2",
            radius_of_curvature_1=100,
            radius_of_curvature_2=-100,
            thickness=4,
            diameter=25.4,
        )

        self.lens3 = Lens(
            name="Test Lens 3",
            radius_of_curvature_1=75,
            radius_of_curvature_2=-75,
            thickness=6,
            diameter=30.0,
        )

    def test_create_comparator(self):
        """Test creating comparator"""
        comp = LensComparator()
        self.assertIsNotNone(comp)
        self.assertEqual(len(comp.lenses), 0)

    def test_add_lens(self):
        """Test adding lenses"""
        comp = LensComparator()
        comp.add_lens(self.lens1)
        comp.add_lens(self.lens2)

        self.assertEqual(len(comp.lenses), 2)

    def test_clear(self):
        """Test clearing lenses"""
        comp = LensComparator()
        comp.add_lens(self.lens1)
        comp.add_lens(self.lens2)
        comp.clear()

        self.assertEqual(len(comp.lenses), 0)
        self.assertEqual(len(comp.results), 0)

    def test_compare_lenses(self):
        """Test comparing lenses"""
        comp = LensComparator()
        comp.add_lens(self.lens1)
        comp.add_lens(self.lens2)

        results = comp.compare()

        self.assertEqual(len(results), 2)
        self.assertIsInstance(results[0], ComparisonResult)
        self.assertEqual(results[0].name, "Test Lens 1")
        self.assertEqual(results[1].name, "Test Lens 2")

    def test_comparison_result_fields(self):
        """Test that comparison results have all required fields"""
        comp = LensComparator()
        comp.add_lens(self.lens1)
        results = comp.compare()

        result = results[0]
        self.assertIsNotNone(result.name)
        self.assertIsNotNone(result.focal_length)
        self.assertIsNotNone(result.f_number)
        self.assertIsNotNone(result.numerical_aperture)
        self.assertIsNotNone(result.diameter)
        self.assertIsNotNone(result.thickness)
        self.assertIsNotNone(result.material)

    def test_parameter_differences(self):
        """Test calculating parameter differences"""
        comp = LensComparator()
        comp.add_lens(self.lens1)
        comp.add_lens(self.lens2)
        comp.compare()

        diffs = comp.get_parameter_differences()

        self.assertIsInstance(diffs, dict)
        self.assertIn("focal_length", diffs)
        self.assertIn("min", diffs["focal_length"])
        self.assertIn("max", diffs["focal_length"])
        self.assertIn("range", diffs["focal_length"])

    def test_rank_by_parameter(self):
        """Test ranking lenses by parameter"""
        comp = LensComparator()
        comp.add_lens(self.lens1)
        comp.add_lens(self.lens2)
        comp.add_lens(self.lens3)
        comp.compare()

        # Rank by focal length (ascending)
        ranked = comp.rank_by_parameter("focal_length", ascending=True)

        self.assertEqual(len(ranked), 3)
        # Check they're in order
        for i in range(len(ranked) - 1):
            self.assertLessEqual(ranked[i].focal_length, ranked[i + 1].focal_length)

    def test_rank_by_diameter_descending(self):
        """Test ranking by diameter descending"""
        comp = LensComparator()
        comp.add_lens(self.lens1)
        comp.add_lens(self.lens3)
        comp.compare()

        ranked = comp.rank_by_parameter("diameter", ascending=False)

        self.assertEqual(ranked[0].diameter, 30.0)
        self.assertEqual(ranked[1].diameter, 25.4)

    def test_get_best_overall(self):
        """Test getting best overall lens"""
        comp = LensComparator()
        comp.add_lens(self.lens1)
        comp.add_lens(self.lens2)
        comp.compare()

        best = comp.get_best_overall()

        self.assertIsNotNone(best)
        self.assertIsInstance(best, ComparisonResult)

    def test_comparison_table_generation(self):
        """Test generating comparison table"""
        comp = LensComparator()
        comp.add_lens(self.lens1)
        comp.add_lens(self.lens2)
        comp.compare()

        table = comp.generate_comparison_table()

        self.assertIsInstance(table, str)
        self.assertIn("LENS COMPARISON", table)
        self.assertIn("Test Lens 1", table)
        self.assertIn("Test Lens 2", table)

    def test_to_dict(self):
        """Test converting result to dictionary"""
        comp = LensComparator()
        comp.add_lens(self.lens1)
        results = comp.compare()

        result_dict = results[0].to_dict()

        self.assertIsInstance(result_dict, dict)
        self.assertIn("name", result_dict)
        self.assertIn("focal_length", result_dict)

    def test_csv_export(self):
        """Test CSV export"""
        comp = LensComparator()
        comp.add_lens(self.lens1)
        comp.add_lens(self.lens2)
        comp.compare()

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".csv") as f:
            filename = f.name

        try:
            comp.export_to_csv(filename)

            # Check file exists
            self.assertTrue(os.path.exists(filename))

            # Check content
            with open(filename, "r") as f:
                content = f.read()
                self.assertIn("name", content)
                self.assertIn("focal_length", content)
        finally:
            if os.path.exists(filename):
                os.remove(filename)


class TestCoatingDesigner(unittest.TestCase):
    """Test coating designer functionality"""

    def test_create_designer(self):
        """Test creating coating designer"""
        designer = CoatingDesigner()
        self.assertIsNotNone(designer)
        self.assertEqual(designer.substrate_index, 1.5168)  # Default BK7

    def test_custom_substrate_index(self):
        """Test custom substrate index"""
        designer = CoatingDesigner(substrate_index=1.6)
        self.assertEqual(designer.substrate_index, 1.6)

    def test_coating_materials_available(self):
        """Test that coating materials are defined"""
        self.assertIn("MgF2", CoatingDesigner.COATING_MATERIALS)
        self.assertIn("TiO2", CoatingDesigner.COATING_MATERIALS)
        self.assertIn("Ta2O5", CoatingDesigner.COATING_MATERIALS)

    def test_single_layer_ar_design(self):
        """Test designing single-layer AR coating"""
        designer = CoatingDesigner()
        layer = designer.design_single_layer_ar(wavelength_nm=550)

        self.assertIsInstance(layer, CoatingLayer)
        self.assertIsNotNone(layer.material)
        self.assertGreater(layer.thickness_nm, 0)
        self.assertGreater(layer.refractive_index, 1.0)

    def test_single_layer_thickness(self):
        """Test single-layer coating thickness is quarter-wave"""
        designer = CoatingDesigner()
        layer = designer.design_single_layer_ar(wavelength_nm=550)

        # Optical thickness should be approximately λ/4
        optical_thickness = layer.refractive_index * layer.thickness_nm
        expected = 550 / 4  # 137.5 nm

        self.assertAlmostEqual(optical_thickness, expected, delta=1.0)

    def test_dual_layer_ar_design(self):
        """Test designing dual-layer AR coating"""
        designer = CoatingDesigner()
        layers = designer.design_dual_layer_ar(wavelength_nm=550)

        self.assertEqual(len(layers), 2)
        self.assertIsInstance(layers[0], CoatingLayer)
        self.assertIsInstance(layers[1], CoatingLayer)

    def test_dual_layer_materials(self):
        """Test dual-layer coating uses different materials"""
        designer = CoatingDesigner()
        layers = designer.design_dual_layer_ar(wavelength_nm=550)

        self.assertNotEqual(layers[0].material, layers[1].material)

    def test_v_coating_design(self):
        """Test designing V-coating"""
        designer = CoatingDesigner()
        layers = designer.design_v_coating(wavelength_nm=550)

        self.assertEqual(len(layers), 3)
        for layer in layers:
            self.assertIsInstance(layer, CoatingLayer)
            self.assertGreater(layer.thickness_nm, 0)

    def test_calculate_reflectivity(self):
        """Test reflectivity calculation"""
        designer = CoatingDesigner()
        layer = designer.design_single_layer_ar(wavelength_nm=550)

        R = designer.calculate_reflectivity([layer], wavelength_nm=550)

        self.assertIsInstance(R, float)
        self.assertGreaterEqual(R, 0)
        self.assertLessEqual(R, 1.0)

    def test_reflectivity_reduced_by_coating(self):
        """Test that coating reduces reflectivity"""
        designer = CoatingDesigner()
        layer = designer.design_single_layer_ar(wavelength_nm=550)

        # Reflectivity without coating
        R_uncoated = designer.calculate_reflectivity([], wavelength_nm=550)

        # Reflectivity with coating
        R_coated = designer.calculate_reflectivity([layer], wavelength_nm=550)

        # Coating should reduce reflectivity
        self.assertLess(R_coated, R_uncoated)

    def test_reflectivity_curve(self):
        """Test generating reflectivity curve"""
        designer = CoatingDesigner()
        layer = designer.design_single_layer_ar(wavelength_nm=550)

        curve = designer.calculate_reflectivity_curve(
            [layer], wavelength_range=(400, 700), num_points=50
        )

        self.assertEqual(len(curve), 50)

        # Check format
        for wl, R in curve:
            self.assertGreaterEqual(wl, 400)
            self.assertLessEqual(wl, 700)
            self.assertGreaterEqual(R, 0)
            self.assertLessEqual(R, 1.0)

    def test_coating_info_generation(self):
        """Test generating coating info string"""
        designer = CoatingDesigner()
        layer = designer.design_single_layer_ar(wavelength_nm=550)

        info = designer.get_coating_info([layer], design_wavelength=550)

        self.assertIsInstance(info, str)
        self.assertIn("COATING SPECIFICATION", info)
        self.assertIn(layer.material, info)
        self.assertIn("550", info)

    def test_coating_info_contains_all_details(self):
        """Test that coating info contains all important details"""
        designer = CoatingDesigner()
        layers = designer.design_dual_layer_ar(wavelength_nm=550)

        info = designer.get_coating_info(layers, design_wavelength=550)

        self.assertIn("Refractive Index", info)
        self.assertIn("Physical Thickness", info)
        self.assertIn("Optical Thickness", info)
        self.assertIn("Reflectivity", info)
        self.assertIn("Transmission", info)


class TestCoatingLayer(unittest.TestCase):
    """Test CoatingLayer dataclass"""

    def test_create_layer(self):
        """Test creating coating layer"""
        layer = CoatingLayer(material="MgF2", refractive_index=1.38, thickness_nm=100)

        self.assertEqual(layer.material, "MgF2")
        self.assertEqual(layer.refractive_index, 1.38)
        self.assertEqual(layer.thickness_nm, 100)


class TestTransferMatrixPhysics(unittest.TestCase):
    """Exact-value tests for the characteristic-matrix reflectivity.

    Guards against regression to incoherent (interface-sum) estimates:
    every value below is the closed-form thin-film result.
    """

    def test_mgf2_quarter_wave_matches_exact_value(self):
        """MgF2 QW on BK7 at design wavelength gives 1.28%, not 0.92%."""
        designer = CoatingDesigner(substrate_index=1.5168)
        mgf2 = CoatingLayer("MgF2", 1.38, 550 / (4 * 1.38))

        R = designer.calculate_reflectivity([mgf2], wavelength_nm=550)

        n0, ns, nc = 1.0, 1.5168, 1.38
        expected = ((n0 * ns - nc**2) / (n0 * ns + nc**2)) ** 2
        self.assertAlmostEqual(R, expected, delta=1e-6)
        self.assertAlmostEqual(R, 0.01284, delta=1e-4)

    def test_uncoated_matches_fresnel(self):
        """Bare substrate matches the Fresnel reflectance."""
        designer = CoatingDesigner(substrate_index=1.5168)

        R = designer.calculate_reflectivity([], wavelength_nm=550)

        expected = ((1.5168 - 1.0) / (1.5168 + 1.0)) ** 2
        self.assertAlmostEqual(R, expected, delta=1e-12)

    def test_ideal_index_quarter_wave_is_zero(self):
        """A QW film with n = sqrt(ns) has exactly zero reflectance."""
        import math

        designer = CoatingDesigner(substrate_index=1.5168)
        n_ideal = math.sqrt(1.5168)
        ideal = CoatingLayer("ideal", n_ideal, 550 / (4 * n_ideal))

        R = designer.calculate_reflectivity([ideal], wavelength_nm=550)

        self.assertLess(R, 1e-12)

    def test_off_design_wavelength_shows_interference(self):
        """Reflectance must vary with wavelength (phase term is live)."""
        designer = CoatingDesigner(substrate_index=1.5168)
        mgf2 = CoatingLayer("MgF2", 1.38, 550 / (4 * 1.38))

        r_design = designer.calculate_reflectivity([mgf2], wavelength_nm=550)
        r_blue = designer.calculate_reflectivity([mgf2], wavelength_nm=400)

        self.assertNotAlmostEqual(r_design, r_blue, delta=1e-4)
        # Design wavelength is the minimum for a single AR layer.
        self.assertLess(r_design, r_blue)

    def test_angled_incidence_computed_not_stubbed(self):
        """Oblique reflectance is angle-dependent and bounded."""
        designer = CoatingDesigner(substrate_index=1.5168)
        mgf2 = CoatingLayer("MgF2", 1.38, 550 / (4 * 1.38))

        r_normal = designer.calculate_reflectivity([mgf2], 550, angle_deg=0)
        r_tilted = designer.calculate_reflectivity([mgf2], 550, angle_deg=30)

        self.assertGreaterEqual(r_tilted, 0.0)
        self.assertLessEqual(r_tilted, 1.0)
        self.assertNotAlmostEqual(r_normal, r_tilted, delta=1e-6)

    def test_invalid_inputs_raise(self):
        """Non-positive wavelength and out-of-range angle are rejected."""
        designer = CoatingDesigner()

        with self.assertRaises(ValueError):
            designer.calculate_reflectivity([], wavelength_nm=0)
        with self.assertRaises(ValueError):
            designer.calculate_reflectivity([], wavelength_nm=550, angle_deg=90)
        with self.assertRaises(ValueError):
            designer.calculate_reflectivity([], wavelength_nm=550, angle_deg=-5)


def run_tests():
    """Run all tests"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestLensComparator))
    suite.addTests(loader.loadTestsFromTestCase(TestCoatingDesigner))
    suite.addTests(loader.loadTestsFromTestCase(TestCoatingLayer))
    suite.addTests(loader.loadTestsFromTestCase(TestTransferMatrixPhysics))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(run_tests())
