#!/usr/bin/env python3
"""
Preset Lens Library
Common lens designs and industry standard templates
"""

import json
from typing import List, Dict, Optional
from dataclasses import dataclass

try:
    from .lens_editor import Lens
    from .optical_system import OpticalSystem
except (ImportError, ValueError):
    import sys
    import os
    sys.path.insert(0, os.path.dirname(__file__))
    from lens_editor import Lens
    from optical_system import OpticalSystem


@dataclass
class LensPreset:
    """A preset lens design"""
    name: str
    category: str
    description: str
    lens: Lens
    manufacturer: Optional[str] = None
    part_number: Optional[str] = None
    typical_use: Optional[str] = None


class PresetLibrary:
    """Library of preset lens designs"""
    
    def __init__(self):
        self.presets: Dict[str, LensPreset] = {}
        self._load_common_presets()
    
    def _load_common_presets(self):
        """Load common preset lenses"""
        
        # Simple lenses
        self.add_preset(LensPreset(
            name="50mm Biconvex",
            category="Simple Lenses",
            description="Standard biconvex lens, 50mm focal length",
            lens=Lens(
                name="50mm Biconvex",
                radius_of_curvature_1=51.5,
                radius_of_curvature_2=-51.5,
                thickness=5.0,
                diameter=25.4,
                material="BK7"
            ),
            typical_use="General purpose focusing, magnification"
        ))
        
        self.add_preset(LensPreset(
            name="100mm Plano-Convex",
            category="Simple Lenses",
            description="Plano-convex lens, 100mm focal length",
            lens=Lens(
                name="100mm Plano-Convex",
                radius_of_curvature_1=51.5,
                radius_of_curvature_2=1e10,  # Flat
                thickness=4.0,
                diameter=25.4,
                material="BK7"
            ),
            typical_use="Collimation, beam shaping"
        ))
        
        self.add_preset(LensPreset(
            name="-50mm Biconcave",
            category="Simple Lenses",
            description="Biconcave lens, -50mm focal length (diverging)",
            lens=Lens(
                name="-50mm Biconcave",
                radius_of_curvature_1=-51.5,
                radius_of_curvature_2=51.5,
                thickness=2.5,
                diameter=25.4,
                material="BK7"
            ),
            typical_use="Beam expansion, reducing convergence"
        ))
        
        # Eyepieces
        self.add_preset(LensPreset(
            name="25mm Plossl Eyepiece",
            category="Eyepieces",
            description="Classic Plossl design, 25mm focal length",
            lens=Lens(
                name="25mm Plossl",
                radius_of_curvature_1=30.0,
                radius_of_curvature_2=-30.0,
                thickness=8.0,
                diameter=24.0,
                material="BK7"
            ),
            typical_use="Telescope eyepiece, 50° field of view"
        ))
        
        # Objectives
        self.add_preset(LensPreset(
            name="Microscope 10x Objective",
            category="Objectives",
            description="Microscope objective, 10x magnification",
            lens=Lens(
                name="10x Objective",
                radius_of_curvature_1=8.0,
                radius_of_curvature_2=-12.0,
                thickness=6.0,
                diameter=18.0,
                material="BK7"
            ),
            typical_use="Microscopy, 10x magnification"
        ))
        
        # Condensers
        self.add_preset(LensPreset(
            name="Abbe Condenser",
            category="Condensers",
            description="Two-element Abbe condenser for microscopy",
            lens=Lens(
                name="Abbe Condenser",
                radius_of_curvature_1=20.0,
                radius_of_curvature_2=-20.0,
                thickness=12.0,
                diameter=30.0,
                material="BK7"
            ),
            typical_use="Microscope illumination"
        ))
        
        # Laser optics
        self.add_preset(LensPreset(
            name="Laser Focusing Lens 532nm",
            category="Laser Optics",
            description="Optimized for green laser (532nm)",
            lens=Lens(
                name="532nm Focus",
                radius_of_curvature_1=75.0,
                radius_of_curvature_2=-75.0,
                thickness=4.0,
                diameter=12.7,
                material="BK7",
                wavelength=532.0
            ),
            typical_use="Laser beam focusing, 532nm wavelength"
        ))
        
        # Camera lenses
        self.add_preset(LensPreset(
            name="50mm Camera Lens Element",
            category="Camera Optics",
            description="Single element approximation of 50mm camera lens",
            lens=Lens(
                name="50mm Camera",
                radius_of_curvature_1=45.0,
                radius_of_curvature_2=-55.0,
                thickness=6.0,
                diameter=40.0,
                material="BK7"
            ),
            typical_use="Photography, normal field of view"
        ))
        
        # UV/IR optics
        self.add_preset(LensPreset(
            name="UV Fused Silica Lens",
            category="Specialty Optics",
            description="UV-grade fused silica, 100mm focal length",
            lens=Lens(
                name="UV Lens",
                radius_of_curvature_1=91.5,
                radius_of_curvature_2=-91.5,
                thickness=5.0,
                diameter=25.4,
                material="FUSEDSILICA",
                wavelength=355.0
            ),
            typical_use="UV applications, spectroscopy"
        ))
    
    def add_preset(self, preset: LensPreset):
        """Add a preset to the library"""
        self.presets[preset.name] = preset
    
    def get_preset(self, name: str) -> Optional[LensPreset]:
        """Get preset by name"""
        return self.presets.get(name)
    
    def list_presets(self, category: Optional[str] = None) -> List[LensPreset]:
        """List all presets, optionally filtered by category"""
        if category:
            return [p for p in self.presets.values() if p.category == category]
        return list(self.presets.values())
    
    def list_categories(self) -> List[str]:
        """Get list of all categories"""
        categories = set(p.category for p in self.presets.values())
        return sorted(categories)
    
    def search_presets(self, query: str) -> List[LensPreset]:
        """Search presets by name or description"""
        query_lower = query.lower()
        results = []
        for preset in self.presets.values():
            if (query_lower in preset.name.lower() or 
                query_lower in preset.description.lower()):
                results.append(preset)
        return results
    
    def get_lens_copy(self, preset_name: str) -> Optional[Lens]:
        """Get a copy of the lens from a preset"""
        preset = self.get_preset(preset_name)
        if preset:
            # Create a new lens with the same parameters
            lens = preset.lens
            return Lens(
                name=lens.name,
                radius_of_curvature_1=lens.radius_of_curvature_1,
                radius_of_curvature_2=lens.radius_of_curvature_2,
                thickness=lens.thickness,
                diameter=lens.diameter,
                refractive_index=lens.refractive_index,
                lens_type=lens.lens_type,
                material=lens.material,
                wavelength=lens.wavelength,
                temperature=lens.temperature
            )
        return None


# Singleton instance
_preset_library = None

def get_preset_library() -> PresetLibrary:
    """Get the singleton preset library instance"""
    global _preset_library
    if _preset_library is None:
        _preset_library = PresetLibrary()
    return _preset_library
