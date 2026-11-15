"""Through-focus MTF and RMS-spot sweeps.

A single-plane MTF hides both depth of field and where focus actually lies.
This module evaluates a user-chosen defocus range and reports the MTF at the
requested spatial frequencies, the RMS spot at every step, and the offset
with the best mean MTF.
"""

import csv
import logging
import math
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from ..constants import WAVELENGTH_GREEN
from ..fields import normalize_fields
from .psf_mtf import ImageQualityAnalyzer

logger = logging.getLogger(__name__)


@dataclass
class FieldThroughFocus:
    """Through-focus data for one field angle."""

    field_angle_deg: float
    frequencies_lp_per_mm: List[float]
    mtf_tangential: Dict[float, List[float]] = field(default_factory=dict)
    mtf_sagittal: Dict[float, List[float]] = field(default_factory=dict)
    spot_rms_um: List[float] = field(default_factory=list)
    best_focus_mm: Optional[float] = None


@dataclass
class ThroughFocusResult:
    """One through-focus sweep."""

    defocus_mm: List[float]
    wavelength_nm: float
    fields: List[FieldThroughFocus]

    @property
    def best_focus_mm(self) -> Optional[float]:
        """Mean best-focus offset across the swept fields."""
        values = [item.best_focus_mm for item in self.fields if item.best_focus_mm is not None]
        if not values:
            return None
        return sum(values) / len(values)

    def rows(self) -> List[Dict[str, Any]]:
        """Flatten the sweep into one row per field/defocus/frequency."""
        rows = []
        for item in self.fields:
            for index, defocus in enumerate(self.defocus_mm):
                spot = item.spot_rms_um[index] if index < len(item.spot_rms_um) else float("nan")
                for frequency in item.frequencies_lp_per_mm:
                    rows.append(
                        {
                            "field_angle_deg": item.field_angle_deg,
                            "defocus_mm": defocus,
                            "wavelength_nm": self.wavelength_nm,
                            "frequency_lp_per_mm": frequency,
                            "mtf_tangential": item.mtf_tangential[frequency][index],
                            "mtf_sagittal": item.mtf_sagittal[frequency][index],
                            "spot_rms_um": spot,
                        }
                    )
        return rows

    def to_csv(self, path: str) -> None:
        """Write the flattened sweep to a CSV file."""
        columns = [
            "field_angle_deg",
            "defocus_mm",
            "wavelength_nm",
            "frequency_lp_per_mm",
            "mtf_tangential",
            "mtf_sagittal",
            "spot_rms_um",
        ]
        with open(path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns)
            writer.writeheader()
            writer.writerows(self.rows())


class ThroughFocusAnalyzer:
    """Run MTF and spot sweeps around the current image plane."""

    def __init__(self, system):
        """Create an analyzer for *system*."""
        self.system = system
        self.analyzer = ImageQualityAnalyzer(system)

    def sweep(
        self,
        defocus_start_mm: float = -0.1,
        defocus_stop_mm: float = 0.1,
        defocus_step_mm: float = 0.01,
        field_angles_deg: Optional[Iterable[float]] = None,
        frequencies_lp_per_mm: Sequence[float] = (30.0,),
        wavelength_nm: float = WAVELENGTH_GREEN,
        use_diffraction: bool = False,
        num_rings: int = 4,
    ) -> ThroughFocusResult:
        """Evaluate MTF and RMS spot at every defocus step.

        Args:
            defocus_start_mm: First focus offset, relative to the current plane.
            defocus_stop_mm: Last focus offset.
            defocus_step_mm: Spacing between offsets.
            field_angles_deg: Fields to sweep. None uses the system's field list
                (or a single on-axis field when the list is empty).
            frequencies_lp_per_mm: Spatial frequencies reported from each MTF.
            wavelength_nm: Wavelength in nm.
            use_diffraction: Use the diffraction MTF instead of the geometric one.
            num_rings: Spot sampling density for the RMS-spot curve.
        """
        defocus_values = _defocus_values(defocus_start_mm, defocus_stop_mm, defocus_step_mm)
        frequencies = _validate_frequencies(frequencies_lp_per_mm)
        fields = self._field_angles(field_angles_deg)

        result = ThroughFocusResult(
            defocus_mm=defocus_values,
            wavelength_nm=float(wavelength_nm),
            fields=[],
        )
        for angle in fields:
            item = FieldThroughFocus(
                field_angle_deg=angle,
                frequencies_lp_per_mm=list(frequencies),
            )
            for frequency in frequencies:
                item.mtf_tangential[frequency] = []
                item.mtf_sagittal[frequency] = []
            for defocus in defocus_values:
                mtf = self.analyzer.calculate_mtf(
                    field_angle_deg=angle,
                    wavelength_nm=wavelength_nm,
                    focus_shift_mm=defocus,
                    max_freq=max(frequencies),
                    use_diffraction=use_diffraction,
                )
                for frequency in frequencies:
                    item.mtf_tangential[frequency].append(
                        _interpolate(mtf.get("freq"), mtf.get("mtf_tan"), frequency)
                    )
                    item.mtf_sagittal[frequency].append(
                        _interpolate(mtf.get("freq"), mtf.get("mtf_sag"), frequency)
                    )
                spot = self.analyzer.spot_analyzer.trace_spot(
                    field_angle_y_deg=angle,
                    wavelength_nm=wavelength_nm,
                    focus_shift_mm=defocus,
                    num_rings=num_rings,
                )
                radius = spot.get("rms_radius")
                item.spot_rms_um.append(float("nan") if radius is None else float(radius) * 1000.0)
            item.best_focus_mm = _best_focus(defocus_values, item)
            result.fields.append(item)
        return result

    def _field_angles(self, field_angles_deg: Optional[Iterable[float]]) -> List[float]:
        """Resolve the requested fields, falling back to the model list."""
        if field_angles_deg is not None:
            return [float(angle) for angle in field_angles_deg]
        points = normalize_fields(getattr(self.system, "fields", None))
        if not points:
            return [0.0]
        distance = getattr(self.system, "object_distance_mm", None)
        return [point.resolve_angle_deg(distance) for point in points]


