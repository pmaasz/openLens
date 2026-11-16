"""Relative illumination and vignetting analysis.

A uniform grid of rays is launched across the entrance aperture at every
field. Rays the clear apertures or the aperture stop reject are counted as
lost, which measures the geometric vignetting directly instead of estimating
it. Throughput is normalized to the on-axis field and multiplied by the
natural :math:`\\cos^4` falloff of the traced chief ray, so the two causes of
dark corners - aperture clipping and the oblique projection of the exit pupil
- are reported separately.

Relative illumination is a fraction here (on-axis = 1.0); the table formats it
as a percentage. Values are measured at the image plane the analyses use.
"""

import math
from dataclasses import dataclass, field
from typing import Any, Iterable, List, Optional, Tuple

from ..constants import EPSILON, NM_TO_MM, WAVELENGTH_GREEN
from ..fields import FieldPoint, launch_field_ray, normalize_fields
from ..optical_system import as_system
from ..ray_tracer import SystemRayTracer3D
from .paraxial import resolve_image_plane_x

#: Samples per side of the square pupil grid clipped to the aperture circle.
#: 12 gives 113 rays, enough for a throughput fraction and still fast enough
#: for the interactive metrics report.
DEFAULT_GRID_SIZE = 12


@dataclass
class FieldIllumination:
    """Relative illumination at one field.

    Attributes:
        field_angle_deg: Field angle in the tangential (XY) plane, degrees.
        image_height_mm: Chief-ray height at the image plane, or None when
            the chief ray is blocked.
        rays_launched: Pupil samples inside the aperture circle.
        rays_through: Samples that survived every aperture and the stop.
        geometric_throughput: ``rays_through`` over the on-axis count, so the
            axis is 1.0. None when the on-axis bundle is fully blocked.
        natural_falloff: ``cos^4`` of the chief ray's angle in image space.
            None when the chief ray does not reach the image plane.
        relative_illumination: Product of the geometric throughput and the
            natural falloff, or None if either is unknown.
    """

    field_angle_deg: float
    image_height_mm: Optional[float]
    rays_launched: int
    rays_through: int
    geometric_throughput: Optional[float]
    natural_falloff: Optional[float]
    relative_illumination: Optional[float]

    @property
    def lost_fraction(self) -> Optional[float]:
        """Fraction of the launched bundle that was clipped, or None.

        This counts every lost ray, including the field-independent loss from
        a stop smaller than the entrance aperture. Compare fields through
        ``geometric_throughput`` for vignetting alone.
        """
        if not self.rays_launched:
            return None
        return 1.0 - self.rays_through / self.rays_launched


@dataclass
class RelativeIlluminationResult:
    """Per-field illumination result.

    Attributes:
        fields: One entry per requested field, in the requested order.
        wavelength_nm: Wavelength that was traced.
        image_plane_x_mm: Image plane the chief rays were measured at.
        entrance_pupil_mm: Diameter of the bundle that was actually sampled.
        on_axis_throughput: Fraction of the on-axis bundle that survived.
        warning: Human-readable reason the result is incomplete, if any.
    """

    fields: List[FieldIllumination] = field(default_factory=list)
    wavelength_nm: float = WAVELENGTH_GREEN
    image_plane_x_mm: Optional[float] = None
    entrance_pupil_mm: Optional[float] = None
    on_axis_throughput: Optional[float] = None
    warning: str = ""

    @property
    def valid(self) -> bool:
        """Whether relative illumination could be normalized to the axis."""
        return bool(self.on_axis_throughput)

    def rows(self) -> List[Tuple[float, Optional[float], Optional[float], Optional[float]]]:
        """Return ``(angle, image_height, relative, lost_fraction)`` rows."""
        return [
            (
                entry.field_angle_deg,
                entry.image_height_mm,
                entry.relative_illumination,
                entry.lost_fraction,
            )
            for entry in self.fields
        ]

    def format_table(self) -> str:
        """Human-readable per-field table for the metrics report."""
        lines = [
            "--- Relative Illumination ---",
            "Image plane: "
            + (
                f"{self.image_plane_x_mm:.3f} mm"
                if self.image_plane_x_mm is not None
                else "unavailable"
            ),
            "Relative illumination is normalized to the on-axis field "
            f"(throughput {_percent(self.on_axis_throughput)}, "
            f"pupil {_number(self.entrance_pupil_mm)} mm).",
            f"{'Angle (deg)':>12}{'Image Ht (mm)':>15}{'Relative':>11}"
            f"{'Natural':>10}{'Geometric':>11}{'Lost':>9}",
        ]
        for entry in self.fields:
            lines.append(
                f"{entry.field_angle_deg:>12.3f}"
                f"{_number(entry.image_height_mm):>15}"
                f"{_percent(entry.relative_illumination):>11}"
                f"{_percent(entry.natural_falloff):>10}"
                f"{_percent(entry.geometric_throughput):>11}"
                f"{_percent(entry.lost_fraction):>9}"
            )
        if self.warning:
            lines.append(f"Note: {self.warning}")
        return "\n".join(lines)


