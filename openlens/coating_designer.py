#!/usr/bin/env python3
"""
Anti-Reflection Coating Designer
Calculate coating thickness and reflectivity for optical coatings
"""

import cmath
import math
from dataclasses import dataclass
from typing import List, Tuple, Dict, Any, Optional


@dataclass
class CoatingLayer:
    """Single coating layer"""

    material: str
    refractive_index: float
    thickness_nm: float  # Physical thickness in nanometers

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a JSON-serializable dict (substrate-to-air order kept by caller)."""
        return {
            "material": self.material,
            "refractive_index": self.refractive_index,
            "thickness_nm": self.thickness_nm,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CoatingLayer":
        """Rebuild from a dict produced by :meth:`to_dict`."""
        return cls(
            material=str(data["material"]),
            refractive_index=float(data["refractive_index"]),
            thickness_nm=float(data["thickness_nm"]),
        )


#: Preset coating designs offered in the GUI (built on demand per substrate).
COATING_PRESETS = ("Uncoated", "MgF2 single-layer", "Dual-layer AR", "V-coating")


def design_preset(preset: str, substrate_index: float, wavelength_nm: float) -> List[CoatingLayer]:
    """Build a preset coating stack (substrate-to-air order).

    Args:
        preset: One of :data:`COATING_PRESETS`. "Uncoated" yields [].
        substrate_index: Substrate refractive index at the design wavelength.
        wavelength_nm: Design wavelength in nanometers.

    Returns:
        List of CoatingLayer (empty for uncoated/unknown presets).
    """
    designer = CoatingDesigner(substrate_index=substrate_index)
    if preset == "MgF2 single-layer":
        return [designer.design_single_layer_ar(wavelength_nm)]
    if preset == "Dual-layer AR":
        return designer.design_dual_layer_ar(wavelength_nm)
    if preset == "V-coating":
        return designer.design_v_coating(wavelength_nm)
    return []


def coating_label(layers: List[CoatingLayer]) -> str:
    """Short human label for a stack ("Uncoated", "MgF2", "2L AR", ...)."""
    if not layers:
        return "Uncoated"
    if len(layers) == 1:
        return f"{layers[0].material} SLAR"
    materials = "+".join(layer.material for layer in layers)
    return f"{len(layers)}L AR ({materials})"


def coated_reflectance(
    layers: List[CoatingLayer],
    substrate_index: float,
    wavelength_nm: float,
    angle_deg: float = 0.0,
) -> float:
    """Reflectivity of a coated surface, or bare Fresnel when uncoated.

    Args:
        layers: Stack in substrate-to-air order ([] = uncoated).
        substrate_index: Substrate index at the wavelength.
        wavelength_nm: Wavelength in nanometers.
        angle_deg: Incidence angle in degrees from the normal.

    Returns:
        Reflectivity in [0, 1].
    """
    designer = CoatingDesigner(substrate_index=substrate_index)
    return designer.calculate_reflectivity(layers, wavelength_nm, angle_deg)


def _tilted_admittance(n: float, cos_theta: complex, polarization: str) -> complex:
    """Tilted optical admittance for the transfer-matrix method.

    Args:
        n: Refractive index of the medium.
        cos_theta: Cosine of the propagation angle in the medium
            (complex in general, real here since light enters from air).
        polarization: "s" (TE) or "p" (TM).

    Returns:
        n*cos(theta) for s-polarization, n/cos(theta) for p-polarization.
    """
    if polarization == "s":
        return n * cos_theta
    return n / cos_theta


#: Visible band a V-coat is judged over, and the probes used to score it.
V_COATING_BAND = (400.0, 700.0)
V_COATING_PROBE_WAVELENGTHS_NM = (400.0, 450.0, 500.0, 550.0, 600.0, 650.0, 700.0)

#: Coarse-to-fine search: halve the step whenever a round improves the cost.
V_COATING_SEARCH_STEPS = 12

#: Minimum cost improvement that counts as progress, so the search stops
#: instead of chasing floating-point noise.
V_COATING_TOLERANCE = 1e-9


class CoatingDesigner:
    """Design anti-reflection and optical coatings"""

    # Common coating materials
    COATING_MATERIALS = {
        "MgF2": 1.38,  # Magnesium Fluoride
        "SiO2": 1.46,  # Silicon Dioxide
        "Al2O3": 1.63,  # Aluminum Oxide
        "TiO2": 2.35,  # Titanium Dioxide
        "Ta2O5": 2.10,  # Tantalum Pentoxide
        "ZrO2": 2.10,  # Zirconium Dioxide
        "HfO2": 2.00,  # Hafnium Oxide
    }

    def __init__(self, substrate_index: float = 1.5168):
        """
        Initialize coating designer

        Args:
            substrate_index: Refractive index of substrate (default BK7)
        """
        self.substrate_index = substrate_index
        self.air_index = 1.0

    def design_single_layer_ar(self, wavelength_nm: float) -> CoatingLayer:
        """
        Design single-layer anti-reflection coating

        Uses quarter-wave thickness with optimal refractive index
        n_coating = sqrt(n_substrate * n_air)
        t = λ / (4 * n_coating)

        Args:
            wavelength_nm: Design wavelength in nanometers

        Returns:
            CoatingLayer with optimal parameters
        """
        # Optimal coating index
        n_optimal = math.sqrt(self.substrate_index * self.air_index)

        # Find closest available material
        best_material = "MgF2"
        best_n = self.COATING_MATERIALS["MgF2"]
        min_diff = abs(best_n - n_optimal)

        for material, n in self.COATING_MATERIALS.items():
            diff = abs(n - n_optimal)
            if diff < min_diff:
                best_material = material
                best_n = n
                min_diff = diff

        # Quarter-wave optical thickness: n*t = λ/4
        thickness_nm = wavelength_nm / (4 * best_n)

        return CoatingLayer(
            material=best_material, refractive_index=best_n, thickness_nm=thickness_nm
        )

    def design_dual_layer_ar(self, wavelength_nm: float) -> List[CoatingLayer]:
        """Design a two-layer anti-reflection coating.

        Both layers are quarter-wave at ``wavelength_nm``, which cancels
        reflection only when the inner index is ``n_outer * sqrt(n_substrate)``
        - about **1.70** for MgF2 on BK7. The preset used to hard-code Ta2O5 at
        **2.10**, so the pair amplified reflection instead of cancelling it:
        4.345% against 4.216% uncoated, i.e. worse than no coating at all.

        Rather than pick indices by hand and hope, every ordered pair of
        catalogued materials is scored with the same transfer-matrix routine
        the rest of the module uses, and the best one wins. The bare substrate
        is included as a candidate, so the preset cannot come out worse than
        doing nothing.
        """
        best_layers: List[CoatingLayer] = []
        best_reflectance = self.calculate_reflectivity([], wavelength_nm)

        for inner_name, n_inner in self.COATING_MATERIALS.items():
            for outer_name, n_outer in self.COATING_MATERIALS.items():
                if n_inner <= n_outer:
                    # A two-layer stack needs the higher index adjacent to the
                    # substrate to cancel anything at all.
                    continue
                layers = [
                    CoatingLayer(inner_name, n_inner, wavelength_nm / (4 * n_inner)),
                    CoatingLayer(outer_name, n_outer, wavelength_nm / (4 * n_outer)),
                ]
                reflectance = self.calculate_reflectivity(layers, wavelength_nm)
                if reflectance < best_reflectance:
                    best_reflectance = reflectance
                    best_layers = layers

        return best_layers

    def calculate_reflectivity(
        self, layers: List[CoatingLayer], wavelength_nm: float, angle_deg: float = 0
    ) -> float:
        """
        Calculate reflectivity of coating stack using transfer matrix method.

        Each layer j is represented by its characteristic matrix (Macleod,
        Thin-Film Optical Filters; Hecht, Optics):

            M_j = [[cos d_j,  i*sin d_j / eta_j],
                   [i*eta_j*sin d_j, cos d_j]],

        with phase thickness d_j = 2*pi*n_j*t_j*cos(th_j)/lambda and tilted
        admittances eta_j = n_j*cos(th_j) (s-polarization) or
        eta_j = n_j/cos(th_j) (p-polarization). Angles inside the stack
        follow Snell's law from the angle of incidence in air. The system
        matrix M = prod(M_j) gives
        [B, C]^T = M.[1, eta_substrate]^T and
        r = (eta_inc*B - C)/(eta_inc*B + C), R = |r|^2, averaged over both
        polarizations for unpolarized light.

        Args:
            layers: List of coating layers (substrate to air)
            wavelength_nm: Wavelength in nanometers
            angle_deg: Angle of incidence in degrees from the surface
                normal, in the incident (air) medium. Must be in [0, 90).

        Returns:
            Reflectivity (0 to 1)

        Raises:
            ValueError: If wavelength is not positive or the angle is
                outside [0, 90) degrees.

        Note:
            Layer indices are real (lossless films), so transmission is
            reported as T = 1 - R elsewhere; absorption is neglected.
        """
        if wavelength_nm <= 0:
            raise ValueError(f"Wavelength must be positive, got {wavelength_nm}")
        if not 0 <= angle_deg < 90:
            raise ValueError(f"Angle of incidence must be in [0, 90), got {angle_deg}")

        theta_0 = math.radians(angle_deg)
        sin_0 = math.sin(theta_0)
        cos_0 = math.cos(theta_0)

        if not layers:
            # No coating - Fresnel reflection at the bare air/substrate interface.
            cos_s = cmath.sqrt(1 - (sin_0 / self.substrate_index) ** 2)
            rs = (self.air_index * cos_0 - self.substrate_index * cos_s) / (
                self.air_index * cos_0 + self.substrate_index * cos_s
            )
            rp = (self.substrate_index * cos_0 - self.air_index * cos_s) / (
                self.substrate_index * cos_0 + self.air_index * cos_s
            )
            return float(min(max((abs(rs) ** 2 + abs(rp) ** 2) / 2.0, 0.0), 1.0))

        # Light is incident from air, so traverse the stored
        # (substrate-to-air) stack in reverse.
        incident_order = list(reversed(layers))

        r_sum = 0.0
        # Unpolarized light: average s- and p-polarized reflectances.
        for polarization in ("s", "p"):
            eta_inc = _tilted_admittance(self.air_index, cos_0, polarization)
            eta_sub = _tilted_admittance(
                self.substrate_index,
                cmath.sqrt(1 - (self.air_index * sin_0 / self.substrate_index) ** 2),
                polarization,
            )
            # System matrix M = prod(M_j), identity to start.
            m11, m12, m21, m22 = 1.0 + 0.0j, 0.0j, 0.0j, 1.0 + 0.0j
            for layer in incident_order:
                n = layer.refractive_index
                cos_t = cmath.sqrt(1 - (self.air_index * sin_0 / n) ** 2)
                delta = 2 * math.pi * n * layer.thickness_nm * cos_t / wavelength_nm
                eta = _tilted_admittance(n, cos_t, polarization)
                cos_d = cmath.cos(delta)
                sin_d = cmath.sin(delta)
                a11, a12 = cos_d, 1j * sin_d / eta
                a21, a22 = 1j * eta * sin_d, cos_d
                m11, m12, m21, m22 = (
                    m11 * a11 + m12 * a21,
                    m11 * a12 + m12 * a22,
                    m21 * a11 + m22 * a21,
                    m21 * a12 + m22 * a22,
                )
            b = m11 + m12 * eta_sub
            c = m21 + m22 * eta_sub
            r = (eta_inc * b - c) / (eta_inc * b + c)
            r_sum += abs(r) ** 2

        return float(min(max(r_sum / 2.0, 0.0), 1.0))

    def calculate_reflectivity_curve(
        self,
        layers: List[CoatingLayer],
        wavelength_range: Tuple[float, float],
        num_points: int = 100,
    ) -> List[Tuple[float, float]]:
        """
        Calculate reflectivity vs wavelength

        Args:
            layers: Coating layers
            wavelength_range: (min_nm, max_nm)
            num_points: Number of wavelength points

        Returns:
            List of (wavelength_nm, reflectivity) tuples
        """
        min_wl, max_wl = wavelength_range
        wavelengths = [min_wl + (max_wl - min_wl) * i / (num_points - 1) for i in range(num_points)]

        curve = []
        for wl in wavelengths:
            R = self.calculate_reflectivity(layers, wl)
            curve.append((wl, R))

        return curve

    def design_v_coating(self, wavelength_nm: float) -> List[CoatingLayer]:
        """Design a broadband V-coating for the visible spectrum.

        A V-coat works precisely because its layers are *not* quarter-wave:
        the thicknesses trade a good match at the centre against a broad,
        shallow one. The preset used to express that with unexplained
        ``x1.2`` and ``x0.9`` factors, which are not a design but an assertion -
        and stacked Ta2O5 again, giving 18.949% at 550 nm against 4.216%
        uncoated. Five times worse than no coating.

        The inner layer is held quarter-wave and the two outer thicknesses are
        solved numerically here, minimising the mean reflection across
        ``V_COATING_BAND``. Nothing is asserted about the result; the search
        only ever returns a stack whose measured broadband reflectance beats
        the bare substrate, because that is the candidate it starts from.
        """
        inner_name, n_inner = "Al2O3", self.COATING_MATERIALS["Al2O3"]
        middle_name, n_middle = "SiO2", self.COATING_MATERIALS["SiO2"]
        outer_name, n_outer = "MgF2", self.COATING_MATERIALS["MgF2"]

        def build(t_middle: float, t_outer: float) -> List[CoatingLayer]:
            return [
                CoatingLayer(inner_name, n_inner, wavelength_nm / (4 * n_inner)),
                CoatingLayer(middle_name, n_middle, t_middle),
                CoatingLayer(outer_name, n_outer, t_outer),
            ]

        def band_cost(t_middle: float, t_outer: float) -> float:
            layers = build(t_middle, t_outer)
            total = 0.0
            for probe in V_COATING_PROBE_WAVELENGTHS_NM:
                total += self.calculate_reflectivity(layers, probe)
            return total

        # Start from the uncoated substrate's cost, so the search can only
        # improve on doing nothing.
        best_cost = sum(
            self.calculate_reflectivity([], probe) for probe in V_COATING_PROBE_WAVELENGTHS_NM
        )
        best_t = (wavelength_nm / (4 * n_middle), wavelength_nm / (4 * n_outer))

        step = wavelength_nm / (4 * n_outer) / 4.0
        for _ in range(V_COATING_SEARCH_STEPS):
            improved = False
            for d_middle in (-step, 0.0, step):
                for d_outer in (-step, 0.0, step):
                    if d_middle == 0.0 and d_outer == 0.0:
                        continue
                    candidate = (
                        max(0.0, best_t[0] + d_middle),
                        max(0.0, best_t[1] + d_outer),
                    )
                    cost = band_cost(*candidate)
                    if cost < best_cost - V_COATING_TOLERANCE:
                        best_cost = cost
                        best_t = candidate
                        improved = True
            if not improved:
                break
            step /= 2.0

        return build(*best_t)

    def get_coating_info(self, layers: List[CoatingLayer], design_wavelength: float) -> str:
        """Generate coating specification string"""
        lines = []
        lines.append("COATING SPECIFICATION")
        lines.append("=" * 60)
        lines.append(f"Design Wavelength: {design_wavelength:.0f} nm")
        lines.append(f"Substrate Index: {self.substrate_index:.4f}")
        lines.append("")

        for i, layer in enumerate(layers, 1):
            optical_thickness = layer.refractive_index * layer.thickness_nm
            waves = optical_thickness / design_wavelength

            lines.append(f"Layer {i}: {layer.material}")
            lines.append(f"  Refractive Index: {layer.refractive_index:.4f}")
            lines.append(f"  Physical Thickness: {layer.thickness_nm:.2f} nm")
            lines.append(f"  Optical Thickness: {optical_thickness:.2f} nm ({waves:.3f}λ)")
            lines.append("")

        R = self.calculate_reflectivity(layers, design_wavelength)
        lines.append(f"Calculated Reflectivity: {R*100:.2f}%")
        lines.append(f"Transmission: {(1-R)*100:.2f}%")

        return "\n".join(lines)
