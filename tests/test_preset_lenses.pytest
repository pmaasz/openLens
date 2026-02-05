"""
Functional tests for preset lens library
"""

import pytest
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from preset_lenses import PresetLensLibrary, get_preset_library


class TestPresetLensLibrary:
    """Test the preset lens library functionality"""
    
    def test_library_initialization(self):
        """Test that the library initializes with presets"""
        library = PresetLensLibrary()
        assert len(library.presets) > 0
        assert isinstance(library.presets, dict)
    
    def test_get_categories(self):
        """Test getting all categories"""
        library = PresetLensLibrary()
        categories = library.get_categories()
        
        assert isinstance(categories, list)
        assert len(categories) > 0
        assert "Educational" in categories
        assert "Eyepiece" in categories
        assert "Objective" in categories
    
    def test_get_preset_by_id(self):
        """Test retrieving a specific preset"""
        library = PresetLensLibrary()
        preset = library.get_preset("simple_plano_convex")
        
        assert preset is not None
        assert preset["name"] == "Simple Plano-Convex"
        assert preset["category"] == "Educational"
        assert "radius1" in preset
        assert "radius2" in preset
        assert "thickness" in preset
        assert "diameter" in preset
        assert "material" in preset
        assert "focal_length" in preset
    
    def test_get_presets_by_category(self):
        """Test filtering presets by category"""
        library = PresetLensLibrary()
        educational = library.get_presets_by_category("Educational")
        
        assert len(educational) >= 2
        for preset in educational.values():
            assert preset["category"] == "Educational"
    
    def test_eyepiece_presets(self):
        """Test eyepiece presets"""
        library = PresetLensLibrary()
        eyepieces = library.get_presets_by_category("Eyepiece")
        
        assert len(eyepieces) >= 2
        assert "kellner_eyepiece" in eyepieces or any("kellner" in k.lower() for k in eyepieces.keys())
        
        for preset in eyepieces.values():
            assert preset["focal_length"] > 0
            assert preset["diameter"] > 0
    
    def test_objective_presets(self):
        """Test objective presets"""
        library = PresetLensLibrary()
        objectives = library.get_presets_by_category("Objective")
        
        assert len(objectives) >= 2
        
        for preset in objectives.values():
            assert preset["focal_length"] > 0
            if "microscope" in preset["name"].lower():
                assert "magnification" in preset
    
    def test_search_presets(self):
        """Test searching presets"""
        library = PresetLensLibrary()
        
        # Search by name
        results = library.search_presets("microscope")
        assert len(results) > 0
        for preset in results.values():
            assert "microscope" in preset["name"].lower() or \
                   "microscope" in preset["description"].lower() or \
                   any("microscope" in app.lower() for app in preset.get("applications", []))
        
        # Search by application
        results = library.search_presets("laser")
        assert len(results) > 0
    
    def test_industry_standard_presets(self):
        """Test industry standard lenses with part numbers"""
        library = PresetLensLibrary()
        standards = library.get_presets_by_category("Industry Standard")
        
        assert len(standards) >= 2
        
        for preset in standards.values():
            assert "part_number" in preset
            assert "vendor" in preset
            assert preset["vendor"] in ["Edmund Optics", "Thorlabs"]
    
    def test_preset_has_required_fields(self):
        """Test that all presets have required fields"""
        library = PresetLensLibrary()
        required_fields = ["name", "category", "description", "radius1", "radius2", 
                          "thickness", "diameter", "material", "focal_length"]
        
        for preset_id, preset in library.get_all_presets().items():
            for field in required_fields:
                assert field in preset, f"Preset {preset_id} missing field {field}"
    
    def test_get_preset_summary(self):
        """Test getting formatted preset summary"""
        library = PresetLensLibrary()
        summary = library.get_preset_summary("simple_plano_convex")
        
        assert "Simple Plano-Convex" in summary
        assert "Educational" in summary
        assert "Focal Length" in summary
        assert "mm" in summary
    
    def test_factory_function(self):
        """Test the factory function"""
        library = get_preset_library()
        assert isinstance(library, PresetLensLibrary)
        assert len(library.presets) > 0
    
    def test_laser_optics_presets(self):
        """Test laser optics category"""
        library = PresetLensLibrary()
        laser_optics = library.get_presets_by_category("Laser Optics")
        
        assert len(laser_optics) >= 2
        
        for preset in laser_optics.values():
            # Laser optics should have UV fused silica or similar
            assert preset["material"] in ["UVFS", "BK7", "N-BK7"]
    
    def test_camera_lens_presets(self):
        """Test camera lens presets"""
        library = PresetLensLibrary()
        camera_lenses = library.get_presets_by_category("Camera Lens")
        
        assert len(camera_lenses) >= 1
        
        for preset in camera_lenses.values():
            if "f_number" in preset:
                assert preset["f_number"] > 0
    
    def test_condenser_presets(self):
        """Test condenser presets"""
        library = PresetLensLibrary()
        condensers = library.get_presets_by_category("Condenser")
        
        assert len(condensers) >= 1
        
        for preset in condensers.values():
            assert "Condenser" in preset["name"]
    
    def test_preset_physical_validity(self):
        """Test that preset parameters are physically valid"""
        library = PresetLensLibrary()
        
        for preset_id, preset in library.get_all_presets().items():
            # Thickness should be positive
            assert preset["thickness"] > 0, f"{preset_id}: Invalid thickness"
            
            # Diameter should be positive
            assert preset["diameter"] > 0, f"{preset_id}: Invalid diameter"
            
            # Focal length can be negative (diverging) but not zero
            assert preset["focal_length"] != 0, f"{preset_id}: Zero focal length"
            
            # Radius1 should not be zero
            if preset["radius1"] != float('inf') and preset["radius1"] != float('-inf'):
                assert preset["radius1"] != 0, f"{preset_id}: Zero radius1"
    
    def test_export_import_preset(self, tmp_path):
        """Test exporting and importing presets"""
        library = PresetLensLibrary()
        
        # Export a preset
        export_file = tmp_path / "test_preset.json"
        library.export_preset("simple_plano_convex", str(export_file))
        
        assert export_file.exists()
        
        # Import it back
        preset_id = library.import_custom_preset(str(export_file))
        assert preset_id.startswith("custom_")
        
        imported = library.get_preset(preset_id)
        assert imported["name"] == "Simple Plano-Convex"


def test_preset_library_integration():
    """Integration test for the complete preset library"""
    library = get_preset_library()
    
    # Get all categories
    categories = library.get_categories()
    assert len(categories) >= 5
    
    # Verify we have presets in each category
    for category in categories:
        presets = library.get_presets_by_category(category)
        assert len(presets) > 0
    
    # Search functionality
    telescope_results = library.search_presets("telescope")
    assert len(telescope_results) > 0
    
    # Get specific preset and verify it's complete
    preset = library.get_preset("biconvex_symmetric")
    assert preset is not None
    assert preset["radius1"] == 50.0
    assert preset["radius2"] == -50.0
    
    # Get summary
    summary = library.get_preset_summary("biconvex_symmetric")
    assert "Symmetric Biconvex" in summary


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
