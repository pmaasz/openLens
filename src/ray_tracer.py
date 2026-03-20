#!/usr/bin/env python3
"""
Ray Tracing Engine for Optical Lens Simulation
Implements Snell's law and ray propagation through lens elements
"""

import math
from typing import List, Optional, Tuple, Any

# Import vector class
try:
    from .vector3 import Vector3, vec3
    from .transform import Matrix4x4
except ImportError:
    from vector3 import Vector3, vec3
    from transform import Matrix4x4

# Import numpy and polarization
try:
    import numpy as np
    try:
        from .polarization import PolarizationCalculator
    except ImportError:
        from polarization import PolarizationCalculator
    HAS_POLARIZATION = True
except ImportError:
    np = None
    HAS_POLARIZATION = False

# Import constants
try:
    from .constants import (
        WAVELENGTH_GREEN, NM_TO_MM, REFRACTIVE_INDEX_AIR, REFRACTIVE_INDEX_VACUUM,
        DEFAULT_NUM_RAYS, DEFAULT_ANGLE_RANGE, DEFAULT_RADIUS_1, DEFAULT_THICKNESS,
        EPSILON, MESH_RESOLUTION_HIGH,
    )
except ImportError:
    from constants import (
        WAVELENGTH_GREEN, NM_TO_MM, REFRACTIVE_INDEX_AIR, REFRACTIVE_INDEX_VACUUM,
        DEFAULT_NUM_RAYS, DEFAULT_ANGLE_RANGE, DEFAULT_RADIUS_1, DEFAULT_THICKNESS,
        EPSILON, MESH_RESOLUTION_HIGH,
    )


class Ray:
    """
    Represents a light ray with position and direction.
    
    Attributes:
        x: X position (mm)
        y: Y position (mm) - height from optical axis
        angle: Angle in radians (from horizontal, positive = upward)
        wavelength: Wavelength in mm (default 0.000550 = 550nm green)
        n: Current refractive index the ray is traveling through
        path: List of (x, y) points along the ray path
    """
    
    def __init__(self, x: float, y: float, angle: float, 
                 wavelength: float = WAVELENGTH_GREEN * NM_TO_MM, n: float = REFRACTIVE_INDEX_AIR) -> None:
        self.x = x
        self.y = y
        self.angle = angle
        self.wavelength = wavelength
        self.n = n
        self.path: List[Tuple[float, float]] = [(x, y)]
        self.terminated = False
    
    def propagate(self, distance: float) -> None:
        """Propagate ray in current direction"""
        self.x += distance * math.cos(self.angle)
        self.y += distance * math.sin(self.angle)
        self.path.append((self.x, self.y))
    
    def refract(self, n1: float, n2: float, surface_normal_angle: float) -> bool:
        """
        Apply Snell's law at an interface.
        
        Args:
            n1: Refractive index of medium ray is coming from
            n2: Refractive index of medium ray is entering
            surface_normal_angle: Angle of surface normal (radians)
        
        Returns:
            True if refraction occurred, False if total internal reflection
        """
        # Check if ray opposes normal
        # cos(theta) = dot product of ray and normal directions
        incident_angle = self.angle - surface_normal_angle
        
        # If ray is traveling opposite to normal (dot product < 0), 
        # use the effective normal pointing into the new medium
        effective_normal = surface_normal_angle
        if math.cos(incident_angle) < 0:
            effective_normal = surface_normal_angle + math.pi
            incident_angle = self.angle - effective_normal
            
        # Snell's law: n1 * sin(theta1) = n2 * sin(theta2)
        sin_incident = math.sin(incident_angle)
        sin_ratio = (n1 / n2) * sin_incident
        
        # Check for total internal reflection
        # TIR occurs when |sin(theta2)| >= 1
        # Use (1.0 - EPSILON) to handle floating-point edge cases at critical angle
        if abs(sin_ratio) >= (1.0 - EPSILON):
            # Total internal reflection - reflect instead of refract
            self.angle = 2 * surface_normal_angle - self.angle
            return False
        
        # Calculate refracted angle
        refracted_angle = math.asin(sin_ratio)
        
        # Update ray angle (relative to horizontal)
        self.angle = effective_normal + refracted_angle
        self.n = n2
        
        return True


