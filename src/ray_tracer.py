#!/usr/bin/env python3
"""
Ray Tracing Engine for Optical Lens Simulation
Implements Snell's law and ray propagation through lens elements
"""

import math


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
    
    def __init__(self, x, y, angle, wavelength=0.000550, n=1.0):
        self.x = x
        self.y = y
        self.angle = angle
        self.wavelength = wavelength
        self.n = n
        self.path = [(x, y)]
        self.terminated = False
    
    def propagate(self, distance):
        """Propagate ray in current direction"""
        self.x += distance * math.cos(self.angle)
        self.y += distance * math.sin(self.angle)
        self.path.append((self.x, self.y))
    
    def refract(self, n1, n2, surface_normal_angle):
        """
        Apply Snell's law at an interface.
        
        Args:
            n1: Refractive index of medium ray is coming from
            n2: Refractive index of medium ray is entering
            surface_normal_angle: Angle of surface normal (radians)
        
        Returns:
            True if refraction occurred, False if total internal reflection
        """
        # Incident angle relative to surface normal
        incident_angle = self.angle - surface_normal_angle
        
        # Snell's law: n1 * sin(theta1) = n2 * sin(theta2)
        sin_incident = math.sin(incident_angle)
        sin_ratio = (n1 / n2) * sin_incident
        
        # Check for total internal reflection
        if abs(sin_ratio) > 1.0:
            # Total internal reflection - reflect instead of refract
            self.angle = 2 * surface_normal_angle - self.angle
            return False
        
        # Calculate refracted angle
        refracted_angle = math.asin(sin_ratio)
        
        # Update ray angle (relative to horizontal)
        self.angle = surface_normal_angle + refracted_angle
        self.n = n2
        
        return True


