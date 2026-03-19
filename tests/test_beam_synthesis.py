import unittest
import math
import sys

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    np = None
    NUMPY_AVAILABLE = False

from src.analysis.beam_synthesis import GaussianBeam, WavefrontSensor, PSFCalculator
from src.vector3 import vec3
from src.ray_tracer import Ray3D
from src.optical_system import OpticalSystem, Lens
from src.constants import WAVELENGTH_GREEN, NM_TO_MM

class TestGaussianBeam(unittest.TestCase):
    def test_initialization(self):
        w0 = 0.1 # mm
        wavelength = 0.00055 # mm
        zR = math.pi * w0**2 / wavelength
        q0 = complex(0, zR) # At waist, R=inf, q = i*zR
        
        beam = GaussianBeam(
            wavelength=wavelength,
            q_x=q0,
            q_y=q0,
            ray=Ray3D(vec3(0,0,0), vec3(1,0,0))
        )
        
        self.assertAlmostEqual(beam.w_x, w0, places=5)
        self.assertEqual(beam.R_x, float('inf'))
        
    def test_propagation(self):
        w0 = 0.1
        wavelength = 0.00055
        zR = math.pi * w0**2 / wavelength
        q0 = complex(0, zR)
        
        beam = GaussianBeam(
            wavelength=wavelength,
            q_x=q0,
            q_y=q0,
            ray=Ray3D(vec3(0,0,0), vec3(1,0,0))
        )
        
        # Propagate by Rayleigh range
        beam.propagate(zR)
        
        # Waist should increase by sqrt(2)
        expected_w = w0 * math.sqrt(2)
        self.assertAlmostEqual(beam.w_x, expected_w, places=4)
        
        # Radius of curvature should be 2*zR (minimum curvature)
        self.assertAlmostEqual(beam.R_x, 2*zR, places=4)

    def test_refraction_flat(self):
        # Refraction at flat surface (R=inf)
        w0 = 0.1
        wavelength = 0.00055
        zR = math.pi * w0**2 / wavelength
        q0 = complex(0, zR)
        
        beam = GaussianBeam(
            wavelength=wavelength,
            q_x=q0,
            q_y=q0,
            ray=Ray3D(vec3(0,0,0), vec3(1,0,0))
        )
        
        # Refract Air -> Glass
        n1 = 1.0
        n2 = 1.5
        beam.refract(n1, n2, float('inf'))
        
        # q_new should be q_old * (n2/n1) ?
        # Formula: 1/q_out = (n1/n2) * 1/q_in
        # q_out = (n2/n1) * q_in
        
        self.assertAlmostEqual(beam.q_x.imag, q0.imag * 1.5, places=5)
        
        # Waist size inside medium?
        # w_new = sqrt(-lambda/(pi * Im(1/q_new)))
        # 1/q_new = (n1/n2) * 1/q_old = (1/1.5) * (1/i*zR) = -i / (1.5*zR)
        # Im(1/q_new) = -1/(1.5*zR)
        # w_new = sqrt(lambda * 1.5 * zR / pi) = sqrt(1.5) * w0
        # Wait. Physical beam size shouldn't change abruptly at interface?
        # Boundary condition: E-field continuity implies w is continuous.
        # But divergence changes.
        # Let's check w property.
        
        # w_x property uses self.wavelength.
        # If beam enters medium, wavelength changes to lambda/n.
        # Does GaussianBeam update its wavelength? No, it stores `wavelength` parameter.
        # If we want to simulate inside medium, we should update beam.wavelength manually?
        # Or `refract` should do it?
        # Typically wavelength is constant (vacuum) in the object, and n is used in formulas.
        # But `GaussianBeam` class has `wavelength` field.
        # If that field is vacuum wavelength, then formula for w needs n.
        # If it's local wavelength, we must update it.
        pass

class TestPSF(unittest.TestCase):
    @unittest.skipIf(not NUMPY_AVAILABLE, "numpy not installed")
    def test_psf_calculation(self):
        # Create a dummy perfect wavefront (flat)
        N = 64
        Y, Z = np.meshgrid(np.linspace(-1, 1, N), np.linspace(-1, 1, N))
        W = np.zeros_like(Y)
        
        # Mask circle
        mask = Y**2 + Z**2 > 1
        W[mask] = np.nan
        
        psf = PSFCalculator.calculate_psf(Y, Z, W)
        
        self.assertEqual(psf.shape[0], N*2) # padded
        
        # Peak should be at center
        center = N # padded size is 2*N, center at N
        self.assertAlmostEqual(psf[center, center], 1.0, places=5)
        
        # Should be symmetric (Airy disk like)
        self.assertAlmostEqual(psf[center+1, center], psf[center-1, center], places=5)

if __name__ == '__main__':
    unittest.main()
