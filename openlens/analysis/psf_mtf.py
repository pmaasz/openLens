from __future__ import annotations

# The annotations below are written against `np.ndarray`. Without this line they
# are evaluated when each function is *defined*, and the optional-import guard
# further down sets np = None when numpy is absent - so importing this module
# raised "AttributeError: 'NoneType' object has no attribute 'ndarray'" instead
# of simply reporting the missing dependency.
from ..constants import (
    WAVELENGTH_GREEN,
    WAVELENGTH_C_LINE,
    WAVELENGTH_D_LINE,
    WAVELENGTH_F_LINE,
)
from typing import List, Tuple, Dict, Any
import logging
import math

logger = logging.getLogger(__name__)

#: The geometric PSF window spans this many RMS spot radii when the spot is
#: wide enough to need it. 2.2 encloses the great majority of a Gaussian spot;
#: a tighter factor would clip the wings and flatter the MTF again.
GEOMETRIC_WINDOW_SPOT_FACTOR = 2.2

#: Log when this fraction of the traced rays or fewer lands inside the window.
GEOMETRIC_CLIP_WARN_FRACTION = 0.98

#: Ceiling on the geometric PSF window. Beyond this the window stops growing
#: with the spot, and whatever falls outside is reported as lost energy
#: rather than silently renormalised away.
GEOMETRIC_WINDOW_MAX_MM = 8.0

#: Ceiling on the geometric MTF pixel count. The window scales with the spot,
#: so an extreme defocus would otherwise ask for an FFT nobody can afford.
GEOMETRIC_MTF_MAX_PIXELS = 1024

# Optional dependencies
try:
    import numpy as np

    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    np = None  # Dummy

# Import dependencies
from ..optical_system import OpticalSystem
from . import SpotDiagram
from .diffraction_psf import DiffractionPSFCalculator, WavefrontSensor


def _map_to_raw_indices(
    target: np.ndarray, raw_extent: float, dx_psf: float, padded_N: int
) -> np.ndarray:
    """Map target coordinates to nearest-below raw-array indices.

    The raw grid spans [-raw_extent/2, +raw_extent/2], so an index is
    ``(coord + raw_extent/2) / dx_psf``.

    floor, not truncation. ``astype(int)`` truncates toward zero, which
    disagrees with floor only for negative values - and negative indices arise
    whenever the requested sensor window is wider than the raw grid. That is
    harmless today only because the result is clipped to [0, padded_N - 1]
    immediately afterwards, which maps every negative index to 0 either way;
    the tests document that. floor is correct on its own, so the clip is free
    to change.

    Returns:
        Clipped int64 indices, same shape as ``target``.
    """
    scaled = (target + raw_extent / 2) / dx_psf
    return np.clip(np.floor(scaled).astype(np.int64), 0, padded_N - 1)


