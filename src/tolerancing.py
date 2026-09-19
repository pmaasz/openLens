import logging
import enum
import random
import copy
import math
import statistics
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

from .optical_system import OpticalSystem
from .analysis import SpotDiagram
from .vector3 import vec3

logger = logging.getLogger(__name__)


def _percentile(values: List[float], pct: float) -> float:
    """Percentile by linear interpolation (numpy 'linear' method).

    Avoids statistics.quantiles (absent on Python 3.7) and the off-by-one
    of indexing int(p * N) without interpolation. pct in [0, 100].
    """
    ordered = sorted(values)
    if not ordered:
        raise ValueError("percentile of empty data")
    if len(ordered) == 1:
        return ordered[0]
    rank = (pct / 100.0) * (len(ordered) - 1)
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    frac = rank - low
    return ordered[low] * (1.0 - frac) + ordered[high] * frac


class ToleranceType(enum.Enum):
    """Toleranced parameter. Native units per type (used as-is, no conversion).

    RADIUS_1/2 (mm), THICKNESS (mm), REFRACTIVE_INDEX (absolute),
    DECENTER_X/Y (mm; X is axial despace realized as the gap before the
    element), TILT_X/Y (deg), AIR_GAP (mm; gap after the element),
    ABBE_NUMBER (absolute), IRREGULARITY (fringes at 632.8 nm, power-
    equivalent radius change at the surface semi-aperture), WEDGE (arcmin,
    thin-element approximation as element tilt of half the wedge),
    FOCUS (mm image-plane shift; compensator-only, never randomized).
    """

    RADIUS_1 = "Radius 1"
    RADIUS_2 = "Radius 2"
    THICKNESS = "Thickness"
    REFRACTIVE_INDEX = "Refractive Index"
    DECENTER_X = "Decenter X"
    DECENTER_Y = "Decenter Y"
    TILT_X = "Tilt X"
    TILT_Y = "Tilt Y"
    DECENTER_Z = "Decenter Z"
    AIR_GAP = "Air Gap"
    ABBE_NUMBER = "Abbe Number"
    IRREGULARITY = "Surface Irregularity"
    WEDGE = "Wedge"
    FOCUS = "Focus"


#: Fringe-to-sag conversion (reflection, HeNe 632.8 nm): PV surface sag
#: per fringe in mm.
FRINGE_SAG_MM = 632.8e-6 / 2


@dataclass
class ToleranceOperand:
    """
    Defines a tolerance on a specific parameter of an element.
    """

    element_index: int  # Index in the flattened element list (0-based)
    param_type: ToleranceType
    min_val: float  # Minimum deviation (e.g. -0.1 mm)
    max_val: float  # Maximum deviation (e.g. +0.1 mm)
    distribution: str = "uniform"  # "uniform" or "gaussian"
    std_dev: float = (
        0.0  # Standard deviation for Gaussian (if 0, assumes sigma is roughly (max-min)/6 ?)
    )
    surface: int = 1  # Surface the operand acts on where applicable (1 or 2)

    def generate_value(self) -> float:
        """Generate a random deviation value based on distribution."""
        if self.distribution == "gaussian":
            # If std_dev is not provided, assume range is +/- 3 sigma
            sigma = self.std_dev
            if sigma == 0:
                sigma = (self.max_val - self.min_val) / 6.0

            val = random.gauss(0, sigma)
            # Clamp to limits? Typically yes for manufacturing
            return max(self.min_val, min(self.max_val, val))
        else:
            # Uniform
            return random.uniform(self.min_val, self.max_val)


