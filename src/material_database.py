#!/usr/bin/env python3
"""
Material Database for Optical Glasses
Supports temperature-dependent refractive indices, transmission spectra,
and importing from major glass catalogs (Schott, Ohara, Hoya)
"""

import json
import logging
import os
import csv
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
import math
from functools import lru_cache

# Setup module logger
logger = logging.getLogger(__name__)


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
    transmission_thickness: float = 10.0  # Thickness for transmission data (mm)
    
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
    
    def _load_builtin_materials(self) -> None:
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
    
    def _load_database(self) -> None:
        """Load materials from JSON file"""
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path, 'r') as f:
                    data = json.load(f)
                    for name, mat_data in data.items():
                        self.materials[name] = MaterialProperties.from_dict(mat_data)
            except Exception as e:
                logger.warning("Could not load material database: %s", e)
    
    def save_database(self) -> None:
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
        # Clear cache as material properties might have changed
        self.get_refractive_index.cache_clear()
        self.save_database()
    
    def list_materials(self, catalog: Optional[str] = None) -> List[str]:
        """List all material names, optionally filtered by catalog"""
        if catalog:
            return [name for name, mat in self.materials.items() 
                   if mat.catalog.upper() == catalog.upper()]
        return list(self.materials.keys())
    
    @lru_cache(maxsize=1024)
    def get_refractive_index(self, material_name: str, wavelength_nm: float, 
                            temperature_c: float = 20.0) -> float:
        """
        Calculate refractive index at specific wavelength and temperature
        using Sellmeier equation and temperature coefficients.
        
        Cached for performance (LRU 1024 entries).
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
    
    def clear_cache(self):
        """Clear refractive index cache"""
        self.get_refractive_index.cache_clear()
    
    def get_transmission(self, material_name: str, wavelength_nm: float, thickness_mm: float = 10.0) -> float:
        """
        Get internal transmission for a specific thickness.
        Normalizes from the catalog reference thickness using Beer-Lambert law:
        T2 = T1^(thickness2 / thickness1)
        """
        mat = self.get_material(material_name)
        if not mat or not mat.transmission_data:
            # Default fallback: 99% per 10mm
            return 0.99 ** (thickness_mm / 10.0)
        
        # Get base transmission from catalog data
        t_base = self._interpolate_transmission(mat.transmission_data, wavelength_nm)
        
        if t_base <= 0:
            return 0.0
        
        # Scale for thickness
        exponent = thickness_mm / mat.transmission_thickness
        return t_base ** exponent

    def _interpolate_transmission(self, data: List[Tuple[float, float]], wavelength_nm: float) -> float:
        """Interpolate transmission value from data points"""
        # Sort by wavelength
        data = sorted(data)
        
        if not data:
            return 1.0
            
        if wavelength_nm <= data[0][0]:
            return data[0][1]
        if wavelength_nm >= data[-1][0]:
            return data[-1][1]
        
        for i in range(len(data) - 1):
            w1, t1 = data[i]
            w2, t2 = data[i + 1]
            if w1 <= wavelength_nm <= w2:
                # Linear interpolation
                ratio = (wavelength_nm - w1) / (w2 - w1)
                return t1 + ratio * (t2 - t1)
        
        return 0.95
    
    def import_agf_catalog(self, catalog_file: str) -> int:
        """
        Import materials from AGF catalog file.
        Returns number of materials imported.
        """
        if not os.path.exists(catalog_file):
            logger.error(f"Catalog file not found: {catalog_file}")
            return 0
            
        count = 0
        current_glass: Optional[Dict] = None
        catalog_name = "AGF_Import"
        
        try:
            with open(catalog_file, 'r', encoding='utf-8', errors='replace') as f:
                lines = f.readlines()
                
            for line in lines:
                parts = line.strip().split()
                if not parts:
                    continue
                    
                key = parts[0].upper()
                
                if key == 'NM':
                    # Save previous glass if exists
                    if current_glass:
                        self._process_agf_glass(current_glass, catalog_name)
                        count += 1
                    
                    # Start new glass
                    # NM "NAME" Formula Nd Vd ...
                    name_raw = parts[1]
                    name = name_raw.strip('"')
                    
                    # Extract basic properties
                    # Format: NM Name Formula Nd Vd ...
                    # Formula 1=Schott, 2=Sellmeier1, etc. But standard is consistent for Nd, Vd
                    try:
                        nd = float(parts[3])
                        vd = float(parts[4])
                        tce = float(parts[5]) if len(parts) > 5 else 0.0
                        density = float(parts[6]) if len(parts) > 6 else 0.0
                    except (IndexError, ValueError):
                        logger.warning(f"Error parsing NM line for {name}")
                        current_glass = None
                        continue
                        
                    current_glass = {
                        'name': name,
                        'nd': nd,
                        'vd': vd,
                        'tce': tce * 1e-6,  # Usually given in 10^-6
                        'density': density,
                        'dispersion': [],
                        'transmission': [],
                        'transmission_thickness': 10.0
                    }
                    
                elif key == 'CD' and current_glass:
                    # Dispersion coefficients
                    # CD C1 C2 C3 ...
                    try:
                        coeffs = [float(x) for x in parts[1:]]
                        current_glass['dispersion'] = coeffs
                    except ValueError:
                        pass
                        
                elif key == 'IT' and current_glass:
                    # Internal Transmission
                    # IT Thickness T1 T2 T3 ... (pairs are interleaved? No usually IT Thk W1 T1 W2 T2 ...)
                    # Zemax AGF: IT <thick> <w1> <t1> <w2> <t2> ...
                    try:
                        thickness = float(parts[1])
                        current_glass['transmission_thickness'] = thickness
                        
                        # Parse pairs
                        vals = [float(x) for x in parts[2:]]
                        pairs = []
                        for i in range(0, len(vals), 2):
                            if i+1 < len(vals):
                                # Wavelength in AGF is usually micrometers
                                w_um = vals[i]
                                t = vals[i+1]
                                pairs.append((w_um * 1000.0, t)) # Convert um to nm
                        
                        current_glass['transmission'] = pairs
                    except (IndexError, ValueError):
                        pass

            # Save last glass
            if current_glass:
                self._process_agf_glass(current_glass, catalog_name)
                count += 1
                
        except Exception as e:
            logger.error(f"Error importing AGF catalog: {e}")
            
        return count

    def _process_agf_glass(self, data: Dict, catalog: str):
        """Convert raw AGF data to MaterialProperties"""
        coeffs = data.get('dispersion', [])
        # Standard AGF coefficients map to Sellmeier 1 (Schott)
        # K1, K2, K3, L1, L2, L3 -> B1, B2, B3, C1, C2, C3
        # Usually 6 or 10 coefficients
        
        b1, b2, b3 = 0.0, 0.0, 0.0
        c1, c2, c3 = 0.0, 0.0, 0.0
        
        if len(coeffs) >= 6:
            b1 = coeffs[0]
            b2 = coeffs[1]
            b3 = coeffs[2]
            c1 = coeffs[3]
            c2 = coeffs[4]
            c3 = coeffs[5]
            
        mat = MaterialProperties(
            name=data['name'],
            catalog=catalog,
            nd=data['nd'],
            vd=data['vd'],
            B1=b1, B2=b2, B3=b3,
            C1=c1, C2=c2, C3=c3,
            thermal_expansion=data.get('tce', 7.1e-6),
            density=data.get('density', 2.5),
            transmission_data=data.get('transmission', []),
            transmission_thickness=data.get('transmission_thickness', 10.0)
        )
        self.add_material(mat)

    def import_csv_catalog(self, catalog_file: str) -> int:
        """
        Import materials from CSV file.
        Expected headers: Name,Catalog,Nd,Vd,B1,B2,B3,C1,C2,C3,...
        """
        if not os.path.exists(catalog_file):
            return 0
            
        count = 0
        try:
            with open(catalog_file, 'r', newline='') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        # Required fields
                        name = row['Name']
                        nd = float(row['Nd'])
                        vd = float(row['Vd'])
                        
                        # Optional fields with defaults
                        mat = MaterialProperties(
                            name=name,
                            catalog=row.get('Catalog', 'Custom'),
                            nd=nd,
                            vd=vd,
                            B1=float(row.get('B1', 0)),
                            B2=float(row.get('B2', 0)),
                            B3=float(row.get('B3', 0)),
                            C1=float(row.get('C1', 0)),
                            C2=float(row.get('C2', 0)),
                            C3=float(row.get('C3', 0)),
                            thermal_expansion=float(row.get('TCE', 7.1)) * 1e-6 if float(row.get('TCE', 0)) > 1e-4 else float(row.get('TCE', 7.1e-6)),
                            density=float(row.get('Density', 2.5))
                        )
                        self.add_material(mat)
                        count += 1
                    except (ValueError, KeyError) as e:
                        logger.warning(f"Skipping invalid CSV row: {e}")
                        continue
        except Exception as e:
            logger.error(f"Error importing CSV catalog: {e}")
            
        return count

    def import_schott_catalog(self, catalog_file: str):
        """Deprecated alias for import_agf_catalog"""
        self.import_agf_catalog(catalog_file)
    
    def export_material(self, material_name: str, output_file: str):
        """Export material data to file"""
        mat = self.get_material(material_name)
        if mat:
            with open(output_file, 'w') as f:
                json.dump(mat.to_dict(), f, indent=2)

    @staticmethod
    def calculate_model_index(nd: float, vd: float, wavelength_nm: float) -> float:
        """
        Calculate refractive index for a 'Model Glass' defined by nd and Vd.
        Uses a simplified 2-term Cauchy dispersion model.
        
        n(λ) = A + B/λ²
        
        A and B are derived from nd (at 587.6nm), nF (486.1nm), nC (656.3nm)
        and the definition of Abbe number Vd = (nd - 1) / (nF - nC).
        """
        # Wavelengths in micrometers
        wl_d = 0.58756
        wl_F = 0.48613
        wl_C = 0.65627
        
        wl_nm_um = wavelength_nm / 1000.0
        
        # 1. Calculate B
        # B = (nd - 1) / (Vd * (1/wl_F² - 1/wl_C²))
        term = (1.0 / (wl_F**2)) - (1.0 / (wl_C**2))
        
        if abs(vd * term) < 1e-9:
             return nd # Avoid division by zero
             
        B = (nd - 1.0) / (vd * term)
        
        # 2. Calculate A
        # A = nd - B/wl_d²
        A = nd - (B / (wl_d**2))
        
        # 3. Calculate n at target wavelength
        n = A + (B / (wl_nm_um**2))
        
        return n


# Convenience function
def get_material_database() -> MaterialDatabase:
    """Get singleton material database"""
    if not hasattr(get_material_database, '_instance'):
        get_material_database._instance = MaterialDatabase()
    return get_material_database._instance
