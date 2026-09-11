from ..constants import WAVELENGTH_GREEN
import math
import logging
from typing import Optional
import numpy as np

# Import internal dependencies
from ..vector3 import vec3
from ..ray_tracer import Ray3D, SystemRayTracer3D
from ..optical_system import OpticalSystem

logger = logging.getLogger(__name__)


class WavefrontError:
    """
    Represents the wavefront error at the exit pupil.
    """

    def __init__(self, Y: np.ndarray, Z: np.ndarray, W: np.ndarray):
        self.Y = Y
        self.Z = Z
        self.W = W  # Wavefront error in waves


class WavefrontSensor:
    """
    Reconstructs wavefront from ray trace data (OPL).
    """

    def __init__(self, system: OpticalSystem):
        self.system = system
        self.tracer = SystemRayTracer3D(system)

    def get_pupil_wavefront(
        self,
        field_angle_deg: float = 0.0,
        wavelength_nm: float = WAVELENGTH_GREEN,
        grid_size: int = 64,
    ) -> WavefrontError:
        """
        Calculate wavefront error map at the exit pupil.

        Method (Smith, Modern Optical Engineering; Born & Wolf Sec. 9.1):
        trace a chief ray (through the pupil centre) and a grid of pupil
        rays, extend every exit ray forward to a reference sphere centred
        on the Gaussian (paraxial-focus) image point, and take
        ``W = (OPL_ray - OPL_chief) / lambda`` in waves. Piston and tilt
        are removed by a least-squares plane fit, i.e. the wavefront is
        referenced to the chief ray, so defocus-free tilt/position does
        not masquerade as aberration.

        Note: lens refractive indices are used as currently set on the
        system lenses; callers needing another wavelength must call
        ``lens.update_refractive_index()`` first (and restore afterwards).

        Returns:
            WavefrontError object containing Y, Z grids (pupil coords) and W (wavefront error in waves)
        """
        # Convert wavelength from nm to mm for OPD scaling
        wavelength_mm = wavelength_nm * 1e-6

        # 1. Define Pupil Grid
        # Get entrance pupil diameter (approx first lens D)
        if not self.system.elements:
            empty = np.array([])
            return WavefrontError(empty, empty, empty)

        ep_diam = self.system.elements[0].lens.diameter
        max_r = ep_diam / 2.0

        y = np.linspace(-max_r, max_r, grid_size)
        z = np.linspace(-max_r, max_r, grid_size)
        Y, Z = np.meshgrid(y, z)

        def _nan_map() -> WavefrontError:
            return WavefrontError(Y, Z, np.full_like(Y, float("nan")))

        angle_rad = math.radians(field_angle_deg)
        dx = math.cos(angle_rad)
        dy = math.sin(angle_rad)
        direction = vec3(dx, dy, 0)

        pupil_x = self.system.elements[0].position
        start_x = pupil_x - 20.0
        dist = pupil_x - start_x

        # 2. Gaussian image point from an on-axis paraxial ray.
        para_ray = Ray3D(
            origin=vec3(start_x, 0.001, 0),
            direction=vec3(1, 0, 0),
            wavelength=wavelength_mm,
        )
        self.tracer.trace_ray(para_ray)
        if para_ray.terminated or len(para_ray.path) < 2:
            logger.warning("Paraxial focus trace failed; cannot reference wavefront")
            return _nan_map()
        p2 = para_ray.path[-1]
        p1 = para_ray.path[-2]
        pdx = p2.x - p1.x
        pdy = p2.y - p1.y
        if abs(pdy) < 1e-12 or abs(pdx) < 1e-12:
            logger.warning("Paraxial ray collimated; no finite image point")
            return _nan_map()
        x_focus = p1.x - p1.y * (pdx / pdy)

        # 3. Chief ray through the pupil centre; its image-plane intercept
        # is the reference-sphere centre Q.
        chief_origin = vec3(pupil_x, 0.0, 0.0) - direction * (dist / dx)
        chief = Ray3D(chief_origin, direction, wavelength=wavelength_mm)
        self.tracer.trace_ray(chief)
        if chief.terminated or abs(chief.direction.x) < 1e-9:
            logger.warning("Chief ray trace failed; cannot reference wavefront")
            return _nan_map()
        t_q = (x_focus - chief.origin.x) / chief.direction.x
        if t_q < 0:
            logger.warning("Chief ray focus behind exit ray; cannot reference wavefront")
            return _nan_map()
        qx = chief.origin.x + t_q * chief.direction.x
        qy = chief.origin.y + t_q * chief.direction.y
        qz = chief.origin.z + t_q * chief.direction.z
        Q = vec3(qx, qy, qz)

        # Reference sphere through the chief exit point, centred on Q.
        R_ref = (chief.origin - Q).magnitude()
        if R_ref <= 1e-9:
            logger.warning("Degenerate reference sphere")
            return _nan_map()
        t_chief = _forward_sphere_intersection(chief.origin, chief.direction, Q, R_ref)
        if t_chief is None:
            t_chief = 0.0
        ref_opl = chief.optical_path_length + chief.n * t_chief

        # 4. Trace Grid
        W = np.zeros_like(Y)
        valid_mask = np.zeros_like(Y, dtype=bool)

        for i in range(grid_size):
            for j in range(grid_size):
                py, pz = Y[i, j], Z[i, j]

                # Check aperture
                if py**2 + pz**2 > max_r**2:
                    W[i, j] = float("nan")
                    continue

                # Ray through (pupil_x, py, pz), back-projected to start plane.
                origin = vec3(pupil_x, py, pz) - direction * (dist / dx)

                ray = Ray3D(origin, direction, wavelength=wavelength_mm)
                self.tracer.trace_ray(ray)

                if ray.terminated:
                    # Vignetted / blocked / TIR: exclude from the OPD map.
                    W[i, j] = float("nan")
                    continue

                t = _forward_sphere_intersection(ray.origin, ray.direction, Q, R_ref)
                if t is None:
                    W[i, j] = float("nan")
                    continue

                opl_ref = ray.optical_path_length + ray.n * t
                W[i, j] = (opl_ref - ref_opl) / wavelength_mm
                valid_mask[i, j] = True

        # Remove piston + tilt (least-squares plane fit over normalized
        # pupil coords) so the map is referenced to the chief ray.
        valid_count = int(np.count_nonzero(valid_mask))
        if valid_count > 0:
            w_valid = W[valid_mask]
            mean_w = float(np.mean(w_valid))
            yn = Y[valid_mask] / max_r
            zn = Z[valid_mask] / max_r
            try:
                design = np.column_stack(
                    [np.ones_like(w_valid), yn, zn]
                )
                coeffs, _, _, _ = np.linalg.lstsq(design, w_valid, rcond=None)
                W[valid_mask] = w_valid - design @ coeffs
            except Exception:
                W[valid_mask] = w_valid - mean_w

        return WavefrontError(Y, Z, W)


