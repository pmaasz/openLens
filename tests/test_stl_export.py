import unittest
import os
import struct
import sys

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.lens import Lens
from src.stl_export import export_lens_stl, STLExporter

class TestSTLExport(unittest.TestCase):
    def setUp(self):
        self.filename = "test_lens_output.stl"
        self.lens = Lens(
            radius_of_curvature_1=50.0,
            radius_of_curvature_2=-50.0,
            thickness=10.0,
            diameter=25.0,
            refractive_index=1.5
        )

    def tearDown(self):
        if os.path.exists(self.filename):
            os.remove(self.filename)

    def test_export_creates_file(self):
        """Test that export creates a valid file"""
        count = export_lens_stl(self.lens, self.filename, resolution=10)
        
        self.assertTrue(os.path.exists(self.filename))
        self.assertGreater(count, 0)
        
        # Check file size
        # Header (80) + Count (4) + Triangles (50 * count)
        expected_size = 84 + 50 * count
        self.assertEqual(os.path.getsize(self.filename), expected_size)
        
    def test_export_flat_surfaces(self):
        """Test export with flat surfaces"""
        flat_lens = Lens(
            radius_of_curvature_1=1e9, # Flat
            radius_of_curvature_2=1e9, # Flat
            thickness=5.0,
            diameter=20.0,
            refractive_index=1.5
        )
        count = export_lens_stl(flat_lens, self.filename, resolution=10)
        self.assertGreater(count, 0)
        
    def test_geometry_consistency(self):
        """Test that generated triangles are valid (normals not zero)"""
        exporter = STLExporter()
        exporter.export_lens_to_stl(50, -50, 10, 25, self.filename, resolution=5)
        
        # Manually check a few triangles
        for tri in exporter.triangles:
            p1, p2, p3 = tri
            # Check for degenerate triangles
            self.assertNotEqual(p1, p2)
            self.assertNotEqual(p1, p3)
            self.assertNotEqual(p2, p3)

if __name__ == '__main__':
    unittest.main()
