"""
Centralized geometry calculations for lens profiles, polylines, and 3D meshes.
Used by exporters (SVG, STL, STEP) and visualization modules.
"""

from bisect import bisect_left
from dataclasses import dataclass
import math
from typing import Any, Dict, List, Optional, Tuple

from .constants import EPSILON
from .lens import Lens


@dataclass(frozen=True)
class FresnelFacet:
    """One radial facet of a stepped Fresnel surface."""

    r_start: float
    r_end: float
    z_start: float
    z_end: float

    @property
    def slope(self) -> float:
        """Return the axial slope of the facet as a function of radius."""
        if abs(self.r_end - self.r_start) < EPSILON:
            return 0.0
        return (self.z_end - self.z_start) / (self.r_end - self.r_start)

    def sag_at(self, radial: float) -> float:
        """Return the facet height at a radial coordinate."""
        if abs(self.r_end - self.r_start) < EPSILON:
            return self.z_start
        fraction = (radial - self.r_start) / (self.r_end - self.r_start)
        fraction = max(0.0, min(1.0, fraction))
        return self.z_start + fraction * (self.z_end - self.z_start)


class LensGeometry:
    """Centralized logic for lens profiles, polylines, and 3D meshes."""

    @staticmethod
    def _parent_sag(lens: Lens, surface: int, radial: float) -> float:
        """Return the smooth parent-surface sag at a radial coordinate."""
        if surface == 1:
            return lens.get_sag_1(radial)
        if surface == 2:
            return lens.get_sag_2(radial)
        raise ValueError(f"surface must be 1 or 2, got {surface}")

    @staticmethod
    def is_fresnel_surface(lens: Lens, surface: int) -> bool:
        """Return whether a surface is stepped for a Fresnel lens.

        The existing boolean model defaults to stepping both surfaces. A
        lens may provide a ``fresnel_surface`` attribute set to ``front`` or
        ``back`` when only one optical surface is grooved.
        """
        if not bool(getattr(lens, "is_fresnel", False)) or surface not in (1, 2):
            return False

        configured_surface = getattr(lens, "fresnel_surface", "both")
        if configured_surface in ("front", 1):
            return surface == 1
        if configured_surface in ("back", 2):
            return surface == 2
        if configured_surface in ("both", None, ""):
            return True
        return True

    @staticmethod
    def fresnel_facets(lens: Lens, surface: int) -> List[FresnelFacet]:
        """Build the linear radial facets used by a Fresnel surface.

        ``groove_pitch`` is the radial width of a zone. Each facet follows
        the parent sag relative to the inner edge, then returns to the
        parent sag at zero at the next zone. This produces the same profile
        for the 2D outline, the revolved 3D mesh, and both ray tracers.
        """
        if not LensGeometry.is_fresnel_surface(lens, surface):
            return []

        half_d = abs(float(lens.diameter)) / 2.0
        pitch = float(getattr(lens, "groove_pitch", 0.0))
        if half_d <= EPSILON or not math.isfinite(pitch) or pitch <= EPSILON:
            return []

        full_zones = int(math.floor(half_d / pitch + 1e-9))
        if full_zones < 1:
            return []

        facets = []
        for index in range(full_zones):
            r_start = index * pitch
            r_end = min((index + 1) * pitch, half_d)
            if r_end <= r_start + EPSILON:
                continue
            z_start = 0.0
            z_end = LensGeometry._parent_sag(lens, surface, r_end) - LensGeometry._parent_sag(
                lens, surface, r_start
            )
            facets.append(FresnelFacet(r_start, r_end, z_start, z_end))

        last_radius = facets[-1].r_end if facets else 0.0
        if half_d - last_radius > EPSILON:
            z_end = LensGeometry._parent_sag(lens, surface, half_d) - LensGeometry._parent_sag(
                lens, surface, last_radius
            )
            facets.append(FresnelFacet(last_radius, half_d, 0.0, z_end))

        return facets

    @staticmethod
    def surface_sag(lens: Lens, surface: int, radial: float) -> float:
        """Return the stepped sag at a radial coordinate."""
        half_d = abs(float(lens.diameter)) / 2.0
        radius = max(0.0, min(half_d, abs(float(radial))))
        facets = LensGeometry.fresnel_facets(lens, surface)
        if not facets:
            return LensGeometry._parent_sag(lens, surface, radius)

        for facet in facets:
            if radius < facet.r_end - EPSILON or facet is facets[-1]:
                return facet.sag_at(radius)
        return facets[-1].sag_at(radius)

    @staticmethod
    def surface_profile(
        lens: Lens,
        surface: int,
        num_points: int = 50,
        max_points: Optional[int] = None,
    ) -> List[Tuple[float, float]]:
        """Return positive-radius ``(z, radius)`` samples for one surface.

        ``max_points`` limits display sampling without changing the facet
        definition used by ray tracing.
        """
        half_d = abs(float(lens.diameter)) / 2.0
        count = max(1, int(num_points))
        if half_d <= EPSILON:
            return [(0.0, 0.0)]

        facets = LensGeometry.fresnel_facets(lens, surface)
        if not facets:
            return [
                (
                    LensGeometry._parent_sag(lens, surface, half_d * i / count),
                    half_d * i / count,
                )
                for i in range(count + 1)
            ]

        subdivisions = max(1, math.ceil((count + 1) / len(facets)))
        profile = []
        for facet in facets:
            for index in range(subdivisions):
                fraction = index / subdivisions
                radius = facet.r_start + fraction * (facet.r_end - facet.r_start)
                profile.append((facet.sag_at(radius), radius))
            profile.append((facet.z_end, facet.r_end))

        if max_points is not None and len(profile) > max_points:
            limit = max(2, int(max_points))
            indices = sorted(
                {round(index * (len(profile) - 1) / (limit - 1)) for index in range(limit)}
            )
            profile = [profile[index] for index in indices]
        return profile

    @staticmethod
    def groove_steps(
        lens: Lens, surface: int, max_steps: Optional[int] = None
    ) -> List[Tuple[float, float, float]]:
        """Return ``(radius, before_z, after_z)`` at each groove reset."""
        facets = LensGeometry.fresnel_facets(lens, surface)
        steps = [
            (current.r_start, previous.z_end, current.z_start)
            for previous, current in zip(facets, facets[1:])
        ]
        if max_steps is not None and len(steps) > max_steps:
            limit = max(1, int(max_steps))
            indices = sorted(
                {round(index * (len(steps) - 1) / max(1, limit - 1)) for index in range(limit)}
            )
            steps = [steps[index] for index in indices]
        return steps

    @staticmethod
    def _signed_points(
        lens: Lens,
        surface: int,
        ascending: bool,
        num_points: int,
        max_points: Optional[int],
    ) -> List[Tuple[float, float]]:
        """Return a full signed radial profile in the requested order."""
        facets = LensGeometry.fresnel_facets(lens, surface)
        if not facets:
            half_d = abs(float(lens.diameter)) / 2.0
            count = max(1, int(num_points))
            points = [
                (
                    LensGeometry._parent_sag(lens, surface, -half_d + 2 * half_d * index / count),
                    -half_d + 2 * half_d * index / count,
                )
                for index in range(count + 1)
            ]
            return points if ascending else list(reversed(points))

        profile = LensGeometry.surface_profile(lens, surface, num_points, max_points)
        if ascending:
            return [(z, -radius) for z, radius in reversed(profile)] + profile[1:]
        return list(reversed(profile)) + [(z, -radius) for z, radius in profile[1:]]

    @staticmethod
    def _minimum_thickness(lens: Lens) -> Optional[float]:
        """Return the minimum local thickness of the rendered profile."""
        try:
            facets_1 = LensGeometry.fresnel_facets(lens, 1)
            facets_2 = LensGeometry.fresnel_facets(lens, 2)
            if not facets_1 and not facets_2:
                return lens.calculate_edge_thickness()

            half_d = abs(float(lens.diameter)) / 2.0
            radii = {0.0, half_d}
            for facet in facets_1 + facets_2:
                radii.add(facet.r_start)
                radii.add(facet.r_end)
            radii = sorted(radii)

            def boundary_values(
                facets: List[FresnelFacet], surface: int, radii: List[float]
            ) -> List[List[float]]:
                if not facets:
                    return [[LensGeometry._parent_sag(lens, surface, radius)] for radius in radii]
                starts = [facet.r_start for facet in facets]
                values_at_radius = []
                for radius in radii:
                    index = bisect_left(starts, radius + EPSILON)
                    candidates = []
                    if index < len(facets):
                        candidates.append(facets[index])
                    if index > 0:
                        candidates.append(facets[index - 1])
                    values_at_radius.append([facet.sag_at(radius) for facet in candidates])
                return values_at_radius

            front_values = boundary_values(facets_1, 1, radii)
            back_values = boundary_values(facets_2, 2, radii)
            values = [
                lens.thickness + back_z - front_z
                for front_options, back_options in zip(front_values, back_values)
                for front_z in front_options
                for back_z in back_options
            ]
            return min(values) if values else lens.calculate_edge_thickness()
        except (ArithmeticError, TypeError, ValueError):
            return None

    @staticmethod
    def lens_outline(
        lens: Lens, num_points: int = 50, max_points: Optional[int] = None
    ) -> Dict[str, Any]:
        """Return the closed 2D cross-section in the lens vertex frame.

        Smooth lenses retain the existing uniform sampling. Fresnel lenses
        use a shared stepped profile with radial zone boundaries, so every
        2D renderer and the revolved 3D renderer show the same grooves.
        ``max_points`` optionally caps the radial samples for interactive
        displays while preserving the profile endpoints.
        """
        thickness = lens.thickness
        front_profile = LensGeometry._signed_points(lens, 1, True, num_points, max_points)
        back_profile = LensGeometry._signed_points(lens, 2, False, num_points, max_points)
        front = list(front_profile)
        back = [(thickness + z, y) for z, y in back_profile]

        edge = None
        minimum_thickness = None
        try:
            if LensGeometry.is_fresnel_surface(lens, 1) or LensGeometry.is_fresnel_surface(lens, 2):
                edge = back[0][0] - front[-1][0]
                minimum_thickness = LensGeometry._minimum_thickness(lens)
            else:
                edge = lens.calculate_edge_thickness()
                minimum_thickness = edge
        except (ArithmeticError, TypeError, ValueError):
            edge = None
            minimum_thickness = None

        return {
            "front": front,
            "back": back,
            "x1_vertex": 0.0,
            "x2_vertex": thickness,
            "x1_edge": front[-1][0],
            "x2_edge": back[0][0],
            "edge_thickness": edge,
            "minimum_thickness": minimum_thickness,
            "feasible": minimum_thickness is not None and minimum_thickness > 0,
        }

    @staticmethod
    def get_lens_polyline(
        lens: Lens, num_points: int = 50, max_points: Optional[int] = None
    ) -> List[Tuple[float, float]]:
        """Get a closed ``(z, r)`` polyline representing the lens section."""
        outline = LensGeometry.lens_outline(lens, num_points, max_points)
        return outline["front"] + outline["back"]
