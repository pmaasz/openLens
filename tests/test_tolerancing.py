
import unittest
import sys
import os

# Add src to path
sys.path.append(os.path.abspath('src'))

from tolerancing import MonteCarloAnalyzer, ToleranceOperand, ToleranceType, InverseSensitivityAnalyzer, generate_yield_report
from optical_system import OpticalSystem
from lens import Lens

class TestTolerancing(unittest.TestCase):
    def setUp(self):
        # Create a simple system
        self.sys = OpticalSystem("Test System")
        self.l1 = Lens("L1", radius_of_curvature_1=100.0, radius_of_curvature_2=-100.0, thickness=5.0, diameter=25.0, material="BK7", wavelength_nm=587.6)
        self.sys.add_lens(self.l1)
        
    def test_tolerance_generation(self):
        # Test Uniform
        tol = ToleranceOperand(0, ToleranceType.RADIUS_1, -1.0, 1.0, distribution="uniform")
        val = tol.generate_value()
        self.assertTrue(-1.0 <= val <= 1.0)
        
        # Test Gaussian
        tol_g = ToleranceOperand(0, ToleranceType.RADIUS_1, -1.0, 1.0, distribution="gaussian", std_dev=0.1)
        val = tol_g.generate_value()
        # High probability of being within range, but theoretically unbounded (though clipped in code)
        self.assertTrue(-1.0 <= val <= 1.0)

    def test_monte_carlo_run(self):
        # Define tolerances
        tols = [
            ToleranceOperand(0, ToleranceType.RADIUS_1, -1.0, 1.0), # +/- 1mm on R1
            ToleranceOperand(0, ToleranceType.THICKNESS, -0.1, 0.1) # +/- 0.1mm on Thickness
        ]
        
        mc = MonteCarloAnalyzer(self.sys, tols, seed=42)
        
        # Run small MC
        stats = mc.run(num_trials=10, criterion='rms_spot_radius', criterion_limit=1.0)
        
        self.assertEqual(stats['trials'], 10)
        self.assertIn('nominal', stats)
        self.assertIn('yield', stats)
        
        # Verify perturbations were applied (check first result)
        res0 = mc.results[0]
        self.assertIn('El_0_RADIUS_1', res0['perturbations'])
        self.assertIn('El_0_THICKNESS', res0['perturbations'])
        
        # Verify mean is reasonable (nominal R1=100)
        # We can't easily verify the exact value without mocking random, 
        # but we can check the stats structure is populated.
        self.assertTrue(stats['mean'] >= 0)
        
        # Test report generation
        report = generate_yield_report(stats)
        self.assertIn("=== Monte Carlo Yield Analysis ===", report)
        self.assertIn("ESTIMATED YIELD:", report)


class TestInverseSensitivity(unittest.TestCase):
    def setUp(self):
        # Create a simple system
        self.sys = OpticalSystem("Test System")
        # Use a biconvex lens where changing R1 definitely affects spot size
        self.l1 = Lens("L1", radius_of_curvature_1=50.0, radius_of_curvature_2=-50.0, thickness=5.0, diameter=25.0, material="BK7", wavelength_nm=587.6)
        self.sys.add_lens(self.l1)

    def test_sensitivity_calculation(self):
        # Define tolerances with large enough values to cause change
        tols = [
            ToleranceOperand(0, ToleranceType.RADIUS_1, -1.0, 1.0), 
            ToleranceOperand(0, ToleranceType.THICKNESS, -0.5, 0.5) 
        ]
        
        analyzer = InverseSensitivityAnalyzer(self.sys, tols)
        sensitivities = analyzer.calculate_sensitivities()
        
        self.assertEqual(len(sensitivities), 2)
        
        # Check first operand (Radius 1)
        s0 = sensitivities[0]
        self.assertEqual(s0['type'], 'RADIUS_1')
        self.assertEqual(s0['test_value'], 1.0)
        # Sensitivity should not be zero (unless system is insensitive, which is unlikely for R1)
        # We can't guarantee exact values without precise optical math, but it should run.
        self.assertIn('sensitivity', s0)

    def test_optimize_limits(self):
        # Define tolerances
        tols = [
            ToleranceOperand(0, ToleranceType.RADIUS_1, -1.0, 1.0),
            ToleranceOperand(0, ToleranceType.THICKNESS, -0.5, 0.5)
        ]
        
        analyzer = InverseSensitivityAnalyzer(self.sys, tols)
        
        # Target degradation: 0.01 rms spot
        # Original sensitivity check:
        # If R1 changes by 1.0, spot might change by X.
        # If X > 0.01, we expect the new limit to be < 1.0.
        
        new_tols = analyzer.optimize_limits(target_yield_criterion=0.01, method='rss')
        
        self.assertEqual(len(new_tols), 2)
        
        # Check if new limits are different from old ones (implies optimization happened)
        # Note: If sensitivity is 0, limit stays same. But R1 should have sensitivity.
        self.assertNotEqual(new_tols[0].max_val, 1.0)
        
        # Check that min/max are symmetric as per current implementation
        self.assertEqual(new_tols[0].min_val, -new_tols[0].max_val)



if __name__ == '__main__':
    unittest.main()
