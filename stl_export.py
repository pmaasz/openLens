#!/usr/bin/env python3
"""
openlens - STL Export Module
Exports lens geometry as STL files for 3D printing
"""

import struct
import math
import numpy as np


class STLExporter:
    """Export lens geometry to STL format"""
    
    def __init__(self):
        self.triangles = []
    
    def calculate_surface_profile(self, radius, diameter, is_front=True, resolution=50):
        """Calculate points on a spherical surface"""
        if abs(radius) > 10000:  # Treat as flat surface
            return None
        
        r = abs(radius)
        h = diameter / 2
        
        if h >= r:
            h = r * 0.95
        
        # Calculate sagitta
        sag = r - math.sqrt(r**2 - h**2)
        
        # Create radial points
        radial_points = []
        for i in range(resolution + 1):
            y = (i / resolution) * h
            if y**2 <= r**2:
                if radius > 0:  # Convex
                    z = r - math.sqrt(r**2 - y**2)
                    if is_front:
                        z = -z
                else:  # Concave
                    z = -(r - math.sqrt(r**2 - y**2))
                    if is_front:
                        z = -z
                radial_points.append((y, z))
        
        return radial_points
    
    def generate_surface_triangles(self, profile_points, z_offset, num_segments=60):
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
                p1 = (r1 * cos1, r1 * sin1, z1 + z_offset)
                p2 = (r2 * cos1, r2 * sin1, z2 + z_offset)
                p3 = (r2 * cos2, r2 * sin2, z2 + z_offset)
                p4 = (r1 * cos2, r1 * sin2, z1 + z_offset)
                
                # Split quad into two triangles
                triangles.append((p1, p2, p3))
                triangles.append((p1, p3, p4))
        
        return triangles
    
    def generate_flat_surface(self, diameter, z_offset, num_segments=60):
        """Generate triangles for a flat surface"""
        triangles = []
        radius = diameter / 2
        angle_step = 2 * math.pi / num_segments
        
        center = (0, 0, z_offset)
        
        for seg in range(num_segments):
            angle1 = seg * angle_step
            angle2 = (seg + 1) * angle_step
            
            p1 = (radius * math.cos(angle1), radius * math.sin(angle1), z_offset)
            p2 = (radius * math.cos(angle2), radius * math.sin(angle2), z_offset)
            
            triangles.append((center, p1, p2))
        
        return triangles
    
    def generate_edge_triangles(self, diameter, z_front, z_back, num_segments=60):
        """Generate triangles for the cylindrical edge with correct z coordinates"""
        triangles = []
        radius = diameter / 2
        angle_step = 2 * math.pi / num_segments
        
        for seg in range(num_segments):
            angle1 = seg * angle_step
            angle2 = (seg + 1) * angle_step
            
            cos1, sin1 = math.cos(angle1), math.sin(angle1)
            cos2, sin2 = math.cos(angle2), math.sin(angle2)
            
            # Four corners of the quad with correct z coordinates
            p1 = (radius * cos1, radius * sin1, z_front)
            p2 = (radius * cos2, radius * sin2, z_front)
            p3 = (radius * cos2, radius * sin2, z_back)
            p4 = (radius * cos1, radius * sin1, z_back)
            
            # Split into two triangles
            triangles.append((p1, p2, p3))
            triangles.append((p1, p3, p4))
        
        return triangles
    
    def calculate_normal(self, p1, p2, p3):
        """Calculate normal vector for a triangle"""
        # Vectors
        v1 = np.array([p2[0] - p1[0], p2[1] - p1[1], p2[2] - p1[2]])
        v2 = np.array([p3[0] - p1[0], p3[1] - p1[1], p3[2] - p1[2]])
        
        # Cross product
        normal = np.cross(v1, v2)
        
        # Normalize
        length = np.linalg.norm(normal)
        if length > 0:
            normal = normal / length
        
        return normal
    
    def export_lens_to_stl(self, r1, r2, thickness, diameter, filename, resolution=50):
        """Export a lens to STL format"""
        self.triangles = []
        
        # Calculate edge z-coordinates at the diameter (same logic as visualizer)
        # For front surface (R1)
        if abs(r1) < 10000:
            r1_abs = abs(r1)
            h_edge = diameter / 2
            if h_edge < r1_abs:
                sag_front = r1_abs - math.sqrt(r1_abs**2 - h_edge**2)
                if r1 > 0:  # Convex front
                    z_front_edge = -sag_front
                else:  # Concave front
                    z_front_edge = sag_front
            else:
                z_front_edge = 0  # Flat at edge
        else:
            z_front_edge = 0  # Flat surface
        
        # For back surface (R2)
        if abs(r2) < 10000:
            r2_abs = abs(r2)
            h_edge = diameter / 2
            if h_edge < r2_abs:
                sag_back = r2_abs - math.sqrt(r2_abs**2 - h_edge**2)
                # Note: R2 sign convention is opposite for back surface
                if r2 > 0:  # Concave from back
                    z_back_edge = thickness + sag_back
                else:  # Convex from back
                    z_back_edge = thickness - sag_back
            else:
                z_back_edge = thickness  # Flat at edge
        else:
            z_back_edge = thickness  # Flat surface
        
        # Generate front surface (R1)
        if abs(r1) < 10000:
            profile1 = self.calculate_surface_profile(r1, diameter, is_front=True, resolution=resolution)
            if profile1:
                front_triangles = self.generate_surface_triangles(profile1, 0)
                self.triangles.extend(front_triangles)
        else:
            # Flat front surface
            front_triangles = self.generate_flat_surface(diameter, z_front_edge)
            self.triangles.extend(front_triangles)
        
        # Generate back surface (R2)
        if abs(r2) < 10000:
            profile2 = self.calculate_surface_profile(r2, diameter, is_front=False, resolution=resolution)
            if profile2:
                back_triangles = self.generate_surface_triangles(profile2, thickness)
                self.triangles.extend(back_triangles)
        else:
            # Flat back surface
            back_triangles = self.generate_flat_surface(diameter, z_back_edge)
            self.triangles.extend(back_triangles)
        
        # Generate edge with correct z coordinates
        edge_triangles = self.generate_edge_triangles(diameter, z_front_edge, z_back_edge)
        self.triangles.extend(edge_triangles)
        
        # Write to STL file
        self.write_binary_stl(filename)
        
        return len(self.triangles)
    
    def write_binary_stl(self, filename):
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
                
                # Calculate normal
                normal = self.calculate_normal(p1, p2, p3)
                
                # Write normal
                f.write(struct.pack('<fff', normal[0], normal[1], normal[2]))
                
                # Write vertices
                f.write(struct.pack('<fff', p1[0], p1[1], p1[2]))
                f.write(struct.pack('<fff', p2[0], p2[1], p2[2]))
                f.write(struct.pack('<fff', p3[0], p3[1], p3[2]))
                
                # Attribute byte count (unused)
                f.write(struct.pack('<H', 0))
    
    def write_ascii_stl(self, filename):
        """Write triangles to ASCII STL file (for debugging)"""
        with open(filename, 'w') as f:
            f.write('solid openlens_lens\n')
            
            for triangle in self.triangles:
                p1, p2, p3 = triangle
                normal = self.calculate_normal(p1, p2, p3)
                
                f.write(f'  facet normal {normal[0]:.6e} {normal[1]:.6e} {normal[2]:.6e}\n')
                f.write('    outer loop\n')
                f.write(f'      vertex {p1[0]:.6e} {p1[1]:.6e} {p1[2]:.6e}\n')
                f.write(f'      vertex {p2[0]:.6e} {p2[1]:.6e} {p2[2]:.6e}\n')
                f.write(f'      vertex {p3[0]:.6e} {p3[1]:.6e} {p3[2]:.6e}\n')
                f.write('    endloop\n')
                f.write('  endfacet\n')
            
            f.write('endsolid openlens_lens\n')


def export_lens_stl(lens, filename, resolution=50):
    """
    Export a lens object to STL file
    
    Args:
        lens: Lens object with r1, r2, thickness, diameter properties
        filename: Output STL filename
        resolution: Number of points along radius (higher = smoother)
    
    Returns:
        Number of triangles generated
    """
    exporter = STLExporter()
    num_triangles = exporter.export_lens_to_stl(
        lens.radius_of_curvature_1,
        lens.radius_of_curvature_2,
        lens.thickness,
        lens.diameter,
        filename,
        resolution=resolution
    )
    return num_triangles


if __name__ == "__main__":
    # Test the STL exporter
    print("Testing STL exporter...")
    
    exporter = STLExporter()
    
    # Test with a biconvex lens
    num_triangles = exporter.export_lens_to_stl(
        r1=100.0,
        r2=-100.0,
        thickness=5.0,
        diameter=50.0,
        filename="test_lens.stl",
        resolution=30
    )
    
    print(f"Generated {num_triangles} triangles")
    print("STL file created: test_lens.stl")