class LensRayTracer:
    """
    Ray tracing engine for single lens elements.
    
    Traces rays through a lens using Snell's law at each surface.
    """
    
    def __init__(self, lens: Any, x_offset: float = 0.0) -> None:
        """
        Initialize ray tracer with a lens.
        
        Args:
            lens: Lens object with optical parameters
            x_offset: X position of the front vertex (mm)
        """
        self.lens = lens
        self.R1 = lens.radius_of_curvature_1
        self.R2 = lens.radius_of_curvature_2
        self.d = lens.thickness
        self.D = lens.diameter
        self.n = lens.refractive_index
        self.x_offset = x_offset
        
        # Calculate lens geometry
        self._calculate_geometry()
    
    def _calculate_geometry(self) -> None:
        """Calculate lens surface positions and centers"""
        # Lens offset - front surface starts at x_offset
        self.lens_offset = self.x_offset
        
        # Front surface vertex
        self.front_vertex_x = self.lens_offset
        
        # Back surface vertex
        self.back_vertex_x = self.lens_offset + self.d
        
        # Calculate surface centers for spherical surfaces
        # Standard sign convention: R > 0 means center is to the right
        # Cx = Vertex + R
        
        # Front surface (R1)
        if abs(self.R1) > 1e6:  # Essentially flat
            self.front_center_x = self.front_vertex_x
            self.front_is_flat = True
        else:
            self.front_center_x = self.front_vertex_x + self.R1
            self.front_is_flat = False
        
        # Back surface (R2)
        if abs(self.R2) > 1e6:  # Essentially flat
            self.back_center_x = self.back_vertex_x
            self.back_is_flat = True
        else:
            self.back_center_x = self.back_vertex_x + self.R2
            self.back_is_flat = False
    
    def _get_surface_normal_angle(self, x: float, y: float, surface_type: str) -> float:
        """
        Calculate surface normal angle at a point.
        """
        if surface_type == 'front':
            if self.front_is_flat:
                return 0  # Normal points right (along +x axis)
            else:
                # Vector from surface center to point
                dx = x - self.front_center_x
                dy = y
                return math.atan2(dy, dx)
        
        else:  # back surface
            if self.back_is_flat:
                return 0  # Normal points right
            else:
                dx = x - self.back_center_x
                dy = y
                return math.atan2(dy, dx)
    
    def _intersect_front_surface(self, ray: Ray) -> Optional[Tuple[float, float]]:
        """Find intersection point of ray with front surface."""
        if self.front_is_flat:
            # Flat surface at x=0
            if abs(math.cos(ray.angle)) < EPSILON:
                return None  # Ray parallel to surface
            
            t = (self.front_vertex_x - ray.x) / math.cos(ray.angle)
            if t < 0:
                return None  # Intersection behind ray
            
            y = ray.y + t * math.sin(ray.angle)
            
            # Check if within lens diameter
            if abs(y) > self.D / 2:
                return None
            
            return (self.front_vertex_x, y)
        
        else:
            # Spherical surface - solve ray-sphere intersection
            cx = self.front_center_x
            R = abs(self.R1)
            
            dx = math.cos(ray.angle)
            dy = math.sin(ray.angle)
            
            # Quadratic equation coefficients
            a = dx*dx + dy*dy
            b = 2 * ((ray.x - cx) * dx + ray.y * dy)
            c = (ray.x - cx)**2 + ray.y**2 - R**2
            
            discriminant = b*b - 4*a*c
            
            # Handle floating-point edge cases
            if discriminant < -EPSILON:
                return None  # Definitely no intersection
            
            # Clamp small negative discriminant to zero (tangent case)
            discriminant = max(0, discriminant)
            
            # Two solutions - pick the one in front of the ray
            sqrt_disc = math.sqrt(discriminant)
            t1 = (-b - sqrt_disc) / (2*a)
            t2 = (-b + sqrt_disc) / (2*a)
            
            # Filter to only positive t values (intersections in front of ray)
            valid_ts = [t for t in [t1, t2] if t > EPSILON]
            if not valid_ts:
                return None  # No valid intersection in front of ray
            
            # Choose appropriate intersection based on surface curvature
            if self.R1 > 0:
                t = min(valid_ts)
            else:
                t = max(valid_ts)
            
            x = ray.x + t * dx
            y = ray.y + t * dy
            
            # Check if within lens diameter
            if abs(y) > self.D / 2:
                return None
            
            return (x, y)
    
    def _intersect_back_surface(self, ray: Ray) -> Optional[Tuple[float, float]]:
        """Find intersection point of ray with back surface."""
        if self.back_is_flat:
            # Flat surface at x=d
            if abs(math.cos(ray.angle)) < EPSILON:
                return None
            
            t = (self.back_vertex_x - ray.x) / math.cos(ray.angle)
            if t < 0:
                return None
            
            y = ray.y + t * math.sin(ray.angle)
            
            if abs(y) > self.D / 2:
                return None
            
            return (self.back_vertex_x, y)
        
        else:
            # Spherical surface
            cx = self.back_center_x
            R = abs(self.R2)
            
            dx = math.cos(ray.angle)
            dy = math.sin(ray.angle)
            
            a = dx*dx + dy*dy
            b = 2 * ((ray.x - cx) * dx + ray.y * dy)
            c = (ray.x - cx)**2 + ray.y**2 - R**2
            
            discriminant = b*b - 4*a*c
            
            if discriminant < -EPSILON:
                return None
            
            discriminant = max(0, discriminant)
            
            sqrt_disc = math.sqrt(discriminant)
            t1 = (-b - sqrt_disc) / (2*a)
            t2 = (-b + sqrt_disc) / (2*a)
            
            valid_ts = [t for t in [t1, t2] if t > EPSILON]
            if not valid_ts:
                # Check if we are already past the surface (physically outside lens volume)
                # This handles cases where surfaces cross (lens too thin for diameter)
                dist_sq = (ray.x - cx)**2 + ray.y**2
                R_sq = R**2
                
                already_exited = False
                # For convex back surface (R2 < 0), glass is inside the sphere.
                # If we are outside the sphere (dist > R), we have exited.
                if self.R2 < 0 and dist_sq > R_sq:
                    already_exited = True
                # For concave back surface (R2 > 0), glass is outside the sphere.
                # If we are inside the sphere (dist < R), we have exited.
                elif self.R2 > 0 and dist_sq < R_sq:
                    already_exited = True
                    
                if already_exited:
                    return (ray.x, ray.y)
                
                return None
            
            # Choose appropriate intersection based on surface curvature
            if self.R2 > 0:
                t = min(valid_ts)
            else:
                t = max(valid_ts)
            
            x = ray.x + t * dx
            y = ray.y + t * dy
            
            if abs(y) > self.D / 2:
                return None
            
            return (x, y)
    
    def trace_ray(self, ray: Ray, propagate_distance: float = (DEFAULT_RADIUS_1)) -> Ray:
        """Trace a ray through the lens."""
        # Find intersection with front surface
        intersection = self._intersect_front_surface(ray)
        
        if intersection is None:
            # Ray misses lens - propagate straight
            ray.propagate(propagate_distance)
            ray.terminated = True
            return ray
        
        # Propagate to front surface
        x1, y1 = intersection
        ray.x, ray.y = x1, y1
        ray.path.append((x1, y1))
        
        # Refract at front surface
        normal_angle = self._get_surface_normal_angle(x1, y1, 'front')
        if not ray.refract(REFRACTIVE_INDEX_AIR, self.n, normal_angle):
            # Total internal reflection at front surface (unusual but possible)
            ray.terminated = True
            return ray
        
        # Propagate through lens to back surface
        intersection = self._intersect_back_surface(ray)
        
        if intersection is None:
            # Ray doesn't exit lens (shouldn't happen normally)
            ray.terminated = True
            return ray
        
        x2, y2 = intersection
        ray.x, ray.y = x2, y2
        ray.path.append((x2, y2))
        
        # Refract at back surface
        normal_angle = self._get_surface_normal_angle(x2, y2, 'back')
        if not ray.refract(self.n, REFRACTIVE_INDEX_AIR, normal_angle):
            # Total internal reflection at back surface
            ray.terminated = True
            return ray
        
        # Propagate after lens
        ray.propagate(propagate_distance)
        
        return ray
    
    def trace_parallel_rays(self, num_rays: int = DEFAULT_NUM_RAYS, 
                           ray_height_range: Optional[Tuple[float, float]] = None, 
                           wavelength: float = WAVELENGTH_GREEN * NM_TO_MM,
                           angle: float = 0.0) -> List[Ray]:
        """Trace parallel rays (collimated beam) through the lens."""
        if ray_height_range is None:
            max_height = self.D / 2 * 0.95  # Use 95% of aperture
            ray_height_range = (-max_height, max_height)
        
        rays = []
        min_h, max_h = ray_height_range
        angle_rad = math.radians(angle)
        
        # Starting position (before lens) - rays start at x=-100 to visualize the beam
        start_x = -100.0
        
        # Calculate lens position (x=0) for target height
        lens_x = 0.0
        
        for i in range(num_rays):
            if num_rays == 1:
                height = 0
            else:
                height = min_h + (max_h - min_h) * i / (num_rays - 1)
            
            y_start = height - (lens_x - start_x) * math.tan(angle_rad)
            
            ray = Ray(start_x, y_start, angle=angle_rad, wavelength=wavelength)
            self.trace_ray(ray)
            rays.append(ray)
        
        return rays
    
    def trace_point_source_rays(self, source_x: float, source_y: float, 
                               num_rays: int = DEFAULT_NUM_RAYS, max_angle: float = DEFAULT_ANGLE_RANGE[1], 
                               wavelength: float = WAVELENGTH_GREEN * NM_TO_MM) -> List[Ray]:
        """Trace rays from a point source."""
        rays = []
        max_angle_rad = math.radians(max_angle)
        
        for i in range(num_rays):
            if num_rays == 1:
                angle = 0
            else:
                angle = -max_angle_rad + 2 * max_angle_rad * i / (num_rays - 1)
            
            ray = Ray(source_x, source_y, angle, wavelength=wavelength)
            self.trace_ray(ray)
            rays.append(ray)
        
        return rays
    
    def find_focal_point(self, rays: List[Ray]) -> Optional[Tuple[float, float]]:
        """Find the focal point from a set of traced parallel rays."""
        crossings = []
        
        for ray in rays:
            if len(ray.path) < 2:
                continue
            
            # Check last segment of ray
            x1, y1 = ray.path[-2]
            x2, y2 = ray.path[-1]
            
            # Check if ray crosses y=0
            if (y1 * y2 <= 0) and abs(y2 - y1) > 1e-6:
                # Linear interpolation to find crossing
                t = -y1 / (y2 - y1)
                x_cross = x1 + t * (x2 - x1)
                crossings.append(x_cross)
        
        if not crossings:
            return None
        
        # Focal point is average crossing location
        focal_x = sum(crossings) / len(crossings)
        
        return (focal_x, 0)
    
    def get_lens_outline(self, num_points: int = MESH_RESOLUTION_HIGH) -> List[Tuple[float, float]]:
        """Get points defining the lens outline for visualization."""
        points = []
        
        # Front surface
        y_max = self.D / 2
        y_values = [y_max - 2 * y_max * i / (num_points - 1) for i in range(num_points)]
        
        for y in y_values:
            if self.front_is_flat:
                x = self.lens_offset
            else:
                R = abs(self.R1)
                if y*y <= R*R:
                    if self.R1 > 0:  # Convex - use right side of sphere
                        x = self.front_center_x + math.sqrt(R*R - y*y)
                    else:  # Concave - use left side of sphere
                        x = self.front_center_x - math.sqrt(R*R - y*y)
                else:
                    continue
            
            points.append((x, y))
        
        # Back surface (reverse direction)
        for y in reversed(y_values):
            if self.back_is_flat:
                x = self.lens_offset + self.d
            else:
                R = abs(self.R2)
                if y*y <= R*R:
                    if self.R2 < 0:  # Convex (from inside) - use left side of sphere
                        x = self.back_center_x - math.sqrt(R*R - y*y)
                    else:  # Concave - use right side of sphere
                        x = self.back_center_x + math.sqrt(R*R - y*y)
                else:
                    continue
            
            points.append((x, y))
        
        return points


