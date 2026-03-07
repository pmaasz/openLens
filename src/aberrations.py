#!/usr/bin/env python3
"""
Lens Aberrations Calculator
Calculates primary optical aberrations for single lens elements
"""

import math
from typing import Optional, Dict, Any

# Import constants
try:
    from .constants import (
        AIRY_DISK_FACTOR,
        SPHERICAL_ABERRATION_EXCELLENT,
        QUALITY_EXCELLENT_THRESHOLD, QUALITY_GOOD_THRESHOLD, QUALITY_FAIR_THRESHOLD,
        WAVELENGTH_GREEN,
        REFRACTIVE_INDEX_AIR,
        EPSILON,
    )
except ImportError:
    from constants import (
        AIRY_DISK_FACTOR,
        SPHERICAL_ABERRATION_EXCELLENT,
        QUALITY_EXCELLENT_THRESHOLD, QUALITY_GOOD_THRESHOLD, QUALITY_FAIR_THRESHOLD,
        WAVELENGTH_GREEN,
        REFRACTIVE_INDEX_AIR,
        EPSILON,
    )

# Airy disk diameter factor (not radius)
# The Airy disk DIAMETER = 2.44 * λ * f/#
# AIRY_DISK_FACTOR from constants is 1.22 (for radius), so we need 2.44 for diameter
AIRY_DISK_DIAMETER_FACTOR = 2.44


