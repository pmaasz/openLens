"""
Preset Lens Library

Provides common lens designs, industry standard lenses, and quick-start templates.
"""

import json
from typing import Dict, List, Any

class PresetLensLibrary:
    """Library of preset lens configurations"""
    
    def __init__(self):
        self.presets = self._initialize_presets()
    
    def _initialize_presets(self) -> Dict[str, Dict[str, Any]]:
        """Initialize preset lens configurations"""
        return {
            # Educational/Basic Lenses
            "simple_plano_convex": {
                "name": "Simple Plano-Convex",
                "category": "Educational",
                "description": "Basic plano-convex lens for learning",
                "radius1": 50.0,
                "radius2": float('inf'),
                "thickness": 5.0,
                "diameter": 25.4,
                "material": "BK7",
                "focal_length": 100.0,
                "applications": ["Beam focusing", "Simple magnification"]
            },
            "biconvex_symmetric": {
                "name": "Symmetric Biconvex",
                "category": "Educational",
                "description": "Equal curvature on both sides",
                "radius1": 50.0,
                "radius2": -50.0,
                "thickness": 6.0,
                "diameter": 25.4,
                "material": "BK7",
                "focal_length": 50.0,
                "applications": ["Relay lenses", "Basic imaging"]
            },
            
            # Eyepieces
            "kellner_eyepiece": {
                "name": "Kellner Eyepiece",
                "category": "Eyepiece",
                "description": "Popular eyepiece design with good field of view",
                "radius1": 15.0,
                "radius2": -30.0,
                "thickness": 4.0,
                "diameter": 20.0,
                "material": "BK7",
                "focal_length": 25.0,
                "applications": ["Telescopes", "Microscopes"]
            },
            "plossl_eyepiece": {
                "name": "Plössl Eyepiece",
                "category": "Eyepiece",
                "description": "Wide field eyepiece with low distortion",
                "radius1": 20.0,
                "radius2": -35.0,
                "thickness": 5.0,
                "diameter": 24.0,
                "material": "BK7",
                "focal_length": 20.0,
                "applications": ["Astronomy", "High-end viewing"]
            },
            
            # Objectives
            "microscope_objective_4x": {
                "name": "4× Microscope Objective",
                "category": "Objective",
                "description": "Low power microscope objective",
                "radius1": 12.0,
                "radius2": -25.0,
                "thickness": 8.0,
                "diameter": 15.0,
                "material": "BK7",
                "focal_length": 40.0,
                "magnification": 4.0,
                "applications": ["Microscopy", "Sample scanning"]
            },
            "microscope_objective_10x": {
                "name": "10× Microscope Objective",
                "category": "Objective",
                "description": "Medium power microscope objective",
                "radius1": 8.0,
                "radius2": -15.0,
                "thickness": 6.0,
                "diameter": 12.0,
                "material": "BK7",
                "focal_length": 16.0,
                "magnification": 10.0,
                "applications": ["Microscopy", "Cell observation"]
            },
            "telescope_objective": {
                "name": "Telescope Objective",
                "category": "Objective",
                "description": "Long focal length for astronomical viewing",
                "radius1": 200.0,
                "radius2": -250.0,
                "thickness": 10.0,
                "diameter": 50.0,
                "material": "BK7",
                "focal_length": 500.0,
                "applications": ["Astronomy", "Long distance viewing"]
            },
            
            # Condensers
            "abbe_condenser": {
                "name": "Abbe Condenser",
                "category": "Condenser",
                "description": "Standard microscope illumination condenser",
                "radius1": 25.0,
                "radius2": -30.0,
                "thickness": 8.0,
                "diameter": 30.0,
                "material": "BK7",
                "focal_length": 35.0,
                "numerical_aperture": 1.25,
                "applications": ["Microscope illumination", "Brightfield imaging"]
            },
            
            # Laser Optics
            "laser_focusing_lens": {
                "name": "Laser Focusing Lens",
                "category": "Laser Optics",
                "description": "High quality lens for laser beam focusing",
                "radius1": 30.0,
                "radius2": -45.0,
                "thickness": 5.0,
                "diameter": 25.4,
                "material": "UVFS",
                "focal_length": 50.0,
                "coating": "AR coated 532nm",
                "applications": ["Laser systems", "Beam shaping"]
            },
            "beam_expander_element": {
                "name": "Beam Expander Element",
                "category": "Laser Optics",
                "description": "Expanding divergent laser beams",
                "radius1": -20.0,
                "radius2": 40.0,
                "thickness": 4.0,
                "diameter": 25.4,
                "material": "UVFS",
                "focal_length": -25.0,
                "applications": ["Laser beam expansion", "Collimation"]
            },
            
            # Camera Lenses
            "camera_lens_50mm": {
                "name": "50mm Camera Lens",
                "category": "Camera Lens",
                "description": "Standard camera lens focal length",
                "radius1": 35.0,
                "radius2": -60.0,
                "thickness": 7.0,
                "diameter": 40.0,
                "material": "BK7",
                "focal_length": 50.0,
                "f_number": 1.8,
                "applications": ["Photography", "General imaging"]
            },
            
            # Industry Standard Part Numbers (Edmund Optics style)
            "edmund_45166": {
                "name": "Edmund #45-166 (25mm PCX)",
                "category": "Industry Standard",
                "description": "Popular plano-convex lens, 25mm dia, 50mm FL",
                "radius1": 25.8,
                "radius2": float('inf'),
                "thickness": 4.8,
                "diameter": 25.0,
                "material": "N-BK7",
                "focal_length": 50.0,
                "part_number": "45-166",
                "vendor": "Edmund Optics",
                "applications": ["Laser focusing", "Beam shaping"]
            },
            "edmund_45168": {
                "name": "Edmund #45-168 (25mm PCX)",
                "category": "Industry Standard",
                "description": "Popular plano-convex lens, 25mm dia, 100mm FL",
                "radius1": 51.5,
                "radius2": float('inf'),
                "thickness": 3.8,
                "diameter": 25.0,
                "material": "N-BK7",
                "focal_length": 100.0,
                "part_number": "45-168",
                "vendor": "Edmund Optics",
                "applications": ["Imaging", "Light collection"]
            },
            "thorlabs_la1509": {
                "name": "Thorlabs LA1509 (25mm PCX)",
                "category": "Industry Standard",
                "description": "Thorlabs plano-convex, 1 inch dia, 100mm FL",
                "radius1": 51.5,
                "radius2": float('inf'),
                "thickness": 3.3,
                "diameter": 25.4,
                "material": "N-BK7",
                "focal_length": 100.0,
                "part_number": "LA1509",
                "vendor": "Thorlabs",
                "applications": ["General purpose", "Optical systems"]
            }
        }
    
    def get_categories(self) -> List[str]:
        """Get list of all preset categories"""
        categories = set()
        for preset in self.presets.values():
            categories.add(preset["category"])
        return sorted(list(categories))
    
    def get_presets_by_category(self, category: str) -> Dict[str, Dict[str, Any]]:
        """Get all presets in a specific category"""
        return {
            key: preset for key, preset in self.presets.items()
            if preset["category"] == category
        }
    
    def get_preset(self, preset_id: str) -> Dict[str, Any]:
        """Get a specific preset by ID"""
        return self.presets.get(preset_id, None)
    
    def search_presets(self, query: str) -> Dict[str, Dict[str, Any]]:
        """Search presets by name, description, or application"""
        query = query.lower()
        results = {}
        for key, preset in self.presets.items():
            if (query in preset["name"].lower() or
                query in preset["description"].lower() or
                any(query in app.lower() for app in preset.get("applications", []))):
                results[key] = preset
        return results
    
    def get_all_presets(self) -> Dict[str, Dict[str, Any]]:
        """Get all available presets"""
        return self.presets
    
    def export_preset(self, preset_id: str, filepath: str):
        """Export a preset to a JSON file"""
        preset = self.get_preset(preset_id)
        if preset:
            with open(filepath, 'w') as f:
                json.dump(preset, f, indent=2)
    
    def import_custom_preset(self, filepath: str) -> str:
        """Import a custom preset from a JSON file"""
        with open(filepath, 'r') as f:
            preset = json.load(f)
        
        # Generate a unique ID
        preset_id = f"custom_{len([k for k in self.presets if k.startswith('custom_')])}"
        self.presets[preset_id] = preset
        return preset_id
    
    def get_preset_summary(self, preset_id: str) -> str:
        """Get a formatted summary of a preset"""
        preset = self.get_preset(preset_id)
        if not preset:
            return "Preset not found"
        
        summary = f"{preset['name']}\n"
        summary += f"Category: {preset['category']}\n"
        summary += f"Description: {preset['description']}\n"
        summary += f"Focal Length: {preset['focal_length']} mm\n"
        summary += f"Diameter: {preset['diameter']} mm\n"
        summary += f"Material: {preset['material']}\n"
        
        if 'part_number' in preset:
            summary += f"Part Number: {preset['part_number']}\n"
        if 'vendor' in preset:
            summary += f"Vendor: {preset['vendor']}\n"
        if 'applications' in preset:
            summary += f"Applications: {', '.join(preset['applications'])}\n"
        
        return summary


def get_preset_library() -> PresetLensLibrary:
    """Factory function to get the preset lens library"""
    return PresetLensLibrary()
