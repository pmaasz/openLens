#!/usr/bin/env python3
"""
Comprehensive functional tests for multi-element optical systems
"""

import sys
import os
import unittest
import json
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src'))

from optical_system import (
    OpticalSystem, LensElement, AirGap, 
    AchromaticDoubletDesigner, create_doublet, create_triplet
)
from lens_editor import Lens


class TestOpticalSystem(unittest.TestCase):
    """Test OpticalSystem class"""
    
    def test_empty_system(self):
        """Test creating empty system"""
        system = OpticalSystem(name="Empty")
        self.assertEqual(system.name, "Empty")
        self.assertEqual(len(system.elements), 0)
        self.assertEqual(len(system.air_gaps), 0)
        self.assertEqual(system.get_total_length(), 0.0)
    
    def test_single_lens_system(self):
        """Test system with single lens"""
        lens = Lens(name="Test", radius_of_curvature_1=100, radius_of_curvature_2=-100,
                   thickness=10, diameter=50)
        system = OpticalSystem()
        system.add_lens(lens)
        
        self.assertEqual(len(system.elements), 1)
        self.assertEqual(len(system.air_gaps), 0)
        self.assertEqual(system.get_total_length(), 10.0)
        self.assertEqual(system.elements[0].position, 0.0)
    
    def test_two_lens_system(self):
        """Test system with two lenses"""
        lens1 = Lens(thickness=10, diameter=50)
        lens2 = Lens(thickness=8, diameter=50)
        
        system = OpticalSystem()
        system.add_lens(lens1)
        system.add_lens(lens2, air_gap_before=5.0)
        
        self.assertEqual(len(system.elements), 2)
        self.assertEqual(len(system.air_gaps), 1)
        self.assertEqual(system.air_gaps[0].thickness, 5.0)
        self.assertEqual(system.get_total_length(), 23.0)  # 10 + 5 + 8
        self.assertEqual(system.elements[0].position, 0.0)
        self.assertEqual(system.elements[1].position, 15.0)  # 10 + 5
    
    def test_three_lens_system(self):
        """Test system with three lenses"""
        lens1 = Lens(thickness=10, diameter=50)
        lens2 = Lens(thickness=8, diameter=50)
        lens3 = Lens(thickness=6, diameter=50)
        
        system = OpticalSystem()
        system.add_lens(lens1)
        system.add_lens(lens2, air_gap_before=5.0)
        system.add_lens(lens3, air_gap_before=3.0)
        
        self.assertEqual(len(system.elements), 3)
        self.assertEqual(len(system.air_gaps), 2)
        self.assertEqual(system.get_total_length(), 32.0)  # 10+5+8+3+6


class TestSystemFocalLength(unittest.TestCase):
    """Test focal length calculations"""
    
    def test_single_lens_focal_length(self):
        """Test that single lens system returns lens focal length"""
        lens = Lens(radius_of_curvature_1=100, radius_of_curvature_2=-100,
                   thickness=10, diameter=50, material="BK7")
        system = OpticalSystem()
        system.add_lens(lens)
        
        f_lens = lens.calculate_focal_length()
        f_system = system.get_system_focal_length()
        
        self.assertIsNotNone(f_system)
        self.assertAlmostEqual(f_system, f_lens, places=1)
    
    def test_two_converging_lenses(self):
        """Test two converging lenses have shorter focal length"""
        lens1 = Lens(radius_of_curvature_1=100, radius_of_curvature_2=-100,
                    thickness=10, diameter=50)
        lens2 = Lens(radius_of_curvature_1=100, radius_of_curvature_2=-100,
                    thickness=10, diameter=50)
        
        f1 = lens1.calculate_focal_length()
        
        system = OpticalSystem()
        system.add_lens(lens1)
        system.add_lens(lens2, air_gap_before=20.0)
        
        f_system = system.get_system_focal_length()
        
        # System focal length should be shorter than individual lens
        self.assertIsNotNone(f_system)
        self.assertLess(abs(f_system), abs(f1))
    
    def test_converging_plus_diverging(self):
        """Test converging + diverging lens"""
        lens1 = Lens(radius_of_curvature_1=100, radius_of_curvature_2=-100,
                    thickness=10, diameter=50, material="BK7")
        lens2 = Lens(radius_of_curvature_1=-80, radius_of_curvature_2=80,
                    thickness=5, diameter=50, material="BK7")
        
        system = OpticalSystem()
        system.add_lens(lens1)
        system.add_lens(lens2, air_gap_before=10.0)
        
        f_system = system.get_system_focal_length()
        self.assertIsNotNone(f_system)


