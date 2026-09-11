"""
3D ray tracing engines for single lenses and multi-element systems.
"""

import math
from typing import List, Optional, Tuple, TYPE_CHECKING

from .ray import Ray3D, Ray, RefractionResult, OpticalIntersector, HAS_POLARIZATION
from .vector3 import Vector3, vec3
from .transform import Matrix4x4
from .constants import (
    EPSILON,
    WAVELENGTH_GREEN,
    NM_TO_MM,
    REFRACTIVE_INDEX_AIR,
    DEFAULT_NUM_RAYS,
    DEFAULT_PROPAGATION_DISTANCE,
    RAY_START_OFFSET_3D_MM,
    RAY_EXIT_PROPAGATION_3D_MM,
)
from .lens import _is_flat

if TYPE_CHECKING:
    from .lens import Lens
    from .optical_system import OpticalSystem


class LensRayTracer3D:
    """
    3D Ray tracing engine for single lens elements.
    Accepts an optional transformation matrix for position/orientation.
    """

    def __init__(
        self, lens: "Lens", transform: Optional[Matrix4x4] = None, x_offset: float = 0.0
    ) -> None:
        self.lens = lens
        # Use effective radius for parabolic surfaces
        self.R1 = (
            lens.get_effective_radius_1()
            if hasattr(lens, "get_effective_radius_1")
            else lens.radius_of_curvature_1
        )
        self.R2 = (
            lens.get_effective_radius_2()
            if hasattr(lens, "get_effective_radius_2")
            else lens.radius_of_curvature_2
        )
        self.d = lens.thickness
        self.D = lens.diameter
        self.n = lens.refractive_index
        self.is_parabolic_1 = bool(getattr(lens, "is_parabolic_1", False))
        self.is_parabolic_2 = bool(getattr(lens, "is_parabolic_2", False))
        self.parabolic_sag_1 = float(getattr(lens, "parabolic_sag_1", 0.0))
        self.parabolic_sag_2 = float(getattr(lens, "parabolic_sag_2", 0.0))

        if transform:
            self.transform = transform
        else:
            self.transform = Matrix4x4.from_translation(x_offset, 0, 0)

        self._calculate_geometry()

    def _calculate_geometry(self) -> None:
        """Calculate lens surface positions and centers in 3D using transform"""
        v0 = vec3(0, 0, 0)
        v1 = vec3(self.d, 0, 0)

        self.front_vertex = self.transform.multiply_point(v0)
        self.back_vertex = self.transform.multiply_point(v1)

        if self.is_parabolic_1 and abs(self.parabolic_sag_1) > EPSILON:
            self.front_center = self.front_vertex
            self.front_is_flat = False
            self.front_is_parabolic = True
        elif _is_flat(self.R1):
            self.front_center = self.front_vertex
            self.front_is_flat = True
            self.front_is_parabolic = False
        else:
            self.front_center = self.transform.multiply_point(vec3(self.R1, 0, 0))
            self.front_is_flat = False
            self.front_is_parabolic = False

        if self.is_parabolic_2 and abs(self.parabolic_sag_2) > EPSILON:
            self.back_center = self.back_vertex
            self.back_is_flat = False
            self.back_is_parabolic = True
        elif _is_flat(self.R2):
            self.back_center = self.back_vertex
            self.back_is_flat = True
            self.back_is_parabolic = False
        else:
            self.back_center = self.transform.multiply_point(vec3(self.d + self.R2, 0, 0))
            self.back_is_flat = False
            self.back_is_parabolic = False

        self.optical_axis = self.transform.multiply_vector(vec3(1, 0, 0)).normalize()

        # Cached inverse transform for the per-ray local-frame math (the
        # transform never changes after __init__). None when singular, in
        # which case callers fall back to a translation-only approximation.
        try:
            self._inv = self.transform.inverse()
        except Exception:
            self._inv = None

        # Single aperture tolerance shared by every aperture check here
        # (matches the exact D/2 convention of the 2D tracer).
        self._aperture_sq = (self.D / 2.0 + 1e-9) ** 2

    def _to_local_point(self, point: Vector3, vertex: Vector3) -> Vector3:
        """Map a world point into the surface-local frame (vertex at origin)."""
        if self._inv is not None:
            return self._inv.multiply_point(point)
        return point - vertex

    def _to_local_vector(self, vector: Vector3) -> Vector3:
        """Map a world direction into the surface-local frame."""
        if self._inv is not None:
            return self._inv.multiply_vector(vector)
        return vector

    def _outward_normal(self, geometric: Vector3, surface_type: str) -> Vector3:
        """Orient a surface normal away from the glass interior.

        Front normals end up ≈ -axis, back normals ≈ +axis, regardless of
        curvature sign. Refraction itself is orientation-agnostic
        (apply_snell auto-flips), but the polarization basis s = k×n and
        tilted-transform handling require one consistent convention, which
        per-sign flip cascades cannot provide.
        """
        normal = geometric.normalize()
        want = -1.0 if surface_type == "front" else 1.0
        if normal.dot(self.optical_axis) * want < 0.0:
            normal = -normal
        return normal

    def _intersect_sphere(
        self, ray: Ray3D, center: Vector3, radius: float, is_convex: bool
    ) -> Optional[Vector3]:
        """Intersect ray with a sphere."""
        t_solutions = OpticalIntersector.intersect_sphere(
            ray.origin.x,
            ray.origin.y,
            ray.origin.z,
            ray.direction.x,
            ray.direction.y,
            ray.direction.z,
            center.x,
            center.y,
            center.z,
            radius,
        )

        if t_solutions is None:
            return None

        t1, t2 = t_solutions

        valid_ts = [t for t in [t1, t2] if t > -EPSILON]
        if not valid_ts:
            return None

        dist_sq = (ray.origin - center).magnitude_sq()
        is_inside = dist_sq < radius**2

        if is_inside:
            t = max(valid_ts)
        else:
            t = min(valid_ts)

        return ray.origin + ray.direction * t

    def _intersect_plane(
        self, ray: Ray3D, point_on_plane: Vector3, normal: Vector3
    ) -> Optional[Vector3]:
        denom = normal.dot(ray.direction)
        if abs(denom) < EPSILON:
            return None

        t = (point_on_plane - ray.origin).dot(normal) / denom
        if t < -EPSILON:
            return None

        return ray.origin + ray.direction * t

    def _intersect_paraboloid(self, ray: Ray3D, vertex: Vector3, R: float) -> Optional[Vector3]:
        """Intersect ray with a paraboloid x = (y²+z²)/(2R) + vertex.x.

        R is the vertex radius (positive opens +x, negative -x). Vertex is in
        world coords, axis is along optical_axis (+x for identity transform).
        For simplicity we assume the paraboloid is axis-aligned with the
        transform's x-axis (true for our translators). We work in local
        coordinates where vertex is at origin and axis is x.
        """
        if abs(R) < EPSILON or abs(R) > 1e10:
            return self._intersect_plane(ray, vertex, self.optical_axis)
        # Transform ray to local coords where vertex is origin and axis is x
        # (cached inverse; translation-only fallback when singular).
        local_origin = self._to_local_point(ray.origin, vertex)
        local_dir = self._to_local_vector(ray.direction)
        # Paraboloid: x = (y²+z²)/(2R)
        # Ray: x = ox + t*dx, y = oy + t*dy, z = oz + t*dz
        ox, oy, oz = local_origin.x, local_origin.y, local_origin.z
        dx, dy, dz = local_dir.x, local_dir.y, local_dir.z
        # Equation: ox + t*dx = ( (oy+t*dy)² + (oz+t*dz)² ) / (2R)
        # => (dy²+dz²)/(2R) * t² + (2*oy*dy+2*oz*dz)/(2R) - dx) * t + (oy²+oz²)/(2R) - ox =0
        # Multiply by 2R: (dy²+dz²) t² + (2*oy*dy+2*oz*dz -2R*dx) t + (oy²+oz² -2R*ox)=0
        a = dy * dy + dz * dz
        b = 2 * (oy * dy + oz * dz - R * dx)
        c = oy * oy + oz * oz - 2 * R * ox
        if abs(a) < EPSILON:
            # Linear
            if abs(b) < EPSILON:
                return None
            t = -c / b
            if t < EPSILON:
                return None
            local_hit = local_origin + local_dir * t
            # Check aperture in local
            if local_hit.y * local_hit.y + local_hit.z * local_hit.z > self._aperture_sq:
                return None
            return self.transform.multiply_point(local_hit)
        disc = b * b - 4 * a * c
        if disc < -EPSILON:
            return None
        disc = max(0.0, disc)
        sqrt_disc = math.sqrt(disc)
        t1 = (-b - sqrt_disc) / (2 * a)
        t2 = (-b + sqrt_disc) / (2 * a)
        # Choose smallest positive
        valid = [t for t in (t1, t2) if t > EPSILON]
        if not valid:
            return None
        # For paraboloid, the smaller t is the first hit when outside
        t = min(valid)
        local_hit = local_origin + local_dir * t
        if local_hit.y * local_hit.y + local_hit.z * local_hit.z > self._aperture_sq:
            # Try other if first outside aperture but second inside
            if len(valid) > 1:
                t_other = max(valid)
                local_hit_other = local_origin + local_dir * t_other
                if (
                    local_hit_other.y * local_hit_other.y + local_hit_other.z * local_hit_other.z
                    <= self._aperture_sq
                ):
                    return self.transform.multiply_point(local_hit_other)
            return None
        return self.transform.multiply_point(local_hit)

    def trace_surface(
        self, ray: Ray3D, surface_type: str, interaction: str = "refract"
    ) -> RefractionResult:
        """Trace ray interaction with a specific surface."""
        if surface_type == "front":
            center = self.front_center
            is_flat = self.front_is_flat
            is_parabolic = getattr(self, "front_is_parabolic", False)
            vertex = self.front_vertex
            R = self.R1
            default_n1 = REFRACTIVE_INDEX_AIR
            default_n2 = self.n
        elif surface_type == "back":
            center = self.back_center
            is_flat = self.back_is_flat
            is_parabolic = getattr(self, "back_is_parabolic", False)
            vertex = self.back_vertex
            R = self.R2
            default_n1 = self.n
            default_n2 = REFRACTIVE_INDEX_AIR
        else:
            return RefractionResult.MISSED

        if is_parabolic:
            # R is the effective vertex radius (may be negative).
            if abs(R) < EPSILON or abs(R) > 1e10:
                normal = -self.optical_axis if surface_type == "front" else self.optical_axis
                intersection = self._intersect_plane(ray, vertex, self.optical_axis)
            else:
                normal = None  # gradient-based: oriented outward below
                intersection = self._intersect_paraboloid(ray, vertex, R)
        elif is_flat:
            normal = self.optical_axis
            intersection = self._intersect_plane(ray, vertex, normal)
        else:
            intersection = self._intersect_sphere(ray, center, abs(R), (R > 0))

        if intersection is None:
            if surface_type == "back" and not is_flat:
                dist_sq = (ray.origin - center).magnitude_sq()
                R_abs = abs(R)
                already_exited = False

                if R < 0 and dist_sq > R_abs**2:
                    already_exited = True
                elif R > 0 and dist_sq < R_abs**2:
                    already_exited = True

                if already_exited:
                    ray.n = default_n2
                    return RefractionResult.REFRACTED

            return RefractionResult.MISSED

        v_to_i = intersection - vertex
        proj = v_to_i.dot(self.optical_axis)
        dist_sq = v_to_i.magnitude_sq() - proj**2

        if dist_sq > self._aperture_sq:
            return RefractionResult.MISSED

        # Accumulate optical path for the segment just travelled in the
        # current medium (air gap before the front surface, glass between
        # the surfaces). Without this, Ray3D.optical_path_length would only
        # contain the exit-propagation leg and every OPL difference (hence
        # every wavefront map) would be wrong by ~millimetres of glass path.
        segment = intersection - ray.origin
        ray.optical_path_length += segment.magnitude() * ray.n

        ray.origin = intersection
        ray.path.append(intersection)

        if is_parabolic and normal is None:
            # Paraboloid normal: gradient of F = x - (y²+z²)/(2R) - vx = 0,
            # i.e. (1, -y/R, -z/R) in the local frame, oriented outward.
            # (Planar fallback keeps the ∓axis normal assigned above.)
            try:
                local_hit = self._to_local_point(intersection, vertex)
                ly, lz = local_hit.y, local_hit.z
                if abs(R) < EPSILON:
                    normal_local = vec3(1, 0, 0)
                else:
                    normal_local = vec3(1, -ly / R, -lz / R).normalize()
                geometric = self.transform.multiply_vector(normal_local)
            except Exception:
                geometric = None
            if geometric is None:
                normal = -self.optical_axis if surface_type == "front" else self.optical_axis
            else:
                normal = self._outward_normal(geometric, surface_type)
        elif is_flat:
            if surface_type == "front":
                normal = -self.optical_axis
            else:
                normal = self.optical_axis
        else:
            normal = self._outward_normal(intersection - center, surface_type)

        current_n = ray.n

        if abs(current_n - default_n1) < 1e-3:
            n1, n2 = default_n1, default_n2
        elif abs(current_n - default_n2) < 1e-3:
            n1, n2 = default_n2, default_n1
        else:
            n1, n2 = current_n, default_n2

        if interaction == "reflect":
            ray.reflect(normal, n1, n2)
            return RefractionResult.REFLECTED
        elif interaction == "refract":
            return ray.refract_or_reflect(n1, n2, normal)

        return RefractionResult.MISSED

    def trace_ray(
        self, ray: Ray3D, propagate_distance: float = DEFAULT_PROPAGATION_DISTANCE
    ) -> Ray3D:
        if self.trace_surface(ray, "front", "refract") is not RefractionResult.REFRACTED:
            if not ray.terminated:
                ray.propagate(propagate_distance)
                ray.terminated = True
            return ray

        if self.trace_surface(ray, "back", "refract") is not RefractionResult.REFRACTED:
            ray.terminated = True
            return ray

        ray.propagate(propagate_distance)
        return ray


