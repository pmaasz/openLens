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
try:
    from .material_database import get_material_database
    MATERIAL_DB_AVAILABLE = True
except (ImportError, ValueError):
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
                 num_grooves: Optional[int] = None) -> None:
        
        self.id = datetime.now().strftime("%Y%m%d%H%M%S%f")
        self.name = name
        self.radius_of_curvature_1 = radius_of_curvature_1
        self.radius_of_curvature_2 = radius_of_curvature_2
        self.thickness = thickness
        self.diameter = diameter
        self.material = material
        self.wavelength = wavelength  # Design wavelength in nm
        self.temperature = temperature  # Operating temperature in °C
        
        # Get refractive index from material database if available
        if MATERIAL_DB_AVAILABLE:
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
        
        # Fresnel properties
        self.is_fresnel = is_fresnel
        self.groove_pitch = groove_pitch
        self.num_grooves = num_grooves
        
        self.created_at = datetime.now().isoformat()
        self.modified_at = datetime.now().isoformat()
        
        # Auto-calculate number of grooves if not provided and is fresnel
        if self.is_fresnel and self.num_grooves is None:
            self.calculate_num_grooves()
    
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
        
        if MATERIAL_DB_AVAILABLE:
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
            "created_at": self.created_at,
            "modified_at": self.modified_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Lens':
        """Create lens from dictionary representation."""
        lens = cls(
            name=data.get("name", "Untitled"),
            radius_of_curvature_1=data.get("radius_of_curvature_1", DEFAULT_RADIUS_1),
            radius_of_curvature_2=data.get("radius_of_curvature_2", DEFAULT_RADIUS_2),
            thickness=data.get("thickness", DEFAULT_THICKNESS),
            diameter=data.get("diameter", DEFAULT_DIAMETER),
            refractive_index=data.get("refractive_index", REFRACTIVE_INDEX_BK7),
            lens_type=data.get("type", "Biconvex"),
            material=data.get("material", "BK7"),
            wavelength=data.get("wavelength", 587.6),
            temperature=data.get("temperature", 20.0),
            is_fresnel=data.get("is_fresnel", False),
            groove_pitch=data.get("groove_pitch", DEFAULT_THICKNESS),
            num_grooves=data.get("num_grooves", None)
        )
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
        
        if R1 == 0 or R2 == 0:
            return None
        
        # Lensmaker's equation: 1/f = (n-1)[1/R1 - 1/R2 + (n-1)d/(nR1R2)]
        try:
            power = (n - 1) * ((1/R1) - (1/R2) + ((n - 1) * d) / (n * R1 * R2))
            
            if abs(power) < EPSILON:
                return None
            
            return 1 / power
        except ZeroDivisionError:
            return None
    
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
        
        reduction_percentage = ((conventional_thickness - fresnel_thickness) / conventional_thickness) * 100
        return {
            'conventional_thickness': conventional_thickness,
            'fresnel_thickness': fresnel_thickness,
            'reduction_percentage': reduction_percentage,
            'weight_reduction_percentage': reduction_percentage * 0.9
        }
    
    def calculate_f_number(self) -> float:
        """Calculate f-number (f/#)"""
        focal_length = self.calculate_focal_length()
        if focal_length is None or self.diameter == 0:
            return float('inf')
        return abs(focal_length) / self.diameter

    def calculate_back_focal_length(self) -> float:
        """Calculate Back Focal Length (BFL)"""
        f = self.calculate_focal_length()
        if f is None: return float('inf')
        
        n = self.refractive_index
        r1 = self.radius_of_curvature_1
        r2 = self.radius_of_curvature_2
        t = self.thickness
        
        try:
            power1 = (n - 1) / r1
            power2 = -(n - 1) / r2
            power_spacing = (n - 1) * (n - 1) * t / (n * r1 * r2)
            total_power = power1 + power2 + power_spacing
            
            if abs(total_power) < EPSILON:
                return float('inf')
            
            return (1.0 - power2 * t) / total_power
        except ZeroDivisionError:
            return float('inf')

    def calculate_front_focal_length(self) -> float:
        """Calculate Front Focal Length (FFL)"""
        n = self.refractive_index
        r1 = self.radius_of_curvature_1
        r2 = self.radius_of_curvature_2
        t = self.thickness
        
        try:
            power1 = (n - 1) / r1
            power2 = -(n - 1) / r2
            power_spacing = (n - 1) * (n - 1) * t / (n * r1 * r2)
            total_power = power1 + power2 + power_spacing
            
            if abs(total_power) < EPSILON:
                return float('inf')
            
            return (1.0 - power1 * t) / total_power
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
