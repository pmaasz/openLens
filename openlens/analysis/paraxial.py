"""One paraxial-focus search for the analysis modules.

The spot diagram, geometric analysis and the wavefront sensor each traced a
near-axis ray to place the image plane. The copies had drifted apart: launch
offsets of 10 mm and 20 mm, collimation thresholds of 1e-9 and 1e-12, and
only some of them updated the lens indices for the wavelength they traced at
(the wavelength-dispersion bug). This module is the single implementation;
the constants live in ``openlens/constants.py``.
"""

import logging
import math
from typing import Optional

from ..constants import (
    NM_TO_MM,
    PARAXIAL_COLLIMATION_EPSILON,
    PARAXIAL_LAUNCH_OFFSET_MM,
    WAVELENGTH_GREEN,
)
from ..optical_system import OpticalSystem
from ..ray_tracer import Ray3D, SystemRayTracer3D
from ..vector3 import vec3

logger = logging.getLogger(__name__)


def resolve_image_plane_x(
    system: OpticalSystem,
    wavelength_nm: float = WAVELENGTH_GREEN,
    tracer: Optional[SystemRayTracer3D] = None,
) -> Optional[float]:
    """Return the configured detector plane, else the paraxial focus.

    ``OpticalSystem.image_plane_x_mm`` names the plane where a detector sits.
    Analyses that need an image plane call this so the stored plane wins over
    the paraxial focus, and a non-finite stored value is ignored rather than
    propagating NaN into every spot.

    Args:
        system: System whose plane is resolved.
        wavelength_nm: Wavelength used for the paraxial fallback, in nm.
        tracer: Optional tracer to reuse for the paraxial fallback.

    Returns:
        The configured plane or paraxial focus in mm, or None when neither
        exists.
    """
    plane = getattr(system, "image_plane_x_mm", None)
    if plane is not None:
        try:
            plane = float(plane)
        except (TypeError, ValueError):
            plane = None
        if plane is not None and math.isfinite(plane):
            return plane
        logger.warning(
            "Ignoring non-finite image plane %r; using the paraxial focus",
            getattr(system, "image_plane_x_mm", None),
        )
    return find_paraxial_focus(system, wavelength_nm, tracer=tracer)


def find_paraxial_focus(
    system: OpticalSystem,
    wavelength_nm: float = WAVELENGTH_GREEN,
    tracer: Optional[SystemRayTracer3D] = None,
) -> Optional[float]:
    """Return the x position where a near-axis ray crosses the optical axis.

    The ray starts 0.001 mm above the axis, ``PARAXIAL_LAUNCH_OFFSET_MM``
    before the first surface, and the axis crossing is interpolated from the
    last traced segment. The lenses are temporarily set to ``wavelength_nm``;
    their wavelength and refractive index are restored on the way out, so a
    caller that already swapped the system for the same wavelength keeps its
    state.

    Args:
        system: System to trace through.
        wavelength_nm: Wavelength to focus, in nanometres.
        tracer: Optional tracer to reuse; one is built when omitted.

    Returns:
        Focus x in mm, or None when the exit ray is collimated, blocked or
        too short to interpolate. Callers pick their own fallback: "no
        focus" means different things to a detector, a plot and a reference
        sphere.
    """
    if not system.elements:
        return None

    if tracer is None:
        tracer = SystemRayTracer3D(system)

    saved = [
        (element.lens, element.lens.wavelength, element.lens.refractive_index)
        for element in system.elements
    ]
    try:
        for element in system.elements:
            element.lens.update_refractive_index(wavelength_nm=wavelength_nm)

        start_x = system.elements[0].position - PARAXIAL_LAUNCH_OFFSET_MM
        ray = Ray3D(
            vec3(start_x, 0.001, 0),
            vec3(1, 0, 0),
            wavelength=wavelength_nm * NM_TO_MM,
        )
        tracer.trace_ray(ray)

        if ray.terminated or len(ray.path) < 2:
            logger.debug("Paraxial ray did not reach the exit; no focus")
            return None

        p2 = ray.path[-1]
        p1 = ray.path[-2]
        dx = p2.x - p1.x
        dy = p2.y - p1.y
        if abs(dy) <= PARAXIAL_COLLIMATION_EPSILON or abs(dx) <= PARAXIAL_COLLIMATION_EPSILON:
            logger.debug("Paraxial exit ray is collimated; no finite focus")
            return None
        return p1.x - p1.y * (dx / dy)
    finally:
        for lens, wavelength, index in saved:
            lens.wavelength = wavelength
            lens.refractive_index = index