def _capture_state(system: OpticalSystem) -> Dict[str, Any]:
    """Capture node transforms, lens params, and air-gap thicknesses."""
    nodes = system.root.get_flat_list()
    node_states = []
    for node, _ in nodes:
        entry: Dict[str, Any] = {
            "position": vec3(node.position.x, node.position.y, node.position.z),
            "rotation": vec3(node.rotation.x, node.rotation.y, node.rotation.z),
        }
        if getattr(node, "is_element", False):
            lens = getattr(node, "element_model", None)
            if lens:
                entry["lens"] = {
                    "r1": lens.radius_of_curvature_1,
                    "r2": lens.radius_of_curvature_2,
                    "thickness": lens.thickness,
                    "nd": (lens.model_nd if lens.model_glass_mode else lens.refractive_index),
                    "vd": lens.model_vd if lens.model_glass_mode else 0,
                    "glass_mode": lens.model_glass_mode,
                }
        node_states.append(entry)
    return {
        "nodes": node_states,
        "gaps": [float(g.thickness) for g in system.air_gaps],
    }


def _restore_state(system: OpticalSystem, state: Dict[str, Any]) -> None:
    """Restore a state captured by :func:`_capture_state`."""
    nodes = system.root.get_flat_list()
    for i, (node, _) in enumerate(nodes):
        if i >= len(state["nodes"]):
            break
        entry = state["nodes"][i]
        node.position = vec3(
            entry["position"].x,
            entry["position"].y,
            entry["position"].z,
        )
        node.rotation = vec3(
            entry["rotation"].x,
            entry["rotation"].y,
            entry["rotation"].z,
        )
        if "lens" in entry and getattr(node, "is_element", False):
            lens = getattr(node, "element_model", None)
            if lens:
                ls = entry["lens"]
                lens.radius_of_curvature_1 = ls["r1"]
                lens.radius_of_curvature_2 = ls["r2"]
                lens.thickness = ls["thickness"]
                lens.model_glass_mode = ls["glass_mode"]
                if lens.model_glass_mode:
                    lens.model_nd = ls["nd"]
                    lens.model_vd = ls["vd"]
                lens.update_refractive_index()
    for gap, thickness in zip(system.air_gaps, state.get("gaps", [])):
        gap.thickness = thickness
    system._update_positions()


def _spherical_sag(R: float, h: float) -> Optional[float]:
    """Vertex sag of a spherical surface (None when undefined there)."""
    if not math.isfinite(R) or abs(R) < 1e-12 or abs(h) > abs(R):
        return None
    magnitude = abs(R) - math.sqrt(max(0.0, R * R - h * h))
    return magnitude if R > 0 else -magnitude


