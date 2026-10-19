from ..constants import PARAXIAL_LAUNCH_OFFSET_MM, WAVELENGTH_GREEN
import math
import logging
from typing import Any, Optional

try:
    import numpy as np

    NUMPY_AVAILABLE = True
except ImportError:  # pragma: no cover - depends on the environment
    NUMPY_AVAILABLE = False

    # Minimal stand-in so the module still imports and its degraded paths
    # return something, rather than the whole application failing at startup.
    # openlens.py imports WavefrontSensor from here at module scope, so an
    # unguarded `import numpy` above meant the GUI could not start without it -
    # contradicting AGENTS.md, which classes numpy as optional.
    class np:  # noqa: N801 - deliberately mirrors the numpy name
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
        def ones_like(arr, dtype=None):
            return arr

        @staticmethod
        def full_like(arr, value, dtype=None):
            return arr

        @staticmethod
        def empty(shape, dtype=None):
            return np.zeros(shape)

        @staticmethod
        def count_nonzero(arr):
            return sum(1 for v in arr if v)

        @staticmethod
        def mean(values):
            values = list(values)
            return sum(values) / len(values) if values else 0.0

        @staticmethod
        def isnan(arr):
            def _isnan(v):
                return v != v

            return [_isnan(v) for v in arr]

        @staticmethod
        def allnan(arr):
            return all(v != v for v in arr)

        @staticmethod
        def linspace(start, stop, num=50, dtype=None):
            if num <= 1:
                return [float(start)]
            step = (stop - start) / (num - 1)
            return [start + step * i for i in range(num)]

        @staticmethod
        def meshgrid(x, y):
            return [[value for value in x] for _ in y], [[value for _ in x] for value in y]


# Import internal dependencies
from ..vector3 import vec3
from ..ray_tracer import Ray3D, SystemRayTracer3D
from ..optical_system import OpticalSystem
from .paraxial import find_paraxial_focus

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
        """Calculate the pupil wavefront at *wavelength_nm*.

        The trace uses the refractive indices the lenses currently carry, and
        the 3D tracer snapshots each index when it is built. So the lenses
        have to be set to the requested wavelength and the tracer rebuilt,
        otherwise the wavefront is the one for whatever wavelength the lenses
        happened to hold: the R, G and B wavefronts came out identical, and
        with them the R/G/B PSFs and the C/F MTFs, so there was no chromatic
        aberration anywhere in the diffraction analysis.

        The lenses are restored afterwards, so asking for a wavefront never
        changes the system it was asked about.

        Args:
            field_angle_deg: Field angle in degrees.
            wavelength_nm: Wavelength to trace at, in nm.
            grid_size: Number of pupil samples per axis.

        Returns:
            WavefrontError with the Y, Z pupil grids and W in waves.
        """
        saved = []
        try:
            # elements is None in the degraded (no-numpy) path, where the
            # body below returns an empty map.
            for element in getattr(self.system, "elements", None) or []:
                lens = element.lens
                saved.append((lens, lens.refractive_index, lens.wavelength))
                # refractive_index_at does not mutate the lens, and it returns
                # the stored index for a material the catalog does not have -
                # which is the right answer there, since there is no
                # dispersion data to apply.
                lens.wavelength = wavelength_nm
                lens.refractive_index = lens.refractive_index_at(wavelength_nm)
            # No tracer rebuild is needed: the tracer's batch validates each
            # element against the lens state it snapshotted - including the
            # index set above - and rebuilds on the next trace. Replacing the
            # tracer would also discard one a caller had installed
            # deliberately.
            return self._compute_pupil_wavefront(
                field_angle_deg=field_angle_deg,
                wavelength_nm=wavelength_nm,
                grid_size=grid_size,
            )
        finally:
            for lens, index, wavelength in saved:
                lens.refractive_index = index
                lens.wavelength = wavelength

    def _compute_pupil_wavefront(
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
        if not NUMPY_AVAILABLE:
            empty = []
            return WavefrontError(empty, empty, empty)

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
        # The pupil grid below launches from this plane; the shared paraxial
        # search uses the same offset (#460).
        dist = PARAXIAL_LAUNCH_OFFSET_MM

        # 2. Gaussian image point from an on-axis paraxial ray. The shared
        # search sets and restores the lenses for the wavelength.
        x_focus = find_paraxial_focus(self.system, wavelength_nm, tracer=self.tracer)
        if x_focus is None:
            logger.warning(
                "Paraxial focus unavailable (collimated exit or failed trace); "
                "cannot reference wavefront"
            )
            return _nan_map()

        # 3. Chief ray through the pupil centre; its image-plane intercept
        # is the reference-sphere centre Q.
        chief_origin = vec3(pupil_x, 0.0, 0.0) - direction * (dist / dx)
        chief = Ray3D(chief_origin, direction, wavelength=wavelength_mm)
        self.tracer.trace_ray(chief)
        # An untraced chief ray must invalidate the whole map. Without the
        # path check, a ray that was blocked but never flagged terminated (or
        # one whose path was cleared) still contributes its origin as the
        # reference-sphere centre, and every in-aperture sample is then measured
        # against a reference plane that was never traced - the exact failure
        # #314 fixed in the implementation this replaced.
        chief_traced = len(chief.path) >= 2 and not chief.terminated
        if not chief_traced or abs(chief.direction.x) < 1e-9:
            logger.warning(
                "Chief ray trace failed (path=%d point(s), terminated=%s); "
                "cannot reference wavefront",
                len(chief.path),
                chief.terminated,
            )
            return _nan_map()
        t_q = (x_focus - chief.origin.x) / chief.direction.x
        # t_q may be negative (focus in front of the exit-propagation end):
        # extending the chief line backward to the image plane is still valid.
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
                design = np.column_stack([np.ones_like(w_valid), yn, zn])
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
        if not NUMPY_AVAILABLE:
            # The beam_synthesis copy this replaced had this guard; without
            # it the FFT path raises "type object 'np' has no attribute
            # 'fft'" on a numpy-less install, breaking the optional-dependency
            # contract in AGENTS.md.
            return []
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
        if not NUMPY_AVAILABLE:
            return []
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
