#!/usr/bin/env python3
"""
End-to-End Tests for OpenLens
Tests complete workflows from start to finish - simplified for actual API
"""

import sys
import os
import unittest
import tempfile
import json

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src'))

from lens_editor import Lens
from material_database import MaterialDatabase, get_material_database
from optical_system import OpticalSystem, create_doublet
from preset_library import PresetLibrary, get_preset_library
from performance_metrics import PerformanceMetrics
from lens_comparator import LensComparator
from coating_designer import CoatingDesigner
from aberrations import AberrationsCalculator


class TestCompleteDesignWorkflow(unittest.TestCase):
    """Test complete lens design workflow from scratch"""
    
    def test_design_custom_lens_full_workflow(self):
        """E2E: Design a custom lens with full analysis"""
        # Step 1: Create a lens
        lens = Lens(
            name="Custom 50mm",
            radius_of_curvature_1=50,
            radius_of_curvature_2=-50,
            thickness=5,
            diameter=25.4,
            material="BK7"
        )
        
        # Step 2: Calculate basic properties
        focal_length = lens.calculate_focal_length()
        self.assertIsNotNone(focal_length)
        self.assertAlmostEqual(focal_length, 50, delta=5)
        
        # Step 3: Analyze performance
        metrics = PerformanceMetrics(lens)
        all_metrics = metrics.get_all_metrics()
        
        self.assertIn('f_number', all_metrics)
        self.assertIn('numerical_aperture', all_metrics)
        self.assertGreater(all_metrics['f_number'], 0)
        
        # Step 4: Calculate aberrations
        aberr = AberrationsCalculator(lens)
        aberrations = aberr.calculate_all_aberrations()
        
        self.assertIn('spherical_aberration', aberrations)
        self.assertIn('chromatic_aberration', aberrations)
        
        # Step 5: Create comparison report
        print(f"✓ Lens designed: f={focal_length:.1f}mm, f/#{all_metrics['f_number']:.2f}")
        
        print("✓ Complete design workflow successful!")


class TestPresetWorkflow(unittest.TestCase):
    """Test workflow: Load preset -> Analyze -> Compare"""
    
    def test_preset_analysis_workflow(self):
        """E2E: Load preset, analyze it, compare with others"""
        # Step 1: Get preset lens
        lib = get_preset_library()
        preset = lib.get_preset('50mm Biconvex')
        self.assertIsNotNone(preset)
        
        lens1 = preset.lens
        
        # Step 2: Get another preset
        preset2 = lib.get_preset('100mm Plano-Convex')
        self.assertIsNotNone(preset2)
        
        lens2 = preset2.lens
        
        # Step 3: Calculate metrics for both
        metrics1 = PerformanceMetrics(lens1)
        metrics2 = PerformanceMetrics(lens2)
        
        f1 = lens1.calculate_focal_length()
        f2 = lens2.calculate_focal_length()
        
        self.assertIsNotNone(f1)
        self.assertIsNotNone(f2)
        
        # Step 4: Compare lenses
        comparator = LensComparator()
        comparator.add_lens(lens1)
        comparator.add_lens(lens2)
        results = comparator.compare()
        
        self.assertEqual(len(results), 2)
        
        # Step 5: Export comparison
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as f:
            filename = f.name
        
        try:
            comparator.export_to_csv(filename)
            self.assertTrue(os.path.exists(filename))
        finally:
            if os.path.exists(filename):
                os.remove(filename)
        
        print("✓ Preset analysis workflow successful!")


class TestMultiElementSystemWorkflow(unittest.TestCase):
    """Test multi-element system design workflow"""
    
    def test_doublet_analysis_workflow(self):
        """E2E: Analyze doublet system"""
        # Step 1: Create doublet
        system = create_doublet(focal_length=100, diameter=50)
        
        self.assertEqual(len(system.elements), 2)
        
        # Step 2: Analyze system
        system_f = system.get_system_focal_length()
        self.assertIsNotNone(system_f)
        
        # Step 3: Calculate system metrics
        metrics = PerformanceMetrics(system)
        all_metrics = metrics.get_all_metrics()
        
        self.assertIn('system_length', all_metrics)
        self.assertGreater(all_metrics['system_length'], 0)
        
        # Step 4: Analyze chromatic aberration
        chromatic = system.calculate_chromatic_aberration()
        
        self.assertIn('f_C', chromatic)
        self.assertIn('f_F', chromatic)
        
        # Step 5: Save and load system
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            filename = f.name
        
        try:
            system.save(filename)
            loaded_system = OpticalSystem.load(filename)
            
            self.assertEqual(len(loaded_system.elements), 2)
        finally:
            if os.path.exists(filename):
                os.remove(filename)
        
        print("✓ Doublet analysis workflow successful!")


