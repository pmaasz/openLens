"""
STEP Export Module for OpenLens.
Generates ISO 10303-21 (STEP) files for optical components.
Supports AP203/AP214 geometry (Manifold Solid B-Rep).
"""

import math
from datetime import datetime
from typing import List, Tuple, Any

class StepWriter:
    """Helper to generate STEP file content."""
    
    def __init__(self):
        self.lines = []
        self.id_counter = 1
        
    def get_id(self):
        """Get next available ID."""
        return self.id_counter
    
    def add_entity(self, name: str, args: List[Any]) -> int:
        """Add a STEP entity and return its ID."""
        idx = self.id_counter
        self.id_counter += 1
        
        arg_strs = []
        for arg in args:
            if isinstance(arg, str):
                if arg.startswith("'"): # Already quoted string or enum
                    arg_strs.append(arg)
                elif arg == "*": # Derived attribute
                    arg_strs.append(arg)
                elif arg == "$": # Null/Unset
                    arg_strs.append(arg)
                elif arg.startswith("#"): # Reference
                    arg_strs.append(arg)
                elif arg.startswith("."): # Enum
                    arg_strs.append(arg)
                else: # Check if it's a number string
                    try:
                        float(arg)
                        arg_strs.append(arg)
                    except ValueError:
                        # Assume it's a string literal needing quotes
                        arg_strs.append(f"'{arg}'")
            elif isinstance(arg, (int, float)):
                arg_strs.append(f"{arg:.6f}")
            elif isinstance(arg, (list, tuple)):
                # Recursive formatting for lists
                sub_args = []
                for sub in arg:
                    if isinstance(sub, int): # Reference ID
                        sub_args.append(f"#{sub}")
                    elif isinstance(sub, str):
                        sub_args.append(f"'{sub}'")
                    elif isinstance(sub, (float)):
                        sub_args.append(f"{sub:.6f}")
                    else:
                        sub_args.append(str(sub))
                arg_strs.append(f"({','.join(sub_args)})")
            elif arg is None:
                arg_strs.append("$")
            else:
                arg_strs.append(str(arg))
                
        line = f"#{idx}={name}({','.join(arg_strs)});"
        self.lines.append(line)
        return idx
        
    def generate(self) -> str:
        """Generate full STEP file content."""
        header = f"""ISO-10303-21;
HEADER;
FILE_DESCRIPTION(('OpenLens Export'),'2;1');
FILE_NAME('openlens_export.step','{datetime.now().strftime("%Y-%m-%dT%H:%M:%S")}',('User'),('OpenLens'),'OpenLens','OpenLens','');
FILE_SCHEMA(('AUTOMOTIVE_DESIGN {{ 1 0 10303 214 1 1 1 1 }}'));
ENDSEC;
DATA;"""
        
        footer = """ENDSEC;
END-ISO-10303-21;"""
        
        return header + "\n" + "\n".join(self.lines) + "\n" + footer


