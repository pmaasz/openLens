import math
import cmath
from typing import List, Tuple, Optional, Dict, Any, Union
from dataclasses import dataclass

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    # Define minimal dummy for type hints if needed
    class np:
        ndarray = Any
        
try:
    from ..vector3 import Vector3, vec3
    from ..ray_tracer import Ray3D, LensRayTracer3D, SystemRayTracer3D
    from ..optical_system import OpticalSystem
    from ..constants import NM_TO_MM, WAVELENGTH_GREEN, REFRACTIVE_INDEX_AIR
except ImportError:
    # Fallback for direct execution
    import sys
    import os
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from vector3 import Vector3, vec3
    from ray_tracer import Ray3D, LensRayTracer3D, SystemRayTracer3D
    from optical_system import OpticalSystem
    from constants import NM_TO_MM, WAVELENGTH_GREEN, REFRACTIVE_INDEX_AIR

@dataclass
class GaussianBeam:
    """
    Represents a fundamental Gaussian Beam (TEM00).
    Uses complex curvature parameter q.
    1/q = 1/R - i * lambda / (pi * w^2)
    """
    wavelength: float # in mm
    q_x: complex      # Complex beam parameter in X (meridional)
    q_y: complex      # Complex beam parameter in Y (sagittal)
    ray: Ray3D        # Central ray carrying the beam

    @property
    def w_x(self) -> float:
        """Beam radius (1/e^2 intensity) in X plane"""
        if self.q_x.imag == 0: return 0.0
        return math.sqrt(-self.wavelength / (math.pi * (1.0/self.q_x).imag))

    @property
    def w_y(self) -> float:
        """Beam radius (1/e^2 intensity) in Y plane"""
        if self.q_y.imag == 0: return 0.0
        return math.sqrt(-self.wavelength / (math.pi * (1.0/self.q_y).imag))
    
    @property
    def R_x(self) -> float:
        """Radius of curvature of wavefront in X plane"""
        inv_q = 1.0/self.q_x
        if inv_q.real == 0: return float('inf')
        return 1.0 / inv_q.real

    def propagate(self, distance: float) -> None:
        """Propagate beam by physical distance d."""
        # Assuming q is defined relative to the local medium (q = z + i*zR)
        # Propagation just adds distance to the real part (curvature radius changes, waist size grows)
        self.q_x += distance
        self.q_y += distance
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
            inv_q_x_new = (n1/n2) * inv_q_x - (Phi/n2)
            if inv_q_x_new == 0:
                self.q_x = complex(float('inf'), 0) # Plane wave
            else:
                self.q_x = 1.0 / inv_q_x_new
                
        # Y plane
        if self.q_y != 0:
            inv_q_y = 1.0 / self.q_y
            inv_q_y_new = (n1/n2) * inv_q_y - (Phi/n2)
            if inv_q_y_new == 0:
                self.q_y = complex(float('inf'), 0)
            else:
                self.q_y = 1.0 / inv_q_y_new
        
        # Ray refraction is handled separately by the tracer calling ray.refract()
        # This method only updates the q parameter.


