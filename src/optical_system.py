#!/usr/bin/env python3
"""
Multi-element optical system design
Supports compound lenses, doublets, triplets with air gaps
"""

from typing import List, Tuple, Optional
from dataclasses import dataclass, field
import math
import json

try:
    from .lens import Lens
    from .material_database import get_material_database
    from .optical_node import OpticalNode, OpticalElement, OpticalAssembly
    from .vector3 import vec3
except (ImportError, ValueError):
    import sys
    import os
    sys.path.insert(0, os.path.dirname(__file__))
    from lens import Lens
    from material_database import get_material_database
    from optical_node import OpticalNode, OpticalElement, OpticalAssembly
    from vector3 import vec3


@dataclass
class LensElement:
    """A lens element in an optical system"""
    lens: Lens
    position: float = 0.0  # Position along optical axis (mm)
    
    def __post_init__(self) -> None:
        """Calculate element thickness"""
        self.thickness = self.lens.thickness


@dataclass
class AirGap:
    """Air gap between lens elements"""
    thickness: float  # mm
    position: float = 0.0


class OpticalSystem:
    """Multi-element optical system"""
    
    def __init__(self, name: str = "Optical System"):
        self.name = name
        self.elements: List[LensElement] = []
        self.air_gaps: List[AirGap] = []
        self.root = OpticalAssembly(name="Root")
        self._update_positions()
    
    def add_lens(self, lens: Lens, air_gap_before: float = 0.0):
        """Add a lens element to the system"""
        # Calculate new position based on last element in flat list
        last_pos = 0.0
        last_thick = 0.0
        
        # Use existing elements list (which is up to date) to find last position
        if self.elements:
            last_elem = self.elements[-1]
            last_pos = last_elem.position
            last_thick = last_elem.lens.thickness
        
        new_pos = last_pos + last_thick + air_gap_before
        
        # Create Hierarchical Node
        # Add to root (flat hierarchy by default)
        node = OpticalElement(element_model=lens, name=lens.name)
        node.position = vec3(new_pos, 0, 0)
        self.root.add_child(node)
        
        # Rebuild flat lists from tree to maintain compatibility
        self._rebuild_from_tree()

    def add_assembly(self, assembly: OpticalAssembly, position: float = 0.0):
        """Add an optical assembly to the system."""
        # Add to hierarchical tree
        assembly.position = vec3(position, 0, 0)
        self.root.add_child(assembly)
        
        # Rebuild flat lists from tree to maintain compatibility
        self._rebuild_from_tree()

    def _rebuild_from_tree(self):
        """Rebuild legacy flat lists from hierarchical tree."""
        # Get flattened list of (node, global_pos)
        flat_nodes = self.root.get_flat_list()
        
        new_elements = []
        new_gaps = []
        
        # Filter for elements
        element_nodes = []
        for node, pos in flat_nodes:
            if getattr(node, 'is_element', False):
                element_nodes.append((node, pos))
        
        for i, (node, global_pos) in enumerate(element_nodes):
            lens = getattr(node, 'element_model', None)
            if not lens: continue
            
            # Create LensElement wrapper
            le = LensElement(lens=lens, position=global_pos.x)
            new_elements.append(le)
            
            # Calculate gap to next element
            if i < len(element_nodes) - 1:
                next_node, next_global_pos = element_nodes[i+1]
                
                # Gap starts after current lens
                gap_start = global_pos.x + lens.thickness
                
                # Gap ends at start of next lens
                gap_end = next_global_pos.x
                
                gap_thickness = gap_end - gap_start
                # Ensure non-negative gap
                if gap_thickness < 0:
                     gap_thickness = 0
                
                gap = AirGap(thickness=gap_thickness, position=gap_start)
                new_gaps.append(gap)
        
        self.elements = new_elements
        self.air_gaps = new_gaps

    def _update_positions(self) -> None:
        """Update positions of all elements"""
        current_pos = 0.0
        gap_idx = 0
        
        for i, element in enumerate(self.elements):
            element.position = current_pos
            
            # Update hierarchical node if it exists as direct child
            if i < len(self.root.children):
                node = self.root.children[i]
                node.position = vec3(current_pos, 0, 0)
            
            current_pos += element.thickness
            
            if gap_idx < len(self.air_gaps):
                self.air_gaps[gap_idx].position = current_pos
                current_pos += self.air_gaps[gap_idx].thickness
                gap_idx += 1
    
    def get_total_length(self) -> float:
        """Get total system length"""
        if not self.elements:
            return 0.0
        
        last_element = self.elements[-1]
        return last_element.position + last_element.thickness
    
    def get_system_focal_length(self) -> Optional[float]:
        """
        Calculate system focal length using thin lens approximation
        For thick lenses, this is approximate
        """
        if not self.elements:
            return None
        
        # For single lens, return its focal length
        if len(self.elements) == 1:
            return self.elements[0].lens.calculate_focal_length()
        
        # For two lenses separated by distance d:
        # 1/f = 1/f1 + 1/f2 - d/(f1*f2)
        if len(self.elements) == 2:
            f1 = self.elements[0].lens.calculate_focal_length()
            f2 = self.elements[1].lens.calculate_focal_length()
            
            if f1 is None or f2 is None:
                return None
            
            d = self.air_gaps[0].thickness if self.air_gaps else 0.0
            
            try:
                power = 1/f1 + 1/f2 - d/(f1*f2)
                return 1/power if power != 0 else None
            except (ZeroDivisionError, OverflowError):
                return None
        
        # For more complex systems, use matrix method (simplified)
        return self._calculate_system_focal_length_matrix()
    
    def _calculate_system_focal_length_matrix(self) -> Optional[float]:
        """Calculate focal length using ABCD matrix method"""
        # Start with identity matrix
        A, B, C, D = 1.0, 0.0, 0.0, 1.0
        
        for i, element in enumerate(self.elements):
            f = element.lens.calculate_focal_length()
            if f is None or f == 0:
                continue
            
            # Lens matrix: [1, 0; -1/f, 1]
            A_new = A * 1 + B * (-1/f)
            B_new = A * 0 + B * 1
            C_new = C * 1 + D * (-1/f)
            D_new = C * 0 + D * 1
            
            A, B, C, D = A_new, B_new, C_new, D_new
            
            # Air gap matrix if not last element
            if i < len(self.air_gaps):
                d = self.air_gaps[i].thickness
                # Translation matrix: [1, d; 0, 1]
                A_new = A * 1 + B * 0
                B_new = A * d + B * 1
                C_new = C * 1 + D * 0
                D_new = C * d + D * 1
                
                A, B, C, D = A_new, B_new, C_new, D_new
        
        # Back focal length: f = -1/C
        if C != 0:
            return -1/C
        return None
    
    def get_numerical_aperture(self) -> float:
        """Calculate system numerical aperture (based on first lens)"""
        if not self.elements:
            return 0.0
        
        first_lens = self.elements[0].lens
        f = first_lens.calculate_focal_length()
        if f is None or f == 0:
            return 0.0
        
        return first_lens.diameter / (2 * abs(f))
    
    def calculate_chromatic_aberration(self) -> dict:
        """Calculate chromatic aberration for the system"""
        if not self.elements:
            return {'longitudinal': 0.0, 'corrected': False}
        
        # Calculate for C (656nm) and F (486nm) lines
        wavelengths = [486.1, 587.6, 656.3]  # F, d, C lines
        focal_lengths = []
        
        for wl in wavelengths:
            # Update all lenses for this wavelength
            temp_focal = []
            for element in self.elements:
                lens = element.lens
                original_wl = lens.wavelength
                lens.update_refractive_index(wavelength=wl)
                f = lens.calculate_focal_length()
                temp_focal.append(f)
                lens.update_refractive_index(wavelength=original_wl)  # Restore
            
            # System focal length at this wavelength
            f_system = self.get_system_focal_length()
            focal_lengths.append(f_system)
        
        if None in focal_lengths:
            return {'longitudinal': 0.0, 'corrected': False}
        
        # Longitudinal chromatic aberration
        lca = abs(focal_lengths[2] - focal_lengths[0])  # f_C - f_F
        
        # Well-corrected if LCA < 0.1% of focal length
        corrected = lca < abs(focal_lengths[1] * 0.001) if focal_lengths[1] else False
        
        return {
            'longitudinal': lca,
            'f_F': focal_lengths[0],
            'f_d': focal_lengths[1],
            'f_C': focal_lengths[2],
            'corrected': corrected
        }
    
    def is_achromatic(self) -> bool:
        """Check if system is achromatic (corrected for chromatic aberration)"""
        chrom = self.calculate_chromatic_aberration()
        return chrom['corrected']
    
    def to_dict(self) -> dict:
        """Export system to dictionary"""
        return {
            'name': self.name,
            'elements': [
                {
                    'lens': elem.lens.to_dict(),
                    'position': elem.position
                }
                for elem in self.elements
            ],
            'air_gaps': [
                {
                    'thickness': gap.thickness,
                    'position': gap.position
                }
                for gap in self.air_gaps
            ]
        }
    
    @classmethod
    def from_dict(cls, data: dict):
        """Import system from dictionary"""
        system = cls(name=data.get('name', 'Optical System'))
        
        elements_data = data.get('elements', [])
        gaps_data = data.get('air_gaps', [])
        
        for i, elem_data in enumerate(elements_data):
            lens = Lens.from_dict(elem_data['lens'])
            air_gap = gaps_data[i]['thickness'] if i < len(gaps_data) else 0.0
            system.add_lens(lens, air_gap_before=air_gap if i > 0 else 0.0)
        
        return system
    
    def save(self, filename: str):
        """Save system to JSON file"""
        with open(filename, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
    
    @classmethod
    def load(cls, filename: str):
        """Load system from JSON file"""
        with open(filename, 'r') as f:
            data = json.load(f)
        return cls.from_dict(data)


class AchromaticDoubletDesigner:
    """Design achromatic doublets"""
    
    @staticmethod
    def design_cemented_doublet(focal_length: float, diameter: float,
                               crown_material: str = "BK7",
                               flint_material: str = "SF11") -> OpticalSystem:
        """
        Design a cemented achromatic doublet
        
        Uses the achromatic condition:
        f1/ν1 + f2/ν2 = 0
        1/f = 1/f1 + 1/f2
        
        where ν is the Abbe number
        """
        db = get_material_database()
        
        crown = db.get_material(crown_material)
        flint = db.get_material(flint_material)
        
        if not crown or not flint:
            raise ValueError(f"Materials not found: {crown_material}, {flint_material}")
        
        # Achromatic condition
        v1 = crown.vd
        v2 = flint.vd
        
        # Calculate individual focal lengths
        # f1/v1 + f2/v2 = 0  =>  f2 = -f1 * v2/v1
        # 1/f = 1/f1 + 1/f2  =>  1/f = 1/f1 - v1/(f1*v2)
        # Solving: f1 = f * (1 + v1/v2)
        
        f1 = focal_length * (1 + v1/v2)
        f2 = -f1 * v2/v1
        
        # Calculate radii for each element
        # Using equiconvex/equiconcave approximation
        n1 = crown.nd
        n2 = flint.nd
        
        # For crown (positive): R1 > 0, R2 < 0
        # Lensmaker: 1/f = (n-1)(1/R1 - 1/R2)
        # For symmetric: R1 = -R2 = R
        # 1/f = (n-1)*2/R  =>  R = 2*f*(n-1)
        
        R1_crown = 2 * f1 * (n1 - 1) / 1.5  # Slightly asymmetric for better correction
        R2_crown = -R1_crown * 1.2  # Contact surface (shared with flint)
        
        # Flint element (negative): R1 = R2_crown, R2 > 0
        R1_flint = R2_crown
        R2_flint = 1 / (1/(2*f2*(n2-1)) - 1/R1_flint) if f2 != 0 else -R2_crown * 1.5
        
        # Create lenses
        crown_lens = Lens(
            name=f"{crown_material} Element",
            radius_of_curvature_1=R1_crown,
            radius_of_curvature_2=R2_crown,
            thickness=diameter * 0.15,  # ~15% of diameter
            diameter=diameter,
            material=crown_material,
            wavelength=587.6
        )
        
        flint_lens = Lens(
            name=f"{flint_material} Element",
            radius_of_curvature_1=R1_flint,
            radius_of_curvature_2=R2_flint,
            thickness=diameter * 0.08,  # Thinner flint
            diameter=diameter,
            material=flint_material,
            wavelength=587.6
        )
        
        # Create system
        system = OpticalSystem(name="Achromatic Doublet")
        system.add_lens(crown_lens, air_gap_before=0.0)
        system.add_lens(flint_lens, air_gap_before=0.0)  # Cemented (no gap)
        
        return system
    
    @staticmethod
    def design_air_spaced_doublet(focal_length: float, diameter: float,
                                  spacing: float,
                                  material1: str = "BK7",
                                  material2: str = "SF11") -> OpticalSystem:
        """Design an air-spaced achromatic doublet"""
        
        # Start with cemented design
        system = AchromaticDoubletDesigner.design_cemented_doublet(
            focal_length, diameter, material1, material2
        )
        
        # Modify to add air gap
        if len(system.air_gaps) > 0:
            system.air_gaps[0].thickness = spacing
        
        system._update_positions()
        system.name = "Air-Spaced Achromatic Doublet"
        
        return system


def create_doublet(focal_length: float = 100.0, diameter: float = 50.0) -> OpticalSystem:
    """Quick function to create an achromatic doublet"""
    return AchromaticDoubletDesigner.design_cemented_doublet(focal_length, diameter)


def create_triplet(focal_length: float = 100.0, diameter: float = 50.0) -> OpticalSystem:
    """Create a simple triplet (Cooke triplet approximation)"""
    
    # Simplified Cooke triplet design
    # Positive crown - negative flint - positive crown
    
    f1 = focal_length * 0.6
    f2 = -focal_length * 0.4
    f3 = focal_length * 0.6
    
    lens1 = Lens(
        name="Front Crown",
        radius_of_curvature_1=60,
        radius_of_curvature_2=-60,
        thickness=diameter * 0.1,
        diameter=diameter,
        material="BK7"
    )
    
    lens2 = Lens(
        name="Flint",
        radius_of_curvature_1=-50,
        radius_of_curvature_2=50,
        thickness=diameter * 0.05,
        diameter=diameter * 0.8,
        material="SF11"
    )
    
    lens3 = Lens(
        name="Rear Crown",
        radius_of_curvature_1=60,
        radius_of_curvature_2=-60,
        thickness=diameter * 0.1,
        diameter=diameter,
        material="BK7"
    )
    
    system = OpticalSystem(name="Triplet")
    system.add_lens(lens1, air_gap_before=0)
    system.add_lens(lens2, air_gap_before=diameter * 0.1)
    system.add_lens(lens3, air_gap_before=diameter * 0.1)
    
    return system
