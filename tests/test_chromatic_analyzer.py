#!/usr/bin/env python3
"""
Functional tests for Chromatic Analyzer
Tests wavelength-dependent calculations and chromatic aberration analysis
"""

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from chromatic_analyzer import ChromaticAnalyzer, ChromaticResult
from material_database import MaterialDatabase, MaterialProperties
import math


class TestChromaticAnalyzer(unittest.TestCase):
    """Test chromatic aberration analysis"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.analyzer = ChromaticAnalyzer()
        self.material_db = MaterialDatabase()
    
    def test_wavelength_constants(self):
        """Test that standard wavelengths are defined"""
        self.assertIn('d', ChromaticAnalyzer.WAVELENGTHS)
        self.assertIn('F', ChromaticAnalyzer.WAVELENGTHS)
        self.assertIn('C', ChromaticAnalyzer.WAVELENGTHS)
        self.assertEqual(ChromaticAnalyzer.WAVELENGTHS['d'], 587.6)
        self.assertEqual(ChromaticAnalyzer.WAVELENGTHS['F'], 486.1)
        self.assertEqual(ChromaticAnalyzer.WAVELENGTHS['C'], 656.3)
    
    def test_abbe_number_calculation(self):
        """Test Abbe number calculation for BK7"""
        abbe = self.analyzer.calculate_abbe_number('BK7')
        # BK7 should have Abbe number around 64
        self.assertGreater(abbe, 60)
        self.assertLess(abbe, 68)
    
    def test_abbe_number_flint_vs_crown(self):
        """Test that flint glass has lower Abbe number than crown"""
        abbe_bk7 = self.analyzer.calculate_abbe_number('BK7')  # Crown
        abbe_f2 = self.analyzer.calculate_abbe_number('F2')    # Flint
        
        # Crown should have higher Abbe number (lower dispersion)
        self.assertGreater(abbe_bk7, abbe_f2)
        
        # F2 should have Abbe number around 36
        self.assertGreater(abbe_f2, 30)
        self.assertLess(abbe_f2, 40)
    
    def test_partial_dispersion(self):
        """Test partial dispersion calculation"""
        partial = self.analyzer.calculate_partial_dispersion('BK7', 'g', 'F')
        
        # Partial dispersion should be positive and reasonable
        self.assertGreater(partial, 0)
        self.assertLess(partial, 1)
    
    def test_refractive_index_wavelength_dependence(self):
        """Test that refractive index varies with wavelength"""
        # Blue light should have higher refractive index than red (normal dispersion)
        n_blue = self.material_db.get_refractive_index('BK7', 450)
        n_green = self.material_db.get_refractive_index('BK7', 550)
        n_red = self.material_db.get_refractive_index('BK7', 650)
        
        self.assertGreater(n_blue, n_green)
        self.assertGreater(n_green, n_red)
    
    def test_refractive_index_temperature_dependence(self):
        """Test that refractive index varies with temperature"""
        n_20c = self.material_db.get_refractive_index('BK7', 587.6, 20)
        n_50c = self.material_db.get_refractive_index('BK7', 587.6, 50)
        
        # Should be different (actual sign depends on material)
        self.assertNotEqual(n_20c, n_50c)
        
        # Change should be small but measurable
        delta_n = abs(n_50c - n_20c)
        self.assertGreater(delta_n, 1e-6)
        self.assertLess(delta_n, 1e-2)
    
    def test_achromatic_doublet_design(self):
        """Test achromatic doublet design"""
        focal_length = 100.0  # mm
        doublet = self.analyzer.design_achromatic_doublet(
            focal_length, 'BK7', 'F2'
        )
        
        # Check structure
        self.assertIn('crown_element', doublet)
        self.assertIn('flint_element', doublet)
        
        # Crown element should be positive (converging)
        self.assertGreater(doublet['crown_element']['power'], 0)
        
        # Flint element should be negative (diverging)
        self.assertLess(doublet['flint_element']['power'], 0)
        
        # Total focal length should match
        self.assertAlmostEqual(doublet['total_focal_length'], focal_length, places=1)
        
        # Total power should be 1/f
        expected_power = 1.0 / focal_length
        self.assertAlmostEqual(doublet['total_power'], expected_power, places=6)
    
    def test_achromatic_condition(self):
        """Test that achromatic doublet satisfies chromatic correction"""
        doublet = self.analyzer.design_achromatic_doublet(100.0, 'BK7', 'F2')
        
        # For achromatic doublet: φ1/V1 + φ2/V2 = 0
        phi1 = doublet['crown_element']['power']
        phi2 = doublet['flint_element']['power']
        V1 = doublet['crown_element']['abbe_number']
        V2 = doublet['flint_element']['abbe_number']
        
        chromatic_sum = phi1 / V1 + phi2 / V2
        
        # Should be very close to zero
        self.assertAlmostEqual(chromatic_sum, 0.0, places=8)
    
    def test_chromatic_focal_shift(self):
        """Test chromatic focal shift calculation"""
        lens_params = {
            'radius1': 50.0,
            'radius2': -50.0,
            'thickness': 5.0,
            'diameter': 25.0,
            'material': 'BK7'
        }
        
        result = self.analyzer.plot_chromatic_focal_shift(
            lens_params, 
            wavelength_range=(450, 650),
            num_points=5
        )
        
        # Check structure
        self.assertIn('wavelengths', result)
        self.assertIn('focal_lengths', result)
        self.assertEqual(len(result['wavelengths']), 5)
        self.assertEqual(len(result['focal_lengths']), 5)
        
        # Wavelengths should span the range
        self.assertAlmostEqual(result['wavelengths'][0], 450, places=1)
        self.assertAlmostEqual(result['wavelengths'][-1], 650, places=1)
        
        # Focal lengths should be positive and vary
        for f in result['focal_lengths']:
            self.assertGreater(f, 0)
        
        # Should show dispersion (different focal lengths)
        focal_range = max(result['focal_lengths']) - min(result['focal_lengths'])
        self.assertGreater(focal_range, 0)
    
    def test_transmission_data(self):
        """Test transmission data retrieval"""
        # BK7 has transmission data
        trans_400 = self.material_db.get_transmission('BK7', 400)
        trans_600 = self.material_db.get_transmission('BK7', 600)
        
        # Should be between 0 and 1
        self.assertGreaterEqual(trans_400, 0)
        self.assertLessEqual(trans_400, 1)
        self.assertGreaterEqual(trans_600, 0)
        self.assertLessEqual(trans_600, 1)
        
        # Visible light should have high transmission
        self.assertGreater(trans_600, 0.9)
    
    def test_transmission_interpolation(self):
        """Test that transmission is interpolated correctly"""
        # Get transmission at wavelength between data points
        trans = self.material_db.get_transmission('BK7', 550)
        
        # Should be reasonable
        self.assertGreater(trans, 0.9)
        self.assertLessEqual(trans, 1.0)
    
    def test_chromatic_result_structure(self):
        """Test ChromaticResult data structure"""
        result = ChromaticResult(
            wavelengths=[450, 550, 650],
            focal_lengths=[100.1, 100.0, 99.9],
            focal_shift=0.2,
            lateral_color=0.05,
            spot_sizes=[0.01, 0.008, 0.012],
            transverse_aberration=[0.02, 0.015, 0.025],
            axial_chromatic_aberration=0.2
        )
        
        # Test to_dict conversion
        result_dict = result.to_dict()
        self.assertIn('wavelengths', result_dict)
        self.assertIn('focal_lengths', result_dict)
        self.assertIn('focal_shift', result_dict)
        self.assertEqual(result_dict['focal_shift'], 0.2)
    
    def test_multiple_materials(self):
        """Test analysis with different materials"""
        materials = ['BK7', 'F2', 'FUSEDSILICA']
        
        for material in materials:
            # Should be able to calculate Abbe number
            abbe = self.analyzer.calculate_abbe_number(material)
            self.assertGreater(abbe, 0)
            self.assertLess(abbe, 100)
            
            # Should be able to get refractive indices
            n = self.material_db.get_refractive_index(material, 587.6)
            self.assertGreater(n, 1.0)
            self.assertLess(n, 3.0)
    
    def test_uv_material_fused_silica(self):
        """Test that fused silica works in UV range"""
        # Fused silica should transmit UV
        trans_250 = self.material_db.get_transmission('FUSEDSILICA', 250)
        trans_200 = self.material_db.get_transmission('FUSEDSILICA', 200)
        
        # Should have reasonable UV transmission
        self.assertGreater(trans_250, 0.8)
        self.assertGreater(trans_200, 0.5)
        
        # Can calculate refractive index in UV
        n_uv = self.material_db.get_refractive_index('FUSEDSILICA', 250)
        n_vis = self.material_db.get_refractive_index('FUSEDSILICA', 550)
        
        # UV should have higher index
        self.assertGreater(n_uv, n_vis)
    
    def test_high_index_material(self):
        """Test high refractive index material (S-LAH79)"""
        n = self.material_db.get_refractive_index('S-LAH79', 587.6)
        
        # Should be high index (around 2.0, but may be slightly less depending on Sellmeier fit)
        self.assertGreater(n, 1.9)
        self.assertLess(n, 2.1)
        
        # Should have low Abbe number (high dispersion)
        abbe = self.analyzer.calculate_abbe_number('S-LAH79')
        self.assertGreater(abbe, 25)
        self.assertLess(abbe, 32)
    
    def test_extreme_wavelengths(self):
        """Test behavior at extreme wavelengths"""
        # Near UV
        n_uv = self.material_db.get_refractive_index('BK7', 380)
        
        # Near IR
        n_ir = self.material_db.get_refractive_index('BK7', 1000)
        
        # Both should be reasonable
        self.assertGreater(n_uv, 1.4)
        self.assertLess(n_uv, 1.7)
        self.assertGreater(n_ir, 1.4)
        self.assertLess(n_ir, 1.6)
        
        # UV should have higher index
        self.assertGreater(n_uv, n_ir)


class TestMaterialDatabase(unittest.TestCase):
    """Test material database functionality"""
    
    def setUp(self):
        self.db = MaterialDatabase()
    
    def test_load_builtin_materials(self):
        """Test that built-in materials are loaded"""
        materials = self.db.list_materials()
        
        # Should have standard materials
        self.assertIn('BK7', materials)
        self.assertIn('F2', materials)
        self.assertIn('FUSEDSILICA', materials)
    
    def test_get_material(self):
        """Test getting material properties"""
        mat = self.db.get_material('BK7')
        
        self.assertIsNotNone(mat)
        self.assertEqual(mat.name, 'BK7')
        self.assertEqual(mat.catalog, 'Schott')
        self.assertAlmostEqual(mat.nd, 1.5168, places=4)
        self.assertAlmostEqual(mat.vd, 64.17, places=2)
    
    def test_sellmeier_coefficients(self):
        """Test that Sellmeier coefficients are present"""
        mat = self.db.get_material('BK7')
        
        # Should have Sellmeier coefficients
        self.assertGreater(mat.B1, 0)
        self.assertGreater(mat.C1, 0)
    
    def test_case_insensitive_lookup(self):
        """Test case-insensitive material lookup"""
        mat1 = self.db.get_material('BK7')
        mat2 = self.db.get_material('bk7')
        mat3 = self.db.get_material('Bk7')
        
        self.assertEqual(mat1.name, mat2.name)
        self.assertEqual(mat1.name, mat3.name)
    
    def test_list_by_catalog(self):
        """Test filtering materials by catalog"""
        schott = self.db.list_materials('Schott')
        ohara = self.db.list_materials('Ohara')
        hoya = self.db.list_materials('Hoya')
        
        self.assertIn('BK7', schott)
        self.assertIn('S-LAH79', ohara)
        self.assertIn('E-FD60', hoya)
    
    def test_temperature_coefficients(self):
        """Test that temperature coefficients exist"""
        mat = self.db.get_material('BK7')
        
        # Should have temperature coefficients
        self.assertIsNotNone(mat.D0)
        self.assertIsNotNone(mat.D1)
    
    def test_physical_properties(self):
        """Test physical property data"""
        mat = self.db.get_material('BK7')
        
        # Should have density
        self.assertGreater(mat.density, 0)
        
        # Should have thermal expansion
        self.assertGreater(mat.thermal_expansion, 0)
        
        # Should have resistance ratings
        self.assertIn(mat.climate_resistance, [0, 1, 2, 3, 4])
        self.assertIn(mat.acid_resistance, [0, 1, 2, 3, 4])


if __name__ == '__main__':
    unittest.main()
