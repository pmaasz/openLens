"""
Centralized geometry calculations for lens profiles, polylines, and 3D meshes.
Used by exporters (SVG, STL, STEP) and visualization modules.
"""

from typing import List, Tuple, Dict, Any

from .lens import Lens


class LensGeometry:
    """Centralized logic for lens profiles, polylines, and 3D meshes.

    All surface sags come from the single source of truth
    (``Lens.get_sag_1/2``); this module only assembles outlines, polylines,
    and meshes from those values.
    """

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

        front = [
            (
                lens.get_sag_1(-half_d + (2 * half_d * j / num_points)),
                -half_d + (2 * half_d * j / num_points),
            )
            for j in range(num_points + 1)
        ]
        back = [
            (
                thickness + lens.get_sag_2(half_d - (2 * half_d * j / num_points)),
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
    def get_lens_polyline(lens: Lens, num_points: int = 50) -> List[Tuple[float, float]]:
        """Get a closed (z, r) polyline representing the lens cross-section.

        Built from the shared outline, so the STEP/SVG export path draws
        exactly what the interactive views draw.

        Args:
            lens: Lens object.
            num_points: Points per surface.

        Returns:
            List of (z, r) coordinates forming a closed loop.
        """
        outline = LensGeometry.lens_outline(lens, num_points)

        # Polyline: Front (Top to Bottom) -> Back (Bottom to Top) -> Close
        return outline["front"] + outline["back"]
