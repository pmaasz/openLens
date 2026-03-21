#!/usr/bin/env python3
"""
Test multi-element optical systems
"""

import sys
import os
import unittest
import tempfile
import json
import math

# Adjust path to find src
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src'))

from optical_system import OpticalSystem, AchromaticDoubletDesigner, create_doublet, create_triplet, AirGap
from lens import Lens

class TestOpticalSystem(unittest.TestCase):

    def setUp(self):
        # Create some basic lenses for testing
        self.lens1 = Lens(name="Lens 1", radius_of_curvature_1=100, radius_of_curvature_2=-100,
                          thickness=10, diameter=50, material="BK7")
        self.lens2 = Lens(name="Lens 2", radius_of_curvature_1=80, radius_of_curvature_2=-80,
                          thickness=8, diameter=50, material="BK7")

    def test_initialization(self):
        system = OpticalSystem(name="Test System")
        self.assertEqual(system.name, "Test System")
        self.assertEqual(len(system.elements), 0)
        self.assertEqual(len(system.air_gaps), 0)
        self.assertEqual(system.get_total_length(), 0.0)

    def test_add_lens(self):
        system = OpticalSystem()
        system.add_lens(self.lens1)
        
        self.assertEqual(len(system.elements), 1)
        self.assertEqual(system.elements[0].lens, self.lens1)
        self.assertEqual(system.elements[0].position, 0.0)
        self.assertEqual(system.get_total_length(), 10.0)

        # Add second lens with air gap
        system.add_lens(self.lens2, air_gap_before=20.0)
        
        self.assertEqual(len(system.elements), 2)
        self.assertEqual(len(system.air_gaps), 1)
        self.assertEqual(system.air_gaps[0].thickness, 20.0)
        
        # Position check: 0 + 10 (thick) + 20 (gap) = 30
        self.assertEqual(system.elements[1].position, 30.0)
        # Total length: 30 + 8 (thick) = 38
        self.assertEqual(system.get_total_length(), 38.0)

    def test_system_focal_length_two_lenses(self):
        system = OpticalSystem()
        system.add_lens(self.lens1)
        system.add_lens(self.lens2, air_gap_before=20.0)
        
        f1 = self.lens1.calculate_focal_length()
        f2 = self.lens2.calculate_focal_length()
        d = 20.0
        
        # Theoretical combined focal length for two thin lenses
        # 1/f = 1/f1 + 1/f2 - d/(f1*f2)
        expected_power = 1/f1 + 1/f2 - d/(f1*f2)
        expected_f = 1/expected_power
        
        calculated_f = system.get_system_focal_length()
        
        # Since the implementation might use matrix method or thick lens approximation,
        # we expect it to be close but maybe not exact to the thin lens formula if using matrix
        # However, the current implementation explicitly uses the thin lens formula for 2 lenses
        self.assertIsNotNone(calculated_f)
        self.assertAlmostEqual(calculated_f, expected_f, places=1)

    def test_system_f_number(self):
        """Test system f-number calculation"""
        system = OpticalSystem()
        # Single lens
        system.add_lens(self.lens1)
        f = self.lens1.calculate_focal_length()
        D = self.lens1.diameter
        expected_f_num = f / D
        
        self.assertAlmostEqual(system.get_system_f_number(), expected_f_num, places=2)
        
        # Two lenses
        system.add_lens(self.lens2, air_gap_before=20.0)
        f_sys = system.get_system_focal_length()
        # Entrance pupil is still lens1 diameter (approximation used in implementation)
        expected_f_num_sys = abs(f_sys) / D
        
        self.assertAlmostEqual(system.get_system_f_number(), expected_f_num_sys, places=2)

    def test_achromatic_doublet_creation(self):
        doublet = create_doublet(focal_length=100, diameter=50)
        
        f_sys = doublet.get_system_focal_length()
        self.assertIsNotNone(f_sys)
        # It's an approximation, so allow some error margin (e.g. 10%)
        self.assertTrue(90 < f_sys < 110, f"Expected ~100mm, got {f_sys}")

    def test_chromatic_aberration(self):
        doublet = create_doublet(focal_length=100, diameter=50)
        chrom = doublet.calculate_chromatic_aberration()
        
        self.assertIn('longitudinal', chrom)
        self.assertIn('corrected', chrom)
        
        # Should be corrected (achromatic)
        self.assertTrue(chrom['corrected'])
        self.assertLess(chrom['longitudinal'], 1.0) # Arbitrary small threshold

    def test_triplet_creation(self):
        triplet = create_triplet(focal_length=100, diameter=50)
        
        self.assertEqual(len(triplet.elements), 3)
        self.assertEqual(len(triplet.air_gaps), 2)
        
        f_sys = triplet.get_system_focal_length()
        self.assertIsNotNone(f_sys)
        # Allow wider margin for triplet approximation
        self.assertTrue(50 < f_sys < 150, f"Expected ~100mm, got {f_sys}")

    def test_serialization(self):
        system = OpticalSystem(name="SaveLoadTest")
        system.add_lens(self.lens1)
        system.add_lens(self.lens2, air_gap_before=5.0)
        
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as tmp:
            tmp_path = tmp.name
        
        try:
            system.save(tmp_path)
            
            # Load back
            loaded_sys = OpticalSystem.load(tmp_path)
            
            self.assertEqual(loaded_sys.name, system.name)
            self.assertEqual(len(loaded_sys.elements), len(system.elements))
            self.assertEqual(len(loaded_sys.air_gaps), len(system.air_gaps))
            
            # Check element details
            self.assertEqual(loaded_sys.elements[0].lens.name, system.elements[0].lens.name)
            self.assertEqual(loaded_sys.air_gaps[0].thickness, system.air_gaps[0].thickness)
            
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_update_positions(self):
        system = OpticalSystem()
        system.add_lens(self.lens1) # 10mm thick
        system.add_lens(self.lens2, air_gap_before=5.0) # 8mm thick
        
        # Initial checks
        self.assertEqual(system.elements[0].position, 0.0)
        self.assertEqual(system.elements[1].position, 15.0) # 0 + 10 + 5
        
        # Modify gap
        system.air_gaps[0].thickness = 10.0
        system._update_positions()
        
        self.assertEqual(system.elements[1].position, 20.0) # 0 + 10 + 10

if __name__ == '__main__':
    unittest.main()
