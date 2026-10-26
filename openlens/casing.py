"""Cylindrical lens casings and their thermal/optical behaviour."""

import math
from dataclasses import dataclass
from typing import Any, Dict, Optional, TYPE_CHECKING

from .constants import DEFAULT_TEMPERATURE, EPSILON
from .mechanical_materials import get_mechanical_material_catalog
from .validation import ValidationError

if TYPE_CHECKING:
    from .optical_system import OpticalSystem


@dataclass
class Casing:
    """An open-ended cylindrical shell around an element stack.

    Coordinates are the assembly's axial frame (mm), matching
    ``LensElement.position``. The shell has no end caps: light enters and
    leaves through the bore.
    """

    material: str = "Aluminium"
    bore_diameter: float = 50.0
    wall_thickness: float = 2.0
    start_x: float = 0.0
    end_x: float = 100.0
    thermal_state_temperature: float = DEFAULT_TEMPERATURE

    def __post_init__(self) -> None:
        """Validate the dimensions that do not depend on the elements."""
        for field, label in (
            ("bore_diameter", "bore diameter"),
            ("wall_thickness", "wall thickness"),
            ("start_x", "start"),
            ("end_x", "end"),
        ):
            value = getattr(self, field)
            try:
                number = float(value)
            except (TypeError, ValueError) as exc:
                raise ValidationError(f"Casing {label} must be a number") from exc
            if not math.isfinite(number):
                raise ValidationError(f"Casing {label} must be finite")
            setattr(self, field, number)
        if self.bore_diameter <= 0:
            raise ValidationError("Casing bore must be positive")
        if self.wall_thickness <= 0:
            raise ValidationError("Casing wall thickness must be positive")
        if self.end_x <= self.start_x:
            raise ValidationError("Casing must be open at both ends (end must be after start)")
        if not self.material:
            raise ValidationError("Casing material must be selected")

    @property
    def inner_radius(self) -> float:
        """Bore radius (mm)."""
        return self.bore_diameter / 2.0

    @property
    def outer_diameter(self) -> float:
        """Outside diameter (mm)."""
        return self.bore_diameter + 2.0 * self.wall_thickness

    @property
    def length(self) -> float:
        """Axial length (mm)."""
        return self.end_x - self.start_x

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the casing."""
        return {
            "material": self.material,
            "bore_diameter": self.bore_diameter,
            "wall_thickness": self.wall_thickness,
            "start_x": self.start_x,
            "end_x": self.end_x,
            "thermal_state_temperature": self.thermal_state_temperature,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Casing":
        """Deserialize a casing, tolerating missing thermal state."""
        return cls(
            material=data.get("material", "Aluminium"),
            bore_diameter=data.get("bore_diameter"),
            wall_thickness=data.get("wall_thickness"),
            start_x=data.get("start_x"),
            end_x=data.get("end_x"),
            thermal_state_temperature=data.get("thermal_state_temperature", DEFAULT_TEMPERATURE),
        )

    def expanded(self, temperature_c: float) -> "Casing":
        """Return a copy expanded from its thermal state to *temperature_c*."""
        material = get_mechanical_material_catalog().get_material(self.material)
        cte = float(material["cte"]) if material else 23.6e-6
        state = float(self.thermal_state_temperature)
        state_factor = 1.0 + cte * (state - DEFAULT_TEMPERATURE)
        target_factor = 1.0 + cte * (temperature_c - DEFAULT_TEMPERATURE)
        factor = target_factor / state_factor if abs(state_factor) > EPSILON else 1.0
        center = (self.start_x + self.end_x) / 2.0
        return Casing(
            material=self.material,
            bore_diameter=self.bore_diameter * factor,
            wall_thickness=self.wall_thickness * factor,
            start_x=center + (self.start_x - center) * factor,
            end_x=center + (self.end_x - center) * factor,
            thermal_state_temperature=temperature_c,
        )


def validate_casing(casing: Casing, system: "OpticalSystem") -> None:
    """Validate a casing against the elements it encloses.

    Raises:
        ValidationError: If the shell would intersect a lens, become the
            aperture stop, or leave less opening than an adjacent element's
            clear aperture.
    """
    elements = list(getattr(system, "elements", []) or [])
    for element in elements:
        lens = element.lens
        lens_start = float(element.position)
        lens_end = lens_start + float(lens.thickness)
        if lens_end < casing.start_x - EPSILON or lens_start > casing.end_x + EPSILON:
            continue
        aperture = max(
            float(lens.diameter),
            float(lens.get_clear_aperture_1() or 0.0),
            float(lens.get_clear_aperture_2() or 0.0),
        )
        if casing.bore_diameter < aperture - EPSILON:
            raise ValidationError(
                f"Casing bore {casing.bore_diameter:g} mm is smaller than "
                f"lens {lens.name!r} clear opening {aperture:g} mm; the "
                "casing would cut into the lens"
            )

    stop = system.get_aperture_stop() if hasattr(system, "get_aperture_stop") else None
    if stop and stop.get("diameter"):
        if casing.bore_diameter < float(stop["diameter"]) - EPSILON:
            raise ValidationError(
                "Casing bore is smaller than the aperture stop; the casing "
                "must not become the aperture stop"
            )


def casing_interference(casing: Optional[Casing], system: "OpticalSystem") -> Optional[str]:
    """Return a warning when the bore is smaller than a lens at this state."""
    if casing is None:
        return None
    elements = list(getattr(system, "elements", []) or [])
    if not elements:
        return None
    largest = max(elements, key=lambda element: float(element.lens.diameter))
    if casing.bore_diameter < float(largest.lens.diameter) - EPSILON:
        return (
            f"Mechanical interference: casing bore {casing.bore_diameter:.3f} mm "
            f"is smaller than lens {largest.lens.name!r} diameter "
            f"{largest.lens.diameter:.3f} mm at this temperature"
        )
    return None


def _axial_interval(x0: float, x1: float, start: float, end: float):
    """Return the ``t`` interval where a segment is inside ``[start, end]``."""
    dx = x1 - x0
    if abs(dx) <= EPSILON:
        return (0.0, 1.0) if start <= x0 <= end else None
    first = (start - x0) / dx
    second = (end - x0) / dx
    low, high = sorted((first, second))
    low = max(0.0, low)
    high = min(1.0, high)
    return (low, high) if low <= high + EPSILON else None


def _first_outside_entry(
    radial_a: float, radial_b: float, radial_c: float, low: float, high: float
) -> Optional[float]:
    """First ``t`` in ``[low, high]`` where a quadratic radial term is >= 0.

    The radial term is ``a t^2 + b t + c``; for a straight segment its square
    is the distance from the axis minus the bore radius squared.
    """
    if radial_a <= EPSILON:
        return low if radial_c >= -EPSILON else None
    discriminant = radial_b * radial_b - 4.0 * radial_a * radial_c
    if discriminant <= EPSILON:
        return low  # the radial distance never drops below the bore
    root = math.sqrt(discriminant)
    first = (-radial_b - root) / (2.0 * radial_a)
    second = (-radial_b + root) / (2.0 * radial_a)
    if first > second:
        first, second = second, first
    candidates = []
    if low <= min(high, first):
        candidates.append(low)
    if max(low, second) <= high:
        candidates.append(max(low, second))
    return min(candidates) if candidates else None


def wall_entry_2d(casing: Casing, start: tuple, end: tuple) -> Optional[tuple]:
    """First point where a meridional segment enters the opaque wall."""
    x0, y0 = float(start[0]), float(start[1])
    x1, y1 = float(end[0]), float(end[1])
    axial = _axial_interval(x0, x1, casing.start_x, casing.end_x)
    if axial is None:
        return None
    dy = y1 - y0
    radius = casing.inner_radius
    t = _first_outside_entry(dy * dy, 2.0 * y0 * dy, y0 * y0 - radius * radius, *axial)
    if t is None:
        return None
    return (x0 + t * (x1 - x0), y0 + t * dy)


def wall_entry_3d(casing: Casing, start: Any, end: Any) -> Optional[Any]:
    """First point where a 3D segment enters the opaque wall."""
    from .vector3 import vec3

    x0, y0, z0 = float(start.x), float(start.y), float(start.z)
    x1, y1, z1 = float(end.x), float(end.y), float(end.z)
    axial = _axial_interval(x0, x1, casing.start_x, casing.end_x)
    if axial is None:
        return None
    dy, dz = y1 - y0, z1 - z0
    radius_sq = casing.inner_radius * casing.inner_radius
    t = _first_outside_entry(
        dy * dy + dz * dz,
        2.0 * (y0 * dy + z0 * dz),
        y0 * y0 + z0 * z0 - radius_sq,
        *axial,
    )
    if t is None:
        return None
    return vec3(x0 + t * (x1 - x0), y0 + t * dy, z0 + t * dz)
