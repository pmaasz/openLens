"""Iterative ray aiming at the aperture stop.

An off-axis bundle launched on a paraxial entrance-pupil grid is not the
bundle the stop actually passes: a wide-angle chief ray enters off-centre and
the stop clips one side. Ray aiming solves for the launch point that makes a
ray cross the stop at a requested coordinate, so the sampled pupil is the real
one. The paraxial launch is the initial guess and the fallback.
"""

import logging
import math
from dataclasses import dataclass
from typing import Any, Optional, Tuple

from .constants import EPSILON, NM_TO_MM, WAVELENGTH_GREEN
from .fields import launch_field_ray
from .ray_tracer import SystemRayTracer3D

logger = logging.getLogger(__name__)

#: Stop-hit error that counts as converged, in mm (1 nm).
DEFAULT_AIM_TOLERANCE_MM = 1e-6

#: Newton iterations before falling back to the paraxial launch.
DEFAULT_AIM_MAX_ITERATIONS = 12

#: Finite-difference step for the 2x2 Jacobian, as a fraction of the pupil radius.
_AIM_JACOBIAN_FRACTION = 1e-3


@dataclass(frozen=True)
class StopGeometry:
    """The aperture stop's plane and clear radius."""

    x_mm: float
    radius_mm: float
    gap_index: int


@dataclass
class RayAimResult:
    """One aimed ray and how it was obtained."""

    ray: Any
    target_y_mm: float
    target_z_mm: float
    stop_y_mm: Optional[float] = None
    stop_z_mm: Optional[float] = None
    error_mm: Optional[float] = None
    converged: bool = False
    iterations: int = 0
    fallback: bool = False


def get_stop_geometry(system) -> Optional[StopGeometry]:
    """Return the validated stop plane and radius, or None if unset."""
    stop = None
    getter = getattr(system, "get_aperture_stop", None)
    if callable(getter):
        stop = getter()
    if not stop:
        return None
    diameter = stop.get("diameter")
    position = stop.get("position")
    if not diameter or diameter <= 0 or position is None:
        return None
    return StopGeometry(
        x_mm=float(position),
        radius_mm=float(diameter) / 2.0,
        gap_index=int(stop["gap_index"]),
    )


