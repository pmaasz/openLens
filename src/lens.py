from datetime import datetime
from typing import Optional, Dict, Any
import logging
import math
import sqlite3
import uuid

logger = logging.getLogger(__name__)

#: Exceptions the material-database layer can realistically raise for
#: corrupt Sellmeier data or storage faults (unknown materials do NOT
#: raise - they return defaults).
_MATERIAL_DB_ERRORS = (ArithmeticError, ValueError, KeyError, sqlite3.Error)

from .constants import (
    DEFAULT_RADIUS_1, DEFAULT_RADIUS_2, DEFAULT_THICKNESS, DEFAULT_DIAMETER,
    REFRACTIVE_INDEX_BK7, EPSILON, LARGE_NUMBER,
    LENS_TYPE_BICONVEX, LENS_TYPE_PRESET_RADII
)

# Material database is an optional dependency
try:
    from .material_database import get_material_database
    MATERIAL_DB_AVAILABLE = True
except ImportError:
    MATERIAL_DB_AVAILABLE = False


class Lens:
    """
    Represents an optical lens with its physical and optical properties.
    Shared model between CLI and GUI.
    """
    
    def __init__(self, 
                 name: str = "Untitled",
                 radius_of_curvature_1: float = DEFAULT_RADIUS_1,
                 radius_of_curvature_2: float = DEFAULT_RADIUS_2,
                 thickness: float = DEFAULT_THICKNESS,
                 diameter: float = DEFAULT_DIAMETER,
                 refractive_index: Optional[float] = None,
                 lens_type: str = "Biconvex",
                 material: str = "BK7",
                 wavelength_nm: float = 587.6,
                 wavelength: Optional[float] = None,
                 temperature: float = 20.0,
                 is_fresnel: bool = False,
                 groove_pitch: float = DEFAULT_THICKNESS,
                 num_grooves: Optional[int] = None,
                 model_glass_mode: bool = False,
                 model_nd: float = 1.5168,
                 model_vd: float = 64.17) -> None:
        
        self.id = uuid.uuid4().hex
        self.name = name
        self.radius_of_curvature_1 = radius_of_curvature_1
        self.radius_of_curvature_2 = radius_of_curvature_2
        self.thickness = thickness
        self.diameter = diameter
        self.material = material
        self.wavelength = wavelength if wavelength is not None else wavelength_nm  # Design wavelength in nm
        self.temperature = temperature  # Operating temperature in °C
        
        # Model Glass Properties
        self.model_glass_mode = model_glass_mode
        self.model_nd = model_nd
        self.model_vd = model_vd

        # Refractive index resolution order:
        #   1. Explicit refractive_index argument wins (honours caller
        #      intent and keeps serialization round-trips exact).
        #   2. Model-glass mode computes it from nd/vd.
        #   3. Material database lookup for known materials.
        #   4. BK7 default constant.
        # The DB layer returns defaults for unknown materials; a raised
        # exception means corrupt Sellmeier data or a storage fault -
        # log it loudly and fall back to the BK7 constant.
        if refractive_index is not None:
            self.refractive_index = float(refractive_index)
        elif self.model_glass_mode and MATERIAL_DB_AVAILABLE:
            try:
                db = get_material_database()
                if hasattr(db, 'calculate_model_index'):
                    self.refractive_index = db.calculate_model_index(
                        self.model_nd, self.model_vd, self.wavelength)
                else:
                    logger.warning(
                        "material DB lacks calculate_model_index; "
                        "using model index %.4f for %s",
                        self.model_nd, self.model_nd)
                    self.refractive_index = self.model_nd
            except _MATERIAL_DB_ERRORS as e:
                logger.warning(
                    "Model-glass index lookup failed (nd=%.4f vd=%.2f wl=%snm):"
                    " %s - using model index",
                    self.model_nd, self.model_vd, self.wavelength, e)
                self.refractive_index = self.model_nd
        elif MATERIAL_DB_AVAILABLE:
            try:
                db = get_material_database()
                mat = db.get_material(material)
                if mat:
                    # Use the resolved design wavelength (the raw parameter
                    # defaults to None when wavelength_nm was given).
                    self.refractive_index = db.get_refractive_index(
                        material, self.wavelength, temperature)
                else:
                    logger.warning(
                        "material %r not in database - using BK7 default",
                        material)
                    self.refractive_index = REFRACTIVE_INDEX_BK7
            except _MATERIAL_DB_ERRORS as e:
                logger.warning(
                    "Material lookup failed for %s @ %snm/%sC: %s - "
                    "using BK7 default",
                    material, self.wavelength, temperature, e)
                self.refractive_index = REFRACTIVE_INDEX_BK7
        else:
            self.refractive_index = REFRACTIVE_INDEX_BK7
            
        self.lens_type = lens_type

        # Apply the lens_type radius preset only when radii are still at
        # their defaults; this preserves custom radii while letting
        # lens_type choose sensible starting geometry.
        self._apply_type_preset_if_needed()
        
        # Fresnel properties
        self.is_fresnel = is_fresnel
        self.groove_pitch = groove_pitch
        self.num_grooves = num_grooves
        
        self.created_at = datetime.now().isoformat()
        self.modified_at = datetime.now().isoformat()
        
        # Auto-calculate number of grooves if not provided and is fresnel
        if self.is_fresnel and self.num_grooves is None:
            self.calculate_num_grooves()
    
    @property
    def radius_of_curvature_1(self) -> float:
        return self._radius_of_curvature_1
    
    @radius_of_curvature_1.setter
    def radius_of_curvature_1(self, value: float) -> None:
        if value == 0:
            self._radius_of_curvature_1 = float('inf')
        else:
            self._radius_of_curvature_1 = value
    
    @property
    def radius_of_curvature_2(self) -> float:
        return self._radius_of_curvature_2
    
    @radius_of_curvature_2.setter
    def radius_of_curvature_2(self, value: float) -> None:
        if value == 0:
            self._radius_of_curvature_2 = float('inf')
        else:
            self._radius_of_curvature_2 = value
    
    def update_refractive_index(self, 
                                 wavelength_nm: Optional[float] = None,
                                 temperature: Optional[float] = None) -> None:
        """
        Update refractive index for new wavelength/temperature.
        """
        if wavelength_nm is not None:
            self.wavelength = wavelength_nm
        if temperature is not None:
            self.temperature = temperature
        
        if self.model_glass_mode and MATERIAL_DB_AVAILABLE:
            try:
                db = get_material_database()
                if hasattr(db, 'calculate_model_index'):
                    self.refractive_index = db.calculate_model_index(
                        self.model_nd, self.model_vd, self.wavelength
                    )
                else:
                    logger.warning(
                        "material DB lacks calculate_model_index; "
                        "keeping model index %.4f", self.model_nd)
                    self.refractive_index = self.model_nd
            except _MATERIAL_DB_ERRORS as e:
                logger.warning(
                    "Model-glass index update failed (wl=%snm): %s - "
                    "keeping model index",
                    self.wavelength, e)
        elif MATERIAL_DB_AVAILABLE:
            try:
                db = get_material_database()
                self.refractive_index = db.get_refractive_index(
                    self.material, self.wavelength, self.temperature
                )
            except _MATERIAL_DB_ERRORS as e:
                logger.warning(
                    "Material index update failed for %s @ %snm/%sC: %s - "
                    "keeping previous index %.4f",
                    self.material, self.wavelength, self.temperature, e,
                    self.refractive_index)
    
    def calculate_num_grooves(self) -> None:
        """Calculate the number of grooves based on diameter and pitch"""
        if self.groove_pitch > 0:
            self.num_grooves = int((self.diameter / 2) / self.groove_pitch)
        else:
            self.num_grooves = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert lens to dictionary representation."""
        return {
            "id": self.id,
            "name": self.name,
            "radius_of_curvature_1": self.radius_of_curvature_1,
            "radius_of_curvature_2": self.radius_of_curvature_2,
            "thickness": self.thickness,
            "diameter": self.diameter,
            "refractive_index": self.refractive_index,
            "type": self.lens_type,
            "material": self.material,
            "wavelength": self.wavelength,
            "temperature": self.temperature,
            "is_fresnel": self.is_fresnel,
            "groove_pitch": self.groove_pitch,
            "num_grooves": self.num_grooves,
            "model_glass_mode": self.model_glass_mode,
            "model_nd": self.model_nd,
            "model_vd": self.model_vd,
            "created_at": self.created_at,
            "modified_at": self.modified_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Lens':
        """Create lens from dictionary representation."""
        r1 = data.get("radius_of_curvature_1", DEFAULT_RADIUS_1)
        r2 = data.get("radius_of_curvature_2", DEFAULT_RADIUS_2)
        lens_type = data.get("type", "Biconvex")
        
        lens = cls(
            name=data.get("name", "Untitled"),
            radius_of_curvature_1=r1,
            radius_of_curvature_2=r2,
            thickness=data.get("thickness", DEFAULT_THICKNESS),
            diameter=data.get("diameter", DEFAULT_DIAMETER),
            refractive_index=data.get("refractive_index", REFRACTIVE_INDEX_BK7),
            lens_type=lens_type,
            material=data.get("material", "BK7"),
            wavelength_nm=data.get("wavelength_nm", data.get("wavelength", 587.6)),
            temperature=data.get("temperature", 20.0),
            is_fresnel=data.get("is_fresnel", False),
            groove_pitch=data.get("groove_pitch", DEFAULT_THICKNESS),
            num_grooves=data.get("num_grooves", None),
            model_glass_mode=data.get("model_glass_mode", False),
            model_nd=data.get("model_nd", 1.5168),
            model_vd=data.get("model_vd", 64.17)
        )

        lens.id = data.get("id", lens.id)
        lens.created_at = data.get("created_at", lens.created_at)
        lens.modified_at = data.get("modified_at", lens.modified_at)
        return lens
    
    def calculate_focal_length(self) -> Optional[float]:
        """
        Calculate focal length using the lensmaker's equation.

        Flat surfaces (radius = inf, as produced by the property setters
        for a 0 radius) contribute 1/R = 0 to the power.
        """
        n = self.refractive_index
        R1 = self.radius_of_curvature_1
        R2 = self.radius_of_curvature_2
        d = self.thickness

        # Lensmaker's equation: 1/f = (n-1)[1/R1 - 1/R2 + (n-1)d/(nR1R2)]
        try:
            power = (n - 1) * ((1/R1) - (1/R2) + ((n - 1) * d) / (n * R1 * R2))

            if abs(power) < EPSILON:
                return None

            return 1 / power
        except ZeroDivisionError:
            return None
    
    def _apply_type_preset_if_needed(self) -> None:
        """Apply the lens_type radius preset if radii are still at defaults."""
        if (self.radius_of_curvature_1 == DEFAULT_RADIUS_1 and
                self.radius_of_curvature_2 == DEFAULT_RADIUS_2 and
                self.lens_type != LENS_TYPE_BICONVEX):
            self._update_radii_for_type()

    def _update_radii_for_type(self) -> None:
        """Apply the standard radius preset for the current lens_type.

        Unknown types leave the radii untouched.
        """
        preset = LENS_TYPE_PRESET_RADII.get(self.lens_type)
        if preset is None:
            return
        self.radius_of_curvature_1, self.radius_of_curvature_2 = preset
    
    def set_lens_type(self, lens_type: str) -> None:
        """Set lens type and update radii accordingly."""
        self.lens_type = lens_type
        self._update_radii_for_type()
        self.modified_at = datetime.now().isoformat()
    
    def classify_lens_type(self) -> str:
        """Classify lens type based on current radii values."""
        r1 = self.radius_of_curvature_1
        r2 = self.radius_of_curvature_2
        
        # Handle flat surfaces (radius = 0 or infinity)
        r1_flat = r1 == 0 or not math.isfinite(r1) or abs(r1) > LARGE_NUMBER if r1 else True
        r2_flat = r2 == 0 or not math.isfinite(r2) or abs(r2) > LARGE_NUMBER if r2 else True
        
        # Determine type based on radii
        if r1_flat and r2_flat:
            return "Unknown"
        elif r1_flat:
            return "Plano-Concave" if r2 > 0 else "Plano-Convex"
        elif r2_flat:
            return "Plano-Convex" if r1 > 0 else "Plano-Concave"
        elif r1 > 0 and r2 < 0:
            return "Biconvex"
        elif r1 < 0 and r2 > 0:
            return "Biconcave"
        elif r1 > 0 and r2 > 0:
            return "Meniscus Convex" if r1 < r2 else "Meniscus Concave"
        elif r1 < 0 and r2 < 0:
            return "Meniscus Concave" if abs(r1) < abs(r2) else "Meniscus Convex"
        else:
            return "Unknown"
    
    def calculate_optical_power(self) -> Optional[float]:
        """
        Calculate optical power in diopters (D).
        
        Optical power P = 1/f where f is in meters.
        Since focal length is in mm, P = 1000/f
        
        Returns:
            Optical power in diopters, or None if focal length is undefined
        """
        f = self.calculate_focal_length()
        if f is None or abs(f) < EPSILON:
            return None
        return 1000.0 / f  # Convert mm to meters for diopters
    
    def calculate_fresnel_efficiency(self) -> Optional[float]:
        """Calculate theoretical efficiency of Fresnel lens"""
        if not self.is_fresnel:
            return None
        
        # Simplified efficiency calculation
        base_efficiency = 0.90
        
        if self.groove_pitch < 0.5:
            efficiency_factor = 0.85
        elif self.groove_pitch < 1.0:
            efficiency_factor = 0.90
        else:
            efficiency_factor = 0.95
        
        return base_efficiency * efficiency_factor
    
    def calculate_fresnel_thickness_reduction(self) -> Optional[Dict[str, float]]:
        """Calculate thickness reduction compared to conventional lens"""
        if not self.is_fresnel or self.num_grooves is None:
            return None
        
        conventional_thickness = self.thickness
        fresnel_thickness = max(1.0, self.groove_pitch * 2)  # Minimum 1mm
        
        # Guard against division by zero
        if abs(conventional_thickness) < EPSILON:
            return None
        
        reduction_percentage = ((conventional_thickness - fresnel_thickness) / conventional_thickness) * 100
        
        # Clamp to meaningful range (can't have more than 100% reduction)
        reduction_percentage = max(0.0, reduction_percentage)
        
        return {
            'conventional_thickness': conventional_thickness,
            'fresnel_thickness': fresnel_thickness,
            'reduction_percentage': reduction_percentage,
            'weight_reduction_percentage': reduction_percentage * 0.9
        }
    
    def calculate_f_number(self) -> float:
        """Calculate f-number (f/#)"""
        focal_length = self.calculate_focal_length()
        if focal_length is None or abs(self.diameter) < EPSILON:
            return float('inf')
        return abs(focal_length) / self.diameter

    def calculate_back_focal_length(self) -> float:
        """
        Calculate Back Focal Length (BFL).
        
        BFL is the distance from the back vertex of the lens to the rear focal point.
        For a thick lens: BFL = f * (1 - d * P1 / n)
        where P1 = (n-1)/R1 is the power of the first surface,
        d is the thickness, n is the refractive index, and f is the focal length.
        
        Returns:
            Back focal length in mm, or inf if undefined
        """
        f = self.calculate_focal_length()
        if f is None:
            return float('inf')
        
        n = self.refractive_index
        r1 = self.radius_of_curvature_1
        t = self.thickness

        try:
            # Power of first surface (flat surface: r1 = inf -> P1 = 0)
            P1 = (n - 1) / r1

            # BFL = f * (1 - d * P1 / n)
            bfl = f * (1.0 - t * P1 / n)

            return bfl
        except ZeroDivisionError:
            return float('inf')

    def calculate_front_focal_length(self) -> float:
        """
        Calculate Front Focal Length (FFL).
        
        FFL is the distance from the front vertex of the lens to the front focal point.
        For a thick lens: FFL = f * (1 - d * P2 / n)
        where P2 = -(n-1)/R2 is the power of the second surface,
        d is the thickness, n is the refractive index, and f is the focal length.
        
        Returns:
            Front focal length in mm, or inf if undefined
        """
        f = self.calculate_focal_length()
        if f is None:
            return float('inf')
        
        n = self.refractive_index
        r2 = self.radius_of_curvature_2
        t = self.thickness

        try:
            # Power of second surface (note: using sign convention where P2 = (n_out - n_in)/R2)
            # For light exiting lens: P2 = (1 - n) / R2 = -(n - 1) / R2
            # Flat surface: r2 = inf -> P2 = 0
            P2 = -(n - 1) / r2

            # FFL = f * (1 - d * P2 / n)
            ffl = f * (1.0 - t * P2 / n)

            return ffl
        except ZeroDivisionError:
            return float('inf')

    def __str__(self) -> str:
        focal_length = self.calculate_focal_length()
        focal_str = f"{focal_length:.2f}mm" if focal_length is not None else "Undefined"
        
        return f"""
Optical Lens Details:
  ID: {self.id}
  Name: {self.name}
  Radius of Curvature 1: {self.radius_of_curvature_1}mm
  Radius of Curvature 2: {self.radius_of_curvature_2}mm
  Center Thickness: {self.thickness}mm
  Diameter: {self.diameter}mm
  Refractive Index: {self.refractive_index}
  Type: {self.lens_type}
  Material: {self.material}
  Calculated Focal Length: {focal_str}
  Created: {self.created_at}
  Modified: {self.modified_at}
"""
