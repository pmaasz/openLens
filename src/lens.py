from datetime import datetime
from typing import Optional, Dict, Any
import math

try:
    from .constants import (
        DEFAULT_RADIUS_1, DEFAULT_RADIUS_2, DEFAULT_THICKNESS, DEFAULT_DIAMETER,
        REFRACTIVE_INDEX_BK7, EPSILON
    )
except ImportError:
    # Fallback constants if constants module not found
    DEFAULT_RADIUS_1 = 100.0
    DEFAULT_RADIUS_2 = -100.0
    DEFAULT_THICKNESS = 5.0
    DEFAULT_DIAMETER = 50.0
    REFRACTIVE_INDEX_BK7 = 1.5168
    EPSILON = 1e-10

# Try to import material database (optional)
get_material_database = None
MATERIAL_DB_AVAILABLE = False

try:
    from .material_database import get_material_database
    MATERIAL_DB_AVAILABLE = True
except (ImportError, ValueError):
    # Fallback for direct script execution
    try:
        from material_database import get_material_database
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
                 refractive_index: float = REFRACTIVE_INDEX_BK7,
                 lens_type: str = "Biconvex",
                 material: str = "BK7",
                 wavelength: float = 587.6,
                 temperature: float = 20.0,
                 is_fresnel: bool = False,
                 groove_pitch: float = DEFAULT_THICKNESS,
                 num_grooves: Optional[int] = None,
                 model_glass_mode: bool = False,
                 model_nd: float = 1.5168,
                 model_vd: float = 64.17) -> None:
        
        self.id = datetime.now().strftime("%Y%m%d%H%M%S%f")
        self.name = name
        self.radius_of_curvature_1 = radius_of_curvature_1
        self.radius_of_curvature_2 = radius_of_curvature_2
        self.thickness = thickness
        self.diameter = diameter
        self.material = material
        self.wavelength = wavelength  # Design wavelength in nm
        self.temperature = temperature  # Operating temperature in °C
        
        # Model Glass Properties
        self.model_glass_mode = model_glass_mode
        self.model_nd = model_nd
        self.model_vd = model_vd

        # Get refractive index from material database if available
        if self.model_glass_mode and MATERIAL_DB_AVAILABLE:
            try:
                db = get_material_database()
                # Check if db has the new method (it might not if reload failed, but here we assume it works)
                if hasattr(db, 'calculate_model_index'):
                    self.refractive_index = db.calculate_model_index(self.model_nd, self.model_vd, self.wavelength)
                else:
                     # Fallback if method missing
                     self.refractive_index = self.model_nd
            except Exception:
                self.refractive_index = self.model_nd
        elif MATERIAL_DB_AVAILABLE:
            try:
                db = get_material_database()
                mat = db.get_material(material)
                if mat:
                    self.refractive_index = db.get_refractive_index(material, wavelength, temperature)
                else:
                    self.refractive_index = refractive_index
            except Exception:
                self.refractive_index = refractive_index
        else:
            self.refractive_index = refractive_index
            
        self.lens_type = lens_type
        
        # Only update radii if using default values and lens_type differs from default
        # This preserves custom radii while allowing lens_type to set defaults when appropriate
        if (radius_of_curvature_1 == DEFAULT_RADIUS_1 and 
            radius_of_curvature_2 == DEFAULT_RADIUS_2 and
            lens_type != "Biconvex"):
            self._update_radii_for_type()
        
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
                                 wavelength: Optional[float] = None,
                                 temperature: Optional[float] = None) -> None:
        """
        Update refractive index for new wavelength/temperature.
        """
        if wavelength is not None:
            self.wavelength = wavelength
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
                    self.refractive_index = self.model_nd
            except Exception:
                pass
        elif MATERIAL_DB_AVAILABLE:
            try:
                db = get_material_database()
                self.refractive_index = db.get_refractive_index(
                    self.material, self.wavelength, self.temperature
                )
            except Exception:
                pass
    
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
            wavelength=data.get("wavelength", 587.6),
            temperature=data.get("temperature", 20.0),
            is_fresnel=data.get("is_fresnel", False),
            groove_pitch=data.get("groove_pitch", DEFAULT_THICKNESS),
            num_grooves=data.get("num_grooves", None),
            model_glass_mode=data.get("model_glass_mode", False),
            model_nd=data.get("model_nd", 1.5168),
            model_vd=data.get("model_vd", 64.17)
        )
        
        # Only update radii if they match defaults and lens_type is different
        if (r1 == DEFAULT_RADIUS_1 and r2 == DEFAULT_RADIUS_2 and lens_type != "Biconvex"):
            lens._update_radii_for_type()
        
        lens.id = data.get("id", lens.id)
        lens.created_at = data.get("created_at", lens.created_at)
        lens.modified_at = data.get("modified_at", lens.modified_at)
        return lens
    
    def calculate_focal_length(self) -> Optional[float]:
        """
        Calculate focal length using the lensmaker's equation.
        """
        n = self.refractive_index
        R1 = self.radius_of_curvature_1
        R2 = self.radius_of_curvature_2
        d = self.thickness
        
        # Use EPSILON for zero check to handle floating-point edge cases
        if abs(R1) < EPSILON or abs(R2) < EPSILON:
            return None
        
        # Lensmaker's equation: 1/f = (n-1)[1/R1 - 1/R2 + (n-1)d/(nR1R2)]
        try:
            power = (n - 1) * ((1/R1) - (1/R2) + ((n - 1) * d) / (n * R1 * R2))
            
            if abs(power) < EPSILON:
                return None
            
            return 1 / power
        except ZeroDivisionError:
            return None
    
    def _update_radii_for_type(self) -> None:
        """Update radii based on the current lens_type."""
        diameter = self.diameter
        if diameter <= 0:
            diameter = DEFAULT_DIAMETER
        
        half_aperture = diameter / 2
        
        lens_type = self.lens_type
        
        if lens_type == "Biconvex":
            self.radius_of_curvature_1 = 100.0
            self.radius_of_curvature_2 = -100.0
        elif lens_type == "Biconcave":
            self.radius_of_curvature_1 = -100.0
            self.radius_of_curvature_2 = 100.0
        elif lens_type == "Plano-Convex":
            self.radius_of_curvature_1 = 100.0
            self.radius_of_curvature_2 = float('inf')
        elif lens_type == "Plano-Concave":
            self.radius_of_curvature_1 = float('inf')
            self.radius_of_curvature_2 = 100.0
        elif lens_type == "Meniscus Convex":
            self.radius_of_curvature_1 = 80.0
            self.radius_of_curvature_2 = -120.0
        elif lens_type == "Meniscus Concave":
            self.radius_of_curvature_1 = -120.0
            self.radius_of_curvature_2 = 80.0
        else:
            pass
    
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
        r1_flat = r1 == 0 or abs(r1) > 1e10 if r1 else True
        r2_flat = r2 == 0 or abs(r2) > 1e10 if r2 else True
        
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
            if abs(r1) < EPSILON:
                return float('inf')
            
            # Power of first surface
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
            if abs(r2) < EPSILON:
                return float('inf')
            
            # Power of second surface (note: using sign convention where P2 = (n_out - n_in)/R2)
            # For light exiting lens: P2 = (1 - n) / R2 = -(n - 1) / R2
            P2 = -(n - 1) / r2
            
            # FFL = f * (1 - d * P2 / n)
            ffl = f * (1.0 - t * P2 / n)
            
            return ffl
        except ZeroDivisionError:
            return float('inf')

    def __str__(self) -> str:
        focal_length = self.calculate_focal_length()
        focal_str = f"{focal_length:.2f}mm" if focal_length else "Undefined"
        
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
