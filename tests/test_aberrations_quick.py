#!/usr/bin/env python3
"""Quick test of aberrations calculator"""

import sys
sys.path.insert(0, 'src')

from lens_editor import Lens
from aberrations import AberrationsCalculator, analyze_lens_quality

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

print("Testing Aberrations Calculator")
print("="*60)
print(f"Lens: {lens.name}")
print(f"Focal Length: {lens.calculate_focal_length():.2f} mm")
print()

# Test aberrations calculator
calc = AberrationsCalculator(lens)
results = calc.calculate_all_aberrations(field_angle=5.0)

print("Aberration Results:")
for key, value in results.items():
    if value is not None and not isinstance(value, str):
        print(f"  {key}: {value}")

print()
print("="*60)
print("Full Summary:")
print(calc.get_aberration_summary(field_angle=5.0))

print()
print("="*60)
print("Quality Analysis:")
quality = analyze_lens_quality(lens, field_angle=5.0)
print(f"Score: {quality['quality_score']}/100")
print(f"Rating: {quality['rating']}")
print(f"Issues: {quality['issues']}")

print("\n✓ Aberrations calculator working!")