def _radius_for_fringes(R: float, h: float, fringes: float) -> Optional[float]:
    """Radius giving an extra sag of ``fringes`` (PV) at height ``h``.

    Power-equivalent approximation for sensitivity budgeting: the sag
    change stands in for the fringe error. Returns None for flat or
    overhanging geometry.
    """
    import math as _math

    if not _math.isfinite(R) or abs(R) < 1e-12 or h <= 0:
        return None
    base = _spherical_sag(R, h)
    if base is None:
        return None
    target = base + fringes * FRINGE_SAG_MM
    span = 0.5 * abs(R)
    lo, hi = (R - span, R + span) if R > 0 else (R - span, R + span)
    f_lo = _spherical_sag(lo, h)
    f_hi = _spherical_sag(hi, h)
    if f_lo is None or f_hi is None:
        return None
    # Sag falls as |R| grows; bracket the root accordingly.
    if R > 0:
        lo, hi = R - span, R  # sag rises toward target
        flo = _spherical_sag(lo, h)
        fhi = base
    else:
        lo, hi = R, R + span
        flo = base
        fhi = _spherical_sag(hi, h)
    if flo is None or fhi is None:
        return None
    if not min(flo, fhi) <= target <= max(flo, fhi):
        return None
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        fmid = _spherical_sag(mid, h)
        if fmid is None:
            return None
        if (fmid <= target) == (flo <= target):
            lo, flo = mid, fmid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def _apply_value(
    system: OpticalSystem,
    param_type: ToleranceType,
    element_index: int,
    value: float,
    surface: int = 1,
) -> bool:
    """Apply one perturbation; shared by random and compensator paths.

    Returns False when the operand addresses nothing (out of range,
    FOCUS which lives in evaluation, or unrepresentable geometry).
    """
    if param_type == ToleranceType.FOCUS:
        return False
    nodes = system.root.get_flat_list()
    element_nodes = [n for n, _ in nodes if getattr(n, "is_element", False)]
    if not 0 <= element_index < len(element_nodes):
        return False
    node = element_nodes[element_index]
    lens = getattr(node, "element_model", None)
    if lens is None:
        return False

    if param_type == ToleranceType.RADIUS_1:
        lens.radius_of_curvature_1 += value
    elif param_type == ToleranceType.RADIUS_2:
        lens.radius_of_curvature_2 += value
    elif param_type == ToleranceType.THICKNESS:
        lens.thickness += value
    elif param_type == ToleranceType.REFRACTIVE_INDEX:
        _ensure_model_glass(lens)
        lens.model_nd += value
        lens.update_refractive_index()
    elif param_type == ToleranceType.ABBE_NUMBER:
        _ensure_model_glass(lens)
        lens.model_vd += value
        lens.update_refractive_index()
    elif param_type == ToleranceType.DECENTER_X:
        # Axial despace realized as the gap before the element.
        if element_index <= 0 or element_index - 1 >= len(system.air_gaps):
            return False
        system.air_gaps[element_index - 1].thickness += value
    elif param_type == ToleranceType.DECENTER_Y:
        node.position.y += value
    elif param_type == ToleranceType.DECENTER_Z:
        node.position.z += value
    elif param_type == ToleranceType.TILT_X:
        node.rotation.x += value
    elif param_type == ToleranceType.TILT_Y:
        node.rotation.y += value
    elif param_type == ToleranceType.AIR_GAP:
        # Gap after the element.
        if element_index >= len(system.air_gaps):
            return False
        system.air_gaps[element_index].thickness += value
    elif param_type == ToleranceType.WEDGE:
        # Arcmin element wedge: thin-element approximation as half-wedge
        # whole-element tilt about x.
        node.rotation.x += value / 120.0
    elif param_type == ToleranceType.IRREGULARITY:
        radius = (
            lens.radius_of_curvature_1 if surface == 1 else lens.radius_of_curvature_2
        )
        getter = (
            getattr(lens, "get_clear_aperture_1", None)
            if surface == 1
            else getattr(lens, "get_clear_aperture_2", None)
        )
        try:
            semi = float(getter()) / 2 if callable(getter) else lens.diameter / 2
        except (TypeError, ValueError):
            semi = lens.diameter / 2
        new_radius = _radius_for_fringes(radius, semi, value)
        if new_radius is None:
            return False
        if surface == 1:
            lens.radius_of_curvature_1 = new_radius
        else:
            lens.radius_of_curvature_2 = new_radius
    else:
        return False

    system._update_positions()
    return True


def _ensure_model_glass(lens) -> None:
    """Switch a lens to model-glass mode, seeding nd/Vd from material."""
    if lens.model_glass_mode:
        return
    lens.model_glass_mode = True
    lens.model_nd = lens.refractive_index
    try:
        from .material_database import get_material_database

        mat = get_material_database().get_material(lens.material)
        if mat:
            lens.model_vd = mat.vd
    except Exception as e:
        logger.debug("Material DB lookup for Vd failed: %s", e)