class LensRayTracer:
    """
    Ray tracing engine for single lens elements.
    
    Traces rays through a lens using Snell's law at each surface.
    """
    
    def __init__(self, lens):
        """
        Initialize ray tracer with a lens.
        
        Args:
            lens: Lens object with optical parameters
        """
        self.lens = lens
        self.R1 = lens.radius_of_curvature_1
        self.R2 = lens.radius_of_curvature_2
        self.d = lens.thickness
        self.D = lens.diameter
        self.n = lens.refractive_index
        
        # Calculate lens geometry
        self._calculate_geometry()
    
    def _calculate_geometry(self):
        """Calculate lens surface positions and centers"""
        # Front surface vertex at x=0
        self.front_vertex_x = 0
        
        # Back surface vertex
        self.back_vertex_x = self.d
        
        # Calculate surface centers for spherical surfaces
        # Front surface (R1)
        if abs(self.R1) > 1e6:  # Essentially flat
            self.front_center_x = 0
            self.front_is_flat = True
        else:
            self.front_center_x = -self.R1
            self.front_is_flat = False
        
        # Back surface (R2)
        if abs(self.R2) > 1e6:  # Essentially flat
            self.back_center_x = self.d
            self.back_is_flat = True
        else:
            self.back_center_x = self.d + self.R2
            self.back_is_flat = False
    
    def _get_surface_normal_angle(self, x, y, surface_type):
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
    
    def _intersect_front_surface(self, ray):
        """
        Find intersection point of ray with front surface.
        
        Returns:
            (x, y) intersection point, or None if no intersection
        """
        if self.front_is_flat:
            # Flat surface at x=0
            if abs(math.cos(ray.angle)) < 1e-10:
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
            
            if discriminant < 0:
                return None  # No intersection
            
            # Two solutions - pick the one in front of the ray
            t1 = (-b - math.sqrt(discriminant)) / (2*a)
            t2 = (-b + math.sqrt(discriminant)) / (2*a)
            
            # Choose appropriate intersection
            if self.R1 > 0:  # Convex
                t = min(t1, t2) if t1 > 0 else t2
            else:  # Concave
                t = max(t1, t2) if t2 > 0 else t1
            
            if t < 0:
                return None
            
            x = ray.x + t * dx
            y = ray.y + t * dy
            
            # Check if within lens diameter
            if abs(y) > self.D / 2:
                return None
            
            return (x, y)
    
    def _intersect_back_surface(self, ray):
        """
        Find intersection point of ray with back surface.
        
        Returns:
            (x, y) intersection point, or None if no intersection
        """
        if self.back_is_flat:
            # Flat surface at x=d
            if abs(math.cos(ray.angle)) < 1e-10:
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
            
            if discriminant < 0:
                return None
            
            t1 = (-b - math.sqrt(discriminant)) / (2*a)
            t2 = (-b + math.sqrt(discriminant)) / (2*a)
            
            # Choose appropriate intersection
            if self.R2 < 0:  # Convex (from inside lens)
                t = min(t1, t2) if t1 > 0 else t2
            else:  # Concave
                t = max(t1, t2) if t2 > 0 else t1
            
            if t < 0:
                return None
            
            x = ray.x + t * dx
            y = ray.y + t * dy
            
            if abs(y) > self.D / 2:
                return None
            
            return (x, y)
    
    def trace_ray(self, ray, propagate_distance=100.0):
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
        ray.refract(1.0, self.n, normal_angle)
        
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
        ray.refract(self.n, 1.0, normal_angle)
        
        # Propagate after lens
        ray.propagate(propagate_distance)
        
        return ray
    
    def trace_parallel_rays(self, num_rays=10, ray_height_range=None, wavelength=0.000550):
        """
        Trace parallel rays (collimated beam) through the lens.
        
        Args:
            num_rays: Number of rays to trace
            ray_height_range: (min_height, max_height) in mm, or None for full aperture
            wavelength: Wavelength in mm
        
        Returns:
            List of traced Ray objects
        """
        if ray_height_range is None:
            max_height = self.D / 2 * 0.95  # Use 95% of aperture
            ray_height_range = (-max_height, max_height)
        
        rays = []
        min_h, max_h = ray_height_range
        
        # Starting position (before lens)
        start_x = -50.0
        
        for i in range(num_rays):
            if num_rays == 1:
                height = 0
            else:
                height = min_h + (max_h - min_h) * i / (num_rays - 1)
            
            ray = Ray(start_x, height, angle=0, wavelength=wavelength)
            self.trace_ray(ray)
            rays.append(ray)
        
        return rays
    
    def trace_point_source_rays(self, source_x, source_y, num_rays=10, 
                                max_angle=30.0, wavelength=0.000550):
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
    
    def find_focal_point(self, rays):
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
    
    def get_lens_outline(self, num_points=100):
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
                x = 0
            else:
                # x = cx + R - sqrt(R^2 - y^2)
                R = abs(self.R1)
                if y*y <= R*R:
                    if self.R1 > 0:  # Convex
                        x = self.front_center_x + R - math.sqrt(R*R - y*y)
                    else:  # Concave
                        x = self.front_center_x - R + math.sqrt(R*R - y*y)
                else:
                    continue
            
            points.append((x, y))
        
        # Back surface (reverse direction)
        for y in reversed(y_values):
            if self.back_is_flat:
                x = self.d
            else:
                R = abs(self.R2)
                if y*y <= R*R:
                    if self.R2 < 0:  # Convex (from lens side)
                        x = self.back_center_x - R + math.sqrt(R*R - y*y)
                    else:  # Concave
                        x = self.back_center_x + R - math.sqrt(R*R - y*y)
                else:
                    continue
            
            points.append((x, y))
        
        return points


class SystemRayTracer:
    """Simple ray tracer for multi-element optical systems"""
    
    def __init__(self, optical_system):
        self.system = optical_system
    
    def trace_parallel_rays_simple(self, num_rays=7):
        """
        Simplified system ray tracing - trace each element independently
        and show approximate propagation
        """
        if not self.system.elements:
            return []
        
        all_rays_data = []
        
        # Trace through first element
        first_elem = self.system.elements[0]
        first_tracer = LensRayTracer(first_elem.lens)
        first_rays = first_tracer.trace_parallel_rays(num_rays=num_rays)
        
        # Store with position offset
        for ray in first_rays:
            offset_path = [(x + first_elem.position + 50, y) for x, y in ray.path]
            all_rays_data.append({
                'path': offset_path,
                'element': 0
            })
        
        return all_rays_data
