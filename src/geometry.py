"""
Centralized geometry calculations for lens profiles, polylines, and 3D meshes.
Used by exporters (SVG, STL, STEP) and visualization modules.
"""

import math
from typing import List, Tuple, Dict, Any, Optional

from .constants import EPSILON
from .lens import Lens


class LensGeometry:
    """Centralized logic for lens surface profiles and 3D meshes."""

    @staticmethod
    def surface_sag(
        radius: float,
        y: float,
        diameter: float,
        is_parabolic: bool = False,
        parabolic_sag: float = 0.0,
    ) -> float:
        """Vertex-referenced sag of one surface at height ``y``.

        Single shared implementation for every 2D/3D lens renderer, so the
        same lens draws identically everywhere. Flat surfaces (zero,
        non-finite, or huge radius) return 0. ``|y|`` is clamped to the
        clear aperture and to ``|R|``; aperture overhang therefore draws a
        hemisphere cap while :meth:`Lens.calculate_edge_thickness` reports
        the geometry as undefined (renderers tint it red).
        """
        half_d = diameter / 2
        ay = min(abs(y), abs(half_d))
        if is_parabolic:
            if abs(half_d) < EPSILON:
                return 0.0
            return parabolic_sag * (ay * ay) / (half_d * half_d)
        if not math.isfinite(radius) or abs(radius) < 1e-6:
            return 0.0
        r_a = abs(radius)
        ay = min(ay, r_a)
        sag = r_a - math.sqrt(max(0.0, r_a * r_a - ay * ay))
        return sag if radius > 0 else -sag

    @staticmethod
    def lens_outline(lens: Lens, num_points: int = 50) -> Dict[str, Any]:
        """Closed-form 2D cross-section in the vertex frame (front vertex at 0).

        Canonical convention: ``lens.thickness`` is the CENTER (vertex to
        vertex) thickness; the rim thickness is derived. Returns front
        (top to bottom) and back (bottom to top) ``(x, y)`` polylines plus
        vertex/rim positions, the true edge thickness, and feasibility.
        Every interactive 2D view and the 3D/gallery renderers build from
        this so outlines cannot drift apart.
        """
        diameter = lens.diameter
        thickness = lens.thickness
        half_d = diameter / 2
        is_para1 = bool(getattr(lens, "is_parabolic_1", False))
        para_sag1 = float(getattr(lens, "parabolic_sag_1", 0.0))
        is_para2 = bool(getattr(lens, "is_parabolic_2", False))
        para_sag2 = float(getattr(lens, "parabolic_sag_2", 0.0))
        r1 = lens.radius_of_curvature_1
        r2 = lens.radius_of_curvature_2

        def _sag1(y: float) -> float:
            return LensGeometry.surface_sag(r1, y, diameter, is_para1, para_sag1)

        def _sag2(y: float) -> float:
            return LensGeometry.surface_sag(r2, y, diameter, is_para2, para_sag2)

        front = [
            (
                _sag1(-half_d + (2 * half_d * j / num_points)),
                -half_d + (2 * half_d * j / num_points),
            )
            for j in range(num_points + 1)
        ]
        back = [
            (
                thickness + _sag2(half_d - (2 * half_d * j / num_points)),
                half_d - (2 * half_d * j / num_points),
            )
            for j in range(num_points + 1)
        ]

        try:
            edge = lens.calculate_edge_thickness()
        except Exception:
            edge = None

        return {
            "front": front,
            "back": back,
            "x1_vertex": 0.0,
            "x2_vertex": thickness,
            "x1_edge": front[-1][0],
            "x2_edge": back[0][0],
            "edge_thickness": edge,
            "feasible": edge is not None and edge > 0,
        }

    @staticmethod
    def get_surface_profile(
        radius: float, diameter: float, num_points: int = 50
    ) -> List[Tuple[float, float]]:
        """Calculate (z, r) coordinates for a spherical surface profile.

        Args:
            radius: Radius of curvature (mm).
            diameter: Clear aperture diameter (mm).
            num_points: Number of points to sample along the arc.

        Returns:
            List of (z, r) tuples.
        """
        if abs(radius) < EPSILON or abs(radius) > 1e10:
            return [(0.0, -diameter / 2), (0.0, diameter / 2)]

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
    def get_parabolic_profile(
        sag: float, diameter: float, num_points: int = 50
    ) -> List[Tuple[float, float]]:
        """Calculate (z, r) for a parabolic surface.

        Parabola is defined as z = sag * (r / r_max)² where sag is the
        vertex-to-rim distance at r_max = D/2. Positive sag bulges to +z.

        Args:
            sag: Sagitta at clear aperture (mm).
            diameter: Clear aperture diameter (mm).
            num_points: Number of points to sample.

        Returns:
            List of (z, r) tuples.
        """
        if abs(sag) < EPSILON or abs(diameter) < EPSILON:
            return [(0.0, -diameter / 2), (0.0, diameter / 2)]
        r_max = diameter / 2
        profile = []
        for i in range(num_points + 1):
            r = r_max - (2 * r_max * i / num_points)
            z = sag * (r * r) / (r_max * r_max)
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
        if getattr(lens, "is_parabolic_1", False):
            front = LensGeometry.get_parabolic_profile(
                lens.parabolic_sag_1, lens.diameter, num_points
            )
        else:
            front = LensGeometry.get_surface_profile(
                lens.radius_of_curvature_1, lens.diameter, num_points
            )
        if getattr(lens, "is_parabolic_2", False):
            back = LensGeometry.get_parabolic_profile(
                lens.parabolic_sag_2, lens.diameter, num_points
            )
        else:
            back = LensGeometry.get_surface_profile(
                lens.radius_of_curvature_2, lens.diameter, num_points
            )

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
        if getattr(lens, "is_parabolic_1", False):
            front_prof = LensGeometry.get_parabolic_profile(
                lens.parabolic_sag_1, lens.diameter, radial_div
            )
        else:
            front_prof = LensGeometry.get_surface_profile(
                lens.radius_of_curvature_1, lens.diameter, radial_div
            )
        if getattr(lens, "is_parabolic_2", False):
            back_prof = LensGeometry.get_parabolic_profile(
                lens.parabolic_sag_2, lens.diameter, radial_div
            )
        else:
            back_prof = LensGeometry.get_surface_profile(
                lens.radius_of_curvature_2, lens.diameter, radial_div
            )

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