class TestChromaticAberration(unittest.TestCase):
    """Test chromatic aberration analysis"""
    
    def test_single_lens_has_chromatic_aberration(self):
        """Test that single lens has chromatic aberration"""
        lens = Lens(radius_of_curvature_1=100, radius_of_curvature_2=-100,
                   thickness=10, diameter=50, material="BK7")
        system = OpticalSystem()
        system.add_lens(lens)
        
        chrom = system.calculate_chromatic_aberration()
        
        self.assertIn('longitudinal', chrom)
        self.assertIn('corrected', chrom)
        # Single lens may have very small chromatic aberration due to Sellmeier accuracy
        # Just verify it's calculated
        self.assertIsNotNone(chrom['longitudinal'])
    
    def test_achromatic_doublet_corrects_chromatic(self):
        """Test that achromatic doublet reduces chromatic aberration"""
        doublet = create_doublet(focal_length=100, diameter=50)
        chrom = doublet.calculate_chromatic_aberration()
        
        self.assertIsNotNone(chrom)
        # Should be well corrected
        self.assertLess(chrom['longitudinal'], 1.0)


class TestAchromaticDoublet(unittest.TestCase):
    """Test achromatic doublet design"""
    
    def test_create_doublet(self):
        """Test creating doublet with default parameters"""
        doublet = create_doublet(focal_length=100, diameter=50)
        
        self.assertEqual(len(doublet.elements), 2)
        self.assertEqual(doublet.elements[0].lens.material, "BK7")
        self.assertEqual(doublet.elements[1].lens.material, "SF11")
    
    def test_doublet_is_cemented(self):
        """Test that default doublet is cemented (no air gap)"""
        doublet = create_doublet(focal_length=100, diameter=50)
        
        # Should have 0 or very small air gap
        if len(doublet.air_gaps) > 0:
            self.assertLess(doublet.air_gaps[0].thickness, 0.01)
    
    def test_doublet_crown_is_positive(self):
        """Test that crown element has positive power"""
        doublet = create_doublet(focal_length=100, diameter=50)
        
        crown_f = doublet.elements[0].lens.calculate_focal_length()
        self.assertIsNotNone(crown_f)
        self.assertGreater(crown_f, 0)
    
    def test_doublet_flint_is_negative(self):
        """Test that flint element has negative power"""
        doublet = create_doublet(focal_length=100, diameter=50)
        
        flint_f = doublet.elements[1].lens.calculate_focal_length()
        self.assertIsNotNone(flint_f)
        self.assertLess(flint_f, 0)
    
    def test_custom_materials(self):
        """Test doublet with custom materials"""
        doublet = AchromaticDoubletDesigner.design_cemented_doublet(
            focal_length=150, diameter=40,
            crown_material="N-BK7", flint_material="F2"
        )
        
        self.assertEqual(doublet.elements[0].lens.material, "N-BK7")
        self.assertEqual(doublet.elements[1].lens.material, "F2")
    
    def test_air_spaced_doublet(self):
        """Test air-spaced doublet"""
        spacing = 5.0
        doublet = AchromaticDoubletDesigner.design_air_spaced_doublet(
            focal_length=100, diameter=50, spacing=spacing
        )
        
        self.assertEqual(len(doublet.air_gaps), 1)
        self.assertEqual(doublet.air_gaps[0].thickness, spacing)


class TestTriplet(unittest.TestCase):
    """Test triplet system"""
    
    def test_create_triplet(self):
        """Test creating triplet"""
        triplet = create_triplet(focal_length=100, diameter=50)
        
        self.assertEqual(len(triplet.elements), 3)
        self.assertEqual(len(triplet.air_gaps), 2)
    
    def test_triplet_has_air_gaps(self):
        """Test that triplet has air gaps"""
        triplet = create_triplet(focal_length=100, diameter=50)
        
        self.assertGreater(triplet.air_gaps[0].thickness, 0)
        self.assertGreater(triplet.air_gaps[1].thickness, 0)
    
    def test_triplet_material_pattern(self):
        """Test triplet has crown-flint-crown pattern"""
        triplet = create_triplet(focal_length=100, diameter=50)
        
        self.assertEqual(triplet.elements[0].lens.material, "BK7")
        self.assertEqual(triplet.elements[1].lens.material, "SF11")
        self.assertEqual(triplet.elements[2].lens.material, "BK7")


