#!/usr/bin/env python3
"""
Lens Aberrations Calculator
Calculates primary optical aberrations for single lens elements
"""

import math
from typing import Optional, Dict, Any, List, Tuple

# Import ray tracer for exact calculations
try:
    from .ray_tracer import LensRayTracer, Ray
except ImportError:
    # Handle circular imports or running as script
    try:
        from ray_tracer import LensRayTracer, Ray
    except ImportError:
        LensRayTracer = None
        Ray = None

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
    Calculate primary (Seidel) aberrations for a single lens element or an optical system.
    
    The five primary aberrations are:
    1. Spherical Aberration (SA)
    2. Coma
    3. Astigmatism
    4. Field Curvature
    5. Distortion
    
    Additionally calculates chromatic aberration when Abbe number is available.
    """
    
    def __init__(self, target: Any) -> None:
        """
        Initialize calculator with a lens or an optical system.
        
        Args:
            target: Lens object or OpticalSystem object.
        """
        self.target = target
        # Check if target is an OpticalSystem (has elements)
        if hasattr(target, 'elements'):
            self.is_system = True
            # For system calculations, use effective properties
            self.n = 1.0 # System in air
            self.D = target.elements[0].lens.diameter if target.elements else 25.0
            # focal_length = target.get_system_focal_length()
        else:
            self.is_system = False
            self.lens = target
            self.n = target.refractive_index
            self.R1 = target.radius_of_curvature_1
            self.R2 = target.radius_of_curvature_2
            self.d = target.thickness
            self.D = target.diameter
        
    def calculate_all_aberrations(self, 
                                   object_distance_mm: Optional[float] = None,
                                   field_angle_deg: float = 0.0,
                                   wavelength_nm: float = 550.0) -> Dict[str, Any]:
        """
        Calculate all primary aberrations.
        
        Args:
            object_distance_mm: Distance to object in mm. None for infinity (collimated light)
            field_angle_deg: Off-axis angle in degrees (for coma, astigmatism, distortion)
            wavelength_nm: Wavelength in nm (for chromatic aberrations)
            
        Returns:
            Dictionary with aberration values and optical parameters
        """
        # Note: Current simplified model uses primary wavelength for Seidel aberrations
        # Future enhancement: Update refractive indices based on wavelength parameter
        if self.is_system:
            focal_length = self.target.get_system_focal_length()
        else:
            focal_length = self.lens.calculate_focal_length()
        
        if focal_length is None:
            return {
                'focal_length': None,
                'spherical': None,
                'spherical_aberration': None,
                'coma': None,
                'astigmatism': None,
                'field_curvature': None,
                'distortion': None,
                'chromatic': None,
                'chromatic_aberration': None,
                'error': 'Cannot calculate focal length (zero optical power)'
            }
        
        # Calculate numerical aperture and other parameters
        na = self._calculate_numerical_aperture(focal_length)
        
        if self.is_system:
            # For systems, we primarily rely on exact calculations where possible
            field_data = self._calculate_field_metrics_system(field_angle_deg)
            return {
                'focal_length': focal_length,
                'numerical_aperture': na,
                'f_number': self._calculate_f_number(focal_length),
                'spherical': self._calculate_spherical_aberration(focal_length),
                'spherical_aberration': self._calculate_spherical_aberration(focal_length),
                'coma': field_data['coma'],
                'astigmatism': field_data['astigmatism'],
                'field_curvature': field_data['field_curvature'],
                'distortion': field_data['distortion'],
                'chromatic': self._calculate_chromatic_aberration(focal_length),
                'chromatic_aberration': self._calculate_chromatic_aberration(focal_length),
                'airy_disk_diameter': self._calculate_airy_disk(focal_length),
                'spot_rms': self._calculate_spot_rms() if self.is_system else 0,
                'strehl': self._calculate_strehl_ratio(focal_length),
                'mtf_cutoff': self._calculate_mtf_cutoff(focal_length)
            }

        return {
            'focal_length': focal_length,
            'numerical_aperture': na,
            'f_number': self._calculate_f_number(focal_length),
            'spherical': self._calculate_spherical_aberration(focal_length),
            'spherical_aberration': self._calculate_spherical_aberration(focal_length),
            'coma': self._calculate_coma(focal_length, field_angle_deg),
            'astigmatism': self._calculate_astigmatism(focal_length, field_angle_deg),
            'field_curvature': self._calculate_field_curvature(focal_length),
            'distortion': self._calculate_distortion(focal_length, field_angle_deg),
            'chromatic': self._calculate_chromatic_aberration(focal_length),
            'chromatic_aberration': self._calculate_chromatic_aberration(focal_length),
            'airy_disk_diameter': self._calculate_airy_disk(focal_length),
            'strehl': self._calculate_strehl_ratio(focal_length),
            'mtf_cutoff': self._calculate_mtf_cutoff(focal_length)
        }
    
    def _calculate_f_number(self, focal_length: float) -> float:
        """Calculate the f-number (f/D)"""
        if self.D <= 0:
            return float('inf')
        return abs(focal_length) / self.D

    def _calculate_numerical_aperture(self, focal_length: float) -> float:
        """Calculate the numerical aperture (NA)"""
        if abs(focal_length) < EPSILON:
            return 0.0
        # For object at infinity: NA = D / (2 * f)
        return self.D / (2 * abs(focal_length))

    def _calculate_field_metrics_system(self, field_angle: float) -> Dict[str, float]:
        """Calculate field-dependent aberrations for an optical system using real ray tracing"""
        try:
            from .analysis.geometric import GeometricTraceAnalysis
            analysis = GeometricTraceAnalysis(self.target)
            
            # 1. Field Curvature and Distortion
            # Sample up to field_angle
            fc_data = analysis.calculate_field_curvature_distortion(
                max_field_angle=max(field_angle, 0.1),
                num_points=10
            )
            
            # 2. Coma (from Ray Fan)
            fan_data = analysis.calculate_ray_fan(field_angle=field_angle)
            
            # Extract metrics at the requested field_angle
            # fc_data['tan_focus_shift'] etc are lists, we want the last element if we sampled up to field_angle
            field_curv = fc_data['tan_focus_shift'][-1] if fc_data['tan_focus_shift'] else 0.0
            dist = fc_data['distortion_pct'][-1] if fc_data['distortion_pct'] else 0.0
            astig = abs(fc_data['tan_focus_shift'][-1] - fc_data['sag_focus_shift'][-1]) if fc_data['tan_focus_shift'] and fc_data['sag_focus_shift'] else 0.0
            
            # Coma estimation from ray fan (asymmetry in transverse error)
            errors = fan_data['ray_errors']
            coma_val = 0.0
            if len(errors) >= 2:
                # Coma ~= (y_top + y_bottom) / 2 - y_chief
                # Ray fan returns errors relative to chief ray, so coma is (error_top + error_bottom)/2
                coma_val = (errors[0] + errors[-1]) / 2.0
                
            return {
                'field_curvature': field_curv,
                'distortion': dist,
                'astigmatism': astig,
                'coma': coma_val
            }
        except Exception:
            return {'field_curvature': 0.0, 'distortion': 0.0, 'astigmatism': 0.0, 'coma': 0.0}

    def _calculate_coma(self, focal_length: float, field_angle_deg: float) -> float:
        """Calculate third-order Seidel coma for a single lens"""
        # Third-order Seidel approximation fallback
        if abs(focal_length) < EPSILON or field_angle_deg == 0:
            return 0.0
            
        # Coma depends on Shape Factor (B) and Conjugate Factor (C)
        # B = (R2 + R1) / (R2 - R1)
        if abs(self.R2 - self.R1) < EPSILON:
            B = 0.0
        else:
            B = (self.R2 + self.R1) / (self.R2 - self.R1)
            
        # For object at infinity, C = -1
        C = -1.0
        
        # Coma S2 = (y^3 * field_angle / f^2) * [(n+1)/n * B + (2n+1)/n * C]
        # (Simplified relative value)
        n = self.n
        factor = ((n + 1.0) / n) * B + ((2.0 * n + 1.0) / n) * C
        coma = ( (self.D/2.0)**3 * math.radians(field_angle_deg) / focal_length**2 ) * factor
        return coma

    def _calculate_astigmatism(self, focal_length: float, field_angle_deg: float) -> float:
        """
        Calculate third-order Seidel astigmatism for a single lens.
        
        For a single thin lens with the stop at the lens, the Seidel coefficient S3
        depends only on the field angle and the optical power.
        
        Transverse Astigmatism (AS) = (y * field_angle^2) / 2
        Longitudinal Astigmatism (L-AS) = f * field_angle^2
        """
        if abs(field_angle_deg) < EPSILON:
            return 0.0
            
        field_angle_rad = math.radians(field_angle_deg)
        
        # Longitudinal astigmatism for a thin lens at the stop is simply f * theta^2
        # according to the Seidel contribution S_III = h_p^2 * phi.
        # Shift in focus: delta_L = f * theta^2
        return focal_length * (field_angle_rad**2)

    def _calculate_field_curvature(self, focal_length: float) -> float:
        """Calculate Petzval field curvature for a single lens"""
        # Petzval Radius R_p = n * f (for a single thin lens)
        return self.n * focal_length

    def _calculate_distortion(self, focal_length: float, field_angle_deg: float) -> float:
        """
        Calculate third-order Seidel distortion for a single lens.
        
        For a single thin lens with the stop AT the lens, the Seidel distortion 
        coefficient S5 is zero. Distortion typically arises when the stop is 
        shifted away from the lens.
        """
        return 0.0

    def calculate_ray_fan(self, 
                          field_angle_deg: float = 0.0, 
                          wavelength_nm: float = 550.0,
                          num_points: int = 21,
                          pupil_axis: str = 'y') -> Dict[str, Any]:
        """
        Interface for calculating ray fan.
        """
        from .analysis.geometric import GeometricTraceAnalysis
        from .optical_system import OpticalSystem
        
        if self.is_system:
            system = self.target
        else:
            system = OpticalSystem(name=self.lens.name)
            system.add_lens(self.lens)
            
        analysis = GeometricTraceAnalysis(system)
        return analysis.calculate_ray_fan(field_angle_deg=field_angle_deg, wavelength_nm=wavelength_nm, num_points=num_points, pupil_axis=pupil_axis)

    def calculate_field_curvature(self, 
                                  max_field_angle_deg: float = 20.0, 
                                  num_points: int = 11,
                                  wavelength_nm: float = 550.0) -> Tuple[List[float], List[float], List[float]]:
        """
        Interface for field curvature calculation.
        Returns (angles_deg, sag_shift_mm, tan_shift_mm)
        """
        from .analysis.geometric import GeometricTraceAnalysis
        from .optical_system import OpticalSystem
        
        if self.is_system:
            system = self.target
        else:
            system = OpticalSystem(name=self.lens.name)
            system.add_lens(self.lens)
            
        analysis = GeometricTraceAnalysis(system)
        data = analysis.calculate_field_curvature_distortion(max_field_angle_deg=max_field_angle_deg, num_points=num_points, wavelength_nm=wavelength_nm)
        return data['field_angles_deg'], data['sag_focus_shift_mm'], data['tan_focus_shift_mm']

    def calculate_distortion_curve(self, 
                                   max_field_angle_deg: float = 20.0, 
                                   num_points: int = 11,
                                   wavelength_nm: float = 550.0) -> Tuple[List[float], List[float]]:
        """
        Interface for distortion curve calculation.
        Returns (angles_deg, distortion_pct)
        """
        from .analysis.geometric import GeometricTraceAnalysis
        from .optical_system import OpticalSystem
        
        if self.is_system:
            system = self.target
        else:
            system = OpticalSystem(name=self.lens.name)
            system.add_lens(self.lens)
            
        analysis = GeometricTraceAnalysis(system)
        data = analysis.calculate_field_curvature_distortion(max_field_angle_deg=max_field_angle_deg, num_points=num_points, wavelength_nm=wavelength_nm)
        return data['field_angles_deg'], data['distortion_pct']
    
    def _calculate_strehl_ratio(self, focal_length: float) -> float:
        """Estimate Strehl ratio from wavefront error/spot size"""
        # Simplified estimation: Strehl ~= exp(-(2*pi*RMS_OPD)^2)
        # For now, return a placeholder based on spot size vs airy disk
        spot_rms = self._calculate_spot_rms() if self.is_system else 5.0 # Placeholder for single lens
        airy_r = self._calculate_airy_disk(focal_length) * 500 # diameter/2 in um
        if airy_r <= 0: return 0
        ratio = airy_r / max(airy_r, spot_rms)
        return min(1.0, ratio**2)

    def _calculate_mtf_cutoff(self, focal_length: float) -> float:
        """Calculate diffraction-limited MTF cutoff frequency in lp/mm"""
        f_num = self._calculate_f_number(focal_length)
        if f_num <= 0: return 0
        wavelength = WAVELENGTH_GREEN * 1e-6 # mm
        return 1.0 / (wavelength * f_num)
    
    def _calculate_spot_rms(self) -> float:
        """Calculate RMS spot size using ray tracing (System only)"""
        if not self.is_system: return 0
        try:
            from .ray_tracer import SystemRayTracer
            tracer = SystemRayTracer(self.target)
            rays = tracer.trace_parallel_rays(num_rays=21)
            
            # Find best focus (minimum RMS)
            # Simplified: calculate at paraxial focus
            f = self.target.get_system_focal_length()
            if not f: return 0
            
            # Use back focal length or last element position + f
            bfl = self.target.calculate_back_focal_length()
            if not bfl: return 0
            
            last_elem = self.target.elements[-1]
            focus_x = last_elem.position + last_elem.thickness + bfl
            
            y_hits = []
            for ray in rays:
                if not ray.terminated:
                    # Propagate to focus_x
                    dist = focus_x - ray.x
                    y_at_focus = ray.y + dist * math.tan(ray.angle)
                    y_hits.append(y_at_focus)
            
            if not y_hits: return 0
            
            mean_y = sum(y_hits) / len(y_hits)
            rms = math.sqrt(sum((y - mean_y)**2 for y in y_hits) / len(y_hits))
            return rms * 1000 # convert to um
        except:
            return 0

    def _calculate_spherical_aberration(self, focal_length: float) -> float:
        """
        Calculate longitudinal spherical aberration (LSA).
        
        Attempts to use exact ray tracing first. If ray tracing fails or
        dependencies are missing, falls back to third-order Seidel approximation.
        
        LSA = Marginal Focus - Paraxial Focus
        
        For Seidel approximation:
        LSA = -K * y^4 / f^3
        
        Returns:
            Longitudinal spherical aberration in mm
        """
        if abs(focal_length) < EPSILON:
            return 0
            
        # Try exact calculation first
        exact_lsa = self._calculate_spherical_aberration_exact()
        if exact_lsa is not None:
            return exact_lsa
            
        # Fallback to Seidel approximation (only for single lens)
        if not self.is_system:
            return self._calculate_spherical_aberration_seidel(focal_length)
        return 0

    def _calculate_spherical_aberration_exact(self) -> Optional[float]:
        """
        Calculate LSA using exact ray tracing.
        Returns None if calculation fails (e.g. TIR, missing dependencies).
        """
        if LensRayTracer is None or Ray is None:
            return None
            
        try:
            if self.is_system:
                from .ray_tracer import SystemRayTracer
                tracer = SystemRayTracer(self.target)
                
                # Trace Marginal Ray
                y_marginal = self.D / 2.0 * 0.99
                ray_m = Ray(self.target.elements[0].position - 10, y_marginal, angle_rad=0.0)
                tracer._trace_ray_through_system(ray_m)
                
                if ray_m.terminated or abs(math.tan(ray_m.angle_rad)) < 1e-9: return None
                m_focus = ray_m.x - ray_m.y / math.tan(ray_m.angle_rad)
                
                # Trace Paraxial Ray
                y_paraxial = self.D / 2.0 * 0.01
                ray_p = Ray(self.target.elements[0].position - 10, y_paraxial, angle_rad=0.0)
                tracer._trace_ray_through_system(ray_p)
                
                if ray_p.terminated or abs(math.tan(ray_p.angle_rad)) < 1e-9: return None
                p_focus = ray_p.x - ray_p.y / math.tan(ray_p.angle_rad)
                
                return m_focus - p_focus
            else:
                # Original single lens logic
                tracer = LensRayTracer(self.lens)
                start_x = -10.0 - self.d
                y_marginal = self.D / 2.0
                ray_marginal = Ray(start_x, y_marginal, angle_rad=0.0)
                tracer.trace_ray(ray_marginal)
                if ray_marginal.terminated or abs(math.tan(ray_marginal.angle_rad)) < 1e-9: return None
                marginal_focus = ray_marginal.x - ray_marginal.y / math.tan(ray_marginal.angle_rad)
                
                y_paraxial = self.D / 2.0 * 0.01
                ray_paraxial = Ray(start_x, y_paraxial, angle_rad=0.0)
                tracer.trace_ray(ray_paraxial)
                if abs(math.tan(ray_paraxial.angle_rad)) < 1e-9: return None
                paraxial_focus = ray_paraxial.x - ray_paraxial.y / math.tan(ray_paraxial.angle_rad)
                
                return marginal_focus - paraxial_focus
        except Exception:
            return None

    def _calculate_chromatic_aberration(self, focal_length: float) -> Optional[float]:
        """Calculate longitudinal chromatic aberration (LCA)"""
        if self.is_system:
            # Use system method if it exists
            if hasattr(self.target, 'calculate_chromatic_aberration'):
                res = self.target.calculate_chromatic_aberration()
                return res.get('longitudinal')
            return 0
        
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
            if self.n < 1.5:  abbe_number = 65 
            elif self.n < 1.6: abbe_number = 55 
            elif self.n < 1.7: abbe_number = 40 
            else: abbe_number = 30  
        
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
║ Spherical Aberration:  {results['spherical']:>10.4f} mm (longitudinal)      ║
║ Coma (@ {field_angle}°):         {results['coma']:>10.4f} (relative)              ║
║ Astigmatism (@ {field_angle}°):  {results['astigmatism']:>10.4f} mm                       ║
║ Field Curvature:       {results['field_curvature']:>10.2f} mm (Petzval radius)     ║
║ Distortion (@ {field_angle}°):   {results['distortion']:>10.4f} %                        ║
╠═══════════════════════════════════════════════════════════════╣
║ CHROMATIC ABERRATION                                          ║
╠═══════════════════════════════════════════════════════════════╣
║ Longitudinal CA:       {results['chromatic']:>10.4f} mm (focal shift)        ║
╚═══════════════════════════════════════════════════════════════╝

INTERPRETATION:
• Spherical Aberration: {'Negligible' if abs(results['spherical']) < 0.001 else 'Moderate' if abs(results['spherical']) < 0.01 else 'Significant'}
  ({abs(results['spherical']):.4f} mm - {'rays focus at different points' if results['spherical'] != 0 else 'well corrected'})

• Chromatic Aberration: {'Negligible' if results['chromatic'] < 0.1 else 'Moderate' if results['chromatic'] < 0.5 else 'Significant'}
  ({results['chromatic']:.4f} mm - {'color fringing minimal' if results['chromatic'] < 0.1 else 'visible color fringing'})

• Distortion: {'None' if abs(results['distortion']) < 0.1 else 'Barrel' if results['distortion'] < 0 else 'Pincushion'}
  ({abs(results['distortion']):.2f}% - {'straight lines appear' + (' curved inward' if results['distortion'] < 0 else ' curved outward') if abs(results['distortion']) > 0.1 else 'minimal'})

• Resolution Limit: {results['airy_disk_diameter']*1000:.2f} μm (diffraction-limited spot size)
"""
        
        return summary


    def _calculate_spherical_aberration_seidel(self, focal_length: float) -> float:
        """Calculate third-order Seidel spherical aberration for a single lens"""
        # Spherical aberration S1 = (y^4 / f^3) * [(n/(n-1))^2 + (n+2)/(n(n-1)^2) * (B + (2(n^2-1)/n+2) * C)^2]
        # B = (R2 + R1) / (R2 - R1)
        if abs(self.R2 - self.R1) < EPSILON:
            B = 0.0
        else:
            B = (self.R2 + self.R1) / (self.R2 - self.R1)
            
        C = -1.0 # Object at infinity
        n = self.n
        y = self.D / 2.0
        
        # Simplified Seidel coefficient calculation
        term1 = (n / (n - 1.0))**2
        term2 = (n + 2.0) / (n * (n - 1.0)**2)
        term3 = (B + (2.0 * (n**2 - 1.0) / (n + 2.0)) * C)**2
        
        # Longitudinal spherical aberration estimation
        lsa = -(y**2 / (8.0 * focal_length**3)) * (term1 + term2 * term3) * focal_length**2
        return lsa

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
    sa = abs(results['spherical'])
    if sa > SPHERICAL_ABERRATION_EXCELLENT:
        issues.append(f"High spherical aberration ({sa:.4f} mm)")
        score -= 40  # Major SA penalty
    elif sa > (SPHERICAL_ABERRATION_EXCELLENT / 10):
        issues.append(f"Moderate spherical aberration ({sa:.4f} mm)")
        score -= 20  # Minor SA penalty
    
    # Evaluate chromatic aberration
    ca = results['chromatic']
    if ca > 0.5:  # Significant chromatic aberration
        issues.append(f"High chromatic aberration ({ca:.4f} mm)")
        score -= 40  # Major SA penalty
    elif ca > 0.1:
        issues.append(f"Moderate chromatic aberration ({ca:.4f} mm)")
        score -= 20  # Minor SA penalty
    
    # Evaluate distortion
    dist = results['distortion']
    dist_abs = abs(dist)
    if dist_abs > 5:
        issues.append(f"High distortion ({dist_abs:.2f}%)")
        score -= 15
    elif dist_abs > 1:
        issues.append(f"Moderate distortion ({dist_abs:.2f}%)")
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
