"""
2D ray tracing engines for single lenses and multi-element systems.
"""

import math
from typing import List, Optional, Tuple, TYPE_CHECKING

from .ray import Ray, RefractionResult, OpticalIntersector
from .constants import (
    EPSILON,
    WAVELENGTH_GREEN,
    NM_TO_MM,
    REFRACTIVE_INDEX_AIR,
    DEFAULT_NUM_RAYS,
    DEFAULT_ANGLE_RANGE,
    DEFAULT_PROPAGATION_DISTANCE,
    MESH_RESOLUTION_HIGH,
    APERTURE_FILL_FACTOR,
    RAY_START_OFFSET_MM,
    RAY_EXIT_PROPAGATION_2D_MM,
)
from .lens import _is_flat

if TYPE_CHECKING:
    from .lens import Lens
    from .optical_system import OpticalSystem


class LensRayTracer:
    """
    Ray tracing engine for single lens elements.

    Traces rays through a lens using Snell's law at each surface.
    """

    def __init__(self, lens: "Lens", x_offset: float = 0.0) -> None:
        """
        Initialize ray tracer with a lens.

        Args:
            lens: Lens object with optical parameters
            x_offset: X position of the front vertex (mm)
        """
        self.lens = lens
        self.R1 = lens.radius_of_curvature_1
        self.R2 = lens.radius_of_curvature_2
        self.d = lens.thickness
        self.D = lens.diameter
        self.n = lens.refractive_index
        self.x_offset = x_offset

        self._calculate_geometry()

    def _calculate_geometry(self) -> None:
        """Calculate lens surface positions and centers"""
        self.lens_offset = self.x_offset
        self.front_vertex_x = self.lens_offset
        self.back_vertex_x = self.lens_offset + self.d

        if _is_flat(self.R1):
            self.front_center_x = self.front_vertex_x
            self.front_is_flat = True
        else:
            self.front_center_x = self.front_vertex_x + self.R1
            self.front_is_flat = False

        if _is_flat(self.R2):
            self.back_center_x = self.back_vertex_x
            self.back_is_flat = True
        else:
            self.back_center_x = self.back_vertex_x + self.R2
            self.back_is_flat = False

    def _get_surface_normal_angle(self, x: float, y: float, surface_type: str) -> float:
        """Calculate surface normal angle at a point."""
        if surface_type == "front":
            if self.front_is_flat:
                return 0
            else:
                dx = x - self.front_center_x
                dy = y
                return math.atan2(dy, dx)
        else:
            if self.back_is_flat:
                return 0
            else:
                dx = x - self.back_center_x
                dy = y
                return math.atan2(dy, dx)

    def _intersect_flat_surface(
        self, ray: Ray, vertex_x: float
    ) -> Optional[Tuple[float, float]]:
        """Find intersection of ray with a flat surface at vertex_x."""
        if abs(math.cos(ray.angle)) < EPSILON:
            return None

        t = (vertex_x - ray.x) / math.cos(ray.angle)
        if t < 0:
            return None

        y = ray.y + t * math.sin(ray.angle)

        if abs(y) > self.D / 2:
            return None

        return (vertex_x, y)

    def _intersect_sphere_surface(
        self,
        ray: Ray,
        center_x: float,
        R: float,
        is_front: bool,
    ) -> Optional[Tuple[float, float]]:
        """
        Find intersection of ray with a spherical surface.

        Args:
            ray: The ray to intersect.
            center_x: X coordinate of the sphere center.
            R: Absolute radius of curvature.
            is_front: True for front surface, False for back surface.
        """
        dx = math.cos(ray.angle)
        dy = math.sin(ray.angle)

        t_solutions = OpticalIntersector.intersect_sphere(
            ray.x, ray.y, 0, dx, dy, 0, center_x, 0, 0, R
        )

        if t_solutions is None:
            return None

        t1, t2 = t_solutions

        valid_ts = [t for t in [t1, t2] if t > EPSILON]
        if not valid_ts:
            if not is_front:
                dist_sq = (ray.x - center_x) ** 2 + ray.y**2
                R_sq = R**2
                R_signed = self.R2 if not is_front else self.R1
                already_exited = False
                if R_signed < 0 and dist_sq > R_sq:
                    already_exited = True
                elif R_signed > 0 and dist_sq < R_sq:
                    already_exited = True
                if already_exited:
                    return (ray.x, ray.y)
            return None

        R_signed = self.R1 if is_front else self.R2
        if is_front:
            t = min(valid_ts) if R_signed > 0 else max(valid_ts)
        else:
            t = max(valid_ts) if R_signed < 0 else min(valid_ts)

        x = ray.x + t * dx
        y = ray.y + t * dy

        if abs(y) > self.D / 2:
            if len(valid_ts) > 1:
                if is_front:
                    t_other = max(valid_ts) if R_signed > 0 else min(valid_ts)
                else:
                    t_other = min(valid_ts) if R_signed < 0 else max(valid_ts)
                x_other = ray.x + t_other * dx
                y_other = ray.y + t_other * dy
                if abs(y_other) <= self.D / 2:
                    return (x_other, y_other)
            return None

        return (x, y)

    def _intersect_front_surface(self, ray: Ray) -> Optional[Tuple[float, float]]:
        """Find intersection point of ray with front surface."""
        if self.front_is_flat:
            return self._intersect_flat_surface(ray, self.front_vertex_x)
        return self._intersect_sphere_surface(
            ray, self.front_center_x, abs(self.R1), is_front=True
        )

    def _intersect_back_surface(self, ray: Ray) -> Optional[Tuple[float, float]]:
        """Find intersection point of ray with back surface."""
        if self.back_is_flat:
            return self._intersect_flat_surface(ray, self.back_vertex_x)
        return self._intersect_sphere_surface(
            ray, self.back_center_x, abs(self.R2), is_front=False
        )

    def trace_ray(
        self, ray: Ray, propagate_distance: float = DEFAULT_PROPAGATION_DISTANCE
    ) -> Ray:
        """Trace a ray through the lens."""
        intersection = self._intersect_front_surface(ray)

        if intersection is None:
            if propagate_distance > 0:
                ray.propagate(propagate_distance)
            ray.terminated = True
            ray.hit = False
            return ray

        x1, y1 = intersection
        ray.x, ray.y = x1, y1
        if len(ray.path) == 0 or ray.path[-1] != (x1, y1):
            ray.path.append((x1, y1))
        ray.hit = True

        normal_angle = self._get_surface_normal_angle(x1, y1, "front")
        if (
            ray.refract_or_reflect(REFRACTIVE_INDEX_AIR, self.n, normal_angle)
            is not RefractionResult.REFRACTED
        ):
            ray.terminated = True
            return ray

        intersection = self._intersect_back_surface(ray)

        if intersection is None:
            dy = math.sin(ray.angle)
            if abs(dy) > EPSILON:
                y_side = (self.D / 2) if dy > 0 else (-self.D / 2)
                t_side = (y_side - ray.y) / dy
                if t_side > EPSILON:
                    x_side = ray.x + t_side * math.cos(ray.angle)
                    ray.x, ray.y = x_side, y_side
                    ray.path.append((x_side, y_side))

            ray.terminated = True
            return ray

        x2, y2 = intersection
        ray.x, ray.y = x2, y2
        if len(ray.path) == 0 or ray.path[-1] != (x2, y2):
            ray.path.append((x2, y2))

        normal_angle = self._get_surface_normal_angle(x2, y2, "back")
        if (
            ray.refract_or_reflect(self.n, REFRACTIVE_INDEX_AIR, normal_angle)
            is not RefractionResult.REFRACTED
        ):
            ray.terminated = True
            return ray

        if propagate_distance > 0:
            ray.propagate(propagate_distance)

        return ray

    def trace_parallel_rays(
        self,
        num_rays: int = DEFAULT_NUM_RAYS,
        ray_height_range: Optional[Tuple[float, float]] = None,
        wavelength_mm: float = WAVELENGTH_GREEN * NM_TO_MM,
        angle_deg: float = 0.0,
    ) -> List[Ray]:
        """Trace parallel rays (collimated beam) through the lens."""
        if ray_height_range is None:
            max_height = self.D / 2 * APERTURE_FILL_FACTOR
            ray_height_range = (-max_height, max_height)

        rays = []
        min_h, max_h = ray_height_range
        angle_rad = math.radians(angle_deg)
        start_x = -RAY_START_OFFSET_MM
        lens_x = 0.0

        for i in range(num_rays):
            if num_rays == 1:
                height = 0
            else:
                height = min_h + (max_h - min_h) * i / (num_rays - 1)

            y_start = height - (lens_x - start_x) * math.tan(angle_rad)
            ray = Ray(start_x, y_start, angle_rad, wavelength_mm=wavelength_mm)
            self.trace_ray(ray)
            rays.append(ray)

        return rays

    def trace_point_source_rays(
        self,
        source_x: float,
        source_y: float,
        num_rays: int = DEFAULT_NUM_RAYS,
        max_angle_deg: float = DEFAULT_ANGLE_RANGE[1],
        wavelength_mm: float = WAVELENGTH_GREEN * NM_TO_MM,
    ) -> List[Ray]:
        """Trace rays from a point source."""
        rays = []
        max_angle_rad = math.radians(max_angle_deg)

        for i in range(num_rays):
            if num_rays == 1:
                angle = 0
            else:
                angle = -max_angle_rad + 2 * max_angle_rad * i / (num_rays - 1)

            ray = Ray(source_x, source_y, angle, wavelength_mm=wavelength_mm)
            self.trace_ray(ray)
            rays.append(ray)

        return rays

    def find_focal_point(self, rays: List[Ray]) -> Optional[Tuple[float, float]]:
        """Find the focal point from a set of traced parallel rays."""
        crossings = []

        for ray in rays:
            if len(ray.path) < 2:
                continue

            last_crossing = None
            for i in range(len(ray.path) - 1):
                x1, y1 = ray.path[i]
                x2, y2 = ray.path[i + 1]

                if (y1 * y2 <= 0) and abs(y2 - y1) > 1e-6:
                    t = -y1 / (y2 - y1)
                    x_cross = x1 + t * (x2 - x1)
                    last_crossing = x_cross

            if last_crossing is not None:
                crossings.append(last_crossing)

        if not crossings:
            return None

        focal_x = sum(crossings) / len(crossings)
        return (focal_x, 0)

    def get_lens_outline(
        self, num_points: int = MESH_RESOLUTION_HIGH
    ) -> List[Tuple[float, float]]:
        """Get points defining the lens outline for visualization."""
        points = []
        y_max = self.D / 2
        y_values = [y_max - 2 * y_max * i / (num_points - 1) for i in range(num_points)]

        for y in y_values:
            if self.front_is_flat:
                x = self.lens_offset
            else:
                R = abs(self.R1)
                if y * y <= R * R:
                    if self.R1 > 0:
                        x = self.lens_offset - R + math.sqrt(R * R - y * y)
                    else:
                        x = self.lens_offset + R - math.sqrt(R * R - y * y)
                else:
                    continue
            points.append((x, y))

        for y in reversed(y_values):
            if self.back_is_flat:
                x = self.lens_offset + self.d
            else:
                R = abs(self.R2)
                if y * y <= R * R:
                    if self.R2 > 0:
                        x = self.lens_offset + self.d + R - math.sqrt(R * R - y * y)
                    else:
                        x = self.lens_offset + self.d - R + math.sqrt(R * R - y * y)
                else:
                    continue
            points.append((x, y))

        return points