class MonteCarloAnalyzer:
    """
    Performs Monte Carlo analysis to estimate production yield.
    Compensators (``compensators``) are operands used as adjustables rather
    than random variables: after each trial's tolerances are applied, every
    compensator is re-optimized within [min_val, max_val] to minimize the
    criterion. FOCUS compensators shift the image plane (no system change);
    all other types move the system itself.
    """

    def __init__(
        self,
        system: OpticalSystem,
        tolerances: List[ToleranceOperand],
        seed: Optional[int] = None,
        compensators: Optional[List[ToleranceOperand]] = None,
        comp_sweeps: int = 1,
    ):
        self.nominal_system = system
        self.tolerances = tolerances
        self.compensators = list(compensators) if compensators else []
        self.comp_sweeps = max(1, comp_sweeps)
        self.results: List[Dict[str, Any]] = []
        if seed is not None:
            random.seed(seed)

    def _get_system_state(self, system: OpticalSystem) -> Dict[str, Any]:
        """Get a capture of the current system parameters for restoration."""
        return _capture_state(system)

    def _set_system_state(self, system: OpticalSystem, state: Dict[str, Any]):
        """Restore system to a previously captured state."""
        _restore_state(system, state)

    def _apply_tolerances(self, system: OpticalSystem) -> Dict[str, float]:
        """
        Apply random tolerances to the system and return the applied values.
        """
        perturbations = {}

        for tol in self.tolerances:
            delta = tol.generate_value()
            perturbations[f"El_{tol.element_index}_{tol.param_type.name}"] = delta
            _apply_value(
                system, tol.param_type, tol.element_index, delta, surface=tol.surface
            )

        # Positions/gaps already synced per application; one final sync.
        system._update_positions()

        return perturbations

    def _spot_rms(self, focus_shift_mm: float = 0.0) -> float:
        """RMS spot radius at an optional image-plane shift (inf on failure)."""
        try:
            spot = SpotDiagram(self.nominal_system)
            return float(spot.trace_spot(focus_shift_mm=focus_shift_mm)["rms_radius"])
        except Exception as e:
            logger.debug("Spot evaluation failed: %s", e)
            return float("inf")

    def _optimize_compensators(self) -> Dict[str, Any]:
        """Re-optimize compensators for the current perturbed trial.

        FOCUS compensators shift the image plane (golden-section search,
        no system change); mechanical compensators are coordinate-descended
        within their ranges. Leaves the system at the compensated state.
        """
        values: Dict[str, Any] = {"focus_shift_mm": 0.0}
        if not self.compensators:
            return values
        focus_ops = [c for c in self.compensators if c.param_type == ToleranceType.FOCUS]
        mech_ops = [c for c in self.compensators if c.param_type != ToleranceType.FOCUS]
        trial_state = _capture_state(self.nominal_system)
        try:
            if focus_ops:
                lo = min(c.min_val for c in focus_ops)
                hi = max(c.max_val for c in focus_ops)
                best_shift, _ = _golden(self._spot_rms, lo, hi)
                values["focus_shift_mm"] = best_shift
            for _ in range(self.comp_sweeps):
                for comp in mech_ops:
                    def trial_rms(v, _c=comp):
                        _restore_state(self.nominal_system, trial_state)
                        _apply_value(
                            self.nominal_system,
                            _c.param_type,
                            _c.element_index,
                            v,
                            surface=_c.surface,
                        )
                        return self._spot_rms(values["focus_shift_mm"])

                    best_v, _ = _golden(trial_rms, comp.min_val, comp.max_val)
                    values[f"El_{comp.element_index}_{comp.param_type.name}"] = best_v
            # Leave the system compensated for the trial evaluation.
            _restore_state(self.nominal_system, trial_state)
            for comp in mech_ops:
                key = f"El_{comp.element_index}_{comp.param_type.name}"
                if key in values:
                    _apply_value(
                        self.nominal_system,
                        comp.param_type,
                        comp.element_index,
                        values[key],
                        surface=comp.surface,
                    )
        except Exception as e:
            logger.debug("Compensator optimization failed: %s", e)
            _restore_state(self.nominal_system, trial_state)
        return values

    def run(
        self,
        num_trials: int = 100,
        criterion: str = "rms_spot_radius",
        criterion_limit: float = 0.05,
    ) -> Dict[str, Any]:
        """
        Run Monte Carlo simulation.

        Args:
            num_trials: Number of systems to simulate.
            criterion: Metric to evaluate ('rms_spot_radius').
            criterion_limit: Pass/Fail threshold.

        Returns:
            Dictionary with statistics and yield.
        """
        self.results = []
        pass_count = 0

        # Analyze nominal system first
        spot_nom = SpotDiagram(self.nominal_system)
        res_nom = spot_nom.trace_spot()
        nominal_val = res_nom["rms_radius"]

        # Save nominal state for restoration instead of deepcopying
        nominal_state = self._get_system_state(self.nominal_system)

        for i in range(num_trials):
            # Apply tolerances directly to the system
            perturbations = self._apply_tolerances(self.nominal_system)

            # Re-optimize compensators (focus and/or mechanical adjusts).
            comp_values = self._optimize_compensators()

            # Analyze
            spot = SpotDiagram(self.nominal_system)
            results = spot.trace_spot(
                focus_shift_mm=comp_values.get("focus_shift_mm", 0.0)
            )

            val = results["rms_radius"]
            passed = val <= criterion_limit
            if passed:
                pass_count += 1

            self.results.append(
                {
                    "trial": i,
                    "perturbations": perturbations,
                    "compensators": comp_values,
                    "value": val,
                    "passed": passed,
                }
            )

            # Restore nominal state
            self._set_system_state(self.nominal_system, nominal_state)

        # Statistics
        values = [r["value"] for r in self.results]
        yield_pct = (pass_count / num_trials) * 100

        stats = {
            "nominal": nominal_val,
            "mean": statistics.mean(values) if values else 0,
            "std_dev": statistics.stdev(values) if len(values) > 1 else 0,
            "min": min(values) if values else 0,
            "max": max(values) if values else 0,
            "yield": yield_pct,
            "trials": num_trials,
            "criterion": criterion,
            "limit": criterion_limit,
            "90th_percentile": _percentile(values, 90.0) if values else 0,
        }

        return stats


