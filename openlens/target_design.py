"""Starting prescriptions from target specifications.

Used by the "New Lens from Target" wizard. The functions return a
feasible starting point or explain why the target cannot be met with the
chosen shape, without touching the library.
"""

import math
from dataclasses import dataclass, field
from typing import List, Optional, Union

from .constants import (
    DEFAULT_MATERIAL_INDICES,
    EPSILON,
    REFRACTIVE_INDEX_BK7,
    WAVELENGTH_D_LINE,
)
from .lens import Lens
from .optical_system import OpticalSystem

try:
    from .material_database import get_material_database as _get_material_database

    HAS_MATERIAL_DATABASE = True
except ImportError:  # pragma: no cover - environment guard
    _get_material_database = None  # type: ignore[assignment]
    HAS_MATERIAL_DATABASE = False


@dataclass
class TargetDesignResult:
    """Outcome of designing from a target.

    Attributes:
        target: A single lens or an optical system, or None if no design
            could be produced.
        warnings: Reasons the design is approximate, infeasible, or could
            not reach the target.
        merit: A small quality summary (achieved values vs target).
    """

    target: Optional[Union[Lens, OpticalSystem]] = None
    warnings: List[str] = field(default_factory=list)
    merit: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        """Whether a design object was produced."""
        return self.target is not None


def material_index(name: str, wavelength_nm: float = WAVELENGTH_D_LINE) -> float:
    """Refractive index for *name* at *wavelength_nm*, with a safe fallback."""
    if HAS_MATERIAL_DATABASE and _get_material_database is not None:
        try:
            material = _get_material_database().get_material(name)
        except Exception:
            material = None
        if material is not None:
            try:
                return float(material.get_refractive_index(wavelength_nm))  # type: ignore[attr-defined]
            except Exception:
                pass
    return float(DEFAULT_MATERIAL_INDICES.get(name, REFRACTIVE_INDEX_BK7))


def solve_symmetric_singlet(
    focal_length_mm: float,
    diameter_mm: float,
    refractive_index: float,
    thickness_mm: float,
):
    """Return (R1, R2, warning_or_None) for a symmetric thick singlet.

    Solves ``1/f = (n-1)(2/R - (n-1)t/(n R^2))`` for R with R1=R, R2=-R.
    """
    n = float(refractive_index)
    f = float(focal_length_mm)
    t = float(thickness_mm)
    if abs(f) < EPSILON:
        return None, None, "target focal length must be non-zero"
    if n <= 1.0:
        return None, None, "refractive index must be greater than 1"
    if t <= 0:
        return None, None, "thickness must be positive"
    # R^2 - 2*f*(n-1)*R + f*(n-1)^2*t/n = 0
    b = -2.0 * f * (n - 1.0)
    c = f * (n - 1.0) ** 2 * t / n
    disc = b * b - 4.0 * c
    if disc < 0:
        return None, None, "no real symmetric singlet satisfies this focal length and thickness"
    sqrt_disc = math.sqrt(disc)
    roots = sorted(((-b - sqrt_disc) / 2.0, (-b + sqrt_disc) / 2.0), key=abs, reverse=True)
    # Prefer the physically larger radius (gentler curves); fall back to the other.
    for radius in roots:
        if abs(radius) < EPSILON:
            continue
        # For a positive focal length want a biconvex shape R1>0, R2<0.
        if f > 0 and radius < 0:
            continue
        if f < 0 and radius > 0:
            continue
        return radius, -radius, None
    # No sign-correct root: return the larger-magnitude one with a warning.
    radius = roots[0] if abs(roots[0]) >= abs(roots[1]) else roots[1]
    return (
        radius,
        -radius,
        "symmetric shape has the opposite power sign; design may not match target",
    )


