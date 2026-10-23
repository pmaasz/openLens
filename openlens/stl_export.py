#!/usr/bin/env python3
"""
openlens - STL Export Module
Exports lens geometry as STL files for 3D printing
"""

import struct
import math
from typing import List, Tuple, Optional, Any

from .vector3 import Vector3
from .atomic import atomic_write_bytes


class STLExporter:
    """Export lens geometry to STL format"""

    def __init__(self):
        self.triangles: List[
            Tuple[
                Tuple[float, float, float],
                Tuple[float, float, float],
                Tuple[float, float, float],
            ]
        ] = []

    def calculate_surface_profile(
        self,
        radius: float,
        diameter: float,
        is_front: bool = True,
        resolution: int = 50,
    ) -> Optional[List[Tuple[float, float]]]:
        """Calculate points on a spherical surface.

        Args:
            radius: Signed radius of curvature (mm). The sign alone sets the
                shape: positive gives a surface curving away from the axis.
            diameter: Full clear/mechanical diameter (mm).
            is_front: Accepted for API compatibility and **ignored**. The
                surface shape is fully determined by the sign of ``radius``,
                and the back surface is positioned by the caller's
                ``z_offset`` (= thickness). Front and back profiles are
                therefore the same function of their own radius.
            resolution: Number of radial steps from the axis to the rim.

        Returns:
            Half-profile as (radius_from_axis, z) pairs, or None if the
            surface is flat.
        """
        # STL exporter wants half-profile (0 to h).
        #
        # The sag formula already carries the sign: copysign makes the
        # denominator negative for a negative radius, so z_sag is +sag for
        # R > 0 and -sag for R < 0. This used to be followed by
        #
        #     if is_front:
        #         if radius < 0: z = -z_sag
        #     else:
        #         if radius < 0: z = -z_sag
        #
        # whose two branches were byte-identical, so is_front did nothing and
        # the negation simply inverted every negative radius. For
        # r1=+50, r2=-50, t=5, D=25 the back rim came out at 6.588 instead of
        # 3.412, and because both surfaces came out identical the biconvex
        # solid was a straight cylinder of constant 5 mm.
        h = diameter / 2.0
        if abs(radius) < 1e-10 or abs(radius) > 1e10:
            # Flat: the exporters have a dedicated flat-fan generator.
            return None

        half_profile = []
        for i in range(resolution + 1):
            y = (i / resolution) * h  # 0 to h
            # sqrt(R^2 - y^2) has no real solution once y > |R|: a sphere
            # of this radius simply does not reach out that far. Swallowing
            # that and using 0.0 exported a flat disc where a curved surface
            # should be, with no error anywhere - the geometry was simply
            # wrong.
            radicand = radius**2 - y**2
            if radicand < 0.0:
                raise ValueError(
                    f"Surface of radius {radius} mm does not extend to "
                    f"{y:.4f} mm: |R| must be at least half the diameter "
                    f"({h:.4f} mm). Widen the radius or reduce the diameter."
                )
            z_sag = (y**2) / (radius + math.copysign(math.sqrt(radicand), radius))

            half_profile.append((y, z_sag))

        return half_profile

    def generate_surface_triangles(
        self,
        profile_points: List[Tuple[float, float]],
        z_offset: float,
        num_segments: int = 60,
        is_front: bool = True,
    ):
        """Generate triangles for a surface of revolution.

        Args:
            profile_points: (radius_from_axis, z) pairs from axis to rim.
            z_offset: Axial offset for the whole surface (0 for the front,
                the centre thickness for the back).
            num_segments: Number of segments around the circumference.
            is_front: Which way the cap faces. The front surface must have its
                normals pointing along -Z and the back along +Z, so that both
                point *out of* the glass. Winding both the same way made every
                front-surface normal point into the solid.

        Returns:
            List of triangle vertex tuples, wound so the normals face outward.
        """
        if not profile_points:
            return []

        triangles = []
        angle_step = 2 * math.pi / num_segments

        # Generate points around the circle
        for seg in range(num_segments):
            angle1 = seg * angle_step
            # Wrap the last segment back to 0 exactly. Computing the final
            # angle as n * step gives 2*pi, and sin(2*pi) is 6.4e-16 rather
            # than 0, so that vertex was a hair's breadth away from the one
            # segment 0 starts at. The two were not the same point, leaving a
            # seam right around the surface: the shell was not watertight and
            # every consumer that checks for closed meshes rejected the file.
            angle2 = ((seg + 1) % num_segments) * angle_step

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
                    if is_front:
                        triangles.append((p1, p3, p2))
                    else:
                        triangles.append((p1, p2, p3))
                else:
                    # Full quad. Reversing the vertex order flips the normal.
                    if is_front:
                        triangles.append((p1, p3, p2))
                        triangles.append((p1, p4, p3))
                    else:
                        triangles.append((p1, p2, p3))
                        triangles.append((p1, p3, p4))

        return triangles

    def generate_flat_surface(
        self,
        diameter: float,
        z_offset: float,
        num_segments: int = 60,
        is_front: bool = True,
    ):
        """Generate triangles for a flat surface"""
        triangles = []
        radius = diameter / 2.0
        angle_step = 2 * math.pi / num_segments

        center = (0.0, 0.0, z_offset)

        for seg in range(num_segments):
            angle1 = seg * angle_step
            # Wrap to exactly 0 for the last segment - see the note in
            # generate_surface_triangles: sin(2*pi) is not 0, so without this
            # the ring does not close on itself.
            angle2 = ((seg + 1) % num_segments) * angle_step

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

    def generate_edge_triangles(
        self, diameter: float, z_front_arr: Any, z_back_arr: Any, num_segments: int = 60
    ):
        """
        Generate triangles for the cylindrical edge.
        z_front_arr: Z coordinate of the front edge: a float, or a list of
            ``num_segments`` values (closed profile) / ``num_segments + 1``
            values (open profile).
        z_back_arr: Z coordinate of the back edge, with the same forms.
        """
        for name, values in (("z_front_arr", z_front_arr), ("z_back_arr", z_back_arr)):
            if isinstance(values, list) and len(values) not in (num_segments, num_segments + 1):
                raise ValueError(
                    f"{name} must have {num_segments} or {num_segments + 1} "
                    f"values, got {len(values)}"
                )

        triangles = []
        radius = diameter / 2.0
        angle_step = 2 * math.pi / num_segments

        for seg in range(num_segments):
            angle1 = seg * angle_step
            # Wrap to exactly 0 for the last segment; sin(2*pi) is not 0 and
            # would leave the barrel open. See generate_surface_triangles.
            angle2 = ((seg + 1) % num_segments) * angle_step

            cos1, sin1 = math.cos(angle1), math.sin(angle1)
            cos2, sin2 = math.cos(angle2), math.sin(angle2)

            zf1 = z_front_arr[seg] if isinstance(z_front_arr, list) else z_front_arr
            zf2 = (
                z_front_arr[(seg + 1) % len(z_front_arr)]
                if isinstance(z_front_arr, list)
                else z_front_arr
            )

            zb1 = z_back_arr[seg] if isinstance(z_back_arr, list) else z_back_arr
            zb2 = (
                z_back_arr[(seg + 1) % len(z_back_arr)]
                if isinstance(z_back_arr, list)
                else z_back_arr
            )

            # Four corners
            p1 = (radius * cos1, radius * sin1, zf1)  # Front 1
            p2 = (radius * cos2, radius * sin2, zf2)  # Front 2
            p3 = (radius * cos2, radius * sin2, zb2)  # Back 2
            p4 = (radius * cos1, radius * sin1, zb1)  # Back 1

            # Edge normals point radially outward.
            # Quad p1(front, seg) -> p2(front, seg+1) -> p3(back, seg+1) -> p4(back, seg)
            #
            #   Triangle 1: (p1, p2, p4). Normal = (p2-p1) x (p4-p1).
            #     (p2-p1) is tangential CCW; (p4-p1) is axial (+Z).
            #     tangent x axial = radial out.
            triangles.append((p1, p2, p4))

            #   Triangle 2: (p2, p3, p4). Normal = (p3-p2) x (p4-p2).
            #     (p3-p2) is axial (+Z); (p4-p2) is tangential CW.
            #     axial x (-tangent) = radial out.
            triangles.append((p2, p3, p4))

        return triangles

    def calculate_normal(
        self,
        p1: Tuple[float, float, float],
        p2: Tuple[float, float, float],
        p3: Tuple[float, float, float],
    ) -> Tuple[float, float, float]:
        """Calculate normal vector for a triangle using Vector3"""
        v1 = Vector3(p2[0] - p1[0], p2[1] - p1[1], p2[2] - p1[2])
        v2 = Vector3(p3[0] - p1[0], p3[1] - p1[1], p3[2] - p1[2])

        normal = v1.cross(v2).normalize()
        return (normal.x, normal.y, normal.z)

    def export_lens_to_stl(
        self,
        r1: float,
        r2: float,
        thickness: float,
        diameter: float,
        filename: str,
        resolution: int = 50,
    ) -> int:
        """Export a lens to STL format"""
        self.triangles = []

        # 1. Front Surface (R1)
        # Vertex at (0,0,0).
        profile1 = self.calculate_surface_profile(
            r1, diameter, is_front=True, resolution=resolution
        )
        if profile1:
            self.triangles.extend(
                self.generate_surface_triangles(
                    profile1, 0.0, num_segments=resolution * 2, is_front=True
                )
            )
            last_z_front = profile1[-1][1]  # Z at the edge
        else:
            # Flat
            self.triangles.extend(
                self.generate_flat_surface(
                    diameter, 0.0, num_segments=resolution * 2, is_front=True
                )
            )
            last_z_front = 0.0

        # 2. Back Surface (R2)
        # Vertex at (0,0,thickness)
        profile2 = self.calculate_surface_profile(
            r2, diameter, is_front=False, resolution=resolution
        )
        if profile2:
            self.triangles.extend(
                self.generate_surface_triangles(
                    profile2, thickness, num_segments=resolution * 2, is_front=False
                )
            )
            last_z_back = profile2[-1][1] + thickness  # Add offset
        else:
            # Flat
            self.triangles.extend(
                self.generate_flat_surface(
                    diameter, thickness, num_segments=resolution * 2, is_front=False
                )
            )
            last_z_back = thickness

        # 3. Edge
        # Edge connects last_z_front ring to last_z_back ring at diameter/2
        self.triangles.extend(
            self.generate_edge_triangles(
                diameter, last_z_front, last_z_back, num_segments=resolution * 2
            )
        )

        # Write
        self.write_binary_stl(filename)
        return len(self.triangles)

    def write_binary_stl(self, filename: str):
        """Write triangles to binary STL file"""
        with atomic_write_bytes(filename) as f:
            # Header (80 bytes)
            header = b"openlens STL export" + b" " * (80 - 19)
            f.write(header)

            # Number of triangles
            f.write(struct.pack("<I", len(self.triangles)))

            # Write each triangle
            for triangle in self.triangles:
                p1, p2, p3 = triangle

                normal = self.calculate_normal(p1, p2, p3)

                f.write(struct.pack("<fff", normal[0], normal[1], normal[2]))
                f.write(struct.pack("<fff", p1[0], p1[1], p1[2]))
                f.write(struct.pack("<fff", p2[0], p2[1], p2[2]))
                f.write(struct.pack("<fff", p3[0], p3[1], p3[2]))
                f.write(struct.pack("<H", 0))


