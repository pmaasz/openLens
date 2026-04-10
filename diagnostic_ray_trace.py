#!/usr/bin/env python3
"""
Diagnostic script to test ray propagation through a multi-element optical system.
"""

import sys
import os
import math

sys.path.insert(0, os.path.join(os.getcwd(), 'src'))

from lens import Lens
from optical_system import OpticalSystem
from ray_tracer import Ray, LensRayTracer, SystemRayTracer

def run_diagnostic():
    # Recreate the first element of Nikon 50mm
    # id: 20260408230150773216, name: Nikon 50mm first element, 
    # radius1: -100.0, radius2: 0.0, thickness: 5.0, diameter: 40.0, material: F2, n: 1.62
    
    lens1 = Lens(
        name="Nikon 50mm Element 1",
        radius_of_curvature_1=-100.0,
        radius_of_curvature_2=0.0,
        thickness=5.0,
        diameter=40.0,
        refractive_index=1.62
    )
    
    # Second element (smaller diameter)
    lens2 = Lens(
        name="Small Pupil Element",
        radius_of_curvature_1=30.0,
        radius_of_curvature_2=-30.0,
        thickness=5.0,
        diameter=20.0, # Smaller aperture!
        refractive_index=1.5
    )
    
    # Third element (at x=40)
    lens3 = Lens(
        name="Rear Element",
        radius_of_curvature_1=50.0,
        radius_of_curvature_2=-50.0,
        thickness=5.0,
        diameter=40.0,
        refractive_index=1.5
    )
    
    system = OpticalSystem("Aperture Test")
    system.add_lens(lens1, air_gap_before=0)     # x=0, d=40
    system.add_lens(lens2, air_gap_before=10.0)  # x=15, d=20 (smaller)
    system.add_lens(lens3, air_gap_before=20.0)  # x=40, d=40 (larger)
    
    # Trace through system
    tracer = SystemRayTracer(system)
    
    print(f"Tracing through system: {system.name}")
    print("Goal: Rays should NOT terminate if they miss the small lens2.")
    
    num_rays = 7
    rays = tracer.trace_parallel_rays(num_rays=num_rays)
    
    for r_idx, ray in enumerate(rays):
        print(f"\nRay {r_idx} starting height: {ray.path[0][1]:.2f}")
        print(f"Path points: {len(ray.path)}")
        for i, (x, y) in enumerate(ray.path):
            print(f"  Point {i}: x={x:.2f}, y={y:.2f}")
        
        # Check if ray continued until the end (x > 45)
        if ray.path[-1][0] > 100:
            print(f"Ray {r_idx} SUCCESS: Propagated through system.")
        else:
            print(f"Ray {r_idx} FAILURE: Stopped at x={ray.path[-1][0]:.2f}")

if __name__ == "__main__":
    run_diagnostic()