def _forward_sphere_intersection(
    origin: "vec3", direction: "vec3", center: "vec3", radius: float
) -> Optional[float]:
    """Smallest positive ray parameter t with |origin + t*d - center| = radius.

    Returns None if the forward ray never meets the sphere.
    """
    w = origin - center
    # Ray3D directions are unit length, but normalize defensively.
    d = direction.normalize()
    b = w.dot(d)
    c = w.magnitude_sq() - radius**2
    disc = b * b - c
    if disc < 0:
        return None
    sq = math.sqrt(max(disc, 0.0))
    for t in (-b - sq, -b + sq):
        if t > 1e-9:
            return t
    return None


class DiffractionPSFCalculator:
    """Calculates PSF using FFT of Pupil Function."""

    @staticmethod
    def calculate_psf(
        wavefront: WavefrontError,
        intensity_map: Optional[np.ndarray] = None,
        pad_factor: int = 4,
    ) -> np.ndarray:
        """
        Calculate PSF via FFT.

        Args:
            wavefront: WavefrontError object.
            intensity_map: Pupil apodization (default uniform).
            pad_factor: Zero padding factor (higher = smoother PSF).

        Returns:
            2D PSF array (normalized intensity).
        """
        wavefront_map = wavefront.W
        N = wavefront_map.shape[0]

        if intensity_map is None:
            amplitude = np.ones_like(wavefront_map)
        else:
            amplitude = np.sqrt(intensity_map)

        # Handle NaNs (outside aperture)
        mask = np.isnan(wavefront_map)
        phase = np.nan_to_num(wavefront_map)
        amplitude[mask] = 0.0

        pupil_function = amplitude * np.exp(1j * 2 * np.pi * phase)

        # Zero padding for better sampling in PSF domain
        padded_N = N * pad_factor
        padded_pupil = np.zeros((padded_N, padded_N), dtype=complex)

        start = (padded_N - N) // 2
        padded_pupil[start : start + N, start : start + N] = pupil_function

        # FFT
        # fftshift moves zero freq to center
        psf_complex = np.fft.fftshift(np.fft.fft2(np.fft.ifftshift(padded_pupil)))

        # Intensity
        psf = np.real(psf_complex * np.conj(psf_complex))

        # Normalize
        if np.max(psf) > 0:
            psf /= np.max(psf)

        return psf

    @staticmethod
    def calculate_mtf(psf: np.ndarray) -> np.ndarray:
        """
        Calculate 2D MTF from PSF.

        Args:
            psf: 2D Point Spread Function (intensity).

        Returns:
            2D Modulation Transfer Function (normalized magnitude of OTF).
        """
        # OTF is FFT of PSF
        # psf is real, so OTF is Hermitian (but we just want magnitude)
        otf = np.fft.fftshift(np.fft.fft2(np.fft.ifftshift(psf)))

        # MTF is magnitude of OTF
        mtf = np.real(np.abs(otf))

        # Normalize DC component to 1.0
        # DC component is at the center after fftshift
        center_y, center_x = mtf.shape[0] // 2, mtf.shape[1] // 2
        dc_val = mtf[center_y, center_x]

        if dc_val > 0:
            mtf /= dc_val

        return mtf