class SystemRayTracer:
    """Ray tracer for multi-element optical systems"""
    
    def __init__(self, optical_system: Any) -> None:
        self.system = optical_system
    
    def trace_parallel_rays(self, num_rays: int = DEFAULT_NUM_RAYS, 
                           angle: float = 0.0,
                           wavelength: float = WAVELENGTH_GREEN * NM_TO_MM) -> List[Ray]:
        """Trace parallel rays through the entire optical system."""
        if not self.system.elements:
            return []
        
        # Calculate first lens diameter to determine ray spread
        first_lens = self.system.elements[0].lens
        max_height = first_lens.diameter / 2 * 0.95
        min_h, max_h = -max_height, max_height
        
        rays = []
        angle_rad = math.radians(angle)
        
        # Determine start position (well before first element)
        first_pos = self.system.elements[0].position
        start_x = first_pos - 100.0
        
        for i in range(num_rays):
            if num_rays == 1:
                height = 0
            else:
                height = min_h + (max_h - min_h) * i / (num_rays - 1)
            
            y_start = height - (first_pos - start_x) * math.tan(angle_rad)
            
            # Create ray
            ray = Ray(start_x, y_start, angle=angle_rad, wavelength=wavelength)
            
            # Trace through system
            self._trace_ray_through_system(ray)
            
            rays.append(ray)
        
        return rays
        
    def _trace_ray_through_system(self, ray: Ray) -> None:
        """Trace a single ray through all elements"""
        
        for i, element in enumerate(self.system.elements):
            if ray.terminated:
                break
            
            # Create a tracer for this specific element at its position
            lens_tracer = LensRayTracer(element.lens, x_offset=element.position)
            
            # Trace through this lens
            lens_tracer.trace_ray(ray, propagate_distance=0)
            
            # If this is the last element and ray is not terminated, propagate out
            if not ray.terminated and i == len(self.system.elements) - 1:
                ray.propagate(100.0)