class InverseSensitivityAnalyzer:
    """
    Calculates required tolerances to achieve a target performance.
    """

    def __init__(self, system: OpticalSystem, tolerances: List[ToleranceOperand]):
        self.system = system
        self.tolerances = tolerances

    def _get_system_state(self, system: OpticalSystem) -> Dict[str, Any]:
        """Get a capture of the current system parameters for restoration."""
        return _capture_state(system)

    def _set_system_state(self, system: OpticalSystem, state: Dict[str, Any]):
        """Restore system to a previously captured state."""
        _restore_state(system, state)

    def calculate_sensitivities(self, criterion: str = "rms_spot_radius") -> List[Dict[str, Any]]:
        """
        Calculate sensitivity of each operand.
        Returns list of dicts with 'operand', 'sensitivity', 'change'.
        """
        results = []

        # Nominal performance
        spot_nom = SpotDiagram(self.system)
        res_nom = spot_nom.trace_spot()
        nominal_val = res_nom["rms_radius"]

        for i, tol in enumerate(self.tolerances):
            # Test at max value
            # Apply single tolerance at max value
            delta = tol.max_val

            # Save state
            original_state = self._get_system_state(self.system)

            self._apply_single_tolerance(self.system, tol, delta)

            # Analyze
            spot = SpotDiagram(self.system)
            res = spot.trace_spot()
            val = res["rms_radius"]

            # Restore state
            self._set_system_state(self.system, original_state)

            change = val - nominal_val
            # Sensitivity = change / tolerance_value
            sensitivity = change / delta if delta != 0 else 0

            results.append(
                {
                    "operand_index": i,
                    "type": tol.param_type.name,
                    "element": tol.element_index,
                    "test_value": delta,
                    "result_value": val,
                    "change": change,
                    "sensitivity": sensitivity,
                }
            )

        return results

    def _apply_single_tolerance(self, system: OpticalSystem, tol: ToleranceOperand, value: float):
        """Helper to apply a single tolerance value."""
        _apply_value(system, tol.param_type, tol.element_index, value, surface=tol.surface)

    def _get_system_state(self, system: OpticalSystem) -> Dict[str, Any]:
        """Get a capture of the current system parameters for restoration."""
        return _capture_state(system)

    def _set_system_state(self, system: OpticalSystem, state: Dict[str, Any]):
        """Restore system to a previously captured state."""
        _restore_state(system, state)

    def optimize_limits(
        self, target_yield_criterion: float, method: str = "rss"
    ) -> List[ToleranceOperand]:
        """
        Calculate new tolerance limits to meet a target performance degradation budget.

        Args:
            target_yield_criterion: The allowed degradation from nominal (e.g. +0.01 rms spot).
            method: 'rss' (Root Sum Square) or 'worst_case' (Linear Sum).

        Returns:
            List of new ToleranceOperand with updated min/max.
        """
        sensitivities = self.calculate_sensitivities()
        new_tolerances = []

        num_vars = len(self.tolerances)
        if num_vars == 0:
            return []

        # Allocate budget per operand
        if method == "rss":
            # Budget per operand = Total / sqrt(N)
            # This assumes all operands contribute equally to the variance
            budget_per_op = target_yield_criterion / math.sqrt(num_vars)
        else:
            # Worst case: Budget / N
            budget_per_op = target_yield_criterion / num_vars

        for i, sens_data in enumerate(sensitivities):
            original_tol = self.tolerances[i]
            s = abs(sens_data["sensitivity"])

            if s < 1e-9:
                # Insensitive parameter, keep original or even loosen?
                # For safety, keep original.
                new_limit = original_tol.max_val
            else:
                # Limit = Budget / Sensitivity
                new_limit = budget_per_op / s

            # Create new operand
            new_tol = copy.deepcopy(original_tol)
            new_tol.max_val = new_limit
            new_tol.min_val = -new_limit  # Assuming symmetric tolerances for simplicity

            new_tolerances.append(new_tol)

        return new_tolerances


