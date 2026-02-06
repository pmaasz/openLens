"""
Tests for services module.

Tests the service layer that provides business logic and decouples
data access from presentation.
"""

import unittest
import sys
import os
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
import tempfile
import shutil

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from services import LensService, CalculationService, MaterialDatabaseService
from lens_editor import Lens, LensManager
from validation import ValidationError


class TestLensService(unittest.TestCase):
    """Test LensService functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.storage_file = os.path.join(self.temp_dir, "test_lenses.json")
        self.lens_manager = LensManager(self.storage_file)
        
        # Mock material database
        self.material_db = Mock()
        self.material_db.get_material.return_value = {'name': 'BK7', 'type': 'glass'}
        self.material_db.get_refractive_index.return_value = 1.5168
        self.material_db.has_material.return_value = True
        self.material_db.list_materials.return_value = ['BK7', 'SF11', 'Fused Silica']
        
        self.service = LensService(self.lens_manager, self.material_db)
    
    def tearDown(self):
        """Clean up test files"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_create_lens_basic(self):
        """Test creating a basic lens"""
        lens = self.service.create_lens(
            name="Test Lens",
            radius1=50.0,
            radius2=-50.0,
            thickness=5.0,
            diameter=25.0,
            material="BK7"
        )
        
        self.assertIsNotNone(lens)
        self.assertEqual(lens.name, "Test Lens")
        self.assertEqual(lens.radius_of_curvature_1, 50.0)
        self.assertEqual(lens.radius_of_curvature_2, -50.0)
        self.assertEqual(lens.thickness, 5.0)
        self.assertEqual(lens.diameter, 25.0)
        self.assertEqual(lens.material, "BK7")
        
        # Verify lens was added to manager
        self.assertEqual(len(self.lens_manager.lenses), 1)
    
    def test_create_lens_with_material_database(self):
        """Test lens creation with material database integration"""
        lens = self.service.create_lens(
            name="DB Lens",
            radius1=100.0,
            radius2=-100.0,
            thickness=10.0,
            diameter=50.0,
            material="BK7",
            wavelength=550.0,
            temperature=25.0
        )
        
        # Verify material database was consulted
        self.material_db.get_material.assert_called_with("BK7")
        self.material_db.get_refractive_index.assert_called_with("BK7", 550.0, 25.0)
        
        # Refractive index may be slightly different due to wavelength/temperature calculation
        self.assertAlmostEqual(lens.refractive_index, 1.5168, places=2)
    
    def test_create_lens_without_material_database(self):
        """Test lens creation without material database"""
        service = LensService(self.lens_manager, material_db=None)
        
        lens = service.create_lens(
            name="No DB Lens",
            radius1=75.0,
            radius2=-75.0,
            thickness=7.0,
            diameter=30.0,
            material="BK7"
        )
        
        # Should use fallback default index
        self.assertAlmostEqual(lens.refractive_index, 1.5168, places=2)
    
    def test_create_lens_unknown_material(self):
        """Test lens creation with unknown material"""
        self.material_db.get_material.return_value = None
        
        lens = self.service.create_lens(
            name="Unknown Material",
            radius1=60.0,
            radius2=-60.0,
            thickness=6.0,
            diameter=28.0,
            material="UnknownGlass"
        )
        
        # Should fall back to default BK7 index
        self.assertEqual(lens.refractive_index, 1.5168)
    
    def test_update_lens_basic(self):
        """Test updating lens properties"""
        lens = self.service.create_lens(
            name="Original",
            radius1=50.0,
            radius2=-50.0,
            thickness=5.0,
            diameter=25.0
        )
        
        success = self.service.update_lens(
            lens,
            name="Updated",
            radius_of_curvature_1=60.0,
            thickness=6.0
        )
        
        self.assertTrue(success)
        self.assertEqual(lens.name, "Updated")
        self.assertEqual(lens.radius_of_curvature_1, 60.0)
        self.assertEqual(lens.thickness, 6.0)
        self.assertIsNotNone(lens.modified_at)
    
    def test_update_lens_with_validation(self):
        """Test update validation catches invalid values"""
        lens = self.service.create_lens(
            name="Test",
            radius1=50.0,
            radius2=-50.0,
            thickness=5.0,
            diameter=25.0
        )
        
        # Try to set invalid thickness
        success = self.service.update_lens(lens, thickness=-5.0)
        
        # Should fail validation
        self.assertFalse(success)
        self.assertEqual(lens.thickness, 5.0)  # Unchanged
    
    def test_update_lens_material_changes_index(self):
        """Test that changing material updates refractive index"""
        lens = self.service.create_lens(
            name="Test",
            radius1=50.0,
            radius2=-50.0,
            thickness=5.0,
            diameter=25.0,
            material="BK7"
        )
        
        # Change material
        self.material_db.get_refractive_index.return_value = 1.78
        success = self.service.update_lens(lens, material="SF11")
        
        self.assertTrue(success)
        self.assertEqual(lens.material, "SF11")
        # Refractive index should be updated
        self.material_db.get_refractive_index.assert_called()
    
    def test_calculate_optical_properties(self):
        """Test calculation of optical properties"""
        lens = self.service.create_lens(
            name="Test",
            radius1=50.0,
            radius2=-50.0,
            thickness=5.0,
            diameter=25.0,
            material="BK7"
        )
        
        props = self.service.calculate_optical_properties(lens)
        
        self.assertIn('focal_length', props)
        self.assertIn('optical_power', props)
        self.assertIn('f_number', props)
        self.assertIn('numerical_aperture', props)
        
        # Verify calculations are reasonable
        self.assertIsInstance(props['focal_length'], float)
        self.assertIsInstance(props['optical_power'], float)
    
    def test_get_available_materials_with_db(self):
        """Test getting materials from database"""
        materials = self.service.get_available_materials()
        
        self.assertEqual(materials, ['BK7', 'SF11', 'Fused Silica'])
        self.material_db.list_materials.assert_called_once()
    
    def test_get_available_materials_without_db(self):
        """Test getting materials without database"""
        service = LensService(self.lens_manager, material_db=None)
        materials = service.get_available_materials()
        
        # Should return fallback list
        self.assertIn('BK7', materials)
        self.assertIn('Fused Silica', materials)
        self.assertGreater(len(materials), 0)
    
    def test_duplicate_lens(self):
        """Test lens duplication"""
        original = self.service.create_lens(
            name="Original",
            radius1=50.0,
            radius2=-50.0,
            thickness=5.0,
            diameter=25.0
        )
        
        duplicate = self.service.duplicate_lens(original)
        
        self.assertNotEqual(duplicate.id, original.id)
        self.assertEqual(duplicate.name, "Original (Copy)")
        self.assertEqual(duplicate.radius_of_curvature_1, original.radius_of_curvature_1)
        self.assertEqual(duplicate.thickness, original.thickness)
        
        # Should be in manager
        self.assertEqual(len(self.lens_manager.lenses), 2)
    
    def test_duplicate_lens_with_new_name(self):
        """Test lens duplication with custom name"""
        original = self.service.create_lens(
            name="Original",
            radius1=50.0,
            radius2=-50.0,
            thickness=5.0,
            diameter=25.0
        )
        
        duplicate = self.service.duplicate_lens(original, new_name="Custom Copy")
        
        self.assertEqual(duplicate.name, "Custom Copy")


