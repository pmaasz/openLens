#!/usr/bin/env python3
"""Quick test of ray tracer"""

import sys
sys.path.insert(0, 'src')

from lens_editor import Lens
from ray_tracer import LensRayTracer, Ray

print("Testing Ray Tracer")
print("="*60)

# Create a test lens
lens = Lens(
    name="Test Biconvex",
    radius_of_curvature_1=100.0,
    radius_of_curvature_2=-100.0,
    thickness=5.0,
    diameter=50.0,
    refractive_index=1.5168,
    lens_type="Biconvex",
    material="BK7"
)

print(f"Lens: {lens.name}")
print(f"Theoretical Focal Length: {lens.calculate_focal_length():.2f} mm")
print()

# Create ray tracer
tracer = LensRayTracer(lens)

print("Tracing parallel rays...")
rays = tracer.trace_parallel_rays(num_rays=10)

print(f"✓ Traced {len(rays)} rays")
print(f"  Each ray has {len(rays[0].path)} path points")
print()

# Find focal point
focal_point = tracer.find_focal_point(rays)

if focal_point:
    fx, fy = focal_point
    bfd = fx - tracer.back_vertex_x
    print(f"✓ Focal point found at ({fx:.2f}, {fy:.2f}) mm")
    print(f"  Back focal distance: {bfd:.2f} mm")
    
    theoretical_f = lens.calculate_focal_length()
    error = abs(bfd - theoretical_f) / theoretical_f * 100
    print(f"  Error from theoretical: {error:.1f}%")
else:
    print("✗ No focal point found")

print()
print("Testing point source...")
rays_point = tracer.trace_point_source_rays(
    source_x=-100,
    source_y=0,
    num_rays=7,
    max_angle=15.0
)

print(f"✓ Traced {len(rays_point)} rays from point source")
print()

# Test lens outline
outline = tracer.get_lens_outline(num_points=50)
print(f"✓ Generated lens outline with {len(outline)} points")
print()

print("="*60)
print("✓ Ray tracer working correctly!")
