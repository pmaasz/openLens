"""Build a read-only optical prescription from a lens or assembly."""

import csv
import io
import math
from typing import Dict, List, Optional, Union

from .constants import EPSILON
from .lens import Lens
from .optical_system import OpticalSystem, as_system

COLUMNS = [
    "surface",
    "radius",
    "conic_parabolic",
    "thickness",
    "material",
    "clear_semi_diameter",
    "mech_semi_diameter",
    "coating",
    "stop",
]


def _fmt_radius(radius: float) -> str:
    if radius is None or not math.isfinite(radius):
        return "Infinity"
    try:
        r = float(radius)
    except (TypeError, ValueError):
        return "Infinity"
    if not math.isfinite(r) or abs(r) > 1e9:
        return "Infinity"
    return f"{r:.6g}"


def _fmt_conic(lens: Lens, side: int) -> str:
    if getattr(lens, f"is_parabolic_{side}", False):
        sag = getattr(lens, f"parabolic_sag_{side}", 0.0)
        try:
            sag_v = float(sag)
        except (TypeError, ValueError):
            sag_v = 0.0
        if math.isfinite(sag_v) and abs(sag_v) > EPSILON:
            return f"Parabolic (sag={sag_v:.6g} mm)"
        return "Parabolic"
    conic = getattr(lens, f"conic_constant_{side}", 0.0)
    try:
        k = float(conic)
    except (TypeError, ValueError):
        k = 0.0
    if not math.isfinite(k) or abs(k) <= EPSILON:
        return "0"
    return f"{k:.6g}"


def _fmt_number(value: Optional[float]) -> str:
    if value is None:
        return ""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return ""
    if not math.isfinite(v):
        return ""
    return f"{v:.6g}"


def _semi_diameters(lens: Lens, side: int):
    clear = lens.get_clear_aperture_1() if side == 1 else lens.get_clear_aperture_2()
    mech = lens.diameter
    clear_semi = clear / 2.0 if clear is not None else None
    mech_semi = mech / 2.0 if mech is not None else None
    return clear_semi, mech_semi


def _coating(lens: Lens, side: int) -> str:
    try:
        return lens.coating_label(side)
    except Exception:
        return ""


def _image_distance(system: OpticalSystem) -> Optional[float]:
    if system.image_plane_x_mm is not None:
        try:
            return float(system.image_plane_x_mm)
        except (TypeError, ValueError):
            return None
    try:
        bfl = system.calculate_back_focal_length()
    except Exception:
        return None
    if bfl is None:
        return None
    try:
        bfl_v = float(bfl)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(bfl_v) or bfl_v < 0:
        return None
    return bfl_v


def build_prescription_rows(target: Union[Lens, OpticalSystem, None]) -> List[Dict[str, str]]:
    """Return prescription rows for *target* in display order.

    Args:
        target: A single lens or an optical system.

    Returns:
        A list of row dicts with keys from :data:`COLUMNS`. Values are
        formatted strings ready for display and CSV export.
    """
    if target is None:
        return []
    if isinstance(target, Lens):
        return _rows_for_system(as_system(target), single_lens=target)
    if isinstance(target, OpticalSystem):
        return _rows_for_system(target, single_lens=None)
    return []


def _rows_for_system(
    system: OpticalSystem, single_lens: Optional[Lens] = None
) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    stop = system.get_aperture_stop()
    stop_gap: Optional[int] = None
    stop_dia: Optional[float] = None
    stop_position: Optional[float] = None
    if stop is not None:
        stop_gap = stop.get("gap_index")
        diameter = stop.get("diameter")
        stop_dia = float(diameter) if diameter is not None else None
        position = stop.get("position")
        stop_position = float(position) if position is not None else None
    gaps = list(system.air_gaps)
    surface_no = 1
    for i, element in enumerate(system.elements):
        lens = element.lens
        # Front surface
        rows.append(
            {
                "surface": str(surface_no),
                "radius": _fmt_radius(lens.radius_of_curvature_1),
                "conic_parabolic": _fmt_conic(lens, 1),
                "thickness": _fmt_number(lens.thickness),
                "material": str(lens.material or ""),
                "clear_semi_diameter": _fmt_number(_semi_diameters(lens, 1)[0]),
                "mech_semi_diameter": _fmt_number(_semi_diameters(lens, 1)[1]),
                "coating": _coating(lens, 1),
                "stop": "",
            }
        )
        surface_no += 1

        # Back surface thickness: distance to stop, next element, or image.
        stop_remainder = None
        back_thickness: Optional[float]
        if stop_gap is not None and stop_gap == i and stop_position is not None:
            back_thickness = stop_position - (element.position + lens.thickness)
            stop_remainder = gaps[i].thickness - back_thickness
        elif i < len(gaps):
            back_thickness = gaps[i].thickness
        else:
            back_thickness = _image_distance(system)

        rows.append(
            {
                "surface": str(surface_no),
                "radius": _fmt_radius(lens.radius_of_curvature_2),
                "conic_parabolic": _fmt_conic(lens, 2),
                "thickness": _fmt_number(back_thickness),
                "material": "AIR",
                "clear_semi_diameter": _fmt_number(_semi_diameters(lens, 2)[0]),
                "mech_semi_diameter": _fmt_number(_semi_diameters(lens, 2)[1]),
                "coating": _coating(lens, 2),
                "stop": "",
            }
        )
        surface_no += 1

        if stop_remainder is not None:
            stop_semi = (stop_dia / 2.0) if stop_dia is not None else None
            rows.append(
                {
                    "surface": str(surface_no),
                    "radius": "Infinity",
                    "conic_parabolic": "0",
                    "thickness": _fmt_number(stop_remainder),
                    "material": "AIR",
                    "clear_semi_diameter": _fmt_number(stop_semi),
                    "mech_semi_diameter": _fmt_number(stop_semi),
                    "coating": "",
                    "stop": "STOP",
                }
            )
            surface_no += 1
    return rows


def rows_to_csv(rows: List[Dict[str, str]], columns: Optional[List[str]] = None) -> str:
    """Serialize prescription rows to CSV text.

    Args:
        rows: Row dicts as returned by :func:`build_prescription_rows`.
        columns: Column order; defaults to :data:`COLUMNS`.

    Returns:
        CSV text with a header row.
    """
    cols = list(columns or COLUMNS)
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({col: row.get(col, "") for col in cols})
    return buf.getvalue()
