import unittest
import sys
import os
import math

# Add src to path
sys.path.append(os.path.abspath('src'))

from analysis.environmental import EnvironmentalAnalyzer
from optical_system import OpticalSystem
from lens import Lens
from material_database import get_material_database, MaterialProperties

class TestEnvironmental(unittest.TestCase):
    def setUp(self):
        self.sys = OpticalSystem("Env Test System")
        # Use BK7 which has full definitions
        self.lens = Lens(
            name="L1",
            radius_of_curvature_1=100.0,
            radius_of_curvature_2=-100.0,
            thickness=10.0,
            material="BK7",
            refractive_index=1.5168
        )
        self.sys.add_lens(self.lens)
        
    def test_air_index(self):
        # Test Edlen equation
        # STP: 20C, 1atm (approx STP for optics)
        # 587.6 nm (d-line)
        n_air = EnvironmentalAnalyzer.calculate_air_index(587.6, temperature_c=20.0, pressure_atm=1.0)
        
        # Expect ~1.00027
        self.assertAlmostEqual(n_air, 1.00027, places=4)
        
        # Test Temperature dependence (Hotter -> Less dense -> Lower index)
        n_hot = EnvironmentalAnalyzer.calculate_air_index(587.6, temperature_c=100.0, pressure_atm=1.0)
        self.assertLess(n_hot, n_air)
        
        # Test Pressure dependence (Higher P -> More dense -> Higher index)
        n_high_p = EnvironmentalAnalyzer.calculate_air_index(587.6, temperature_c=20.0, pressure_atm=2.0)
        self.assertGreater(n_high_p, n_air)

    def test_thermal_expansion(self):
        # Apply 120C (+100C delta from 20C)
        # BK7 CTE = 7.1e-6
        # Scaling = 1 + 7.1e-6 * 100 = 1 + 7.1e-4 = 1.00071
        
        new_sys = EnvironmentalAnalyzer.apply_environment(self.sys, temperature_c=120.0, pressure_atm=1.0)
        new_lens = new_sys.elements[0].lens
        
        expected_scaling = 1.0 + 7.1e-6 * 100
        
        self.assertAlmostEqual(new_lens.radius_of_curvature_1, 100.0 * expected_scaling, places=4)
        self.assertAlmostEqual(new_lens.thickness, 10.0 * expected_scaling, places=4)
        
    def test_pressure_effect_on_index(self):
        # Nominal system at 1atm
        # New system at 2atm
        # Glass index (relative) should decrease because air index increases
        # n_glass_rel = n_glass_abs / n_air_abs
        
        new_sys = EnvironmentalAnalyzer.apply_environment(self.sys, temperature_c=20.0, pressure_atm=2.0)
        new_lens = new_sys.elements[0].lens
        
        # Calculate expected change
        n_air_1 = EnvironmentalAnalyzer.calculate_air_index(587.6, temperature_c=20.0, pressure_atm=1.0)
        n_air_2 = EnvironmentalAnalyzer.calculate_air_index(587.6, temperature_c=20.0, pressure_atm=2.0)
        
        # Original index (relative to 1atm air)
        # BK7 nd = 1.5168
        n_orig = 1.5168 
        
        # Expected new index (relative to 2atm air)
        # n_new = n_orig * (n_air_1 / n_air_2)
        expected_n = n_orig * (n_air_1 / n_air_2)
        
        # Need to allow some tolerance because get_refractive_index recalculates exactly from Sellmeier
        # whereas n_orig is just nominal nd.
        # But wait, EnvironmentalAnalyzer calls get_refractive_index first to get n_rel_T.
        # So it uses the calculated value, not hardcoded 1.5168.
        # Let's verify against the calculated value.
        
        db = get_material_database()
        n_calc_orig = db.get_refractive_index("BK7", 587.6, 20.0)
        expected_n = n_calc_orig * (n_air_1 / n_air_2)
        
        self.assertAlmostEqual(new_lens.refractive_index, expected_n, places=5)
        self.assertLess(new_lens.refractive_index, n_calc_orig)

    def test_air_gap_expansion(self):
        # Add a second lens with air gap
        # Material BK7
        l2 = Lens("L2", radius_of_curvature_1=50, thickness=5, material="BK7")
        self.sys.add_lens(l2, air_gap_before=10.0)
        
        # Apply +100C
        # Housing CTE assumed ~23.6e-6 (Aluminum)
        # Scaling = 1 + 23.6e-6 * 100 = 1.00236
        
        new_sys = EnvironmentalAnalyzer.apply_environment(self.sys, temperature_c=120.0, pressure_atm=1.0)
        
        # Check gap
        gap = new_sys.air_gaps[0]
        expected_gap = 10.0 * (1.0 + 23.6e-6 * 100)
        
        self.assertAlmostEqual(gap.thickness, expected_gap, places=5)
        
        # Check if positions updated correctly
        # Pos1 = 0
        # Pos2 = Thickness1 + Gap
        # Thickness1 also expanded (BK7 CTE)
        
        l1_cte = 7.1e-6
        l1_thick_new = 10.0 * (1.0 + l1_cte * 100)
        expected_pos2 = l1_thick_new + expected_gap
        
        self.assertAlmostEqual(new_sys.elements[1].position, expected_pos2, places=4)

if __name__ == '__main__':
    unittest.main()
