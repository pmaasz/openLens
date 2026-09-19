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
        # Direct attributes: Lens always defines these (constructor sets them
        # before anything reads them; from_dict hydrates them with defaults).
        self.R1 = lens.get_effective_radius_1()
        self.R2 = lens.get_effective_radius_2()
        self.d = lens.thickness
        self.D = lens.diameter
        self.n = lens.refractive_index
        self.x_offset = x_offset
        # Per-surface clear apertures (polished aperture; fall back to the
        # mechanical outer diameter when unset).
        get_ca1 = getattr(lens, "get_clear_aperture_1", None)
        get_ca2 = getattr(lens, "get_clear_aperture_2", None)
        self.CA1 = (get_ca1() if callable(get_ca1) else self.D) or self.D
        self.CA2 = (get_ca2() if callable(get_ca2) else self.D) or self.D
        # Parabolic flags
        self.is_parabolic_1 = bool(lens.is_parabolic_1)
        self.is_parabolic_2 = bool(lens.is_parabolic_2)
        self.parabolic_sag_1 = float(lens.parabolic_sag_1)
        self.parabolic_sag_2 = float(lens.parabolic_sag_2)

        self._calculate_geometry()

    def _calculate_geometry(self) -> None:
        """Calculate lens surface positions and centers"""
        self.lens_offset = self.x_offset
        self.front_vertex_x = self.lens_offset
        self.back_vertex_x = self.lens_offset + self.d

        # Parabolic surfaces are not flat but have no spherical center
        if self.is_parabolic_1 and abs(self.parabolic_sag_1) > EPSILON:
            self.front_is_flat = False
            self.front_is_parabolic = True
            self.front_center_x = self.front_vertex_x  # not used
        elif _is_flat(self.R1):
            self.front_center_x = self.front_vertex_x
            self.front_is_flat = True
            self.front_is_parabolic = False
        else:
            self.front_center_x = self.front_vertex_x + self.R1
            self.front_is_flat = False
            self.front_is_parabolic = False

        if self.is_parabolic_2 and abs(self.parabolic_sag_2) > EPSILON:
            self.back_is_flat = False
            self.back_is_parabolic = True
            self.back_center_x = self.back_vertex_x
        elif _is_flat(self.R2):
            self.back_center_x = self.back_vertex_x
            self.back_is_flat = True
            self.back_is_parabolic = False
        else:
            self.back_center_x = self.back_vertex_x + self.R2
            self.back_is_flat = False
            self.back_is_parabolic = False

    def _get_surface_normal_angle(self, x: float, y: float, surface_type: str) -> float:
        """Calculate surface normal angle at a point."""
        if surface_type == "front":
            if self.front_is_flat:
                return 0
            if self.front_is_parabolic:
                r_max = self.D / 2
                if abs(r_max) < EPSILON:
                    return 0
                # Parabola x = vertex + a*y^2, a = sag/r_max^2
                a = self.parabolic_sag_1 / (r_max * r_max)
                # Gradient (1, -2*a*y) -> normal
                return math.atan2(-2 * a * y, 1)
            else:
                dx = x - self.front_center_x
                dy = y
                return math.atan2(dy, dx)
        else:
            if self.back_is_flat:
                return 0
            if self.back_is_parabolic:
                r_max = self.D / 2
                if abs(r_max) < EPSILON:
                    return 0
                a = self.parabolic_sag_2 / (r_max * r_max)
                return math.atan2(-2 * a * y, 1)
            else:
                dx = x - self.back_center_x
                dy = y
                return math.atan2(dy, dx)

    def _intersect_flat_surface(
        self, ray: Ray, vertex_x: float, semi_aperture: Optional[float] = None
    ) -> Optional[Tuple[float, float]]:
        """Find intersection of ray with a flat surface at vertex_x."""
        cos_a = math.cos(ray.angle)
        if abs(cos_a) < EPSILON:
            return None

        t = (vertex_x - ray.x) / cos_a
        if t < 0:
            return None

        y = ray.y + t * math.sin(ray.angle)

        if abs(y) > (self.D / 2 if semi_aperture is None else semi_aperture):
            return None

        return (vertex_x, y)

    def _intersect_sphere_surface(
        self,
        ray: Ray,
        center_x: float,
        R: float,
        is_front: bool,
        semi_aperture: Optional[float] = None,
    ) -> Optional[Tuple[float, float]]:
        """
        Find intersection of ray with a spherical surface.

        Args:
            ray: The ray to intersect.
            center_x: X coordinate of the sphere center.
            R: Absolute radius of curvature.
            is_front: True for front surface, False for back surface.
            semi_aperture: Lateral half-aperture for clipping (defaults to D/2).
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
            return None

        # Mirror tracer_3d: a ray inside the sphere exits (max t), a ray
        # outside enters (min t). A zero-length "hit" at the current
        # position is never valid - it fabricates a refraction point and
        # lets missed rays continue through the system.
        dist_sq = (ray.x - center_x) ** 2 + ray.y**2
        inside = dist_sq < R * R - EPSILON
        limit = self.D / 2 if semi_aperture is None else semi_aperture
        for t in sorted(valid_ts, reverse=inside):
            x = ray.x + t * dx
            y = ray.y + t * dy
            if abs(y) <= limit:
                return (x, y)
        return None

    def _intersect_parabolic_surface(
        self,
        ray: Ray,
        vertex_x: float,
        sag: float,
        semi_aperture: Optional[float] = None,
    ) -> Optional[Tuple[float, float]]:
        """Intersect ray with a parabolic surface x = vertex + a*y^2, a=sag/r_max^2."""
        r_max = self.D / 2 if semi_aperture is None else semi_aperture
        if abs(r_max) < EPSILON or abs(sag) < EPSILON:
            return self._intersect_flat_surface(ray, vertex_x)
        a = sag / (r_max * r_max)
        # Ray: x = ray.x + t*cos, y = ray.y + t*sin
        cos_a = math.cos(ray.angle)
        sin_a = math.sin(ray.angle)
        # Equation: ray.x + t*cos = vertex_x + a*(ray.y + t*sin)^2
        # => a*sin^2 * t^2 + (2*a*ray.y*sin - cos)*t + (a*ray.y^2 + vertex_x - ray.x)=0
        A = a * sin_a * sin_a
        B = 2 * a * ray.y * sin_a - cos_a
        C = a * ray.y * ray.y + vertex_x - ray.x
        # Linear case when A ~0 (ray nearly parallel to axis)
        if abs(A) < EPSILON:
            if abs(B) < EPSILON:
                return None
            t = -C / B
            if t < EPSILON:
                return None
            y = ray.y + t * sin_a
            if abs(y) > r_max + 1e-6:
                return None
            return (vertex_x + a * y * y, y)
        disc = B * B - 4 * A * C
        if disc < -EPSILON:
            return None
        disc = max(0.0, disc)
        sqrt_disc = math.sqrt(disc)
        t1 = (-B - sqrt_disc) / (2 * A)
        t2 = (-B + sqrt_disc) / (2 * A)
        valid = [t for t in (t1, t2) if t > EPSILON]
        if not valid:
            return None
        # Choose smallest positive t (first intersection)
        t = min(valid)
        y = ray.y + t * sin_a
        if abs(y) > r_max + 1e-6:
            # Try other if first is outside aperture but second inside
            if len(valid) > 1:
                t_other = max(valid)
                y_other = ray.y + t_other * sin_a
                if abs(y_other) <= r_max:
                    return (vertex_x + a * y_other * y_other, y_other)
            return None
        return (vertex_x + a * y * y, y)

    def _intersect_front_surface(self, ray: Ray) -> Optional[Tuple[float, float]]:
        """Find intersection point of ray with front surface."""
        semi = self.CA1 / 2
        if self.front_is_parabolic:
            return self._intersect_parabolic_surface(
                ray, self.front_vertex_x, self.parabolic_sag_1, semi
            )
        if self.front_is_flat:
            return self._intersect_flat_surface(ray, self.front_vertex_x, semi)
        return self._intersect_sphere_surface(
            ray, self.front_center_x, abs(self.R1), is_front=True, semi_aperture=semi
        )

    def _intersect_back_surface(self, ray: Ray) -> Optional[Tuple[float, float]]:
        """Find intersection point of ray with back surface."""
        semi = self.CA2 / 2
        if self.back_is_parabolic:
            return self._intersect_parabolic_surface(
                ray, self.back_vertex_x, self.parabolic_sag_2, semi
            )
        if self.back_is_flat:
            return self._intersect_flat_surface(ray, self.back_vertex_x, semi)
        return self._intersect_sphere_surface(
            ray, self.back_center_x, abs(self.R2), is_front=False, semi_aperture=semi
        )

    def trace_ray(self, ray: Ray, propagate_distance: float = DEFAULT_PROPAGATION_DISTANCE) -> Ray:
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
                y_side = (self.CA2 / 2) if dy > 0 else (-self.CA2 / 2)
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
        fill: float = 1.0,
    ) -> List[Ray]:
        """Trace parallel rays (collimated beam) through the lens.

        Args:
            fill: Fraction of the semi-aperture spanned by the fan when
                ``ray_height_range`` is omitted. Defaults to the full
                aperture so rim spherical aberration is traced; pass the
                legacy viz-style ``APERTURE_FILL_FACTOR`` (0.95) explicitly
                for display fans.
        """
        if ray_height_range is None:
            max_height = self.D / 2 * fill
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

    def get_lens_outline(self, num_points: int = MESH_RESOLUTION_HIGH) -> List[Tuple[float, float]]:
        """Get points defining the lens outline for visualization."""
        points = []
        y_max = self.D / 2
        y_values = [y_max - 2 * y_max * i / (num_points - 1) for i in range(num_points)]

        for y in y_values:
            if self.front_is_parabolic:
                a = self.parabolic_sag_1 / (y_max * y_max) if abs(y_max) > EPSILON else 0
                x = self.lens_offset + a * y * y
            elif self.front_is_flat:
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
            if self.back_is_parabolic:
                a = self.parabolic_sag_2 / (y_max * y_max) if abs(y_max) > EPSILON else 0
                x = self.lens_offset + self.d + a * y * y
            elif self.back_is_flat:
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
        self._tracers: List[LensRayTracer] = []
        self._sync_tracers()

    def _sync_tracers(self) -> None:
        """Rebuild per-element tracers from current lens geometry/positions.

        Refreshed once per public trace call (not per ray per element),
        so lens-parameter or structural edits between calls are picked up
        while the per-ray loop stays allocation-free.
        """
        self._tracers = [
            LensRayTracer(element.lens, x_offset=element.position)
            for element in self.system.elements
        ]

    def trace_parallel_rays(
        self,
        num_rays: int = DEFAULT_NUM_RAYS,
        angle_deg: float = 0.0,
        wavelength_mm: float = WAVELENGTH_GREEN * NM_TO_MM,
        fill: float = 1.0,
    ) -> List[Ray]:
        """Trace parallel rays through the entire optical system.

        Args:
            fill: Fraction of the entrance-pupil semi-aperture spanned by
                the fan. Defaults to the full aperture; pass the legacy
                viz-style ``APERTURE_FILL_FACTOR`` (0.95) explicitly for
                display fans.
        """
        if not self.system.elements:
            return []

        self._sync_tracers()

        first_lens = self.system.elements[0].lens
        max_height = first_lens.diameter / 2 * fill
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
        self._sync_tracers()
        self._trace_ray_through_system(ray)
        return ray

    def _trace_ray_through_system(self, ray: Ray) -> None:
        """Trace a single ray through all elements.

        A ray that misses an element aperture or terminates inside one
        (TIR/side exit) stops here: it is marked terminated and never
        propagated forward, and a terminated flag is never cleared.
        Rays wider than the aperture stop are vignetted at the stop plane.
        Elements with decenter/tilt are traced in their local frame (the
        2D trace covers the y-meridian: decenter_y and tilt_z apply;
        decenter_z/tilt_x/tilt_y tip out of plane and are 3D-only).
        """

        stop = self.system.get_aperture_stop()
        stop_gap = stop["gap_index"] if stop is not None else None
        stop_semi = (
            stop["diameter"] / 2
            if stop is not None and stop.get("diameter")
            else None
        )

        for i, tracer in enumerate(self._tracers):
            element = self.system.elements[i]
            dy = float(getattr(element, "decenter_y", 0.0) or 0.0)
            tz = math.radians(float(getattr(element, "tilt_z", 0.0) or 0.0))
            if dy == 0.0 and tz == 0.0:
                tracer.trace_ray(ray, propagate_distance=0)
            else:
                self._trace_aligned_element(ray, element, tracer)

            if not ray.hit or ray.terminated:
                ray.terminated = True
                break

            if stop_gap is not None and stop_semi is not None and stop_gap == i:
                if not self._apply_stop(ray, stop):
                    break

            if i < len(self._tracers) - 1:
                next_pos = self.system.elements[i + 1].position
                if next_pos > ray.x:
                    dist = next_pos - ray.x
                    ray.propagate(dist)
                else:
                    ray.propagate(EPSILON)
            else:
                ray.propagate(RAY_EXIT_PROPAGATION_2D_MM)

    def _apply_stop(self, ray: Ray, stop: dict) -> bool:
        """Vignette a ray at the aperture stop plane.

        Returns True if the ray passes, False if it is stopped (ray is
        terminated with the stop-plane point appended).
        """
        semi = stop["diameter"] / 2
        stop_x = stop["position"]
        cos_a = math.cos(ray.angle)
        if abs(cos_a) < EPSILON:
            ray.terminated = True
            return False
        t = (stop_x - ray.x) / cos_a
        y_stop = ray.y if t < 0 else ray.y + t * math.sin(ray.angle)
        if abs(y_stop) > semi:
            if t >= 0:
                ray.x = stop_x
                ray.y = y_stop
                ray.path.append((ray.x, ray.y))
            ray.terminated = True
            return False
        return True

    def _trace_aligned_element(self, ray: Ray, element, tracer: LensRayTracer) -> None:
        """Trace through a decentered/tilted element via its local frame.

        The frame matches the tree convention exactly: origin at the
        element's front vertex, rotation about that origin, so 2D results
        agree with the 3D tracer (which refracts through the node global
        transform). The ray is mapped into the frame, traced with a
        centered element tracer, then mapped back including the new path
        points. Exact for the centered-tracer math; identity when alignment
        is zero (callers take the fast path instead).
        """
        dy = float(getattr(element, "decenter_y", 0.0) or 0.0)
        tz = math.radians(float(getattr(element, "tilt_z", 0.0) or 0.0))
        lens = element.lens
        cx = element.position
        cos_t = math.cos(tz)
        sin_t = math.sin(tz)

        # World -> local (translate to front vertex, rotate by -tz).
        n_path = len(ray.path)
        lx = (ray.x - cx) * cos_t + (ray.y - dy) * sin_t
        ly = -(ray.x - cx) * sin_t + (ray.y - dy) * cos_t
        ray.x, ray.y = lx, ly
        ray.angle = ray.angle - tz

        local = LensRayTracer(lens, x_offset=0.0)
        local.trace_ray(ray, propagate_distance=0)

        # Local -> world (rotate by +tz, translate back), including the
        # points appended during the local trace.
        for k in range(n_path, len(ray.path)):
            px, py = ray.path[k]
            ray.path[k] = (
                px * cos_t - py * sin_t + cx,
                px * sin_t + py * cos_t + dy,
            )
        ray.x, ray.y = ray.path[-1]
        ray.angle = ray.angle + tz
