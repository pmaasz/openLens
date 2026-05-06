"""
Interactive Ray Tracing Module
Allows users to click and drag rays to see real-time propagation through optical systems.
"""

import math
from typing import List, Tuple, Optional, Dict, Any, Union
from dataclasses import dataclass

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    np = None
    HAS_NUMPY = False

try:
    from .vector3 import Vector3, vec3
    from .ray_tracer import Ray3D, SystemRayTracer3D
except ImportError:
    from vector3 import Vector3, vec3
    from ray_tracer import Ray3D, SystemRayTracer3D


@dataclass
class InteractiveRay:
    """Represents an interactive ray that can be manipulated by user."""
    origin: Union[Vector3, Any]  # Vector3 or numpy array if numpy is available
    direction: Union[Vector3, Any]
    wavelength: float
    color: str
    path_segments: List[Tuple[Any, Any]]  # List of (start, end) points
    
    def __post_init__(self):
        if HAS_NUMPY and isinstance(self.origin, (list, tuple, np.ndarray)):
            self.origin = np.array(self.origin)
            self.direction = np.array(self.direction)
            self.direction = self.direction / np.linalg.norm(self.direction)
        else:
            if not isinstance(self.origin, Vector3):
                self.origin = Vector3(*self.origin)
            if not isinstance(self.direction, Vector3):
                self.direction = Vector3(*self.direction)
            self.direction = self.direction.normalize()


class InteractiveRayTracer:
    """Interactive ray tracing using the core SystemRayTracer3D."""
    
    def __init__(self, optical_system):
        self.optical_system = optical_system
        self.interactive_rays: List[InteractiveRay] = []
        self.selected_ray: Optional[InteractiveRay] = None
        self.ray_colors = ['red', 'blue', 'green', 'yellow', 'cyan', 'magenta']
        self.core_tracer = SystemRayTracer3D(optical_system)
        
    def add_ray(self, origin: Tuple[float, float, float], 
                direction: Tuple[float, float, float],
                wavelength: float = 0.0005876) -> InteractiveRay:
        """Add a new interactive ray."""
        color = self.ray_colors[len(self.interactive_rays) % len(self.ray_colors)]
        
        # Internal wavelength convention is mm
        # 587.6 nm -> 0.0005876 mm
        if wavelength > 1.0: # Likely nm
            wavelength = wavelength * 1e-6

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
        if HAS_NUMPY:
            ray.origin = np.array(new_origin)
        else:
            ray.origin = Vector3(*new_origin)
        self._trace_ray(ray)
    
    def update_ray_direction(self, ray: InteractiveRay,
                            new_direction: Tuple[float, float, float]):
        """Update ray direction and retrace."""
        if HAS_NUMPY:
            ray.direction = np.array(new_direction)
            ray.direction = ray.direction / np.linalg.norm(ray.direction)
        else:
            ray.direction = Vector3(*new_direction).normalize()
        self._trace_ray(ray)
    
    def update_ray_angle(self, ray: InteractiveRay, angle_degrees: float):
        """Update ray direction by angle (in XZ plane)."""
        angle_rad = math.radians(angle_degrees)
        new_dir = (math.cos(angle_rad), 0, math.sin(angle_rad))
        self.update_ray_direction(ray, new_dir)
    
    def _trace_ray(self, ray: InteractiveRay):
        """Trace a single ray using the core 3D ray tracer."""
        ray.path_segments.clear()
        
        # Convert to Vector3 for core tracer
        if HAS_NUMPY and isinstance(ray.origin, np.ndarray):
            origin = Vector3(float(ray.origin[0]), float(ray.origin[1]), float(ray.origin[2]))
            direction = Vector3(float(ray.direction[0]), float(ray.direction[1]), float(ray.direction[2]))
        else:
            origin = ray.origin
            direction = ray.direction
            
        # Create core ray object
        core_ray = Ray3D(origin, direction, wavelength=ray.wavelength)
        
        # Trace through system
        self.core_tracer.trace_ray(core_ray)
        
        # Convert path back to segments
        for i in range(len(core_ray.path) - 1):
            p1 = core_ray.path[i]
            p2 = core_ray.path[i+1]
            
            if HAS_NUMPY:
                s1 = np.array([p1.x, p1.y, p1.z])
                s2 = np.array([p2.x, p2.y, p2.z])
            else:
                s1 = p1
                s2 = p2
                
            ray.path_segments.append((s1, s2))
    
    def _find_next_intersection(self, pos, direction):
        # Legacy method, no longer used but kept for internal API if needed
        return None
    
    def _intersect_surface(self, pos, direction, surface):
        # Legacy method
        return None
    
    def _calculate_surface_normal(self, surface, point):
        # Legacy method
        return Vector3(0, 0, 1)
    
    def _calculate_ray_interaction(self, incident, normal, surface, wavelength):
        # Legacy method
        return None
    
    def get_ray_info(self, ray: InteractiveRay) -> Dict[str, Any]:
        """Get detailed information about a ray."""
        total_path_length = 0.0
        
        def get_norm(v):
            if HAS_NUMPY and isinstance(v, np.ndarray):
                return np.linalg.norm(v)
            return v.magnitude()

        for start, end in ray.path_segments:
            total_path_length += get_norm(end - start)
        
        def to_list(v):
            if HAS_NUMPY and isinstance(v, np.ndarray):
                return v.tolist()
            return [v.x, v.y, v.z]

        return {
            'origin': to_list(ray.origin),
            'direction': to_list(ray.direction),
            'wavelength': ray.wavelength,
            'color': ray.color,
            'num_segments': len(ray.path_segments),
            'total_path_length': total_path_length,
            'final_position': to_list(ray.path_segments[-1][1]) if ray.path_segments else None
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
            # Update origin (XZ plane)
            new_origin = (mouse_pos[0], 0, mouse_pos[1])
            self.tracer.update_ray_origin(ray, new_origin)
        
        elif self.drag_mode == 'direction':
            # Calculate angle from origin to mouse
            def get_coord(v, idx):
                if HAS_NUMPY and isinstance(v, np.ndarray):
                    return v[idx]
                return [v.x, v.y, v.z][idx]

            dx = mouse_pos[0] - get_coord(ray.origin, 0)
            dz = mouse_pos[1] - get_coord(ray.origin, 2)
            angle = math.degrees(math.atan2(dz, dx))
            self.tracer.update_ray_angle(ray, angle)
    
    def end_drag(self):
        """End dragging."""
        self.drag_mode = None
        self.drag_start = None
    
    def find_ray_at_position(self, pos: Tuple[float, float], 
                            tolerance: float = 0.5) -> Optional[InteractiveRay]:
        """Find ray near mouse position."""
        for ray in self.tracer.interactive_rays:
            # Check if near origin (XZ plane)
            def get_coord(v, idx):
                if HAS_NUMPY and isinstance(v, np.ndarray):
                    return v[idx]
                return [v.x, v.y, v.z][idx]

            ox, oz = get_coord(ray.origin, 0), get_coord(ray.origin, 2)
            dist = math.sqrt((pos[0] - ox)**2 + (pos[1] - oz)**2)
            if dist < tolerance:
                return ray
        return None
    
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
