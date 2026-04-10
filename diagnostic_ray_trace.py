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
    
    # Second element
    lens2 = Lens(
        name="Nikon 50mm Element 2",
        radius_of_curvature_1=30.0,
        radius_of_curvature_2=-30.0,
        thickness=5.0,
        diameter=40.0,
        refractive_index=1.62
    )
    
    system = OpticalSystem("Nikon Test")
    system.add_lens(lens1, air_gap_before=0)
    system.add_lens(lens2, air_gap_before=10.0)
    
    # Trace through system
    tracer = SystemRayTracer(system)
    
    print(f"Tracing through system: {system.name}")
    
    num_rays = 5
    rays = tracer.trace_parallel_rays(num_rays=num_rays)
    
    for r_idx, ray in enumerate(rays):
        print(f"\nRay {r_idx} path ({len(ray.path)} points):")
        for i, (x, y) in enumerate(ray.path):
            print(f"  Point {i}: x={x:.2f}, y={y:.2f}")
        
        if ray.terminated:
             print(f"Ray {r_idx} TERMINATED")
        
        # Success if it reached past second lens
        if len(ray.path) >= 6:
            print(f"Ray {r_idx} SUCCESS")
        else:
            print(f"Ray {r_idx} FAILURE")

if __name__ == "__main__":
    run_diagnostic()