class RayAimer:
    """Solve for first-surface launch points that hit the stop on target."""

    def __init__(
        self,
        system,
        angle_y_deg: float = 0.0,
        angle_z_deg: float = 0.0,
        object_distance_mm: Optional[float] = None,
        wavelength_mm: float = WAVELENGTH_GREEN * NM_TO_MM,
        tracer: Optional[SystemRayTracer3D] = None,
        tolerance_mm: float = DEFAULT_AIM_TOLERANCE_MM,
        max_iterations: int = DEFAULT_AIM_MAX_ITERATIONS,
    ) -> None:
        """Create an aimer for one field and wavelength.

        Args:
            system: Optical system to aim through.
            angle_y_deg: Field angle in the X-Y plane, degrees.
            angle_z_deg: Field angle in the X-Z plane, degrees.
            object_distance_mm: Finite object distance in mm. None uses the
                system's setting; an unset system is collimated.
            wavelength_mm: Wavelength in mm.
            tracer: Optional tracer sharing the caller's prepared scene.
            tolerance_mm: Stop-hit error that counts as converged.
            max_iterations: Newton iterations before falling back.

        Raises:
            ValueError: If the tolerance is not positive or the iteration
                limit is not positive.
        """
        if tolerance_mm <= 0 or not math.isfinite(tolerance_mm):
            raise ValueError("aim tolerance must be positive and finite")
        if max_iterations <= 0:
            raise ValueError("aim max_iterations must be positive")
        self.system = system
        self.angle_y_deg = float(angle_y_deg)
        self.angle_z_deg = float(angle_z_deg)
        if object_distance_mm is None:
            object_distance_mm = getattr(system, "object_distance_mm", None)
        self.object_distance_mm = object_distance_mm
        self.wavelength_mm = float(wavelength_mm)
        self.tracer = tracer or SystemRayTracer3D(system)
        self.tolerance_mm = float(tolerance_mm)
        self.max_iterations = int(max_iterations)
        self.stop = get_stop_geometry(system)
        self.first_radius_mm = (
            system.elements[0].lens.diameter / 2.0 if getattr(system, "elements", None) else 0.0
        )

    def aim(
        self,
        stop_y_mm: float,
        stop_z_mm: float,
        pupil_y_mm: Optional[float] = None,
        pupil_z_mm: Optional[float] = None,
    ) -> RayAimResult:
        """Return the traced ray that crosses the stop at ``(stop_y_mm, stop_z_mm)``.

        A system without a defined stop has nothing to aim at, so the
        paraxial launch is traced and returned unchanged and is reported as
        converged.

        Args:
            stop_y_mm: Target stop height, mm from the axis.
            stop_z_mm: Target stop height in the sagittal direction, mm.
            pupil_y_mm: Optional initial first-surface height. Default scales
                the stop target by the entrance-pupil radius / stop radius.
            pupil_z_mm: Optional initial sagittal height, same scaling.
        """
        target_y = float(stop_y_mm)
        target_z = float(stop_z_mm)
        stop = self.stop
        if stop is None:
            ray = self._launch(target_y * self._initial_scale(), target_z * self._initial_scale())
            self.tracer.trace_ray(ray)
            return RayAimResult(
                ray=ray,
                target_y_mm=target_y,
                target_z_mm=target_z,
                converged=True,
                fallback=True,
            )

        scale = self._initial_scale()
        guess = (
            target_y * scale if pupil_y_mm is None else float(pupil_y_mm),
            target_z * scale if pupil_z_mm is None else float(pupil_z_mm),
        )
        fallback_ray = self._launch(*guess)
        self.tracer.trace_ray(fallback_ray)
        fallback_hit = stop_plane_crossing(fallback_ray, stop.x_mm)
        fallback_error = _distance(fallback_hit, target_y, target_z)

        pupil_y, pupil_z = guess
        for iteration in range(1, self.max_iterations + 1):
            ray = self._launch(pupil_y, pupil_z)
            self.tracer.trace_ray(ray)
            hit = stop_plane_crossing(ray, stop.x_mm)
            if hit is None:
                break
            error = _distance(hit, target_y, target_z) or 0.0
            if error <= self.tolerance_mm:
                return RayAimResult(
                    ray=ray,
                    target_y_mm=target_y,
                    target_z_mm=target_z,
                    stop_y_mm=hit[0],
                    stop_z_mm=hit[1],
                    error_mm=error,
                    converged=True,
                    iterations=iteration,
                )
            if iteration == self.max_iterations:
                break

            jacobian = self._jacobian(pupil_y, pupil_z, hit, stop.x_mm)
            if jacobian is None:
                break
            step_y, step_z = _solve_step(jacobian, target_y - hit[0], target_z - hit[1])
            if step_y is None or step_z is None:
                break

            limit = max(2.0 * max(self.first_radius_mm, stop.radius_mm), 1.0)
            pupil_y, pupil_z = _bounded_step(pupil_y, pupil_z, step_y, step_z, limit)
            if not (math.isfinite(pupil_y) and math.isfinite(pupil_z)):
                break

        return RayAimResult(
            ray=fallback_ray,
            target_y_mm=target_y,
            target_z_mm=target_z,
            stop_y_mm=None if fallback_hit is None else fallback_hit[0],
            stop_z_mm=None if fallback_hit is None else fallback_hit[1],
            error_mm=fallback_error,
            converged=False,
            iterations=self.max_iterations,
            fallback=True,
        )

    def _launch(self, pupil_y_mm: float, pupil_z_mm: float):
        """Build one ray at the requested first-surface point."""
        return launch_field_ray(
            self.system,
            angle_y_deg=self.angle_y_deg,
            angle_z_deg=self.angle_z_deg,
            pupil_y=pupil_y_mm,
            pupil_z=pupil_z_mm,
            object_distance_mm=self.object_distance_mm,
            wavelength_mm=self.wavelength_mm,
        )

    def _initial_scale(self) -> float:
        """Entrance-pupil radius over stop radius, for the initial guess."""
        if self.stop is None or self.stop.radius_mm <= 0:
            return 1.0
        return self.first_radius_mm / self.stop.radius_mm

    def _jacobian(
        self, pupil_y: float, pupil_z: float, hit: Tuple[float, float], stop_x_mm: float
    ) -> Optional[Tuple[float, float, float, float]]:
        """Finite-difference d(stop hit)/d(first-surface launch point)."""
        step = max(_AIM_JACOBIAN_FRACTION * self.first_radius_mm, 1e-5)
        columns = []
        for axis in (0, 1):
            point = [pupil_y, pupil_z]
            point[axis] += step
            ray = self._launch(*point)
            self.tracer.trace_ray(ray)
            shifted = stop_plane_crossing(ray, stop_x_mm)
            direction = 1.0
            if shifted is None:
                # At the rim the outward probe leaves the clear aperture;
                # probe inward instead so the boundary still has a Jacobian.
                point[axis] -= 2.0 * step
                ray = self._launch(*point)
                self.tracer.trace_ray(ray)
                shifted = stop_plane_crossing(ray, stop_x_mm)
                direction = -1.0
            if shifted is None:
                return None
            columns.append(
                (
                    (shifted[0] - hit[0]) / (direction * step),
                    (shifted[1] - hit[1]) / (direction * step),
                )
            )
        return (
            columns[0][0],
            columns[1][0],
            columns[0][1],
            columns[1][1],
        )


