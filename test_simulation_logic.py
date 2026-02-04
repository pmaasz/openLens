#!/usr/bin/env python3
"""
Automated test that simulates clicking the Run Simulation button
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from lens_editor import Lens
from ray_tracer import LensRayTracer

print("="*70)
print("AUTOMATED SIMULATION TEST")
print("="*70)
print()

# Create a test lens
lens = Lens(
    name="Auto Test Lens",
    radius_of_curvature_1=100,
    radius_of_curvature_2=-100,
    thickness=10,
    diameter=50,
    material="BK7"
)

print(f"Created lens: {lens.name}")
print(f"  R1: {lens.radius_of_curvature_1} mm")
print(f"  R2: {lens.radius_of_curvature_2} mm")
print(f"  Thickness: {lens.thickness} mm")
print(f"  Diameter: {lens.diameter} mm")
print()

# Simulate what run_simulation() does
print("Step 1: Check prerequisites...")
try:
    from src.ray_tracer import LensRayTracer
    RAY_TRACING_AVAILABLE = True
    print("  ✓ Ray tracer available")
except:
    RAY_TRACING_AVAILABLE = False
    print("  ✗ Ray tracer NOT available")

try:
    import matplotlib
    VISUALIZATION_AVAILABLE = True
    print("  ✓ Matplotlib available")
except:
    VISUALIZATION_AVAILABLE = False
    print("  ✗ Matplotlib NOT available")

if not RAY_TRACING_AVAILABLE or not VISUALIZATION_AVAILABLE:
    print("\n✗ Cannot run simulation - missing dependencies")
    sys.exit(1)

print()
print("Step 2: Get simulation parameters...")
num_rays = 11
ray_angle = 0
print(f"  Number of rays: {num_rays}")
print(f"  Ray angle: {ray_angle}°")

print()
print("Step 3: Create ray tracer...")
tracer = LensRayTracer(lens)
print(f"  ✓ Ray tracer created")

print()
print("Step 4: Trace rays...")
if abs(ray_angle) < 0.1:
    rays = tracer.trace_parallel_rays(num_rays=num_rays)
    focal_point = tracer.find_focal_point(rays)
    print(f"  ✓ Traced {len(rays)} parallel rays")
    print(f"  Focal point: {focal_point}")
else:
    source_x = -100.0
    source_y = 0
    rays = tracer.trace_point_source_rays(source_x, source_y, num_rays=num_rays, max_angle=abs(ray_angle))
    focal_point = None
    print(f"  ✓ Traced {len(rays)} point source rays")

print()
print("Step 5: Get lens outline...")
lens_outline = tracer.get_lens_outline()
print(f"  ✓ Got {len(lens_outline) if lens_outline else 0} outline points")

print()
print("Step 6: Prepare visualization data...")
if lens_outline:
    xs = [p[0] for p in lens_outline]
    ys = [p[1] for p in lens_outline]
    print(f"  Lens X range: [{min(xs):.1f}, {max(xs):.1f}]")
    print(f"  Lens Y range: [{min(ys):.1f}, {max(ys):.1f}]")

print(f"  Ray path segments:")
for i, ray in enumerate(rays[:3]):  # Show first 3 rays
    print(f"    Ray {i}: {len(ray.path)} segments")
    if len(ray.path) > 0:
        print(f"      Start: ({ray.path[0][0]:.1f}, {ray.path[0][1]:.1f})")
        print(f"      End:   ({ray.path[-1][0]:.1f}, {ray.path[-1][1]:.1f})")

print()
print("="*70)
print("✓ ALL SIMULATION STEPS COMPLETED SUCCESSFULLY!")
print("="*70)
print()
print("The simulation logic works. If the GUI isn't showing the plot,")
print("the issue is in the matplotlib canvas rendering or update.")
print()