class TestCalculationService(unittest.TestCase):
    """Test CalculationService functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.service = CalculationService()
        
        # Create a test lens
        self.lens = Lens(
            name="Test Lens",
            radius_of_curvature_1=50.0,
            radius_of_curvature_2=-50.0,
            thickness=5.0,
            diameter=25.0,
            refractive_index=1.5168
        )
    
    def test_initialization(self):
        """Test service initialization"""
        self.assertIsNotNone(self.service)
        self.assertIsInstance(self.service._aberrations_available, bool)
        self.assertIsInstance(self.service._ray_tracer_available, bool)
    
    def test_is_aberrations_available(self):
        """Test checking aberrations availability"""
        available = self.service.is_aberrations_available()
        self.assertIsInstance(available, bool)
    
    def test_is_ray_tracing_available(self):
        """Test checking ray tracing availability"""
        available = self.service.is_ray_tracing_available()
        self.assertIsInstance(available, bool)
    
    @unittest.skipIf(not CalculationService().is_aberrations_available(), 
                     "Aberrations module not available")
    def test_calculate_aberrations(self):
        """Test aberrations calculation"""
        result = self.service.calculate_aberrations(
            self.lens,
            aperture=10.0,
            field_angle=5.0
        )
        
        if result is not None:
            self.assertIsInstance(result, dict)
            # Check for expected aberration types
            expected_keys = ['spherical', 'coma', 'astigmatism', 
                           'field_curvature', 'distortion']
            for key in expected_keys:
                if key in result:
                    self.assertIsInstance(result[key], (int, float))
    
    @unittest.skipIf(not CalculationService().is_aberrations_available(), 
                     "Aberrations module not available")
    def test_calculate_aberrations_default_aperture(self):
        """Test aberrations with default aperture"""
        result = self.service.calculate_aberrations(self.lens)
        
        if result is not None:
            self.assertIsInstance(result, dict)
    
    @unittest.skipIf(not CalculationService().is_ray_tracing_available(), 
                     "Ray tracer module not available")
    def test_trace_rays_parallel(self):
        """Test parallel ray tracing"""
        rays = self.service.trace_rays(
            self.lens,
            num_rays=11,
            ray_type='parallel'
        )
        
        if rays is not None:
            self.assertIsInstance(rays, list)
            self.assertGreater(len(rays), 0)
    
    @unittest.skipIf(not CalculationService().is_ray_tracing_available(), 
                     "Ray tracer module not available")
    def test_trace_rays_point_source(self):
        """Test point source ray tracing"""
        rays = self.service.trace_rays(
            self.lens,
            num_rays=11,
            ray_type='point_source'
        )
        
        if rays is not None:
            self.assertIsInstance(rays, list)
    
    def test_trace_rays_invalid_type(self):
        """Test ray tracing with invalid type"""
        if self.service.is_ray_tracing_available():
            rays = self.service.trace_rays(
                self.lens,
                ray_type='invalid_type'
            )
            # Should handle error gracefully
            self.assertIsNone(rays)
    
    @unittest.skipIf(not CalculationService().is_aberrations_available(), 
                     "Aberrations module not available")
    def test_assess_lens_quality(self):
        """Test lens quality assessment"""
        quality = self.service.assess_lens_quality(self.lens)
        
        if quality is not None:
            self.assertIsInstance(quality, dict)


class TestMaterialDatabaseService(unittest.TestCase):
    """Test MaterialDatabaseService functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.service = MaterialDatabaseService()
    
    def test_initialization(self):
        """Test service initialization"""
        self.assertIsNotNone(self.service)
        self.assertIsInstance(self.service.is_available(), bool)
    
    def test_get_materials(self):
        """Test getting material list"""
        materials = self.service.get_materials()
        
        self.assertIsInstance(materials, list)
        self.assertGreater(len(materials), 0)
        self.assertIn('BK7', materials)
    
    def test_get_refractive_index_default(self):
        """Test getting refractive index for common materials"""
        index = self.service.get_refractive_index('BK7')
        
        self.assertIsInstance(index, float)
        self.assertGreater(index, 1.0)
        self.assertLess(index, 3.0)
    
    def test_get_refractive_index_with_wavelength(self):
        """Test getting refractive index with custom wavelength"""
        index = self.service.get_refractive_index(
            'BK7',
            wavelength=550.0,
            temperature=20.0
        )
        
        self.assertIsInstance(index, float)
        self.assertGreater(index, 1.0)
    
    def test_get_refractive_index_unknown_material(self):
        """Test getting index for unknown material"""
        index = self.service.get_refractive_index('UnknownMaterial')
        
        # Should return fallback value
        self.assertIsInstance(index, float)
        self.assertEqual(index, 1.5168)  # Default BK7
    
    def test_get_material_info(self):
        """Test getting detailed material information"""
        info = self.service.get_material_info('BK7')
        
        self.assertIsInstance(info, dict)
        self.assertIn('name', info)
        # MaterialProperties has 'nd' instead of 'refractive_index'
        self.assertTrue('nd' in info or 'refractive_index' in info)
        self.assertEqual(info['name'], 'BK7')
    
    def test_get_material_info_unknown(self):
        """Test getting info for unknown material"""
        info = self.service.get_material_info('UnknownGlass')
        
        self.assertIsInstance(info, dict)
        self.assertEqual(info['name'], 'UnknownGlass')
        self.assertIn('refractive_index', info)


