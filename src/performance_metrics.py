#!/usr/bin/env python3
"""
Performance Metrics Calculator
Calculate professional optical specifications
"""

import math
from typing import Optional, Dict

try:
    from .lens_editor import Lens
    from .optical_system import OpticalSystem
except (ImportError, ValueError):
    import sys
    import os
    sys.path.insert(0, os.path.dirname(__file__))
    from lens_editor import Lens
    from optical_system import OpticalSystem


class PerformanceMetrics:
    """Calculate optical performance metrics"""
    
    def __init__(self, lens_or_system):
        """
        Initialize with either a Lens or OpticalSystem
        """
        if isinstance(lens_or_system, Lens):
            self.lens = lens_or_system
            self.system = None
        elif isinstance(lens_or_system, OpticalSystem):
            self.lens = None
            self.system = lens_or_system
        else:
            raise ValueError("Must provide Lens or OpticalSystem")
    
    def calculate_f_number(self) -> Optional[float]:
        """
        Calculate f-number (f/#)
        f/# = f / D
        where f is focal length, D is entrance pupil diameter
        """
        if self.lens:
            f = self.lens.calculate_focal_length()
            D = self.lens.diameter
        elif self.system:
            f = self.system.get_system_focal_length()
            D = self.system.elements[0].lens.diameter if self.system.elements else None
        else:
            return None
        
        if f and D and D > 0:
            return abs(f) / D
        return None
    
    def calculate_numerical_aperture(self) -> Optional[float]:
        """
        Calculate numerical aperture (NA)
        NA = n * sin(θ)
        For small angles: NA ≈ D / (2f)
        """
        if self.lens:
            f = self.lens.calculate_focal_length()
            D = self.lens.diameter
            n = self.lens.refractive_index
        elif self.system:
            f = self.system.get_system_focal_length()
            if self.system.elements:
                D = self.system.elements[0].lens.diameter
                n = 1.0  # Air
            else:
                return None
        else:
            return None
        
        if f and D and abs(f) > 0:
            # Small angle approximation
            na = D / (2 * abs(f))
            return min(na, 1.0)  # Can't exceed 1.0 in air
        return None
    
    def calculate_back_focal_length(self) -> Optional[float]:
        """
        Calculate back focal length (BFL)
        Distance from last surface to focal point
        """
        if self.lens:
            # For thin lens: BFL ≈ EFL - thickness/2
            f = self.lens.calculate_focal_length()
            if f:
                return f - self.lens.thickness / 2
        elif self.system:
            # For system: focal point distance from last surface
            f = self.system.get_system_focal_length()
            if f and self.system.elements:
                last_elem = self.system.elements[-1]
                # Approximate: system focal length - distance to last surface
                return f
        return None
    
    def calculate_working_distance(self, magnification: float = 1.0) -> Optional[float]:
        """
        Calculate working distance for given magnification
        WD = f * (1 + 1/M)
        """
        if self.lens:
            f = self.lens.calculate_focal_length()
        elif self.system:
            f = self.system.get_system_focal_length()
        else:
            return None
        
        if f and magnification != 0:
            return abs(f) * (1 + 1/magnification)
        return None
    
    def calculate_magnification(self, object_distance: float) -> Optional[float]:
        """
        Calculate magnification for given object distance
        M = -v/u = f/(f-u)
        """
        if self.lens:
            f = self.lens.calculate_focal_length()
        elif self.system:
            f = self.system.get_system_focal_length()
        else:
            return None
        
        if f and object_distance != f:
            return f / (f - object_distance)
        return None
    
    def calculate_resolution_rayleigh(self) -> Optional[float]:
        """
        Calculate Rayleigh resolution limit (angular)
        θ = 1.22 * λ / D (radians)
        Returns resolution in microradians
        """
        wavelength = 550e-6  # Default 550nm in mm
        
        if self.lens:
            D = self.lens.diameter
            if hasattr(self.lens, 'wavelength'):
                wavelength = self.lens.wavelength / 1000.0  # nm to mm
        elif self.system and self.system.elements:
            D = self.system.elements[0].lens.diameter
        else:
            return None
        
        if D > 0:
            theta_rad = 1.22 * wavelength / D
            return theta_rad * 1e6  # Convert to microradians
        return None
    
    def calculate_airy_disk_radius(self) -> Optional[float]:
        """
        Calculate Airy disk radius at focal plane
        r = 1.22 * λ * f / D (mm)
        """
        wavelength = 550e-6  # Default 550nm in mm
        
        if self.lens:
            f = self.lens.calculate_focal_length()
            D = self.lens.diameter
            if hasattr(self.lens, 'wavelength'):
                wavelength = self.lens.wavelength / 1000.0
        elif self.system:
            f = self.system.get_system_focal_length()
            D = self.system.elements[0].lens.diameter if self.system.elements else None
        else:
            return None
        
        if f and D and D > 0:
            return 1.22 * wavelength * abs(f) / D
        return None
    
    def calculate_depth_of_field(self, object_distance: float, 
                                 circle_of_confusion: float = 0.03) -> Optional[Dict[str, float]]:
        """
        Calculate depth of field
        CoC: circle of confusion in mm (0.03mm is typical for 35mm film)
        """
        f_number = self.calculate_f_number()
        
        if self.lens:
            f = self.lens.calculate_focal_length()
        elif self.system:
            f = self.system.get_system_focal_length()
        else:
            return None
        
        if not (f and f_number and object_distance > 0):
            return None
        
        # Hyperfocal distance
        H = f**2 / (f_number * circle_of_confusion) + f
        
        # Near and far limits
        if object_distance < H:
            near = (object_distance * (H - f)) / (H + object_distance - 2*f)
            far = (object_distance * (H - f)) / (H - object_distance)
        else:
            near = H / 2
            far = float('inf')
        
        dof = far - near if far != float('inf') else float('inf')
        
        return {
            'near': near,
            'far': far,
            'total': dof,
            'hyperfocal': H
        }
    
    def get_all_metrics(self) -> Dict[str, any]:
        """Get all available performance metrics"""
        metrics = {}
        
        # Basic metrics
        metrics['f_number'] = self.calculate_f_number()
        metrics['numerical_aperture'] = self.calculate_numerical_aperture()
        metrics['back_focal_length'] = self.calculate_back_focal_length()
        metrics['working_distance_1x'] = self.calculate_working_distance(1.0)
        
        # Resolution
        metrics['rayleigh_limit_urad'] = self.calculate_resolution_rayleigh()
        metrics['airy_disk_radius_mm'] = self.calculate_airy_disk_radius()
        
        # Focal length
        if self.lens:
            metrics['focal_length'] = self.lens.calculate_focal_length()
            metrics['entrance_pupil_diameter'] = self.lens.diameter
        elif self.system:
            metrics['focal_length'] = self.system.get_system_focal_length()
            metrics['system_length'] = self.system.get_total_length()
            if self.system.elements:
                metrics['entrance_pupil_diameter'] = self.system.elements[0].lens.diameter
        
        return metrics
