#!/usr/bin/env python3
"""
Chromatic Aberration Analyzer
Performs wavelength-dependent ray tracing and dispersion analysis
"""

from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass
import logging
import math

from .constants import (
    WAVELENGTH_D_LINE,
    WAVELENGTH_C_LINE,
    WAVELENGTH_F_LINE,
    DEFAULT_DIAMETER,
    EPSILON,
)
from .material_database import MaterialDatabase

logger = logging.getLogger(__name__)

# Reference off-axis field (degrees) at which lateral color is evaluated.
# Lateral color is identically zero on the optical axis, so a documented
# small field angle is required for a meaningful number.
REFERENCE_FIELD_DEG = 5.0


def thick_lens_focal_length_mm(n: float, R1: float, R2: float, d: float) -> Optional[float]:
    """Thick-lens effective focal length in mm (single source for dict inputs).

    Mirrors ``Lens.calculate_focal_length``:
    ``1/f = (n-1)*[1/R1 - 1/R2 + (n-1)*d/(n*R1*R2)]``.
    Zero radii are treated as flat (infinite), matching the Lens setters.

    Args:
        n: Refractive index at the wavelength of interest.
        R1: First surface radius of curvature (mm).
        R2: Second surface radius of curvature (mm).
        d: Center thickness (mm).

    Returns:
        Effective focal length in mm, or None for an afocal geometry.
    """
    if R1 == 0:
        R1 = float("inf")
    if R2 == 0:
        R2 = float("inf")
    try:
        power = (n - 1) * ((1 / R1) - (1 / R2) + ((n - 1) * d) / (n * R1 * R2))
    except ZeroDivisionError:
        return None
    if abs(power) < EPSILON:
        return None
    return 1 / power


@dataclass
class ChromaticResult:
    """Results from chromatic analysis"""

    wavelengths: List[float]  # nm
    focal_lengths: List[float]  # mm
    focal_shift: float  # mm (difference between red and blue)
    lateral_color: float  # mm (at image plane)
    spot_sizes: List[float]  # mm (for each wavelength)
    transverse_aberration: List[float]  # mm
    axial_chromatic_aberration: float  # mm

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "wavelengths": self.wavelengths,
            "focal_lengths": self.focal_lengths,
            "focal_shift": self.focal_shift,
            "lateral_color": self.lateral_color,
            "spot_sizes": self.spot_sizes,
            "transverse_aberration": self.transverse_aberration,
            "axial_chromatic_aberration": self.axial_chromatic_aberration,
        }


