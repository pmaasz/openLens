#!/usr/bin/env python3
"""
Material Database for Optical Glasses
Supports temperature-dependent refractive indices, transmission spectra,
and importing from major glass catalogs (Schott, Ohara, Hoya)
"""

import json
import os
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
import math


@dataclass
class MaterialProperties:
    """Optical material properties"""
    name: str
    catalog: str  # Schott, Ohara, Hoya, Custom
    nd: float  # Refractive index at d-line (587.6 nm)
    vd: float  # Abbe number
    
    # Sellmeier coefficients for wavelength-dependent refractive index
    # n^2 = 1 + B1*λ^2/(λ^2-C1) + B2*λ^2/(λ^2-C2) + B3*λ^2/(λ^2-C3)
    B1: float = 0.0
    B2: float = 0.0
    B3: float = 0.0
    C1: float = 0.0
    C2: float = 0.0
    C3: float = 0.0
    
    # Temperature coefficients (dn/dT in 1/°C)
    D0: float = 0.0  # Absolute term
    D1: float = 0.0  # Linear term
    D2: float = 0.0  # Quadratic term
    E0: float = 0.0  # Wavelength term
    E1: float = 0.0  # Wavelength term
    
    # Thermal properties
    thermal_expansion: float = 7.1e-6  # α (1/K)
    
    # Transmission data (wavelength in nm, transmission 0-1)
    transmission_data: List[Tuple[float, float]] = field(default_factory=list)
    
    # Physical properties
    density: float = 2.51  # g/cm³
    
    # Chemical properties
    climate_resistance: int = 1  # 0-4 scale
    acid_resistance: int = 1
    alkali_resistance: int = 1
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict):
        """Create from dictionary"""
        return cls(**data)


