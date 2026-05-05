from typing import List, Tuple, Dict, Any, Optional, Union
import math

# Optional dependencies
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    np = None # Dummy

# Import dependencies
try:
    from ..optical_system import OpticalSystem
    from . import SpotDiagram
    from .diffraction_psf import DiffractionPSFCalculator, WavefrontSensor
except ImportError:
    # Fallback
    try:
        from src.optical_system import OpticalSystem
        from src.analysis import SpotDiagram
        from src.analysis.diffraction_psf import DiffractionPSFCalculator, WavefrontSensor
    except ImportError:
        # Last resort
        from optical_system import OpticalSystem
        from analysis import SpotDiagram
        from analysis.diffraction_psf import DiffractionPSFCalculator, WavefrontSensor

class ImageQualityAnalyzer:
    """
    Analyzer for Image Quality metrics: PSF (Point Spread Function) 
    and MTF (Modulation Transfer Function).
    """
    
    def __init__(self, system: OpticalSystem):
        self.system = system
        self.spot_analyzer = SpotDiagram(system)
        self.wavefront_sensor = WavefrontSensor(system)
        
    def calculate_spot_diagram(self, 
                               field_angle_deg: float = 0.0, 
                               wavelength_nm: float = 550.0,
                               num_rings: int = 6,
                               focus_shift_mm: float = 0.0) -> List[Tuple[float, float]]:
        """
        Wrapper for calculate_spot in SpotDiagram for backward compatibility/consistency.
        Returns a list of (y, z) coordinates in mm.
        """
        res = self.spot_analyzer.trace_spot(
            field_angle_y_deg=field_angle_deg,
            wavelength_nm=wavelength_nm,
            focus_shift_mm=focus_shift_mm,
            num_rings=num_rings
        )
        return res['points']

    def calculate_psf(self, 
                      field_angle_deg: float = 0.0, 
                      wavelength_nm: float = 550.0,
                      focus_shift_mm: float = 0.0,
                      sensor_size_mm: float = 0.1,  # mm (size of the window to compute PSF)
                      pixels: int = 64,
                      use_diffraction: bool = False) -> Dict[str, Any]:
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
            return self._calculate_diffraction_psf(field_angle_deg, wavelength_nm, focus_shift_mm, sensor_size_mm, pixels)

        # 1. Trace Rays (High density for good PSF)
        # Use a large number of rings for better statistics
        res = self.spot_analyzer.trace_spot(
            field_angle_y_deg=field_angle_deg,
            wavelength_nm=wavelength_nm,
            focus_shift_mm=focus_shift_mm,
            num_rings=25  # ~1000 rays
        )
        
        points = res['points'] # List of (y, z) tuples
        if not points:
            return {
                'image': np.zeros((pixels, pixels)),
                'x_axis': np.linspace(-sensor_size/2, sensor_size/2, pixels),
                'y_axis': np.linspace(-sensor_size/2, sensor_size/2, pixels),
                'centroid': (0,0),
                'step_size': sensor_size/pixels
            }
            
        # 2. Centering
        # Find centroid to center the PSF window
        y_coords = [p[0] for p in points]
        z_coords = [p[1] for p in points]
        
        centroid_y = np.mean(y_coords)
        centroid_z = np.mean(z_coords)
        
        # 3. Binning (Histogram)
        # Define bin edges centered on centroid
        half_size = sensor_size / 2.0
        
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
        if total_energy > 0:
            psf_norm = H / total_energy
        else:
            psf_norm = H
            
        return {
            'image': psf_norm,
            'y_axis': (y_bins[:-1] + y_bins[1:]) / 2, # Bin centers
            'z_axis': (z_bins[:-1] + z_bins[1:]) / 2,
            'centroid': (centroid_y, centroid_z),
            'step_size': sensor_size / pixels,
            'raw_count': len(points)
        }

    def calculate_mtf(self, 
                      field_angle_deg: float = 0.0, 
                      wavelength_nm: float = 550.0,
                      focus_shift_mm: float = 0.0,
                      max_freq: float = 100.0,
                      use_diffraction: bool = False) -> Dict[str, Any]:
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
        if use_diffraction:
            # For diffraction MTF, we calculate the autocorrelation of the pupil function
            # OR take the FFT of the Diffraction PSF.
            # DiffractionPSFCalculator has a helper for this.
            
            # 1. Get Wavefront
            pupil_grid_size = 64
            wf = self.wavefront_sensor.get_pupil_wavefront(
                field_angle_deg=field_angle_deg,
                wavelength_nm=wavelength_nm,
                grid_size=pupil_grid_size
            )
            
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
            
            mtf_tan = mtf_tan_full[center_y:] # From DC to max freq
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
            L_grid = ep_diam # We used +/- max_r = ep_diam/2
            
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
            
            grid_size = wf.W.shape[0] # N
            dx_pupil = L_grid / grid_size
            df = dx_pupil / (wavelength_nm * 1e-6 * efl)
            
            freqs = np.arange(len(mtf_tan)) * df
            
            # Filter
            mask = freqs <= max_freq
            
            return {
                'freq': freqs[mask],
                'mtf_tan': mtf_tan[mask],
                'mtf_sag': mtf_sag[mask]
            }

        # 1. Calculate PSF with sufficient resolution
        # Resolution requirement: 
        # Max freq = 100 lp/mm -> period = 0.01 mm
        # Sampling theorem: need pixel size < 0.005 mm (5 microns)
        # Let's use 2 microns (0.002 mm).
        # Sensor size: needs to cover the spot. Say 0.2 mm.
        # Pixels = 0.2 / 0.002 = 100 pixels.
        
        pixel_size_mm = 0.002 # 2 microns
        window_size_mm = 0.256 # 256 microns, power of 2 roughly
        num_pixels = 128
        
        psf_data = self.calculate_psf(
            field_angle_deg=field_angle_deg,
            wavelength_nm=wavelength_nm,
            focus_shift_mm=focus_shift_mm,
            sensor_size_mm=window_size_mm,
            pixels=num_pixels
        )
            
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
        
        mtf_tan = mtf_tan_full[center_y:] # From DC to max freq
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
        L_grid = ep_diam # We used +/- max_r = ep_diam/2
        
        # Sampling frequency in MTF domain
        # Fs = L_grid / (wavelength * 1e-6 * efl)
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
        # So df = dx_pupil / (lambda * f).
        # dx_pupil = L_grid / N_pupil.
        # So df = L_grid / (N_pupil * lambda * f).
        
        # This means the frequency step depends only on pupil sampling and physical parameters.
        # Padding (M) just interpolates the MTF?
        # No, padding in Pupil domain (N -> M) interpolates the PSF.
        # We are calculating MTF from PSF.
        # If we calculated PSF with padding factor P (size M = P*N).
        # The PSF has M points.
        # Taking FFT of PSF (size M) gives MTF (size M).
        # The frequency step df is 1 / (M * dx_psf).
        # dx_psf = (lambda * f) / (M * dx_pupil).
        # So df = 1 / ( (lambda*f)/dx_pupil ) = dx_pupil / (lambda * f).
        # This is consistent.
        
        grid_size = wf.W.shape[0] # N
        dx_pupil = L_grid / grid_size
        df = dx_pupil / (wavelength_nm * 1e-6 * efl)
        
        freqs = np.arange(len(mtf_tan)) * df
        
        # Filter
        mask = freqs <= max_freq
        
        return {
            'freq': freqs[mask],
            'mtf_tan': mtf_tan[mask],
            'mtf_sag': mtf_sag[mask]
        }

        # 1. Calculate PSF with sufficient resolution
        # Resolution requirement: 
        # Max freq = 100 lp/mm -> period = 0.01 mm
        # Sampling theorem: need pixel size < 0.005 mm (5 microns)
        # Let's use 2 microns (0.002 mm).
        # Sensor size: needs to cover the spot. Say 0.2 mm.
        # Pixels = 0.2 / 0.002 = 100 pixels.
        
        pixel_size = 0.002 # 2 microns
        window_size = 0.256 # 256 microns, power of 2 roughly
        num_pixels = 128
        
        psf_data = self.calculate_psf(
            field_angle=field_angle,
            wavelength=wavelength,
            focus_shift=focus_shift,
            sensor_size=window_size,
            pixels=num_pixels
        )
        
        psf = psf_data['image'] # shape (128, 128)
        
        # 2. Compute LSF
        # Y is axis 0 (Tangential), Z is axis 1 (Sagittal)
        
        # Tangential MTF: modulation along Y.
        # LSF_tan(y) = sum(PSF(y, z), axis=z)
        lsf_tan = np.sum(psf, axis=1) # Sum over Z (cols) -> profile along Y
        
        # Sagittal MTF: modulation along Z.
        # LSF_sag(z) = sum(PSF(y, z), axis=y)
        lsf_sag = np.sum(psf, axis=0) # Sum over Y (rows) -> profile along Z
        
        # 3. Compute FFT
        # fft returns standard order (DC at 0, pos freq, neg freq)
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
        
        fs = 1.0 / (psf_data['step_size']) # samples per mm
        freqs = np.fft.fftfreq(num_pixels, d=psf_data['step_size'])
        
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
            'freq': pos_freqs[mask],
            'mtf_tan': pos_mtf_tan[mask],
            'mtf_sag': pos_mtf_sag[mask]
        }

    def _calculate_diffraction_psf(self, 
                                 field_angle: float, 
                                 wavelength: float,
                                 focus_shift: float,
                                 sensor_size: float,
                                 pixels: int) -> Dict[str, Any]:
        """Helper to calculate Diffraction PSF."""
        # 1. Get Wavefront
        pupil_grid_size = 64
        wf = self.wavefront_sensor.get_pupil_wavefront(
            field_angle=field_angle,
            wavelength=wavelength * 1e-6,
            grid_size=pupil_grid_size
        )
        
        # 2. Calculate PSF
        pad_factor = 4
        psf_raw = DiffractionPSFCalculator.calculate_psf(wf, pad_factor=pad_factor)
        
        # 3. Resample to requested grid
        # Calculate raw grid parameters
        # dx_psf = (lambda * f) / (N_padded * dx_pupil)
        # dx_pupil = L_pupil / N_pupil
        
        ep_diam = self.system.elements[0].lens.diameter if self.system.elements else 1.0
        # Use simple EFL approximation or distance to image plane if available
        # Ideally, we should use the actual distance from exit pupil to image plane
        # For now, use effective focal length as a reasonable approximation for infinite conjugates
        efl = self.system.get_system_focal_length() 
        if efl is None or efl == 0:
             efl = 100.0
        
        N_pupil = wf.W.shape[0]
        dx_pupil = ep_diam / N_pupil
        padded_N = psf_raw.shape[0]
        
        dx_psf = (wavelength * 1e-6 * efl) / (padded_N * dx_pupil)
        
        raw_extent = padded_N * dx_psf
        
        # Create target coordinates
        target_y = np.linspace(-sensor_size/2, sensor_size/2, pixels)
        target_z = np.linspace(-sensor_size/2, sensor_size/2, pixels)
        
        # Resample
        # Using simple nearest neighbor for robustness if scipy missing
        # Map target coords to raw indices
        
        Y_target, Z_target = np.meshgrid(target_y, target_z, indexing='ij')
        
        # Indices in raw array
        # raw_y starts at -raw_extent/2 centered at 0
        # index = (coord - (-raw_extent/2)) / dx_psf
        
        idx_y = ((Y_target + raw_extent/2) / dx_psf).astype(int)
        idx_z = ((Z_target + raw_extent/2) / dx_psf).astype(int)
        
        # Clip indices
        idx_y = np.clip(idx_y, 0, padded_N - 1)
        idx_z = np.clip(idx_z, 0, padded_N - 1)
        
        psf_resampled = psf_raw[idx_y, idx_z]
        
        return {
            'image': psf_resampled,
            'y_axis': target_y,
            'z_axis': target_z,
            'centroid': (0,0),
            'step_size': sensor_size / pixels,
            'raw_count': 0
        }

    def simulate_image(self, 
                      image_array: np.ndarray, 
                      pixel_size: float = 0.005, 
                      wavelengths: Tuple[float, float, float] = (656.3, 587.6, 486.1),
                      field_angle: float = 0.0,
                      focus_shift: float = 0.0) -> np.ndarray:
        """
        Simulate image degradation by convolving with PSF.
        
        Args:
            image_array: Input image (H, W, 3) normalized 0-1.
            pixel_size: Sensor pixel size in mm.
            wavelengths: Tuple of (R, G, B) wavelengths in nm.
            field_angle: Field angle for PSF calculation.
            focus_shift: Defocus in mm.
            
        Returns:
            Simulated image (H, W, 3) normalized 0-1.
        """
        try:
            from scipy.signal import fftconvolve
            # Helper for when scipy is available
            def _convolve(img, kern):
                return fftconvolve(img, kern, mode='same')
        except ImportError:
            # Fallback: use numpy-based fft convolution
            def _convolve(img, kern):
                return self._numpy_fftconvolve(img, kern)

        output_image = np.zeros_like(image_array)
        
        # PSF physical size (FOV)
        # Should be large enough to contain the spot.
        # Say 0.1 mm or 0.2 mm.
        # Let's use 0.2 mm or 64x64 pixels minimum
        psf_size_mm = max(0.2, pixel_size * 64)
        psf_pixels = int(psf_size_mm / pixel_size)
        # Ensure odd size for centering
        if psf_pixels % 2 == 0: psf_pixels += 1
        
        # Process each channel
        for i, wl in enumerate(wavelengths):
            # Calculate PSF for this channel
            # Use Diffraction PSF for realistic results if possible?
            # Or Geometric? Let's default to Geometric for speed unless specifically asked.
            # Actually, Geometric PSF is often sparse (dots). Convolving with sparse dots looks like multiple images.
            # Diffraction PSF is smoother. Let's use Diffraction.
            
            psf_data = self.calculate_psf(
                field_angle=field_angle,
                wavelength=wl,
                focus_shift=focus_shift,
                sensor_size=psf_pixels * pixel_size,
                pixels=psf_pixels,
                use_diffraction=True
            )
            
            kernel = psf_data['image']
            
            # Normalize kernel
            kernel_sum = np.sum(kernel)
            if kernel_sum > 0:
                kernel /= kernel_sum
                
            # Convolve
            channel = image_array[:, :, i]
            # mode='same' keeps the output size same as input
            convolved = _convolve(channel, kernel)
            
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
        
        out_crop = out_full[start_y:start_y+h, start_x:start_x+w]
        
        return out_crop
