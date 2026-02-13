#!/usr/bin/env python3
"""
Functional tests for Export Enhancements
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import unittest
import tempfile
import json
from lens_editor import Lens
from export_formats import ZemaxExporter, PrescriptionExporter

# Check if SVG exporter exists
try:
    from export_formats import SVGExporter
    SVG_AVAILABLE = True
except ImportError:
    SVG_AVAILABLE = False


class TestZemaxExport(unittest.TestCase):
    """Test Zemax format export"""
    
    def setUp(self):
        """Create test lens"""
        self.lens = Lens(
            name="Test Lens",
            radius_of_curvature_1=50.0,
            radius_of_curvature_2=-50.0,
            thickness=5.0,
            diameter=25.0,
            refractive_index=1.5168,
            lens_type="Biconvex",
            material="BK7"
        )
    
    def test_export_single_lens(self):
        """Test exporting single lens to Zemax format"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.zmx', delete=False) as f:
            filename = f.name
        
        try:
            ZemaxExporter.export_lens(self.lens, filename)
            
            # Verify file was created and has content
            self.assertTrue(os.path.exists(filename))
            
            with open(filename, 'r') as f:
                content = f.read()
            
            self.assertIn('OpenLens Export', content)
            self.assertIn('Test Lens', content)
            self.assertIn('SURF', content)
            self.assertIn('BK7', content)
            
            print("✓ Exported lens to Zemax format successfully")
            print(f"  File size: {os.path.getsize(filename)} bytes")
            
        finally:
            if os.path.exists(filename):
                os.unlink(filename)
    
    def test_zemax_surface_data(self):
        """Test Zemax surface data formatting"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.zmx', delete=False) as f:
            filename = f.name
        
        try:
            ZemaxExporter.export_lens(self.lens, filename)
            
            with open(filename, 'r') as f:
                content = f.read()
            
            # Check for required Zemax keywords
            self.assertIn('CURV', content)
            self.assertIn('DISZ', content)
            self.assertIn('DIAM', content)
            self.assertIn('GLAS', content)
            
            print("✓ Zemax surface data formatted correctly")
            
        finally:
            if os.path.exists(filename):
                os.unlink(filename)


class TestOpticStudioExport(unittest.TestCase):
    """Test OpticStudio format export"""
    
    def setUp(self):
        """Create test lens"""
        self.lens = Lens(
            name="OpticStudio Test",
            radius_of_curvature_1=75.0,
            radius_of_curvature_2=-75.0,
            thickness=6.0,
            diameter=30.0,
            refractive_index=1.5168,
            material="BK7"
        )
    
    def test_export_opticstudio(self):
        """Test exporting to OpticStudio format"""
        from export_formats import OpticStudioExporter
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            filename = f.name
        
        try:
            OpticStudioExporter.export_lens(self.lens, filename)
            
            self.assertTrue(os.path.exists(filename))
            
            with open(filename, 'r') as f:
                content = f.read()
            
            self.assertIn('OpenLens', content)
            self.assertIn('OpticStudio Test', content)
            
            print("✓ Exported to OpticStudio format successfully")
            
        finally:
            if os.path.exists(filename):
                os.unlink(filename)


@unittest.skipUnless(SVG_AVAILABLE, "SVGExporter not available")
class TestSVGExport(unittest.TestCase):
    """Test SVG export"""
    
    def setUp(self):
        """Create test lens"""
        self.lens = Lens(
            name="SVG Test Lens",
            radius_of_curvature_1=50.0,
            radius_of_curvature_2=-50.0,
            thickness=5.0,
            diameter=25.0,
            refractive_index=1.5168,
            material="BK7"
        )
    
    def test_export_svg(self):
        """Test exporting lens to SVG format"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.svg', delete=False) as f:
            filename = f.name
        
        try:
            SVGExporter.export_lens(self.lens, filename)
            
            self.assertTrue(os.path.exists(filename))
            
            with open(filename, 'r') as f:
                content = f.read()
            
            # Check for SVG tags
            self.assertIn('<svg', content)
            self.assertIn('</svg>', content)
            
            print("✓ Exported to SVG format successfully")
            print(f"  File size: {os.path.getsize(filename)} bytes")
            
        finally:
            if os.path.exists(filename):
                os.unlink(filename)
    
    def test_svg_lens_outline(self):
        """Test SVG contains lens outline"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.svg', delete=False) as f:
            filename = f.name
        
        try:
            SVGExporter.export_lens(self.lens, filename)
            
            with open(filename, 'r') as f:
                content = f.read()
            
            # Check for path elements (lens outline)
            self.assertIn('<path', content)
            
            print("✓ SVG contains lens outline")
            
        finally:
            if os.path.exists(filename):
                os.unlink(filename)


class TestPrescriptionExport(unittest.TestCase):
    """Test prescription file export"""
    
    def setUp(self):
        """Create test lens"""
        self.lens = Lens(
            name="Prescription Test",
            radius_of_curvature_1=100.0,
            radius_of_curvature_2=-100.0,
            thickness=4.0,
            diameter=20.0,
            refractive_index=1.5168,
            lens_type="Biconvex",
            material="BK7"
        )
    
    def test_export_prescription_json(self):
        """Test exporting lens prescription as JSON"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            filename = f.name
        
        try:
            # Export using lens.to_dict()
            with open(filename, 'w') as f:
                json.dump(self.lens.to_dict(), f, indent=2)
            
            self.assertTrue(os.path.exists(filename))
            
            # Verify content
            with open(filename, 'r') as f:
                data = json.load(f)
            
            self.assertEqual(data['name'], 'Prescription Test')
            self.assertEqual(data['radius_of_curvature_1'], 100.0)
            self.assertEqual(data['radius_of_curvature_2'], -100.0)
            self.assertEqual(data['material'], 'BK7')
            
            print("✓ Exported prescription JSON successfully")
            print(f"  Keys: {', '.join(data.keys())}")
            
        finally:
            if os.path.exists(filename):
                os.unlink(filename)
    
    def test_prescription_roundtrip(self):
        """Test prescription export and import roundtrip"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            filename = f.name
        
        try:
            # Export
            with open(filename, 'w') as f:
                json.dump(self.lens.to_dict(), f, indent=2)
            
            # Import
            with open(filename, 'r') as f:
                data = json.load(f)
            
            imported_lens = Lens.from_dict(data)
            
            # Verify all properties match
            self.assertEqual(imported_lens.name, self.lens.name)
            self.assertEqual(imported_lens.radius_of_curvature_1, self.lens.radius_of_curvature_1)
            self.assertEqual(imported_lens.radius_of_curvature_2, self.lens.radius_of_curvature_2)
            self.assertEqual(imported_lens.thickness, self.lens.thickness)
            self.assertEqual(imported_lens.diameter, self.lens.diameter)
            self.assertEqual(imported_lens.material, self.lens.material)
            
            print("✓ Prescription roundtrip successful")
            
        finally:
            if os.path.exists(filename):
                os.unlink(filename)


class TestExportEdgeCases(unittest.TestCase):
    """Test edge cases in export functionality"""
    
    def test_export_plano_convex(self):
        """Test exporting plano-convex lens"""
        lens = Lens(
            name="Plano-Convex",
            radius_of_curvature_1=50.0,
            radius_of_curvature_2=float('inf'),  # Flat surface
            thickness=5.0,
            diameter=25.0,
            refractive_index=1.5168,
            lens_type="Plano-Convex",
            material="BK7"
        )
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.zmx', delete=False) as f:
            filename = f.name
        
        try:
            ZemaxExporter.export_lens(lens, filename)
            self.assertTrue(os.path.exists(filename))
            print("✓ Exported plano-convex lens successfully")
            
        finally:
            if os.path.exists(filename):
                os.unlink(filename)
    
    def test_export_with_special_characters(self):
        """Test exporting lens with special characters in name"""
        lens = Lens(
            name="Test-Lens_#1 (v2.0)",
            radius_of_curvature_1=50.0,
            radius_of_curvature_2=-50.0,
            thickness=5.0,
            diameter=25.0,
            refractive_index=1.5168
        )
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            filename = f.name
        
        try:
            with open(filename, 'w') as f:
                json.dump(lens.to_dict(), f, indent=2)
            
            self.assertTrue(os.path.exists(filename))
            print("✓ Exported lens with special characters")
            
        finally:
            if os.path.exists(filename):
                os.unlink(filename)


def run_tests():
    """Run all export enhancement tests"""
    print("="*70)
    print("TESTING: Export Enhancements")
    print("="*70)
    
    suite = unittest.TestLoader().loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print("\n" + "="*70)
    if result.wasSuccessful():
        print("✓ All export tests passed!")
    else:
        print("✗ Some tests failed")
    print("="*70)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
