import unittest
import os
import tempfile
from src.io.step_export import StepExporter
from src.lens import Lens

class TestStepExport(unittest.TestCase):
    def setUp(self):
        self.lens = Lens(
            name="Test Lens",
            radius_of_curvature_1=100.0,
            radius_of_curvature_2=-100.0,
            thickness=10.0,
            diameter=50.0,
            refractive_index=1.5
        )
        self.temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.step')
        self.temp_file.close()

    def tearDown(self):
        if os.path.exists(self.temp_file.name):
            os.remove(self.temp_file.name)

    def test_step_generation(self):
        """Test that STEP file is generated with expected headers and entities."""
        exporter = StepExporter(self.lens)
        exporter.export(self.temp_file.name)
        
        with open(self.temp_file.name, 'r') as f:
            content = f.read()
            
        # Check Header
        self.assertIn("ISO-10303-21;", content)
        self.assertIn("FILE_SCHEMA(('AUTOMOTIVE_DESIGN", content)
        
        # Check Entities
        self.assertIn("MANIFOLD_SOLID_BREP", content)
        self.assertIn("CLOSED_SHELL", content)
        self.assertIn("ADVANCED_FACE", content)
        self.assertIn("CARTESIAN_POINT", content)
        self.assertIn("Test Lens", content)
        
    def test_flat_surface_handling(self):
        """Test lens with flat surface (Plano-Convex)."""
        self.lens.radius_of_curvature_1 = 99999.0 # Effectively flat
        exporter = StepExporter(self.lens)
        exporter.export(self.temp_file.name)
        
        with open(self.temp_file.name, 'r') as f:
            content = f.read()
            
        self.assertIn("PLANE", content)

if __name__ == '__main__':
    unittest.main()