def _golden(func, lo: float, hi: float, iters: int = 12):
    """Golden-section minimum of func on [lo, hi]; returns (x, f(x))."""
    if not lo < hi:
        x = lo
        return x, func(x)
    inv_phi = (math.sqrt(5.0) - 1.0) / 2
    a, b = lo, hi
    c = b - inv_phi * (b - a)
    d = a + inv_phi * (b - a)
    fc, fd = func(c), func(d)
    for _ in range(iters):
        if fc < fd:
            b, fd = d, fc
            d = c
            c = b - inv_phi * (b - a)
            fc = func(c)
        else:
            a, fc = c, fd
            c = d
            d = a + inv_phi * (b - a)
            fd = func(d)
    x = 0.5 * (a + b)
    return x, func(x)


#: Standard tolerance grades (shop capabilities). Radius/thickness/gaps in
#: mm, tilts in arcmin (converted to degrees by the builder), index/Abbe
#: absolute, irregularity in fringes at 632.8 nm, wedge in arcmin.
TOLERANCE_GRADES: Dict[str, Dict[str, float]] = {
    "Commercial": {
        "radius": 0.5,
        "thickness": 0.1,
        "index": 0.001,
        "abbe": 0.5,
        "decenter": 0.05,
        "tilt_arcmin": 3.0,
        "airgap": 0.1,
        "irregularity_fringes": 1.0,
        "wedge_arcmin": 3.0,
    },
    "Precision": {
        "radius": 0.1,
        "thickness": 0.02,
        "index": 0.0005,
        "abbe": 0.2,
        "decenter": 0.01,
        "tilt_arcmin": 1.0,
        "airgap": 0.02,
        "irregularity_fringes": 0.25,
        "wedge_arcmin": 1.0,
    },
    "High Precision": {
        "radius": 0.02,
        "thickness": 0.005,
        "index": 0.0002,
        "abbe": 0.1,
        "decenter": 0.005,
        "tilt_arcmin": 0.5,
        "airgap": 0.005,
        "irregularity_fringes": 0.1,
        "wedge_arcmin": 0.5,
    },
}