class AberrationsCalculator:
    """
    Calculate primary (Seidel) aberrations for a single lens element.
    
    The five primary aberrations are:
    1. Spherical Aberration (SA)
    2. Coma
    3. Astigmatism
    4. Field Curvature
    5. Distortion
    
    Additionally calculates chromatic aberration when Abbe number is available.
    """
    
    def __init__(self, lens: Any) -> None:
        """
        Initialize calculator with a lens object.
        
        Args:
            lens: Lens object with optical parameters (radius_of_curvature_1,
                  radius_of_curvature_2, thickness, diameter, refractive_index)
        """
        self.lens = lens
        self.n = lens.refractive_index
        self.R1 = lens.radius_of_curvature_1
        self.R2 = lens.radius_of_curvature_2
        self.d = lens.thickness
        self.D = lens.diameter
        
    def calculate_all_aberrations(self, 
                                   object_distance: Optional[float] = None,
                                   field_angle: float = 0.0) -> Dict[str, Any]:
        """
        Calculate all primary aberrations.
        
        Args:
            object_distance: Distance to object in mm. None for infinity (collimated light)
            field_angle: Off-axis angle in degrees (for coma, astigmatism, distortion)
            
        Returns:
            Dictionary with aberration values and optical parameters
        """
        focal_length = self.lens.calculate_focal_length()
        
        if focal_length is None:
            return {
                'focal_length': None,
                'spherical_aberration': None,
                'coma': None,
                'astigmatism': None,
                'field_curvature': None,
                'distortion': None,
                'chromatic_aberration': None,
                'error': 'Cannot calculate focal length (zero optical power)'
            }
        
        # Calculate numerical aperture and other parameters
        na = self._calculate_numerical_aperture(focal_length)
        
        return {
            'focal_length': focal_length,
            'numerical_aperture': na,
            'f_number': self._calculate_f_number(focal_length),
            'spherical_aberration': self._calculate_spherical_aberration(focal_length),
            'coma': self._calculate_coma(focal_length, field_angle),
            'astigmatism': self._calculate_astigmatism(focal_length, field_angle),
            'field_curvature': self._calculate_field_curvature(focal_length),
            'distortion': self._calculate_distortion(focal_length, field_angle),
            'chromatic_aberration': self._calculate_chromatic_aberration(focal_length),
            'airy_disk_diameter': self._calculate_airy_disk(focal_length)
        }
    
    def _calculate_numerical_aperture(self, focal_length: float) -> float:
        """
        Calculate numerical aperture NA = n_medium * sin(θ) where θ = arctan(D/2f).
        
        For a lens in air, the numerical aperture uses the medium refractive index (air = 1.0),
        NOT the lens material's refractive index.
        
        Args:
            focal_length: Focal length in mm
            
        Returns:
            Numerical aperture (dimensionless)
        """
        if focal_length == 0:
            return 0
        # Use air refractive index (1.0), not lens material index
        theta = math.atan(self.D / (2 * abs(focal_length)))
        return REFRACTIVE_INDEX_AIR * math.sin(theta)
    
    def _calculate_f_number(self, focal_length: float) -> float:
        """
        Calculate f-number (f/#) = f/D.
        
        Args:
            focal_length: Focal length in mm
            
        Returns:
            F-number (dimensionless)
        """
        if self.D == 0:
            return float('inf')
        return abs(focal_length) / self.D
    
    def _calculate_spherical_aberration(self, focal_length: float) -> float:
        """
        Calculate longitudinal spherical aberration (LSA).
        
        Uses the third-order Seidel spherical aberration coefficient for a thin lens.
        The formula accounts for both shape factor (q) and position factor (p).
        
        For collimated light (object at infinity), position factor p = -1.
        
        The shape factor q = (R2 + R1) / (R2 - R1) determines the lens bend.
        
        LSA = (y^2 / (2*f)) * S_I
        
        where S_I is the Seidel spherical aberration coefficient depending on
        shape factor, position factor, and refractive index.
        
        Returns:
            Longitudinal spherical aberration in mm
        """
        if abs(focal_length) < EPSILON:
            return 0
            
        # Shape factor: q = (R2 + R1) / (R2 - R1)
        denominator = self.R2 - self.R1
        if abs(denominator) < EPSILON:
            # Handle degenerate cases
            if abs(self.R1) > 1e6 and abs(self.R2) > 1e6:
                shape_factor = 0  # Flat plate
            else:
                shape_factor = 0  # Fallback for meniscus with R1 ≈ R2
        else:
            shape_factor = (self.R2 + self.R1) / denominator
        
        # Aperture radius
        y = self.D / 2
        
        n = self.n
        
        # For object at infinity, position factor p = -1
        p = -1.0
        
        # Guard against n = 1 (would cause division by zero)
        if abs(n - 1.0) < EPSILON:
            return 0
        
        # Third-order spherical aberration coefficient (Seidel)
        # This is a more complete formula that includes shape and position factors
        # Based on: S_I = (1/4) * [(n+2)/(n(n-1)^2)] * q^2 + [(3n+2)(n-1)/(n(n-1)^2)] * p*q + ...
        # Simplified form for practical calculation:
        
        # Optimal shape factor for minimum spherical aberration (object at infinity):
        # q_opt = -2(n^2 - 1) / (n + 2)
        q_opt = -2 * (n * n - 1) / (n + 2)
        
        # Spherical aberration coefficient (proportional to deviation from optimal shape)
        # Using the formula: K ∝ (n / (n-1)^2) * f(q, p, n)
        K_base = n / (8 * (n - 1) ** 2)
        
        # Shape-dependent term (simplified but physically motivated)
        # SA is minimized at q_opt and increases quadratically with deviation
        shape_term = 1.0 + (shape_factor - q_opt) ** 2 / 4.0
        
        K = K_base * shape_term
        
        # Longitudinal spherical aberration
        # LSA = -K * y^4 / f^3
        lsa = -K * (y ** 4) / (abs(focal_length) ** 3)
        
        return lsa
    
    def _calculate_coma(self, focal_length: float, field_angle_deg: float) -> float:
        """
        Calculate coma aberration.
        
        Coma varies linearly with field angle and with cube of aperture.
        Tangential coma: TCO ∝ y³ * θ / f²
        
        Args:
            focal_length: Focal length in mm
            field_angle_deg: Field angle in degrees
            
        Returns:
            Tangential coma coefficient (relative units)
        """
        if focal_length == 0 or field_angle_deg == 0:
            return 0
        
        field_angle_rad = math.radians(field_angle_deg)
        y = self.D / 2
        
        # Shape factor
        # q = (R2 + R1) / (R2 - R1)
        denominator = self.R2 - self.R1
        
        if abs(denominator) < 1e-9:
            shape_factor = 0
        else:
            shape_factor = (self.R2 + self.R1) / denominator
        
        # Coma coefficient (simplified)
        n = self.n
        K_coma = (n / (2 * (n - 1))) * shape_factor
        
        coma = K_coma * (y**3) * field_angle_rad / (abs(focal_length)**2)
        
        return coma
    
    def _calculate_astigmatism(self, focal_length: float, field_angle_deg: float) -> float:
        """
        Calculate astigmatism.
        
        Astigmatism causes point sources to appear as lines.
        AST ∝ θ² / f
        
        Args:
            focal_length: Focal length in mm
            field_angle_deg: Field angle in degrees
            
        Returns:
            Astigmatic focal difference in mm
        """
        if focal_length == 0 or field_angle_deg == 0:
            return 0
        
        field_angle_rad = math.radians(field_angle_deg)
        
        # Simplified astigmatism formula
        # Astigmatic difference between sagittal and tangential foci
        astigmatism = abs(focal_length) * (field_angle_rad**2) / (2 * self.n)
        
        return astigmatism
    
    def _calculate_field_curvature(self, focal_length: float) -> float:
        """
        Calculate Petzval field curvature.
        
        The Petzval surface is curved, causing off-axis points to focus
        on a curved surface rather than a flat plane.
        
        Petzval sum for single lens: P = 1/(n*f)
        Petzval radius of curvature: R_p = 1/P = n*f
        
        For converging lenses (positive f), the Petzval radius is positive
        (curved toward the lens). For diverging lenses, it's negative.
        
        Returns:
            Petzval radius of curvature in mm
        """
        if focal_length == 0:
            return 0
        
        # Petzval radius preserving sign information
        # R_p = n * f (not -abs(f)*n which was incorrect)
        petzval_radius = self.n * focal_length
        
        return petzval_radius
    
    def _calculate_distortion(self, focal_length: float, field_angle_deg: float) -> float:
        """
        Calculate distortion (barrel or pincushion).
        
        Distortion ∝ θ³
        
        Positive = pincushion distortion
        Negative = barrel distortion
        
        Args:
            focal_length: Focal length in mm
            field_angle_deg: Field angle in degrees
            
        Returns:
            Distortion coefficient (%)
        """
        if focal_length == 0 or field_angle_deg == 0:
            return 0
        
        field_angle_rad = math.radians(field_angle_deg)
        
        # Shape factor determines sign of distortion
        # q = (R2 + R1) / (R2 - R1)
        denominator = self.R2 - self.R1
        
        if abs(denominator) < 1e-9:  # Avoid division by zero
            # For flat plate (R1=R2=inf) or meniscus with R1=R2
            shape_factor = 0
        else:
            shape_factor = (self.R2 + self.R1) / denominator
        
        # Simplified distortion coefficient
        distortion_pct = shape_factor * (field_angle_rad**3) * 100
        
        return distortion_pct
    
    def _calculate_chromatic_aberration(self, focal_length: float) -> Optional[float]:
        """
        Calculate longitudinal chromatic aberration (LCA).
        
        Chromatic aberration occurs because refractive index varies with wavelength.
        
        For accurate calculation, we need the Abbe number (V_d).
        Since we don't have it in the lens object, we'll use typical values
        based on material, or provide an estimate.
        
        LCA = f / V_d
        
        Returns:
            Longitudinal chromatic aberration in mm, or None if Abbe number unknown
        """
        # Typical Abbe numbers for common materials
        abbe_numbers = {
            'BK7': 64.17,  # Standard crown glass
            'Fused Silica': 67.8,  # Low dispersion
            'Crown Glass': 60.0,
            'Flint Glass': 36.0,
            'SF11': 25.76,
            'Sapphire': 72.0
        }
        
        material = self.lens.material
        abbe_number = abbe_numbers.get(material)
        
        if abbe_number is None:
            # Estimate based on refractive index
            # Higher index generally means lower Abbe number
            if self.n < 1.5:  # Low index glass
                abbe_number = 65  # Low dispersion
            elif self.n < 1.6:  # Medium index
                abbe_number = 55  # Medium dispersion
            elif self.n < 1.7:  # Higher index
                abbe_number = 40  # Higher dispersion
            else:
                abbe_number = 30  # High dispersion (flint glass)
        
        # Longitudinal chromatic aberration
        lca = abs(focal_length) / abbe_number
        
        return lca
    
    def _calculate_airy_disk(self, focal_length: float, wavelength: float = WAVELENGTH_GREEN * 1e-6) -> float:
        """
        Calculate Airy disk diameter (diffraction-limited spot size).
        
        Airy disk diameter = 2.44 * λ * f/# 
        
        Note: The factor 2.44 is for DIAMETER. The first zero of the Airy pattern
        occurs at 1.22 * λ * f/# from the center (radius), so the diameter is 2.44.
        
        Args:
            focal_length: Focal length in mm
            wavelength: Wavelength in mm (default 550nm = 0.000550mm green light)
            
        Returns:
            Airy disk diameter in mm
        """
        f_number = self._calculate_f_number(focal_length)
        
        if f_number == float('inf'):
            return 0
        
        # Use 2.44 for diameter (not 1.22 which is for radius)
        airy_diameter = AIRY_DISK_DIAMETER_FACTOR * wavelength * f_number
        
        return airy_diameter
    
    def get_aberration_summary(self,
                               object_distance: Optional[float] = None,
                               field_angle: float = 5.0) -> str:
        """
        Get a formatted summary of all aberrations.
        
        Args:
            object_distance: Distance to object (mm). None for infinity
            field_angle: Off-axis angle in degrees
            
        Returns:
            Formatted string with aberration summary
        """
        results = self.calculate_all_aberrations(object_distance, field_angle)
        
        if results.get('error'):
            return f"Error: {results['error']}"
        
        f = results['focal_length']
        
        summary = f"""
╔═══════════════════════════════════════════════════════════════╗
║              LENS ABERRATIONS ANALYSIS                        ║
╠═══════════════════════════════════════════════════════════════╣
║ Lens: {self.lens.name:<52} ║
║ Material: {self.lens.material:<48} ║
╠═══════════════════════════════════════════════════════════════╣
║ BASIC PARAMETERS                                              ║
╠═══════════════════════════════════════════════════════════════╣
║ Focal Length:          {f:>10.2f} mm                      ║
║ F-number (f/#):        {results['f_number']:>10.2f}                          ║
║ Numerical Aperture:    {results['numerical_aperture']:>10.4f}                          ║
║ Airy Disk Diameter:    {results['airy_disk_diameter']:>10.6f} mm (diffraction limit) ║
╠═══════════════════════════════════════════════════════════════╣
║ PRIMARY ABERRATIONS (Seidel)                                  ║
╠═══════════════════════════════════════════════════════════════╣
║ Spherical Aberration:  {results['spherical_aberration']:>10.4f} mm (longitudinal)      ║
║ Coma (@ {field_angle}°):         {results['coma']:>10.4f} (relative)              ║
║ Astigmatism (@ {field_angle}°):  {results['astigmatism']:>10.4f} mm                       ║
║ Field Curvature:       {results['field_curvature']:>10.2f} mm (Petzval radius)     ║
║ Distortion (@ {field_angle}°):   {results['distortion']:>10.4f} %                        ║
╠═══════════════════════════════════════════════════════════════╣
║ CHROMATIC ABERRATION                                          ║
╠═══════════════════════════════════════════════════════════════╣
║ Longitudinal CA:       {results['chromatic_aberration']:>10.4f} mm (focal shift)        ║
╚═══════════════════════════════════════════════════════════════╝

INTERPRETATION:
• Spherical Aberration: {'Negligible' if abs(results['spherical_aberration']) < 0.001 else 'Moderate' if abs(results['spherical_aberration']) < 0.01 else 'Significant'}
  ({abs(results['spherical_aberration']):.4f} mm - {'rays focus at different points' if results['spherical_aberration'] != 0 else 'well corrected'})

• Chromatic Aberration: {'Negligible' if results['chromatic_aberration'] < 0.1 else 'Moderate' if results['chromatic_aberration'] < 0.5 else 'Significant'}
  ({results['chromatic_aberration']:.4f} mm - {'color fringing minimal' if results['chromatic_aberration'] < 0.1 else 'visible color fringing'})

• Distortion: {'None' if abs(results['distortion']) < 0.1 else 'Barrel' if results['distortion'] < 0 else 'Pincushion'}
  ({abs(results['distortion']):.2f}% - {'straight lines appear' + (' curved inward' if results['distortion'] < 0 else ' curved outward') if abs(results['distortion']) > 0.1 else 'minimal'})

• Resolution Limit: {results['airy_disk_diameter']*1000:.2f} μm (diffraction-limited spot size)
"""
        
        return summary