def design_singlet_from_target(
    focal_length_mm: float,
    f_number: Optional[float] = None,
    diameter_mm: Optional[float] = None,
    material: str = "BK7",
    wavelength_nm: float = WAVELENGTH_D_LINE,
    thickness_mm: Optional[float] = None,
    name: str = "Target Singlet",
) -> TargetDesignResult:
    """Design a symmetric singlet close to the requested target.

    Args:
        focal_length_mm: Target effective focal length in mm.
        f_number: Target f-number; used to derive diameter when needed.
        diameter_mm: Clear aperture/diameter in mm. Overrides *f_number*.
        material: Glass/catalog name.
        wavelength_nm: Design wavelength in nm.
        thickness_mm: Center thickness in mm, or None for a sensible default.
        name: Name for the resulting lens.

    Returns:
        A result containing the lens (when producible), warnings and
        achieved metrics.
    """
    result = TargetDesignResult()
    try:
        f = float(focal_length_mm)
    except (TypeError, ValueError):
        result.warnings.append("focal length must be a number")
        return result
    if not math.isfinite(f) or abs(f) < EPSILON:
        result.warnings.append("focal length must be finite and non-zero")
        return result

    if diameter_mm is not None:
        try:
            diameter = float(diameter_mm)
        except (TypeError, ValueError):
            result.warnings.append("diameter must be a number")
            return result
    elif f_number is not None:
        try:
            diameter = abs(f / float(f_number))
        except (TypeError, ValueError, ZeroDivisionError):
            result.warnings.append("f-number must be a positive number")
            return result
    else:
        diameter = max(10.0, abs(f) / 2.0)

    if not math.isfinite(diameter) or diameter <= 0:
        result.warnings.append("diameter must be positive")
        return result

    if thickness_mm is None:
        candidates = [
            max(2.0, min(diameter * 0.12, abs(f) * 0.15, diameter * 0.4)),
            max(2.0, diameter * 0.08),
            max(2.0, diameter * 0.16),
            max(2.0, diameter * 0.22),
        ]
    else:
        try:
            candidates = [float(thickness_mm)]
        except (TypeError, ValueError):
            result.warnings.append("thickness must be a number")
            return result
    candidates = [t for t in candidates if math.isfinite(t) and t > 0]
    if not candidates:
        result.warnings.append("thickness must be positive")
        return result
    n = material_index(material, wavelength_nm)
    best = None  # (score, warning, lens, achieved_f, edge, thickness)
    fallback_warning = None
    for thickness in candidates:
        r1, r2, warning = solve_symmetric_singlet(f, diameter, n, thickness)
        if r1 is None or r2 is None:
            if fallback_warning is None:
                fallback_warning = warning or "no solution"
            continue
        try:
            lens = Lens(
                name=name,
                radius_of_curvature_1=r1,
                radius_of_curvature_2=r2,
                thickness=thickness,
                diameter=diameter,
                material=material,
                refractive_index=n,
                wavelength=wavelength_nm,
            )
        except Exception as exc:
            if fallback_warning is None:
                fallback_warning = f"could not build lens: {exc}"
            continue
        achieved_f = lens.calculate_focal_length()
        edge = lens.calculate_edge_thickness()
        score = (
            0 if edge is not None and edge > 0 else 1,
            abs(achieved_f - f) if achieved_f and math.isfinite(achieved_f) else float("inf"),
            abs(thickness - candidates[0]),
        )
        if best is None or score < best[0]:
            best = (score, warning, lens, achieved_f, edge, thickness)
    if best is None:
        if fallback_warning:
            result.warnings.append(fallback_warning)
        return result
    _, warning, lens, achieved_f, edge, thickness = best
    if warning:
        result.warnings.append(warning)

    result.target = lens
    result.merit = {
        "target_focal_length_mm": f,
        "achieved_focal_length_mm": achieved_f,
        "edge_thickness_mm": edge,
        "diameter_mm": diameter,
        "f_number": abs(achieved_f) / diameter if achieved_f and diameter > 0 else None,
    }
    if achieved_f is None or not math.isfinite(achieved_f):
        result.warnings.append("the starting shape is afocal")
    elif abs(achieved_f - f) / max(abs(f), EPSILON) > 0.05:
        result.warnings.append(
            f"achieved focal length {achieved_f:.2f} mm differs from target {f:.2f} mm"
        )
    if edge is None:
        result.warnings.append("edge thickness is undefined for this geometry")
    elif edge <= 0:
        result.warnings.append("edge thickness is not positive; the surfaces intersect")
    elif edge < 0.5:
        result.warnings.append(f"edge thickness is thin ({edge:.2f} mm)")
    if thickness >= diameter:
        result.warnings.append("center thickness is unusually large for the diameter")
    return result


