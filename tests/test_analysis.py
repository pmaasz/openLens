import unittest
import math
import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.analysis import SpotDiagram
from src.optical_system import OpticalSystem, create_doublet
from src.lens import Lens
from src.constants import NM_TO_MM

class TestSpotDiagram(unittest.TestCase):
    def setUp(self):
        # Create a simple singlet system (perfect paraxial lens approx)
        self.lens = Lens(
            radius_of_curvature_1=100.0,
            radius_of_curvature_2=-100.0,
            thickness=5.0,
            diameter=25.0,
            refractive_index=1.5
        )
        self.system = OpticalSystem()
        self.system.add_lens(self.lens)
        
        self.spot = SpotDiagram(self.system)
        
    def test_hexapolar_grid(self):
        """Test hexapolar grid generation"""
        points = self.spot.generate_hexapolar_grid(rings=2, diameter=10.0)
        # Expected points: 1 (center) + 6 (ring 1) + 12 (ring 2) = 19
        self.assertEqual(len(points), 19)
        
        # Check center
        self.assertEqual(points[0], (0.0, 0.0))
        
        # Check radius of last point (should be on the edge radius 5.0)
        # The points are generated in order of rings
        last_pt = points[-1]
        dist = math.sqrt(last_pt[0]**2 + last_pt[1]**2)
        self.assertAlmostEqual(dist, 5.0, places=4)
        
    def test_on_axis_spot(self):
        """Test on-axis spot diagram"""
        results = self.spot.trace_spot(field_angle_x_deg=0, field_angle_y_deg=0, num_rings=3)
        
        # For a symmetric lens on axis, centroid should be at (0,0)
        cent_y, cent_z = results['centroid']
        self.assertAlmostEqual(cent_y, 0.0, places=3)
        self.assertAlmostEqual(cent_z, 0.0, places=3)
        
        # RMS radius should be small (but not zero due to spherical aberration)
        self.assertGreater(results['rms_radius'], 0.0)
        self.assertLess(results['rms_radius'], 0.3) # Expect decent focus (RMS ~0.24)
        
    def test_defocus(self):
        """Test that spot size increases with defocus"""
        # Best focus
        res_focus = self.spot.trace_spot(focus_shift_mm=0.0)
        
        # Defocus by 1mm
        res_defocus = self.spot.trace_spot(focus_shift_mm=1.0)
        
        self.assertGreater(res_defocus['rms_radius'], res_focus['rms_radius'])
        
    def test_off_axis_spot(self):
        """Test off-axis spot diagram"""
        # 5 degrees off-axis in Y
        results = self.spot.trace_spot(field_angle_y_deg=5.0, num_rings=3)
        
        # Centroid should be shifted in Y
        cent_y, cent_z = results['centroid']
        self.assertNotAlmostEqual(cent_y, 0.0)
        self.assertAlmostEqual(cent_z, 0.0, places=3) # Symmetry in Z preserved
        
        # RMS should likely be worse than on-axis due to coma/astigmatism
        on_axis = self.spot.trace_spot(field_angle_y_deg=0.0, num_rings=3)
        self.assertGreater(results['rms_radius'], on_axis['rms_radius'])

if __name__ == '__main__':
    unittest.main()
