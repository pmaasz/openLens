#!/usr/bin/env python3
"""
Performance Metrics Calculator
Calculate professional optical specifications
"""

import math
from typing import Optional, Dict, Any

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
    
    def calculate_f_number(self, entrance_pupil_diameter: Optional[float] = None) -> Optional[float]:
        """
        Calculate f-number (f/#)
        f/# = f / D
        where f is focal length, D is entrance pupil diameter
        
        Args:
            entrance_pupil_diameter: Optional custom entrance pupil diameter (mm)
        """
        if self.lens:
            f = self.lens.calculate_focal_length()
            D = entrance_pupil_diameter if entrance_pupil_diameter else self.lens.diameter
        elif self.system:
            f = self.system.get_system_focal_length()
            if entrance_pupil_diameter:
                D = entrance_pupil_diameter
            elif self.system.elements:
                D = self.system.elements[0].lens.diameter
            else:
                D = None
        else:
            return None
        
        if f and D and D > 0:
            return abs(f) / D
        return None
    
    def calculate_numerical_aperture(self, half_angle_deg: Optional[float] = None, 
                                     medium_index: float = 1.0) -> Optional[float]:
        """
        Calculate numerical aperture (NA)
        NA = n * sin(θ)
        
        Args:
            half_angle_deg: Half-angle of the maximum cone of light (degrees)
                           If not provided, calculates from f-number
            medium_index: Refractive index of the medium (default 1.0 for air)
        
        Returns:
            Numerical aperture value
        """
        if half_angle_deg is not None:
            # Direct calculation from half-angle
            theta_rad = math.radians(half_angle_deg)
            return medium_index * math.sin(theta_rad)
        
        # Calculate from lens geometry
        if self.lens:
            f = self.lens.calculate_focal_length()
            D = self.lens.diameter
        elif self.system:
            f = self.system.get_system_focal_length()
            if self.system.elements:
                D = self.system.elements[0].lens.diameter
            else:
                return None
        else:
            return None
        
        if f and D and abs(f) > 0:
            # NA = sin(arctan(D/(2f))) ≈ D/(2f) for small angles
            half_angle = math.atan(D / (2 * abs(f)))
            na = medium_index * math.sin(half_angle)
            return min(na, medium_index)  # Can't exceed medium index
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
    
    def estimate_resolution_rayleigh(self, wavelength: float = 550.0, 
                                     f_number: Optional[float] = None) -> Optional[float]:
        """
        Estimate spatial resolution using Rayleigh criterion
        
        Args:
            wavelength: Wavelength in nanometers
            f_number: F-number (if not provided, calculated from lens)
        
        Returns:
            Resolution in micrometers (μm)
        """
        if f_number is None:
            f_number = self.calculate_f_number()
        
        if f_number is None or f_number <= 0:
            return None
        
        # Rayleigh resolution: r = 1.22 * λ * f/#
        # wavelength in nm, result in μm
        wavelength_um = wavelength / 1000.0  # nm to μm
        resolution_um = 1.22 * wavelength_um * f_number
        
        return resolution_um
    
    def estimate_mtf_cutoff(self, wavelength: float = 550.0,
                           f_number: Optional[float] = None) -> Optional[float]:
        """
        Estimate MTF (Modulation Transfer Function) cutoff frequency
        
        The diffraction-limited MTF cutoff is:
        fc = 1 / (λ * f/#) in cycles per unit length
        
        Args:
            wavelength: Wavelength in nanometers
            f_number: F-number (if not provided, calculated from lens)
        
        Returns:
            MTF cutoff frequency in line pairs per millimeter (lp/mm)
        """
        if f_number is None:
            f_number = self.calculate_f_number()
        
        if f_number is None or f_number <= 0:
            return None
        
        # Convert wavelength from nm to mm
        wavelength_mm = wavelength * 1e-6
        
        # MTF cutoff: fc = 1 / (λ * f/#)
        mtf_cutoff = 1.0 / (wavelength_mm * f_number)
        
        return mtf_cutoff
    
    def calculate_airy_disk_radius(self, wavelength: float = 550.0) -> Optional[float]:
        """
        Calculate Airy disk radius at focal plane
        r = 1.22 * λ * f / D (mm)
        
        Args:
            wavelength: Wavelength in nanometers (default 550nm)
        
        Returns:
            Airy disk radius in mm
        """
        wavelength_mm = wavelength * 1e-6  # nm to mm
        
        if self.lens:
            f = self.lens.calculate_focal_length()
            D = self.lens.diameter
        elif self.system:
            f = self.system.get_system_focal_length()
            D = self.system.elements[0].lens.diameter if self.system.elements else None
        else:
            return None
        
        if f and D and D > 0:
            return 1.22 * wavelength_mm * abs(f) / D
        return None
    
    def calculate_field_of_view(self, sensor_size: float) -> Optional[float]:
        """
        Calculate field of view for a given sensor size
        
        FOV = 2 * arctan(sensor_size / (2 * f))
        
        Args:
            sensor_size: Sensor diagonal or dimension in mm
        
        Returns:
            Field of view in degrees
        """
        if self.lens:
            f = self.lens.calculate_focal_length()
        elif self.system:
            f = self.system.get_system_focal_length()
        else:
            return None
        
        if f is None or abs(f) < 0.001:
            return None
        
        # FOV = 2 * arctan(d / 2f)
        fov_rad = 2 * math.atan(sensor_size / (2 * abs(f)))
        fov_deg = math.degrees(fov_rad)
        
        return fov_deg
    
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
    
    def get_all_metrics(self, entrance_pupil_diameter: Optional[float] = None,
                        wavelength: float = 550.0,
                        object_distance: float = 1000.0,
                        sensor_size: float = 36.0) -> Dict[str, Any]:
        """
        Get all available performance metrics
        
        Args:
            entrance_pupil_diameter: Entrance pupil diameter in mm (defaults to lens diameter)
            wavelength: Wavelength in nm (default 550nm green)
            object_distance: Object distance in mm for DOF calculation
            sensor_size: Sensor size in mm for FOV calculation
        
        Returns:
            Dictionary with all calculated metrics
        """
        metrics = {}
        
        # Focal length
        if self.lens:
            metrics['effective_focal_length'] = self.lens.calculate_focal_length()
            metrics['entrance_pupil_diameter'] = entrance_pupil_diameter or self.lens.diameter
        elif self.system:
            metrics['effective_focal_length'] = self.system.get_system_focal_length()
            metrics['system_length'] = self.system.get_total_length()
            if self.system.elements:
                metrics['entrance_pupil_diameter'] = entrance_pupil_diameter or self.system.elements[0].lens.diameter
        
        # Basic metrics
        metrics['f_number'] = self.calculate_f_number(entrance_pupil_diameter)
        metrics['numerical_aperture'] = self.calculate_numerical_aperture()
        metrics['back_focal_length'] = self.calculate_back_focal_length()
        metrics['working_distance_1x'] = self.calculate_working_distance(1.0)
        
        # Resolution metrics
        f_num = metrics['f_number']
        metrics['resolution_um'] = self.estimate_resolution_rayleigh(wavelength, f_num)
        metrics['mtf_cutoff_lpmm'] = self.estimate_mtf_cutoff(wavelength, f_num)
        metrics['rayleigh_limit_urad'] = self.calculate_resolution_rayleigh()
        metrics['airy_disk_radius_mm'] = self.calculate_airy_disk_radius(wavelength)
        
        # Field of view
        metrics['field_of_view_deg'] = self.calculate_field_of_view(sensor_size)
        
        # Depth of field
        dof = self.calculate_depth_of_field(object_distance)
        if dof:
            metrics['dof_near_mm'] = dof['near']
            metrics['dof_far_mm'] = dof['far']
            metrics['dof_total_mm'] = dof['total']
            metrics['hyperfocal_mm'] = dof['hyperfocal']
        
        return metrics
    
    def format_metrics_report(self, metrics: Optional[Dict[str, Any]] = None) -> str:
        """
        Format metrics into a readable report
        
        Args:
            metrics: Dictionary of metrics (if None, calculates fresh)
        
        Returns:
            Formatted string report
        """
        if metrics is None:
            metrics = self.get_all_metrics()
        
        lines = []
        lines.append("=" * 50)
        lines.append("    PERFORMANCE METRICS DASHBOARD")
        lines.append("=" * 50)
        lines.append("")
        
        # Focal length and f-number
        lines.append("BASIC OPTICAL PARAMETERS")
        lines.append("-" * 30)
        
        if 'effective_focal_length' in metrics and metrics['effective_focal_length']:
            lines.append(f"  Effective Focal Length: {metrics['effective_focal_length']:.2f} mm")
        
        if 'f_number' in metrics and metrics['f_number']:
            lines.append(f"  F-Number:               f/{metrics['f_number']:.2f}")
        
        if 'numerical_aperture' in metrics and metrics['numerical_aperture']:
            lines.append(f"  Numerical Aperture:     {metrics['numerical_aperture']:.4f}")
        
        if 'back_focal_length' in metrics and metrics['back_focal_length']:
            lines.append(f"  Back Focal Length:      {metrics['back_focal_length']:.2f} mm")
        
        if 'entrance_pupil_diameter' in metrics and metrics['entrance_pupil_diameter']:
            lines.append(f"  Entrance Pupil:         {metrics['entrance_pupil_diameter']:.2f} mm")
        
        lines.append("")
        lines.append("RESOLUTION & IMAGE QUALITY")
        lines.append("-" * 30)
        
        if 'resolution_um' in metrics and metrics['resolution_um']:
            lines.append(f"  Resolution (Rayleigh):  {metrics['resolution_um']:.3f} μm")
        
        if 'mtf_cutoff_lpmm' in metrics and metrics['mtf_cutoff_lpmm']:
            lines.append(f"  MTF Cutoff:             {metrics['mtf_cutoff_lpmm']:.1f} lp/mm")
        
        if 'airy_disk_radius_mm' in metrics and metrics['airy_disk_radius_mm']:
            airy_um = metrics['airy_disk_radius_mm'] * 1000  # mm to μm
            lines.append(f"  Airy Disk Radius:       {airy_um:.3f} μm")
        
        lines.append("")
        lines.append("FIELD & DEPTH")
        lines.append("-" * 30)
        
        if 'field_of_view_deg' in metrics and metrics['field_of_view_deg']:
            lines.append(f"  Field of View:          {metrics['field_of_view_deg']:.2f}°")
        
        if 'dof_near_mm' in metrics and metrics['dof_near_mm']:
            near = metrics['dof_near_mm']
            far = metrics.get('dof_far_mm', float('inf'))
            far_str = f"{far:.1f}" if far != float('inf') else "∞"
            lines.append(f"  Depth of Field:         {near:.1f} mm to {far_str} mm")
        
        if 'hyperfocal_mm' in metrics and metrics['hyperfocal_mm']:
            lines.append(f"  Hyperfocal Distance:    {metrics['hyperfocal_mm']:.1f} mm")
        
        if 'working_distance_1x' in metrics and metrics['working_distance_1x']:
            lines.append(f"  Working Distance (1x):  {metrics['working_distance_1x']:.2f} mm")
        
        lines.append("")
        lines.append("=" * 50)
        
        return "\n".join(lines)
