#!/usr/bin/env python3
"""
Refine StepExporter to handle multi-body assemblies.
Iterates through all elements in an OpticalSystem and generates discrete solids.
"""

import sys
import os
import unittest
import tempfile
import math

# Adjust path to find src
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src'))

from optical_system import OpticalSystem, create_doublet
try:
    from io.step_export import StepExporter
except ImportError:
    # Handle the case where io is not a package (due to python built-in 'io' shadowing)
    try:
        from src.io.step_export import StepExporter
    except ImportError:
        # Another fallback for standard layout
        import sys
        import os
        sys.path.append(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src', 'io'))
        from step_export import StepExporter

from lens import Lens

class TestStepExporterMultiBody(unittest.TestCase):

    def setUp(self):
        # Create a simple doublet system
        self.system = create_doublet(focal_length=100.0, diameter=40.0)
        self.exporter = StepExporter(self.system)

    def test_export_doublet_to_step(self):
        """Export a doublet and check if the STEP file is generated and contains multiple solids."""
        with tempfile.NamedTemporaryFile(suffix='.step', delete=False) as tmp:
            tmp_path = tmp.name
        
        try:
            self.exporter.export(tmp_path)
            
            # Check if file exists and has content
            self.assertTrue(os.path.exists(tmp_path))
            with open(tmp_path, 'r') as f:
                content = f.read()
                
            # Verify basic STEP structure
            self.assertIn("ISO-10303-21;", content)
            self.assertIn("DATA;", content)
            self.assertIn("END-ISO-10303-21;", content)
            
            # Verify we have multiple MANIFOLD_SOLID_BREP entities
            # One for each lens in the doublet
            solid_count = content.count("MANIFOLD_SOLID_BREP")
            self.assertEqual(solid_count, 2, f"Expected 2 solids for doublet, found {solid_count}")
            
            # Verify lens names are present in the solids
            for element in self.system.elements:
                self.assertIn(f"'{element.lens.name}'", content)
                
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_export_single_lens(self):
        """Verify it still works for a single lens."""
        lens = Lens(name="SingleLens", radius_of_curvature_1=50, radius_of_curvature_2=-50, thickness=5, diameter=30)
        exporter = StepExporter(lens)
        
        with tempfile.NamedTemporaryFile(suffix='.step', delete=False) as tmp:
            tmp_path = tmp.name
            
        try:
            exporter.export(tmp_path)
            with open(tmp_path, 'r') as f:
                content = f.read()
            
            solid_count = content.count("MANIFOLD_SOLID_BREP")
            self.assertEqual(solid_count, 1)
            self.assertIn("'SingleLens'", content)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

if __name__ == '__main__':
    unittest.main()
