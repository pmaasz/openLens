#!/usr/bin/env python3
"""
Export to professional optical design formats
Zemax, OpticStudio, SVG technical drawings
"""

import math
from typing import Optional, List, Tuple

try:
    from .lens_editor import Lens
    from .optical_system import OpticalSystem
except (ImportError, ValueError):
    import sys
    import os
    sys.path.insert(0, os.path.dirname(__file__))
    from lens_editor import Lens
    from optical_system import OpticalSystem


class ZemaxExporter:
    """Export to Zemax format (.zmx)"""
    
    @staticmethod
    def export_lens(lens: Lens, filename: str):
        """Export single lens to Zemax format"""
        with open(filename, 'w') as f:
            f.write("! OpenLens Export\n")
            f.write(f"! {lens.name}\n")
            f.write("VERS 140000\n")
            f.write("MODE SEQ\n")
            f.write("\n")
            
            # Surface 0 (object)
            f.write("SURF 0\n")
            f.write("  TYPE STANDARD\n")
            f.write("  CURV 0.0\n")
            f.write("  DISZ INFINITY\n")
            f.write("\n")
            
            # Surface 1 (front)
            f.write("SURF 1\n")
            f.write("  TYPE STANDARD\n")
            f.write(f"  CURV {1/lens.radius_of_curvature_1 if lens.radius_of_curvature_1 != 0 else 0}\n")
            f.write(f"  DISZ {lens.thickness}\n")
            f.write(f"  DIAM {lens.diameter}\n")
            f.write(f"  GLAS {lens.material}\n")
            f.write("\n")
            
            # Surface 2 (back)
            f.write("SURF 2\n")
            f.write("  TYPE STANDARD\n")
            f.write(f"  CURV {1/lens.radius_of_curvature_2 if lens.radius_of_curvature_2 != 0 else 0}\n")
            f.write("  DISZ 100.0\n")
            f.write("\n")
            
            # Image surface
            f.write("SURF 3\n")
            f.write("  TYPE STANDARD\n")
            f.write("\n")


