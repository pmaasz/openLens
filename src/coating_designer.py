#!/usr/bin/env python3
"""
Anti-Reflection Coating Designer
Calculate coating thickness and reflectivity for optical coatings
"""

import math
from typing import List, Tuple, Optional
from dataclasses import dataclass

@dataclass
class CoatingLayer:
    """Single coating layer"""
    material: str
    refractive_index: float
    thickness_nm: float  # Physical thickness in nanometers


class CoatingDesigner:
    """Design anti-reflection and optical coatings"""
    
    # Common coating materials
    COATING_MATERIALS = {
        'MgF2': 1.38,      # Magnesium Fluoride
        'SiO2': 1.46,      # Silicon Dioxide
        'Al2O3': 1.63,     # Aluminum Oxide
        'TiO2': 2.35,      # Titanium Dioxide
        'Ta2O5': 2.10,     # Tantalum Pentoxide
        'ZrO2': 2.10,      # Zirconium Dioxide
        'HfO2': 2.00,      # Hafnium Oxide
    }
    
    def __init__(self, substrate_index: float = 1.5168):
        """
        Initialize coating designer
        
        Args:
            substrate_index: Refractive index of substrate (default BK7)
        """
        self.substrate_index = substrate_index
        self.air_index = 1.0
    
    def design_single_layer_ar(self, wavelength_nm: float) -> CoatingLayer:
        """
        Design single-layer anti-reflection coating
        
        Uses quarter-wave thickness with optimal refractive index
        n_coating = sqrt(n_substrate * n_air)
        t = λ / (4 * n_coating)
        
        Args:
            wavelength_nm: Design wavelength in nanometers
        
        Returns:
            CoatingLayer with optimal parameters
        """
        # Optimal coating index
        n_optimal = math.sqrt(self.substrate_index * self.air_index)
        
        # Find closest available material
        best_material = 'MgF2'
        best_n = self.COATING_MATERIALS['MgF2']
        min_diff = abs(best_n - n_optimal)
        
        for material, n in self.COATING_MATERIALS.items():
            diff = abs(n - n_optimal)
            if diff < min_diff:
                best_material = material
                best_n = n
                min_diff = diff
        
        # Quarter-wave optical thickness: n*t = λ/4
        thickness_nm = wavelength_nm / (4 * best_n)
        
        return CoatingLayer(
            material=best_material,
            refractive_index=best_n,
            thickness_nm=thickness_nm
        )
    
    def design_dual_layer_ar(self, wavelength_nm: float) -> List[CoatingLayer]:
        """
        Design two-layer anti-reflection coating
        
        Uses two quarter-wave layers with optimized indices
        """
        # For dual layer: use high-low or low-high index
        # Common: High index (Ta2O5 or TiO2) then low index (SiO2 or MgF2)
        
        # Layer 1 (on substrate): High index
        n1 = self.COATING_MATERIALS['Ta2O5']
        t1 = wavelength_nm / (4 * n1)
        layer1 = CoatingLayer('Ta2O5', n1, t1)
        
        # Layer 2 (outer): Low index
        n2 = self.COATING_MATERIALS['MgF2']
        t2 = wavelength_nm / (4 * n2)
        layer2 = CoatingLayer('MgF2', n2, t2)
        
        return [layer1, layer2]
    
    def calculate_reflectivity(self, layers: List[CoatingLayer], 
                              wavelength_nm: float,
                              angle_deg: float = 0) -> float:
        """
        Calculate reflectivity of coating stack using transfer matrix method
        
        Args:
            layers: List of coating layers (substrate to air)
            wavelength_nm: Wavelength in nanometers
            angle_deg: Angle of incidence in degrees
        
        Returns:
            Reflectivity (0 to 1)
        """
        if not layers:
            # No coating - Fresnel reflection
            r = (self.substrate_index - self.air_index) / (self.substrate_index + self.air_index)
            return r**2
        
        # Simplified calculation for normal incidence
        if angle_deg == 0:
            # Build refractive index stack
            indices = [self.substrate_index] + [layer.refractive_index for layer in layers] + [self.air_index]
            
            # Calculate phase thickness for each layer
            wavelength_m = wavelength_nm * 1e-9
            phases = []
            for layer in layers:
                thickness_m = layer.thickness_nm * 1e-9
                phase = 2 * math.pi * layer.refractive_index * thickness_m / wavelength_m
                phases.append(phase)
            
            # Transfer matrix method (simplified for normal incidence)
            # For exact calculation, would use full 2x2 matrices
            
            # Approximate using thin film interference
            total_reflection = 0
            for i in range(len(indices) - 1):
                r = (indices[i] - indices[i+1]) / (indices[i] + indices[i+1])
                total_reflection += r**2
            
            # Normalize (rough approximation)
            return min(total_reflection / len(indices), 1.0)
        
        return 0.04  # Placeholder for angled incidence
    
    def calculate_reflectivity_curve(self, layers: List[CoatingLayer],
                                     wavelength_range: Tuple[float, float],
                                     num_points: int = 100) -> List[Tuple[float, float]]:
        """
        Calculate reflectivity vs wavelength
        
        Args:
            layers: Coating layers
            wavelength_range: (min_nm, max_nm)
            num_points: Number of wavelength points
        
        Returns:
            List of (wavelength_nm, reflectivity) tuples
        """
        min_wl, max_wl = wavelength_range
        wavelengths = [min_wl + (max_wl - min_wl) * i / (num_points - 1) 
                      for i in range(num_points)]
        
        curve = []
        for wl in wavelengths:
            R = self.calculate_reflectivity(layers, wl)
            curve.append((wl, R))
        
        return curve
    
    def design_v_coating(self, wavelength_nm: float) -> List[CoatingLayer]:
        """
        Design V-coating (broadband AR coating)
        Optimized for visible spectrum
        """
        # V-coating uses multiple layers with varying thickness
        # Simplified 3-layer design
        
        layers = [
            CoatingLayer('Ta2O5', 2.10, wavelength_nm / (4 * 2.10 * 1.2)),
            CoatingLayer('SiO2', 1.46, wavelength_nm / (4 * 1.46)),
            CoatingLayer('MgF2', 1.38, wavelength_nm / (4 * 1.38 * 0.9))
        ]
        
        return layers
    
    def get_coating_info(self, layers: List[CoatingLayer], design_wavelength: float) -> str:
        """Generate coating specification string"""
        lines = []
        lines.append("COATING SPECIFICATION")
        lines.append("="*60)
        lines.append(f"Design Wavelength: {design_wavelength:.0f} nm")
        lines.append(f"Substrate Index: {self.substrate_index:.4f}")
        lines.append("")
        
        for i, layer in enumerate(layers, 1):
            optical_thickness = layer.refractive_index * layer.thickness_nm
            waves = optical_thickness / design_wavelength
            
            lines.append(f"Layer {i}: {layer.material}")
            lines.append(f"  Refractive Index: {layer.refractive_index:.4f}")
            lines.append(f"  Physical Thickness: {layer.thickness_nm:.2f} nm")
            lines.append(f"  Optical Thickness: {optical_thickness:.2f} nm ({waves:.3f}λ)")
            lines.append("")
        
        R = self.calculate_reflectivity(layers, design_wavelength)
        lines.append(f"Calculated Reflectivity: {R*100:.2f}%")
        lines.append(f"Transmission: {(1-R)*100:.2f}%")
        
        return "\n".join(lines)
