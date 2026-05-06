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
    from .geometry import LensGeometry
except ImportError:
    import sys
    import os
    sys.path.insert(0, os.path.dirname(__file__))
    from vector3 import Vector3, vec3
    from geometry import LensGeometry

class STLExporter:
    """Export lens geometry to STL format"""
    
    def __init__(self):
        self.triangles: List[Tuple[Tuple[float, float, float], Tuple[float, float, float], Tuple[float, float, float]]] = []
    
    def calculate_surface_profile(self, radius: float, diameter: float, is_front: bool = True, resolution: int = 50) -> Optional[List[Tuple[float, float]]]:
        """Calculate points on a spherical surface"""
        # Use centralized geometry logic
        profile = LensGeometry.get_surface_profile(radius, diameter, resolution)
        
        # Original STL exporter used (y, z) format where y is radial and z is axial.
        # LensGeometry returns (z, r) where r is radial.
        # We need to adapt it. 
        # Note: LensGeometry returns full profile (top to bottom). 
        # STL exporter wants half-profile (0 to h).
        
        half_profile = []
        # Profiles are returned top to bottom. Middle point (r=0) is at index resolution/2 if resolution is even.
        # Let's just recalculate the half for clarity if needed, or filter.
        # Actually, let's just use the logic from LensGeometry to get the half-profile.
        
        h = diameter / 2.0
        for i in range(resolution + 1):
            y = (i / resolution) * h # 0 to h
            # Re-use LensGeometry's stable sag calculation
            if abs(radius) < 1e-10 or abs(radius) > 1e10:
                z_sag = 0.0
            else:
                try:
                    z_sag = (y**2) / (radius + math.copysign(math.sqrt(radius**2 - y**2), radius))
                except (ValueError, ZeroDivisionError):
                    z_sag = 0.0
            
            # Apply STL exporter's specific sign logic
            z = z_sag
            if is_front:
                if radius < 0: z = -z_sag
            else:
                if radius < 0: z = -z_sag
            
            half_profile.append((y, z))
            
        return half_profile
    
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

def export_lens_stl(item: Any, filename: str, resolution: int = 50) -> int:
    """Wrapper for Lens or OpticalSystem object"""
    exporter = STLExporter()
    
    # Check if it's an OpticalSystem
    if hasattr(item, 'elements') and hasattr(item, 'air_gaps'):
        # Export entire assembly
        exporter.triangles = []
        for element in item.elements:
            lens = element.lens
            pos = element.position
            
            # Generate lens triangles
            # 1. Front Surface
            profile1 = exporter.calculate_surface_profile(lens.radius_of_curvature_1, lens.diameter, is_front=True, resolution=resolution)
            if profile1:
                exporter.triangles.extend(exporter.generate_surface_triangles(profile1, pos, num_segments=resolution*2))
                last_z_front = profile1[-1][1] + pos
            else:
                exporter.triangles.extend(exporter.generate_flat_surface(lens.diameter, pos, num_segments=resolution*2, is_front=True))
                last_z_front = pos
                
            # 2. Back Surface
            profile2 = exporter.calculate_surface_profile(lens.radius_of_curvature_2, lens.diameter, is_front=False, resolution=resolution)
            if profile2:
                exporter.triangles.extend(exporter.generate_surface_triangles(profile2, pos + lens.thickness, num_segments=resolution*2))
                last_z_back = profile2[-1][1] + pos + lens.thickness
            else:
                exporter.triangles.extend(exporter.generate_flat_surface(lens.diameter, pos + lens.thickness, num_segments=resolution*2, is_front=False))
                last_z_back = pos + lens.thickness
                
            # 3. Edge
            exporter.triangles.extend(exporter.generate_edge_triangles(lens.diameter, last_z_front, last_z_back, num_segments=resolution*2))
            
        exporter.write_binary_stl(filename)
        return len(exporter.triangles)
    
    # Single lens
    return exporter.export_lens_to_stl(
        item.radius_of_curvature_1,
        item.radius_of_curvature_2,
        item.thickness,
        item.diameter,
        filename,
        resolution
    )

if __name__ == "__main__":
    exporter = STLExporter()
    exporter.export_lens_to_stl(100, -100, 5, 50, "test_lens.stl")
    print("Done")