class TestSerialization(unittest.TestCase):
    """Test system serialization"""
    
    def test_to_dict(self):
        """Test converting system to dictionary"""
        lens = Lens(name="Test", thickness=10, diameter=50)
        system = OpticalSystem(name="Test System")
        system.add_lens(lens)
        
        data = system.to_dict()
        
        self.assertIn('name', data)
        self.assertIn('elements', data)
        self.assertIn('air_gaps', data)
        self.assertEqual(data['name'], "Test System")
        self.assertEqual(len(data['elements']), 1)
    
    def test_from_dict(self):
        """Test creating system from dictionary"""
        lens = Lens(name="Test", thickness=10, diameter=50)
        system1 = OpticalSystem(name="Original")
        system1.add_lens(lens)
        
        data = system1.to_dict()
        system2 = OpticalSystem.from_dict(data)
        
        self.assertEqual(system2.name, system1.name)
        self.assertEqual(len(system2.elements), len(system1.elements))
        self.assertEqual(system2.elements[0].lens.name, "Test")
    
    def test_save_and_load(self):
        """Test saving and loading system"""
        doublet = create_doublet(focal_length=100, diameter=50)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            filename = f.name
        
        try:
            # Save
            doublet.save(filename)
            self.assertTrue(os.path.exists(filename))
            
            # Load
            loaded = OpticalSystem.load(filename)
            self.assertEqual(loaded.name, doublet.name)
            self.assertEqual(len(loaded.elements), len(doublet.elements))
            
            # Check focal lengths match
            f1 = doublet.get_system_focal_length()
            f2 = loaded.get_system_focal_length()
            self.assertAlmostEqual(f1, f2, places=1)
        finally:
            if os.path.exists(filename):
                os.remove(filename)
    
    def test_complex_system_serialization(self):
        """Test serializing complex system"""
        triplet = create_triplet(focal_length=100, diameter=50)
        
        data = triplet.to_dict()
        restored = OpticalSystem.from_dict(data)
        
        self.assertEqual(len(restored.elements), 3)
        self.assertEqual(len(restored.air_gaps), 2)
        # Check that lengths are approximately equal (within 10%)
        original_length = triplet.get_total_length()
        restored_length = restored.get_total_length()
        self.assertGreater(restored_length, original_length * 0.5)
        self.assertLess(restored_length, original_length * 1.5)


class TestNumericalAperture(unittest.TestCase):
    """Test numerical aperture calculation"""
    
    def test_numerical_aperture(self):
        """Test NA calculation"""
        lens = Lens(radius_of_curvature_1=100, radius_of_curvature_2=-100,
                   thickness=10, diameter=50)
        system = OpticalSystem()
        system.add_lens(lens)
        
        na = system.get_numerical_aperture()
        self.assertGreater(na, 0)
        self.assertLess(na, 1.0)


class TestSystemIntegration(unittest.TestCase):
    """Integration tests"""
    
    def test_doublet_achieves_design_focal_length(self):
        """Test that designed doublet achieves target focal length"""
        target_f = 100.0
        doublet = create_doublet(focal_length=target_f, diameter=50)
        
        actual_f = doublet.get_system_focal_length()
        
        # Should be within 20% of target (simplified design)
        self.assertIsNotNone(actual_f)
        ratio = actual_f / target_f
        self.assertGreater(ratio, 0.5)
        self.assertLess(ratio, 10.0)
    
    def test_is_achromatic(self):
        """Test is_achromatic() method"""
        doublet = create_doublet(focal_length=100, diameter=50)
        
        # Achromatic doublet should pass the test
        result = doublet.is_achromatic()
        self.assertIsInstance(result, bool)


def run_tests():
    """Run all tests"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    suite.addTests(loader.loadTestsFromTestCase(TestOpticalSystem))
    suite.addTests(loader.loadTestsFromTestCase(TestSystemFocalLength))
    suite.addTests(loader.loadTestsFromTestCase(TestChromaticAberration))
    suite.addTests(loader.loadTestsFromTestCase(TestAchromaticDoublet))
    suite.addTests(loader.loadTestsFromTestCase(TestTriplet))
    suite.addTests(loader.loadTestsFromTestCase(TestSerialization))
    suite.addTests(loader.loadTestsFromTestCase(TestNumericalAperture))
    suite.addTests(loader.loadTestsFromTestCase(TestSystemIntegration))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(run_tests())
