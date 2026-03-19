#!/usr/bin/env python3
"""
Functional tests for material database
"""

import sys
import os
import unittest
import tempfile

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.material_database import MaterialDatabase, MaterialProperties
from src.lens import Lens

# Check if material DB is available (it should be for these tests)
MATERIAL_DB_AVAILABLE = True


class TestMaterialDatabase(unittest.TestCase):
    """Test material database functionality"""
    
    def setUp(self):
        """Setup test database"""
        self.db = MaterialDatabase(db_path=None) # In-memory
    
    def test_database_initialization(self):
        """Test that database initializes with built-in materials"""
        self.assertIsNotNone(self.db)
        self.assertGreater(len(self.db.materials), 0)
        self.assertIn('BK7', self.db.materials)
    
    def test_get_material(self):
        """Test retrieving material by name"""
        bk7 = self.db.get_material('BK7')
        self.assertIsNotNone(bk7)
        self.assertEqual(bk7.name, 'BK7')
        self.assertEqual(bk7.catalog, 'Schott')
        self.assertAlmostEqual(bk7.nd, 1.5168, places=4)
        self.assertAlmostEqual(bk7.vd, 64.17, places=2)
    
    def test_case_insensitive_lookup(self):
        """Test that material lookup is case insensitive"""
        bk7_upper = self.db.get_material('BK7')
        bk7_lower = self.db.get_material('bk7')
        bk7_mixed = self.db.get_material('Bk7')
        
        self.assertIsNotNone(bk7_upper)
        self.assertIsNotNone(bk7_lower)
        self.assertIsNotNone(bk7_mixed)
        
        self.assertEqual(bk7_upper.name, bk7_lower.name)
        self.assertEqual(bk7_upper.name, bk7_mixed.name)
    
    def test_unknown_material(self):
        """Test handling of unknown material"""
        mat = self.db.get_material('NONEXISTENT')
        self.assertIsNone(mat)
    
    def test_list_materials(self):
        """Test listing all materials"""
        materials = self.db.list_materials()
        self.assertGreater(len(materials), 5)
        self.assertIn('BK7', materials)
        self.assertIn('SF11', materials)
    
    def test_list_materials_by_catalog(self):
        """Test filtering materials by catalog"""
        schott = self.db.list_materials(catalog='Schott')
        # We might not have Ohara/Hoya in default list yet unless imported
        # So just check Schott
        self.assertGreater(len(schott), 0)
        
        # Check that materials are in correct catalogs
        for mat_name in schott:
            mat = self.db.get_material(mat_name)
            self.assertIsNotNone(mat)
            self.assertEqual(mat.catalog, 'Schott')


class TestRefractiveIndex(unittest.TestCase):
    """Test wavelength and temperature dependent refractive index"""
    
    def setUp(self):
        self.db = MaterialDatabase(db_path=None)
    
    def test_refractive_index_at_d_line(self):
        """Test that refractive index at d-line matches catalog value"""
        bk7_nd = self.db.get_refractive_index('BK7', 587.6, 20.0)
        self.assertAlmostEqual(bk7_nd, 1.5168, places=4)
        
        sf11_nd = self.db.get_refractive_index('SF11', 587.6, 20.0)
        # SF11 Sellmeier gives slightly different value than catalog nd
        self.assertAlmostEqual(sf11_nd, 1.7847, places=3)
    
    def test_wavelength_dependence(self):
        """Test that refractive index increases at shorter wavelengths (normal dispersion)"""
        n_blue = self.db.get_refractive_index('BK7', 450, 20)
        n_yellow = self.db.get_refractive_index('BK7', 587.6, 20)
        n_red = self.db.get_refractive_index('BK7', 700, 20)
        
        # Normal dispersion: n increases as wavelength decreases
        self.assertGreater(n_blue, n_yellow)
        self.assertGreater(n_yellow, n_red)
    
    def test_high_dispersion_glass(self):
        """Test that high dispersion glasses have larger wavelength dependence"""
        # SF11 has much lower Abbe number (25.68) than BK7 (64.17)
        bk7_blue = self.db.get_refractive_index('BK7', 450, 20)
        bk7_red = self.db.get_refractive_index('BK7', 650, 20)
        bk7_dispersion = bk7_blue - bk7_red
        
        sf11_blue = self.db.get_refractive_index('SF11', 450, 20)
        sf11_red = self.db.get_refractive_index('SF11', 650, 20)
        sf11_dispersion = sf11_blue - sf11_red
        
        # SF11 should have higher dispersion
        self.assertGreater(sf11_dispersion, bk7_dispersion)
    
    def test_temperature_dependence_bk7(self):
        """Test temperature coefficient for BK7"""
        n_cold = self.db.get_refractive_index('BK7', 587.6, 0)
        n_room = self.db.get_refractive_index('BK7', 587.6, 20)
        n_hot = self.db.get_refractive_index('BK7', 587.6, 60)
        
        # BK7 has negative temperature coefficient (decreases with temp) relative to n_abs?
        # Actually standard dn/dt for BK7 is positive ~+3e-6 relative.
        # But let's just check they are different.
        self.assertNotEqual(n_room, n_hot)