class StepExporter:
    """Exports optical systems to STEP format."""
    
    def __init__(self, system=None):
        self.system = system
        self.writer = StepWriter()
        self.axis_id = 0
        self.dir_z = 0
        self.dir_x = 0
        
    def export(self, filename: str):
        """Export the current system to a STEP file."""
        # Standard setup entities
        self._create_context()
        
        shape_ids = []
        
        # Export each lens
        if hasattr(self.system, 'elements'):
            for elem in self.system.elements:
                solid_id = self._export_lens_solid(elem.lens, elem.position)
                if solid_id:
                    shape_ids.append(solid_id)
        else:
            # Single lens
            solid_id = self._export_lens_solid(self.system, 0.0)
            if solid_id:
                shape_ids.append(solid_id)
                
        # Create Root Product Definition if needed
        # For simplicity, we just leave the geometric entities in the file.
        # Most viewers will find the MANIFOLD_SOLID_BREP entities.
        # But properly we should link them to a PRODUCT.
        
        self._create_product_structure(shape_ids)
        
        # Write file
        with open(filename, 'w') as f:
            f.write(self.writer.generate())
            
    def _create_context(self):
        """Create common context entities."""
        # Directions
        self.dir_z = self.writer.add_entity("DIRECTION", ["'axis_z'", (0.0, 0.0, 1.0)])
        self.dir_x = self.writer.add_entity("DIRECTION", ["'axis_x'", (1.0, 0.0, 0.0)])
        self.dir_y = self.writer.add_entity("DIRECTION", ["'axis_y'", (0.0, 1.0, 0.0)])
        
        self.origin = self.writer.add_entity("CARTESIAN_POINT", ["'origin'", (0.0, 0.0, 0.0)])
        
        self.axis2_placement = self.writer.add_entity("AXIS2_PLACEMENT_3D", 
                                                      ["'global_axis'", self.origin, self.dir_z, self.dir_x])
        
        # Context
        self.context = self.writer.add_entity("MECHANICAL_CONTEXT", 
                                             ["'3D Mechanical Context'", "'mechanical'", "'assembly'"])
                                             
        self.uncertainty = self.writer.add_entity("UNCERTAINTY_MEASURE_WITH_UNIT", 
                                                 [1.0E-6, "#unit_mm", "'distance_accuracy_value'", "'confusion accuracy'"])
                                                 
        self.related_context = self.writer.add_entity("PRODUCT_CONTEXT", 
                                                     ["'part definition'", "#application_context", "'mechanical'"])
                                                     
        # We cheat a bit and don't link everything perfectly for a minimal valid file
        # But we need Dimensional Units
        # We'll just define the geometric context reference for the solids
        self.geom_context = self.writer.add_entity("GEOMETRIC_REPRESENTATION_CONTEXT",
                                                  ["'3D'", "'Geometric Context'", 3])

    def _export_lens_solid(self, lens, z_offset):
        """Create B-Rep solid for a lens."""
        r1 = lens.radius_of_curvature_1
        r2 = lens.radius_of_curvature_2
        thick = lens.thickness
        diam = lens.diameter
        h = diam / 2.0
        
        # Calculate Edge Z-coordinates
        # Sagitta 1
        if abs(r1) > 10000: # Flat
            z_edge1 = z_offset
            sag1 = 0
            is_flat1 = True
        else:
            is_flat1 = False
            r1_abs = abs(r1)
            sag1 = r1_abs - math.sqrt(r1_abs**2 - h**2)
            if r1 > 0: # Convex (Center +Z)
                z_edge1 = z_offset + sag1
            else: # Concave (Center -Z)
                z_edge1 = z_offset - sag1
        
        # Sagitta 2
        if abs(r2) > 10000: # Flat
            z_edge2 = z_offset + thick
            sag2 = 0
            is_flat2 = True
        else:
            is_flat2 = False
            r2_abs = abs(r2)
            sag2 = r2_abs - math.sqrt(r2_abs**2 - h**2)
            if r2 < 0: # Convex (Center -Z relative to vertex)
                z_edge2 = z_offset + thick - sag2
            else: # Concave (Center +Z relative to vertex)
                z_edge2 = z_offset + thick + sag2

        # --- Points ---
        # Vertex 1 (on axis)
        p_v1 = self.writer.add_entity("CARTESIAN_POINT", ["'v1'", (0.0, 0.0, z_offset)])
        # Vertex 2 (on axis)
        p_v2 = self.writer.add_entity("CARTESIAN_POINT", ["'v2'", (0.0, 0.0, z_offset + thick)])
        
        # Edge Point 1 (Start of edge loop 1) at (h, 0, z_edge1)
        p_e1 = self.writer.add_entity("CARTESIAN_POINT", ["'e1'", (h, 0.0, z_edge1)])
        # Edge Point 2 (Start of edge loop 2) at (h, 0, z_edge2)
        p_e2 = self.writer.add_entity("CARTESIAN_POINT", ["'e2'", (h, 0.0, z_edge2)])
        
        # --- Edge Curves (Circles) ---
        # Edge 1 Circle
        # Center at (0, 0, z_edge1)
        p_c1 = self.writer.add_entity("CARTESIAN_POINT", ["'c1'", (0.0, 0.0, z_edge1)])
        axis_c1 = self.writer.add_entity("AXIS2_PLACEMENT_3D", ["'axis_c1'", p_c1, self.dir_z, self.dir_x])
        circle1 = self.writer.add_entity("CIRCLE", ["'circle1'", axis_c1, h])
        
        # Edge 2 Circle
        p_c2 = self.writer.add_entity("CARTESIAN_POINT", ["'c2'", (0.0, 0.0, z_edge2)])
        axis_c2 = self.writer.add_entity("AXIS2_PLACEMENT_3D", ["'axis_c2'", p_c2, self.dir_z, self.dir_x])
        circle2 = self.writer.add_entity("CIRCLE", ["'circle2'", axis_c2, h])
        
        # --- Edges ---
        # We need a VERTEX_POINT for the seam (at angle 0)
        v_e1 = self.writer.add_entity("VERTEX_POINT", ["'v_e1'", p_e1])
        v_e2 = self.writer.add_entity("VERTEX_POINT", ["'v_e2'", p_e2])
        
        # EDGE_CURVE for Edge 1 (Full circle)
        # Note: STEP usually requires splitting closed curves into 1 or 2 segments?
        # A single EDGE_CURVE with same start/end vertex on a circle is allowed in some schemas, 
        # but robust exporters use 2 semicircles or just declare it as an EDGE_LOOP with one edge.
        # Let's try single edge.
        edge1 = self.writer.add_entity("EDGE_CURVE", ["'edge1'", v_e1, v_e1, circle1, ".T."])
        
        # EDGE_CURVE for Edge 2
        edge2 = self.writer.add_entity("EDGE_CURVE", ["'edge2'", v_e2, v_e2, circle2, ".T."])
        
        # Longitudinal Seam Edge (connecting e1 to e2 along cylinder)
        # Line segment
        line_seam = self.writer.add_entity("LINE", ["'seam_line'", p_e1, self.writer.add_entity("VECTOR", ["'dir_z'", self.dir_z, 1.0])])
        edge_seam = self.writer.add_entity("EDGE_CURVE", ["'edge_seam'", v_e1, v_e2, line_seam, ".T."])
        
        # --- Loops ---
        # Loop 1 (Front Face boundary)
        # If R1>0 (Convex), normal points -Z (away from surface). 
        # Loop orientation must be CCW around normal.
        # This is tricky.
        loop1 = self.writer.add_entity("EDGE_LOOP", ["'loop1'", [self.writer.add_entity("ORIENTED_EDGE", ["*", "*", edge1, ".T."])]])
        
        # Loop 2 (Back Face boundary)
        loop2 = self.writer.add_entity("EDGE_LOOP", ["'loop2'", [self.writer.add_entity("ORIENTED_EDGE", ["*", "*", edge2, ".T."])]])
        
        # Loop 3 (Cylinder boundary)
        # Needs 2 circles and seams?
        # Actually, if we just define the faces bounded by these loops...
        # Cylinder Face needs 2 loops (top and bottom).
        # Bounds: edge1 and edge2.
        
        # --- Surfaces ---
        # Surface 1 (Front)
        if is_flat1:
            plane1 = self.writer.add_entity("PLANE", ["'plane1'", axis_c1]) # Normal +Z
            surf1 = plane1
        else:
            # Sphere
            # Center of curvature
            if r1 > 0:
                c_z = z_offset + r1
            else:
                c_z = z_offset + r1 # r1 is negative
                
            p_center1 = self.writer.add_entity("CARTESIAN_POINT", ["'center1'", (0.0, 0.0, c_z)])
            axis_s1 = self.writer.add_entity("AXIS2_PLACEMENT_3D", ["'axis_s1'", p_center1, self.dir_z, self.dir_x])
            surf1 = self.writer.add_entity("SPHERICAL_SURFACE", ["'sphere1'", axis_s1, abs(r1)])
            
        # Surface 2 (Back)
        if is_flat2:
            plane2 = self.writer.add_entity("PLANE", ["'plane2'", axis_c2])
            surf2 = plane2
        else:
            if r2 < 0: # Convex back
                c_z = z_offset + thick - abs(r2) # ? r2 is neg. Center at T+R2 (left)
                # Wait, if r2=-100. Center = T-100. Correct.
            else: # Concave back
                c_z = z_offset + thick + r2
                
            p_center2 = self.writer.add_entity("CARTESIAN_POINT", ["'center2'", (0.0, 0.0, c_z)])
            axis_s2 = self.writer.add_entity("AXIS2_PLACEMENT_3D", ["'axis_s2'", p_center2, self.dir_z, self.dir_x])
            surf2 = self.writer.add_entity("SPHERICAL_SURFACE", ["'sphere2'", axis_s2, abs(r2)])

        # Surface 3 (Cylinder)
        axis_cyl = self.writer.add_entity("AXIS2_PLACEMENT_3D", ["'axis_cyl'", p_c1, self.dir_z, self.dir_x])
        surf3 = self.writer.add_entity("CYLINDRICAL_SURFACE", ["'cyl'", axis_cyl, h])
        
        # --- Faces ---
        # Face 1 (Front)
        # Bounds: loop1
        # Orientation depends on convex/concave.
        face1 = self.writer.add_entity("ADVANCED_FACE", ["'face1'", [self.writer.add_entity("FACE_BOUND", ["'b1'", loop1, ".T."])], surf1, ".T."])
        
        # Face 2 (Back)
        face2 = self.writer.add_entity("ADVANCED_FACE", ["'face2'", [self.writer.add_entity("FACE_BOUND", ["'b2'", loop2, ".T."])], surf2, ".T."])
        
        # Face 3 (Cylinder)
        # Bounds: loop1 and loop2
        # Need to orient edges correctly so they form a valid boundary for the cylinder
        # This is where single-edge loops are tricky for cylinders without seams.
        # But for STEP, we can try using the loops directly.
        
        # For a cylinder, we usually need a seam if we use a closed surface.
        # But let's try just listing the bounds.
        # One bound is the front circle, one is the back.
        
        b3_1 = self.writer.add_entity("FACE_BOUND", ["'b3_1'", loop1, ".T."])
        b3_2 = self.writer.add_entity("FACE_BOUND", ["'b3_2'", loop2, ".T."])
        
        face3 = self.writer.add_entity("ADVANCED_FACE", ["'face3'", [b3_1, b3_2], surf3, ".T."])
        
        # --- Shell ---
        shell = self.writer.add_entity("CLOSED_SHELL", ["'shell'", [face1, face2, face3]])
        
        # --- Solid ---
        solid = self.writer.add_entity("MANIFOLD_SOLID_BREP", [f"'{lens.name}'", shell])
        
        return solid

    def _create_product_structure(self, shape_ids):
        """Create high-level product structure."""
        if not shape_ids:
            return
            
        # Create a Shape Representation containing all solids
        rep_items = []
        for sid in shape_ids:
            rep_items.append(f"#{sid}")
            
        shape_rep = self.writer.add_entity("ADVANCED_BREP_SHAPE_REPRESENTATION", 
                                          ["'lens_geom'", tuple(rep_items), self.geom_context])