class Ray3D:
    """
    Represents a light ray in 3D space with optional polarization.
    """
    
    def __init__(self, origin: Vector3, direction: Vector3, 
                 wavelength: float = WAVELENGTH_GREEN * NM_TO_MM, 
                 intensity: float = 1.0, n: float = REFRACTIVE_INDEX_AIR,
                 polarization_vector: Optional[Any] = None) -> None:
        self.origin = origin
        self.direction = direction.normalize()
        self.wavelength = wavelength
        self.intensity = intensity
        self.n = n
        self.path: List[Vector3] = [origin]
        self.terminated = False
        self.optical_path_length: float = 0.0
        
        # Polarization (E-field vector)
        self.polarization_vector = polarization_vector
        if self.polarization_vector is not None and HAS_POLARIZATION:
            # Ensure it's a numpy array
            if not isinstance(self.polarization_vector, np.ndarray):
                self.polarization_vector = np.array(self.polarization_vector, dtype=complex)
    
    def propagate(self, distance: float) -> None:
        """Propagate ray in current direction"""
        self.origin = self.origin + self.direction * distance
        self.path.append(self.origin)
        self.optical_path_length += distance * self.n
    
    def _compute_fresnel_reflectance(self, n1: float, n2: float, cos_i: float, cos_t: float) -> float:
        """Calculate Fresnel reflectance for unpolarized light."""
        if n1 == n2: return 0.0
        
        # Rs = (n1 cos_i - n2 cos_t) / (n1 cos_i + n2 cos_t)
        rs_den = n1 * cos_i + n2 * cos_t
        if rs_den == 0: return 1.0
        rs = ((n1 * cos_i - n2 * cos_t) / rs_den)**2
        
        # Rp = (n1 cos_t - n2 cos_i) / (n1 cos_t + n2 cos_i)
        rp_den = n1 * cos_t + n2 * cos_i
        if rp_den == 0: return 1.0
        rp = ((n1 * cos_t - n2 * cos_i) / rp_den)**2
        
        return 0.5 * (rs + rp)

    def _update_polarization(self, normal: Vector3, n1: float, n2: float, 
                             new_direction: Vector3, interaction: str) -> None:
        """
        Update polarization vector based on interaction (reflect/refract).
        """
        if self.polarization_vector is None or not HAS_POLARIZATION:
            return

        k_inc = self.direction # Incident direction
        n = normal
        
        # 1. Calculate Basis Vectors
        s_vec = k_inc.cross(n)
        s_mag = s_vec.magnitude()
        
        if s_mag < 1e-6:
            if abs(k_inc.x) < 0.9:
                arb = vec3(1, 0, 0)
            else:
                arb = vec3(0, 1, 0)
            s_vec = k_inc.cross(arb).normalize()
        else:
            s_vec = s_vec.normalize()
            
        p_inc = s_vec.cross(k_inc).normalize()
        
        # p-vector outgoing
        k_out = new_direction
        p_out = s_vec.cross(k_out).normalize()
        
        # 2. Project E-field onto s and p
        E = self.polarization_vector
        s_np = np.array([s_vec.x, s_vec.y, s_vec.z])
        p_inc_np = np.array([p_inc.x, p_inc.y, p_inc.z])
        p_out_np = np.array([p_out.x, p_out.y, p_out.z])
        
        E_s = np.dot(E, s_np)
        E_p = np.dot(E, p_inc_np)
        
        # 3. Fresnel Coefficients
        cos_i = abs(k_inc.dot(n))
        angle_deg = math.degrees(math.acos(min(1.0, cos_i)))
        
        calc = PolarizationCalculator()
        coeffs = calc.fresnel_coefficients(n1, n2, angle_deg)
        
        # 4. Update E-field and Intensity
        if interaction == 'reflect':
            r_s = coeffs['r_s']
            r_p = coeffs['r_p']
            
            E_new = r_s * E_s * s_np + r_p * E_p * p_out_np
            
            R_s = np.abs(r_s)**2
            R_p = np.abs(r_p)**2
            
            P_total_old = np.abs(E_s)**2 + np.abs(E_p)**2
            if P_total_old > 1e-9:
                reflectance_factor = (R_s * np.abs(E_s)**2 + R_p * np.abs(E_p)**2) / P_total_old
                self.intensity *= reflectance_factor
            else:
                self.intensity = 0.0

            self.polarization_vector = E_new
            
        elif interaction == 'refract':
            t_s = coeffs['t_s']
            t_p = coeffs['t_p']
            
            E_new = t_s * E_s * s_np + t_p * E_p * p_out_np
            
            if coeffs['total_internal_reflection']:
                 self.intensity = 0.0
                 self.polarization_vector = np.zeros(3, dtype=complex)
                 return

            theta1_rad = math.radians(angle_deg)
            theta2_rad = math.radians(coeffs['theta_transmitted_deg'])
            
            if n1 * math.cos(theta1_rad) > 1e-9:
                geo_factor = (n2 * math.cos(theta2_rad)) / (n1 * math.cos(theta1_rad))
            else:
                geo_factor = 0
            
            T_s = geo_factor * np.abs(t_s)**2
            T_p = geo_factor * np.abs(t_p)**2
            
            P_total_old = np.abs(E_s)**2 + np.abs(E_p)**2
            if P_total_old > 1e-9:
                transmittance_factor = (T_s * np.abs(E_s)**2 + T_p * np.abs(E_p)**2) / P_total_old
                self.intensity *= transmittance_factor
            else:
                self.intensity = 0.0
                
            self.polarization_vector = E_new

    def reflect(self, normal: Vector3, n1: Optional[float] = None, n2: Optional[float] = None) -> None:
        """
        Reflect ray off a surface normal.
        """
        old_direction = self.direction
        dot = self.direction.dot(normal)
        
        # Calculate new direction first
        new_direction = self.direction - normal * (2 * dot)
        new_direction = new_direction.normalize()
        self.direction = new_direction
        
        if n1 is not None and n2 is not None:
             if self.polarization_vector is not None and HAS_POLARIZATION:
                 temp_ray_dir = self.direction
                 self.direction = old_direction
                 self._update_polarization(normal, n1, n2, new_direction, 'reflect')
                 self.direction = temp_ray_dir
                 return

             cos_i = abs(dot)
             ratio = n1 / n2
             sin2_t = ratio**2 * (1.0 - cos_i**2)
             
             if sin2_t > 1.0:
                 R = 1.0 # TIR
             else:
                 cos_t = math.sqrt(1.0 - sin2_t)
                 R = self._compute_fresnel_reflectance(n1, n2, cos_i, cos_t)
             
             self.intensity *= R

    def refract(self, n1: float, n2: float, normal: Vector3) -> bool:
        """
        Apply Snell's law at an interface using vector math.
        """
        cos_i = -self.direction.dot(normal)
        effective_normal = normal
        
        if cos_i < 0:
            cos_i = -cos_i
            effective_normal = -normal
            
        ratio = n1 / n2
        sin2_t = ratio**2 * (1.0 - cos_i**2)
        
        if sin2_t > 1.0:
            self.reflect(effective_normal, n1, n2)
            return False
        
        cos_t = math.sqrt(1.0 - sin2_t)
        
        new_direction = self.direction * ratio + effective_normal * (ratio * cos_i - cos_t)
        new_direction = new_direction.normalize()
        
        if self.polarization_vector is not None and HAS_POLARIZATION:
            self._update_polarization(effective_normal, n1, n2, new_direction, 'refract')
            self.direction = new_direction
            self.n = n2
            return True
        
        R = self._compute_fresnel_reflectance(n1, n2, cos_i, cos_t)
        self.intensity *= (1.0 - R)
        
        self.direction = new_direction
        self.n = n2
        
        return True