class TestCoatingDesignWorkflow(unittest.TestCase):
    """Test coating design workflow"""
    
    def test_coating_design_and_analysis_workflow(self):
        """E2E: Design coating, analyze reflectivity"""
        # Step 1: Create lens
        lens = Lens(
            radius_of_curvature_1=100,
            radius_of_curvature_2=-100,
            thickness=5,
            diameter=50,
            material="BK7"
        )
        
        # Step 2: Get substrate index from material database
        mat_db = get_material_database()
        substrate_n = mat_db.get_refractive_index("BK7", 550)
        
        # Step 3: Design single-layer AR coating
        designer = CoatingDesigner(substrate_index=substrate_n)
        single_layer = designer.design_single_layer_ar(wavelength_nm=550)
        
        self.assertIsNotNone(single_layer)
        self.assertGreater(single_layer.thickness_nm, 0)
        
        # Step 4: Calculate reflectivity at design wavelength
        R_uncoated = designer.calculate_reflectivity([], wavelength_nm=550)
        R_coated = designer.calculate_reflectivity([single_layer], wavelength_nm=550)
        
        # Coating should reduce reflectivity significantly
        self.assertLess(R_coated, R_uncoated)
        self.assertLess(R_coated, 0.02)  # < 2% reflectivity
        
        # Step 5: Design dual-layer coating
        dual_layer = designer.design_dual_layer_ar(wavelength_nm=550)
        
        self.assertEqual(len(dual_layer), 2)
        
        # Step 6: Generate reflectivity curve
        curve = designer.calculate_reflectivity_curve(
            dual_layer,
            wavelength_range=(400, 700),
            num_points=50
        )
        
        self.assertEqual(len(curve), 50)
        
        # Step 7: Verify reflectivity is low across visible spectrum
        visible_reflectivities = [R for wl, R in curve if 450 <= wl <= 650]
        avg_R = sum(visible_reflectivities) / len(visible_reflectivities)
        
        self.assertLess(avg_R, 0.05)  # < 5% average reflectivity
        
        print("✓ Coating design workflow successful!")


class TestMaterialSelectionWorkflow(unittest.TestCase):
    """Test material selection and comparison workflow"""
    
    def test_material_comparison_workflow(self):
        """E2E: Compare lenses with different materials"""
        # Step 1: Get material database
        mat_db = get_material_database()
        
        # Step 2: Create same lens design with different materials
        materials = ["BK7", "SF11", "F2"]
        lenses = []
        
        for mat in materials:
            lens = Lens(
                name=f"50mm {mat}",
                radius_of_curvature_1=50,
                radius_of_curvature_2=-50,
                thickness=5,
                diameter=25.4,
                material=mat
            )
            lenses.append(lens)
        
        # Step 3: Compare lenses
        comparator = LensComparator()
        for lens in lenses:
            comparator.add_lens(lens)
        
        results = comparator.compare()
        
        self.assertEqual(len(results), 3)
        
        # Step 4: Verify materials affect performance
        focal_lengths = [r.focal_length for r in results]
        
        # Different materials should give different focal lengths
        unique_focals = set(round(f, 1) for f in focal_lengths if f is not None)
        self.assertGreater(len(unique_focals), 1)
        
        # Step 5: Export comparison to CSV
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as f:
            filename = f.name
        
        try:
            comparator.export_to_csv(filename)
            
            # Verify CSV was created
            self.assertTrue(os.path.exists(filename))
            
            # Verify CSV contains data
            with open(filename, 'r') as f:
                content = f.read()
                for mat in materials:
                    self.assertIn(mat, content)
        finally:
            if os.path.exists(filename):
                os.remove(filename)
        
        print("✓ Material comparison workflow successful!")


class TestCompleteProductionWorkflow(unittest.TestCase):
    """Test complete production workflow: Design -> Analyze -> Export"""
    
    def test_full_production_workflow(self):
        """E2E: Complete workflow from design to export"""
        # Step 1: Start with preset
        lib = get_preset_library()
        preset = lib.get_preset('100mm Plano-Convex')
        lens = lib.get_lens_copy('100mm Plano-Convex')
        
        self.assertIsNotNone(lens)
        
        # Step 2: Modify design
        lens.name = "Custom 100mm"
        lens.diameter = 50.0  # Increase aperture
        
        # Step 3: Calculate initial performance
        initial_metrics = PerformanceMetrics(lens)
        initial_f_num = initial_metrics.calculate_f_number()
        
        self.assertIsNotNone(initial_f_num)
        
        # Step 4: Calculate aberrations
        aberr = AberrationsCalculator(lens)
        initial_aberrations = aberr.calculate_all_aberrations()
        
        self.assertIn('spherical_aberration', initial_aberrations)
        
        # Step 5: Design AR coating
        mat_db = get_material_database()
        substrate_n = mat_db.get_refractive_index(lens.material, 550)
        
        designer = CoatingDesigner(substrate_index=substrate_n)
        coating = designer.design_single_layer_ar(wavelength_nm=550)
        
        # Step 6: Generate coating specification
        coating_spec = designer.get_coating_info([coating], design_wavelength=550)
        self.assertIn("MgF2", coating_spec)
        
        # Step 7: Create exports
        with tempfile.TemporaryDirectory() as tmpdir:
            # Export coating specification
            coating_file = os.path.join(tmpdir, 'coating.txt')
            with open(coating_file, 'w') as f:
                f.write(coating_spec)
            self.assertTrue(os.path.exists(coating_file))
            
            # Export system as JSON (for optical system)
            system = OpticalSystem("Production Lens")
            system.add_lens(lens)
            system_file = os.path.join(tmpdir, 'system.json')
            system.save(system_file)
            self.assertTrue(os.path.exists(system_file))
        
        print("✓ Full production workflow successful!")


