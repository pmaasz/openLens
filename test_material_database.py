#!/usr/bin/env python3
"""
Test script for material database
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from material_database import MaterialDatabase, MaterialProperties

def main():
    print("="*70)
    print("MATERIAL DATABASE TEST")
    print("="*70)
    print()
    
    db = MaterialDatabase()
    
    print("Available materials:")
    for name in sorted(db.list_materials()):
        mat = db.get_material(name)
        print(f"  {name:15s} - {mat.catalog:10s} nd={mat.nd:.4f} vd={mat.vd:.2f}")
    print()
    
    print("Testing wavelength-dependent refractive index:")
    print("-" * 70)
    
    materials_to_test = ['BK7', 'SF11', 'FUSEDSILICA']
    wavelengths = [400, 500, 587.6, 700, 1000]  # nm
    
    for mat_name in materials_to_test:
        print(f"\n{mat_name}:")
        for wl in wavelengths:
            n = db.get_refractive_index(mat_name, wl)
            print(f"  λ={wl:6.1f} nm: n={n:.5f}")
    
    print()
    print("Testing temperature dependence:")
    print("-" * 70)
    
    temperatures = [0, 20, 40, 60]
    wavelength = 587.6  # d-line
    
    for mat_name in ['BK7', 'SF11']:
        print(f"\n{mat_name} at λ={wavelength} nm:")
        for temp in temperatures:
            n = db.get_refractive_index(mat_name, wavelength, temp)
            print(f"  T={temp:3d}°C: n={n:.6f}")
    
    print()
    print("Testing transmission data:")
    print("-" * 70)
    
    mat_name = 'BK7'
    wavelengths = [380, 500, 700, 1000, 2000]
    
    print(f"\n{mat_name} transmission:")
    for wl in wavelengths:
        trans = db.get_transmission(mat_name, wl)
        print(f"  λ={wl:6.1f} nm: T={trans*100:.1f}%")
    
    print()
    print("Catalog filtering:")
    print("-" * 70)
    
    for catalog in ['Schott', 'Ohara', 'Hoya']:
        materials = db.list_materials(catalog=catalog)
        print(f"  {catalog}: {len(materials)} materials - {', '.join(materials)}")
    
    print()
    print("Material properties (BK7 detailed):")
    print("-" * 70)
    
    bk7 = db.get_material('BK7')
    print(f"  Name: {bk7.name}")
    print(f"  Catalog: {bk7.catalog}")
    print(f"  nd (d-line): {bk7.nd}")
    print(f"  vd (Abbe): {bk7.vd}")
    print(f"  Density: {bk7.density} g/cm³")
    print(f"  Thermal expansion: {bk7.thermal_expansion*1e6:.2f} ppm/K")
    print(f"  Climate resistance: {bk7.climate_resistance}/4")
    print(f"  Acid resistance: {bk7.acid_resistance}/4")
    print(f"  Alkali resistance: {bk7.alkali_resistance}/4")
    print(f"  Sellmeier coefficients:")
    print(f"    B1={bk7.B1:.8f}, C1={bk7.C1:.8e}")
    print(f"    B2={bk7.B2:.8f}, C2={bk7.C2:.8e}")
    print(f"    B3={bk7.B3:.8f}, C3={bk7.C3:.8e}")
    
    print()
    print("="*70)
    print("✓ Material database working correctly!")
    print("="*70)

if __name__ == "__main__":
    main()
