import math
import statistics
from typing import List, Tuple, Optional, Dict, Any
try:
    from ..vector3 import Vector3, vec3
    from ..ray_tracer import Ray3D, SystemRayTracer3D
    from ..optical_system import OpticalSystem
    from ..constants import NM_TO_MM, WAVELENGTH_GREEN
except ImportError:
    # Fallback for direct execution or if .. resolution fails
    # This might happen if running as script from src/analysis/
    try:
        from vector3 import Vector3, vec3
        from ray_tracer import Ray3D, SystemRayTracer3D
        from optical_system import OpticalSystem
        from constants import NM_TO_MM, WAVELENGTH_GREEN
    except ImportError:
         # Try absolute imports from src root if running from project root
         import sys
         import os
         sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
         from vector3 import Vector3, vec3
         from ray_tracer import Ray3D, SystemRayTracer3D
         from optical_system import OpticalSystem
         from constants import NM_TO_MM, WAVELENGTH_GREEN

class SpotDiagram:
    """
    Spot Diagram Analysis Tool.
    Generates and analyzes spot diagrams for optical systems.
    """
    
    def __init__(self, system: OpticalSystem):
        self.system = system
        self.tracer = SystemRayTracer3D(system)
        
    def generate_hexapolar_grid(self, rings: int = 6, diameter: Optional[float] = None) -> List[Tuple[float, float]]:
        """
        Generate a hexapolar grid of points in the entrance pupil.
        
        Args:
            rings: Number of rings in the hexapolar grid.
            diameter: Diameter of the entrance pupil. If None, uses system first lens diameter.
            
        Returns:
            List of (y, z) offsets from the optical axis.
        """
        if diameter is None:
            if self.system.elements:
                diameter = self.system.elements[0].lens.diameter
            else:
                return [(0.0, 0.0)]
                
        radius = diameter / 2.0
        points = [(0.0, 0.0)] # Center point
        
        for i in range(1, rings + 1):
            num_points = 6 * i
            r = radius * (i / rings)
            for j in range(num_points):
                angle = 2 * math.pi * j / num_points
                y = r * math.cos(angle)
                z = r * math.sin(angle)
                points.append((y, z))
                
        return points
        
    def trace_spot(self, 
                  field_angle_x: float = 0.0, 
                  field_angle_y: float = 0.0, 
                  wavelength: float = WAVELENGTH_GREEN,
                  image_plane_x: Optional[float] = None,
                  num_rings: int = 6,
                  focus_shift: float = 0.0) -> Dict[str, Any]:
        """
        Trace rays to generate a spot diagram.
        
        Args:
            field_angle_x: Field angle in degrees (X-Z plane tilt? No, usually field is defined by angle)
                           Since X is optical axis:
                           field_angle_y: Angle in XY plane (tilts direction y component)
                           field_angle_z: Angle in XZ plane (tilts direction z component)
                           Let's treat inputs as angles in degrees.
            field_angle_y: Angle in degrees relative to optical axis in XY plane.
            wavelength: Wavelength in nm.
            image_plane_x: Absolute X position of image plane. If None, uses paraxial focus.
            num_rings: Sampling density.
            focus_shift: Offset from the nominal image plane (defocus).
            
        Returns:
            Dictionary containing spot data and statistics.
        """
        # Convert wavelength to mm
        wl_mm = wavelength * NM_TO_MM
        
        # Determine image plane position
        if image_plane_x is None:
            # Calculate paraxial focus position
            # Find system total length
            length = self.system.get_total_length()
            
            # Trace a paraxial ray to find focus
            start_x = self.system.elements[0].position - 10.0
            para_ray = Ray3D(vec3(start_x, 0.001, 0), vec3(1, 0, 0), wavelength=wl_mm)
            self.tracer.trace_ray(para_ray)
            
            # Find intersection with axis (y=0)
            if len(para_ray.path) >= 2:
                p2 = para_ray.path[-1]
                p1 = para_ray.path[-2]
                # Linear interpolation for y=0
                # y = m*x + c  -> x = (y-c)/m
                # slope m = (y2-y1)/(x2-x1)
                dx = p2.x - p1.x
                dy = p2.y - p1.y
                if abs(dy) > 1e-9:
                    slope = dy/dx
                    # y - y1 = m(x - x1) -> -y1 = m(x_focus - x1) -> x_focus = x1 - y1/m
                    x_focus = p1.x - p1.y / slope
                    image_plane_x = x_focus
                else:
                    image_plane_x = length + 100 # Default if collimated
            else:
                image_plane_x = length + 100
        
        target_x = image_plane_x + focus_shift
        
        # Generate pupil points
        pupil_points = self.generate_hexapolar_grid(rings=num_rings)
        
        # Calculate ray direction based on field angles
        # Tan(theta)
        tan_y = math.tan(math.radians(field_angle_y))
        tan_z = math.tan(math.radians(field_angle_x)) # using input x as 'other' angle (z-tilt)
        
        # Direction vector (normalized later by Ray3D)
        # dx=1, dy=tan_y, dz=tan_z
        direction = vec3(1.0, tan_y, tan_z).normalize()
        
        # Start rays before first element
        start_x = self.system.elements[0].position - 50.0
        
        spot_points = []
        valid_rays = 0
        
        for py, pz in pupil_points:
            # Launch ray from pupil coordinate projected back to start_x
            # The "Pupil" is usually defined at the first surface or a specific stop.
            # Simplified: Launch parallel bundle for infinite object
            # Ray origin = (start_x, py, pz) ?
            # For off-axis fields, the "beam" is tilted, but still fills the pupil?
            # Yes, vignetting might occur.
            
            first_lens_x = self.system.elements[0].position
            
            # Back-propagate from aperture to start position
            dist = first_lens_x - start_x
            # We want to be at (py, pz) when x = first_lens_x
            # direction is (dx, dy, dz)
            # P_lens = P_start + t * D
            # t = dist / D.x
            # P_start = P_lens - (dist/D.x) * D
            
            t = dist / direction.x
            origin = vec3(first_lens_x, py, pz) - direction * t
            
            ray = Ray3D(origin, direction, wavelength=wl_mm)
            self.tracer.trace_ray(ray)
            
            if not ray.terminated:
                # Find intersection with image plane X = target_x
                # P = O + t*D
                # P.x = O.x + t*D.x = target_x
                # t = (target_x - O.x) / D.x
                
                last_pt = ray.path[-1] # Usually endpoint of propagation
                # But ray might have stopped earlier or propagated further.
                # Ray3D.direction is the final direction.
                # Ray3D.origin is the last intersection point.
                
                if abs(ray.direction.x) > 1e-6:
                    t = (target_x - ray.origin.x) / ray.direction.x
                    
                    # If t is huge, ray might be parallel to plane (unlikely)
                    
                    spot_y = ray.origin.y + t * ray.direction.y
                    spot_z = ray.origin.z + t * ray.direction.z
                    
                    spot_points.append((spot_y, spot_z))
                    valid_rays += 1
                    
        # Calculate Statistics
        if not spot_points:
            return {
                'rms_radius': 0.0,
                'geo_radius': 0.0,
                'centroid': (0.0, 0.0),
                'points': [],
                'valid_rays': 0,
                'image_plane_x': target_x
            }
            
        # Centroid
        sum_y = sum(p[0] for p in spot_points)
        sum_z = sum(p[1] for p in spot_points)
        cent_y = sum_y / valid_rays
        cent_z = sum_z / valid_rays
        
        # RMS Radius (relative to centroid)
        sum_sq_dist = 0.0
        max_dist_sq = 0.0
        
        for y, z in spot_points:
            dy = y - cent_y
            dz = z - cent_z
            dist_sq = dy*dy + dz*dz
            sum_sq_dist += dist_sq
            if dist_sq > max_dist_sq:
                max_dist_sq = dist_sq
                
        rms_radius = math.sqrt(sum_sq_dist / valid_rays)
        geo_radius = math.sqrt(max_dist_sq)
        
        return {
            'rms_radius': rms_radius, # mm
            'geo_radius': geo_radius, # mm
            'centroid': (cent_y, cent_z), # mm
            'points': spot_points,
            'valid_rays': valid_rays,
            'image_plane_x': target_x
        }
