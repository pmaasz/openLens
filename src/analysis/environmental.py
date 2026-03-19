import math
import copy
from typing import Optional

try:
    from ..optical_system import OpticalSystem
    from ..lens import Lens
    from ..material_database import get_material_database
except ImportError:
    import sys
    import os
    # Assuming we are in src/analysis/environmental.py, go up two levels to reach src parent
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
    from src.optical_system import OpticalSystem
    from src.lens import Lens
    from src.material_database import get_material_database

class EnvironmentalAnalyzer:
    """
    Analyzes optical system performance under environmental changes 
    (Temperature and Pressure).
    """
    
    # Standard reference conditions
    REF_TEMP = 20.0       # °C
    REF_PRESSURE = 1.0    # atm (101.325 kPa)
    
    @staticmethod
    def calculate_air_index(wavelength_nm: float, temperature: float, pressure_atm: float) -> float:
        """
        Calculate refractive index of air using the Edlen equation.
        
        Args:
            wavelength_nm: Wavelength in nanometers
            temperature: Temperature in Celsius
            pressure_atm: Pressure in Atmospheres
            
        Returns:
            Absolute refractive index of air
        """
        # Convert wavelength to microns
        wl = wavelength_nm / 1000.0
        if wl <= 0: return 1.0
        
        # Dispersion formula for standard air (15°C, 1013.25 mbar, dry)
        # (n-1) * 10^8
        # Formula from NIST / Ciddor (simplified Edlen)
        s2 = 1.0 / (wl * wl)
        n_s_minus_1_e8 = 8342.54 + 2406147.0 / (130.0 - s2) + 15998.0 / (38.9 - s2)
        n_s_minus_1 = n_s_minus_1_e8 * 1e-8
        
        # Temperature and Pressure correction
        # P in Pa, T in K
        # Here input is atm and C
        P = pressure_atm * 101325.0
        T = temperature + 273.15
        
        # Edlen equation for T and P
        # (n_tp - 1) = (n_s - 1) * (P / 96095.43) * ( (1 + 10^-8 * (0.601 - 0.00972*T)*P) / (1 + 0.0036610*T) )
        # Using a slightly simpler form often cited for optical engineering (Zemax manual approx):
        
        # (n - 1)_TP = (n_ref - 1) * (P / P_ref) / (1 + 0.003495 * (T - 15))
        # But our ref is usually 20C.
        
        # Let's use the rigorous update:
        # n_tp - 1 = (n_s - 1) * (P / 101325) * (288.15 / T)
        # This is the Ideal Gas Law approximation which is usually sufficient for optics
        
        n_tp = 1.0 + n_s_minus_1 * (P / 101325.0) * (288.15 / T)
        
        return n_tp

    @classmethod
    def apply_environment(cls, system: OpticalSystem, temperature: float, pressure: float) -> OpticalSystem:
        """
        Create a new OpticalSystem with environmental effects applied.
        
        Args:
            system: The nominal optical system
            temperature: New temperature in °C
            pressure: New pressure in atm
            
        Returns:
            A new OpticalSystem instance with perturbed parameters
        """
        # Deep copy the system
        new_system = copy.deepcopy(system)
        new_system.name = f"{system.name} (T={temperature}C, P={pressure}atm)"
        
        db = get_material_database()
        
        delta_T = temperature - cls.REF_TEMP
        
        # 1. Update Elements (Glass)
        for element in new_system.elements:
            lens = element.lens
            
            # Get material properties
            mat = db.get_material(lens.material)
            
            # Get CTE (Coefficient of Thermal Expansion)
            # Default to BK7/standard glass if unknown (~7.1e-6)
            alpha = mat.thermal_expansion if mat else 7.1e-6
            
            # --- Apply Thermal Expansion to Geometry ---
            scaling_factor = 1.0 + alpha * delta_T
            
            # Radius
            lens.radius_of_curvature_1 *= scaling_factor
            lens.radius_of_curvature_2 *= scaling_factor
            
            # Thickness
            lens.thickness *= scaling_factor
            element.thickness = lens.thickness # Update wrapper too
            
            # Diameter (mechanical only, but good to update)
            lens.diameter *= scaling_factor
            
            # --- Apply Refractive Index Changes ---
            # 1. Get relative index at new Temperature (assuming P=1 atm constant in catalog data)
            # update_refractive_index uses the MaterialDatabase which handles dn/dT
            lens.update_refractive_index(temperature=temperature)
            n_rel_T = lens.refractive_index
            
            # 2. Correct for Pressure change (Index of Air)
            # n_glass_abs = n_rel_T * n_air(T, P_ref)
            # n_new_rel = n_glass_abs / n_air(T, P_new)
            # n_new_rel = n_rel_T * (n_air(T, P_ref) / n_air(T, P_new))
            
            # Note: n_rel_T is relative to air at the NEW temperature T (but reference pressure)
            n_air_ref = cls.calculate_air_index(lens.wavelength, temperature, cls.REF_PRESSURE)
            n_air_new = cls.calculate_air_index(lens.wavelength, temperature, pressure)
            
            if n_air_new != 0:
                lens.refractive_index = n_rel_T * (n_air_ref / n_air_new)
                
        # 2. Update Air Gaps (Housing Expansion)
        # We need an assumption for housing CTE.
        # Aluminum ~ 23.6e-6, Steel ~ 12e-6, Invar ~ 1e-6
        # Let's assume Aluminum for generic "Housing"
        housing_alpha = 23.6e-6 
        gap_scaling = 1.0 + housing_alpha * delta_T
        
        for gap in new_system.air_gaps:
            gap.thickness *= gap_scaling
            
        # 3. Update positions based on new thicknesses
        new_system._update_positions()
        
        return new_system

