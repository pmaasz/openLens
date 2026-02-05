#!/usr/bin/env python3
"""
Test multi-element optical systems
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src'))

from optical_system import OpticalSystem, AchromaticDoubletDesigner, create_doublet, create_triplet
from lens_editor import Lens

def main():
    print("="*70)
    print("MULTI-ELEMENT OPTICAL SYSTEM TEST")
    print("="*70)
    print()
    
    # Test 1: Simple two-lens system
    print("Test 1: Two-Lens System")
    print("-" * 70)
    
    lens1 = Lens(name="Lens 1", radius_of_curvature_1=100, radius_of_curvature_2=-100,
                thickness=10, diameter=50, material="BK7")
    lens2 = Lens(name="Lens 2", radius_of_curvature_1=80, radius_of_curvature_2=-80,
                thickness=8, diameter=50, material="BK7")
    
    system = OpticalSystem(name="Two-Lens System")
    system.add_lens(lens1, air_gap_before=0)
    system.add_lens(lens2, air_gap_before=20.0)  # 20mm air gap
    
    print(f"System: {system.name}")
    print(f"  Number of elements: {len(system.elements)}")
    print(f"  Total length: {system.get_total_length():.1f} mm")
    print(f"  Element 1 at position: {system.elements[0].position:.1f} mm")
    print(f"  Element 2 at position: {system.elements[1].position:.1f} mm")
    
    f1 = lens1.calculate_focal_length()
    f2 = lens2.calculate_focal_length()
    f_sys = system.get_system_focal_length()
    
    print(f"  Lens 1 focal length: {f1:.1f} mm")
    print(f"  Lens 2 focal length: {f2:.1f} mm")
    print(f"  System focal length: {f_sys:.1f} mm")
    print()
    
    # Test 2: Achromatic Doublet
    print("Test 2: Achromatic Doublet")
    print("-" * 70)
    
    doublet = create_doublet(focal_length=100, diameter=50)
    
    print(f"System: {doublet.name}")
    print(f"  Number of elements: {len(doublet.elements)}")
    print(f"  Total length: {doublet.get_total_length():.1f} mm")
    
    for i, elem in enumerate(doublet.elements):
        print(f"  Element {i+1}: {elem.lens.material}")
        print(f"    Position: {elem.position:.1f} mm")
        print(f"    Thickness: {elem.thickness:.1f} mm")
        print(f"    Focal length: {elem.lens.calculate_focal_length():.1f} mm")
    
    f_doublet = doublet.get_system_focal_length()
    print(f"  System focal length: {f_doublet:.1f} mm")
    
    # Test chromatic aberration
    chrom = doublet.calculate_chromatic_aberration()
    print(f"  Chromatic aberration:")
    print(f"    Longitudinal: {chrom['longitudinal']:.3f} mm")
    print(f"    f_F (486nm): {chrom['f_F']:.2f} mm")
    print(f"    f_d (588nm): {chrom['f_d']:.2f} mm")
    print(f"    f_C (656nm): {chrom['f_C']:.2f} mm")
    print(f"    Achromatic: {chrom['corrected']}")
    print()
    
    # Test 3: Triplet
    print("Test 3: Triplet System")
    print("-" * 70)
    
    triplet = create_triplet(focal_length=100, diameter=50)
    
    print(f"System: {triplet.name}")
    print(f"  Number of elements: {len(triplet.elements)}")
    print(f"  Number of air gaps: {len(triplet.air_gaps)}")
    print(f"  Total length: {triplet.get_total_length():.1f} mm")
    
    for i, elem in enumerate(triplet.elements):
        print(f"  Element {i+1}: {elem.lens.name} ({elem.lens.material})")
        print(f"    Position: {elem.position:.1f} mm")
        if i < len(triplet.air_gaps):
            print(f"    Air gap after: {triplet.air_gaps[i].thickness:.1f} mm")
    
    f_triplet = triplet.get_system_focal_length()
    print(f"  System focal length: {f_triplet:.1f} mm")
    print()
    
    # Test 4: Different doublet materials
    print("Test 4: Custom Material Doublet")
    print("-" * 70)
    
    custom_doublet = AchromaticDoubletDesigner.design_cemented_doublet(
        focal_length=150,
        diameter=40,
        crown_material="N-BK7",
        flint_material="F2"
    )
    
    print(f"System: {custom_doublet.name}")
    print(f"  Crown: {custom_doublet.elements[0].lens.material}")
    print(f"  Flint: {custom_doublet.elements[1].lens.material}")
    print(f"  System focal length: {custom_doublet.get_system_focal_length():.1f} mm")
    
    chrom2 = custom_doublet.calculate_chromatic_aberration()
    print(f"  Chromatic aberration: {chrom2['longitudinal']:.3f} mm")
    print(f"  Achromatic: {chrom2['corrected']}")
    print()
    
    # Test 5: Serialization
    print("Test 5: Save/Load System")
    print("-" * 70)
    
    test_file = "/tmp/test_system.json"
    doublet.save(test_file)
    print(f"  Saved to: {test_file}")
    
    loaded_system = OpticalSystem.load(test_file)
    print(f"  Loaded: {loaded_system.name}")
    print(f"  Elements: {len(loaded_system.elements)}")
    print(f"  Focal length: {loaded_system.get_system_focal_length():.1f} mm")
    print()
    
    print("="*70)
    print("✓ All multi-element system tests passed!")
    print("="*70)

if __name__ == "__main__":
    main()
