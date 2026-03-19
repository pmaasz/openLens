import unittest
import os
import sys

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.optical_system import OpticalSystem
from src.lens import Lens
from src.io.export import ISO10110Generator

class TestDrawingExport(unittest.TestCase):
    def setUp(self):
        self.filename = "test_drawing.svg"
        self.lens = Lens(
            radius_of_curvature_1=50.0,
            radius_of_curvature_2=-50.0,
            thickness=10.0,
            diameter=25.0,
            refractive_index=1.5
        )
        self.system = OpticalSystem(name="Test System")
        self.system.add_lens(self.lens)

    def tearDown(self):
        if os.path.exists(self.filename):
            os.remove(self.filename)

    def test_svg_generation(self):
        """Test SVG generation"""
        generator = ISO10110Generator(self.system)
        generator.generate_svg(self.filename)
        
        self.assertTrue(os.path.exists(self.filename))
        
        with open(self.filename, 'r') as f:
            content = f.read()
            
        # Check for key SVG elements
        self.assertIn('<svg', content)
        self.assertIn('ISO 10110 Drawing', content)
        self.assertIn('class="lens"', content)
        self.assertIn('Radius', content)
        self.assertIn('50.00', content) # R1 value
        self.assertIn('Test System', content)

if __name__ == '__main__':
    unittest.main()
