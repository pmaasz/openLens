# openlens API Documentation

Complete API reference for using openlens as a Python library in your own projects.

---

## Table of Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [Core Modules](#core-modules)
  - [Lens Module](#lens-module)
  - [Optical Calculations](#optical-calculations)
  - [Ray Tracing](#ray-tracing)
  - [Aberrations Analysis](#aberrations-analysis)
  - [Material Database](#material-database)
  - [Optical Systems](#optical-systems)
- [Advanced Features](#advanced-features)
- [Examples](#examples)
- [Error Handling](#error-handling)

---

## Installation

### As a Library

To use openlens in your own Python projects:

```bash
# Clone the repository
git clone <repository-url>
cd openLens

# Install as a package
pip install -e .

# Or add the src directory to your Python path
import sys
sys.path.append('/path/to/openLens/src')
```

### Dependencies

**Required:**
- Python 3.6+

**Optional (for full functionality):**
- `matplotlib` - For 3D visualization
- `numpy` - For numerical computations, ray tracing, STL export

---

## Quick Start

```python
from lens_editor import Lens, LensManager
from aberrations import AberrationsCalculator

# Create a lens
lens = Lens(
    name="My Biconvex Lens",
    radius_of_curvature_1=100.0,
    radius_of_curvature_2=-100.0,
    thickness=5.0,
    diameter=50.0,
    material="BK7"
)

# Calculate focal length
focal_length = lens.calculate_focal_length()
print(f"Focal length: {focal_length:.2f} mm")

# Analyze aberrations
calc = AberrationsCalculator(lens)
aberrations = calc.calculate_all_aberrations()
print(f"Spherical aberration: {aberrations['spherical']:.4f}")

# Save lens to file
manager = LensManager()
manager.add_lens(lens)
manager.save_to_file("my_lenses.json")
```

---

## Core Modules

### Lens Module

**Module:** `lens_editor.py`

The `Lens` class represents a single optical lens element.

#### Class: `Lens`

```python
class Lens:
    def __init__(
        self,
        name="Untitled",
        radius_of_curvature_1=100.0,
        radius_of_curvature_2=-100.0,
        thickness=5.0,
        diameter=50.0,
        refractive_index=1.5168,
        lens_type="Biconvex",
        material="BK7",
        wavelength=587.6,
        temperature=20.0
    )
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | str | "Untitled" | Lens identifier |
| `radius_of_curvature_1` | float | 100.0 | Front surface radius (mm), positive=convex |
| `radius_of_curvature_2` | float | -100.0 | Back surface radius (mm), negative=convex |
| `thickness` | float | 5.0 | Center thickness (mm) |
| `diameter` | float | 50.0 | Physical diameter (mm) |
| `refractive_index` | float | 1.5168 | Refractive index at design wavelength |
| `lens_type` | str | "Biconvex" | Lens type classification |
| `material` | str | "BK7" | Optical material name |
| `wavelength` | float | 587.6 | Design wavelength (nm) |
| `temperature` | float | 20.0 | Operating temperature (°C) |

**Attributes:**

- `id` (str): Unique identifier (timestamp-based)
- `created_at` (str): ISO format creation timestamp
- `modified_at` (str): ISO format modification timestamp

**Methods:**

##### `calculate_focal_length()`

Calculate the effective focal length using the thick lens lensmaker's equation.

```python
focal_length = lens.calculate_focal_length()
```

**Returns:** `float` - Focal length in mm (positive=converging, negative=diverging)

**Formula:**
```
1/f = (n-1) * [1/R1 - 1/R2 + (n-1)*d/(n*R1*R2)]
```

##### `calculate_optical_power()`

Calculate optical power in diopters.

```python
power = lens.calculate_optical_power()
```

**Returns:** `float` - Optical power in diopters (D)

**Formula:**
```
P = 1000 / f
```

##### `to_dict()`

Serialize lens to dictionary.

```python
data = lens.to_dict()
```

**Returns:** `dict` - All lens properties as dictionary

##### `from_dict(data)` (classmethod)

Create lens from dictionary.

```python
lens = Lens.from_dict(data)
```

**Parameters:**
- `data` (dict): Dictionary with lens properties

**Returns:** `Lens` - New lens instance

##### `update_refractive_index(wavelength=None, temperature=None)`

Update refractive index for new conditions (requires material database).

```python
lens.update_refractive_index(wavelength=632.8, temperature=25.0)
```

---

#### Class: `LensManager`

```python
class LensManager:
    def __init__(self, filename="lenses.json")
```

Manages a collection of lenses with persistence.

**Methods:**

##### `add_lens(lens)`

Add a lens to the collection.

```python
manager.add_lens(lens)
```

##### `get_lens(lens_id)`

Retrieve a lens by ID.

```python
lens = manager.get_lens("20260206123456789012")
```

**Returns:** `Lens` or `None`

##### `delete_lens(lens_id)`

Remove a lens from collection.

```python
success = manager.delete_lens(lens_id)
```

**Returns:** `bool` - Success status

##### `list_all_lenses()`

Get all lenses in collection.

```python
lenses = manager.list_all_lenses()
```

**Returns:** `list[Lens]`

##### `save_to_file(filename=None)`

Persist lenses to JSON file.

```python
manager.save_to_file("my_lenses.json")
```

##### `load_from_file(filename=None)`

Load lenses from JSON file.

```python
manager.load_from_file("my_lenses.json")
```

---

### Optical Calculations

**Module:** `lens_editor.py`

#### Sign Convention

openlens uses the **Cartesian sign convention**:

- **Positive radius**: Surface center is to the right (convex from left)
- **Negative radius**: Surface center is to the left (concave from left)
- **Positive focal length**: Converging lens
- **Negative focal length**: Diverging lens

#### Thick Lens Formula

For accurate calculations with non-negligible thickness:

```python
# Implemented in Lens.calculate_focal_length()
n = lens.refractive_index
R1 = lens.radius_of_curvature_1
R2 = lens.radius_of_curvature_2
d = lens.thickness

# Calculate power contributions
power1 = (n - 1) / R1
power2 = -(n - 1) / R2
power_spacing = (n - 1) * (n - 1) * d / (n * R1 * R2)

total_power = power1 + power2 + power_spacing
focal_length = 1 / total_power if total_power != 0 else float('inf')
```

---

### Ray Tracing

**Module:** `ray_tracer.py`

Accurate physical ray tracing using Snell's law and vector mathematics.

#### Class: `Ray`

```python
class Ray:
    def __init__(self, origin, direction, wavelength=587.6, intensity=1.0)
```

Represents a light ray.

**Parameters:**
- `origin` (array): 3D starting point [x, y, z]
- `direction` (array): 3D unit direction vector
- `wavelength` (float): Wavelength in nm
- `intensity` (float): Relative intensity (0.0 to 1.0)

**Attributes:**
- `path` (list): List of 3D points along ray path
- `is_blocked` (bool): Whether ray was blocked by aperture

---

#### Class: `LensRayTracer`

```python
class LensRayTracer:
    def __init__(self, lens)
```

Performs ray tracing through a lens.

**Methods:**

##### `trace_parallel_rays(num_rays=11, height_range=None)`

Trace parallel rays (collimated beam).

```python
from ray_tracer import LensRayTracer

tracer = LensRayTracer(lens)
rays = tracer.trace_parallel_rays(num_rays=21, height_range=(-20, 20))
focal_point = tracer.find_focal_point(rays)
```

**Parameters:**
- `num_rays` (int): Number of rays to trace
- `height_range` (tuple): (min_height, max_height) in mm, default uses aperture

**Returns:** `list[Ray]` - Traced rays with paths

##### `trace_point_source(source_position, num_rays=11, angle_range=(-30, 30))`

Trace rays from a point source.

```python
rays = tracer.trace_point_source(
    source_position=[-100, 0, 0],
    num_rays=21,
    angle_range=(-45, 45)
)
```

**Parameters:**
- `source_position` (list): 3D coordinates [x, y, z]
- `num_rays` (int): Number of rays to trace
- `angle_range` (tuple): (min_angle, max_angle) in degrees

**Returns:** `list[Ray]` - Traced rays with paths

##### `find_focal_point(rays, search_range=(0, 500))`

Find focal point from traced rays.

```python
focal_point = tracer.find_focal_point(rays)
if focal_point is not None:
    fx, fy, fz = focal_point
    print(f"Focal point at: x={fx:.2f} mm")
```

**Parameters:**
- `rays` (list[Ray]): Traced rays
- `search_range` (tuple): X-axis range to search (mm)

**Returns:** `array` or `None` - 3D focal point coordinates

##### `trace_ray(ray)`

Trace a single ray through the lens.

```python
ray = Ray(origin=[0, 5, 0], direction=[1, 0, 0])
traced_ray = tracer.trace_ray(ray)
```

**Returns:** `Ray` - Ray with updated path

---

### Aberrations Analysis

**Module:** `aberrations.py`

Calculate and analyze optical aberrations.

#### Class: `AberrationsCalculator`

```python
class AberrationsCalculator:
    def __init__(self, lens, aperture=None, field_angle=0.0)
```

**Parameters:**
- `lens` (Lens): Lens to analyze
- `aperture` (float): Semi-aperture in mm (default: diameter/2)
- `field_angle` (float): Field angle in degrees (default: 0.0)

**Methods:**

##### `calculate_all_aberrations()`

Calculate all five Seidel aberrations.

```python
calc = AberrationsCalculator(lens)
aberrations = calc.calculate_all_aberrations()

print(f"Spherical: {aberrations['spherical']:.4f}")
print(f"Coma: {aberrations['coma']:.4f}")
print(f"Astigmatism: {aberrations['astigmatism']:.4f}")
print(f"Field Curvature: {aberrations['field_curvature']:.4f}")
print(f"Distortion: {aberrations['distortion']:.4f}")
```

**Returns:** `dict` with keys:
- `spherical`: Longitudinal spherical aberration (mm)
- `coma`: Tangential coma (mm)
- `astigmatism`: Astigmatic difference (mm)
- `field_curvature`: Petzval curvature (mm⁻¹)
- `distortion`: Percent distortion (%)

##### `calculate_chromatic_aberration(wavelength1=486.1, wavelength2=656.3)`

Calculate chromatic aberration.

```python
chrom_aberr = calc.calculate_chromatic_aberration()
```

**Parameters:**
- `wavelength1` (float): Blue wavelength (nm), default F-line
- `wavelength2` (float): Red wavelength (nm), default C-line

**Returns:** `float` - Axial chromatic aberration (mm)

##### `calculate_spot_size()`

Calculate geometric spot size at best focus.

```python
spot_size = calc.calculate_spot_size()
```

**Returns:** `float` - RMS spot diameter (mm)

##### `calculate_diffraction_limit()`

Calculate Airy disk diameter.

```python
airy_diameter = calc.calculate_diffraction_limit()
```

**Returns:** `float` - Airy disk diameter (µm)

---

#### Function: `analyze_lens_quality(lens, verbose=False)`

Perform comprehensive lens quality analysis.

```python
from aberrations import analyze_lens_quality

quality = analyze_lens_quality(lens, verbose=True)

print(f"Overall Quality Score: {quality['overall_score']}/100")
print(f"Quality Rating: {quality['quality_rating']}")
print(f"Diffraction Limited: {quality['is_diffraction_limited']}")
```

**Returns:** `dict` with keys:
- `overall_score` (float): 0-100 quality score
- `quality_rating` (str): "Excellent", "Good", "Fair", or "Poor"
- `is_diffraction_limited` (bool): Performance limited by diffraction
- `aberrations` (dict): All aberration values
- `f_number` (float): F-number (f/#)
- `numerical_aperture` (float): NA value
- `airy_disk_diameter_um` (float): Diffraction limit (µm)
- `recommendations` (list): Improvement suggestions

---

### Material Database

**Module:** `material_database.py`

Access optical material properties with wavelength and temperature dependence.

#### Class: `MaterialDatabase`

```python
from material_database import get_material_database

db = get_material_database()
```

**Methods:**

##### `get_available_materials()`

List all available materials.

```python
materials = db.get_available_materials()
print(materials)  # ['BK7', 'Fused Silica', 'SF11', ...]
```

**Returns:** `list[str]`

##### `get_material(material_name)`

Get material properties.

```python
material = db.get_material("BK7")
print(f"Abbe number: {material['abbe_number']}")
print(f"Base refractive index: {material['refractive_index']}")
```

**Returns:** `dict` with keys:
- `name` (str): Material name
- `refractive_index` (float): Base index at 587.6 nm
- `abbe_number` (float): Abbe number (Vd)
- `dispersion_formula` (str): Formula type
- `sellmeier_coefficients` (dict): Sellmeier equation coefficients
- `thermal_coefficient` (float): dn/dT (1/°C)

##### `get_refractive_index(material_name, wavelength=587.6, temperature=20.0)`

Calculate refractive index at specific conditions.

```python
n = db.get_refractive_index("BK7", wavelength=632.8, temperature=25.0)
print(f"n @ 632.8nm, 25°C: {n:.6f}")
```

**Parameters:**
- `material_name` (str): Material name
- `wavelength` (float): Wavelength in nm
- `temperature` (float): Temperature in °C

**Returns:** `float` - Refractive index

##### `get_abbe_number(material_name)`

Get Abbe number (dispersion measure).

```python
vd = db.get_abbe_number("BK7")
print(f"Abbe number: {vd:.2f}")
```

**Returns:** `float` - Abbe number (Vd)

---

### Optical Systems

**Module:** `optical_system.py`

Multi-element optical systems.

#### Class: `OpticalSystem`

```python
from optical_system import OpticalSystem

system = OpticalSystem(name="My Doublet")
system.add_element(lens1, position=0.0)
system.add_element(lens2, position=10.0)
```

**Methods:**

##### `add_element(lens, position=0.0)`

Add a lens element at specified position.

**Parameters:**
- `lens` (Lens): Lens element to add
- `position` (float): Z-position along optical axis (mm)

##### `calculate_system_focal_length()`

Calculate effective focal length of the system.

```python
f_system = system.calculate_system_focal_length()
```

**Returns:** `float` - System focal length (mm)

##### `trace_through_system(rays)`

Trace rays through all elements.

```python
rays = [Ray([0, 5, 0], [1, 0, 0]) for _ in range(10)]
traced_rays = system.trace_through_system(rays)
```

**Returns:** `list[Ray]` - Rays traced through entire system

---

## Advanced Features

### STL Export

**Module:** `stl_export.py`

Export lens geometry to STL format for 3D printing or CAD.

```python
from stl_export import export_lens_stl

export_lens_stl(
    lens,
    filename="my_lens.stl",
    resolution=100,
    mount_thickness=2.0
)
```

**Parameters:**
- `lens` (Lens): Lens to export
- `filename` (str): Output STL filename
- `resolution` (int): Mesh resolution (vertices per surface)
- `mount_thickness` (float): Optional mounting ring thickness (mm)

---

### Coating Designer

**Module:** `coating_designer.py`

Design anti-reflection and dielectric coatings.

```python
from coating_designer import CoatingDesigner

designer = CoatingDesigner(lens)
designer.add_layer(material="MgF2", thickness=110.0)  # nm
transmittance = designer.calculate_transmittance(wavelength=550.0)
```

---

### Image Simulator

**Module:** `image_simulator.py`

Simulate image formation through lens systems.

```python
from image_simulator import ImageSimulator

simulator = ImageSimulator(lens)
image = simulator.simulate_image(
    object_distance=200.0,
    object_size=10.0,
    resolution=512
)
```

---

### Performance Metrics

**Module:** `performance_metrics.py`

Calculate MTF, PSF, and other performance metrics.

```python
from performance_metrics import calculate_mtf

mtf = calculate_mtf(lens, spatial_frequency=100)  # lp/mm
```

---

## Examples

### Example 1: Design and Analyze a Lens

```python
from lens_editor import Lens
from aberrations import analyze_lens_quality

# Create a biconvex lens
lens = Lens(
    name="Test Biconvex",
    radius_of_curvature_1=50.0,
    radius_of_curvature_2=-50.0,
    thickness=6.0,
    diameter=25.0,
    material="BK7"
)

# Calculate properties
f = lens.calculate_focal_length()
power = lens.calculate_optical_power()

print(f"Focal length: {f:.2f} mm")
print(f"Optical power: {power:.2f} D")

# Analyze quality
quality = analyze_lens_quality(lens, verbose=True)
print(f"\nQuality score: {quality['overall_score']:.1f}/100")
print(f"Rating: {quality['quality_rating']}")

# Show recommendations
for rec in quality['recommendations']:
    print(f"  • {rec}")
```

### Example 2: Ray Tracing Simulation

```python
from lens_editor import Lens
from ray_tracer import LensRayTracer

# Create lens
lens = Lens(
    name="Ray Trace Demo",
    radius_of_curvature_1=100.0,
    radius_of_curvature_2=-100.0,
    thickness=5.0,
    diameter=40.0,
    material="BK7"
)

# Trace parallel rays
tracer = LensRayTracer(lens)
rays = tracer.trace_parallel_rays(num_rays=21, height_range=(-15, 15))

# Find focal point
focal_point = tracer.find_focal_point(rays)
if focal_point is not None:
    print(f"Focal point: {focal_point[0]:.2f} mm")
    print(f"Calculated focal length: {lens.calculate_focal_length():.2f} mm")
    
    # Calculate spot size at focus
    spot_size = 0
    for ray in rays:
        if ray.path:
            fy = ray.path[-1][1]
            spot_size = max(spot_size, abs(fy))
    print(f"Spot radius: {spot_size:.4f} mm")
```

### Example 3: Material Properties

```python
from material_database import get_material_database

db = get_material_database()

# Compare materials at different wavelengths
materials = ["BK7", "Fused Silica", "SF11"]
wavelengths = [486.1, 587.6, 656.3]  # F, d, C lines

print("Material | F-line | d-line | C-line | Abbe #")
print("-" * 55)

for mat in materials:
    indices = [db.get_refractive_index(mat, wl) for wl in wavelengths]
    abbe = db.get_abbe_number(mat)
    print(f"{mat:12} | {indices[0]:.4f} | {indices[1]:.4f} | {indices[2]:.4f} | {abbe:.2f}")
```

### Example 4: Multi-Element System

```python
from lens_editor import Lens
from optical_system import OpticalSystem

# Create doublet lens system
lens1 = Lens(
    name="Crown Element",
    radius_of_curvature_1=50.0,
    radius_of_curvature_2=-100.0,
    thickness=4.0,
    diameter=25.0,
    material="BK7"
)

lens2 = Lens(
    name="Flint Element",
    radius_of_curvature_1=100.0,
    radius_of_curvature_2=-50.0,
    thickness=2.0,
    diameter=25.0,
    material="SF11"
)

# Create system
system = OpticalSystem(name="Achromatic Doublet")
system.add_element(lens1, position=0.0)
system.add_element(lens2, position=4.1)  # 0.1mm air gap

# Calculate system properties
f_system = system.calculate_system_focal_length()
print(f"System focal length: {f_system:.2f} mm")
```

### Example 5: Batch Processing

```python
from lens_editor import Lens, LensManager
from aberrations import analyze_lens_quality
import json

# Create a series of lenses with varying parameters
manager = LensManager("lens_family.json")

for r1 in range(40, 120, 20):
    lens = Lens(
        name=f"Biconvex_R{r1}",
        radius_of_curvature_1=float(r1),
        radius_of_curvature_2=float(-r1),
        thickness=5.0,
        diameter=25.0,
        material="BK7"
    )
    manager.add_lens(lens)

# Analyze all lenses
results = []
for lens in manager.list_all_lenses():
    quality = analyze_lens_quality(lens)
    results.append({
        'name': lens.name,
        'focal_length': lens.calculate_focal_length(),
        'quality_score': quality['overall_score'],
        'rating': quality['quality_rating']
    })

# Save results
with open('analysis_results.json', 'w') as f:
    json.dump(results, f, indent=2)

# Find best performer
best = max(results, key=lambda x: x['quality_score'])
print(f"Best lens: {best['name']} (score: {best['quality_score']:.1f})")
```

---

## Error Handling

### Common Exceptions

#### Invalid Lens Parameters

```python
try:
    lens = Lens(radius_of_curvature_1=0)  # Invalid!
except ValueError as e:
    print(f"Invalid parameter: {e}")
```

#### Missing Material

```python
from material_database import get_material_database

db = get_material_database()
try:
    n = db.get_refractive_index("NonExistentGlass")
except KeyError as e:
    print(f"Material not found: {e}")
    # Fallback to default
    n = 1.5168
```

#### Ray Tracing Failures

```python
from ray_tracer import LensRayTracer

tracer = LensRayTracer(lens)
rays = tracer.trace_parallel_rays()

if not rays:
    print("Warning: No rays successfully traced")
    
focal_point = tracer.find_focal_point(rays)
if focal_point is None:
    print("Warning: Could not determine focal point")
    # Use calculated value instead
    focal_length = lens.calculate_focal_length()
```

### Best Practices

1. **Always validate user input** before creating lenses
2. **Check return values** for None before using
3. **Use try-except** for file operations
4. **Verify material availability** before creating lenses with custom materials
5. **Set reasonable defaults** for optional parameters

---

## API Version

**Current Version:** 2.0.0

### Version History

- **2.0.0** - Major feature additions (ray tracing, aberrations, material database)
- **1.2.0** - Ray tracing implementation
- **1.1.0** - Aberrations calculator
- **1.0.0** - Initial release

---

## Support

For issues, questions, or feature requests:
- Check the [main README](../README.md) for usage examples
- Review [TESTING.md](TESTING.md) for test coverage details
- See [ARCHITECTURE.md](ARCHITECTURE.md) for design documentation

---

**Last Updated:** February 2026
