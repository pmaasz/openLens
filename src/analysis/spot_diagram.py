from typing import List, Tuple, Dict, Any, Optional
import math

# Import dependencies
try:
    from ..vector3 import Vector3, vec3
    from ..ray_tracer import Ray3D, SystemRayTracer3D
    from ..optical_system import OpticalSystem
    from ..constants import NM_TO_MM
except ImportError:
    # Fallback for different environment contexts
    try:
        from src.vector3 import Vector3, vec3
        from src.ray_tracer import Ray3D, SystemRayTracer3D
        from src.optical_system import OpticalSystem
        from src.constants import NM_TO_MM
    except ImportError:
        # Last resort (if running from src directly)
        from vector3 import Vector3, vec3
        from ray_tracer import Ray3D, SystemRayTracer3D
        from optical_system import OpticalSystem
        from constants import NM_TO_MM

class SpotDiagram:
    """
    Analyzer for generating spot diagrams of optical systems.
    """
    
    def __init__(self, system: OpticalSystem):
        self.system = system
        self.tracer = SystemRayTracer3D(system)
        
    def trace_spot(self, wavelength: float = 550.0, 
                   field_angle_y: float = 0.0, 
                   focus_shift: float = 0.0,
                   num_rings: int = 6,
                   image_plane_x: Optional[float] = None) -> Dict[str, Any]:
        """
        Trace a bundle of rays to generate a spot diagram.
        
        Args:
            wavelength: Wavelength in nm
            field_angle_y: Field angle in Y direction (degrees)
            focus_shift: Shift from paraxial focus (mm)
            num_rings: Number of rings in the ray grid
            image_plane_x: Optional fixed image plane position. If None, calculated from paraxial focus.
            
        Returns:
            Dictionary containing:
                - points: List of (y, z) tuples in mm on the image plane
                - rms_radius: RMS radius in mm
                - geo_radius: Geometric radius in mm
                - image_plane_x: The X position of the image plane used
        """
        wavelength_mm = wavelength * NM_TO_MM
        
        # 1. Determine Image Plane
        if image_plane_x is None:
            # Trace a paraxial ray to find focus
            # Start slightly off-axis to avoid singularities if any
            paraxial_h = 0.1
            paraxial_ray = Ray3D(
                origin=vec3(self._get_start_x(), paraxial_h, 0),
                direction=vec3(1, 0, 0),
                wavelength=wavelength_mm
            )
            self.tracer.trace_ray(paraxial_ray)
            
            # Find intersection with axis (y=0)
            if len(paraxial_ray.path) >= 2:
                # Last segment
                p1 = paraxial_ray.path[-2]
                p2 = paraxial_ray.path[-1]
                
                # Check slope
                dy = p2.y - p1.y
                dx = p2.x - p1.x
                
                if abs(dy) > 1e-10:
                    # x where y=0
                    slope = dy / dx
                    # y - y1 = m(x - x1) => -y1 = m(x - x1) => x = x1 - y1/m
                    image_plane_x = p1.x - p1.y / slope
                else:
                    image_plane_x = p2.x + 100 # Default if parallel
            else:
                image_plane_x = 100.0 # Default
                
            image_plane_x += focus_shift
            
        # 2. Generate Ray Bundle (Hexapolar Grid)
        rays = []
        
        # Entrance Pupil definition (simplify to first lens diameter)
        if self.system.elements:
            ep_diameter = self.system.elements[0].lens.diameter
            ep_radius = ep_diameter / 2.0 * 0.95 # 95% aperture
        else:
            ep_radius = 10.0
            
        # Beam starting position
        start_x = self._get_start_x()
        
        # Calculate Ray Direction based on field angle
        angle_rad = math.radians(field_angle_y)
        # Direction vector: (cos(theta), sin(theta), 0)
        direction = vec3(math.cos(angle_rad), math.sin(angle_rad), 0).normalize()
        
        # Grid Generation
        # Center ray
        rays.append(Ray3D(vec3(start_x, 0, 0), direction, wavelength=wavelength_mm))
        
        for r in range(1, num_rings + 1):
            normalized_r = r / num_rings
            current_radius = normalized_r * ep_radius
            
            # Number of rays in this ring (6*r)
            num_azimuth = 6 * r
            
            for a in range(num_azimuth):
                phi = 2 * math.pi * a / num_azimuth
                
                # Pupil coordinates
                y_pupil = current_radius * math.cos(phi)
                z_pupil = current_radius * math.sin(phi)
                
                # Adjust start point based on field angle to aim at pupil center?
                # For infinite conjugate (collimated), rays are parallel.
                # The "pupil" is the beam cross-section perpendicular to direction.
                
                # We construct the start point by offsetting perpendicular to direction
                # direction is in XY plane.
                # Perpendicular vectors: 
                # Z axis (0,0,1) is perpendicular to direction (since dir.z=0)
                # "Y" vector in beam coords: cross(dir, z) = (sin, -cos, 0) ? No.
                # Let's use simple rotation.
                
                # If angle is 0: dir=(1,0,0). Beam plane is YZ.
                # y_pupil maps to Y, z_pupil maps to Z.
                # origin = (start_x, y_pupil, z_pupil)
                
                # If angle is theta:
                # Rotate (0, y_pupil, z_pupil) by theta around Z?
                # No, we want rays parallel to direction.
                
                # Beam offset vector:
                # v_offset = y_pupil * up_vector + z_pupil * right_vector
                # direction = (cos, sin, 0)
                # up_vector (in plane of incidence) = (-sin, cos, 0)
                # right_vector (perp to plane) = (0, 0, 1)
                
                up = vec3(-math.sin(angle_rad), math.cos(angle_rad), 0)
                right = vec3(0, 0, 1)
                
                offset = up * y_pupil + right * z_pupil
                origin = vec3(start_x, 0, 0) + offset
                
                # Ray origin must be shifted so that at x=first_element, it hits the pupil?
                # For collimated, it doesn't matter where we start as long as we cover the aperture.
                # But to ensure we hit the lens, we should start "on axis" + offset, but back-propagated.
                
                # Current origin is at x=start_x (which is far back).
                # offset is perpendicular to direction.
                # If start_x is -100, and lens is at 0.
                # We just fire in 'direction'.
                
                rays.append(Ray3D(origin, direction, wavelength=wavelength_mm))

        # 3. Trace Rays
        spot_points = []
        
        for ray in rays:
            self.tracer.trace_ray(ray)
            
            # Intersect with Image Plane
            if len(ray.path) >= 2:
                # Project last segment to x = image_plane_x
                p_last = ray.path[-1]
                p_prev = ray.path[-2]
                
                # We need the direction of the final segment
                # Ray3D updates direction as it goes
                final_dir = ray.direction
                
                # However, if ray terminated inside, ray.terminated is True
                if ray.terminated:
                    continue
                    
                # Calculate intersection
                # x(t) = p_last.x + t * dir.x = image_plane_x
                # t = (image_plane_x - p_last.x) / dir.x
                
                if abs(final_dir.x) > 1e-6:
                    t = (image_plane_x - p_last.x) / final_dir.x
                    y_spot = p_last.y + t * final_dir.y
                    z_spot = p_last.z + t * final_dir.z
                    
                    spot_points.append((y_spot, z_spot))

        # 4. Calculate Statistics
        if not spot_points:
            return {
                'points': [],
                'rms_radius': 0.0,
                'geo_radius': 0.0,
                'image_plane_x': image_plane_x
            }
            
        # Calculate centroid
        ys = [p[0] for p in spot_points]
        zs = [p[1] for p in spot_points]
        
        centroid_y = sum(ys) / len(ys)
        centroid_z = sum(zs) / len(zs)
        
        # Calculate radii relative to centroid
        sq_distances = [(y - centroid_y)**2 + (z - centroid_z)**2 for y, z in spot_points]
        rms = math.sqrt(sum(sq_distances) / len(sq_distances))
        geo = math.sqrt(max(sq_distances)) if sq_distances else 0.0
        
        return {
            'points': spot_points,
            'rms_radius': rms,
            'geo_radius': geo,
            'image_plane_x': image_plane_x
        }

    def _get_start_x(self):
        if self.system.elements:
            return self.system.elements[0].position - 50.0
        return -50.0