def stop_plane_crossing(ray, stop_x_mm: float) -> Optional[Tuple[float, float]]:
    """The ``(y, z)`` where a traced ray crosses the stop plane, or None."""
    path = getattr(ray, "path", None) or []
    for first, second in zip(path, path[1:]):
        dx = second.x - first.x
        if abs(dx) < EPSILON:
            continue
        if (first.x - stop_x_mm) * (second.x - stop_x_mm) <= 0:
            fraction = (stop_x_mm - first.x) / dx
            return (
                first.y + fraction * (second.y - first.y),
                first.z + fraction * (second.z - first.z),
            )

    if path and abs(path[-1].x - stop_x_mm) <= 1e-7:
        return (path[-1].y, path[-1].z)
    return None


def _distance(
    hit: Optional[Tuple[float, float]], target_y: float, target_z: float
) -> Optional[float]:
    """Euclidean distance from a stop hit to the target, or None."""
    if hit is None:
        return None
    return math.hypot(hit[0] - target_y, hit[1] - target_z)


def _solve_step(
    jacobian: Tuple[float, float, float, float], delta_y: float, delta_z: float
) -> Tuple[Optional[float], Optional[float]]:
    """Solve the 2x2 Newton system, or return ``(None, None)`` if singular."""
    a, b, c, d = jacobian
    determinant = a * d - b * c
    if not math.isfinite(determinant) or abs(determinant) < 1e-12:
        return None, None
    step_y = (delta_y * d - delta_z * b) / determinant
    step_z = (delta_z * a - delta_y * c) / determinant
    return step_y, step_z


def _bounded_step(
    pupil_y: float, pupil_z: float, step_y: float, step_z: float, limit: float
) -> Tuple[float, float]:
    """Apply a Newton step, clamped to ``limit`` so a bad Jacobian cannot run away."""
    length = math.hypot(step_y, step_z)
    if length > limit and length > 0:
        factor = limit / length
        step_y *= factor
        step_z *= factor
    return pupil_y + step_y, pupil_z + step_z