class LensRayTracer3D:
    """
    3D Ray tracing engine for single lens elements.
    Accepts an optional transformation matrix for position/orientation.
    """
    
    def __init__(self, lens: Any, transform: Optional[Matrix4x4] = None, x_offset: float = 0.0) -> None:
        self.lens = lens
        self.R1 = lens.radius_of_curvature_1
        self.R2 = lens.radius_of_curvature_2
        self.d = lens.thickness
        self.D = lens.diameter
        self.n = lens.refractive_index
        
        if transform:
            self.transform = transform
        else:
            self.transform = Matrix4x4.from_translation(x_offset, 0, 0)
        
        self._calculate_geometry()
    
    def _calculate_geometry(self) -> None:
        """Calculate lens surface positions and centers in 3D using transform"""
        # Canonical positions (lens along X axis, Front vertex at 0)
        v0 = vec3(0, 0, 0)
        v1 = vec3(self.d, 0, 0)
        
        # Front Vertex
        self.front_vertex = self.transform.multiply_point(v0)
        
        # Back Vertex
        self.back_vertex = self.transform.multiply_point(v1)
        
        # Front Center
        if abs(self.R1) > 1e6:
            self.front_center = self.front_vertex
            self.front_is_flat = True
        else:
            self.front_center = self.transform.multiply_point(vec3(self.R1, 0, 0))
            self.front_is_flat = False
        
        # Back Center
        if abs(self.R2) > 1e6:
            self.back_center = self.back_vertex
            self.back_is_flat = True
        else:
            self.back_center = self.transform.multiply_point(vec3(self.d + self.R2, 0, 0))
            self.back_is_flat = False

        # Orientation Vectors (for plane normals)
        # Canonical normal is +X (1,0,0)
        self.optical_axis = self.transform.multiply_vector(vec3(1, 0, 0)).normalize()

    def _intersect_sphere(self, ray: Ray3D, center: Vector3, radius: float, is_convex: bool) -> Optional[Vector3]:
        """Intersect ray with a sphere."""
        oc = ray.origin - center
        a = ray.direction.magnitude_sq()
        b = 2.0 * oc.dot(ray.direction)
        c = oc.magnitude_sq() - radius**2
        
        discriminant = b*b - 4*a*c
        
        if discriminant < 0:
            return None
        
        sqrt_disc = math.sqrt(discriminant)
        t1 = (-b - sqrt_disc) / (2*a)
        t2 = (-b + sqrt_disc) / (2*a)
        
        valid_ts = [t for t in [t1, t2] if t > EPSILON]
        if not valid_ts:
            return None

        # R > 0 (Convex) means center is further along axis.
        # But this assumes we approach from "left" relative to the surface curvature.
        # Since we are working in 3D global space, 'min' vs 'max' depends on whether we are inside or outside.
        
        # Simple heuristic:
        # If we are outside the sphere (distance to center > radius), we hit the near side (min t).
        # If we are inside (distance < radius), we hit the far side (max t).
        dist_sq = oc.magnitude_sq()
        is_inside = dist_sq < radius**2
        
        if is_inside:
             t = max(valid_ts)
        else:
             t = min(valid_ts)
            
        return ray.origin + ray.direction * t

    def _intersect_plane(self, ray: Ray3D, point_on_plane: Vector3, normal: Vector3) -> Optional[Vector3]:
        denom = normal.dot(ray.direction)
        if abs(denom) < EPSILON:
            return None
        
        t = (point_on_plane - ray.origin).dot(normal) / denom
        if t < EPSILON:
            return None
            
        return ray.origin + ray.direction * t

    def trace_surface(self, ray: Ray3D, surface_type: str, interaction: str = 'refract') -> bool:
        """Trace ray interaction with a specific surface."""
        if surface_type == 'front':
            center = self.front_center
            is_flat = self.front_is_flat
            vertex = self.front_vertex
            R = self.R1
            # Normal for flat front surface points opposite to incoming? No, along optical axis.
            # If flat, normal is self.optical_axis.
            # Transition: Air -> Glass
            default_n1 = REFRACTIVE_INDEX_AIR
            default_n2 = self.n
        elif surface_type == 'back':
            center = self.back_center
            is_flat = self.back_is_flat
            vertex = self.back_vertex
            R = self.R2
            # Transition: Glass -> Air
            default_n1 = self.n
            default_n2 = REFRACTIVE_INDEX_AIR
        else:
            return False

        # Intersect
        if is_flat:
            # Planar intersection
            # Normal is optical axis
            normal = self.optical_axis
            intersection = self._intersect_plane(ray, vertex, normal)
        else:
            # Spherical intersection
            # Note: We don't need is_convex flag anymore with the inside/outside logic
            intersection = self._intersect_sphere(ray, center, abs(R), (R > 0))
        
        if intersection is None:
            # Check for "already exited" condition (crossed surfaces)
            # Only relevant for back surface (exiting lens)
            if surface_type == 'back' and not is_flat:
                dist_sq = (ray.origin - center).magnitude_sq()
                R_abs = abs(R)
                already_exited = False
                
                # R < 0 (Convex back): Glass is inside sphere.
                # If dist > R, we are outside (in Air).
                if R < 0 and dist_sq > R_abs**2:
                    already_exited = True
                # R > 0 (Concave back): Glass is outside sphere.
                # If dist < R, we are inside (in Air).
                elif R > 0 and dist_sq < R_abs**2:
                    already_exited = True
                    
                if already_exited:
                    # We are already in air.
                    ray.n = default_n2
                    return True
            
            return False
            
        # Check aperture (distance from optical axis line)
        # Vector from vertex to intersection
        v_to_i = intersection - vertex
        # Project onto optical axis
        proj = v_to_i.dot(self.optical_axis)
        # Distance squared from axis = |v_to_i|^2 - proj^2
        dist_sq = v_to_i.magnitude_sq() - proj**2
        
        if dist_sq > ((self.D/2) + 1e-4)**2: # Tolerance
             return False

        # Move ray
        ray.origin = intersection
        ray.path.append(intersection)
        
        # Calculate Normal
        if is_flat:
            # If front, normal is optical axis (pointing into lens).
            # If back, normal is -optical axis (pointing out of lens).
            # Wait, normal should usually point OUT of the object for standard renderers,
            # but for refraction n1->n2, normal usually points from n1 into n2?
            # Or just surface normal.
            # Let's align normal with optical axis for Front, opposite for Back?
            # Actually, sphere normal is (intersection - center).
            # For Convex Front (Center to right), normal points Left (out).
            # For Flat Front, normal should point Left (out)?
            # My previous logic used (1,0,0) for front flat. That points IN.
            
            # Let's standardize: Normal points OUT of the lens volume.
            if surface_type == 'front':
                normal = -self.optical_axis
            else:
                normal = self.optical_axis
        else:
            # Sphere normal: (intersection - center).normalize()
            # If Convex Front (Center inside): Normal points In -> Out.
            # If Concave Front (Center outside): Normal points Out -> In?
            # (P - C).
            # R1 > 0 (Convex Front): C is to right. P is to left. P-C points Left (Out). Correct.
            # R1 < 0 (Concave Front): C is to left. P is to right. P-C points Right (In).
            # We want Outward normal.
            normal = (intersection - center).normalize()
            if R < 0: # Concave front means center is on air side. P-C points into glass?
                # Let's check. R < 0. Center is at -|R|. P is at 0. P-C = 0 - (-R) = +R. Points Right (Into Glass).
                # We want Outward normal (Left). So flip.
                normal = -normal
            
            # For Back Surface:
            # R2 < 0 (Convex Back): Center is left. P is right. P-C points Right (Out). Correct.
            # R2 > 0 (Concave Back): Center is right. P is left. P-C points Left (In).
            # We want Outward normal (Right). So flip.
            if surface_type == 'back' and R > 0:
                normal = -normal

        # Interact
        current_n = ray.n
        
        # Logic to determine n1/n2 based on direction vs normal
        # If ray enters (dot(ray, normal) < 0), we go n1 -> n2.
        # If ray exits (dot(ray, normal) > 0), we go n2 -> n1?
        # Actually, trace_surface assumes we know the transition (default_n1 -> default_n2).
        # But we might be tracing rays backwards or internally?
        # Let's trust the surface type defaults for now, but verify with ray.n.
        
        if abs(current_n - default_n1) < 1e-3:
            n1, n2 = default_n1, default_n2
        elif abs(current_n - default_n2) < 1e-3:
            n1, n2 = default_n2, default_n1
        else:
            n1, n2 = current_n, default_n2 # Guess
            
        if interaction == 'reflect':
            ray.reflect(normal, n1, n2)
            return True
        elif interaction == 'refract':
            return ray.refract(n1, n2, normal)
            
        return False

    def trace_ray(self, ray: Ray3D, propagate_distance: float = DEFAULT_RADIUS_1) -> Ray3D:
        # 1. Intersect Front Surface
        if not self.trace_surface(ray, 'front', 'refract'):
            if not ray.terminated:
                 # Missed
                 ray.propagate(propagate_distance)
                 ray.terminated = True
            return ray
            
        # 2. Intersect Back Surface
        if not self.trace_surface(ray, 'back', 'refract'):
             ray.terminated = True
             return ray
             
        # Propagate to end
        ray.propagate(propagate_distance)
        return ray