def tolerances_for_system(
    system: OpticalSystem,
    grade: str = "Precision",
    distribution: str = "uniform",
) -> List[ToleranceOperand]:
    """Build a full tolerance set for a system from a shop grade.

    Emits per-element radius/thickness/index/Abbe/decenter/tilt/
    irregularity/wedge operands plus one AIR_GAP operand per gap.
    (Axial despace is covered once via AIR_GAP; see DECENTER_X docs.)

    Args:
        system: Optical system to tolerance.
        grade: One of "Commercial", "Precision", "High Precision".
        distribution: "uniform" or "gaussian" for every operand.

    Raises:
        ValueError: For an unknown grade.
    """
    if grade not in TOLERANCE_GRADES:
        raise ValueError(
            f"Unknown tolerance grade '{grade}'. Choose from {sorted(TOLERANCE_GRADES)}"
        )
    g = TOLERANCE_GRADES[grade]
    tilt_deg = g["tilt_arcmin"] / 60.0
    operands: List[ToleranceOperand] = []
    for i in range(len(system.elements)):
        operands.append(
            ToleranceOperand(i, ToleranceType.RADIUS_1, -g["radius"], g["radius"], distribution)
        )
        operands.append(
            ToleranceOperand(i, ToleranceType.RADIUS_2, -g["radius"], g["radius"], distribution)
        )
        operands.append(
            ToleranceOperand(
                i, ToleranceType.THICKNESS, -g["thickness"], g["thickness"], distribution
            )
        )
        operands.append(
            ToleranceOperand(
                i, ToleranceType.REFRACTIVE_INDEX, -g["index"], g["index"], distribution
            )
        )
        operands.append(
            ToleranceOperand(i, ToleranceType.ABBE_NUMBER, -g["abbe"], g["abbe"], distribution)
        )
        operands.append(
            ToleranceOperand(
                i, ToleranceType.DECENTER_Y, -g["decenter"], g["decenter"], distribution
            )
        )
        operands.append(
            ToleranceOperand(
                i, ToleranceType.DECENTER_Z, -g["decenter"], g["decenter"], distribution
            )
        )
        operands.append(
            ToleranceOperand(i, ToleranceType.TILT_X, -tilt_deg, tilt_deg, distribution)
        )
        operands.append(
            ToleranceOperand(i, ToleranceType.TILT_Y, -tilt_deg, tilt_deg, distribution)
        )
        operands.append(
            ToleranceOperand(
                i,
                ToleranceType.IRREGULARITY,
                -g["irregularity_fringes"],
                g["irregularity_fringes"],
                distribution,
                surface=1,
            )
        )
        operands.append(
            ToleranceOperand(
                i,
                ToleranceType.IRREGULARITY,
                -g["irregularity_fringes"],
                g["irregularity_fringes"],
                distribution,
                surface=2,
            )
        )
        operands.append(
            ToleranceOperand(
                i,
                ToleranceType.WEDGE,
                -g["wedge_arcmin"],
                g["wedge_arcmin"],
                distribution,
            )
        )
    for i in range(len(system.air_gaps)):
        operands.append(
            ToleranceOperand(i, ToleranceType.AIR_GAP, -g["airgap"], g["airgap"], distribution)
        )
    return operands


def generate_yield_report(stats: Dict[str, Any]) -> str:
    """Generate a text report from Monte Carlo stats."""
    lines = []
    lines.append("=== Monte Carlo Yield Analysis ===")
    lines.append(f"Criterion: {stats['criterion']}")
    lines.append(f"Pass/Fail Limit: {stats['limit']}")
    lines.append(f"Number of Trials: {stats['trials']}")
    lines.append("-" * 30)
    lines.append(f"Nominal Performance: {stats['nominal']:.4f}")
    lines.append(f"Mean Performance:    {stats['mean']:.4f}")
    lines.append(f"Std Dev:             {stats['std_dev']:.4f}")
    lines.append(f"90th Percentile:     {stats['90th_percentile']:.4f}")
    lines.append(f"Worst Case (Max):    {stats['max']:.4f}")
    lines.append("-" * 30)
    lines.append(f"ESTIMATED YIELD:     {stats['yield']:.1f}%")
    lines.append("==================================")
    return "\n".join(lines)
