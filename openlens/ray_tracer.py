"""
Ray Tracing Engine for Optical Lens Simulation

Backward-compatibility shim.  All implementation has been split into:

- openlens/ray.py            — RefractionResult, OpticalIntersector, Ray, Ray3D
- openlens/tracer_2d.py      — LensRayTracer, SystemRayTracer
- openlens/tracer_3d.py      — LensRayTracer3D, SystemRayTracer3D

Existing ``from .ray_tracer import …`` statements continue to work.
"""

# Re-export everything so existing imports are unaffected
from .vector3 import Vector3, vec3  # noqa: F401
from .transform import Matrix4x4  # noqa: F401
from .ray import (  # noqa: F401
    RefractionResult,
    OpticalIntersector,
    Ray,
    Ray3D,
    HAS_POLARIZATION,
)
from .tracer_2d import LensRayTracer, SystemRayTracer  # noqa: F401
from .tracer_3d import LensRayTracer3D, SystemRayTracer3D  # noqa: F401
