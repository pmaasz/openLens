# OpenLens Python API

> **The authoritative API reference is
> [`docs/sphinx/source/api/index.rst`](sphinx/source/api/index.rst).**
> It is generated from the source docstrings. This file is kept as a short
> entry point for links to `docs/API_DOCUMENTATION.md`.

## Install

```bash
pip install -e .
pip install -e .[visualization]   # numpy + matplotlib
```

## First lens

```python
from openlens.lens import Lens

lens = Lens(
    name="Biconvex demo",
    radius_of_curvature_1=50.0,
    radius_of_curvature_2=-50.0,
    thickness=5.0,
    diameter=25.0,
    material="BK7",
)

print(lens.calculate_focal_length())
print(lens.calculate_back_focal_length())
print(lens.calculate_working_flange_distance())
```

## Trace rays

```python
from openlens.ray_tracer import LensRayTracer

tracer = LensRayTracer(lens)
rays = tracer.trace_parallel_rays(num_rays=11)
```

## Analyze image quality

```python
from openlens.aberrations import AberrationsCalculator
from openlens.performance_metrics import PerformanceMetrics

aberrations = AberrationsCalculator(lens).calculate_all_aberrations(field_angle_deg=5.0)
report = PerformanceMetrics(lens).format_metrics_report()
```

Failed traces and undefined quantities return `None`; check before formatting.
For multi-element systems, use `OpticalSystem` from
`openlens.optical_system`. For persistence, use `DatabaseManager` or the GUI
`LensStorage` facade; JSON is an interchange format, not primary state.