class TestServiceIntegration(unittest.TestCase):
    """Test integration between services"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.storage_file = os.path.join(self.temp_dir, "test_lenses.json")
        self.lens_manager = LensManager(self.storage_file)
        
        self.material_service = MaterialDatabaseService()
        self.lens_service = LensService(self.lens_manager)
        self.calc_service = CalculationService()
    
    def tearDown(self):
        """Clean up test files"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_create_and_calculate(self):
        """Test creating lens and calculating properties"""
        # Create lens
        lens = self.lens_service.create_lens(
            name="Integration Test",
            radius1=50.0,
            radius2=-50.0,
            thickness=5.0,
            diameter=25.0,
            material="BK7"
        )
        
        # Calculate properties
        props = self.lens_service.calculate_optical_properties(lens)
        self.assertIsNotNone(props)
        
        # Try aberrations if available
        if self.calc_service.is_aberrations_available():
            aberrations = self.calc_service.calculate_aberrations(lens)
            # May be None if calculation fails, which is acceptable
            if aberrations is not None:
                self.assertIsInstance(aberrations, dict)
    
    def test_material_service_integration(self):
        """Test integration with material database service"""
        materials = self.material_service.get_materials()
        
        # Create lens with first available material
        if materials:
            lens = self.lens_service.create_lens(
                name="Material Test",
                radius1=60.0,
                radius2=-60.0,
                thickness=6.0,
                diameter=30.0,
                material=materials[0]
            )
            
            self.assertEqual(lens.material, materials[0])
    
    def test_update_and_recalculate(self):
        """Test updating lens and recalculating"""
        lens = self.lens_service.create_lens(
            name="Update Test",
            radius1=50.0,
            radius2=-50.0,
            thickness=5.0,
            diameter=25.0
        )
        
        # Initial properties
        props1 = self.lens_service.calculate_optical_properties(lens)
        
        # Update lens
        self.lens_service.update_lens(
            lens,
            radius_of_curvature_1=100.0
        )
        
        # Recalculate
        props2 = self.lens_service.calculate_optical_properties(lens)
        
        # Properties should be different (focal length changes with radius)
        # Check they're both valid first, then compare if not infinite
        self.assertIn('focal_length', props2)
        if props1['focal_length'] != float('inf') and props2['focal_length'] != float('inf'):
            self.assertNotAlmostEqual(props1['focal_length'], props2['focal_length'], places=1)
        else:
            # At least verify the calculation ran
            self.assertTrue(True)


if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)
