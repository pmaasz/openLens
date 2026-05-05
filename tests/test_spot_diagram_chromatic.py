
import unittest
import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.optical_system import OpticalSystem
from src.lens import Lens
from src.analysis import SpotDiagram
from src.constants import WAVELENGTH_F_LINE, WAVELENGTH_D_LINE, WAVELENGTH_C_LINE

# Mock material database for testing
try:
    from src.material_database import get_material_database
    HAS_DB = True
except ImportError:
    HAS_DB = False

class TestSpotDiagramChromatic(unittest.TestCase):
    def setUp(self):
        # Create a simple singlet
        # Using BK7 explicitly if possible, otherwise generic
        if HAS_DB:
            self.lens = Lens(radius_of_curvature_1=50.0, radius_of_curvature_2=-50.0, 
                             thickness=5.0, diameter=20.0, material="BK7")
        else:
            self.lens = Lens(radius_of_curvature_1=50.0, radius_of_curvature_2=-50.0, 
                             thickness=5.0, diameter=20.0, refractive_index=1.5168)
            
        self.system = OpticalSystem("Test System")
        self.system.add_lens(self.lens, air_gap_before=0.0)
        self.analyzer = SpotDiagram(self.system)

    def test_chromatic_update(self):
        """Test that trace_spot updates lens indices for different wavelengths"""
        # Manually update to F-line (blue)
        self.lens.update_refractive_index(wavelength_nm=WAVELENGTH_F_LINE)
        n_F = self.lens.refractive_index
        
        self.lens.update_refractive_index(wavelength_nm=WAVELENGTH_C_LINE)
        n_C = self.lens.refractive_index
        
        self.assertNotAlmostEqual(n_F, n_C)
        
        # Reset to green
        self.lens.update_refractive_index(wavelength_nm=WAVELENGTH_D_LINE)
        
        # Now trace through analyzer and check if results differ by wavelength
        res_F = self.analyzer.trace_spot(wavelength_nm=WAVELENGTH_F_LINE, num_rings=3)
        res_C = self.analyzer.trace_spot(wavelength_nm=WAVELENGTH_C_LINE, num_rings=3)
        
        # If dispersion is working, the focal points (and thus spot sizes at a fixed plane) should differ
        # Or specifically, the rays should have different paths.
        
        # Let's check the ray endpoints relative to paraxial focus of d-line
        # trace_spot automatically finds the "best" focus for that wavelength if image_plane_x is None.
        # So image_plane_x should differ due to longitudinal chromatic aberration.
        
        plane_F = res_F['image_plane_x']
        plane_C = res_C['image_plane_x']
        
        # For a positive singlet, Blue focus is shorter than Red focus
        # f_blue < f_red => plane_F < plane_C
        
        self.assertLess(plane_F, plane_C, "Blue focus should be shorter than Red focus for singlet")
        
        # Also verify that the lens state was restored
        self.assertEqual(self.lens.wavelength, 587.6, "Lens wavelength should be restored")
        # approximate check for refractive index restoration
        self.assertAlmostEqual(self.lens.refractive_index, 1.5168, places=3, msg="Lens refractive index should be restored")

if __name__ == '__main__':
    unittest.main()