class MaterialDatabase:
    """Database of optical materials"""
    
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or os.path.join(
            os.path.dirname(__file__), '..', 'data', 'materials.json'
        )
        self.materials: Dict[str, MaterialProperties] = {}
        self._load_builtin_materials()
        self._load_database()
    
    def _load_builtin_materials(self):
        """Load built-in material definitions"""
        
        # Schott BK7 (most common optical glass)
        self.materials['BK7'] = MaterialProperties(
            name='BK7',
            catalog='Schott',
            nd=1.5168,
            vd=64.17,
            B1=1.03961212,
            B2=0.231792344,
            B3=1.01046945,
            C1=6.00069867e-3,
            C2=2.00179144e-2,
            C3=1.03560653e2,
            D0=-1.28e-6,
            D1=9.3e-9,
            D2=4.43e-11,
            E0=0.48e-6,
            E1=2.0e-9,
            thermal_expansion=7.1e-6,
            density=2.51,
            climate_resistance=1,
            acid_resistance=1,
            alkali_resistance=2,
            transmission_data=[
                (380, 0.95), (400, 0.97), (500, 0.995), (600, 0.998),
                (700, 0.998), (800, 0.998), (1000, 0.997), (1500, 0.99),
                (2000, 0.98), (2500, 0.5)
            ]
        )
        
        # Schott N-BK7 (improved BK7)
        self.materials['N-BK7'] = MaterialProperties(
            name='N-BK7',
            catalog='Schott',
            nd=1.5168,
            vd=64.17,
            B1=1.03961212,
            B2=0.231792344,
            B3=1.01046945,
            C1=6.00069867e-3,
            C2=2.00179144e-2,
            C3=1.03560653e2,
            D0=-1.28e-6,
            D1=9.3e-9,
            D2=4.43e-11,
            E0=0.48e-6,
            E1=2.0e-9,
            thermal_expansion=7.1e-6,
            density=2.51,
            climate_resistance=2,
            acid_resistance=2,
            alkali_resistance=2
        )
        
        # Schott SF11 (dense flint, high dispersion)
        self.materials['SF11'] = MaterialProperties(
            name='SF11',
            catalog='Schott',
            nd=1.78472,
            vd=25.68,
            B1=1.73759695,
            B2=0.313747346,
            B3=1.89878101,
            C1=1.35382130e-2,
            C2=6.15960463e-2,
            C3=1.74017590e2,
            D0=1.62e-6,
            D1=1.4e-8,
            D2=1.8e-10,
            E0=1.0e-6,
            E1=3.5e-9,
            thermal_expansion=8.2e-6,
            density=4.74,
            climate_resistance=1,
            acid_resistance=1,
            alkali_resistance=2
        )
        
        # Schott F2 (flint glass)
        self.materials['F2'] = MaterialProperties(
            name='F2',
            catalog='Schott',
            nd=1.62004,
            vd=36.37,
            B1=1.34533359,
            B2=0.209073176,
            B3=0.937357162,
            C1=9.97743871e-3,
            C2=4.70450767e-2,
            C3=1.11886764e2,
            D0=0.0,
            D1=1.1e-8,
            D2=1.5e-10,
            thermal_expansion=8.2e-6,
            density=3.61,
            climate_resistance=1,
            acid_resistance=1,
            alkali_resistance=2
        )
        
        # Fused Silica (UV grade) - Corrected Sellmeier coefficients
        self.materials['FUSEDSILICA'] = MaterialProperties(
            name='FUSEDSILICA',
            catalog='Schott',
            nd=1.45846,
            vd=67.82,
            B1=0.6961663,
            B2=0.4079426,
            B3=0.8974794,
            C1=0.0684043**2,  # C values should be squared
            C2=0.1162414**2,
            C3=9.896161**2,
            D0=9.7e-6,
            D1=0.0,
            D2=0.0,
            thermal_expansion=0.55e-6,
            density=2.20,
            climate_resistance=4,
            acid_resistance=4,
            alkali_resistance=1,
            transmission_data=[
                (200, 0.9), (250, 0.95), (300, 0.98), (400, 0.995),
                (600, 0.998), (1000, 0.998), (2000, 0.98), (3000, 0.5)
            ]
        )
        
        # Ohara S-LAH79 (high index)
        self.materials['S-LAH79'] = MaterialProperties(
            name='S-LAH79',
            catalog='Ohara',
            nd=2.00330,
            vd=28.27,
            B1=2.19229800,
            B2=0.408815500,
            B3=1.98550700,
            C1=1.19110700e-2,
            C2=5.95184000e-2,
            C3=1.51571600e2,
            thermal_expansion=6.5e-6,
            density=4.91,
            climate_resistance=2,
            acid_resistance=2,
            alkali_resistance=2
        )
        
        # Hoya E-FD60 (high Abbe, low dispersion)
        self.materials['E-FD60'] = MaterialProperties(
            name='E-FD60',
            catalog='Hoya',
            nd=1.52249,
            vd=59.48,
            B1=0.98653903,
            B2=0.21835181,
            B3=0.96818604,
            C1=5.87927586e-3,
            C2=1.98357771e-2,
            C3=9.86051455e1,
            thermal_expansion=7.7e-6,
            density=2.53,
            climate_resistance=2,
            acid_resistance=2,
            alkali_resistance=2
        )
    
    def _load_database(self):
        """Load materials from JSON file"""
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path, 'r') as f:
                    data = json.load(f)
                    for name, mat_data in data.items():
                        self.materials[name] = MaterialProperties.from_dict(mat_data)
            except Exception as e:
                print(f"Warning: Could not load material database: {e}")
    
    def save_database(self):
        """Save materials to JSON file"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        data = {name: mat.to_dict() for name, mat in self.materials.items()}
        with open(self.db_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def get_material(self, name: str) -> Optional[MaterialProperties]:
        """Get material by name"""
        return self.materials.get(name.upper())
    
    def add_material(self, material: MaterialProperties):
        """Add or update material"""
        self.materials[material.name.upper()] = material
        self.save_database()
    
    def list_materials(self, catalog: Optional[str] = None) -> List[str]:
        """List all material names, optionally filtered by catalog"""
        if catalog:
            return [name for name, mat in self.materials.items() 
                   if mat.catalog.upper() == catalog.upper()]
        return list(self.materials.keys())
    
    def get_refractive_index(self, material_name: str, wavelength_nm: float, 
                            temperature_c: float = 20.0) -> float:
        """
        Calculate refractive index at specific wavelength and temperature
        using Sellmeier equation and temperature coefficients
        """
        mat = self.get_material(material_name)
        if not mat:
            return 1.5168  # Default to BK7
        
        # Convert wavelength to micrometers
        wavelength_um = wavelength_nm / 1000.0
        lambda_sq = wavelength_um ** 2
        
        # Sellmeier equation
        n_sq = 1.0
        if mat.C1 > 0:
            n_sq += mat.B1 * lambda_sq / (lambda_sq - mat.C1)
        if mat.C2 > 0:
            n_sq += mat.B2 * lambda_sq / (lambda_sq - mat.C2)
        if mat.C3 > 0:
            n_sq += mat.B3 * lambda_sq / (lambda_sq - mat.C3)
        
        n_base = math.sqrt(n_sq)
        
        # Temperature correction
        if temperature_c != 20.0:
            delta_T = temperature_c - 20.0
            dn_abs = mat.D0 * delta_T + mat.D1 * delta_T**2 + mat.D2 * delta_T**3
            dn_rel = (n_base**2 - 1) / (2 * n_base) * (mat.E0 * delta_T + mat.E1 * delta_T**2)
            n_base += dn_abs + dn_rel
        
        return n_base
    
    def get_transmission(self, material_name: str, wavelength_nm: float) -> float:
        """Get transmission at specific wavelength (0-1)"""
        mat = self.get_material(material_name)
        if not mat or not mat.transmission_data:
            return 0.95  # Default transmission
        
        # Linear interpolation
        data = sorted(mat.transmission_data)
        if wavelength_nm <= data[0][0]:
            return data[0][1]
        if wavelength_nm >= data[-1][0]:
            return data[-1][1]
        
        for i in range(len(data) - 1):
            w1, t1 = data[i]
            w2, t2 = data[i + 1]
            if w1 <= wavelength_nm <= w2:
                ratio = (wavelength_nm - w1) / (w2 - w1)
                return t1 + ratio * (t2 - t1)
        
        return 0.95
    
    def import_schott_catalog(self, catalog_file: str):
        """Import materials from Schott catalog file"""
        # Placeholder for catalog import
        # Would parse AGF or other catalog format
        pass
    
    def export_material(self, material_name: str, output_file: str):
        """Export material data to file"""
        mat = self.get_material(material_name)
        if mat:
            with open(output_file, 'w') as f:
                json.dump(mat.to_dict(), f, indent=2)


# Convenience function
def get_material_database() -> MaterialDatabase:
    """Get singleton material database"""
    if not hasattr(get_material_database, '_instance'):
        get_material_database._instance = MaterialDatabase()
    return get_material_database._instance
