import math
import logging
from typing import List, Tuple, Optional, Dict, Any

logger = logging.getLogger(__name__)

from ..ray_tracer import SystemRayTracer3D
from ..optical_system import OpticalSystem
from ..constants import NM_TO_MM, WAVELENGTH_GREEN
from ..fields import launch_field_ray
from ..ray_aiming import (
    DEFAULT_AIM_MAX_ITERATIONS,
    DEFAULT_AIM_TOLERANCE_MM,
    RayAimer,
    get_stop_geometry,
)
from .paraxial import resolve_image_plane_x


class SpotDiagram:
    """
    Spot Diagram Analysis Tool.
    Generates and analyzes spot diagrams for optical systems.
    """

    def __init__(self, system: OpticalSystem):
        self.system = system
        self.tracer = SystemRayTracer3D(system)

    def generate_hexapolar_grid(
        self, rings: int = 6, diameter: Optional[float] = None
    ) -> List[Tuple[float, float]]:
        """
        Generate a hexapolar grid of points in the entrance pupil.

        Args:
            rings: Number of rings in the hexapolar grid.
            diameter: Diameter of the entrance pupil. If None, uses system first lens diameter.

        Returns:
            List of (y, z) offsets from the optical axis.
        """
        if diameter is None:
            if self.system.elements:
                diameter = self.system.elements[0].lens.diameter
            else:
                return [(0.0, 0.0)]

        radius = diameter / 2.0
        points = [(0.0, 0.0)]  # Center point

        for i in range(1, rings + 1):
            num_points = 6 * i
            r = radius * (i / rings)
            for j in range(num_points):
                angle = 2 * math.pi * j / num_points
                y = r * math.cos(angle)
                z = r * math.sin(angle)
                points.append((y, z))

        return points

    def trace_spot(
        self,
        field_angle_x_deg: float = 0.0,
        field_angle_y_deg: float = 0.0,
        wavelength_nm: float = WAVELENGTH_GREEN,
        image_plane_x_mm: Optional[float] = None,
        num_rings: int = 6,
        focus_shift_mm: float = 0.0,
        object_distance_mm: Optional[float] = None,
        aim_at_stop: bool = False,
        aim_tolerance_mm: float = DEFAULT_AIM_TOLERANCE_MM,
        aim_max_iterations: int = DEFAULT_AIM_MAX_ITERATIONS,
    ) -> Dict[str, Any]:
        """
        Trace rays to generate a spot diagram.

        Args:
            field_angle_x_deg: Field angle in degrees (X-Z plane tilt)
            field_angle_y_deg: Angle in degrees relative to optical axis in XY plane.
            wavelength_nm: Wavelength in nm.
            image_plane_x_mm: Absolute X position of the image plane. If None,
                uses the system's configured plane, else the paraxial focus.
            num_rings: Sampling density.
            focus_shift_mm: Offset from the nominal image plane (defocus).
            object_distance_mm: Finite object distance in mm. None uses the
                system's setting; an unset system is collimated.
            aim_at_stop: Aim each pupil ray at its stop coordinate instead of
                the paraxial entrance-pupil point. Off preserves the historical
                bundle exactly.
            aim_tolerance_mm: Stop-hit error that counts as converged.
            aim_max_iterations: Newton iterations before using the paraxial ray.

        Returns:
            Dictionary containing spot data and statistics.
        """
        # Convert wavelength to mm
        wl_mm = wavelength_nm * NM_TO_MM
        if object_distance_mm is None:
            object_distance_mm = getattr(self.system, "object_distance_mm", None)

        # Store original states and update lenses for this wavelength
        original_states = []
        for element in self.system.elements:
            lens = element.lens
            original_states.append((lens, lens.wavelength, lens.refractive_index))
            lens.update_refractive_index(wavelength_nm=wavelength_nm)

        target_x = 0.0
        # Hoisted above the try: the statistics block below reads them, and
        # leaving the initialisation inside the try made any failure before
        # that point surface as UnboundLocalError instead of its real cause.
        spot_points = []
        valid_rays = 0

        try:
            # Determine image plane position. A stored detector plane wins;
            # otherwise the shared paraxial-focus search (#460) places it at
            # the focus, or well behind a collimated system.
            if image_plane_x_mm is None:
                image_plane_x_mm = resolve_image_plane_x(
                    self.system,
                    wavelength_nm,
                    tracer=self.tracer,
                    object_distance_mm=object_distance_mm,
                )
                if image_plane_x_mm is None:
                    image_plane_x_mm = self.system.get_total_length() + 100

            target_x = image_plane_x_mm + focus_shift_mm

            # Generate pupil points
            pupil_points = self.generate_hexapolar_grid(rings=num_rings)

            aimer = None
            aim_radius = 0.0
            entrance_radius = 0.0
            stop = get_stop_geometry(self.system) if aim_at_stop else None
            if stop is not None and self.system.elements:
                entrance_radius = self.system.elements[0].lens.diameter / 2.0
                aim_radius = stop.radius_mm
                aimer = RayAimer(
                    self.system,
                    angle_y_deg=field_angle_y_deg,
                    angle_z_deg=field_angle_x_deg,
                    object_distance_mm=object_distance_mm,
                    wavelength_mm=wl_mm,
                    tracer=self.tracer,
                    tolerance_mm=aim_tolerance_mm,
                    max_iterations=aim_max_iterations,
                )
            aim_failures = 0

            for py, pz in pupil_points:
                if aimer is not None and entrance_radius > 0:
                    scale = aim_radius / entrance_radius
                    aimed = aimer.aim(
                        py * scale,
                        pz * scale,
                        pupil_y_mm=py,
                        pupil_z_mm=pz,
                    )
                    ray = aimed.ray
                    if not aimed.converged:
                        aim_failures += 1
                else:
                    ray = launch_field_ray(
                        self.system,
                        angle_y_deg=field_angle_y_deg,
                        angle_z_deg=field_angle_x_deg,
                        pupil_y=py,
                        pupil_z=pz,
                        object_distance_mm=object_distance_mm,
                        wavelength_mm=wl_mm,
                    )
                    self.tracer.trace_ray(ray)

                if not ray.terminated:
                    # Find intersection with image plane X = target_x
                    if abs(ray.direction.x) > 1e-6:
                        t = (target_x - ray.origin.x) / ray.direction.x

                        spot_y = ray.origin.y + t * ray.direction.y
                        spot_z = ray.origin.z + t * ray.direction.z

                        spot_points.append((spot_y, spot_z))
                        valid_rays += 1

        finally:
            # Restore original states
            for lens, wl, n in original_states:
                lens.wavelength = wl
                lens.refractive_index = n

        # Reached only when the try body completed without raising. This check
        # must NOT live in finally: a return there discards any in-flight
        # exception, so a tracer failure that happened before the first spot
        # point landed was reported as a clean rms_radius of 0.0 - a tracer bug
        # masquerading as an optical result - instead of propagating.
        if valid_rays < 2:
            # Fewer than two rays cannot define a spot: the RMS radius would be
            # the distance of a single ray from its own centroid, i.e. exactly
            # 0.0. Reporting that as a perfect spot lets a fully vignetted
            # system outscore every physically real design in the optimizer
            # and score 100% production yield in Monte Carlo. None forces
            # callers to treat it as a failure instead of a great number.
            logger.warning(
                "Only %d ray(s) reached the image plane (blocked or TIR); "
                "spot statistics are undefined",
                valid_rays,
            )
            return {
                "rms_radius": None,
                "geo_radius": None,
                "centroid": (0.0, 0.0),
                "points": spot_points,
                "valid_rays": valid_rays,
                "image_plane_x": target_x,
                "aim_failures": aim_failures,
                "error": "Fewer than 2 rays reached the image plane",
            }

        # Centroid
        sum_y = sum(p[0] for p in spot_points)
        sum_z = sum(p[1] for p in spot_points)
        cent_y = sum_y / valid_rays
        cent_z = sum_z / valid_rays

        # RMS Radius (relative to centroid)
        sum_sq_dist = 0.0
        max_dist_sq = 0.0

        for y, z in spot_points:
            dy = y - cent_y
            dz = z - cent_z
            dist_sq = dy * dy + dz * dz
            sum_sq_dist += dist_sq
            if dist_sq > max_dist_sq:
                max_dist_sq = dist_sq

        rms_radius = math.sqrt(sum_sq_dist / valid_rays)
        geo_radius = math.sqrt(max_dist_sq)

        return {
            "rms_radius": rms_radius,  # mm
            "geo_radius": geo_radius,  # mm
            "centroid": (cent_y, cent_z),  # mm
            "points": spot_points,
            "valid_rays": valid_rays,
            "image_plane_x": target_x,
            "aim_failures": aim_failures,
        }

    def trace_chief_ray(
        self,
        field_angle_x_deg: float = 0.0,
        field_angle_y_deg: float = 0.0,
        wavelength_nm: float = WAVELENGTH_GREEN,
        image_plane_x_mm: Optional[float] = None,
        focus_shift_mm: float = 0.0,
        object_distance_mm: Optional[float] = None,
        aim_at_stop: bool = False,
        aim_tolerance_mm: float = DEFAULT_AIM_TOLERANCE_MM,
        aim_max_iterations: int = DEFAULT_AIM_MAX_ITERATIONS,
    ) -> Optional[Tuple[float, float]]:
        """Trace the single ray through the centre of the entrance pupil.

        Unlike the hexapolar bundle, this ray carries no coma or spherical
        aberration, so its image height is the chief-ray height that lateral
        color is defined by and does not depend on the aperture.

        Args:
            field_angle_x_deg: Field angle in the X-Z plane (degrees).
            field_angle_y_deg: Field angle in the X-Y plane (degrees).
            wavelength_nm: Wavelength in nm.
            image_plane_x_mm: Absolute X position of the image plane. If None,
                uses the system's configured plane, else the paraxial focus.
            focus_shift_mm: Offset from the nominal image plane (defocus).
            object_distance_mm: Finite object distance in mm. None uses the
                system's setting; an unset system is collimated.
            aim_at_stop: Aim the chief ray through the stop centre.
            aim_tolerance_mm: Stop-hit error that counts as converged.
            aim_max_iterations: Newton iterations before using the paraxial ray.

        Returns:
            The ``(y, z)`` intersection with the image plane, or None if the
            system is empty or the ray never reaches the plane.
        """
        if not self.system.elements:
            return None
        if object_distance_mm is None:
            object_distance_mm = getattr(self.system, "object_distance_mm", None)

        wl_mm = wavelength_nm * NM_TO_MM
        original_states = []
        for element in self.system.elements:
            lens = element.lens
            original_states.append((lens, lens.wavelength, lens.refractive_index))
            lens.update_refractive_index(wavelength_nm=wavelength_nm)

        try:
            if image_plane_x_mm is None:
                image_plane_x_mm = resolve_image_plane_x(
                    self.system,
                    wavelength_nm,
                    tracer=self.tracer,
                    object_distance_mm=object_distance_mm,
                )
                if image_plane_x_mm is None:
                    image_plane_x_mm = self.system.get_total_length() + 100
            target_x = image_plane_x_mm + focus_shift_mm

            ray = None
            stop = get_stop_geometry(self.system) if aim_at_stop else None
            if stop is not None:
                aimed = RayAimer(
                    self.system,
                    angle_y_deg=field_angle_y_deg,
                    angle_z_deg=field_angle_x_deg,
                    object_distance_mm=object_distance_mm,
                    wavelength_mm=wl_mm,
                    tracer=self.tracer,
                    tolerance_mm=aim_tolerance_mm,
                    max_iterations=aim_max_iterations,
                ).aim(0.0, 0.0)
                ray = aimed.ray
            if ray is None:
                ray = launch_field_ray(
                    self.system,
                    angle_y_deg=field_angle_y_deg,
                    angle_z_deg=field_angle_x_deg,
                    object_distance_mm=object_distance_mm,
                    wavelength_mm=wl_mm,
                )
                self.tracer.trace_ray(ray)
            if ray.terminated or abs(ray.direction.x) <= 1e-6:
                return None
            t = (target_x - ray.origin.x) / ray.direction.x
            return (
                ray.origin.y + t * ray.direction.y,
                ray.origin.z + t * ray.direction.z,
            )
        finally:
            for lens, wavelength, index in original_states:
                lens.wavelength = wavelength
                lens.refractive_index = index
