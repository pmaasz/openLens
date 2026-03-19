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
except ImportError:
    from vector3 import Vector3, vec3

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
            # For reflection, we reflect around the *surface* normal (effective or not works, but typically same side)
            # If we used effective normal, we are "entering" new medium? No, TIR means we stay in old.
            # But the formula 2*normal - angle works for mirror reflection.
            # If normal is flipped, 2*(norm+pi) - angle = 2*norm + 2pi - angle = 2*norm - angle (mod 2pi).
            # So reflection formula is invariant to normal flip.
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
        
        Args:
            x: X coordinate
            y: Y coordinate
            surface_type: 'front' or 'back'
        
        Returns:
            Angle of surface normal in radians
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
        """
        Find intersection point of ray with front surface.
        
        Returns:
            (x, y) intersection point, or None if no intersection
        """
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
            # Ray: (x, y) = (ray.x, ray.y) + t*(cos(angle), sin(angle))
            # Sphere: (x - cx)^2 + y^2 = R^2
            
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
            # For Convex front (R1 > 0), we hit the near side (min t)
            # For Concave front (R1 < 0), we hit the far side (max t)
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
        """
        Find intersection point of ray with back surface.
        
        Returns:
            (x, y) intersection point, or None if no intersection
        """
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
            
            # Handle floating-point edge cases
            if discriminant < -EPSILON:
                return None  # Definitely no intersection
            
            # Clamp small negative discriminant to zero (tangent case)
            discriminant = max(0, discriminant)
            
            sqrt_disc = math.sqrt(discriminant)
            t1 = (-b - sqrt_disc) / (2*a)
            t2 = (-b + sqrt_disc) / (2*a)
            
            # Filter to only positive t values (intersections in front of ray)
            valid_ts = [t for t in [t1, t2] if t > EPSILON]
            if not valid_ts:
                return None  # No valid intersection in front of ray
            
            # Choose appropriate intersection based on surface curvature
            # For Concave back (R2 > 0), we hit the near side (min t)
            # For Convex back (R2 < 0), we hit the far side (max t)
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
        """
        Trace a ray through the lens.
        
        Args:
            ray: Ray object to trace
            propagate_distance: Distance to propagate after lens (mm)
        
        Returns:
            Ray object with updated path
        """
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
            # This can happen for high-index glass at steep angles
            ray.terminated = True
            return ray
        
        # Propagate after lens
        ray.propagate(propagate_distance)
        
        return ray
    
    def trace_parallel_rays(self, num_rays: int = DEFAULT_NUM_RAYS, 
                           ray_height_range: Optional[Tuple[float, float]] = None, 
                           wavelength: float = WAVELENGTH_GREEN * NM_TO_MM,
                           angle: float = 0.0) -> List[Ray]:
        """
        Trace parallel rays (collimated beam) through the lens.
        
        Args:
            num_rays: Number of rays to trace
            ray_height_range: (min_height, max_height) in mm, or None for full aperture
            wavelength: Wavelength in mm
            angle: Angle of the parallel beam in degrees (default 0.0)
        
        Returns:
            List of traced Ray objects
        """
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
            
            # Calculate starting y so ray hits the lens at 'height'
            # y = y_start + (x - x_start) * tan(angle)
            # height = y_start + (lens_x - start_x) * tan(angle)
            # y_start = height - (lens_x - start_x) * tan(angle)
            
            y_start = height - (lens_x - start_x) * math.tan(angle_rad)
            
            ray = Ray(start_x, y_start, angle=angle_rad, wavelength=wavelength)
            self.trace_ray(ray)
            rays.append(ray)
        
        return rays
    
    def trace_point_source_rays(self, source_x: float, source_y: float, 
                               num_rays: int = DEFAULT_NUM_RAYS, max_angle: float = DEFAULT_ANGLE_RANGE[1], 
                               wavelength: float = WAVELENGTH_GREEN * NM_TO_MM) -> List[Ray]:
        """
        Trace rays from a point source.
        
        Args:
            source_x: X position of source (mm)
            source_y: Y position of source (mm)
            num_rays: Number of rays to trace
            max_angle: Maximum ray angle from horizontal (degrees)
            wavelength: Wavelength in mm
        
        Returns:
            List of traced Ray objects
        """
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
        """
        Find the focal point from a set of traced parallel rays.
        
        Args:
            rays: List of traced Ray objects
        
        Returns:
            (x, y) focal point, or None if rays don't converge
        """
        # Find where rays cross the optical axis (y=0)
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
        """
        Get points defining the lens outline for visualization.
        
        Args:
            num_points: Number of points per surface
        
        Returns:
            List of (x, y) points outlining the lens
        """
        points = []
        
        # Front surface
        y_max = self.D / 2
        y_values = [y_max - 2 * y_max * i / (num_points - 1) for i in range(num_points)]
        
        for y in y_values:
            if self.front_is_flat:
                x = self.lens_offset
            else:
                # Sphere equation: (x - Cx)^2 + y^2 = R^2
                # x = Cx ± sqrt(R^2 - y^2)
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
        """
        Trace parallel rays through the entire optical system.
        
        Args:
            num_rays: Number of rays to trace
            angle: Angle of the parallel beam in degrees
            wavelength: Wavelength in mm
        
        Returns:
            List of fully traced Ray objects
        """
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
            
            # Calculate starting y so ray hits the first lens at 'height'
            # y = y_start + (x - x_start) * tan(angle)
            # height = y_start + (first_pos - start_x) * tan(angle)
            # y_start = height - (first_pos - start_x) * tan(angle)
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
            # We must account for the element's position
            lens_tracer = LensRayTracer(element.lens, x_offset=element.position)
            
            # Trace through this lens
            # The tracer will find the intersection with the front surface
            # So we don't need to manually propagate exactly to the front
            lens_tracer.trace_ray(ray, propagate_distance=0)
            
            # If this is the last element and ray is not terminated, propagate out
            if not ray.terminated and i == len(self.system.elements) - 1:
                ray.propagate(100.0)