def export_lens_stl(item: Any, filename: str, resolution: int = 50) -> int:
    """Wrapper for Lens or OpticalSystem object"""
    exporter = STLExporter()

    # Check if it's an OpticalSystem
    if hasattr(item, "elements") and hasattr(item, "air_gaps"):
        # Export entire assembly
        exporter.triangles = []
        for element in item.elements:
            lens = element.lens
            pos = element.position

            # Generate lens triangles
            # 1. Front Surface
            profile1 = exporter.calculate_surface_profile(
                lens.radius_of_curvature_1,
                lens.diameter,
                is_front=True,
                resolution=resolution,
            )
            if profile1:
                exporter.triangles.extend(
                    exporter.generate_surface_triangles(profile1, pos, num_segments=resolution * 2)
                )
                last_z_front = profile1[-1][1] + pos
            else:
                exporter.triangles.extend(
                    exporter.generate_flat_surface(
                        lens.diameter, pos, num_segments=resolution * 2, is_front=True
                    )
                )
                last_z_front = pos

            # 2. Back Surface
            profile2 = exporter.calculate_surface_profile(
                lens.radius_of_curvature_2,
                lens.diameter,
                is_front=False,
                resolution=resolution,
            )
            if profile2:
                exporter.triangles.extend(
                    exporter.generate_surface_triangles(
                        profile2,
                        pos + lens.thickness,
                        num_segments=resolution * 2,
                        # The back cap is wound like the front one unless it
                        # says otherwise: the half of the solid with the
                        # wrong winding has its normals pointing into the
                        # glass, and the exported mesh is inside-out (its
                        # signed volume is negative). The single-lens path
                        # already passes is_front=False here.
                        is_front=False,
                    )
                )
                last_z_back = profile2[-1][1] + pos + lens.thickness
            else:
                exporter.triangles.extend(
                    exporter.generate_flat_surface(
                        lens.diameter,
                        pos + lens.thickness,
                        num_segments=resolution * 2,
                        is_front=False,
                    )
                )
                last_z_back = pos + lens.thickness

            # 3. Edge
            exporter.triangles.extend(
                exporter.generate_edge_triangles(
                    lens.diameter,
                    last_z_front,
                    last_z_back,
                    num_segments=resolution * 2,
                )
            )

        exporter.write_binary_stl(filename)
        return len(exporter.triangles)

    # Single lens
    return exporter.export_lens_to_stl(
        item.radius_of_curvature_1,
        item.radius_of_curvature_2,
        item.thickness,
        item.diameter,
        filename,
        resolution,
    )
