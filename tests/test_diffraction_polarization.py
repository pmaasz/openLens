"""
Functional tests for diffraction and polarization modules
"""

import unittest
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Try to import numpy
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

if NUMPY_AVAILABLE:
    from diffraction import DiffractionCalculator
    from polarization import (PolarizationCalculator, PolarizationState, 
                              JonesMatrices)


@unittest.skipUnless(NUMPY_AVAILABLE, "requires numpy")
class TestDiffraction(unittest.TestCase):
    """Test diffraction calculations"""
    
    def setUp(self):
        self.calc = DiffractionCalculator(wavelength=550e-9)
        self.focal_length = 50.0  # mm
        self.aperture = 25.0  # mm
    
    def test_airy_disk_radius(self):
        """Test Airy disk radius calculation"""
        radius = self.calc.airy_disk_radius(self.focal_length, self.aperture)
        
        # Should be positive
        self.assertGreater(radius, 0)
        
        # Should be in reasonable range (micrometers)
        self.assertGreater(radius, 0.1)
        self.assertLess(radius, 100)
        
        # Expected value check (1.22 * λ * f / D)
        expected = 1.22 * 550e-9 * 0.05 / 0.025 * 1e6
        self.assertAlmostEqual(radius, expected, places=2)
    
    def test_rayleigh_criterion(self):
        """Test Rayleigh diffraction limit"""
        resolution = self.calc.rayleigh_criterion(self.aperture)
        
        # Should be positive
        self.assertGreater(resolution, 0)
        
        # Should be in reasonable range (arcseconds)
        self.assertGreater(resolution, 0.01)
        self.assertLess(resolution, 100)
    
    def test_diffraction_spot_size(self):
        """Test diffraction-limited spot size"""
        f_number = 2.0
        spot = self.calc.diffraction_limited_spot_size(f_number)
        
        # Should be positive
        self.assertGreater(spot, 0)
        
        # Should scale with f-number
        spot_f4 = self.calc.diffraction_limited_spot_size(4.0)
        self.assertAlmostEqual(spot_f4 / spot, 2.0, places=1)
    
    def test_numerical_aperture_resolution(self):
        """Test NA-based resolution"""
        na = 0.5
        resolution = self.calc.numerical_aperture_resolution(na)
        
        # Should be positive
        self.assertGreater(resolution, 0)
        
        # Higher NA should give better resolution (smaller value)
        resolution_high_na = self.calc.numerical_aperture_resolution(0.9)
        self.assertLess(resolution_high_na, resolution)
    
    def test_airy_pattern(self):
        """Test Airy pattern calculation"""
        radius = 10.0  # micrometers
        r, intensity = self.calc.airy_pattern(radius, self.focal_length, 
                                             self.aperture, num_points=100)
        
        # Check array lengths
        self.assertEqual(len(r), 100)
        self.assertEqual(len(intensity), 100)
        
        # Check normalization
        self.assertAlmostEqual(np.max(intensity), 1.0, places=5)
        
        # Center should be maximum
        self.assertEqual(intensity[0], np.max(intensity))
        
        # Intensity should decay
        self.assertLess(intensity[-1], intensity[0])
    
    def test_point_spread_function_2d(self):
        """Test 2D PSF calculation"""
        size = 20.0  # micrometers
        pixels = 65  # Use odd number for true center pixel
        
        psf = self.calc.point_spread_function_2d(size, self.focal_length,
                                                 self.aperture, pixels=pixels)
        
        # Check shape
        self.assertEqual(psf.shape, (pixels, pixels))
        
        # Check normalization
        self.assertAlmostEqual(np.max(psf), 1.0, places=5)
        
        # Center should be maximum
        center = pixels // 2
        max_idx = np.unravel_index(np.argmax(psf), psf.shape)
        # Max should be at center
        self.assertEqual(max_idx[0], center)
        self.assertEqual(max_idx[1], center)
        
        # Should be symmetric
        self.assertAlmostEqual(psf[center, center+1], psf[center, center-1], places=3)
        self.assertAlmostEqual(psf[center+1, center], psf[center-1, center], places=3)
    
    def test_encircled_energy(self):
        """Test encircled energy calculation"""
        r, encircled = self.calc.encircled_energy(self.focal_length, self.aperture)
        
        # Check lengths
        self.assertGreater(len(r), 0)
        self.assertEqual(len(r), len(encircled))
        
        # Should be monotonically increasing
        for i in range(1, len(encircled)):
            self.assertGreaterEqual(encircled[i], encircled[i-1])
        
        # Should start near 0 and end near 1
        self.assertLess(encircled[0], 0.1)
        self.assertGreater(encircled[-1], 0.95)
        
        # Airy disk should contain ~84% of energy
        airy_r = self.calc.airy_disk_radius(self.focal_length, self.aperture)
        idx = np.argmin(np.abs(r - airy_r))
        self.assertGreater(encircled[idx], 0.75)
        self.assertLess(encircled[idx], 0.90)
    
    def test_calculate_metrics(self):
        """Test comprehensive metrics calculation"""
        metrics = self.calc.calculate_metrics(self.focal_length, self.aperture)
        
        # Check all expected keys
        expected_keys = ['airy_disk_radius_um', 'rayleigh_limit_arcsec',
                        'diffraction_spot_um', 'f_number', 'wavelength_nm']
        for key in expected_keys:
            self.assertIn(key, metrics)
        
        # Check values are reasonable
        self.assertGreater(metrics['airy_disk_radius_um'], 0)
        self.assertGreater(metrics['rayleigh_limit_arcsec'], 0)
        self.assertGreater(metrics['diffraction_spot_um'], 0)
        self.assertEqual(metrics['f_number'], self.focal_length / self.aperture)
        self.assertEqual(metrics['wavelength_nm'], 550)
    
    def test_wavelength_dependence(self):
        """Test wavelength dependence of diffraction"""
        # Red light (longer wavelength)
        calc_red = DiffractionCalculator(wavelength=650e-9)
        radius_red = calc_red.airy_disk_radius(self.focal_length, self.aperture)
        
        # Blue light (shorter wavelength)
        calc_blue = DiffractionCalculator(wavelength=450e-9)
        radius_blue = calc_blue.airy_disk_radius(self.focal_length, self.aperture)
        
        # Red should have larger Airy disk
        self.assertGreater(radius_red, radius_blue)
        
        # Ratio should be approximately wavelength ratio
        ratio = radius_red / radius_blue
        wavelength_ratio = 650 / 450
        self.assertAlmostEqual(ratio, wavelength_ratio, places=1)