class ImageQualityAnalyzer:
    """
    Analyzer for Image Quality metrics: PSF (Point Spread Function)
    and MTF (Modulation Transfer Function).
    """

    def __init__(self, system: OpticalSystem):
        self.system = system
        self.spot_analyzer = SpotDiagram(system)
        self.wavefront_sensor = WavefrontSensor(system)

    #: Keys every calculate_psf branch must return. The three branches had
    #: drifted apart (the empty one returned x_axis and no z_axis), so
    #: plot_psf raised KeyError on a fully blocked design. Asserted in one
    #: place rather than documented in three.
    PSF_KEYS = frozenset(
        {
            "image",
            "y_axis",
            "z_axis",
            "centroid",
            "step_size",
            "raw_count",
            "captured_fraction",
        }
    )

    def _psf_result(self, **fields) -> Dict[str, Any]:
        """Build a PSF payload, asserting the key set every branch owes."""
        missing = self.PSF_KEYS - set(fields)
        if missing:
            raise AssertionError(f"calculate_psf result is missing keys: {sorted(missing)}")
        return fields

    def calculate_spot_diagram(
        self,
        field_angle_deg: float = 0.0,
        wavelength_nm: float = WAVELENGTH_GREEN,
        num_rings: int = 6,
        focus_shift_mm: float = 0.0,
    ) -> List[Tuple[float, float]]:
        """
        Wrapper for calculate_spot in SpotDiagram for backward compatibility/consistency.
        Returns a list of (y, z) coordinates in mm.
        """
        res = self.spot_analyzer.trace_spot(
            field_angle_y_deg=field_angle_deg,
            wavelength_nm=wavelength_nm,
            focus_shift_mm=focus_shift_mm,
            num_rings=num_rings,
        )
        return res["points"]

    def calculate_psf(
        self,
        field_angle_deg: float = 0.0,
        wavelength_nm: float = WAVELENGTH_GREEN,
        focus_shift_mm: float = 0.0,
        sensor_size_mm: float = 0.1,  # mm (size of the window to compute PSF)
        pixels: int = 64,
        use_diffraction: bool = False,
    ) -> Dict[str, Any]:
        """
        Calculate the Point Spread Function (PSF).

        Args:
            field_angle_deg: Field angle in Y direction (degrees)
            wavelength_nm: Wavelength in nm
            focus_shift_mm: Defocus in mm
            sensor_size_mm: Size of the square sensor area to bin rays (mm)
            pixels: Number of pixels along one side of the sensor area
            use_diffraction: If True, uses FFT of Pupil Function (Wavefront).
                             If False, uses Geometric Ray Spot Diagram.

        Returns:
            Dictionary containing:
                - image: 2D numpy array of the PSF (normalized intensity)
                - x_axis: 1D array of spatial coordinates (mm)
                - y_axis: 1D array of spatial coordinates (mm)
                - centroid: (y, z) of the centroid in mm
                - step_size: pixel size in mm
        """
        if use_diffraction:
            return self._calculate_diffraction_psf(
                field_angle_deg, wavelength_nm, focus_shift_mm, sensor_size_mm, pixels
            )

        # 1. Trace Rays (High density for good PSF)
        # Use a large number of rings for better statistics
        res = self.spot_analyzer.trace_spot(
            field_angle_y_deg=field_angle_deg,
            wavelength_nm=wavelength_nm,
            focus_shift_mm=focus_shift_mm,
            num_rings=25,  # ~1000 rays
        )

        points = res["points"]  # List of (y, z) tuples
        if not points:
            # Same key set as the normal and diffraction branches below.
            # This one returned x_axis and no z_axis, so plot_psf - which
            # reads z_axis - raised KeyError, and openlens.py calls
            # calculate_psf and plot_psf back to back: a fully blocked design
            # turned the PSF dialog into "Failed to calculate PSF: 'z_axis'".
            # Axes are built as bin centers exactly as in the normal branch,
            # so an empty PSF has the same extent as a populated one.
            empty_bins = np.linspace(-sensor_size_mm / 2, sensor_size_mm / 2, pixels + 1)
            empty_axis = (empty_bins[:-1] + empty_bins[1:]) / 2
            return self._psf_result(
                image=np.zeros((pixels, pixels)),
                y_axis=empty_axis,
                z_axis=empty_axis.copy(),
                centroid=(0.0, 0.0),
                step_size=sensor_size_mm / pixels,
                raw_count=0,
                captured_fraction=0.0,
            )

        # 2. Centering
        # Find centroid to center the PSF window
        y_coords = [p[0] for p in points]
        z_coords = [p[1] for p in points]

        centroid_y = np.mean(y_coords)
        centroid_z = np.mean(z_coords)

        # 3. Window sizing.
        # sensor_size_mm was taken literally, so any spot wider than about
        # 0.1 mm radius had most of its light fall outside the frame.
        # histogram2d discards those points silently, and the normalisation
        # below then divided by the binned sum, so the image still summed to
        # 1.0 - the MTF described only the clipped core and looked better
        # than the lens really is.
        #
        # The window now grows to cover the spot the tracer actually
        # produced, keeping the requested sensor size as a floor. The extent
        # of the returned axis follows the window, so a wider spot yields a
        # correspondingly larger image.
        spot_rms = res.get("rms_radius")
        if spot_rms is not None and math.isfinite(spot_rms) and spot_rms > 0:
            required_half = GEOMETRIC_WINDOW_SPOT_FACTOR * spot_rms
            window_mm = max(sensor_size_mm, 2.0 * required_half)
            # Bounded, so a pathological spot cannot ask for an image large
            # enough to exhaust memory. When the cap bites the rays outside
            # are genuinely lost, which is why the normalisation below counts
            # traced rays rather than binned ones and reports the shortfall.
            window_mm = min(window_mm, GEOMETRIC_WINDOW_MAX_MM)
        else:
            window_mm = sensor_size_mm
        half_size = window_mm / 2.0

        # Y is Tangential (vertical on detector), Z is Sagittal (horizontal on detector)
        # We want image[row, col]. Row usually Y, Col usually Z.
        # Histogram2d returns H, xedges, yedges. H[x, y].
        # Let's map Y -> rows, Z -> cols.

        y_bins = np.linspace(centroid_y - half_size, centroid_y + half_size, pixels + 1)
        z_bins = np.linspace(centroid_z - half_size, centroid_z + half_size, pixels + 1)

        # points are (y, z). histogram2d(x, y) bins x into rows? No, check docs.
        # np.histogram2d(x, y, bins=[x_edges, y_edges]) returns H[x_bin, y_bin]
        # We pass y_coords as sample x, z_coords as sample y.

        H, _, _ = np.histogram2d(y_coords, z_coords, bins=[y_bins, z_bins])

        # H is (ny, nz).
        # Normalize to max 1.0 (Strehl-like ratio? No, just peak 1 for visualization)
        # Or sum to 1 (probability density).
        # For MTF calculation, sum to 1 is better (DC component = 1).

        total_energy = np.sum(H)
        # Normalise by every ray traced, not by the ones that happened to
        # land in the frame. Dividing by the binned sum made the image sum to
        # 1.0 even when 91% of the light had been thrown away, which hid the
        # clipping from the MTF entirely.
        traced = len(points)
        if traced > 0:
            psf_norm = H / traced
            captured_fraction = float(total_energy) / traced
        else:
            psf_norm = H
            captured_fraction = 0.0

        if captured_fraction < GEOMETRIC_CLIP_WARN_FRACTION:
            logger.warning(
                "Geometric PSF: only %.1f%% of %d rays landed inside the "
                "%.3f mm window (RMS spot %.4f mm). The image is normalised "
                "by the traced ray count, so it sums to %.3f rather than 1; "
                "the MTF reflects the clipped spot.",
                100.0 * captured_fraction,
                traced,
                window_mm,
                float(spot_rms) if spot_rms is not None else float("nan"),
                captured_fraction,
            )

        return self._psf_result(
            image=psf_norm,
            y_axis=(y_bins[:-1] + y_bins[1:]) / 2,  # Bin centers
            z_axis=(z_bins[:-1] + z_bins[1:]) / 2,
            centroid=(centroid_y, centroid_z),
            step_size=window_mm / pixels,
            raw_count=traced,
            captured_fraction=captured_fraction,
        )

    def calculate_mtf(
        self,
        field_angle_deg: float = 0.0,
        wavelength_nm: float = WAVELENGTH_GREEN,
        focus_shift_mm: float = 0.0,
        max_freq: float = 100.0,
        use_diffraction: bool = False,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Calculate the Modulation Transfer Function (MTF).

        Args:
            field_angle_deg: Field angle in degrees
            wavelength_nm: Wavelength in nm
            focus_shift_mm: Defocus in mm
            max_freq: Maximum spatial frequency to return (lp/mm)
            use_diffraction: If True, uses FFT of Pupil Function.

        Returns:
            Dictionary containing:
                - freq: Array of spatial frequencies (lp/mm)
                - mtf_tan: Tangential MTF values
                - mtf_sag: Sagittal MTF values
        """
        # Handle legacy aliases
        if "field_angle" in kwargs:
            field_angle_deg = kwargs.pop("field_angle")
        if "max_freq" in kwargs:
            max_freq = kwargs.pop("max_freq")
        if kwargs:
            raise TypeError(f"Unexpected kwargs: {list(kwargs.keys())}")
        if use_diffraction:
            # For diffraction MTF, we calculate the autocorrelation of the pupil function
            # OR take the FFT of the Diffraction PSF.
            # DiffractionPSFCalculator has a helper for this.

            # 1. Get Wavefront
            pupil_grid_size = 64
            wf = self.wavefront_sensor.get_pupil_wavefront(
                field_angle_deg=field_angle_deg,
                wavelength_nm=wavelength_nm,
                grid_size=pupil_grid_size,
            )

            # 1b. Apply the defocus. This branch had its own copy of the
            # wavefront->PSF chain and dropped focus_shift_mm on the floor, so
            # the diffraction MTF was the same at every defocus.
            _, _, na = self._pupil_geometry()
            self._apply_defocus(wf, focus_shift_mm, wavelength_nm, na)

            # 2. Calculate PSF (high res)
            pad_factor = 4
            psf_raw = DiffractionPSFCalculator.calculate_psf(wf, pad_factor=pad_factor)

            # 3. Calculate MTF from PSF
            mtf_2d = DiffractionPSFCalculator.calculate_mtf(psf_raw)

            # 4. Extract Profiles
            center_y, center_x = mtf_2d.shape[0] // 2, mtf_2d.shape[1] // 2

            # Tangential (along Y axis in frequency domain) -> Corresponds to spatial Y modulation?
            # Wait. MTF(fy, fz).
            # Tangential MTF is usually defined for modulation along the tangential direction (Y).
            # This corresponds to frequency fy? Yes.
            # Sagittal MTF -> fz.

            # Extract slices from 2D MTF
            # Positive frequencies only
            n_half = mtf_2d.shape[0] // 2

            # Slice along axes
            mtf_tan_full = mtf_2d[:, center_x]
            mtf_sag_full = mtf_2d[center_y, :]

            mtf_tan = mtf_tan_full[center_y:]  # From DC to max freq
            mtf_sag = mtf_sag_full[center_x:]

            # 5. Frequency Scale
            # Max frequency (cutoff) = 1 / (lambda * F/#)
            # The FFT frequency scale is determined by the spatial sampling.
            # dx (spatial sampling of PSF) = (lambda * f) / (N_pupil * dx_pupil) * (something)
            # Actually, simpler:
            # Max Frequency in MTF corresponds to the cutoff frequency of the system.
            # Cutoff = D / (lambda * f).
            # The MTF array spans from -Cutoff to +Cutoff?
            # No. The MTF array spans -Fs/2 to Fs/2 where Fs = 1/dx_psf.
            # dx_psf = (lambda * f) / L_pupil_grid.
            # So Fs = L_pupil_grid / (lambda * f).
            # This makes sense. The max frequency we can resolve is limited by the pupil size.
            # The MTF array has size M (padded size).
            # So frequency step df = Fs / M = L_pupil_grid / (lambda * f * M).
            # The cutoff frequency is D / (lambda * f).
            # D is approx L_pupil_grid.
            # So the cutoff is at index M * (D/L) ?
            # If L_pupil_grid is exactly D (which we try to set), then Fs = Cutoff * (something).

            # Let's use physical parameters.
            ep_diam = self.system.elements[0].lens.diameter if self.system.elements else 1.0
            efl = self.system.get_system_focal_length() or 100.0

            # Pupil Grid physical size L = ep_diam (approx, based on get_pupil_wavefront range)
            L_grid = ep_diam  # We used +/- max_r = ep_diam/2

            # Sampling frequency in MTF domain
            # Fs = L_grid / (wavelength_nm * 1e-6 * efl)
            # This assumes the PSF calculation uses the standard FFT scaling.
            # Yes, if we pad to M, the spatial extent of PSF is lambda*f/dx_pupil.
            # dx_pupil = L_grid / N.
            # So Extent = lambda*f*N/L_grid.
            # Fs = 1 / (Extent/M) = M / Extent = M * L_grid / (lambda*f*N).
            # Wait, frequency resolution df = 1/Extent.
            # df = L_grid / (lambda * f * N) ? No. 1/Extent = (dx_pupil) / (lambda * f).

            # Let's re-verify:
            # df = 1 / (Total Spatial Range).
            # Total Spatial Range (FOV of PSF) = M * dx_psf.
            # dx_psf = (lambda * f) / (M * dx_pupil).
            # FOV = (lambda * f) / dx_pupil.
            # So df = 1 / ( (lambda*f)/dx_pupil ) = dx_pupil / (lambda * f).
            # This is consistent.

            grid_size = wf.W.shape[0]  # N
            # The pupil grid is np.linspace(-max_r, max_r, N): N samples
            # spanning 2*max_r in N-1 intervals, so the sample spacing is
            # L_grid/(N-1). Dividing by N understated it by N/(N-1) and
            # reported every frequency low by that factor.
            dx_pupil = L_grid / (grid_size - 1) if grid_size > 1 else L_grid
            df = dx_pupil / (wavelength_nm * 1e-6 * efl)

            freqs = np.arange(len(mtf_tan)) * df

            # Filter
            mask = freqs <= max_freq

            return {
                "freq": freqs[mask],
                "mtf_tan": mtf_tan[mask],
                "mtf_sag": mtf_sag[mask],
            }

        # 1. Calculate PSF with sufficient resolution.
        # The window used to be a fixed 0.256 mm with a fixed 128 pixels, so
        # a spot wider than about 0.1 mm radius had most of its light
        # discarded by the histogram - and the MTF was then computed from the
        # clipped core, describing a better lens than the one being tested.
        #
        # The window is now sized from the spot the tracer produces (the same
        # 2.2 RMS radii calculate_psf uses), and the pixel count is derived
        # from it so the sampling stays at ~2 microns. Fixing the window while
        # leaving the pixel count alone would have kept the clipping away but
        # coarsened the sampling, trading one wrong answer for another.
        target_pixel_mm = 0.002  # 2 microns
        window_floor_mm = 0.256  # ~128 pixels at 2 microns

        spot_res = self.spot_analyzer.trace_spot(
            field_angle_y_deg=field_angle_deg,
            wavelength_nm=wavelength_nm,
            focus_shift_mm=focus_shift_mm,
            num_rings=25,
        )
        spot_rms = spot_res.get("rms_radius")
        if spot_rms is not None and math.isfinite(spot_rms) and spot_rms > 0:
            window_size_mm = max(
                window_floor_mm,
                2.0 * GEOMETRIC_WINDOW_SPOT_FACTOR * spot_rms,
            )
        else:
            window_size_mm = window_floor_mm

        num_pixels = max(128, int(math.ceil(window_size_mm / target_pixel_mm)))
        num_pixels = min(num_pixels, GEOMETRIC_MTF_MAX_PIXELS)

        psf_data = self.calculate_psf(
            field_angle_deg=field_angle_deg,
            wavelength_nm=wavelength_nm,
            focus_shift_mm=focus_shift_mm,
            sensor_size_mm=window_size_mm,
            pixels=num_pixels,
        )

        psf = psf_data["image"]  # shape (128, 128)

        # 2. Compute LSF
        # Y is axis 0 (Tangential), Z is axis 1 (Sagittal)

        # Tangential MTF: modulation along Y.
        # LSF_tan(y) = sum(PSF(y, z), axis=z)
        lsf_tan = np.sum(psf, axis=1)  # Sum over Z (cols) -> profile along Y

        # Sagittal MTF: modulation along Z.
        # LSF_sag(z) = sum(PSF(y, z), axis=y)
        lsf_sag = np.sum(psf, axis=0)  # Sum over Y (rows) -> profile along Z

        # 3. Compute MTF (Magnitude of FFT of LSF)
        # Use rfft for efficiency as LSF is real
        mtf_tan_raw = np.abs(np.fft.fft(lsf_tan))
        mtf_sag_raw = np.abs(np.fft.fft(lsf_sag))

        # Normalize DC to 1.0
        if mtf_tan_raw[0] > 0:
            mtf_tan_raw /= mtf_tan_raw[0]
        if mtf_sag_raw[0] > 0:
            mtf_sag_raw /= mtf_sag_raw[0]

        # 4. Frequency Scaling
        # Sampling freq Fs = 1 / pixel_size
        # Freq resolution df = Fs / N
        # Freqs = k * df

        fs = 1.0 / (psf_data["step_size"])  # samples per mm
        freqs = np.fft.fftfreq(num_pixels, d=psf_data["step_size"])

        # Take only positive frequencies up to max_freq
        # fftfreq returns [0, 1, ..., n/2-1, -n/2, ..., -1]
        # We only want the first half

        n_half = num_pixels // 2
        pos_freqs = freqs[:n_half]
        pos_mtf_tan = mtf_tan_raw[:n_half]
        pos_mtf_sag = mtf_sag_raw[:n_half]

        # Filter to max_freq
        mask = (pos_freqs <= max_freq) & (pos_freqs >= 0)

        return {
            "freq": pos_freqs[mask],
            "mtf_tan": pos_mtf_tan[mask],
            "mtf_sag": pos_mtf_sag[mask],
        }

    def _pupil_geometry(self) -> tuple:
        """Return (pupil_diameter_mm, effective_focal_length_mm, numerical_aperture).

        The pupil diameter and EFL are approximations - the pupil is taken as
        the first element's mechanical diameter, and the EFL is used in place
        of the true distance from the exit pupil to the image plane. That is
        the same approximation the PSF resampling already uses, so the two
        stay consistent.
        """
        ep_diam = self.system.elements[0].lens.diameter if self.system.elements else 1.0
        efl = self.system.get_system_focal_length()
        if efl is None or efl == 0:
            efl = 100.0
        na = ep_diam / (2.0 * abs(efl)) if efl else 0.0
        return ep_diam, efl, na

    @staticmethod
    def _apply_defocus(wf, focus_shift_mm: float, wavelength_nm: float, na: float):
        """Add the defocus term to a pupil wavefront, in waves.

        An image-plane defocus of ``dz`` adds a quadratic phase across the
        pupil:

            W(p) = dz * NA^2 * p^2 / (2 * lambda)

        with ``p`` the pupil coordinate normalised to 1 at the edge and
        ``lambda`` in mm. Without it the wavefront was identical at every
        defocus, so the PSF and the diffraction MTF were bit-identical at 0 mm
        and at 2 mm - the defocus argument did nothing at all.

        The sign of the quadratic does not change the PSF (the intensity is
        the square of the modulus, and the pupil is symmetric), but its
        magnitude does, so the scale is what matters here.

        Args:
            wf: The wavefront to modify in place.
            focus_shift_mm: Defocus in mm. Zero leaves the wavefront alone.
            wavelength_nm: Wavelength in nm.
            na: Numerical aperture.

        Returns:
            The same wavefront object, for convenience.
        """
        if not focus_shift_mm or wf is None or not HAS_NUMPY:
            return wf

        y = np.asarray(wf.Y)
        z = np.asarray(wf.Z)
        if y.size == 0:
            return wf

        radius = float(np.max(np.sqrt(y * y + z * z)))
        if radius <= 0.0:
            return wf

        p_squared = (y * y + z * z) / (radius * radius)
        wavelength_mm = wavelength_nm * 1e-6
        wf.W = np.asarray(wf.W) + focus_shift_mm * na * na * p_squared / (2.0 * wavelength_mm)
        return wf

    def _calculate_diffraction_psf(
        self,
        field_angle_deg: float,
        wavelength_nm: float,
        focus_shift_mm: float,
        sensor_size_mm: float,
        pixels: int,
    ) -> Dict[str, Any]:
        """Helper to calculate Diffraction PSF."""
        # 1. Get Wavefront
        pupil_grid_size = 64
        wf = self.wavefront_sensor.get_pupil_wavefront(
            field_angle_deg=field_angle_deg,
            wavelength_nm=wavelength_nm,
            grid_size=pupil_grid_size,
        )

        # 1b. Apply the defocus. The wavefront is referenced to the Gaussian
        # focus, so without this the defocus argument had no effect at all.
        ep_diam, efl, na = self._pupil_geometry()
        self._apply_defocus(wf, focus_shift_mm, wavelength_nm, na)

        # 2. Calculate PSF
        pad_factor = 4
        psf_raw = DiffractionPSFCalculator.calculate_psf(wf, pad_factor=pad_factor)

        # 3. Resample to requested grid
        # Calculate raw grid parameters
        # dx_psf = (lambda * f) / (N_padded * dx_pupil)
        # dx_pupil = L_pupil / N_pupil

        # ep_diam, efl and na come from _pupil_geometry() above, so the
        # defocus term and the resampling use the same approximations.

        N_pupil = wf.W.shape[0]
        # Same N-1 interval spacing as above; the error inflated dx_psf and
        # therefore raw_extent, shifting the resample window as well.
        dx_pupil = ep_diam / (N_pupil - 1) if N_pupil > 1 else ep_diam
        padded_N = psf_raw.shape[0]

        dx_psf = (wavelength_nm * 1e-6 * efl) / (padded_N * dx_pupil)
        if dx_psf <= 0.0 or not np.isfinite(dx_psf):
            # An empty system (or a degenerate pupil) leaves no spacing to
            # divide by. The index arithmetic below would divide by zero,
            # producing inf and then INT_MIN on the cast to int.
            logger.warning(
                "Degenerate PSF spacing (dx_psf=%r) for %s; returning an empty "
                "PSF rather than resampling garbage",
                dx_psf,
                self.system.name,
            )
            # Spelled out rather than reusing a helper so this stays
            # independently mergeable.
            axis = np.linspace(-sensor_size_mm / 2, sensor_size_mm / 2, pixels)
            return {
                "image": np.zeros((pixels, pixels)),
                "y_axis": axis,
                "z_axis": axis.copy(),
                "centroid": (0.0, 0.0),
                "step_size": sensor_size_mm / pixels,
                "raw_count": 0,
            }

        raw_extent = padded_N * dx_psf

        # Create target coordinates
        target_y = np.linspace(-sensor_size_mm / 2, sensor_size_mm / 2, pixels)
        target_z = np.linspace(-sensor_size_mm / 2, sensor_size_mm / 2, pixels)

        # Resample
        # Using simple nearest neighbor for robustness if scipy missing
        # Map target coords to raw indices

        Y_target, Z_target = np.meshgrid(target_y, target_z, indexing="ij")

        # Indices in raw array
        # raw_y starts at -raw_extent/2 centered at 0
        # index = (coord - (-raw_extent/2)) / dx_psf

        idx_y = _map_to_raw_indices(Y_target, raw_extent, dx_psf, padded_N)
        idx_z = _map_to_raw_indices(Z_target, raw_extent, dx_psf, padded_N)

        psf_resampled = psf_raw[idx_y, idx_z]

        return self._psf_result(
            image=psf_resampled,
            y_axis=target_y,
            z_axis=target_z,
            centroid=(0.0, 0.0),
            step_size=sensor_size_mm / pixels,
            raw_count=0,
            captured_fraction=1.0,
        )

    def simulate_image(
        self,
        image_array: np.ndarray,
        pixel_size_mm: float = 0.005,
        wavelengths_nm: Tuple[float, float, float] = (
            WAVELENGTH_C_LINE,
            WAVELENGTH_D_LINE,
            WAVELENGTH_F_LINE,
        ),
        field_angle_deg: float = 0.0,
        focus_shift_mm: float = 0.0,
        **kwargs,
    ) -> np.ndarray:
        """
        Simulate image degradation by convolving with PSF.

        Args:
            image_array: Input image, either (H, W) grayscale or (H, W, C)
                multi-channel, with C matching ``wavelengths_nm``. Float input
                is taken as normalized 0-1; integer input is scaled by its
                dtype maximum first.
            pixel_size_mm: Sensor pixel size in mm.
            wavelengths_nm: Tuple of (R, G, B) wavelengths in nm.
            field_angle_deg: Field angle for PSF calculation.
            focus_shift_mm: Defocus in mm.

        Returns:
            Simulated image in the same shape as the input, normalized 0-1
            and always float64.

        Raises:
            ValueError: If the array is neither 2-D nor 3-D, or its channel
                count does not match ``wavelengths_nm``.
        """
        # Handle legacy alias pixel_size
        if "pixel_size" in kwargs:
            pixel_size_mm = kwargs.pop("pixel_size")
        if "wavelengths" in kwargs:
            wavelengths_nm = kwargs.pop("wavelengths")
        if kwargs:
            raise TypeError(f"Unexpected kwargs: {list(kwargs.keys())}")
        try:
            from scipy.signal import fftconvolve

            # Helper for when scipy is available
            def _convolve(img, kern):
                return fftconvolve(img, kern, mode="same")

        except ImportError:
            # Fallback: use numpy-based fft convolution
            def _convolve(img, kern):
                return self._numpy_fftconvolve(img, kern)

        output_image = np.zeros(image_array.shape, dtype=np.float64)

        # Accept 2-D grayscale or 3-D RGB, and integer or float input. The
        # old np.zeros_like(image_array) inherited the input dtype, so a uint8
        # image truncated every float result to 0 or 1 before the clip, and
        # image_array[:, :, i] raised IndexError on a 2-D input.
        image_array = np.asarray(image_array)
        if image_array.ndim not in (2, 3):
            raise ValueError(
                f"image_array must be 2-D (H, W) or 3-D (H, W, C); got shape "
                f"{image_array.shape}"
            )
        if image_array.ndim == 3 and image_array.shape[2] != len(wavelengths_nm):
            raise ValueError(
                f"image_array has {image_array.shape[2]} channels but "
                f"{len(wavelengths_nm)} wavelengths were given"
            )

        if np.issubdtype(image_array.dtype, np.integer):
            # Integer input carries 0..max, not the documented 0..1. Scale it
            # so the convolution sees real intensities; without this the
            # np.clip(0, 1) below saturates the whole image to 1.
            scale = float(np.iinfo(image_array.dtype).max)
            work = image_array.astype(np.float64) / scale
        else:
            work = image_array.astype(np.float64)

        is_grayscale = work.ndim == 2

        # PSF physical size (FOV)
        # Should be large enough to contain the spot.
        # Say 0.1 mm or 0.2 mm.
        # Let's use 0.2 mm or 64x64 pixels minimum
        psf_size_mm = max(0.2, pixel_size_mm * 64)
        psf_pixels = int(psf_size_mm / pixel_size_mm)
        # Ensure odd size for centering
        if psf_pixels % 2 == 0:
            psf_pixels += 1

        # Process each channel
        channel_results = []
        for i, wl in enumerate(wavelengths_nm):
            # Calculate PSF for this channel
            # Use Diffraction PSF for realistic results if possible?
            # Or Geometric? Let's default to Geometric for speed unless specifically asked.
            # Actually, Geometric PSF is often sparse (dots). Convolving with sparse dots looks like multiple images.
            # Diffraction PSF is smoother. Let's use Diffraction.

            psf_data = self.calculate_psf(
                field_angle_deg=field_angle_deg,
                wavelength_nm=wl,
                focus_shift_mm=focus_shift_mm,
                sensor_size_mm=psf_pixels * pixel_size_mm,
                pixels=psf_pixels,
                use_diffraction=True,
            )

            kernel = psf_data["image"]

            # Normalize kernel
            kernel_sum = np.sum(kernel)
            if kernel_sum > 0:
                kernel /= kernel_sum

            # Convolve
            channel = work if is_grayscale else work[:, :, i]
            # mode='same' keeps the output size same as input
            convolved = np.asarray(_convolve(channel, kernel), dtype=np.float64)

            channel_results.append(convolved)

        if is_grayscale:
            # One plane in, one plane out: combine the per-wavelength results
            # rather than inventing a third axis the caller did not ask for.
            output_image[:, :] = np.mean(channel_results, axis=0)
        else:
            for i, convolved in enumerate(channel_results):
                output_image[:, :, i] = convolved

        return np.clip(output_image, 0, 1)

    def _numpy_fftconvolve(self, img: np.ndarray, kernel: np.ndarray) -> np.ndarray:
        """
        Fallback FFT convolution using numpy.
        """
        h, w = img.shape
        kh, kw = kernel.shape

        # Pad to size M + N - 1
        shape = (h + kh - 1, w + kw - 1)

        # FFT
        fft_img = np.fft.fft2(img, s=shape)
        fft_ker = np.fft.fft2(kernel, s=shape)

        # Multiply
        fft_out = fft_img * fft_ker

        # IFFT
        out_full = np.real(np.fft.ifft2(fft_out))

        # Crop to 'same' size
        # Center of full convolution is at (h+kh-2)/2, (w+kw-2)/2
        # We want window of size h, w around center

        start_y = (kh - 1) // 2
        start_x = (kw - 1) // 2

        out_crop = out_full[start_y : start_y + h, start_x : start_x + w]

        return out_crop