class OpticStudioExporter:
    """Export to Zemax OpticStudio text format"""
    
    @staticmethod
    def export_lens(lens: Lens, filename: str):
        """
        Export single lens to OpticStudio text prescription format.
        This is a human-readable format that can be imported into OpticStudio.
        """
        with open(filename, 'w') as f:
            # Header
            f.write("# OpenLens Export - OpticStudio Format\n")
            f.write(f"# Lens: {lens.name}\n")
            f.write("#" + "="*60 + "\n\n")
            
            # System info
            f.write("SYSTEM PRESCRIPTION DATA\n")
            f.write("-" * 40 + "\n")
            f.write(f"Title: {lens.name}\n")
            f.write("Units: Millimeters\n")
            f.write("Type: Sequential\n")
            f.write("\n")
            
            # Lens data
            f.write("LENS DATA SUMMARY\n")
            f.write("-" * 40 + "\n")
            f.write(f"Material: {lens.material}\n")
            f.write(f"Refractive Index (d-line): {lens.refractive_index:.6f}\n")
            f.write(f"Clear Aperture: {lens.diameter:.4f} mm\n")
            
            focal_length = lens.calculate_focal_length()
            if focal_length:
                f.write(f"Effective Focal Length: {focal_length:.4f} mm\n")
            f.write("\n")
            
            # Surface data table
            f.write("SURFACE DATA DETAIL\n")
            f.write("-" * 40 + "\n")
            f.write(f"{'Surface':<10} {'Type':<12} {'Radius':<14} {'Thickness':<12} {'Glass':<10} {'Diameter':<10}\n")
            f.write("-" * 70 + "\n")
            
            # Object surface
            f.write(f"{'OBJ':<10} {'STANDARD':<12} {'Infinity':<14} {'Infinity':<12} {'':<10} {'':<10}\n")
            
            # Stop surface (entrance pupil at front surface)
            f.write(f"{'STO':<10} {'STANDARD':<12} {'Infinity':<14} {'0.0000':<12} {'':<10} {lens.diameter:<10.4f}\n")
            
            # Front surface
            r1_str = f"{lens.radius_of_curvature_1:.4f}" if abs(lens.radius_of_curvature_1) < 1e10 else "Infinity"
            f.write(f"{'1':<10} {'STANDARD':<12} {r1_str:<14} {lens.thickness:<12.4f} {lens.material:<10} {lens.diameter:<10.4f}\n")
            
            # Back surface
            r2_str = f"{lens.radius_of_curvature_2:.4f}" if abs(lens.radius_of_curvature_2) < 1e10 else "Infinity"
            f.write(f"{'2':<10} {'STANDARD':<12} {r2_str:<14} {'100.0000':<12} {'':<10} {lens.diameter:<10.4f}\n")
            
            # Image surface
            f.write(f"{'IMA':<10} {'STANDARD':<12} {'Infinity':<14} {'':<12} {'':<10} {'':<10}\n")
            
            f.write("\n")
            f.write("# End of OpenLens Export\n")
    
    @staticmethod
    def export_system(system: OpticalSystem, filename: str):
        """Export optical system to OpticStudio format"""
        with open(filename, 'w') as f:
            # Header
            f.write("# OpenLens Export - OpticStudio Format\n")
            f.write(f"# System: {system.name}\n")
            f.write("#" + "="*60 + "\n\n")
            
            f.write("SYSTEM PRESCRIPTION DATA\n")
            f.write("-" * 40 + "\n")
            f.write(f"Title: {system.name}\n")
            f.write("Units: Millimeters\n")
            f.write("Type: Sequential\n")
            f.write(f"Number of Elements: {len(system.elements)}\n")
            
            total_length = system.get_total_length()
            if total_length:
                f.write(f"Total Length: {total_length:.4f} mm\n")
            
            system_fl = system.get_system_focal_length()
            if system_fl:
                f.write(f"System Focal Length: {system_fl:.4f} mm\n")
            f.write("\n")
            
            # Surface data
            f.write("SURFACE DATA DETAIL\n")
            f.write("-" * 40 + "\n")
            f.write(f"{'Surface':<10} {'Type':<12} {'Radius':<14} {'Thickness':<12} {'Glass':<10}\n")
            f.write("-" * 60 + "\n")
            
            # Object
            f.write(f"{'OBJ':<10} {'STANDARD':<12} {'Infinity':<14} {'Infinity':<12} {'':<10}\n")
            
            surf_num = 1
            for i, elem in enumerate(system.elements):
                lens = elem.lens
                
                # Air gap before lens
                if elem.air_gap_before > 0:
                    f.write(f"{surf_num:<10} {'STANDARD':<12} {'Infinity':<14} {elem.air_gap_before:<12.4f} {'':<10}\n")
                    surf_num += 1
                
                # Front surface
                r1_str = f"{lens.radius_of_curvature_1:.4f}" if abs(lens.radius_of_curvature_1) < 1e10 else "Infinity"
                f.write(f"{surf_num:<10} {'STANDARD':<12} {r1_str:<14} {lens.thickness:<12.4f} {lens.material:<10}\n")
                surf_num += 1
                
                # Back surface
                r2_str = f"{lens.radius_of_curvature_2:.4f}" if abs(lens.radius_of_curvature_2) < 1e10 else "Infinity"
                f.write(f"{surf_num:<10} {'STANDARD':<12} {r2_str:<14} {'100.0000':<12} {'':<10}\n")
                surf_num += 1
            
            # Image
            f.write(f"{'IMA':<10} {'STANDARD':<12} {'Infinity':<14} {'':<12} {'':<10}\n")
            
            f.write("\n")
            f.write("# End of OpenLens Export\n")