class SystemRayTracer:
    """Ray tracer for multi-element optical systems"""

    def __init__(self, optical_system: "OpticalSystem") -> None:
        self.system = optical_system

    def trace_parallel_rays(
        self,
        num_rays: int = DEFAULT_NUM_RAYS,
        angle_deg: float = 0.0,
        wavelength_mm: float = WAVELENGTH_GREEN * NM_TO_MM,
    ) -> List[Ray]:
        """Trace parallel rays through the entire optical system."""
        if not self.system.elements:
            return []

        first_lens = self.system.elements[0].lens
        max_height = first_lens.diameter / 2 * APERTURE_FILL_FACTOR
        min_h, max_h = -max_height, max_height

        rays = []
        angle_rad = math.radians(angle_deg)
        first_pos = self.system.elements[0].position
        start_x = first_pos - RAY_START_OFFSET_MM

        for i in range(num_rays):
            if num_rays == 1:
                height = 0
            else:
                height = min_h + (max_h - min_h) * i / (num_rays - 1)

            y_start = height - (first_pos - start_x) * math.tan(angle_rad)
            ray = Ray(start_x, y_start, angle_rad, wavelength_mm=wavelength_mm)
            self._trace_ray_through_system(ray)
            rays.append(ray)

        return rays

    def trace_ray(self, ray: Ray) -> Ray:
        """Trace a single ray through all elements"""
        self._trace_ray_through_system(ray)
        return ray

    def _trace_ray_through_system(self, ray: Ray) -> None:
        """Trace a single ray through all elements"""

        for i, element in enumerate(self.system.elements):
            lens_tracer = LensRayTracer(element.lens, x_offset=element.position)
            lens_tracer.trace_ray(ray, propagate_distance=0)

            if not ray.hit:
                ray.terminated = False
                if i < len(self.system.elements) - 1:
                    next_pos = self.system.elements[i + 1].position
                    if next_pos > ray.x:
                        dist = next_pos - ray.x
                        ray.propagate(dist)
                else:
                    ray.propagate(RAY_EXIT_PROPAGATION_2D_MM)
                continue

            if ray.terminated:
                if math.cos(ray.angle) > 0.1:
                    ray.propagate(RAY_EXIT_PROPAGATION_2D_MM - ray.x)
                break

            if i < len(self.system.elements) - 1:
                next_pos = self.system.elements[i + 1].position
                if next_pos > ray.x:
                    dist = next_pos - ray.x
                    ray.propagate(dist)
                else:
                    ray.propagate(EPSILON)
            else:
                ray.propagate(RAY_EXIT_PROPAGATION_2D_MM)
