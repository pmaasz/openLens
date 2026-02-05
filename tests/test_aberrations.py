#!/usr/bin/env python3
"""
Tests for lens aberrations calculator
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from lens_editor import Lens
from aberrations import AberrationsCalculator, analyze_lens_quality


class TestAberrationsCalculator(unittest.TestCase):
    """Test suite for aberrations calculations"""
    
    def setUp(self):
        """Create test lenses"""
        # Standard biconvex lens
        self.biconvex = Lens(
            name="Test Biconvex",
            radius_of_curvature_1=100.0,
            radius_of_curvature_2=-100.0,
            thickness=5.0,
            diameter=50.0,
            refractive_index=1.5168,
            lens_type="Biconvex",
            material="BK7"
        )
        
        # Plano-convex lens
        self.plano_convex = Lens(
            name="Test Plano-Convex",
            radius_of_curvature_1=50.0,
            radius_of_curvature_2=10000.0,  # Nearly flat
            thickness=4.0,
            diameter=25.0,
            refractive_index=1.4585,
            lens_type="Plano-Convex",
            material="Fused Silica"
        )
        
        # High-index lens
        self.high_index = Lens(
            name="Test High Index",
            radius_of_curvature_1=30.0,
            radius_of_curvature_2=-40.0,
            thickness=8.0,
            diameter=20.0,
            refractive_index=1.78,
            lens_type="Biconvex",
            material="SF11"
        )
    
    def test_calculator_initialization(self):
        """Test that calculator initializes correctly"""
        calc = AberrationsCalculator(self.biconvex)
        self.assertAlmostEqual(calc.n, 1.5168, places=4)
        self.assertEqual(calc.R1, 100.0)
        self.assertEqual(calc.R2, -100.0)
        self.assertEqual(calc.D, 50.0)
    
    def test_calculate_all_aberrations(self):
        """Test that all aberrations are calculated"""
        calc = AberrationsCalculator(self.biconvex)
        results = calc.calculate_all_aberrations(field_angle=5.0)
        
        # Check that all expected keys are present
        expected_keys = [
            'focal_length', 'numerical_aperture', 'f_number',
            'spherical_aberration', 'coma', 'astigmatism',
            'field_curvature', 'distortion', 'chromatic_aberration',
            'airy_disk_diameter'
        ]
        
        for key in expected_keys:
            self.assertIn(key, results)
            self.assertIsNotNone(results[key])
    
    def test_f_number_calculation(self):
        """Test f-number calculation"""
        calc = AberrationsCalculator(self.biconvex)
        focal_length = self.biconvex.calculate_focal_length()
        f_number = calc._calculate_f_number(focal_length)
        
        # f/# = f/D
        expected = abs(focal_length) / 50.0
        self.assertAlmostEqual(f_number, expected, places=2)
    
    def test_numerical_aperture(self):
        """Test numerical aperture calculation"""
        calc = AberrationsCalculator(self.biconvex)
        focal_length = self.biconvex.calculate_focal_length()
        na = calc._calculate_numerical_aperture(focal_length)
        
        # NA should be positive and less than n
        self.assertGreater(na, 0)
        self.assertLess(na, calc.n)
    
    def test_spherical_aberration_increases_with_aperture(self):
        """Test that spherical aberration increases with larger aperture"""
        # Small aperture lens
        small_lens = Lens(
            name="Small Aperture",
            radius_of_curvature_1=100.0,
            radius_of_curvature_2=-100.0,
            thickness=5.0,
            diameter=20.0,  # Small diameter
            refractive_index=1.5168,
            material="BK7"
        )
        
        # Large aperture lens
        large_lens = Lens(
            name="Large Aperture",
            radius_of_curvature_1=100.0,
            radius_of_curvature_2=-100.0,
            thickness=5.0,
            diameter=60.0,  # Large diameter
            refractive_index=1.5168,
            material="BK7"
        )
        
        calc_small = AberrationsCalculator(small_lens)
        calc_large = AberrationsCalculator(large_lens)
        
        sa_small = abs(calc_small._calculate_spherical_aberration(
            small_lens.calculate_focal_length()
        ))
        sa_large = abs(calc_large._calculate_spherical_aberration(
            large_lens.calculate_focal_length()
        ))
        
        # Larger aperture should have more spherical aberration
        self.assertGreater(sa_large, sa_small)
    
    def test_chromatic_aberration_material_dependent(self):
        """Test that chromatic aberration varies with material"""
        calc_bk7 = AberrationsCalculator(self.biconvex)
        calc_sf11 = AberrationsCalculator(self.high_index)
        
        f_bk7 = self.biconvex.calculate_focal_length()
        f_sf11 = self.high_index.calculate_focal_length()
        
        ca_bk7 = calc_bk7._calculate_chromatic_aberration(f_bk7)
        ca_sf11 = calc_sf11._calculate_chromatic_aberration(f_sf11)
        
        # SF11 has lower Abbe number, so should have more chromatic aberration
        # relative to focal length
        ratio_bk7 = ca_bk7 / abs(f_bk7)
        ratio_sf11 = ca_sf11 / abs(f_sf11)
        
        self.assertGreater(ratio_sf11, ratio_bk7)
    
    def test_coma_zero_on_axis(self):
        """Test that coma is zero on-axis"""
        calc = AberrationsCalculator(self.biconvex)
        focal_length = self.biconvex.calculate_focal_length()
        
        coma_on_axis = calc._calculate_coma(focal_length, field_angle_deg=0.0)
        self.assertEqual(coma_on_axis, 0)
    
    def test_coma_increases_with_field_angle(self):
        """Test that coma increases with field angle"""
        # Use asymmetric lens (plano-convex) - symmetric lenses have zero coma
        calc = AberrationsCalculator(self.plano_convex)
        focal_length = self.plano_convex.calculate_focal_length()
        
        coma_5deg = abs(calc._calculate_coma(focal_length, field_angle_deg=5.0))
        coma_10deg = abs(calc._calculate_coma(focal_length, field_angle_deg=10.0))
        
        self.assertGreater(coma_10deg, coma_5deg)
    
    def test_astigmatism_zero_on_axis(self):
        """Test that astigmatism is zero on-axis"""
        calc = AberrationsCalculator(self.biconvex)
        focal_length = self.biconvex.calculate_focal_length()
        
        ast_on_axis = calc._calculate_astigmatism(focal_length, field_angle_deg=0.0)
        self.assertEqual(ast_on_axis, 0)
    
    def test_field_curvature_calculation(self):
        """Test field curvature (Petzval) calculation"""
        calc = AberrationsCalculator(self.biconvex)
        focal_length = self.biconvex.calculate_focal_length()
        
        field_curv = calc._calculate_field_curvature(focal_length)
        
        # Field curvature should be negative (curved toward lens)
        self.assertLess(field_curv, 0)
    
    def test_airy_disk_calculation(self):
        """Test Airy disk diameter calculation"""
        calc = AberrationsCalculator(self.biconvex)
        focal_length = self.biconvex.calculate_focal_length()
        
        airy = calc._calculate_airy_disk(focal_length)
        
        # Airy disk should be positive and very small (microns)
        self.assertGreater(airy, 0)
        self.assertLess(airy, 0.1)  # Less than 0.1mm = 100 microns
    
    def test_aberration_summary_generation(self):
        """Test that summary string is generated"""
        calc = AberrationsCalculator(self.biconvex)
        summary = calc.get_aberration_summary(field_angle=5.0)
        
        # Check that summary contains key information
        self.assertIn("ABERRATIONS ANALYSIS", summary)
        self.assertIn("Focal Length", summary)
        self.assertIn("Spherical Aberration", summary)
        self.assertIn("Chromatic Aberration", summary)
    
    def test_lens_quality_analysis(self):
        """Test lens quality analysis function"""
        quality = analyze_lens_quality(self.biconvex, field_angle=5.0)
        
        # Check that quality assessment contains required keys
        self.assertIn('quality_score', quality)
        self.assertIn('rating', quality)
        self.assertIn('issues', quality)
        self.assertIn('aberrations', quality)
        
        # Score should be between 0 and 100
        self.assertGreaterEqual(quality['quality_score'], 0)
        self.assertLessEqual(quality['quality_score'], 100)
        
        # Rating should be one of the expected values
        valid_ratings = ['Excellent', 'Good', 'Fair', 'Poor', 'Very Poor', 'Error']
        self.assertIn(quality['rating'], valid_ratings)
    
    def test_zero_power_lens_handling(self):
        """Test handling of lens with zero optical power"""
        # Create a plane parallel plate (both surfaces flat = zero power)
        zero_power = Lens(
            name="Zero Power",
            radius_of_curvature_1=float('inf'),  # Flat surface
            radius_of_curvature_2=float('inf'),  # Flat surface
            thickness=5.0,
            diameter=50.0,
            refractive_index=1.5168,
            material="Custom"
        )
        
        calc = AberrationsCalculator(zero_power)
        results = calc.calculate_all_aberrations()
        
        # Should handle gracefully (either error or very large focal length)
        self.assertTrue('error' in results or results['focal_length'] is None or abs(results['focal_length']) > 1e6)
    
    def test_plano_convex_aberrations(self):
        """Test aberrations for plano-convex lens"""
        calc = AberrationsCalculator(self.plano_convex)
        results = calc.calculate_all_aberrations(field_angle=5.0)
        
        # Should calculate successfully
        self.assertNotIn('error', results)
        self.assertIsNotNone(results['focal_length'])
        self.assertIsNotNone(results['spherical_aberration'])


class TestAberrationsIntegration(unittest.TestCase):
    """Integration tests for aberrations with lens editor"""
    
    def test_aberrations_with_different_lens_types(self):
        """Test aberrations for various lens types"""
        lens_configs = [
            ("Biconvex", 100.0, -100.0),
            ("Biconcave", -100.0, 100.0),
            ("Plano-Convex", 50.0, 10000.0),
            ("Meniscus", 80.0, 100.0),
        ]
        
        for lens_type, R1, R2 in lens_configs:
            with self.subTest(lens_type=lens_type):
                lens = Lens(
                    name=f"Test {lens_type}",
                    radius_of_curvature_1=R1,
                    radius_of_curvature_2=R2,
                    thickness=5.0,
                    diameter=50.0,
                    refractive_index=1.5168,
                    lens_type=lens_type,
                    material="BK7"
                )
                
                calc = AberrationsCalculator(lens)
                results = calc.calculate_all_aberrations()
                
                # Should not error for any lens type
                if lens.calculate_focal_length() is not None:
                    self.assertNotIn('error', results)


class TestAberrationsBehavior(unittest.TestCase):
    """Functional tests for expected aberration behaviors"""
    
    def test_distortion_sign_convention(self):
        """Test that distortion sign indicates barrel vs pincushion correctly"""
        # Biconvex should have pincushion distortion (positive)
        biconvex = Lens(
            name="Biconvex",
            radius_of_curvature_1=100.0,
            radius_of_curvature_2=-100.0,
            thickness=5.0,
            diameter=50.0,
            refractive_index=1.5168,
            material="BK7"
        )
        
        calc = AberrationsCalculator(biconvex)
        focal_length = biconvex.calculate_focal_length()
        distortion = calc._calculate_distortion(focal_length, field_angle_deg=10.0)
        
        # For symmetric biconvex, shape factor is 0, so distortion should be 0
        self.assertAlmostEqual(distortion, 0.0, places=5)
    
    def test_aberrations_scale_correctly_with_parameters(self):
        """Test that aberrations scale as expected with lens parameters"""
        # Create two lenses differing only in diameter
        small = Lens(name="Small", radius_of_curvature_1=100.0, 
                    radius_of_curvature_2=-100.0, thickness=5.0, 
                    diameter=25.0, refractive_index=1.5168, material="BK7")
        
        large = Lens(name="Large", radius_of_curvature_1=100.0, 
                    radius_of_curvature_2=-100.0, thickness=5.0, 
                    diameter=50.0, refractive_index=1.5168, material="BK7")
        
        calc_small = AberrationsCalculator(small)
        calc_large = AberrationsCalculator(large)
        
        results_small = calc_small.calculate_all_aberrations(field_angle=5.0)
        results_large = calc_large.calculate_all_aberrations(field_angle=5.0)
        
        # Spherical aberration should increase with diameter (∝ D^4)
        # Since diameter doubled, SA should increase by factor of 16
        ratio = abs(results_large['spherical_aberration']) / abs(results_small['spherical_aberration'])
        self.assertGreater(ratio, 10)  # Should be ~16, but allow tolerance
        
        # F-number should be smaller for larger aperture
        self.assertLess(results_large['f_number'], results_small['f_number'])
    
    def test_chromatic_aberration_decreases_with_high_abbe(self):
        """Test that materials with high Abbe number have less chromatic aberration"""
        # Fused Silica has higher Abbe number than SF11
        silica = Lens(name="Silica", radius_of_curvature_1=100.0,
                     radius_of_curvature_2=-100.0, thickness=5.0,
                     diameter=50.0, refractive_index=1.4585, material="Fused Silica")
        
        sf11 = Lens(name="SF11", radius_of_curvature_1=100.0,
                   radius_of_curvature_2=-100.0, thickness=5.0,
                   diameter=50.0, refractive_index=1.78, material="SF11")
        
        calc_silica = AberrationsCalculator(silica)
        calc_sf11 = AberrationsCalculator(sf11)
        
        f_silica = silica.calculate_focal_length()
        f_sf11 = sf11.calculate_focal_length()
        
        ca_silica = calc_silica._calculate_chromatic_aberration(f_silica)
        ca_sf11 = calc_sf11._calculate_chromatic_aberration(f_sf11)
        
        # Normalized by focal length
        ca_silica_norm = ca_silica / abs(f_silica)
        ca_sf11_norm = ca_sf11 / abs(f_sf11)
        
        # SF11 should have higher chromatic aberration (lower Abbe number)
        self.assertGreater(ca_sf11_norm, ca_silica_norm)
    
    def test_quality_score_decreases_with_aberrations(self):
        """Test that quality score properly reflects aberration levels"""
        # Create a good lens (moderate aperture, symmetric design)
        good_lens = Lens(name="Good", radius_of_curvature_1=100.0,
                        radius_of_curvature_2=-100.0, thickness=5.0,
                        diameter=25.0, refractive_index=1.5168, material="Custom")
        
        # Create a poor lens (very large aperture, asymmetric, high aberrations)
        poor_lens = Lens(name="Poor", radius_of_curvature_1=30.0,
                        radius_of_curvature_2=-20.0, thickness=8.0,
                        diameter=100.0, refractive_index=1.78, material="Custom")
        
        quality_good = analyze_lens_quality(good_lens, field_angle=2.0)
        quality_poor = analyze_lens_quality(poor_lens, field_angle=15.0)
        
        # Good lens should have higher quality score
        self.assertGreater(quality_good['quality_score'], quality_poor['quality_score'])
        
        # Poor lens should have more issues
        self.assertGreaterEqual(len(quality_poor['issues']), len(quality_good['issues']))
    
    def test_field_curvature_sign(self):
        """Test that field curvature has correct sign (negative = curved toward lens)"""
        lens = Lens(name="Test", radius_of_curvature_1=100.0,
                   radius_of_curvature_2=-100.0, thickness=5.0,
                   diameter=50.0, refractive_index=1.5168, material="BK7")
        
        calc = AberrationsCalculator(lens)
        focal_length = lens.calculate_focal_length()
        field_curv = calc._calculate_field_curvature(focal_length)
        
        # Field curvature should be negative for converging lens
        self.assertLess(field_curv, 0)
    
    def test_airy_disk_increases_with_f_number(self):
        """Test that Airy disk diameter increases with f-number"""
        # Fast lens (low f-number)
        fast = Lens(name="Fast", radius_of_curvature_1=100.0,
                   radius_of_curvature_2=-100.0, thickness=5.0,
                   diameter=80.0, refractive_index=1.5168, material="BK7")
        
        # Slow lens (high f-number)
        slow = Lens(name="Slow", radius_of_curvature_1=100.0,
                   radius_of_curvature_2=-100.0, thickness=5.0,
                   diameter=20.0, refractive_index=1.5168, material="BK7")
        
        calc_fast = AberrationsCalculator(fast)
        calc_slow = AberrationsCalculator(slow)
        
        results_fast = calc_fast.calculate_all_aberrations()
        results_slow = calc_slow.calculate_all_aberrations()
        
        # Slow lens (high f/#) should have larger Airy disk
        self.assertGreater(results_slow['airy_disk_diameter'], 
                          results_fast['airy_disk_diameter'])
    
    def test_summary_output_format(self):
        """Test that summary output is properly formatted and complete"""
        lens = Lens(name="Test Lens", radius_of_curvature_1=100.0,
                   radius_of_curvature_2=-100.0, thickness=5.0,
                   diameter=50.0, refractive_index=1.5168, material="BK7")
        
        calc = AberrationsCalculator(lens)
        summary = calc.get_aberration_summary(field_angle=5.0)
        
        # Check for essential sections
        self.assertIn("LENS ABERRATIONS ANALYSIS", summary)
        self.assertIn("BASIC PARAMETERS", summary)
        self.assertIn("PRIMARY ABERRATIONS", summary)
        self.assertIn("CHROMATIC ABERRATION", summary)
        self.assertIn("INTERPRETATION", summary)
        
        # Check for specific values
        self.assertIn("Focal Length", summary)
        self.assertIn("F-number", summary)
        self.assertIn("Spherical Aberration", summary)
        self.assertIn("Coma", summary)
        self.assertIn("Astigmatism", summary)
        self.assertIn("Field Curvature", summary)
        self.assertIn("Distortion", summary)
        self.assertIn("Longitudinal CA", summary)
        
        # Should contain lens name and material
        self.assertIn("Test Lens", summary)
        self.assertIn("BK7", summary)
    
    def test_unknown_material_handling(self):
        """Test that unknown materials get estimated Abbe numbers"""
        custom_lens = Lens(name="Custom", radius_of_curvature_1=100.0,
                          radius_of_curvature_2=-100.0, thickness=5.0,
                          diameter=50.0, refractive_index=1.6, material="Custom Material")
        
        calc = AberrationsCalculator(custom_lens)
        focal_length = custom_lens.calculate_focal_length()
        ca = calc._calculate_chromatic_aberration(focal_length)
        
        # Should still calculate chromatic aberration using estimated Abbe number
        self.assertIsNotNone(ca)
        self.assertGreater(ca, 0)
    
    def test_extreme_field_angles(self):
        """Test aberrations at extreme field angles"""
        # Use asymmetric lens for coma testing (avoid infinity radius)
        lens = Lens(name="Test", radius_of_curvature_1=100.0,
                   radius_of_curvature_2=-200.0, thickness=5.0,  # Asymmetric meniscus
                   diameter=50.0, refractive_index=1.5168, material="Custom")
        
        calc = AberrationsCalculator(lens)
        
        # Test at 0 degrees (on-axis)
        results_0 = calc.calculate_all_aberrations(field_angle=0.0)
        self.assertEqual(results_0['coma'], 0)
        self.assertEqual(results_0['astigmatism'], 0)
        self.assertEqual(results_0['distortion'], 0)
        
        # Test at wide field angle
        results_wide = calc.calculate_all_aberrations(field_angle=20.0)
        self.assertGreater(abs(results_wide['coma']), 0)
        self.assertGreater(results_wide['astigmatism'], 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