class SystemRayTracer3D:
    """Ray tracer for multi-element optical systems in 3D"""
    
    def __init__(self, optical_system: Any) -> None:
        self.system = optical_system
    
    def trace_ray(self, ray: Ray3D) -> Ray3D:
        """Trace a single ray through the entire system."""
        
        # Collect elements with transforms
        elements = []
        if hasattr(self.system, 'root'):
             # Use hierarchy
             nodes = self.system.root.get_flat_list()
             for node, _ in nodes:
                 if getattr(node, 'is_element', False):
                     transform = node.get_global_transform()
                     elements.append((node.element_model, transform))
        else:
             # Fallback
             for elem in self.system.elements:
                 t = Matrix4x4.from_translation(elem.position, 0, 0)
                 elements.append((elem.lens, t))

        for lens, transform in elements:
            if ray.terminated:
                break
            
            tracer = LensRayTracer3D(lens, transform=transform)
            # Propagate distance 0 because we loop through next element
            tracer.trace_ray(ray, propagate_distance=0)
            
        # Propagate a bit after last element
        if not ray.terminated:
             ray.propagate(50.0)
             
        return ray

    def trace_grid(self, size: float = 10.0, grid_points: int = 5, 
                   wavelength: float = WAVELENGTH_GREEN * NM_TO_MM) -> List[Ray3D]:
        """
        Trace a grid of parallel rays (simulating a collimated beam).
        """
        rays = []
        if not self.system.elements:
            return rays
            
        first_pos = self.system.elements[0].position
        start_x = first_pos - 50.0
        
        half_size = size / 2
        step = size / (grid_points - 1) if grid_points > 1 else 0
        
        for i in range(grid_points):
            y = -half_size + i * step
            for j in range(grid_points):
                z = -half_size + j * step
                
                origin = vec3(start_x, y, z)
                direction = vec3(1, 0, 0) # +X direction
                
                ray = Ray3D(origin, direction, wavelength=wavelength)
                self.trace_ray(ray)
                rays.append(ray)
                
        return rays
