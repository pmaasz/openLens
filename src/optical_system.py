#!/usr/bin/env python3
"""
Multi-element optical system design
Supports compound lenses, doublets, triplets with air gaps
"""

from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass, field
import math
import json
from datetime import datetime

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
    lens_id: Optional[str] = None # Reference to lens ID for database persistence

    def __post_init__(self) -> None:
        """Calculate element thickness and ensure ID is set"""
        self.thickness = self.lens.thickness
        if self.lens_id is None and hasattr(self.lens, 'id'):
            self.lens_id = self.lens.id

    def refresh(self, lens_lookup: Optional[dict] = None) -> None:
        """Update the lens reference if it exists in the lookup table"""
        if lens_lookup and self.lens_id in lens_lookup:
            self.lens = lens_lookup[self.lens_id]
            self.thickness = self.lens.thickness
        else:
            self.thickness = self.lens.thickness


@dataclass
class AirGap:
    """Air gap between lens elements"""
    thickness: float  # mm
    position: float = 0.0

    def __format__(self, format_spec):
        return format(self.thickness, format_spec)


class OpticalSystem:
    """Multi-element optical system"""
    
    def __init__(self, name: str = "Optical System"):
        self.id = datetime.now().strftime("%Y%m%d%H%M%S%f")
        self.created_at = datetime.now().isoformat()
        self.modified_at = datetime.now().isoformat()
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
        
        # Ensure flat list is up to date before adding
        if not self.elements and len(self.root.children) > 0:
             self._rebuild_from_tree()

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

    def remove_lens(self, index: int) -> bool:
        """Remove a lens element by index"""
        if not 0 <= index < len(self.elements):
            return False
            
        # Find all element nodes in the tree
        flat_nodes = self.root.get_flat_list()
        element_nodes = []
        for node, _ in flat_nodes:
            if getattr(node, 'is_element', False):
                element_nodes.append(node)
        
        if 0 <= index < len(element_nodes):
            node_to_remove = element_nodes[index]
            # Find the parent of this node and remove it
            # In a flat hierarchy, it's self.root
            if node_to_remove in self.root.children:
                self.root.children.remove(node_to_remove)
                self._rebuild_from_tree()
                return True
            else:
                # Search deeper if nested (though currently flat by add_lens)
                def find_and_remove(parent, target):
                    if target in parent.children:
                        parent.children.remove(target)
                        return True
                    for child in parent.children:
                        if not getattr(child, 'is_element', False):
                            if find_and_remove(child, target):
                                return True
                    return False
                
                if find_and_remove(self.root, node_to_remove):
                    self._rebuild_from_tree()
                    return True
            
        return False

    def refresh_references(self, lens_lookup: dict) -> None:
        """Update all lens elements with the latest lens references from the lookup table"""
        for element in self.elements:
            element.refresh(lens_lookup)
        self._update_positions()

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
                # Ensure non-negative gap, allowing zero (but not negative)
                if gap_thickness < -1e-12:
                     gap_thickness = 0
                elif abs(gap_thickness) < 1e-12:
                     gap_thickness = 0.0
                
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
    
    def calculate_optical_power(self) -> Optional[float]:
        """Calculate the total optical power of the system in diopters."""
        efl = self.get_system_focal_length()
        if efl is None or abs(efl) < 1e-10:
            return 0.0
        return 1000.0 / efl

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
        
        # For more complex systems, use matrix method
        matrix = self._calculate_system_matrix()
        if not matrix:
            return None
            
        A, B, C, D = matrix
        
        # System Focal Length f = -1 / C
        if abs(C) < 1e-10:
            return None # Infinite focal length (afocal)
            
        return -1.0 / C
    
    def get_system_f_number(self) -> Optional[float]:
        """Calculate system F-number (f/D)"""
        f = self.get_system_focal_length()
        if f is None:
            return None
        
        if not self.elements:
            return None
            
        # Approximation: Use first lens diameter as entrance pupil
        entrance_pupil = self.elements[0].lens.diameter
        if entrance_pupil <= 1e-9:
            return None
            
        return abs(f) / entrance_pupil

    def save(self, filename: str) -> bool:
        """Save optical system to JSON file"""
        try:
            with open(filename, 'w') as f:
                json.dump(self.to_dict(), f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving optical system: {e}")
            return False
            
    def to_dict(self) -> Dict[str, Any]:
        """Convert system to dictionary for serialization"""
        return {
            "id": self.id,
            "name": self.name,
            "created_at": self.created_at,
            "modified_at": self.modified_at,
            "elements": [
                {
                    "lens": e.lens.to_dict(),
                    "position": e.position,
                    "lens_id": e.lens_id
                } for e in self.elements
            ],
            "air_gaps": [
                {
                    "thickness": g.thickness,
                    "position": g.position
                } for g in self.air_gaps
            ]
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'OpticalSystem':
        """Create optical system from dictionary"""
        system = cls(name=data.get("name", "Unnamed System"))
        system.id = data.get("id", system.id)
        system.created_at = data.get("created_at", system.created_at)
        system.modified_at = data.get("modified_at", system.modified_at)
        
        # Load elements
        system.elements = []
        # Clear default root children to avoid duplication if any
        system.root.children = []
        
        gaps_data = data.get("air_gaps", [])
        
        for i, e_data in enumerate(data.get("elements", [])):
            lens_data = e_data.get("lens")
            lens = Lens.from_dict(lens_data)
            
            # Use gap logic consistent with add_lens
            gap_before = 0.0
            if i > 0 and i-1 < len(gaps_data):
                gap_before = gaps_data[i-1].get('thickness', 0.0)
            
            system.add_lens(lens, air_gap_before=gap_before)
            
        return system

    @staticmethod
    def load(filename: str) -> Optional['OpticalSystem']:
        """Load optical system from JSON file"""
        try:
            with open(filename, 'r') as f:
                data = json.load(f)
            return OpticalSystem.from_dict(data)
        except Exception as e:
            print(f"Error loading optical system: {e}")
            return None

    def calculate_chromatic_aberration(self) -> Dict[str, Any]:
        """Calculate system longitudinal chromatic aberration using standard F, d, C lines."""
        # Standard Fraunhofer lines in nm
        lines = {
            'F': 486.1,  # Blue
            'd': 587.6,  # Yellow (Reference)
            'C': 656.3   # Red
        }
        
        bfls = {}
        original_states = []
        
        # Save original wavelengths
        for element in self.elements:
            original_states.append(element.lens.wavelength)
            
        try:
            for line, wl in lines.items():
                for element in self.elements:
                    element.lens.update_refractive_index(wavelength=wl)
                bfls[line] = self.calculate_back_focal_length()
            
            if bfls['F'] is not None and bfls['C'] is not None:
                longitudinal = bfls['C'] - bfls['F']
                return {
                    "longitudinal": longitudinal,
                    "bfl_F": bfls['F'],
                    "bfl_d": bfls['d'],
                    "bfl_C": bfls['C'],
                    "corrected": abs(longitudinal) < 0.1
                }
            return {"longitudinal": 0.0, "corrected": False}
                
        finally:
            # Restore original wavelengths
            for i, element in enumerate(self.elements):
                element.lens.update_refractive_index(wavelength=original_states[i])

    def _calculate_system_matrix(self) -> Optional[Tuple[float, float, float, float]]:
        """Calculate system ray-transfer (ABCD) matrix"""
        if not self.elements:
            return None
            
        # Identity matrix
        A, B, C, D = 1.0, 0.0, 0.0, 1.0
        
        for i, element in enumerate(self.elements):
            # Matrix for thin lens (simplified)
            # This should ideally be the thick lens matrix for accuracy
            f = element.lens.calculate_focal_length()
            if f:
                P = -1.0 / f
                # Lens matrix: [1 0; P 1]
                A_l, B_l, C_l, D_l = 1.0, 0.0, P, 1.0
                # Multiply current matrix by lens matrix
                A, B, C, D = (A_l*A + B_l*C, A_l*B + B_l*D, 
                              C_l*A + D_l*C, C_l*B + D_l*D)
            
            # Gap to next lens
            if i < len(self.elements) - 1:
                d = self.air_gaps[i].thickness
                # Propagation matrix: [1 d; 0 1]
                A_p, B_p, C_p, D_p = 1.0, d, 0.0, 1.0
                # Multiply by propagation matrix
                A, B, C, D = (A_p*A + B_p*C, A_p*B + B_p*D, 
                              C_p*A + D_p*C, C_p*B + D_p*D)
                
        return A, B, C, D
    
    def calculate_back_focal_length(self) -> Optional[float]:
        """Calculate Back Focal Length (BFL) of the system."""
        matrix = self._calculate_system_matrix()
        if not matrix:
            return None
        A, B, C, D = matrix
        if abs(C) < 1e-10:
            return None
        return -A / C
    
    def get_numerical_aperture(self) -> float:
        """Calculate system numerical aperture (based on first lens)"""
        if not self.elements:
            return 0.0
        first_lens = self.elements[0].lens
        f = first_lens.calculate_focal_length()
        if f is None or f == 0:
            return 0.0
        return first_lens.diameter / (2 * abs(f))
    
    def get_f_number(self) -> Optional[float]:
        """Calculate system f-number"""
        f = self.get_system_focal_length()
        if f is None:
            return None
        if not self.elements:
            return None
        entrance_pupil = self.elements[0].lens.diameter
        if entrance_pupil <= 0:
            return None
        return abs(f) / entrance_pupil

class AchromaticDoubletDesigner:
    """Designer for achromatic doublets"""
    pass

def create_doublet(focal_length: float = 100, diameter: float = 50) -> OpticalSystem:
    """Helper to create a doublet"""
    sys = OpticalSystem(name="Doublet")
    l1 = Lens(name="Crown", radius_of_curvature_1=60, radius_of_curvature_2=-60, 
              thickness=5, diameter=diameter, material="BK7")
    l2 = Lens(name="Flint", radius_of_curvature_1=-60, radius_of_curvature_2=-100000, 
              thickness=3, diameter=diameter, material="SF11")
    sys.add_lens(l1)
    sys.add_lens(l2, air_gap_before=0.1)
    return sys

def create_triplet(focal_length: float = 100, diameter: float = 50) -> OpticalSystem:
    """Helper to create a triplet"""
    sys = OpticalSystem(name="Triplet")
    l1 = Lens(name="Outer 1", radius_of_curvature_1=100, radius_of_curvature_2=-100, 
              thickness=5, diameter=diameter, material="BK7")
    l2 = Lens(name="Inner", radius_of_curvature_1=-80, radius_of_curvature_2=80, 
              thickness=3, diameter=diameter, material="SF11")
    l3 = Lens(name="Outer 2", radius_of_curvature_1=100, radius_of_curvature_2=-100, 
              thickness=5, diameter=diameter, material="BK7")
    sys.add_lens(l1)
    sys.add_lens(l2, air_gap_before=5.0)
    sys.add_lens(l3, air_gap_before=5.0)
    return sys

    def calculate_back_focal_length(self) -> Optional[float]:
        """
        Calculate Back Focal Length (BFL) of the system.
        BFL is the distance from the last surface to the back focal point.
        """
        matrix = self._calculate_system_matrix()
        if not matrix:
            return None
            
        A, B, C, D = matrix
        
        if abs(C) < 1e-10:
            return None # Infinite focal length
            
        return -A / C

    def _calculate_system_matrix(self) -> Optional[Tuple[float, float, float, float]]:
        """
        Calculate system ray transfer matrix [A, B; C, D].
        Treats each surface and thickness individually (thick lens model).
        """
        if not self.elements:
            return None

        # Matrix for ray vector [y, u] (height, angle)
        # M = [[A, B], [C, D]]
        # Initial matrix is identity
        A, B, C, D = 1.0, 0.0, 0.0, 1.0
        
        # Current refractive index (starts in air)
        n_current = 1.0
        
        for i, element in enumerate(self.elements):
            lens = element.lens
            n_lens = lens.refractive_index
            
            # Refraction at first surface (air to lens)
            R1 = lens.radius_of_curvature_1
            if R1 != 0:
                # Surface power: (n2 - n1) / R
                P1 = (n_lens - n_current) / R1
                # Refraction matrix: [1 0; P 1]
                A_s, B_s, C_s, D_s = 1.0, 0.0, P1, 1.0
                A, B, C, D = (A_s*A + B_s*C, A_s*B + B_s*D, 
                            C_s*A + D_s*C, C_s*B + D_s*D)
            
            # Propagation through lens thickness
            d = lens.thickness / n_lens  # Effective thickness
            A_p, B_p, C_p, D_p = 1.0, d, 0.0, 1.0
            A, B, C, D = (A_p*A + B_p*C, A_p*B + B_p*D, 
                          C_p*A + D_p*C, C_p*B + D_p*D)
            
            # Refraction at second surface (lens to air)
            R2 = lens.radius_of_curvature_2
            if R2 != 0:
                P2 = (1.0 - n_lens) / R2
                A_s, B_s, C_s, D_s = 1.0, 0.0, P2, 1.0
                A, B, C, D = (A_s*A + B_s*C, A_s*B + B_s*D, 
                            C_s*A + D_s*C, C_s*B + D_s*D)
            
            n_current = 1.0
            
            # Air gap propagation
            if i < len(self.air_gaps):
                d = self.air_gaps[i].thickness
                A_p, B_p, C_p, D_p = 1.0, d, 0.0, 1.0
                A, B, C, D = (A_p*A + B_p*C, A_p*B + B_p*D, 
                              C_p*A + D_p*C, C_p*B + D_p*D)
        
        return A, B, C, D
    
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
            'id': self.id,
            'name': self.name,
            'type': 'OpticalSystem',
            'created_at': self.created_at,
            'modified_at': self.modified_at,
            'elements': [
                {
                    'lens': elem.lens.to_dict(),
                    'lens_id': elem.lens_id or (elem.id if hasattr(elem, 'id') else None),
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
    def from_dict(cls, data: dict, lens_lookup: Optional[dict] = None):
        """Import system from dictionary"""
        system = cls(name=data.get('name', 'Optical System'))
        system.id = data.get('id', system.id)
        system.created_at = data.get('created_at', system.created_at)
        system.modified_at = data.get('modified_at', system.modified_at)
        
        elements_data = data.get('elements', [])
        gaps_data = data.get('air_gaps', [])
        
        for i, elem_data in enumerate(elements_data):
            lens_id = elem_data.get('lens_id')
            if lens_lookup and lens_id in lens_lookup:
                lens = lens_lookup[lens_id]
            else:
                lens = Lens.from_dict(elem_data['lens'])
                
            # Gap logic: 
            # If adding the first lens (i=0), gap_before is 0.
            # If adding subsequent lenses (i>0), gap_before is the gap stored at index i-1.
            air_gap = 0.0
            if i > 0 and i-1 < len(gaps_data):
                air_gap = gaps_data[i-1]['thickness']
                
            system.add_lens(lens, air_gap_before=air_gap)
        
        return system


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
        
        # Power distribution for achromat:
        # P1 = P * V1 / (V1 - V2)
        # P2 = P * V2 / (V2 - V1)
        # f1 = 1/P1, f2 = 1/P2
        
        if v1 == v2:
             # Impossible to achromatize with same Abbe number
             f1 = focal_length * 2
             f2 = focal_length * 2
        else:
            f1 = focal_length * (v1 - v2) / v1
            f2 = focal_length * (v2 - v1) / v2
        
        # Calculate radii for each element
        # Crown (Equiconvex approximation)
        n1 = crown.nd
        n2 = flint.nd
        
        # Lensmaker: 1/f = (n-1)(1/R1 - 1/R2)
        # Equiconvex: R1 = -R2 = 2*f*(n-1)
        
        R1_crown = 2 * f1 * (n1 - 1)
        R2_crown = -R1_crown
        
        # Flint element (negative)
        # Cemented: R1_flint = R2_crown
        R1_flint = R2_crown
        
        # Calculate R2_flint to satisfy f2
        # P2 = 1/f2 = (n2-1)(1/R1_flint - 1/R2_flint)
        # 1/f2 / (n2-1) = 1/R1_flint - 1/R2_flint
        # 1/R2_flint = 1/R1_flint - 1/(f2*(n2-1))
        
        term = 1.0/(f2 * (n2 - 1))
        inv_R2 = (1.0 / R1_flint) - term
        
        if abs(inv_R2) < 1e-10:
             R2_flint = 0.0 # Planar? Or infinite?
             # For this codebase, let's use a very large number for infinity
             R2_flint = 1e10
        else:
             R2_flint = 1.0 / inv_R2
        
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
    # Powers chosen to roughly sum to 1/f with spacing
    
    f1 = focal_length * 0.75
    f2 = -focal_length * 0.5
    f3 = focal_length * 0.75
    
    # Calculate radii
    # Lens 1 (BK7): Equiconvex
    n_bk7 = 1.5168
    r1_crown = 2 * f1 * (n_bk7 - 1)
    
    # Lens 2 (SF11): Equiconcave
    n_sf11 = 1.7847
    r_flint = 2 * abs(f2) * (n_sf11 - 1)
    
    lens1 = Lens(
        name="Front Crown",
        radius_of_curvature_1=r1_crown,
        radius_of_curvature_2=-r1_crown,
        thickness=diameter * 0.1,
        diameter=diameter,
        material="BK7"
    )
    
    lens2 = Lens(
        name="Flint",
        radius_of_curvature_1=-r_flint,
        radius_of_curvature_2=r_flint,
        thickness=diameter * 0.05,
        diameter=diameter * 0.8,
        material="SF11"
    )
    
    lens3 = Lens(
        name="Rear Crown",
        radius_of_curvature_1=r1_crown,
        radius_of_curvature_2=-r1_crown,
        thickness=diameter * 0.1,
        diameter=diameter,
        material="BK7"
    )
    
    system = OpticalSystem(name="Triplet")
    
    # Air gaps roughly 10% of focal length or based on diameter
    gap = focal_length * 0.05
    
    system.add_lens(lens1, air_gap_before=0)
    system.add_lens(lens2, air_gap_before=gap)
    system.add_lens(lens3, air_gap_before=gap)
    
    return system
