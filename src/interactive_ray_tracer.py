"""
Interactive Ray Tracing Module
Allows users to click and drag rays to see real-time propagation through optical systems.
"""

import numpy as np
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class InteractiveRay:
    """Represents an interactive ray that can be manipulated by user."""
    origin: np.ndarray
    direction: np.ndarray
    wavelength: float
    color: str
    path_segments: List[Tuple[np.ndarray, np.ndarray]]  # List of (start, end) points
    
    def __post_init__(self):
        self.origin = np.array(self.origin)
        self.direction = np.array(self.direction)
        # Normalize direction
        self.direction = self.direction / np.linalg.norm(self.direction)


class InteractiveRayTracer:
    """Interactive ray tracing with real-time user manipulation."""
    
    def __init__(self, optical_system):
        self.optical_system = optical_system
        self.interactive_rays: List[InteractiveRay] = []
        self.selected_ray: Optional[InteractiveRay] = None
        self.ray_colors = ['red', 'blue', 'green', 'yellow', 'cyan', 'magenta']
        
    def add_ray(self, origin: Tuple[float, float, float], 
                direction: Tuple[float, float, float],
                wavelength: float = 587.6) -> InteractiveRay:
        """Add a new interactive ray."""
        color = self.ray_colors[len(self.interactive_rays) % len(self.ray_colors)]
        ray = InteractiveRay(
            origin=origin,
            direction=direction,
            wavelength=wavelength,
            color=color,
            path_segments=[]
        )
        self.interactive_rays.append(ray)
        self._trace_ray(ray)
        return ray
    
    def remove_ray(self, ray: InteractiveRay):
        """Remove an interactive ray."""
        if ray in self.interactive_rays:
            self.interactive_rays.remove(ray)
        if self.selected_ray == ray:
            self.selected_ray = None
    
    def clear_rays(self):
        """Remove all interactive rays."""
        self.interactive_rays.clear()
        self.selected_ray = None
    
    def update_ray_origin(self, ray: InteractiveRay, 
                         new_origin: Tuple[float, float, float]):
        """Update ray origin and retrace."""
        ray.origin = np.array(new_origin)
        self._trace_ray(ray)
    
    def update_ray_direction(self, ray: InteractiveRay,
                            new_direction: Tuple[float, float, float]):
        """Update ray direction and retrace."""
        ray.direction = np.array(new_direction)
        ray.direction = ray.direction / np.linalg.norm(ray.direction)
        self._trace_ray(ray)
    
    def update_ray_angle(self, ray: InteractiveRay, angle_degrees: float):
        """Update ray direction by angle (in XZ plane)."""
        angle_rad = np.radians(angle_degrees)
        new_direction = np.array([
            np.cos(angle_rad),
            0,
            np.sin(angle_rad)
        ])
        self.update_ray_direction(ray, new_direction)
    
    def _trace_ray(self, ray: InteractiveRay):
        """Trace a single ray through the optical system."""
        ray.path_segments.clear()
        
        current_pos = ray.origin.copy()
        current_dir = ray.direction.copy()
        
        # Trace through system
        for i in range(100):  # Max 100 bounces
            # Find next intersection
            intersection = self._find_next_intersection(current_pos, current_dir)
            
            if intersection is None:
                # Ray exits system - trace to boundary
                end_pos = current_pos + current_dir * 50.0
                ray.path_segments.append((current_pos.copy(), end_pos))
                break
            
            surface, hit_point, surface_normal = intersection
            
            # Add segment to hit point
            ray.path_segments.append((current_pos.copy(), hit_point.copy()))
            
            # Calculate refraction/reflection
            new_dir = self._calculate_ray_interaction(
                current_dir, surface_normal, surface, ray.wavelength
            )
            
            if new_dir is None:
                # Total internal reflection or absorbed
                break
            
            # Continue from hit point
            current_pos = hit_point + new_dir * 0.001  # Small offset
            current_dir = new_dir
    
    def _find_next_intersection(self, pos: np.ndarray, direction: np.ndarray):
        """Find next surface intersection along ray path."""
        if not hasattr(self.optical_system, 'surfaces'):
            return None
        
        closest_t = float('inf')
        closest_intersection = None
        
        for surface in self.optical_system.surfaces:
            t = self._intersect_surface(pos, direction, surface)
            if t is not None and 0.001 < t < closest_t:
                closest_t = t
                hit_point = pos + direction * t
                normal = self._calculate_surface_normal(surface, hit_point)
                closest_intersection = (surface, hit_point, normal)
        
        return closest_intersection
    
    def _intersect_surface(self, pos: np.ndarray, direction: np.ndarray, 
                          surface: Any) -> Optional[float]:
        """Calculate ray-surface intersection parameter t."""
        # Simplified sphere intersection
        if hasattr(surface, 'radius') and hasattr(surface, 'center'):
            oc = pos - surface.center
            a = np.dot(direction, direction)
            b = 2.0 * np.dot(oc, direction)
            c = np.dot(oc, oc) - surface.radius ** 2
            discriminant = b * b - 4 * a * c
            
            if discriminant < 0:
                return None
            
            t = (-b - np.sqrt(discriminant)) / (2.0 * a)
            if t > 0:
                return t
            
            t = (-b + np.sqrt(discriminant)) / (2.0 * a)
            if t > 0:
                return t
        
        return None
    
    def _calculate_surface_normal(self, surface: Any, point: np.ndarray) -> np.ndarray:
        """Calculate surface normal at intersection point."""
        if hasattr(surface, 'center'):
            normal = point - surface.center
            return normal / np.linalg.norm(normal)
        return np.array([0, 0, 1])
    
    def _calculate_ray_interaction(self, incident: np.ndarray, normal: np.ndarray,
                                   surface: Any, wavelength: float) -> Optional[np.ndarray]:
        """Calculate refracted/reflected ray direction."""
        # Get refractive indices
        n1 = 1.0  # Air
        n2 = 1.5  # Glass (simplified)
        
        if hasattr(surface, 'material'):
            if hasattr(surface.material, 'get_refractive_index'):
                n2 = surface.material.get_refractive_index(wavelength)
        
        # Snell's law
        cos_i = -np.dot(incident, normal)
        
        if cos_i < 0:
            # Ray exiting surface
            normal = -normal
            cos_i = -cos_i
            n1, n2 = n2, n1
        
        eta = n1 / n2
        k = 1.0 - eta * eta * (1.0 - cos_i * cos_i)
        
        if k < 0:
            # Total internal reflection
            return incident - 2 * np.dot(incident, normal) * normal
        
        # Refraction
        refracted = eta * incident + (eta * cos_i - np.sqrt(k)) * normal
        return refracted / np.linalg.norm(refracted)
    
    def get_ray_info(self, ray: InteractiveRay) -> Dict[str, Any]:
        """Get detailed information about a ray."""
        total_path_length = 0.0
        for start, end in ray.path_segments:
            total_path_length += np.linalg.norm(end - start)
        
        return {
            'origin': ray.origin.tolist(),
            'direction': ray.direction.tolist(),
            'wavelength': ray.wavelength,
            'color': ray.color,
            'num_segments': len(ray.path_segments),
            'total_path_length': total_path_length,
            'final_position': ray.path_segments[-1][1].tolist() if ray.path_segments else None
        }
    
    def get_all_rays_data(self) -> List[Dict[str, Any]]:
        """Get data for all interactive rays."""
        return [self.get_ray_info(ray) for ray in self.interactive_rays]