def _defocus_values(start: float, stop: float, step: float) -> List[float]:
    """Inclusive defocus grid, with the requested endpoints preserved."""
    start = float(start)
    stop = float(stop)
    step = float(step)
    if not (math.isfinite(start) and math.isfinite(stop) and math.isfinite(step)):
        raise ValueError("defocus range and step must be finite")
    if step <= 0:
        raise ValueError("defocus step must be positive")

    if start > stop:
        start, stop = stop, start
    span = stop - start
    count = int(math.floor(span / step + 1e-9))
    values = [round(start + index * step, 12) for index in range(count + 1)]
    if not values or not math.isclose(values[-1], stop, abs_tol=1e-12):
        values.append(round(stop, 12))
    return values


def _validate_frequencies(frequencies: Sequence[float]) -> Tuple[float, ...]:
    """A non-empty, positive, duplicate-free frequency list."""
    result = []
    for frequency in frequencies:
        value = float(frequency)
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f"spatial frequency must be positive, got {frequency!r}")
        if value not in result:
            result.append(value)
    if not result:
        raise ValueError("at least one spatial frequency is required")
    return tuple(result)


def _interpolate(frequencies, values, target: float) -> float:
    """Linearly interpolate an MTF profile at *target*, clamped at the ends."""
    if frequencies is None or values is None:
        return float("nan")
    try:
        count = min(len(frequencies), len(values))
    except TypeError:
        return float("nan")
    if count == 0:
        return float("nan")
    if target <= float(frequencies[0]):
        return float(values[0])
    if target >= float(frequencies[count - 1]):
        return float(values[count - 1])
    for index in range(1, count):
        upper = float(frequencies[index])
        if target <= upper:
            lower = float(frequencies[index - 1])
            if upper == lower:
                return float(values[index])
            fraction = (target - lower) / (upper - lower)
            return float(values[index - 1]) + fraction * (
                float(values[index]) - float(values[index - 1])
            )
    return float(values[count - 1])


def _best_focus(defocus_values: List[float], item: FieldThroughFocus) -> Optional[float]:
    """Defocus with the highest mean MTF, falling back to the smallest spot.

    A near diffraction-limited design has a geometrically flat MTF: every
    step reads within numerical noise of 1.0, so the peak is whatever value
    happened to round up. The RMS spot still has a clear minimum there, so
    it decides the focus when the MTF curve is flat.
    """
    best_index = None
    best_value = -math.inf
    curve = []
    for index in range(len(defocus_values)):
        values: List[float] = []
        for frequency in item.frequencies_lp_per_mm:
            values.extend(
                (
                    item.mtf_tangential[frequency][index],
                    item.mtf_sagittal[frequency][index],
                )
            )
        finite = [value for value in values if math.isfinite(value)]
        if not finite:
            continue
        mean = sum(finite) / len(finite)
        curve.append(mean)
        if mean > best_value:
            best_value = mean
            best_index = index

    if best_index is None:
        return None
    if curve and math.isclose(max(curve), min(curve), rel_tol=1e-3, abs_tol=1e-6):
        spot_focus = _smallest_spot(defocus_values, item)
        if spot_focus is not None:
            return spot_focus
    return defocus_values[best_index]


def _smallest_spot(defocus_values: List[float], item: FieldThroughFocus) -> Optional[float]:
    """Defocus where the RMS spot is smallest, or None without a finite spot."""
    best_index = None
    best_value = math.inf
    for index, radius in enumerate(item.spot_rms_um[: len(defocus_values)]):
        if math.isfinite(radius) and radius < best_value:
            best_value = radius
            best_index = index
    return None if best_index is None else defocus_values[best_index]
