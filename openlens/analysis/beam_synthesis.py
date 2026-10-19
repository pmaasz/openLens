import logging
import math
from typing import Tuple, Optional, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)

try:
    import numpy as np

    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

    # Minimal stand-in so the graceful-degradation returns below actually work.
    # The old dummy declared only `ndarray`, so every "return an empty result"
    # path raised AttributeError: type object 'np' has no attribute 'array' -
    # the exact opposite of graceful degradation. These return plain Python
    # lists, which is all an empty-result caller can use anyway.
    class np:  # noqa: N801 - deliberately mirrors the numpy name
        """Just enough numpy for the empty/degraded return paths."""

        ndarray = Any
        float64 = float
        inf = float("inf")

        @staticmethod
        def array(values, dtype=None):
            return list(values)

        @staticmethod
        def zeros(shape, dtype=None):
            if isinstance(shape, int):
                return [0.0] * shape
            rows, cols = shape
            return [[0.0] * cols for _ in range(rows)]

        @staticmethod
        def ones(shape, dtype=None):
            if isinstance(shape, int):
                return [1.0] * shape
            rows, cols = shape
            return [[1.0] * cols for _ in range(rows)]

        @staticmethod
        def linspace(start, stop, num=50, dtype=None):
            if num <= 1:
                return [float(start)]
            step = (stop - start) / (num - 1)
            return [start + step * i for i in range(num)]

        @staticmethod
        def meshgrid(x, y):
            return [[value for value in x] for _ in y], [[value for _ in x] for value in y]


from ..vector3 import vec3
from ..ray_tracer import RefractionResult, Ray3D, LensRayTracer3D, SystemRayTracer3D
from ..optical_system import OpticalSystem
from ..constants import NM_TO_MM, WAVELENGTH_GREEN


@dataclass
class GaussianBeam:
    """
    Represents a fundamental Gaussian Beam (TEM00).
    Uses complex curvature parameter q.
    1/q = 1/R - i * lambda / (pi * w^2)
    """

    wavelength: float  # LOCAL wavelength in mm (vacuum / n)
    q_x: complex  # Complex beam parameter in X (meridional)
    q_y: complex  # Complex beam parameter in Y (sagittal)
    ray: Ray3D  # Central ray carrying the beam
    n: float = 1.0  # LOCAL refractive index q is defined against

    @property
    def w_x(self) -> float:
        """Beam radius (1/e^2 intensity) in X plane"""
        if self.q_x.imag == 0:
            return 0.0
        return math.sqrt(-self.wavelength / (math.pi * (1.0 / self.q_x).imag))

    @property
    def w_y(self) -> float:
        """Beam radius (1/e^2 intensity) in Y plane"""
        if self.q_y.imag == 0:
            return 0.0
        return math.sqrt(-self.wavelength / (math.pi * (1.0 / self.q_y).imag))

    @property
    def R_x(self) -> float:
        """Radius of curvature of wavefront in X plane"""
        inv_q = 1.0 / self.q_x
        if inv_q.real == 0:
            return float("inf")
        return 1.0 / inv_q.real

    @property
    def R_y(self) -> float:
        """Radius of curvature of wavefront in Y plane"""
        inv_q = 1.0 / self.q_y
        if inv_q.real == 0:
            return float("inf")
        return 1.0 / inv_q.real

    def advance_q(self, distance: float) -> None:
        """Advance q by a physical distance d, without moving the ray.

        q is defined against the *local* medium - ``refract`` uses the reduced
        form ``1/q' = (n1/n2)(1/q) - Phi/n2`` - so the propagation step inside
        glass is d/n, not d. Advancing by d made w_x jump across an n=1.0->1.5
        surface (0.1323 -> 0.1621 mm for R=50).

        Kept separate from :meth:`propagate` because the BSP ray tracer has
        already moved the ray itself and must not move it twice.
        """
        step = distance / self.n if self.n else distance
        self.q_x += step
        self.q_y += step

    def propagate(self, distance: float) -> None:
        """Propagate beam by physical distance d."""
        # Assuming q is defined relative to the local medium (q = z + i*zR)
        # Propagation just adds distance to the real part (curvature radius changes, waist size grows)
        self.advance_q(distance)
        self.ray.propagate(distance)

    def refract(self, n1: float, n2: float, radius_of_curvature: float) -> None:
        """
        Refract beam at interface with radius R.
        R > 0 if center of curvature is to the right (convex surface from left).
        Uses thin-lens approximation for the ABCD matrix of the interface.
        """
        # Power of surface
        # Phi = (n2 - n1) / R
        if abs(radius_of_curvature) < 1e-9:
            # Flat surface (R = infinity, Phi = 0)
            Phi = 0.0
        else:
            Phi = (n2 - n1) / radius_of_curvature

        # 1/q_out = (n1/n2) * (1/q_in) - Phi/n2
        # We update 1/q directly

        # X plane
        if self.q_x != 0:
            inv_q_x = 1.0 / self.q_x
            inv_q_x_new = (n1 / n2) * inv_q_x - (Phi / n2)
            if inv_q_x_new == 0:
                self.q_x = complex(float("inf"), 0)  # Plane wave
            else:
                self.q_x = 1.0 / inv_q_x_new

        # Y plane
        if self.q_y != 0:
            inv_q_y = 1.0 / self.q_y
            inv_q_y_new = (n1 / n2) * inv_q_y - (Phi / n2)
            if inv_q_y_new == 0:
                self.q_y = complex(float("inf"), 0)
            else:
                self.q_y = 1.0 / inv_q_y_new

        # The reduced-q form above only works if the beam also carries the
        # *local* wavelength and index: w = sqrt(-lambda_local / (pi*Im(1/q))),
        # and lambda_local = lambda_vacuum / n. self.wavelength was left at its
        # vacuum value, so every beam radius computed after entering glass was
        # too large by n. self.wavelength is local to medium n1, so the vacuum
        # wavelength is n1 * self.wavelength.
        self.wavelength = (n1 * self.wavelength) / n2 if n2 else self.wavelength
        self.n = n2

        # Ray refraction is handled separately by the tracer calling ray.refract_or_reflect()
        # This method only updates the q parameter.