class ChromaticAnalyzer:
    """Analyzes chromatic aberration and wavelength-dependent behavior"""

    # Standard spectral lines
    WAVELENGTHS = {
        "i": 365.0,  # Mercury i-line (UV)
        "h": 404.7,  # Mercury h-line (violet)
        "g": 435.8,  # Mercury g-line (blue)
        "F": WAVELENGTH_F_LINE,  # Hydrogen F-line (blue)
        "d": WAVELENGTH_D_LINE,  # Helium d-line (yellow) - reference
        "D": 589.3,  # Sodium D-line (yellow)
        "e": 546.1,  # Mercury e-line (green)
        "C": WAVELENGTH_C_LINE,  # Hydrogen C-line (red)
        "r": 706.5,  # Helium r-line (red)
        "s": 852.1,  # Cesium s-line (near IR)
        "t": 1014.0,  # Mercury t-line (near IR)
    }

    def __init__(self, material_db: Optional[MaterialDatabase] = None):
        self.material_db = material_db or MaterialDatabase()

    def analyze_lens(
        self,
        lens_params: dict,
        wavelengths: Optional[List[float]] = None,
        num_rays: int = 11,
        temperature_c: float = 20.0,
    ) -> ChromaticResult:
        """
        Analyze chromatic aberration for a lens.

        Focal lengths use the thick-lens lensmaker's equation evaluated with
        the wavelength-dependent index. Spot sizes are RMS spot radii from
        exact ray tracing (hexapolar pupil sampling) at each wavelength's own
        paraxial image plane, so they scale with aperture and include
        spherical aberration. Lateral color is the chief-ray image-height
        difference between the extreme wavelengths at the reference field.

        Args:
            lens_params: Dictionary with lens parameters (radius1, radius2,
                thickness, diameter, material). Missing diameter defaults to
                DEFAULT_DIAMETER.
            wavelengths: List of wavelengths in nm (defaults to F, d, C lines)
            num_rays: Approximate number of rays per spot diagram
            temperature_c: Temperature in Celsius

        Returns:
            ChromaticResult with analysis data

        Raises:
            ValueError: If the geometry is afocal (no finite focal length).
        """
        from .lens import Lens
        from .optical_system import OpticalSystem
        from .analysis.spot_diagram import SpotDiagram

        if wavelengths is None:
            # Use primary spectral lines (blue, yellow, red)
            wavelengths = [
                self.WAVELENGTHS["F"],
                self.WAVELENGTHS["d"],
                self.WAVELENGTHS["C"],
            ]

        R1 = lens_params.get("radius1", 50.0)
        R2 = lens_params.get("radius2", -50.0)
        d = lens_params.get("thickness", 5.0)
        diameter = lens_params.get("diameter", DEFAULT_DIAMETER)
        material_name = lens_params.get("material", "BK7")
        num_rings = max(1, round(math.sqrt(max(num_rays - 1, 1) / 3.0)))

        focal_lengths = []
        spot_sizes = []
        transverse_aberrations = []
        image_planes = []

        for wavelength in wavelengths:
            # Wavelength-dependent refractive index (Sellmeier + TIE-19).
            n = self.material_db.get_refractive_index(material_name, wavelength, temperature_c)

            lens = Lens(
                name=f"chromatic@{wavelength:g}nm",
                radius_of_curvature_1=R1,
                radius_of_curvature_2=R2,
                thickness=d,
                diameter=diameter,
                refractive_index=n,
                material=material_name,
                wavelength=wavelength,
                temperature=temperature_c,
            )
            focal_length = lens.calculate_focal_length()
            if focal_length is None:
                raise ValueError(
                    f"Afocal geometry (R1={R1}, R2={R2}) has no finite "
                    f"focal length; chromatic analysis is undefined."
                )

            system = OpticalSystem(name=f"chromatic@{wavelength:g}nm")
            system.add_lens(lens)
            spot = SpotDiagram(system).trace_spot(
                wavelength_nm=wavelength,
                num_rings=num_rings,
            )
            if spot.get("error") or not spot.get("valid_rays"):
                logger.warning("Spot trace failed at %.1fnm; reporting NaN", wavelength)
                spot_sizes.append(float("nan"))
                transverse_aberrations.append(float("nan"))
                image_planes.append(float("nan"))
            else:
                spot_sizes.append(spot["rms_radius"])
                transverse_aberrations.append(spot["geo_radius"])
                image_planes.append(spot["image_plane_x"])

            focal_lengths.append(focal_length)

        # Calculate chromatic aberration metrics
        focal_shift = max(focal_lengths) - min(focal_lengths)
        axial_chromatic = abs(focal_lengths[0] - focal_lengths[-1])

        # Lateral color: chief-ray image-height difference between the
        # extreme wavelengths at the reference field, evaluated at the
        # middle wavelength's image plane.
        lateral_color = self._lateral_color(
            R1,
            R2,
            d,
            diameter,
            material_name,
            wavelengths[0],
            wavelengths[-1],
            wavelengths[len(wavelengths) // 2],
            image_planes[len(wavelengths) // 2],
            temperature_c,
            num_rings,
        )

        return ChromaticResult(
            wavelengths=wavelengths,
            focal_lengths=focal_lengths,
            focal_shift=focal_shift,
            lateral_color=lateral_color,
            spot_sizes=spot_sizes,
            transverse_aberration=transverse_aberrations,
            axial_chromatic_aberration=axial_chromatic,
        )

    def _lateral_color(
        self,
        R1: float,
        R2: float,
        d: float,
        diameter: float,
        material_name: str,
        wl_first: float,
        wl_last: float,
        wl_ref: float,
        image_plane_x_mm: float,
        temperature_c: float,
        num_rings: int,
    ) -> float:
        """Chief-ray image-height difference between two wavelengths.

        Traces hexapolar bundles at REFERENCE_FIELD_DEG through lenses
        whose indices are set at each extreme wavelength, and returns the
        centroid separation at the reference image plane. Returns 0.0 for
        a single wavelength and NaN if either trace fails.
        """
        from .lens import Lens
        from .optical_system import OpticalSystem
        from .analysis.spot_diagram import SpotDiagram

        if wl_first == wl_last or not math.isfinite(image_plane_x_mm):
            return 0.0

        centroids = []
        for wavelength in (wl_first, wl_last):
            n = self.material_db.get_refractive_index(material_name, wavelength, temperature_c)
            lens = Lens(
                name=f"lateral@{wavelength:g}nm",
                radius_of_curvature_1=R1,
                radius_of_curvature_2=R2,
                thickness=d,
                diameter=diameter,
                refractive_index=n,
                material=material_name,
                wavelength=wavelength,
                temperature=temperature_c,
            )
            system = OpticalSystem(name=f"lateral@{wavelength:g}nm")
            system.add_lens(lens)
            spot = SpotDiagram(system).trace_spot(
                field_angle_y_deg=REFERENCE_FIELD_DEG,
                wavelength_nm=wavelength,
                image_plane_x_mm=image_plane_x_mm,
                num_rings=num_rings,
            )
            if spot.get("error") or not spot.get("valid_rays"):
                logger.warning(
                    "Lateral-color trace failed at %.1fnm; reporting NaN",
                    wavelength,
                )
                return float("nan")
            centroids.append(spot["centroid"])

        dy = centroids[0][0] - centroids[1][0]
        dz = centroids[0][1] - centroids[1][1]
        return math.sqrt(dy * dy + dz * dz)

    def calculate_abbe_number(self, material_name: str) -> float:
        """
        Calculate Abbe number (V_d) from material data
        V_d = (n_d - 1) / (n_F - n_C)
        """
        n_d = self.material_db.get_refractive_index(material_name, self.WAVELENGTHS["d"])
        n_F = self.material_db.get_refractive_index(material_name, self.WAVELENGTHS["F"])
        n_C = self.material_db.get_refractive_index(material_name, self.WAVELENGTHS["C"])

        return (n_d - 1.0) / (n_F - n_C)

    def calculate_partial_dispersion(
        self, material_name: str, line1: str = "g", line2: str = "F"
    ) -> float:
        """
        Calculate partial dispersion P_x,y = (n_x - n_y) / (n_F - n_C)
        """
        n_x = self.material_db.get_refractive_index(material_name, self.WAVELENGTHS[line1])
        n_y = self.material_db.get_refractive_index(material_name, self.WAVELENGTHS[line2])
        n_F = self.material_db.get_refractive_index(material_name, self.WAVELENGTHS["F"])
        n_C = self.material_db.get_refractive_index(material_name, self.WAVELENGTHS["C"])

        return (n_x - n_y) / (n_F - n_C)

    def design_achromatic_doublet(
        self,
        focal_length: float,
        crown_material: str = "BK7",
        flint_material: str = "F2",
    ) -> Dict:
        """
        Design an achromatic doublet to correct chromatic aberration

        Args:
            focal_length: Desired focal length in mm
            crown_material: Low dispersion glass (crown)
            flint_material: High dispersion glass (flint)

        Returns:
            Dictionary with lens parameters for both elements
        """
        # Get Abbe numbers
        V1 = self.calculate_abbe_number(crown_material)
        V2 = self.calculate_abbe_number(flint_material)

        # Get refractive indices at d-line
        n1 = self.material_db.get_refractive_index(crown_material, self.WAVELENGTHS["d"])
        n2 = self.material_db.get_refractive_index(flint_material, self.WAVELENGTHS["d"])

        # Calculate power distribution (thin lens approximation)
        # For achromatic doublet: φ1/V1 + φ2/V2 = 0
        # φ1 + φ2 = 1/f

        phi_total = 1.0 / focal_length
        phi1 = phi_total * V1 / (V1 - V2)
        phi2 = phi_total * V2 / (V2 - V1)

        # Focal lengths of individual elements
        f1 = 1.0 / phi1 if phi1 != 0 else float("inf")
        f2 = 1.0 / phi2 if phi2 != 0 else float("inf")

        return {
            "crown_element": {
                "focal_length": f1,
                "power": phi1,
                "material": crown_material,
                "n": n1,
                "abbe_number": V1,
            },
            "flint_element": {
                "focal_length": f2,
                "power": phi2,
                "material": flint_material,
                "n": n2,
                "abbe_number": V2,
            },
            "total_focal_length": focal_length,
            "total_power": phi_total,
        }

    def plot_chromatic_focal_shift(
        self,
        lens_params: dict,
        wavelength_range: Tuple[float, float] = (400, 700),
        num_points: int = 50,
    ) -> Dict[str, List[float]]:
        """
        Calculate focal length vs wavelength

        Returns:
            Dictionary with 'wavelengths' and 'focal_lengths' lists
            (focal length is None at any wavelength with afocal power)
        """
        wavelengths = []
        focal_lengths = []

        material_name = lens_params.get("material", "BK7")
        wl_min, wl_max = wavelength_range

        for i in range(num_points):
            wl = wl_min + (wl_max - wl_min) * i / (num_points - 1)
            n = self.material_db.get_refractive_index(material_name, wl)

            # Thick-lens lensmaker's equation (shared helper).
            R1 = lens_params.get("radius1", 50.0)
            R2 = lens_params.get("radius2", -50.0)
            d = lens_params.get("thickness", 5.0)

            focal_length = thick_lens_focal_length_mm(n, R1, R2, d)

            wavelengths.append(wl)
            focal_lengths.append(focal_length)

        return {"wavelengths": wavelengths, "focal_lengths": focal_lengths}