def _percent(value: Optional[float]) -> str:
    """Format a fraction as a percentage, or ``N/A`` when missing."""
    if value is None or not math.isfinite(value):
        return "N/A"
    return f"{value * 100.0:.1f}%"


def _number(value: Optional[float]) -> str:
    """Format a length, or ``N/A`` when missing."""
    if value is None or not math.isfinite(value):
        return "N/A"
    return f"{value:.3f}"


class RelativeIlluminationAnalyzer:
    """Trace bundles per field and measure how much light reaches the image.

    The entrance grid spans the axial entrance pupil: the largest axial
    launch height that the clear apertures and the stop pass. Sampling the
    first element's full diameter instead would weight rays that cannot exist
    and let an off-axis field report more throughput than the axis. An
    explicit ``entrance_pupil_mm`` overrides the automatic radius.

    Rays are launched at each field angle rather than aimed at the stop:
    aiming would move the bundle to fit the opening and hide the clipping
    this analysis exists to measure.

    Args:
        target: A ``Lens`` or an ``OpticalSystem``. A bare lens is wrapped,
            and its image plane, fields and object distance are kept.
    """

    def __init__(self, target: Any) -> None:
        self.system = as_system(target)
        self.tracer = SystemRayTracer3D(self.system)

    def analyze(
        self,
        fields: Optional[Iterable[Any]] = None,
        wavelength_nm: float = WAVELENGTH_GREEN,
        grid_size: int = DEFAULT_GRID_SIZE,
        object_distance_mm: Optional[float] = None,
        entrance_pupil_mm: Optional[float] = None,
    ) -> RelativeIlluminationResult:
        """Measure relative illumination at every field.

        Args:
            fields: Field angles in degrees or ``FieldPoint`` objects.
                Defaults to the model's field list, or the axis when unset.
            wavelength_nm: Wavelength to trace, in nm.
            grid_size: Samples per side of the pupil grid; at least 2.
            object_distance_mm: Finite object distance in mm. None uses the
                system's setting; an unset system is collimated.
            entrance_pupil_mm: Diameter of the bundle to sample, in mm.
                Defaults to the axial entrance pupil. A diameter larger than
                the optics is sampled as requested, so the loss is reported.

        Returns:
            The per-field result. A field whose chief ray is blocked still
            appears, with an unknown natural falloff rather than a zero.

        Raises:
            ValueError: If the system has no elements, ``grid_size`` is too
                small to sample an aperture, or ``entrance_pupil_mm`` is not
                a positive number.
        """
        if not self.system.elements:
            raise ValueError("relative illumination needs at least one optical element")
        if grid_size < 2:
            raise ValueError(f"grid_size must be at least 2, got {grid_size!r}")

        if object_distance_mm is None:
            object_distance_mm = getattr(self.system, "object_distance_mm", None)
        model_fields = fields if fields is not None else getattr(self.system, "fields", None)
        field_points = normalize_fields(model_fields)
        if not field_points:
            field_points = [FieldPoint()]

        grid = _pupil_grid(grid_size)
        image_plane = resolve_image_plane_x(
            self.system,
            wavelength_nm,
            tracer=self.tracer,
            object_distance_mm=object_distance_mm,
        )
        wavelength_mm = wavelength_nm * NM_TO_MM

        original_states = []
        for element in self.system.elements:
            lens = element.lens
            original_states.append((lens, lens.wavelength, lens.refractive_index))
            lens.update_refractive_index(wavelength_nm=wavelength_nm)

        result = RelativeIlluminationResult(
            wavelength_nm=wavelength_nm, image_plane_x_mm=image_plane
        )
        try:
            radius = (
                self._requested_radius(entrance_pupil_mm)
                if entrance_pupil_mm is not None
                else self._axial_pupil_radius(object_distance_mm, wavelength_mm)
            )
            result.entrance_pupil_mm = 2.0 * radius
            on_axis_through, _ = self._bundle(0.0, radius, grid, object_distance_mm, wavelength_mm)
            result.on_axis_throughput = on_axis_through / len(grid)
            if on_axis_through == 0:
                result.warning = (
                    "the on-axis bundle is fully blocked; relative illumination is undefined"
                )
            for point in field_points:
                angle = point.resolve_angle_deg(object_distance_mm)
                rays_through, chief = self._bundle(
                    angle, radius, grid, object_distance_mm, wavelength_mm
                )
                natural = _natural_falloff(chief)
                geometric = rays_through / on_axis_through if on_axis_through else None
                relative = (
                    geometric * natural if geometric is not None and natural is not None else None
                )
                result.fields.append(
                    FieldIllumination(
                        field_angle_deg=angle,
                        image_height_mm=_image_height(chief, image_plane),
                        rays_launched=len(grid),
                        rays_through=rays_through,
                        geometric_throughput=geometric,
                        natural_falloff=natural,
                        relative_illumination=relative,
                    )
                )
        finally:
            for lens, wavelength, refractive_index in original_states:
                lens.wavelength = wavelength
                lens.refractive_index = refractive_index
        return result

    def _first_clear_radius(self) -> float:
        """Half the first element's clear aperture, in mm."""
        lens = self.system.elements[0].lens
        getter = getattr(lens, "get_clear_aperture_1", None)
        diameter = getter() if callable(getter) else lens.diameter
        return float(diameter or lens.diameter) / 2.0

    def _requested_radius(self, entrance_pupil_mm: float) -> float:
        """Validate an explicit pupil diameter and return its radius."""
        try:
            diameter = float(entrance_pupil_mm)
        except (TypeError, ValueError):
            raise ValueError(
                f"entrance pupil must be a positive diameter in mm, " f"got {entrance_pupil_mm!r}"
            ) from None
        if not math.isfinite(diameter) or diameter <= 0:
            raise ValueError(
                f"entrance pupil must be a positive diameter in mm, " f"got {entrance_pupil_mm!r}"
            )
        return diameter / 2.0

    def _axial_pupil_radius(
        self, object_distance_mm: Optional[float], wavelength_mm: float
    ) -> float:
        """Largest axial launch height that still reaches the image.

        The first clear aperture is only an upper bound. Where the stop or a
        later surface clips the axial bundle the real entrance pupil is
        smaller, and normalising against the clipped rays would let an
        off-axis field report more than 100% of the axis.
        """

        def passes(radius: float) -> bool:
            return not self._trace(0.0, radius, 0.0, object_distance_mm, wavelength_mm).terminated

        limit = self._first_clear_radius()
        if passes(limit):
            return limit
        if not passes(0.0):
            # The axis itself is blocked; keep the full grid so the warning
            # names the real problem instead of a collapsed pupil.
            return limit
        low, high = 0.0, limit
        for _ in range(20):
            middle = 0.5 * (low + high)
            if passes(middle):
                low = middle
            else:
                high = middle
        return low if low > 0 else limit

    def _trace(
        self,
        angle_deg: float,
        pupil_y: float,
        pupil_z: float,
        object_distance_mm: Optional[float],
        wavelength_mm: float,
    ) -> Any:
        """Launch and trace one ray for this system and wavelength."""
        ray = launch_field_ray(
            self.system,
            angle_y_deg=angle_deg,
            pupil_y=pupil_y,
            pupil_z=pupil_z,
            object_distance_mm=object_distance_mm,
            wavelength_mm=wavelength_mm,
        )
        self.tracer.trace_ray(ray)
        return ray

    def _bundle(
        self,
        angle_deg: float,
        radius: float,
        grid: List[Tuple[float, float]],
        object_distance_mm: Optional[float],
        wavelength_mm: float,
    ) -> Tuple[int, Any]:
        """Trace one field's bundle; return survivors and the chief ray."""
        through = 0
        for pupil_y, pupil_z in grid:
            ray = self._trace(
                angle_deg,
                pupil_y * radius,
                pupil_z * radius,
                object_distance_mm,
                wavelength_mm,
            )
            if not ray.terminated:
                through += 1

        chief = self._trace(angle_deg, 0.0, 0.0, object_distance_mm, wavelength_mm)
        return through, chief


def _pupil_grid(size: int) -> List[Tuple[float, float]]:
    """Return unit-disc pupil points from a ``size`` x ``size`` square grid."""
    step = 2.0 / size
    points = []
    for row in range(size):
        y = -1.0 + (row + 0.5) * step
        for column in range(size):
            z = -1.0 + (column + 0.5) * step
            if y * y + z * z <= 1.0:
                points.append((y, z))
    return points


def _natural_falloff(chief) -> Optional[float]:
    """``cos^4`` of the chief ray's image-space angle, or None if blocked."""
    if chief.terminated or chief.direction.x <= EPSILON:
        return None
    return chief.direction.x**4


def _image_height(chief, image_plane_x_mm: Optional[float]) -> Optional[float]:
    """Chief-ray height at the image plane, or None when the ray is blocked."""
    if chief.terminated:
        return None
    point = chief.origin
    if image_plane_x_mm is not None and chief.direction.x > EPSILON:
        distance = (image_plane_x_mm - chief.origin.x) / chief.direction.x
        if distance >= 0:
            point = chief.origin + chief.direction * distance
    return math.hypot(point.y, point.z)