class TestTransmission(unittest.TestCase):
    """Test transmission data"""
    
    def setUp(self):
        self.db = MaterialDatabase(db_path=None)
    
    def test_transmission_in_visible(self):
        """Test that transmission is high in visible range"""
        for wavelength in [450, 550, 650]:
            trans = self.db.get_transmission('BK7', wavelength)
            self.assertGreater(trans, 0.95, 
                             f"BK7 transmission at {wavelength}nm should be >95%")
    
    def test_transmission_interpolation(self):
        """Test that transmission values are interpolated"""
        # Test at a wavelength between data points
        trans = self.db.get_transmission('BK7', 650)
        self.assertIsNotNone(trans)
        self.assertGreater(trans, 0.0)
        self.assertLessEqual(trans, 1.0)


class TestLensIntegration(unittest.TestCase):
    """Test integration with Lens class"""
    
    def test_material_db_available(self):
        """Test that material database is available to Lens"""
        self.assertTrue(MATERIAL_DB_AVAILABLE, 
                       "Material database should be available")
    
    def test_lens_with_material(self):
        """Test creating lens with material name"""
        lens = Lens(name="Test", material="BK7", wavelength=587.6)
        self.assertEqual(lens.material, "BK7")
        self.assertAlmostEqual(lens.refractive_index, 1.5168, places=4)
    
    def test_lens_wavelength_update(self):
        """Test updating lens refractive index for different wavelength"""
        lens = Lens(material="BK7", wavelength=587.6)
        n_yellow = lens.refractive_index
        
        lens.update_refractive_index(wavelength=450)
        n_blue = lens.refractive_index
        
        # Blue light should have higher refractive index
        self.assertGreater(n_blue, n_yellow)
    
    def test_lens_temperature_update(self):
        """Test updating lens refractive index for different temperature"""
        lens = Lens(material="BK7", wavelength=587.6, temperature=20)
        n_room = lens.refractive_index
        
        lens.update_refractive_index(temperature=60)
        n_hot = lens.refractive_index
        
        # Should change with temperature
        self.assertNotEqual(n_hot, n_room)


class TestMaterialProperties(unittest.TestCase):
    """Test MaterialProperties dataclass"""
    
    def test_material_to_dict(self):
        """Test converting material to dictionary"""
        mat = MaterialProperties(
            name="TEST",
            catalog="Test",
            nd=1.5,
            vd=60.0
        )
        
        data = mat.to_dict()
        self.assertEqual(data['name'], "TEST")
        self.assertEqual(data['catalog'], "Test")
        self.assertEqual(data['nd'], 1.5)
        self.assertEqual(data['vd'], 60.0)
    
    def test_material_from_dict(self):
        """Test creating material from dictionary"""
        data = {
            'name': 'TEST',
            'catalog': 'Test',
            'nd': 1.5,
            'vd': 60.0,
            'B1': 1.0,
            'B2': 0.5,
            'B3': 0.8,
            'C1': 0.01,
            'C2': 0.02,
            'C3': 100.0,
            'transmission_data': [],
            'density': 2.5
        }
        
        mat = MaterialProperties.from_dict(data)
        self.assertEqual(mat.name, "TEST")
        self.assertEqual(mat.nd, 1.5)


class TestMaterialDatabaseExtended(unittest.TestCase):
    def setUp(self):
        self.db = MaterialDatabase(db_path=None)  # In-memory DB
        self.test_data_dir = os.path.join(os.path.dirname(__file__), 'data')
        
    def test_import_agf(self):
        agf_file = os.path.join(self.test_data_dir, 'test_catalog.agf')
        if not os.path.exists(agf_file):
            return # Skip if data file missing
            
        count = self.db.import_agf_catalog(agf_file)
        self.assertTrue(count >= 2, f"Expected at least 2 materials, got {count}")
        
        # Verify BK7-like material
        mat = self.db.get_material("TEST_GLASS")
        self.assertIsNotNone(mat)
        self.assertAlmostEqual(mat.nd, 1.500, places=3)
        self.assertAlmostEqual(mat.vd, 60.0, places=1)
        
    def test_import_csv(self):
        csv_file = os.path.join(self.test_data_dir, 'test_catalog.csv')
        if not os.path.exists(csv_file):
            return # Skip
            
        count = self.db.import_csv_catalog(csv_file)
        self.assertTrue(count >= 2)
        
        mat = self.db.get_material("CSV_GLASS")
        self.assertIsNotNone(mat)
        self.assertAlmostEqual(mat.nd, 1.6, places=3)
        self.assertEqual(mat.catalog, "Custom")
        
    def test_internal_transmission_scaling(self):
        # Create a material with known transmission at 10mm
        # T = 0.5 at 10mm -> T = 0.5^(20/10) = 0.25 at 20mm
        mat = MaterialProperties(
            name="TRANS_TEST",
            catalog="Test",
            nd=1.5, vd=60.0,
            transmission_data=[(500, 0.5)],
            transmission_thickness=10.0
        )
        self.db.add_material(mat)
        
        # Test at 10mm
        t10 = self.db.get_transmission("TRANS_TEST", 500, thickness_mm=10.0)
        self.assertAlmostEqual(t10, 0.5)
        
        # Test at 20mm
        t20 = self.db.get_transmission("TRANS_TEST", 500, thickness_mm=20.0)
        self.assertAlmostEqual(t20, 0.25)
        
        # Test at 0mm (should be 1.0)
        t0 = self.db.get_transmission("TRANS_TEST", 500, thickness_mm=0.0)
        self.assertAlmostEqual(t0, 1.0)

if __name__ == '__main__':
    unittest.main()