class SVGExporter:
    """Export lens diagrams as SVG (Scalable Vector Graphics)"""
    
    @staticmethod
    def _generate_arc_path(cx: float, cy: float, radius: float, 
                           y_start: float, y_end: float, 
                           is_left_surface: bool) -> str:
        """
        Generate SVG path for a lens surface arc.
        
        Args:
            cx: Center x of the arc circle
            cy: Center y of the arc circle  
            radius: Radius of curvature (absolute value)
            y_start: Starting y coordinate (top)
            y_end: Ending y coordinate (bottom)
            is_left_surface: True for left/front surface, False for right/back
        
        Returns:
            SVG path d attribute string
        """
        # Calculate arc endpoints
        half_height = abs(y_end - y_start) / 2
        
        if radius < half_height:
            # Radius too small, use straight line
            return ""
        
        # Calculate x offset from center for the arc endpoints
        try:
            x_offset = math.sqrt(radius * radius - half_height * half_height)
        except ValueError:
            return ""
        
        if is_left_surface:
            # Left surface: arc curves to the left (center is to the right of surface)
            x_top = cx - x_offset
            x_bottom = cx - x_offset
        else:
            # Right surface: arc curves to the right (center is to the left of surface)
            x_top = cx + x_offset
            x_bottom = cx + x_offset
        
        y_top = cy - half_height
        y_bottom = cy + half_height
        
        # SVG arc parameters
        large_arc = 0  # Always use small arc for lens surfaces
        sweep = 1 if is_left_surface else 0
        
        return f"M {x_top:.2f} {y_top:.2f} A {radius:.2f} {radius:.2f} 0 {large_arc} {sweep} {x_bottom:.2f} {y_bottom:.2f}"
    
    @staticmethod
    def _get_surface_x(radius: float, half_diameter: float, base_x: float, is_front: bool) -> float:
        """Calculate x position of surface edge given radius and y position"""
        if abs(radius) > 1e9:  # Flat surface
            return base_x
        
        try:
            sag = abs(radius) - math.sqrt(radius * radius - half_diameter * half_diameter)
        except ValueError:
            sag = 0
        
        if is_front:
            if radius > 0:  # Convex front
                return base_x - sag
            else:  # Concave front
                return base_x + sag
        else:
            if radius > 0:  # Concave back (radius measured from back)
                return base_x + sag
            else:  # Convex back
                return base_x - sag
    
    @staticmethod
    def export_lens(lens: Lens, filename: str, width: int = 400, height: int = 300,
                   show_rays: bool = False, show_labels: bool = True):
        """
        Export lens cross-section as SVG.
        
        Args:
            lens: Lens object to export
            filename: Output SVG filename
            width: SVG width in pixels
            height: SVG height in pixels
            show_rays: Whether to show ray paths (simplified)
            show_labels: Whether to show dimension labels
        """
        # Calculate scaling
        margin = 40
        available_width = width - 2 * margin
        available_height = height - 2 * margin
        
        # Scale to fit lens
        max_dimension = max(lens.thickness * 2, lens.diameter)
        scale = min(available_width, available_height) / max_dimension * 0.8
        
        # Center position
        cx = width / 2
        cy = height / 2
        
        # Scaled lens dimensions
        thickness = lens.thickness * scale
        half_diameter = (lens.diameter / 2) * scale
        
        # Calculate surface positions
        front_x = cx - thickness / 2
        back_x = cx + thickness / 2
        
        with open(filename, 'w') as f:
            # SVG header
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
            f.write(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">\n')
            f.write('  <defs>\n')
            f.write('    <style>\n')
            f.write('      .lens-fill { fill: #b3d9ff; fill-opacity: 0.5; }\n')
            f.write('      .lens-stroke { stroke: #0066cc; stroke-width: 2; fill: none; }\n')
            f.write('      .axis { stroke: #999999; stroke-width: 1; stroke-dasharray: 5,5; }\n')
            f.write('      .ray { stroke: #ff6600; stroke-width: 1.5; fill: none; }\n')
            f.write('      .label { font-family: Arial, sans-serif; font-size: 12px; fill: #333333; }\n')
            f.write('      .title { font-family: Arial, sans-serif; font-size: 14px; font-weight: bold; fill: #333333; }\n')
            f.write('    </style>\n')
            f.write('  </defs>\n')
            f.write('\n')
            
            # Background
            f.write(f'  <rect width="{width}" height="{height}" fill="white"/>\n')
            f.write('\n')
            
            # Title
            f.write(f'  <text x="{width/2}" y="25" class="title" text-anchor="middle">{lens.name}</text>\n')
            f.write('\n')
            
            # Optical axis
            f.write(f'  <line x1="{margin}" y1="{cy}" x2="{width-margin}" y2="{cy}" class="axis"/>\n')
            f.write('\n')
            
            # Generate lens outline path
            r1 = lens.radius_of_curvature_1
            r2 = lens.radius_of_curvature_2
            
            # Calculate sag (surface deviation from flat)
            def calc_sag(radius, half_d):
                if abs(radius) > 1e9:
                    return 0
                try:
                    return abs(radius) - math.sqrt(radius * radius - half_d * half_d)
                except ValueError:
                    return 0
            
            sag1 = calc_sag(r1, lens.diameter / 2) * scale
            sag2 = calc_sag(r2, lens.diameter / 2) * scale
            
            # Front surface edge x positions
            if abs(r1) > 1e9:  # Flat
                front_top_x = front_x
                front_bot_x = front_x
            elif r1 > 0:  # Convex front
                front_top_x = front_x + sag1
                front_bot_x = front_x + sag1
            else:  # Concave front
                front_top_x = front_x - sag1
                front_bot_x = front_x - sag1
            
            # Back surface edge x positions
            if abs(r2) > 1e9:  # Flat
                back_top_x = back_x
                back_bot_x = back_x
            elif r2 < 0:  # Convex back (negative radius)
                back_top_x = back_x - sag2
                back_bot_x = back_x - sag2
            else:  # Concave back
                back_top_x = back_x + sag2
                back_bot_x = back_x + sag2
            
            # Build path for lens outline
            top_y = cy - half_diameter
            bot_y = cy + half_diameter
            
            # Start path
            path_parts = []
            
            # Front surface (top to bottom)
            if abs(r1) > 1e9:  # Flat surface
                path_parts.append(f"M {front_top_x:.2f} {top_y:.2f}")
                path_parts.append(f"L {front_bot_x:.2f} {bot_y:.2f}")
            else:
                # Curved surface using quadratic bezier approximation
                r1_scaled = abs(r1) * scale
                # Control point for quadratic bezier
                if r1 > 0:  # Convex
                    ctrl_x = front_x
                else:  # Concave
                    ctrl_x = front_top_x + sag1 * 2
                
                path_parts.append(f"M {front_top_x:.2f} {top_y:.2f}")
                path_parts.append(f"Q {ctrl_x:.2f} {cy:.2f} {front_bot_x:.2f} {bot_y:.2f}")
            
            # Bottom edge
            path_parts.append(f"L {back_bot_x:.2f} {bot_y:.2f}")
            
            # Back surface (bottom to top)
            if abs(r2) > 1e9:  # Flat surface
                path_parts.append(f"L {back_top_x:.2f} {top_y:.2f}")
            else:
                r2_scaled = abs(r2) * scale
                if r2 < 0:  # Convex back
                    ctrl_x = back_x
                else:  # Concave back
                    ctrl_x = back_bot_x - sag2 * 2
                
                path_parts.append(f"Q {ctrl_x:.2f} {cy:.2f} {back_top_x:.2f} {top_y:.2f}")
            
            # Close path
            path_parts.append("Z")
            
            path_d = " ".join(path_parts)
            
            # Draw lens
            f.write(f'  <path d="{path_d}" class="lens-fill"/>\n')
            f.write(f'  <path d="{path_d}" class="lens-stroke"/>\n')
            f.write('\n')
            
            # Optional rays
            if show_rays:
                ray_y_positions = [-half_diameter * 0.7, 0, half_diameter * 0.7]
                for ray_y in ray_y_positions:
                    # Simplified parallel rays
                    f.write(f'  <line x1="{margin}" y1="{cy + ray_y}" x2="{front_top_x}" y2="{cy + ray_y}" class="ray"/>\n')
                f.write('\n')
            
            # Labels
            if show_labels:
                # Diameter label
                f.write(f'  <text x="{margin + 10}" y="{cy - half_diameter - 5}" class="label">∅{lens.diameter:.1f}mm</text>\n')
                
                # Thickness label
                f.write(f'  <text x="{cx}" y="{cy + half_diameter + 20}" class="label" text-anchor="middle">t={lens.thickness:.1f}mm</text>\n')
                
                # Material label
                f.write(f'  <text x="{cx}" y="{height - 15}" class="label" text-anchor="middle">{lens.material} (n={lens.refractive_index:.4f})</text>\n')
                
                # Focal length
                fl = lens.calculate_focal_length()
                if fl:
                    f.write(f'  <text x="{width - margin - 10}" y="{cy - 10}" class="label" text-anchor="end">f={fl:.1f}mm</text>\n')
            
            f.write('\n')
            f.write('</svg>\n')
    
    @staticmethod
    def export_system(system: OpticalSystem, filename: str, width: int = 600, height: int = 300):
        """Export optical system as SVG diagram"""
        margin = 40
        
        with open(filename, 'w') as f:
            # SVG header
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
            f.write(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">\n')
            f.write('  <defs>\n')
            f.write('    <style>\n')
            f.write('      .lens-fill { fill: #b3d9ff; fill-opacity: 0.5; }\n')
            f.write('      .lens-stroke { stroke: #0066cc; stroke-width: 2; fill: none; }\n')
            f.write('      .axis { stroke: #999999; stroke-width: 1; stroke-dasharray: 5,5; }\n')
            f.write('      .title { font-family: Arial, sans-serif; font-size: 14px; font-weight: bold; }\n')
            f.write('    </style>\n')
            f.write('  </defs>\n')
            
            # Background
            f.write(f'  <rect width="{width}" height="{height}" fill="white"/>\n')
            
            # Title
            f.write(f'  <text x="{width/2}" y="25" class="title" text-anchor="middle">{system.name}</text>\n')
            
            # Optical axis
            cy = height / 2
            f.write(f'  <line x1="{margin}" y1="{cy}" x2="{width-margin}" y2="{cy}" class="axis"/>\n')
            
            # Calculate total system length for scaling
            total_length = system.get_total_length() or 100
            
            # Get max diameter for vertical scaling
            max_diameter = max((elem.lens.diameter for elem in system.elements), default=50)
            
            available_width = width - 2 * margin
            available_height = height - 2 * margin
            
            scale_x = available_width / total_length * 0.8
            scale_y = available_height / max_diameter * 0.8
            scale = min(scale_x, scale_y)
            
            # Draw each lens element
            x_pos = margin + 20
            for i, elem in enumerate(system.elements):
                lens = elem.lens
                
                # Add air gap
                x_pos += elem.air_gap_before * scale
                
                # Lens dimensions
                t = lens.thickness * scale
                h = lens.diameter / 2 * scale
                
                # Simple rectangle for each lens (simplified)
                f.write(f'  <rect x="{x_pos}" y="{cy - h}" width="{t}" height="{h * 2}" class="lens-fill"/>\n')
                f.write(f'  <rect x="{x_pos}" y="{cy - h}" width="{t}" height="{h * 2}" class="lens-stroke"/>\n')
                
                x_pos += t
            
            f.write('</svg>\n')


class PrescriptionExporter:
    """Export lens prescription format"""
    
    @staticmethod
    def export_prescription(lens: Lens, filename: str):
        """Export lens prescription (industry standard format)"""
        with open(filename, 'w') as f:
            f.write("LENS PRESCRIPTION\n")
            f.write("="*60 + "\n\n")
            f.write(f"Lens Name: {lens.name}\n")
            f.write(f"Lens Type: {lens.lens_type}\n\n")
            
            f.write("OPTICAL PARAMETERS:\n")
            f.write(f"  Radius of Curvature 1: {lens.radius_of_curvature_1:.3f} mm\n")
            f.write(f"  Radius of Curvature 2: {lens.radius_of_curvature_2:.3f} mm\n")
            f.write(f"  Center Thickness: {lens.thickness:.3f} mm\n")
            f.write(f"  Clear Aperture: {lens.diameter:.3f} mm\n")
            f.write(f"  Material: {lens.material}\n")
            f.write(f"  Refractive Index: {lens.refractive_index:.4f}\n")
            
            f_length = lens.calculate_focal_length()
            if f_length:
                f.write(f"  Focal Length: {f_length:.3f} mm\n")
            
            f.write("\n")
            f.write("Generated by OpenLens\n")

