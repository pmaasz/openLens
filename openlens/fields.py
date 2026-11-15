"""Field points and finite-conjugate launching shared by the analyses.

A field is either an angle (parallel input, object at infinity) or an object
height at a finite object distance. Weights are used when several fields are
aggregated into one merit value.

The model keeps an empty list by default, which means "analysis default":
on-axis for the calculators, sensor-derived in the GUI. Existing designs keep
their infinity/single-field behaviour until a caller sets a list.
"""

import math
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

from .constants import EPSILON, NM_TO_MM, RAY_START_OFFSET_3D_MM, WAVELENGTH_GREEN

#: Metrics ``weighted_aggregate`` combines across fields. Only field-dependent
#: quantities: f-number and the pupil are design properties, not field ones.
FIELD_METRIC_KEYS = (
    "spherical",
    "coma",
    "astigmatism",
    "field_curvature",
    "distortion",
    "chromatic",
    "spot_rms",
    "strehl",
    "wfe_rms_waves",
    "mtf_cutoff",
    "airy_disk_diameter",
)


def validate_object_distance(value: Any) -> Optional[float]:
    """Return a positive finite object distance in mm, or None for infinity.

    Raises:
        ValueError: If the value is not a positive finite number. A silently
            ignored distance was the original #444 bug; a wrong number is
            worse than a refused one.
    """
    if value is None:
        return None
    try:
        distance = float(value)
    except (TypeError, ValueError):
        raise ValueError(
            f"object distance must be a positive distance in mm, got {value!r}"
        ) from None
    if not math.isfinite(distance) or distance <= 0:
        raise ValueError(f"object distance must be a positive distance in mm, got {value!r}")
    return distance


@dataclass
class FieldPoint:
    """One field sample: an angle at infinity or an object height at a distance.

    Args:
        angle_deg: Field angle in degrees, measured in the XY (tangential)
            plane from the optical axis.
        height_mm: Object height in mm for a finite-conjugate field. Mutually
            exclusive with ``angle_deg``.
        weight: Relative importance when fields are aggregated. Must be
            positive.
    """

    angle_deg: float = 0.0
    height_mm: Optional[float] = None
    weight: float = 1.0

    def __post_init__(self) -> None:
        self.angle_deg = _finite_float(self.angle_deg, "field angle")
        if self.height_mm is not None:
            self.height_mm = _finite_float(self.height_mm, "field height")
            if abs(self.angle_deg) > EPSILON:
                raise ValueError("a field has either an angle or a height, not both")
        self.weight = _finite_float(self.weight, "field weight")
        if self.weight <= 0:
            raise ValueError(f"field weight must be positive, got {self.weight!r}")

    def resolve_angle_deg(self, object_distance_mm: Optional[float]) -> float:
        """Return the field angle that reproduces this field at a distance.

        An object at height ``h`` in front of a system whose front vertex is
        the pupil centre appears at ``-atan(h / distance)``. A height without
        a finite object distance is an incomplete field, not an on-axis one.
        """
        if self.height_mm is None:
            return self.angle_deg
        distance = validate_object_distance(object_distance_mm)
        if distance is None:
            raise ValueError(f"field height {self.height_mm!r} mm needs a finite object distance")
        return -math.degrees(math.atan2(self.height_mm, distance))

    def to_dict(self) -> Dict[str, Any]:
        """Serializable form."""
        return {
            "angle_deg": self.angle_deg,
            "height_mm": self.height_mm,
            "weight": self.weight,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FieldPoint":
        """Build from a serialized field."""
        return cls(
            angle_deg=data.get("angle_deg", 0.0),
            height_mm=data.get("height_mm"),
            weight=data.get("weight", 1.0),
        )


def _finite_float(value: Any, label: str) -> float:
    """Return *value* as a finite float; raise ValueError otherwise."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label} must be a finite number, got {value!r}") from None
    if not math.isfinite(number):
        raise ValueError(f"{label} must be a finite number, got {value!r}")
    return number


def normalize_fields(fields: Optional[Iterable[Any]]) -> List[FieldPoint]:
    """Return a list of FieldPoint from model data or an API call.

    Accepts None/[], a single FieldPoint, dictionaries from JSON, or bare
    numbers (an angle in degrees). Copies the points so a caller mutating the
    returned list cannot reach into the model.
    """
    if fields is None:
        return []
    if isinstance(fields, FieldPoint):
        return [FieldPoint.from_dict(fields.to_dict())]
    points: List[FieldPoint] = []
    for item in fields:
        if isinstance(item, FieldPoint):
            points.append(FieldPoint.from_dict(item.to_dict()))
        elif isinstance(item, dict):
            points.append(FieldPoint.from_dict(item))
        else:
            points.append(FieldPoint(angle_deg=item))
    return points


def weighted_aggregate(
    metrics: List[Dict[str, Any]],
    weights: List[float],
    keys: Iterable[str] = FIELD_METRIC_KEYS,
) -> Dict[str, Optional[float]]:
    """Weighted mean of each field's metric.

    A metric that could not be measured for a field is left out of both the
    sum and the weight total, so a failed field does not drag a good one
    toward zero. All fields missing a metric yields None, not 0.0.
    """
    aggregate: Dict[str, Optional[float]] = {}
    for key in keys:
        total = 0.0
        total_weight = 0.0
        for result, weight in zip(metrics, weights):
            value = result.get(key)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                continue
            if not math.isfinite(value):
                continue
            total += float(weight) * float(value)
            total_weight += float(weight)
        aggregate[key] = total / total_weight if total_weight > 0 else None
    return aggregate


def launch_field_ray(
    system: Any,
    angle_y_deg: float = 0.0,
    angle_z_deg: float = 0.0,
    pupil_y: float = 0.0,
    pupil_z: float = 0.0,
    object_distance_mm: Optional[float] = None,
    wavelength_mm: float = WAVELENGTH_GREEN * NM_TO_MM,
    start_x: Optional[float] = None,
):
    """Build a ray for one field and one pupil point.

    At infinity the existing parallel fan is preserved: the ray is aimed at
    ``(pupil_y, pupil_z)`` on the first surface and back-propagated to
    ``start_x``. At a finite object distance every ray starts at the object
    point and is aimed at the same pupil point, which is what makes the
    conjugate real rather than a label.
    """
    from .ray import Ray3D
    from .vector3 import vec3

    if not system.elements:
        raise ValueError("cannot launch a field ray into an empty system")

    first_x = system.elements[0].position
    tan_y = math.tan(math.radians(angle_y_deg))
    tan_z = math.tan(math.radians(angle_z_deg))
    direction = vec3(1.0, tan_y, tan_z).normalize()

    distance = validate_object_distance(object_distance_mm)
    if distance is not None:
        origin = vec3(first_x - distance, -distance * tan_y, -distance * tan_z)
        target = vec3(first_x, pupil_y, pupil_z)
        aimed = target - origin
        if aimed.magnitude() > EPSILON:
            direction = aimed.normalize()
        return Ray3D(origin, direction, wavelength=wavelength_mm)

    if start_x is None:
        start_x = first_x - RAY_START_OFFSET_3D_MM
    launch_point = vec3(first_x, pupil_y, pupil_z)
    travel = (first_x - start_x) / direction.x
    origin = launch_point - direction * travel
    return Ray3D(origin, direction, wavelength=wavelength_mm)