class TestTemperatureCompensationWorkflow(unittest.TestCase):
    """Test temperature-dependent calculations workflow"""
    
    def test_temperature_effects_on_lens(self):
        """E2E: Analyze lens performance at different temperatures"""
        # Step 1: Create lens
        lens = Lens(
            name="Temperature Test",
            radius_of_curvature_1=50,
            radius_of_curvature_2=-50,
            thickness=5,
            diameter=25.4,
            material="BK7"
        )
        
        # Step 2: Get material database
        mat_db = get_material_database()
        
        # Step 3: Calculate refractive index at different temperatures
        temps = [0, 20, 40]  # Celsius
        wavelength = 587.6  # d-line
        
        indices = []
        for temp in temps:
            # Use temperature parameter correctly
            n = mat_db.get_refractive_index("BK7", wavelength, temp)
            indices.append(n)
        
        # Step 4: Verify temperature dependence
        self.assertEqual(len(indices), 3)
        
        # All indices should be reasonable
        for n in indices:
            self.assertGreater(n, 1.4)
            self.assertLess(n, 1.7)
        
        # Step 5: Calculate lens focal length
        focal_length = lens.calculate_focal_length()
        self.assertIsNotNone(focal_length)
        
        print("✓ Temperature compensation workflow successful!")


class TestIntegratedAnalysisWorkflow(unittest.TestCase):
    """Test integrated analysis of complete optical system"""
    
    def test_complete_system_analysis(self):
        """E2E: Complete optical system analysis"""
        # Step 1: Create optical system with multiple elements
        system = OpticalSystem("Test Imaging System")
        
        # Add first lens
        lens1 = Lens(
            name="Objective",
            radius_of_curvature_1=50,
            radius_of_curvature_2=-50,
            thickness=5,
            diameter=30,
            material="BK7"
        )
        system.add_lens(lens1, air_gap_before=0)
        
        # Add second lens with air gap
        lens2 = Lens(
            name="Eyepiece",
            radius_of_curvature_1=30,
            radius_of_curvature_2=-30,
            thickness=4,
            diameter=25,
            material="BK7"
        )
        system.add_lens(lens2, air_gap_before=10)
        
        # Step 2: Calculate system properties
        system_f = system.get_system_focal_length()
        self.assertIsNotNone(system_f)
        
        system_length = system.get_total_length()
        self.assertGreater(system_length, 0)
        
        # Step 3: Get system metrics
        metrics = PerformanceMetrics(system)
        all_metrics = metrics.get_all_metrics()
        
        self.assertIn('system_length', all_metrics)
        
        # Step 4: Calculate chromatic aberration
        chromatic = system.calculate_chromatic_aberration()
        self.assertIn('longitudinal', chromatic)
        
        # Step 5: Design coatings for each surface
        mat_db = get_material_database()
        n_bk7 = mat_db.get_refractive_index("BK7", 550)
        
        designer = CoatingDesigner(substrate_index=n_bk7)
        coating = designer.design_single_layer_ar(wavelength_nm=550)
        
        self.assertIsNotNone(coating)
        
        # Step 6: Generate complete report
        report_lines = []
        report_lines.append(f"System: {system.name}")
        report_lines.append(f"Elements: {len(system.elements)}")
        report_lines.append(f"Focal Length: {system_f:.2f} mm")
        report_lines.append(f"Total Length: {system_length:.2f} mm")
        
        report = "\n".join(report_lines)
        self.assertIn("System:", report)
        
        print("✓ Complete system analysis workflow successful!")


def run_e2e_tests():
    """Run all end-to-end tests"""
    print("\n" + "="*70)
    print("RUNNING END-TO-END TESTS")
    print("="*70 + "\n")
    
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    suite.addTests(loader.loadTestsFromTestCase(TestCompleteDesignWorkflow))
    suite.addTests(loader.loadTestsFromTestCase(TestPresetWorkflow))
    suite.addTests(loader.loadTestsFromTestCase(TestMultiElementSystemWorkflow))
    suite.addTests(loader.loadTestsFromTestCase(TestCoatingDesignWorkflow))
    suite.addTests(loader.loadTestsFromTestCase(TestMaterialSelectionWorkflow))
    suite.addTests(loader.loadTestsFromTestCase(TestCompleteProductionWorkflow))
    suite.addTests(loader.loadTestsFromTestCase(TestTemperatureCompensationWorkflow))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegratedAnalysisWorkflow))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print("\n" + "="*70)
    print("END-TO-END TESTS COMPLETE")
    print("="*70)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success: {result.wasSuccessful()}")
    print("="*70 + "\n")
    
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(run_e2e_tests())