class Ray3D:
    """
    Represents a light ray in 3D space.
    
    Attributes:
        origin: Starting position (Vector3)
        direction: Direction vector (Vector3, normalized)
        wavelength: Wavelength in mm
        intensity: Ray intensity (0-1)
        n: Current refractive index
        path: List of points along the ray path
    """
    
    def __init__(self, origin: Vector3, direction: Vector3, 
                 wavelength: float = WAVELENGTH_GREEN * NM_TO_MM, 
                 intensity: float = 1.0, n: float = REFRACTIVE_INDEX_AIR) -> None:
        self.origin = origin
        self.direction = direction.normalize()
        self.wavelength = wavelength
        self.intensity = intensity
        self.n = n
        self.path: List[Vector3] = [origin]
        self.terminated = False
        self.optical_path_length: float = 0.0
    
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

    def reflect(self, normal: Vector3, n1: Optional[float] = None, n2: Optional[float] = None) -> None:
        """
        Reflect ray off a surface normal.
        Optionally apply Fresnel reflection if refractive indices are provided.
        """
        dot = self.direction.dot(normal)
        self.direction = self.direction - normal * (2 * dot)
        self.direction = self.direction.normalize()
        
        if n1 is not None and n2 is not None:
             cos_i = abs(dot)
             
             # Calculate cos_t using Snell's law
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
        Updates intensity using Fresnel transmission.
        """
        # Ensure normal points against the ray for standard calculation
        cos_i = -self.direction.dot(normal)
        effective_normal = normal
        
        if cos_i < 0:
            cos_i = -cos_i
            effective_normal = -normal
            
        ratio = n1 / n2
        sin2_t = ratio**2 * (1.0 - cos_i**2)
        
        if sin2_t > 1.0:
            # Total internal reflection
            self.reflect(effective_normal, n1, n2)
            return False
        
        cos_t = math.sqrt(1.0 - sin2_t)
        
        # Calculate Transmission (1 - R)
        R = self._compute_fresnel_reflectance(n1, n2, cos_i, cos_t)
        self.intensity *= (1.0 - R)
        
        # Vector Snell's Law
        self.direction = self.direction * ratio + effective_normal * (ratio * cos_i - cos_t)
        self.direction = self.direction.normalize()
        self.n = n2
        
        return True

class LensRayTracer3D:
    """
    3D Ray tracing engine for single lens elements.
    """
    
    def __init__(self, lens: Any, x_offset: float = 0.0) -> None:
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
        """Calculate lens surface positions and centers in 3D"""
        # Centers are on the optical axis (X-axis)
        # Front surface vertex
        self.front_vertex = vec3(self.x_offset, 0, 0)
        self.back_vertex = vec3(self.x_offset + self.d, 0, 0)
        
        # Front surface (R1)
        if abs(self.R1) > 1e6:
            self.front_center = self.front_vertex
            self.front_is_flat = True
        else:
            self.front_center = vec3(self.x_offset + self.R1, 0, 0)
            self.front_is_flat = False
        
        # Back surface (R2)
        if abs(self.R2) > 1e6:
            self.back_center = self.back_vertex
            self.back_is_flat = True
        else:
            self.back_center = vec3(self.x_offset + self.d + self.R2, 0, 0)
            self.back_is_flat = False

    def _intersect_sphere(self, ray: Ray3D, center: Vector3, radius: float, is_convex: bool) -> Optional[Vector3]:
        """
        Intersect ray with a sphere.
        
        Args:
            ray: Ray3D object
            center: Sphere center
            radius: Sphere radius (absolute value)
            is_convex: True if surface is convex relative to incoming light
        
        Returns:
            Intersection point or None
        """
        oc = ray.origin - center
        a = ray.direction.magnitude_sq() # Should be 1
        b = 2.0 * oc.dot(ray.direction)
        c = oc.magnitude_sq() - radius**2
        
        discriminant = b*b - 4*a*c
        
        if discriminant < 0:
            return None
        
        sqrt_disc = math.sqrt(discriminant)
        t1 = (-b - sqrt_disc) / (2*a)
        t2 = (-b + sqrt_disc) / (2*a)
        
        # Filter to only positive t values (intersections in front of ray)
        valid_ts = [t for t in [t1, t2] if t > EPSILON]
        if not valid_ts:
            return None

        # Choose appropriate intersection based on surface curvature
        if is_convex: # R > 0 convention
            t = min(valid_ts)
        else:
            t = max(valid_ts)
            
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
        """
        Trace ray interaction with a specific surface.
        
        Args:
            ray: Ray to trace (modified in place)
            surface_type: 'front' or 'back'
            interaction: 'refract' or 'reflect'
            
        Returns:
            True if interaction successful (ray continues), False if terminated/missed
        """
        # 1. Determine surface parameters
        if surface_type == 'front':
            center = self.front_center
            is_flat = self.front_is_flat
            vertex = self.front_vertex
            R = self.R1
            is_convex = (R > 0)
            # Default transition for front: Air -> Glass
            default_n1 = REFRACTIVE_INDEX_AIR
            default_n2 = self.n
        elif surface_type == 'back':
            center = self.back_center
            is_flat = self.back_is_flat
            vertex = self.back_vertex
            R = self.R2
            is_convex = (R > 0)
            # Default transition for back: Glass -> Air
            default_n1 = self.n
            default_n2 = REFRACTIVE_INDEX_AIR
        else:
            return False

        # 2. Intersect
        if is_flat:
            # Use standard trace_ray normal direction for intersection plane (1,0,0)
            intersection = self._intersect_plane(ray, vertex, vec3(1,0,0))
        else:
            intersection = self._intersect_sphere(ray, center, abs(R), is_convex)
        
        if intersection is None:
            return False
            
        # Check aperture
        r_sq = intersection.y**2 + intersection.z**2
        if r_sq > ((self.D/2) + 1e-9)**2:
             return False

        # Move ray to intersection
        ray.origin = intersection
        ray.path.append(intersection)
        
        # 3. Calculate Normal
        if is_flat:
            if surface_type == 'front':
                normal = vec3(1,0,0)
            else:
                normal = vec3(-1,0,0) # Back surface points out (left)
        else:
            normal = (intersection - center).normalize()

        # 4. Interact
        # Determine n1 (current) and n2 (target)
        current_n = ray.n
        
        if abs(current_n - default_n1) < 1e-3:
            # Standard direction
            n1 = current_n
            n2 = default_n2
        elif abs(current_n - default_n2) < 1e-3:
            # Reverse direction
            n1 = current_n
            n2 = default_n1
        else:
            # Fallback
            n1 = current_n
            n2 = default_n2
            
        if interaction == 'reflect':
            ray.reflect(normal, n1, n2)
            return True
        elif interaction == 'refract':
            return ray.refract(n1, n2, normal)
            
        return False

    def trace_ray(self, ray: Ray3D, propagate_distance: float = DEFAULT_RADIUS_1) -> Ray3D:
        # 1. Intersect Front Surface
        if not self.trace_surface(ray, 'front', 'refract'):
            # Ray missed or TIR (terminated)
            if not ray.terminated: # If terminated by trace_surface (TIR), keep it. If just False (missed), propagate.
                # Wait, trace_surface doesn't set terminated for miss.
                # If trace_surface returns False:
                # - Missed aperture/surface: ray position updated? No.
                # - TIR: ray.terminated is NOT set by trace_surface (refract returns False but reflects).
                # Actually, refract returns False on TIR. trace_surface returns that False.
                
                # Handling miss vs TIR:
                # If ray path length didn't change (no intersection), it's a miss.
                # But trace_surface updates path only on intersection.
                # Checking path length is tricky if we don't know start.
                pass
            
            # Legacy behavior for trace_ray:
            # If miss front: propagate and terminate.
            # If TIR front: terminate.
            
            # Check if we intersected (ray path grew)
            # Actually, let's just use the logic: if terminated, done. If not, propagate and done.
            # But trace_surface doesn't set terminated.
            
            # Let's revert to manual check or improve trace_surface return?
            # Or just check if ray position changed?
            
            # If refraction failed (TIR), trace_surface returns False.
            # If intersection failed, trace_surface returns False.
            
            # Let's just handle it simply:
            if len(ray.path) == 1: # No intersection added (assuming start with 1 point)
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
        for i, element in enumerate(self.system.elements):
            if ray.terminated:
                break
            
            # Create tracer for this element
            # Note: We must create the tracer with the correct x_offset for the element
            lens_tracer = LensRayTracer3D(element.lens, x_offset=element.position)
            
            # Trace through lens (propagate_distance=0 because we handle propagation between lenses manually or let the loop handle it)
            lens_tracer.trace_ray(ray, propagate_distance=0)
            
        # Propagate a bit after last element if not terminated
        if not ray.terminated:
             ray.propagate(50.0)
             
        return ray

    def trace_grid(self, size: float = 10.0, grid_points: int = 5, 
                   wavelength: float = WAVELENGTH_GREEN * NM_TO_MM) -> List[Ray3D]:
        """
        Trace a grid of parallel rays (simulating a collimated beam).
        
        Args:
            size: Width/Height of grid (mm)
            grid_points: Number of points along one axis (total rays = points^2)
            wavelength: Wavelength
            
        Returns:
            List of traced Ray3D objects
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


