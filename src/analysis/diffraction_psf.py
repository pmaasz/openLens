import math
import logging
from typing import Tuple, Optional, Any, List
import numpy as np

# Import internal dependencies
try:
    from ..vector3 import Vector3, vec3
    from ..ray_tracer import Ray3D, SystemRayTracer3D
    from ..optical_system import OpticalSystem
    from ..constants import NM_TO_MM, WAVELENGTH_GREEN
except ImportError:
    # Fallback for direct execution
    from src.vector3 import Vector3, vec3
    from src.ray_tracer import Ray3D, SystemRayTracer3D
    from src.optical_system import OpticalSystem
    from src.constants import NM_TO_MM, WAVELENGTH_GREEN

logger = logging.getLogger(__name__)

class WavefrontError:
    """
    Represents the wavefront error at the exit pupil.
    """
    def __init__(self, Y: np.ndarray, Z: np.ndarray, W: np.ndarray):
        self.Y = Y
        self.Z = Z
        self.W = W # Wavefront error in waves

class WavefrontSensor:
    """
    Reconstructs wavefront from ray trace data (OPL).
    """
    def __init__(self, system: OpticalSystem):
        self.system = system
        self.tracer = SystemRayTracer3D(system)

    def get_pupil_wavefront(self, field_angle: float = 0.0, 
                           wavelength: float = WAVELENGTH_GREEN * NM_TO_MM,
                           grid_size: int = 64) -> WavefrontError:
        """
        Calculate wavefront error map at the exit pupil.
        
        Returns:
            WavefrontError object containing Y, Z grids (pupil coords) and W (wavefront error in waves)
        """
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
        
        # 2. Trace Reference Ray (Chief Ray)
        # Through center of pupil
        ref_ray = Ray3D(
            origin=vec3(self.system.elements[0].position - 20, 0, 0),
            direction=vec3(math.cos(math.radians(field_angle)), math.sin(math.radians(field_angle)), 0),
            wavelength=wavelength
        )
        self.tracer.trace_ray(ref_ray)
        ref_opl = ref_ray.optical_path_length
        
        # 3. Trace Grid
        W = np.zeros_like(Y)
        valid_mask = np.zeros_like(Y, dtype=bool)
        
        start_x = self.system.elements[0].position - 20
        
        # Direction vector
        angle_rad = math.radians(field_angle)
        dx = math.cos(angle_rad)
        dy = math.sin(angle_rad)
        dz = 0
        direction = vec3(dx, dy, dz)
        
        # Back-project grid points to start plane
        pupil_x = self.system.elements[0].position
        dist = pupil_x - start_x
        
        for i in range(grid_size):
            for j in range(grid_size):
                py, pz = Y[i, j], Z[i, j]
                
                # Check aperture
                if py**2 + pz**2 > max_r**2:
                    W[i, j] = float('nan')
                    continue
                
                # Calculate start point
                # Ray should hit (pupil_x, py, pz)
                origin = vec3(pupil_x, py, pz) - direction * (dist / dx)
                
                ray = Ray3D(origin, direction, wavelength=wavelength)
                self.tracer.trace_ray(ray)
                
                if ray.terminated and len(ray.path) < len(self.system.elements):
                    # Vignetted
                    W[i, j] = float('nan')
                else:
                    # Calculate OPD
                    if not ref_ray.path: continue
                    ref_end = ref_ray.path[-1]
                    
                    # Extend ray to plane X = ref_end.x (exit pupil reference sphere approximation)
                    # Ideally, we trace to the reference sphere centered at the image point.
                    # For now, using planar exit pupil approximation for infinite conjugate or paraxial.
                    
                    if abs(ray.direction.x) > 1e-6:
                        t = (ref_end.x - ray.origin.x) / ray.direction.x
                        ray.propagate(t) # Updates OPL
                        
                        # OPD = OPL_ray - OPL_ref
                        # W = OPD / wavelength
                        W[i, j] = (ray.optical_path_length - ref_opl) / wavelength
                        valid_mask[i, j] = True

        # Remove Piston (mean) and Tilt (linear terms) if desired
        # For now just Piston
        valid_W = W[valid_mask]
        if valid_W.size > 0:
            mean_w = np.mean(valid_W)
            W[valid_mask] -= mean_w
            
        return WavefrontError(Y, Z, W)


class DiffractionPSFCalculator:
    """Calculates PSF using FFT of Pupil Function."""
    
    @staticmethod
    def calculate_psf(wavefront: WavefrontError, 
                      intensity_map: Optional[np.ndarray] = None,
                      pad_factor: int = 4) -> np.ndarray:
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
        padded_pupil[start:start+N, start:start+N] = pupil_function
        
        # FFT
        # fftshift moves zero freq to center
        psf_complex = np.fft.fftshift(np.fft.fft2(np.fft.ifftshift(padded_pupil)))
        
        # Intensity
        psf = np.abs(psf_complex)**2
        
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
        mtf = np.abs(otf)
        
        # Normalize DC component to 1.0
        # DC component is at the center after fftshift
        center_y, center_x = mtf.shape[0] // 2, mtf.shape[1] // 2
        dc_val = mtf[center_y, center_x]
        
        if dc_val > 0:
            mtf /= dc_val
            
        return mtf
