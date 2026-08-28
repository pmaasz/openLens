"""
Ray Tracing Engine for Optical Lens Simulation

Backward-compatibility shim.  All implementation has been split into:

- src/ray.py            — RefractionResult, OpticalIntersector, Ray, Ray3D
- src/tracer_2d.py      — LensRayTracer, SystemRayTracer
- src/tracer_3d.py      — LensRayTracer3D, SystemRayTracer3D

Existing ``from .ray_tracer import …`` statements continue to work.
"""

# Re-export everything so existing imports are unaffected
from .ray import (  # noqa: F401
    RefractionResult,
    OpticalIntersector,
    Ray,
    Ray3D,
    HAS_POLARIZATION,
)
from .tracer_2d import LensRayTracer, SystemRayTracer  # noqa: F401
from .tracer_3d import LensRayTracer3D, SystemRayTracer3D  # noqa: F401