class RayManipulator:
    """Handles user interaction for ray manipulation."""
    
    def __init__(self, interactive_tracer: InteractiveRayTracer):
        self.tracer = interactive_tracer
        self.drag_mode = None  # 'origin' or 'direction'
        self.drag_start = None
        
    def start_drag(self, ray: InteractiveRay, mode: str, mouse_pos: Tuple[float, float]):
        """Start dragging a ray."""
        self.tracer.selected_ray = ray
        self.drag_mode = mode
        self.drag_start = mouse_pos
    
    def update_drag(self, mouse_pos: Tuple[float, float]):
        """Update ray during drag."""
        if self.tracer.selected_ray is None or self.drag_mode is None:
            return
        
        ray = self.tracer.selected_ray
        
        if self.drag_mode == 'origin':
            # Update origin
            new_origin = (mouse_pos[0], 0, mouse_pos[1])
            self.tracer.update_ray_origin(ray, new_origin)
        
        elif self.drag_mode == 'direction':
            # Calculate angle from origin to mouse
            dx = mouse_pos[0] - ray.origin[0]
            dz = mouse_pos[1] - ray.origin[2]
            angle = np.degrees(np.arctan2(dz, dx))
            self.tracer.update_ray_angle(ray, angle)
    
    def end_drag(self):
        """End dragging."""
        self.drag_mode = None
        self.drag_start = None
    
    def find_ray_at_position(self, pos: Tuple[float, float], 
                            tolerance: float = 0.5) -> Optional[InteractiveRay]:
        """Find ray near mouse position."""
        for ray in self.tracer.interactive_rays:
            # Check if near origin
            origin_2d = (ray.origin[0], ray.origin[2])
            dist = np.sqrt((pos[0] - origin_2d[0])**2 + (pos[1] - origin_2d[1])**2)
            if dist < tolerance:
                return ray
        return None