class WavefrontSensor:
    """
    Reconstructs wavefront from ray trace data (OPL).
    """
    def __init__(self, system: OpticalSystem):
        self.system = system
        self.tracer = SystemRayTracer3D(system)

    def get_pupil_wavefront(self, field_angle: float = 0.0, 
                           wavelength: float = WAVELENGTH_GREEN * NM_TO_MM,
                           grid_size: int = 64) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Calculate wavefront error map at the exit pupil.
        
        Returns:
            Y, Z grids (pupil coords) and W (wavefront error in waves)
        """
        # 1. Define Pupil Grid
        # Get entrance pupil diameter (approx first lens D)
        if not self.system.elements:
            return np.array([]), np.array([]), np.array([])
            
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
                    
                    # Extend ray to plane X = ref_end.x
                    if abs(ray.direction.x) > 1e-6:
                        t = (ref_end.x - ray.origin.x) / ray.direction.x
                        ray.propagate(t) # Updates OPL
                        
                        W[i, j] = (ray.optical_path_length - ref_opl) / wavelength
                        valid_mask[i, j] = True

        # Remove Piston (mean)
        valid_W = W[valid_mask]
        if valid_W.size > 0:
            mean_w = np.mean(valid_W)
            W[valid_mask] -= mean_w
            
        return Y, Z, W


class PSFCalculator:
    """Calculates PSF using FFT of Pupil Function."""
    
    @staticmethod
    def calculate_psf(pupil_grid_Y: np.ndarray, pupil_grid_Z: np.ndarray, 
                      wavefront_map: np.ndarray, intensity_map: Optional[np.ndarray] = None) -> np.ndarray:
        """
        Calculate PSF via FFT.
        
        Args:
            pupil_grid_Y, Z: Coordinates at pupil.
            wavefront_map: Wavefront error in waves.
            intensity_map: Pupil apodization (default uniform).
            
        Returns:
            2D PSF array (normalized intensity).
        """
        # Create complex pupil function
        # P(y, z) = A(y, z) * exp(i * 2 * pi * W(y, z))
        
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
        pad_factor = 2 # or 4 for smoother PSF
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
        if not NUMPY_AVAILABLE:
            return np.array([])
            
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


class BeamSynthesisPropagator:
    """
    Propagates a wavefront by decomposing it into Gaussian beamlets.
    (Beam Synthesis Propagation / BSP)
    """
    def __init__(self, system: OpticalSystem):
        self.system = system
        self.tracer = SystemRayTracer3D(system)

    def propagate_to_image(self, wavelength_mm: float = WAVELENGTH_GREEN * NM_TO_MM, 
                          grid_size: int = 32, image_plane_x: Optional[float] = None,
                          detector_size: float = 0.1, detector_pixels: int = 64) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
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
        
        # Beamlet spacing
        delta = ep_diam / grid_size
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
            
        det_y = np.linspace(-detector_size/2, detector_size/2, detector_pixels)
        det_z = np.linspace(-detector_size/2, detector_size/2, detector_pixels)
        DY, DZ = np.meshgrid(det_y, det_z)
        
        E_field = np.zeros_like(DY, dtype=complex)
        
        # 3. Sum Beamlets
        for beam in beamlets:
            # Intersect ray with image plane
            if abs(beam.ray.direction.x) < 1e-6: continue
            
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
            amp = (w0 / wx) * np.exp(-(local_y**2)/(wx**2) - (local_z**2)/(wy**2))
            
            # Phase
            k = 2 * np.pi / wavelength
            phase_curv = k * (local_y**2 / (2*Rx) + local_z**2 / (2*Ry))
            phase_opl = k * beam.ray.optical_path_length
            
            E_beam = amp * np.exp(-1j * (phase_curv + phase_opl))
            E_field += E_beam
            
        Intensity = np.abs(E_field)**2
        return DY, DZ, Intensity

    def _trace_beamlet(self, beam: GaussianBeam) -> None:
        """Helper to trace beamlet through system elements."""
        for i, element in enumerate(self.system.elements):
            if beam.ray.terminated: break
            
            tracer = LensRayTracer3D(element.lens, x_offset=element.position)
            
            # Front
            if not tracer.trace_surface(beam.ray, 'front', 'refract'):
                beam.ray.terminated = True
                return
            
            # Update q (distance from previous)
            if len(beam.ray.path) >= 2:
                dist = (beam.ray.path[-1] - beam.ray.path[-2]).magnitude()
                beam.q_x += dist
                beam.q_y += dist
            
            # Refract beam q
            beam.refract(1.0, element.lens.refractive_index, element.lens.radius_of_curvature_1)
            
            # Back
            if not tracer.trace_surface(beam.ray, 'back', 'refract'):
                beam.ray.terminated = True
                return
                
            if len(beam.ray.path) >= 2:
                dist = (beam.ray.path[-1] - beam.ray.path[-2]).magnitude()
                beam.q_x += dist
                beam.q_y += dist
            
            # Refract beam q
            beam.refract(element.lens.refractive_index, 1.0, element.lens.radius_of_curvature_2)
