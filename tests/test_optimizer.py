#!/usr/bin/env python3
"""
Test optimization engine
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src'))

from optical_system import create_doublet
from optimizer import (
    OptimizationVariable, OptimizationTarget, 
    LensOptimizer, create_doublet_optimizer
)

def main():
    print("="*70)
    print("OPTICAL OPTIMIZATION ENGINE TEST")
    print("="*70)
    print()
    
    # Create initial doublet design - deliberately suboptimal
    print("Creating initial (suboptimal) achromatic doublet...")
    from lens_editor import Lens
    from optical_system import OpticalSystem
    
    # Create a suboptimal doublet to show improvement
    crown = Lens(name="Crown", radius_of_curvature_1=80, radius_of_curvature_2=-120,
                thickness=8, diameter=50, material="BK7")
    flint = Lens(name="Flint", radius_of_curvature_1=-120, radius_of_curvature_2=150,
                thickness=5, diameter=50, material="SF11")
    
    doublet = OpticalSystem(name="Doublet")
    doublet.add_lens(crown)
    doublet.add_lens(flint, air_gap_before=0)
    
    print(f"Initial design:")
    print(f"  System focal length: {doublet.get_system_focal_length():.2f} mm")
    chrom_initial = doublet.calculate_chromatic_aberration()
    print(f"  Chromatic aberration: {chrom_initial['longitudinal']:.4f} mm")
    print(f"  Achromatic: {chrom_initial['corrected']}")
    print()
    
    # Show initial lens parameters
    print("Initial lens parameters:")
    for i, elem in enumerate(doublet.elements):
        print(f"  Element {i+1} ({elem.lens.material}):")
        print(f"    R1: {elem.lens.radius_of_curvature_1:.2f} mm")
        print(f"    R2: {elem.lens.radius_of_curvature_2:.2f} mm")
        print(f"    Thickness: {elem.lens.thickness:.2f} mm")
    print()
    
    # Create optimizer
    print("Setting up optimizer...")
    optimizer = create_doublet_optimizer(doublet, target_focal_length=100.0)
    
    print(f"Optimization variables: {len(optimizer.variables)}")
    for var in optimizer.variables:
        print(f"  {var.name}: {var.current_value:.2f} [{var.min_value:.0f}, {var.max_value:.0f}]")
    
    print(f"\nOptimization targets: {len(optimizer.targets)}")
    for target in optimizer.targets:
        print(f"  {target.name}: {target.target_type} (weight={target.weight})")
    print()
    
    # Run optimization with simplex method
    print("Running Nelder-Mead simplex optimization...")
    print("-" * 70)
    
    result = optimizer.optimize_simplex(max_iterations=50, tolerance=1e-6)
    
    print(f"\nOptimization complete!")
    print(f"  Status: {'SUCCESS' if result.success else 'FAILED'}")
    print(f"  Iterations: {result.iterations}")
    print(f"  Initial merit: {result.initial_merit:.6f}")
    print(f"  Final merit: {result.final_merit:.6f}")
    print(f"  Improvement: {result.improvement:.2f}%")
    print(f"  Message: {result.message}")
    print()
    
    # Show optimized design
    print("Optimized lens parameters:")
    optimized = result.optimized_system
    for i, elem in enumerate(optimized.elements):
        print(f"  Element {i+1} ({elem.lens.material}):")
        print(f"    R1: {elem.lens.radius_of_curvature_1:.2f} mm")
        print(f"    R2: {elem.lens.radius_of_curvature_2:.2f} mm")
        print(f"    Thickness: {elem.lens.thickness:.2f} mm")
    print()
    
    # Compare performance
    print("Performance comparison:")
    print("-" * 70)
    
    f_initial = doublet.get_system_focal_length()
    f_optimized = optimized.get_system_focal_length()
    print(f"  Focal length:")
    print(f"    Initial: {f_initial:.2f} mm")
    print(f"    Optimized: {f_optimized:.2f} mm")
    print(f"    Error: {abs(f_optimized - 100):.2f} mm")
    
    chrom_optimized = optimized.calculate_chromatic_aberration()
    print(f"\n  Chromatic aberration:")
    print(f"    Initial: {chrom_initial['longitudinal']:.6f} mm")
    print(f"    Optimized: {chrom_optimized['longitudinal']:.6f} mm")
    print(f"    Reduction: {(1 - chrom_optimized['longitudinal']/max(chrom_initial['longitudinal'], 1e-10))*100:.1f}%")
    
    print()
    print("Merit function history (first 10 and last 10):")
    history = result.merit_history
    if len(history) <= 20:
        for i, merit in enumerate(history):
            print(f"  Iteration {i}: {merit:.6f}")
    else:
        for i in range(10):
            print(f"  Iteration {i}: {history[i]:.6f}")
        print("  ...")
        for i in range(len(history)-10, len(history)):
            print(f"  Iteration {i}: {history[i]:.6f}")
    
    print()
    print("="*70)
    print("✓ Optimization engine test complete!")
    print("="*70)

if __name__ == "__main__":
    main()
