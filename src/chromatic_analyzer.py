#!/usr/bin/env python3
"""
Chromatic Aberration Analyzer
Performs wavelength-dependent ray tracing and dispersion analysis
"""

import math
from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass
from material_database import MaterialDatabase


@dataclass
class ChromaticResult:
    """Results from chromatic analysis"""
    wavelengths: List[float]  # nm
    focal_lengths: List[float]  # mm
    focal_shift: float  # mm (difference between red and blue)
    lateral_color: float  # mm (at image plane)
    spot_sizes: List[float]  # mm (for each wavelength)
    transverse_aberration: List[float]  # mm
    axial_chromatic_aberration: float  # mm
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            'wavelengths': self.wavelengths,
            'focal_lengths': self.focal_lengths,
            'focal_shift': self.focal_shift,
            'lateral_color': self.lateral_color,
            'spot_sizes': self.spot_sizes,
            'transverse_aberration': self.transverse_aberration,
            'axial_chromatic_aberration': self.axial_chromatic_aberration
        }


class ChromaticAnalyzer:
    """Analyzes chromatic aberration and wavelength-dependent behavior"""
    
    # Standard spectral lines
    WAVELENGTHS = {
        'i': 365.0,   # Mercury i-line (UV)
        'h': 404.7,   # Mercury h-line (violet)
        'g': 435.8,   # Mercury g-line (blue)
        'F': 486.1,   # Hydrogen F-line (blue)
        'd': 587.6,   # Helium d-line (yellow) - reference
        'D': 589.3,   # Sodium D-line (yellow)
        'e': 546.1,   # Mercury e-line (green)
        'C': 656.3,   # Hydrogen C-line (red)
        'r': 706.5,   # Helium r-line (red)
        's': 852.1,   # Cesium s-line (near IR)
        't': 1014.0   # Mercury t-line (near IR)
    }
    
    def __init__(self, material_db: Optional[MaterialDatabase] = None):
        self.material_db = material_db or MaterialDatabase()
    
    def analyze_lens(self, lens_params: dict, 
                     wavelengths: Optional[List[float]] = None,
                     num_rays: int = 11,
                     temperature_c: float = 20.0) -> ChromaticResult:
        """
        Analyze chromatic aberration for a lens
        
        Args:
            lens_params: Dictionary with lens parameters
            wavelengths: List of wavelengths in nm (defaults to F, d, C lines)
            num_rays: Number of rays to trace per wavelength
            temperature_c: Temperature in Celsius
        
        Returns:
            ChromaticResult with analysis data
        """
        if wavelengths is None:
            # Use primary spectral lines (blue, yellow, red)
            wavelengths = [self.WAVELENGTHS['F'], 
                          self.WAVELENGTHS['d'], 
                          self.WAVELENGTHS['C']]
        
        focal_lengths = []
        spot_sizes = []
        transverse_aberrations = []
        
        material_name = lens_params.get('material', 'BK7')
        
        for wavelength in wavelengths:
            # Get wavelength-dependent refractive index
            n = self.material_db.get_refractive_index(
                material_name, wavelength, temperature_c
            )
            
            # Calculate focal length using lensmaker's equation
            # 1/f = (n-1)[1/R1 - 1/R2 + (n-1)d/(nR1R2)]
            R1 = lens_params.get('radius1', 50.0)
            R2 = lens_params.get('radius2', -50.0)
            d = lens_params.get('thickness', 5.0)
            
            # Simplified lensmaker's equation (thin lens approximation)
            focal_length = 1.0 / ((n - 1) * (1/R1 - 1/R2))
            
            # Estimate spot size based on spherical aberration
            spot_size = abs(focal_length) * 0.001  # Rough estimate
            
            # Estimate transverse aberration
            transverse_ab = abs(focal_length) * 0.002
            
            focal_lengths.append(focal_length)
            spot_sizes.append(spot_size)
            transverse_aberrations.append(transverse_ab)
        
        # Calculate chromatic aberration metrics
        focal_shift = max(focal_lengths) - min(focal_lengths)
        axial_chromatic = abs(focal_lengths[0] - focal_lengths[-1])
        
        # Lateral color (difference in image height for off-axis rays)
        lateral_color = abs(transverse_aberrations[0] - transverse_aberrations[-1])
        
        return ChromaticResult(
            wavelengths=wavelengths,
            focal_lengths=focal_lengths,
            focal_shift=focal_shift,
            lateral_color=lateral_color,
            spot_sizes=spot_sizes,
            transverse_aberration=transverse_aberrations,
            axial_chromatic_aberration=axial_chromatic
        )
    
    def calculate_abbe_number(self, material_name: str) -> float:
        """
        Calculate Abbe number (V_d) from material data
        V_d = (n_d - 1) / (n_F - n_C)
        """
        n_d = self.material_db.get_refractive_index(material_name, self.WAVELENGTHS['d'])
        n_F = self.material_db.get_refractive_index(material_name, self.WAVELENGTHS['F'])
        n_C = self.material_db.get_refractive_index(material_name, self.WAVELENGTHS['C'])
        
        return (n_d - 1.0) / (n_F - n_C)
    
    def calculate_partial_dispersion(self, material_name: str, 
                                     line1: str = 'g', 
                                     line2: str = 'F') -> float:
        """
        Calculate partial dispersion P_x,y = (n_x - n_y) / (n_F - n_C)
        """
        n_x = self.material_db.get_refractive_index(material_name, self.WAVELENGTHS[line1])
        n_y = self.material_db.get_refractive_index(material_name, self.WAVELENGTHS[line2])
        n_F = self.material_db.get_refractive_index(material_name, self.WAVELENGTHS['F'])
        n_C = self.material_db.get_refractive_index(material_name, self.WAVELENGTHS['C'])
        
        return (n_x - n_y) / (n_F - n_C)
    
    def design_achromatic_doublet(self, focal_length: float,
                                  crown_material: str = 'BK7',
                                  flint_material: str = 'F2') -> Dict:
        """
        Design an achromatic doublet to correct chromatic aberration
        
        Args:
            focal_length: Desired focal length in mm
            crown_material: Low dispersion glass (crown)
            flint_material: High dispersion glass (flint)
        
        Returns:
            Dictionary with lens parameters for both elements
        """
        # Get Abbe numbers
        V1 = self.calculate_abbe_number(crown_material)
        V2 = self.calculate_abbe_number(flint_material)
        
        # Get refractive indices at d-line
        n1 = self.material_db.get_refractive_index(crown_material, self.WAVELENGTHS['d'])
        n2 = self.material_db.get_refractive_index(flint_material, self.WAVELENGTHS['d'])
        
        # Calculate power distribution (thin lens approximation)
        # For achromatic doublet: φ1/V1 + φ2/V2 = 0
        # φ1 + φ2 = 1/f
        
        phi_total = 1.0 / focal_length
        phi1 = phi_total * V1 / (V1 - V2)
        phi2 = phi_total * V2 / (V2 - V1)
        
        # Focal lengths of individual elements
        f1 = 1.0 / phi1 if phi1 != 0 else float('inf')
        f2 = 1.0 / phi2 if phi2 != 0 else float('inf')
        
        return {
            'crown_element': {
                'focal_length': f1,
                'power': phi1,
                'material': crown_material,
                'n': n1,
                'abbe_number': V1
            },
            'flint_element': {
                'focal_length': f2,
                'power': phi2,
                'material': flint_material,
                'n': n2,
                'abbe_number': V2
            },
            'total_focal_length': focal_length,
            'total_power': phi_total
        }
    
    def plot_chromatic_focal_shift(self, lens_params: dict,
                                   wavelength_range: Tuple[float, float] = (400, 700),
                                   num_points: int = 50) -> Dict[str, List[float]]:
        """
        Calculate focal length vs wavelength
        
        Returns:
            Dictionary with 'wavelengths' and 'focal_lengths' lists
        """
        wavelengths = []
        focal_lengths = []
        
        material_name = lens_params.get('material', 'BK7')
        wl_min, wl_max = wavelength_range
        
        for i in range(num_points):
            wl = wl_min + (wl_max - wl_min) * i / (num_points - 1)
            n = self.material_db.get_refractive_index(material_name, wl)
            
            # Calculate focal length using lensmaker's equation
            R1 = lens_params.get('radius1', 50.0)
            R2 = lens_params.get('radius2', -50.0)
            
            focal_length = 1.0 / ((n - 1) * (1/R1 - 1/R2))
            
            wavelengths.append(wl)
            focal_lengths.append(focal_length)
        
        return {
            'wavelengths': wavelengths,
            'focal_lengths': focal_lengths
        }