def analyze_lens_quality(lens: Any, field_angle: float = 5.0) -> Dict[str, Any]:
    """
    Convenience function to analyze lens quality.
    
    Args:
        lens: Lens object
        field_angle: Field angle for off-axis aberrations (degrees)
        
    Returns:
        Dictionary with quality assessment
    """
    calc = AberrationsCalculator(lens)
    results = calc.calculate_all_aberrations(field_angle=field_angle)
    
    if results.get('error'):
        return {'quality_score': 0, 'rating': 'Error', 'issues': [results['error']]}
    
    issues = []
    score = 100
    
    # Evaluate spherical aberration
    sa = abs(results['spherical_aberration'])
    if sa > SPHERICAL_ABERRATION_EXCELLENT:
        issues.append(f"High spherical aberration ({sa:.4f} mm)")
        score -= 20  # Major SA penalty
    elif sa > (SPHERICAL_ABERRATION_EXCELLENT / 10):
        issues.append(f"Moderate spherical aberration ({sa:.4f} mm)")
        score -= 10  # Minor SA penalty
    
    # Evaluate chromatic aberration
    ca = results['chromatic_aberration']
    if ca > 0.5:  # Significant chromatic aberration
        issues.append(f"High chromatic aberration ({ca:.4f} mm)")
        score -= 20  # Major SA penalty
    elif ca > 0.1:
        issues.append(f"Moderate chromatic aberration ({ca:.4f} mm)")
        score -= 10  # Minor SA penalty
    
    # Evaluate distortion
    dist = abs(results['distortion'])
    if dist > 5:
        issues.append(f"High distortion ({dist:.2f}%)")
        score -= 15  # Astigmatism penalty
    elif dist > 1:
        issues.append(f"Moderate distortion ({dist:.2f}%)")
        score -= 5
    
    # Evaluate astigmatism
    ast = results['astigmatism']
    if ast > 1.0:  # Large astigmatism
        issues.append(f"High astigmatism ({ast:.4f} mm)")
        score -= 15  # Astigmatism penalty
    elif ast > 0.1:  # Moderate astigmatism
        issues.append(f"Moderate astigmatism ({ast:.4f} mm)")
        score -= 5
    
    # Determine rating
    if score >= (QUALITY_EXCELLENT_THRESHOLD + 5):  # 90
        rating = "Excellent"
    elif score >= (QUALITY_GOOD_THRESHOLD + 5):  # 75
        rating = "Good"
    elif score >= (QUALITY_FAIR_THRESHOLD + 10):  # 60
        rating = "Fair"
    elif score >= (QUALITY_FAIR_THRESHOLD - 10):  # 40
        rating = "Poor"
    else:
        rating = "Very Poor"
    
    return {
        'quality_score': score,
        'rating': rating,
        'issues': issues if issues else ["No significant aberrations detected"],
        'aberrations': results
    }