def design_doublet_from_target(
    focal_length_mm: float,
    diameter_mm: float,
    crown_material: str = "BK7",
    flint_material: str = "SF11",
    wavelength_nm: float = WAVELENGTH_D_LINE,
    name: str = "Target Doublet",
) -> TargetDesignResult:
    """Design a cemented achromatic doublet close to the requested target."""
    from .optical_system import AchromaticDoubletDesigner

    result = TargetDesignResult()
    try:
        f = float(focal_length_mm)
        diameter = float(diameter_mm)
    except (TypeError, ValueError):
        result.warnings.append("focal length and diameter must be numbers")
        return result
    if not math.isfinite(f) or abs(f) < EPSILON:
        result.warnings.append("focal length must be finite and non-zero")
        return result
    if not math.isfinite(diameter) or diameter <= 0:
        result.warnings.append("diameter must be positive")
        return result

    try:
        if HAS_MATERIAL_DATABASE and _get_material_database is not None:
            system = AchromaticDoubletDesigner.design_cemented_doublet(
                f, diameter, crown_material, flint_material
            )
        else:
            raise ValueError("material database unavailable")
    except Exception as exc:
        # Fallback: build from default indices so the wizard still works.
        try:
            system = _fallback_doublet(f, diameter, crown_material, flint_material, wavelength_nm)
            result.warnings.append(f"used default material data ({exc})")
        except Exception as inner:
            result.warnings.append(f"could not design doublet: {inner}")
            return result

    system.name = name
    achieved_f = system.get_system_focal_length()
    result.target = system
    result.merit = {
        "target_focal_length_mm": f,
        "achieved_focal_length_mm": achieved_f,
        "diameter_mm": diameter,
        "f_number": abs(achieved_f) / diameter if achieved_f and diameter > 0 else None,
    }
    for element in system.elements:
        edge = element.lens.calculate_edge_thickness()
        if edge is not None and edge <= 0:
            result.warnings.append(f"{element.lens.name}: edge thickness is not positive")
    if achieved_f is None or not math.isfinite(achieved_f):
        result.warnings.append("the starting doublet is afocal")
    elif abs(achieved_f - f) / max(abs(f), EPSILON) > 0.10:
        result.warnings.append(
            f"achieved focal length {achieved_f:.2f} mm differs from target {f:.2f} mm"
        )
    return result


def _fallback_doublet(
    focal_length: float,
    diameter: float,
    crown_material: str,
    flint_material: str,
    wavelength_nm: float,
) -> OpticalSystem:
    """Cemented doublet using catalog/default indices when DB is missing."""
    n1 = material_index(crown_material, wavelength_nm)
    n2 = material_index(flint_material, wavelength_nm)
    # Generic split when Abbe data is unavailable.
    v1 = 64.17 if crown_material.upper() == "BK7" else 50.0
    v2 = 25.68 if crown_material.upper() != flint_material.upper() else 30.0
    if flint_material.upper() == "SF11":
        v2 = 25.68
    if abs(v1 - v2) < EPSILON:
        f1 = focal_length * 2.0
        f2 = focal_length * 2.0
    else:
        f1 = focal_length * (v1 - v2) / v1
        f2 = focal_length * (v2 - v1) / v2
    R1_crown = 2.0 * f1 * (n1 - 1.0)
    R2_crown = -R1_crown
    R1_flint = R2_crown
    term = 1.0 / (f2 * (n2 - 1.0))
    inv_R2 = (1.0 / R1_flint) - term
    R2_flint = 1.0 / inv_R2 if abs(inv_R2) > 1e-12 else float("inf")
    crown = Lens(
        name=f"{crown_material} Element",
        radius_of_curvature_1=R1_crown,
        radius_of_curvature_2=R2_crown,
        thickness=max(1.0, diameter * 0.15),
        diameter=diameter,
        material=crown_material,
        refractive_index=n1,
        wavelength=wavelength_nm,
    )
    flint = Lens(
        name=f"{flint_material} Element",
        radius_of_curvature_1=R1_flint,
        radius_of_curvature_2=R2_flint,
        thickness=max(1.0, diameter * 0.08),
        diameter=diameter,
        material=flint_material,
        refractive_index=n2,
        wavelength=wavelength_nm,
    )
    system = OpticalSystem(name="Achromatic Doublet")
    system.add_lens(crown, air_gap_before=0.0)
    system.add_lens(flint, air_gap_before=0.0)
    return system