class SystemRayTracer3D:
    """Ray tracer for multi-element optical systems in 3D"""

    def __init__(self, optical_system: "OpticalSystem") -> None:
        self.system = optical_system

    def trace_ray(self, ray: Ray3D) -> Ray3D:
        """Trace a single ray through the entire system."""

        elements = []
        if hasattr(self.system, "root"):
            nodes = self.system.root.get_flat_list()
            for node, _ in nodes:
                if getattr(node, "is_element", False):
                    transform = node.get_global_transform()
                    elements.append((node.element_model, transform))
        else:
            for elem in self.system.elements:
                t = Matrix4x4.from_translation(elem.position, 0, 0)
                elements.append((elem.lens, t))

        for lens, transform in elements:
            if ray.terminated:
                break

            tracer = LensRayTracer3D(lens, transform=transform)
            tracer.trace_ray(ray, propagate_distance=0)

        if not ray.terminated:
            ray.propagate(RAY_EXIT_PROPAGATION_3D_MM)

        return ray

    def trace_off_axis_rays(
        self,
        field_angle_deg: float,
        num_rays: int = DEFAULT_NUM_RAYS,
        wavelength_mm: float = WAVELENGTH_GREEN * NM_TO_MM,
    ) -> List[Ray3D]:
        """
        Trace a bundle of rays at a given field angle.
        Rays are distributed across the entrance pupil.
        """
        if not self.system.elements:
            return []

        first_lens = self.system.elements[0].lens
        max_r = first_lens.diameter / 2.0

        ep_x = self.system.elements[0].position
        start_x = ep_x - RAY_START_OFFSET_3D_MM

        angle_rad = math.radians(field_angle_deg)
        direction = vec3(math.cos(angle_rad), math.sin(angle_rad), 0.0)

        rays = []
        for i in range(num_rays):
            r = -max_r + 2.0 * max_r * i / (num_rays - 1) if num_rays > 1 else 0

            p_ep = vec3(ep_x, r, 0)

            t = (ep_x - start_x) / direction.x
            origin = p_ep - direction * t

            ray = Ray3D(origin, direction, wavelength=wavelength_mm)
            self.trace_ray(ray)
            rays.append(ray)

        return rays

    def trace_grid(
        self,
        size: float = 10.0,
        grid_points: int = 5,
        wavelength: float = WAVELENGTH_GREEN * NM_TO_MM,
    ) -> List[Ray3D]:
        """
        Trace a grid of parallel rays (simulating a collimated beam).
        """
        rays = []
        if not self.system.elements:
            return rays

        first_pos = self.system.elements[0].position
        start_x = first_pos - RAY_START_OFFSET_3D_MM

        half_size = size / 2
        step = size / (grid_points - 1) if grid_points > 1 else 0

        for i in range(grid_points):
            y = -half_size + i * step
            for j in range(grid_points):
                z = -half_size + j * step

                origin = vec3(start_x, y, z)
                direction = vec3(1, 0, 0)

                ray = Ray3D(origin, direction, wavelength=wavelength)
                self.trace_ray(ray)
                rays.append(ray)

        return rays