@unittest.skipUnless(NUMPY_AVAILABLE, "requires numpy")
class TestPolarization(unittest.TestCase):
    """Test polarization calculations"""
    
    def setUp(self):
        self.calc = PolarizationCalculator()
    
    def test_polarization_states(self):
        """Test polarization state creation"""
        # Horizontal
        h = PolarizationState.linear_horizontal()
        self.assertAlmostEqual(np.abs(h.jones_vector[0]), 1.0)
        self.assertAlmostEqual(np.abs(h.jones_vector[1]), 0.0)
        
        # Vertical
        v = PolarizationState.linear_vertical()
        self.assertAlmostEqual(np.abs(v.jones_vector[0]), 0.0)
        self.assertAlmostEqual(np.abs(v.jones_vector[1]), 1.0)
        
        # 45 degrees
        pol_45 = PolarizationState.linear_45()
        self.assertAlmostEqual(np.abs(pol_45.jones_vector[0]), 1/np.sqrt(2))
        self.assertAlmostEqual(np.abs(pol_45.jones_vector[1]), 1/np.sqrt(2))
        
        # Circular
        circ_r = PolarizationState.circular_right()
        self.assertAlmostEqual(circ_r.intensity(), 1.0)
    
    def test_intensity_conservation(self):
        """Test that intensity is conserved through transformations"""
        state = PolarizationState.linear_horizontal()
        initial_intensity = state.intensity()
        
        # Through rotator
        rotator = JonesMatrices.rotator(30)
        state_rot = state.apply_matrix(rotator)
        self.assertAlmostEqual(state_rot.intensity(), initial_intensity, places=5)
        
        # Through retarder
        retarder = JonesMatrices.quarter_wave_plate(0)
        state_ret = state.apply_matrix(retarder)
        self.assertAlmostEqual(state_ret.intensity(), initial_intensity, places=5)
    
    def test_brewster_angle(self):
        """Test Brewster angle calculation"""
        n1 = 1.0  # air
        n2 = 1.5  # glass
        
        brewster = self.calc.brewster_angle(n1, n2)
        
        # Should be between 0 and 90
        self.assertGreater(brewster, 0)
        self.assertLess(brewster, 90)
        
        # Expected value: arctan(1.5/1.0) = 56.31°
        self.assertAlmostEqual(brewster, 56.31, places=1)
    
    def test_fresnel_coefficients(self):
        """Test Fresnel coefficient calculation"""
        n1 = 1.0
        n2 = 1.5
        angle = 0.0  # Normal incidence
        
        coeffs = self.calc.fresnel_coefficients(n1, n2, angle)
        
        # At normal incidence, |r_s| = |r_p| (magnitudes are equal)
        self.assertAlmostEqual(np.abs(coeffs['r_s']), np.abs(coeffs['r_p']), places=5)
        
        # Check expected value at normal incidence: r = (n1-n2)/(n1+n2)
        expected_r = (n1 - n2) / (n1 + n2)
        self.assertAlmostEqual(np.abs(coeffs['r_s']), np.abs(expected_r), places=5)
    
    def test_brewster_angle_no_p_reflection(self):
        """Test that p-polarization has zero reflection at Brewster angle"""
        n1 = 1.0
        n2 = 1.5
        
        brewster = self.calc.brewster_angle(n1, n2)
        coeffs = self.calc.fresnel_coefficients(n1, n2, brewster)
        
        # r_p should be zero at Brewster angle
        self.assertAlmostEqual(np.abs(coeffs['r_p']), 0.0, places=3)
        
        # r_s should be non-zero
        self.assertGreater(np.abs(coeffs['r_s']), 0.01)
    
    def test_total_internal_reflection(self):
        """Test total internal reflection"""
        n1 = 1.5  # glass
        n2 = 1.0  # air
        
        # Calculate critical angle
        critical_angle = np.degrees(np.arcsin(n2 / n1))
        
        # Above critical angle should have TIR
        angle = critical_angle + 5
        coeffs = self.calc.fresnel_coefficients(n1, n2, angle)
        
        self.assertTrue(coeffs['total_internal_reflection'])
        self.assertAlmostEqual(np.abs(coeffs['r_s']), 1.0)
        self.assertAlmostEqual(np.abs(coeffs['r_p']), 1.0)
    
    def test_energy_conservation(self):
        """Test that R + T = 1 (energy conservation)"""
        n1 = 1.0
        n2 = 1.5
        angle = 30.0
        
        rt = self.calc.reflectance_transmittance(n1, n2, angle)
        
        # For s-polarization
        self.assertAlmostEqual(rt['R_s'] + rt['T_s'], 1.0, places=5)
        
        # For p-polarization
        self.assertAlmostEqual(rt['R_p'] + rt['T_p'], 1.0, places=5)
    
    def test_malus_law(self):
        """Test Malus' law"""
        intensity = 1.0
        
        # Parallel polarizers (0°) should transmit all
        transmitted_0 = self.calc.malus_law(intensity, 0)
        self.assertAlmostEqual(transmitted_0, intensity, places=5)
        
        # Perpendicular polarizers (90°) should transmit nothing
        transmitted_90 = self.calc.malus_law(intensity, 90)
        self.assertAlmostEqual(transmitted_90, 0.0, places=5)
        
        # 45° should transmit 50%
        transmitted_45 = self.calc.malus_law(intensity, 45)
        self.assertAlmostEqual(transmitted_45, 0.5, places=5)
    
    def test_jones_matrices_unitary(self):
        """Test that Jones matrices preserve intensity"""
        state = PolarizationState.linear_horizontal()
        initial_intensity = state.intensity()
        
        # Rotator
        rotator = JonesMatrices.rotator(45)
        state_rot = state.apply_matrix(rotator)
        self.assertAlmostEqual(state_rot.intensity(), initial_intensity, places=5)
        
        # QWP
        qwp = JonesMatrices.quarter_wave_plate(0)
        state_qwp = state.apply_matrix(qwp)
        self.assertAlmostEqual(state_qwp.intensity(), initial_intensity, places=5)
        
        # HWP
        hwp = JonesMatrices.half_wave_plate(0)
        state_hwp = state.apply_matrix(hwp)
        self.assertAlmostEqual(state_hwp.intensity(), initial_intensity, places=5)
    
    def test_qwp_linear_to_circular(self):
        """Test quarter-wave plate converts linear to circular"""
        # Horizontal linear at 45° to QWP fast axis
        h = PolarizationState.linear_horizontal()
        qwp = JonesMatrices.quarter_wave_plate(45)
        
        # Should produce circular
        circular = h.apply_matrix(qwp)
        stokes = circular.stokes_parameters()
        
        # S3 (circularity) should be non-zero for circular polarization
        # S1 and S2 should be small for circular
        self.assertLess(np.abs(stokes[1]), 0.1)  # S1 ≈ 0
        self.assertLess(np.abs(stokes[2]), 0.1)  # S2 ≈ 0
        self.assertGreater(np.abs(stokes[3]), 0.9)  # S3 ≈ ±1
    
    def test_hwp_rotation(self):
        """Test half-wave plate rotates polarization by 2θ"""
        # Horizontal polarization
        h = PolarizationState.linear_horizontal()
        
        # HWP at 22.5° should rotate to 45°
        hwp = JonesMatrices.half_wave_plate(22.5)
        rotated = h.apply_matrix(hwp)
        
        # Check if it's at 45°
        self.assertAlmostEqual(np.abs(rotated.jones_vector[0]), 
                              np.abs(rotated.jones_vector[1]), places=3)
    
    def test_polarizer(self):
        """Test linear polarizer"""
        # Unpolarized approximation (average of H and V)
        h = PolarizationState.linear_horizontal()
        v = PolarizationState.linear_vertical()
        
        # Horizontal polarizer should pass H, block V
        pol_h = JonesMatrices.linear_polarizer(0)
        
        h_after = h.apply_matrix(pol_h)
        v_after = v.apply_matrix(pol_h)
        
        # H should pass through (intensity preserved)
        self.assertAlmostEqual(h_after.intensity(), h.intensity(), places=5)
        
        # V should be blocked (zero intensity)
        self.assertAlmostEqual(v_after.intensity(), 0.0, places=5)
    
    def test_stokes_parameters(self):
        """Test Stokes parameters calculation"""
        # Horizontal linear: [1, 1, 0, 0]
        h = PolarizationState.linear_horizontal()
        stokes_h = h.stokes_parameters()
        self.assertAlmostEqual(stokes_h[0], 1.0, places=5)
        self.assertAlmostEqual(stokes_h[1], 1.0, places=5)
        self.assertAlmostEqual(stokes_h[2], 0.0, places=5)
        self.assertAlmostEqual(stokes_h[3], 0.0, places=5)
        
        # Vertical linear: [1, -1, 0, 0]
        v = PolarizationState.linear_vertical()
        stokes_v = v.stokes_parameters()
        self.assertAlmostEqual(stokes_v[0], 1.0, places=5)
        self.assertAlmostEqual(stokes_v[1], -1.0, places=5)
        self.assertAlmostEqual(stokes_v[2], 0.0, places=5)
        self.assertAlmostEqual(stokes_v[3], 0.0, places=5)
        
        # Right circular: [1, 0, 0, ±1] (sign depends on convention)
        circ_r = PolarizationState.circular_right()
        stokes_r = circ_r.stokes_parameters()
        self.assertAlmostEqual(stokes_r[0], 1.0, places=5)
        self.assertAlmostEqual(stokes_r[1], 0.0, places=5)
        self.assertAlmostEqual(stokes_r[2], 0.0, places=5)
        self.assertAlmostEqual(np.abs(stokes_r[3]), 1.0, places=5)  # Check magnitude
    
    def test_birefringence_retardance(self):
        """Test birefringence retardance calculation"""
        delta_n = 0.01  # Typical for quartz
        thickness = 0.5  # mm
        wavelength = 550  # nm
        
        retardance = self.calc.birefringence_retardance(delta_n, thickness, wavelength)
        
        # Should be positive
        self.assertGreater(retardance, 0)
        
        # Should be periodic in 360°
        self.assertAlmostEqual(retardance % 360, retardance)


@unittest.skipUnless(NUMPY_AVAILABLE, "requires numpy")
class TestDiffractionPolarizationIntegration(unittest.TestCase):
    """Test integration between diffraction and polarization"""
    
    def test_combined_analysis(self):
        """Test that both modules can work together"""
        # Diffraction analysis
        diff_calc = DiffractionCalculator(wavelength=550e-9)
        focal_length = 50.0
        aperture = 25.0
        
        diff_metrics = diff_calc.calculate_metrics(focal_length, aperture)
        
        # Polarization analysis
        pol_calc = PolarizationCalculator()
        n1 = 1.0
        n2 = 1.5
        
        brewster = pol_calc.brewster_angle(n1, n2)
        
        # Both should produce valid results
        self.assertGreater(diff_metrics['airy_disk_radius_um'], 0)
        self.assertGreater(brewster, 0)


if __name__ == '__main__':
    print("Running Diffraction and Polarization Tests...\n")
    unittest.main(verbosity=2)
