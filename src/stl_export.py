#!/usr/bin/env python3
"""
openlens - STL Export Module
Exports lens geometry as STL files for 3D printing
"""

import struct
import math
from typing import List, Tuple, Optional, Any

try:
    from .vector3 import Vector3, vec3
except ImportError:
    import sys
    import os
    sys.path.insert(0, os.path.dirname(__file__))
    from vector3 import Vector3, vec3

class STLExporter:
    """Export lens geometry to STL format"""
    
    def __init__(self):
        self.triangles: List[Tuple[Tuple[float, float, float], Tuple[float, float, float], Tuple[float, float, float]]] = []
    
    def calculate_surface_profile(self, radius: float, diameter: float, is_front: bool = True, resolution: int = 50) -> Optional[List[Tuple[float, float]]]:
        """Calculate points on a spherical surface"""
        if abs(radius) > 10000:  # Treat as flat surface
            return None
        
        r = abs(radius)
        h = diameter / 2.0
        
        if h >= r:
            h = r * 0.99 # Slightly less than full hemisphere to avoid sqrt issues
        
        # Calculate sagitta at aperture
        sag = r - math.sqrt(r**2 - h**2)
        
        # Create radial points
        radial_points = []
        for i in range(resolution + 1):
            y = (i / resolution) * h
            
            # z coordinate relative to vertex
            # For a sphere centered at (0, 0, R) or (0, 0, -R)
            # Sag(y) = R - sqrt(R^2 - y^2)
            
            z_sag = r - math.sqrt(r**2 - y**2)
            
            # Sign convention: 
            # If Front Surface (light comes from -Z):
            #   Positive Radius (Convex): Center is at +Z. Vertex at 0. Surface bulges to -Z.
            #   Wait, standard convention:
            #   Front Convex (R>0): Center at +R. Surface at Z(y) = R - sqrt(R^2-y^2). 
            #   At y=0, z=0. At y=h, z > 0? No, convex means it bulges towards incoming light (left).
            #   Usually vertex is at 0.
            #   If R>0 (Convex), center is at +R. Surface points satisfy (z-R)^2 + y^2 = R^2.
            #   z = R - sqrt(R^2 - y^2). This yields z>0 for y>0. This curves "backwards" (away from light).
            #   A "Biconvex" lens has Front R>0, Back R<0.
            #   Front Surface (R>0): Vertex at 0. Bulges RIGHT? No, standard biconvex bulges OUT.
            #   Let's check `Lens` class or ray tracer.
            #   Ray Tracer: Center = (x + R, 0, 0).
            #   Surface: (x - cx)^2 + ... = R^2
            #   If R>0, cx = x0 + R. Vertex at x0.
            #   (x - (x0+R))^2 + y^2 = R^2
            #   x - x0 - R = -sqrt(R^2 - y^2)  (taking left hemisphere)
            #   x = x0 + R - sqrt(R^2 - y^2)
            #   At y=0, x=x0. At y=h, x > x0.
            #   So R>0 is convex (bulges to right).
            #   Wait, usually "Convex" front surface means it collects light.
            #   If light travels +Z, and surface bulges to -Z, it's convex?
            #   Standard convention: R>0 means center of curvature is to the right.
            #   So a front surface with R>0 bulges to the right (away from object). That is CONCAVE for incoming light.
            #   A standard biconvex lens has R1 > 0, R2 < 0?
            #   Let's check `src/lens.py`.
            #   Default: R1=100 (Convex), R2=-100 (Convex).
            #   Wait, if R1=100, Center is at +100. Vertex at 0. Surface curve is to the right.
            #   That means the glass is to the left? No, glass is to the right of front surface.
            #   If glass is to right, and surface curves to right, then it is CONVEX.
            #   Visual: ( object )   ( lens )
            #            |          /      \
            #   Front surface: /  (bulges left)
            #   Center of curvature for / is to the Right. So R > 0.
            #   Equation: (z - R)^2 + y^2 = R^2 => z = R - sqrt(R^2 - y^2).
            #   At y=0, z=0. At y=h, z>0.
            #   This surface bulges to the RIGHT.
            #   If it bulges to the right, and glass is to the right, then it is CONCAVE.
            #   
            #   Let's re-verify the ray tracer logic.
            #   `LensRayTracer.intersect_spherical`:
            #   center = vector(lens.radius, 0, 0) (relative to vertex at 0)
            #   Ray origin 0,0,0.
            #   Collision with sphere.
            
            #   If R1=100. Center=(100,0,0). Vertex=0.
            #   Surface is left hemisphere of sphere at x=100.
            #   Points: x = 100 - sqrt(100^2 - y^2).
            #   y=0 -> x=0.
            #   y=10 -> x = 100 - 99.5 = 0.5.
            #   So surface curves to the RIGHT (positive X).
            #   If glass is in +X, this is a CONVEX surface.
            #   Wait, "Convex" means "Bulging out".
            #   If I hold a ball, the surface is convex.
            #   If R1=100, the surface shape is ) (bulges left).
            #   NO. Center is at +100.
            #   Sphere is at +100.
            #   Vertex is at 0.
            #   The surface at 0 is the "left side" of the sphere.
            #   The sphere is to the right.
            #   So the surface shape is ( .
            #   That looks convex from the outside (left).
            #   So R1>0 is Convex. Correct.
            
            #   Implementation here:
            #   z_sag = r - math.sqrt(r**2 - y**2) (always positive)
            
            if is_front:
                # If R>0 (Convex), surface moves +Z as y increases.
                if radius > 0:
                     z = z_sag
                else:
                    # R<0 (Concave). Center at -R.
                    # Vertex at 0.
                    # Surface is right hemisphere of sphere at -R.
                    # x = -R + sqrt(R^2 - y^2).
                    # y=0 -> x=0. y=h -> x < 0.
                    # Surface moves -Z.
                    z = -z_sag
            else: # Back surface
                # Vertex is at `thickness`. Glass is to the left ( < thickness).
                # If R2 < 0 (Convex back). Center is at thickness + R2 (so left of thickness).
                # Surface is right hemisphere.
                # x = center + sqrt...
                # x = (thick - |R2|) + sqrt(R2^2 - y^2).
                # y=0 -> x=thick. y=h -> x < thick.
                # So surface moves -Z (left).
                
                if radius < 0: # Convex back
                    z = -z_sag
                else: # Concave back (R2 > 0)
                    # Center at thick + R.
                    # x = thick + R - sqrt...
                    # y=0 -> x=thick. y=h -> x > thick.
                    # Surface moves +Z (right).
                    z = z_sag
                    
            radial_points.append((y, z))
        
        return radial_points
    
    def generate_surface_triangles(self, profile_points: List[Tuple[float, float]], z_offset: float, num_segments: int = 60):
        """Generate triangles for a surface of revolution"""
        if not profile_points:
            return []
        
        triangles = []
        angle_step = 2 * math.pi / num_segments
        
        # Generate points around the circle
        for seg in range(num_segments):
            angle1 = seg * angle_step
            angle2 = (seg + 1) * angle_step
            
            cos1, sin1 = math.cos(angle1), math.sin(angle1)
            cos2, sin2 = math.cos(angle2), math.sin(angle2)
            
            # Create triangles for each radial segment
            for i in range(len(profile_points) - 1):
                r1, z1 = profile_points[i]
                r2, z2 = profile_points[i + 1]
                
                # Four points of the quad
                # Add z_offset to the profile z
                p1 = (r1 * cos1, r1 * sin1, z1 + z_offset)
                p2 = (r2 * cos1, r2 * sin1, z2 + z_offset)
                p3 = (r2 * cos2, r2 * sin2, z2 + z_offset)
                p4 = (r1 * cos2, r1 * sin2, z1 + z_offset)
                
                # Handle singularity at center (r1 ~ 0)
                if r1 < 1e-9:
                    # Triangle fan at center
                    # p1 and p4 are the same (the center point)
                    # Only emit one triangle: Center -> Outer1 -> Outer2
                    # (p1, p2, p3)
                    triangles.append((p1, p2, p3))
                else:
                    # Full quad
                    triangles.append((p1, p2, p3))
                    triangles.append((p1, p3, p4))
        
        return triangles
    
    def generate_flat_surface(self, diameter: float, z_offset: float, num_segments: int = 60, is_front: bool = True):
        """Generate triangles for a flat surface"""
        triangles = []
        radius = diameter / 2.0
        angle_step = 2 * math.pi / num_segments
        
        center = (0.0, 0.0, z_offset)
        
        for seg in range(num_segments):
            angle1 = seg * angle_step
            angle2 = (seg + 1) * angle_step
            
            p1 = (radius * math.cos(angle1), radius * math.sin(angle1), z_offset)
            p2 = (radius * math.cos(angle2), radius * math.sin(angle2), z_offset)
            
            # Winding order depends on facing
            if is_front:
                # Normal -Z (if it's a flat front surface)
                triangles.append((center, p2, p1))
            else:
                # Normal +Z (if it's a flat back surface)
                triangles.append((center, p1, p2))
        
        return triangles
    
    def generate_edge_triangles(self, diameter: float, z_front_arr: Any, z_back_arr: Any, num_segments: int = 60):
        """
        Generate triangles for the cylindrical edge.
        z_front_arr: Z coordinate of front edge (float or list)
        z_back_arr: Z coordinate of back edge (float or list)
        """
        triangles = []
        radius = diameter / 2.0
        angle_step = 2 * math.pi / num_segments
        
        for seg in range(num_segments):
            angle1 = seg * angle_step
            angle2 = (seg + 1) * angle_step
            
            cos1, sin1 = math.cos(angle1), math.sin(angle1)
            cos2, sin2 = math.cos(angle2), math.sin(angle2)
            
            zf1 = z_front_arr[seg] if isinstance(z_front_arr, list) else z_front_arr
            zf2 = z_front_arr[seg+1] if isinstance(z_front_arr, list) else z_front_arr
            
            zb1 = z_back_arr[seg] if isinstance(z_back_arr, list) else z_back_arr
            zb2 = z_back_arr[seg+1] if isinstance(z_back_arr, list) else z_back_arr
            
            # Four corners
            p1 = (radius * cos1, radius * sin1, zf1) # Front 1
            p2 = (radius * cos2, radius * sin2, zf2) # Front 2
            p3 = (radius * cos2, radius * sin2, zb2) # Back 2
            p4 = (radius * cos1, radius * sin1, zb1) # Back 1
            
            # Edge normals point out (radially)
            # Winding: p1, p2, p3
            triangles.append((p1, p3, p2)) # 1-3-2?
            # Let's check: 1->2 is CCW around Z. 
            # 1 is Front (e.g. z=0), 3 is Back (e.g. z=5).
            # 1=(1,0,0), 2=(0,1,0). 3=(0,1,5).
            # v1 = 3-1 = (-1, 1, 5). v2 = 2-1 = (-1, 1, 0).
            # Cross: (1*0 - 5*1, ...) = -5. Normal points In?
            # Correct is likely (p1, p4, p3) and (p1, p3, p2) or similar.
            
            # Use p4 (Back 1), p3 (Back 2), p2 (Front 2), p1 (Front 1)
            # 1 -> 2 (Front CCW). 
            # Quad 1-2-3-4.
            # Triangle 1: 1-2-4? (Front1, Front2, Back1). 
            # Normal: (2-1) x (4-1).
            # (2-1) is Tangential CCW. (4-1) is Axial (+Z).
            # Tangent x Axial = Radial Out.
            # So (p1, p2, p4) is correct for outward normal.
            triangles.append((p1, p2, p4))
            
            # Triangle 2: 2-3-4? (Front2, Back2, Back1).
            # Normal: (3-2) x (4-2).
            # (3-2) is Axial (+Z). (4-2) is Tangential CW (-Tangent).
            # Axial x (-Tangent) = - (Axial x Tangent) = - (-Radial) = Radial Out.
            # So (p2, p3, p4) is correct.
            triangles.append((p2, p3, p4))
        
        return triangles
    
    def calculate_normal(self, p1: Tuple[float, float, float], 
                         p2: Tuple[float, float, float], 
                         p3: Tuple[float, float, float]) -> Tuple[float, float, float]:
        """Calculate normal vector for a triangle using Vector3"""
        v1 = Vector3(p2[0] - p1[0], p2[1] - p1[1], p2[2] - p1[2])
        v2 = Vector3(p3[0] - p1[0], p3[1] - p1[1], p3[2] - p1[2])
        
        normal = v1.cross(v2).normalize()
        return (normal.x, normal.y, normal.z)
    
    def export_lens_to_stl(self, r1: float, r2: float, thickness: float, diameter: float, filename: str, resolution: int = 50) -> int:
        """Export a lens to STL format"""
        self.triangles = []
        
        # 1. Front Surface (R1)
        # Vertex at (0,0,0).
        profile1 = self.calculate_surface_profile(r1, diameter, is_front=True, resolution=resolution)
        if profile1:
            self.triangles.extend(self.generate_surface_triangles(profile1, 0.0, num_segments=resolution*2))
            last_z_front = profile1[-1][1] # Z at the edge
        else:
            # Flat
            self.triangles.extend(self.generate_flat_surface(diameter, 0.0, num_segments=resolution*2, is_front=True))
            last_z_front = 0.0
            
        # 2. Back Surface (R2)
        # Vertex at (0,0,thickness)
        profile2 = self.calculate_surface_profile(r2, diameter, is_front=False, resolution=resolution)
        if profile2:
            self.triangles.extend(self.generate_surface_triangles(profile2, thickness, num_segments=resolution*2))
            last_z_back = profile2[-1][1] + thickness # Add offset
        else:
            # Flat
            self.triangles.extend(self.generate_flat_surface(diameter, thickness, num_segments=resolution*2, is_front=False))
            last_z_back = thickness
            
        # 3. Edge
        # Edge connects last_z_front ring to last_z_back ring at diameter/2
        self.triangles.extend(self.generate_edge_triangles(diameter, last_z_front, last_z_back, num_segments=resolution*2))
        
        # Write
        self.write_binary_stl(filename)
        return len(self.triangles)
    
    def write_binary_stl(self, filename: str):
        """Write triangles to binary STL file"""
        with open(filename, 'wb') as f:
            # Header (80 bytes)
            header = b'openlens STL export' + b' ' * (80 - 19)
            f.write(header)
            
            # Number of triangles
            f.write(struct.pack('<I', len(self.triangles)))
            
            # Write each triangle
            for triangle in self.triangles:
                p1, p2, p3 = triangle
                
                normal = self.calculate_normal(p1, p2, p3)
                
                f.write(struct.pack('<fff', normal[0], normal[1], normal[2]))
                f.write(struct.pack('<fff', p1[0], p1[1], p1[2]))
                f.write(struct.pack('<fff', p2[0], p2[1], p2[2]))
                f.write(struct.pack('<fff', p3[0], p3[1], p3[2]))
                f.write(struct.pack('<H', 0))

def export_lens_stl(lens: Any, filename: str, resolution: int = 50) -> int:
    """Wrapper for Lens object"""
    exporter = STLExporter()
    return exporter.export_lens_to_stl(
        lens.radius_of_curvature_1,
        lens.radius_of_curvature_2,
        lens.thickness,
        lens.diameter,
        filename,
        resolution
    )

if __name__ == "__main__":
    exporter = STLExporter()
    exporter.export_lens_to_stl(100, -100, 5, 50, "test_lens.stl")
    print("Done")