class BeamSynthesisPropagator:
    """
    Propagates a wavefront by decomposing it into Gaussian beamlets.
    (Beam Synthesis Propagation / BSP)
    """

    def __init__(self, system: OpticalSystem):
        self.system = system
        self.tracer = SystemRayTracer3D(system)

    def propagate_to_image(
        self,
        wavelength_mm: float = WAVELENGTH_GREEN * NM_TO_MM,
        grid_size: int = 32,
        image_plane_x: Optional[float] = None,
        detector_size: float = 0.1,
        detector_pixels: int = 64,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Decompose pupil into Gaussian beamlets, propagate them, and sum coherent field at image plane.

        Returns:
            Y, Z grids (detector) and Intensity map.
        """
        if not NUMPY_AVAILABLE:
            raise ImportError("numpy is required for BSP calculation.")

        # 1. Define Pupil Grid and Beamlets
        if not self.system.elements:
            return np.array([]), np.array([]), np.array([])

        ep_diam = self.system.elements[0].lens.diameter
        max_r = ep_diam / 2.0

        # Beamlet spacing. The grid is np.linspace(-max_r, max_r, grid_size),
        # which spans 2*max_r in grid_size-1 intervals, so the spacing is
        # ep_diam/(grid_size-1). Dividing by grid_size overstated the spacing
        # by grid_size/(grid_size-1) - 3% at grid_size=32 - and that error went
        # straight into the beamlet waist below.
        delta = (2.0 * max_r) / (grid_size - 1) if grid_size > 1 else 2.0 * max_r
        # Beamlet waist w0. Overlap factor ~1.5
        w0 = 1.5 * delta

        # Initial q (planar wavefront at pupil)
        # 1/q = 1/R - i * lambda / (pi * w0^2)
        # R = inf -> 1/q = -i * lambda / (pi * w0^2)
        # q = i * (pi * w0^2 / lambda) = i * zR
        zR = math.pi * w0**2 / wavelength_mm
        q0 = complex(0, zR)

        beamlets = []

        # Grid loop (using simple loops for beamlet creation)
        start_x = self.system.elements[0].position - 20
        direction = vec3(1, 0, 0)

        y_vals = np.linspace(-max_r, max_r, grid_size)
        z_vals = np.linspace(-max_r, max_r, grid_size)

        pupil_x = self.system.elements[0].position
        dist = pupil_x - start_x

        for py in y_vals:
            for pz in z_vals:
                if py**2 + pz**2 > max_r**2:
                    continue

                # Create ray
                origin = vec3(pupil_x, py, pz) - direction * dist
                ray = Ray3D(origin, direction, wavelength=wavelength_mm)

                # Create beamlet
                beam = GaussianBeam(wavelength_mm, q0, q0, ray)

                # Manual trace loop:
                self._trace_beamlet(beam)

                if not beam.ray.terminated:
                    beamlets.append(beam)

        # 2. Define Detector Grid
        if image_plane_x is None:
            # Default to paraxial focus (approx)
            image_plane_x = self.system.get_total_length() + 50

        det_y = np.linspace(-detector_size / 2, detector_size / 2, detector_pixels)
        det_z = np.linspace(-detector_size / 2, detector_size / 2, detector_pixels)
        DY, DZ = np.meshgrid(det_y, det_z)

        E_field = np.zeros_like(DY, dtype=complex)

        # 3. Sum Beamlets
        for beam in beamlets:
            # Intersect ray with image plane
            if abs(beam.ray.direction.x) < 1e-6:
                continue

            t = (image_plane_x - beam.ray.origin.x) / beam.ray.direction.x
            # Propagate beam to image plane
            beam.propagate(t)

            center_y = beam.ray.origin.y
            center_z = beam.ray.origin.z

            # Beam width at image plane
            wx = beam.w_x
            wy = beam.w_y

            # Radius of curvature
            Rx = beam.R_x
            Ry = beam.R_y

            # Local coordinates on detector
            local_y = DY - center_y
            local_z = DZ - center_z

            # Simplified Gaussian field
            amp = (w0 / wx) * np.exp(-(local_y**2) / (wx**2) - (local_z**2) / (wy**2))

            # Phase
            k = 2 * np.pi / wavelength_mm
            phase_curv = k * (local_y**2 / (2 * Rx) + local_z**2 / (2 * Ry))
            phase_opl = k * beam.ray.optical_path_length

            E_beam = amp * np.exp(-1j * (phase_curv + phase_opl))
            E_field += E_beam

        Intensity = np.abs(E_field) ** 2
        return DY, DZ, Intensity

    def _trace_beamlet(self, beam: GaussianBeam) -> None:
        """Helper to trace beamlet through system elements."""
        for i, element in enumerate(self.system.elements):
            if beam.ray.terminated:
                break

            tracer = LensRayTracer3D(element.lens, x_offset=element.position)

            # Front
            if tracer.trace_surface(beam.ray, "front", "refract") is not RefractionResult.REFRACTED:
                beam.ray.terminated = True
                return

            # Update q (distance from previous). advance_q divides by the local
            # index; the inline `q_x += dist` this replaces did not, so a beam
            # crossing a thick element propagated as if it were in air.
            if len(beam.ray.path) >= 2:
                dist = (beam.ray.path[-1] - beam.ray.path[-2]).magnitude()
                beam.advance_q(dist)

            # Refract beam q. n1 is the medium the beam is actually in, which
            # is air for the first element and the previous element's glass for
            # every one after it - not a hardcoded 1.0.
            beam.refract(beam.n, element.lens.refractive_index, element.lens.radius_of_curvature_1)

            # Back
            if tracer.trace_surface(beam.ray, "back", "refract") is not RefractionResult.REFRACTED:
                beam.ray.terminated = True
                return

            if len(beam.ray.path) >= 2:
                dist = (beam.ray.path[-1] - beam.ray.path[-2]).magnitude()
                beam.advance_q(dist)

            # Refract beam q
            beam.refract(element.lens.refractive_index, 1.0, element.lens.radius_of_curvature_2)
