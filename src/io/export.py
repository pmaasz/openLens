"""
ISO 10110 Drawing Export Module.
Generates SVG drawings of optical components and systems.
"""

import math
from typing import List, Dict, Tuple, Optional
from datetime import datetime

try:
    from ..optical_system import OpticalSystem
    from ..lens import Lens
except (ImportError, ValueError):
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from src.optical_system import OpticalSystem
    from src.lens import Lens

class ISO10110Generator:
    """Generates ISO 10110 compliant SVG drawings."""
    
    def __init__(self, system: OpticalSystem):
        self.system = system
        
    def generate_svg(self, filename: str, width: int = 800, height: int = 600):
        """Generate SVG file."""
        svg_content = self._render_svg(width, height)
        with open(filename, 'w') as f:
            f.write(svg_content)
            
    def _render_svg(self, width: int, height: int) -> str:
        """Render SVG content."""
        scale = self._calculate_scale(width, height)
        center_x = width / 2
        center_y = height / 2
        
        # Header
        lines = [
            f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">',
            f'<defs>',
            f'<style>',
            f'  .lens {{ fill: #E0E0E0; stroke: black; stroke-width: 2; opacity: 0.8; }}',
            f'  .axis {{ stroke: black; stroke-width: 1; stroke-dasharray: 5,5; }}',
            f'  .text {{ font-family: Arial; font-size: 12px; }}',
            f'  .title {{ font-family: Arial; font-size: 16px; font-weight: bold; }}',
            f'  .table {{ fill: none; stroke: black; stroke-width: 1; }}',
            f'</style>',
            f'</defs>',
            f'<rect width="100%" height="100%" fill="white"/>',
            f'<text x="20" y="30" class="title">ISO 10110 Drawing: {self.system.name}</text>',
            f'<text x="20" y="50" class="text">Date: {datetime.now().strftime("%Y-%m-%d")}</text>'
        ]
        
        # Optical Axis
        lines.append(f'<line x1="20" y1="{center_y}" x2="{width-20}" y2="{center_y}" class="axis"/>')
        
        # Draw Lenses
        # Get flattened elements
        elements = self.system.elements
        
        # We need cumulative positions. OpticalSystem.elements.position is absolute Z?
        # Yes, standard `OpticalSystem.elements` has absolute `position`.
        
        # Center the system in X
        if elements:
            total_length = elements[-1].position + elements[-1].thickness
            start_x = center_x - (total_length * scale) / 2
        else:
            start_x = center_x
            
        for i, elem in enumerate(elements):
            lens = elem.lens
            pos_x = start_x + elem.position * scale
            
            # Draw lens profile
            path = self._generate_lens_path(lens, pos_x, center_y, scale)
            lines.append(f'<path d="{path}" class="lens"/>')
            
            # Label
            lines.append(f'<text x="{pos_x}" y="{center_y + lens.diameter/2*scale + 20}" class="text" text-anchor="middle">L{i+1}</text>')
            
        # Draw ISO Table Block
        table_x = width - 300
        table_y = height - 150 # Start near bottom right
        # We don't need to pass height as it's calculated dynamically
        lines.append(self._generate_iso_table(table_x, table_y, 280, 0))

        lines.append('</svg>')
        return "\n".join(lines)
        
    def _calculate_scale(self, width: int, height: int) -> float:
        """Calculate drawing scale to fit system."""
        if not self.system.elements:
            return 10.0
            
        # Bounds
        min_x = 0
        max_x = self.system.elements[-1].position + self.system.elements[-1].thickness
        max_diam = max(e.lens.diameter for e in self.system.elements)
        
        margin = 50
        avail_w = width - 2*margin
        avail_h = height - 2*margin
        
        scale_x = avail_w / (max_x if max_x > 0 else 10)
        scale_y = avail_h / (max_diam if max_diam > 0 else 10)
        
        return min(scale_x, scale_y) * 0.8 # 80% fit

    def _generate_lens_path(self, lens: Lens, x: float, y: float, scale: float) -> str:
        """Generate SVG path for a lens cross-section."""
        r1 = lens.radius_of_curvature_1
        r2 = lens.radius_of_curvature_2
        thick = lens.thickness * scale
        h = (lens.diameter / 2) * scale
        
        # Vertex 1 is at (x, y)
        # Vertex 2 is at (x + thick, y)
        
        path = []
        
        if abs(r1) > 10000:
            # Flat
            x1_edge = x
            path.append(f"M {x1_edge} {y - h}")
            path.append(f"L {x1_edge} {y + h}")
        else:
            r1_s = abs(r1) * scale
            s1 = r1_s - math.sqrt(r1_s**2 - h**2)
            
            if r1 > 0: # Convex (Center Right)
                # Vertex at X. Edges at X + s1.
                x1_edge = x + s1
                # Move to Top Edge
                path.append(f"M {x1_edge} {y - h}")
                # Arc to Bottom Edge
                # A rx ry x-axis-rotation large-arc-flag sweep-flag x y
                # Sweep flag: 1 for "positive angle".
                # Standard SVG coordinate system (Y down).
                path.append(f"A {r1_s} {r1_s} 0 0 0 {x1_edge} {y + h}")
            else: # Concave (Center Left)
                # Vertex at X. Edges at X - s1?
                # No, if Vertex at X, and Center Left, Arc bulges Right (into glass).
                # That is Concave.
                # Edges at X - s1.
                x1_edge = x - s1
                path.append(f"M {x1_edge} {y - h}")
                path.append(f"A {r1_s} {r1_s} 0 0 1 {x1_edge} {y + h}")
                
        # Back Arc
        # Vertex 2 at X + Thick
        x2 = x + thick
        
        if abs(r2) > 10000:
            # Flat
            x2_edge = x2
            path.append(f"L {x2_edge} {y + h}") # Connect from front bottom to back bottom?
            # We are at Front Bottom.
            # Draw line to Back Bottom.
            path.append(f"L {x2_edge} {y + h}")
            path.append(f"L {x2_edge} {y - h}")
        else:
            r2_s = abs(r2) * scale
            s2 = r2_s - math.sqrt(r2_s**2 - h**2)
            
            # If R2 < 0 (Convex Back). Center Left.
            # Bulges Right (into air).
            # Vertex at X2. Edge at X2 - s2.
            
            if r2 < 0: # Convex Back
                x2_edge = x2 - s2
                path.append(f"L {x2_edge} {y + h}")
                path.append(f"A {r2_s} {r2_s} 0 0 0 {x2_edge} {y - h}")
            else: # Concave Back (Center Right)
                # Bulges Left (into glass).
                # Vertex at X2. Edge at X2 + s2.
                x2_edge = x2 + s2
                path.append(f"L {x2_edge} {y + h}")
                path.append(f"A {r2_s} {r2_s} 0 0 1 {x2_edge} {y - h}")
                
        # Close path (Back Top to Front Top)
        path.append("Z")
        
        return " ".join(path)

    def _generate_iso_table(self, x: float, y: float, w: float, h: float) -> str:
        """Generate SVG table for system data."""
        lines = []
        
        # Calculate dynamic height based on elements
        num_surfaces = len(self.system.elements) * 2 if self.system.elements else 0
        header_h = 25
        row_h = 20
        total_h = header_h + num_surfaces * row_h + 10
        
        # Adjust y to align bottom if needed, but here we just draw down from y
        
        # Background
        lines.append(f'<rect x="{x}" y="{y}" width="{w}" height="{total_h}" fill="white" stroke="black" stroke-width="1"/>')
        
        # Headers
        headers = ["Surf", "Radius", "Thick", "Mat", "Diam"]
        col_x = [x + 10, x + 50, x + 110, x + 160, x + 210]
        
        # Draw Header Row
        lines.append(f'<line x1="{x}" y1="{y+header_h}" x2="{x+w}" y2="{y+header_h}" stroke="black" stroke-width="1"/>')
        for i, header in enumerate(headers):
            lines.append(f'<text x="{col_x[i]}" y="{y+18}" class="text" font-weight="bold">{header}</text>')
            
        # Draw Rows
        curr_y = y + header_h + 15
        surf_idx = 1
        
        for elem in self.system.elements:
            lens = elem.lens
            
            # Surface 1 (Front)
            lines.append(f'<text x="{col_x[0]}" y="{curr_y}" class="text">{surf_idx}</text>')
            lines.append(f'<text x="{col_x[1]}" y="{curr_y}" class="text">{lens.radius_of_curvature_1:.2f}</text>')
            lines.append(f'<text x="{col_x[2]}" y="{curr_y}" class="text">{lens.thickness:.2f}</text>')
            lines.append(f'<text x="{col_x[3]}" y="{curr_y}" class="text">{lens.material}</text>')
            lines.append(f'<text x="{col_x[4]}" y="{curr_y}" class="text">{lens.diameter:.2f}</text>')
            curr_y += row_h
            surf_idx += 1
            
            # Surface 2 (Back)
            lines.append(f'<text x="{col_x[0]}" y="{curr_y}" class="text">{surf_idx}</text>')
            lines.append(f'<text x="{col_x[1]}" y="{curr_y}" class="text">{lens.radius_of_curvature_2:.2f}</text>')
            # Thickness is usually to next surface. For single lens, it's air?
            # Let's put "-" for back surface thickness unless we have air gap info
            lines.append(f'<text x="{col_x[2]}" y="{curr_y}" class="text">-</text>') 
            lines.append(f'<text x="{col_x[3]}" y="{curr_y}" class="text"></text>')
            lines.append(f'<text x="{col_x[4]}" y="{curr_y}" class="text">{lens.diameter:.2f}</text>')
            curr_y += row_h
            surf_idx += 1
            
        return "\n".join(lines)
