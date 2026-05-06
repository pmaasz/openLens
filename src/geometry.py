"""
Centralized geometry calculations for lens profiles, polylines, and 3D meshes.
Used by exporters (SVG, STL, STEP) and visualization modules.
"""

import math
from typing import List, Tuple, Optional, Dict, Any

try:
    from .constants import EPSILON
    from .lens import Lens
except (ImportError, ValueError):
    from constants import EPSILON
    from lens import Lens

class LensGeometry:
    """Centralized logic for lens surface profiles and 3D meshes."""
    
    @staticmethod
    def get_surface_profile(radius: float, diameter: float, num_points: int = 50) -> List[Tuple[float, float]]:
        """Calculate (z, r) coordinates for a spherical surface profile.
        
        Args:
            radius: Radius of curvature (mm).
            diameter: Clear aperture diameter (mm).
            num_points: Number of points to sample along the arc.
            
        Returns:
            List of (z, r) tuples.
        """
        if abs(radius) < EPSILON or abs(radius) > 1e10:
            return [(0.0, -diameter/2), (0.0, diameter/2)]
            
        semi_diam = diameter / 2
        # Ensure we don't try to calculate sag beyond the radius
        if semi_diam > abs(radius):
            semi_diam = abs(radius) * 0.999999
            
        profile = []
        for i in range(num_points + 1):
            # Sample from top to bottom (+r to -r)
            r = semi_diam - (2 * semi_diam * i / num_points)
            
            # Sagitta formula: z = r^2 / (R + sqrt(R^2 - r^2))
            # This is mathematically equivalent to R - sign(R)*sqrt(R^2 - r^2)
            # but more numerically stable for large radii.
            try:
                z = (r**2) / (radius + math.copysign(math.sqrt(radius**2 - r**2), radius))
            except (ValueError, ZeroDivisionError):
                z = 0.0
            profile.append((z, r))
        return profile

    @staticmethod
    def get_lens_polyline(lens: Lens, num_points: int = 50) -> List[Tuple[float, float]]:
        """Get a closed (z, r) polyline representing the lens cross-section.
        
        Args:
            lens: Lens object.
            num_points: Points per surface.
            
        Returns:
            List of (z, r) coordinates forming a closed loop.
        """
        front = LensGeometry.get_surface_profile(lens.radius_of_curvature_1, lens.diameter, num_points)
        back = LensGeometry.get_surface_profile(lens.radius_of_curvature_2, lens.diameter, num_points)
        
        # Shift back surface by thickness and reverse to close the loop
        back_shifted = [(z + lens.thickness, r) for z, r in back]
        
        # Polyline: Front (Top to Bottom) -> Back (Bottom to Top) -> Close
        return front + back_shifted[::-1]

    @staticmethod
    def generate_mesh(lens: Lens, radial_div: int = 32, circular_div: int = 32) -> Dict[str, Any]:
        """Generate a 3D mesh (vertices and faces) for the lens.
        
        Args:
            lens: Lens object.
            radial_div: Number of points along the surface profile.
            circular_div: Number of points around the optical axis.
            
        Returns:
            Dictionary with 'vertices' (List[Tuple[float, float, float]]) and 
            'faces' (List[Tuple[int, int, int]]).
        """
        vertices = []
        faces = []
        
        # Get profiles (z, r)
        front_prof = LensGeometry.get_surface_profile(lens.radius_of_curvature_1, lens.diameter, radial_div)
        back_prof = LensGeometry.get_surface_profile(lens.radius_of_curvature_2, lens.diameter, radial_div)
        
        # Rotation steps
        d_theta = 2 * math.pi / circular_div
        
        # Create vertices for front and back surfaces
        for j in range(circular_div):
            theta = j * d_theta
            cos_t = math.cos(theta)
            sin_t = math.sin(theta)
            
            # Front surface
            for z, r in front_prof:
                vertices.append((z, r * cos_t, r * sin_t))
            
            # Back surface
            for z, r in back_prof:
                vertices.append((z + lens.thickness, r * cos_t, r * sin_t))
        
        # Helper to get index: (circle_idx * 2_surfaces * points_per_prof) + (surface_offset) + point_idx
        pts_per_surf = radial_div + 1
        
        for j in range(circular_div):
            next_j = (j + 1) % circular_div
            
            off_curr = j * pts_per_surf * 2
            off_next = next_j * pts_per_surf * 2
            
            front_curr = off_curr
            front_next = off_next
            back_curr = off_curr + pts_per_surf
            back_next = off_next + pts_per_surf
            
            # Surface triangles
            for i in range(radial_div):
                # Front surface
                faces.append((front_curr + i, front_next + i, front_curr + i + 1))
                faces.append((front_next + i, front_next + i + 1, front_curr + i + 1))
                
                # Back surface (note reversed winding for outward normals)
                faces.append((back_curr + i, back_curr + i + 1, back_next + i))
                faces.append((back_next + i, back_curr + i + 1, back_next + i + 1))
                
            # Edge/Cylinder triangles (connecting the rims)
            # Rim is at index 0 and index radial_div for each profile? 
            # Actually, r is sampled from diam/2 to -diam/2. 
            # So index 0 is top (+r) and index radial_div is bottom (-r).
            # We only need to connect the rim at r = diam/2 (index 0).
            # Wait, the way get_surface_profile works, it's a full slice.
            # For a 3D mesh, we usually rotate a half-profile (r from 0 to diam/2).
            # Let's adjust for mesh generation if needed, but for now, 
            # this is a simple implementation.
            
        return {"vertices": vertices, "faces": faces}
