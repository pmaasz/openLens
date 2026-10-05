import unittest
import math
import sys

try:
    import numpy as np

    NUMPY_AVAILABLE = True
except ImportError:
    np = None
    NUMPY_AVAILABLE = False

from src.analysis.beam_synthesis import GaussianBeam, NUMPY_AVAILABLE
from src.vector3 import vec3
from src.ray_tracer import Ray3D
from src.optical_system import OpticalSystem, Lens
from src.constants import WAVELENGTH_GREEN, NM_TO_MM


class TestGaussianBeam(unittest.TestCase):
    def test_initialization(self):
        w0 = 0.1  # mm
        wavelength = 0.00055  # mm
        zR = math.pi * w0**2 / wavelength
        q0 = complex(0, zR)  # At waist, R=inf, q = i*zR

        beam = GaussianBeam(
            wavelength=wavelength,
            q_x=q0,
            q_y=q0,
            ray=Ray3D(vec3(0, 0, 0), vec3(1, 0, 0)),
        )

        self.assertAlmostEqual(beam.w_x, w0, places=5)
        self.assertEqual(beam.R_x, float("inf"))

    def test_propagation(self):
        w0 = 0.1
        wavelength = 0.00055
        zR = math.pi * w0**2 / wavelength
        q0 = complex(0, zR)

        beam = GaussianBeam(
            wavelength=wavelength,
            q_x=q0,
            q_y=q0,
            ray=Ray3D(vec3(0, 0, 0), vec3(1, 0, 0)),
        )

        # Propagate by Rayleigh range
        beam.propagate(zR)

        # Waist should increase by sqrt(2)
        expected_w = w0 * math.sqrt(2)
        self.assertAlmostEqual(beam.w_x, expected_w, places=4)

        # Radius of curvature should be 2*zR (minimum curvature)
        self.assertAlmostEqual(beam.R_x, 2 * zR, places=4)

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
            ray=Ray3D(vec3(0, 0, 0), vec3(1, 0, 0)),
        )

        # Refract Air -> Glass
        n1 = 1.0
        n2 = 1.5
        beam.refract(n1, n2, float("inf"))

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


class TestGaussianBeamCurvature(unittest.TestCase):
    """R_y must exist and agree with the analytic radius of curvature.

    propagate_to_image() reads beam.R_y for the sagittal phase term, so a
    missing property made every beam-synthesis propagation raise
    AttributeError. The existing tests only ever exercised R_x.
    """

    @staticmethod
    def _beam(q_x, q_y, wavelength=0.00055):
        return GaussianBeam(
            wavelength=wavelength,
            q_x=complex(*q_x),
            q_y=complex(*q_y),
            ray=Ray3D(vec3(0, 0, 0), vec3(1, 0, 0)),
        )

    @staticmethod
    def _analytic_R(q):
        """R = |q|^2 / Re(q), infinite at the waist."""
        if q.real == 0:
            return float("inf")
        return abs(q) ** 2 / q.real

    def test_ry_exists(self):
        beam = self._beam((3.0, 5.0), (3.0, 7.0))
        self.assertTrue(hasattr(beam, "R_y"))
        self.assertIsInstance(beam.R_y, float)

    def test_ry_matches_analytic_value(self):
        for real, imag in ((3.0, 5.0), (-2.0, 1.5), (10.0, 0.5), (-7.5, 2.0)):
            with self.subTest(q=complex(real, imag)):
                beam = self._beam((real, imag), (real, imag))
                self.assertAlmostEqual(beam.R_y, self._analytic_R(beam.q_y), places=9)

    def test_ry_at_waist_is_infinite(self):
        """A planar wavefront has infinite radius, as for R_x."""
        beam = self._beam((0.0, 5.0), (0.0, 5.0))
        self.assertEqual(beam.R_y, float("inf"))
        self.assertEqual(beam.R_x, float("inf"))

    def test_ry_is_independent_of_rx(self):
        """An astigmatic beam has different curvatures per plane."""
        beam = self._beam((3.0, 5.0), (3.0, 9.0))
        self.assertAlmostEqual(beam.R_x, self._analytic_R(beam.q_x), places=9)
        self.assertAlmostEqual(beam.R_y, self._analytic_R(beam.q_y), places=9)
        self.assertNotAlmostEqual(beam.R_x, beam.R_y, places=6)

    def test_ry_tracks_propagation_like_rx(self):
        beam = self._beam((0.0, 5.0), (0.0, 5.0))
        beam.propagate(5.0)
        self.assertAlmostEqual(beam.R_y, beam.R_x, places=9)
        self.assertAlmostEqual(beam.R_y, 10.0, places=6)  # 2*zR


@unittest.skipIf(not NUMPY_AVAILABLE, "numpy not installed")
class TestBeamSynthesisPropagation(unittest.TestCase):
    """propagate_to_image must run to completion, not raise part-way."""

    @staticmethod
    def _propagator():
        from src.analysis.beam_synthesis import BeamSynthesisPropagator

        system = OpticalSystem(name="BSP")
        system.add_lens(
            Lens(
                radius_of_curvature_1=50.0,
                radius_of_curvature_2=-50.0,
                thickness=5.0,
                diameter=20.0,
                refractive_index=1.5,
            )
        )
        return BeamSynthesisPropagator(system)

    def test_propagate_to_image_returns_finite_intensity(self):
        """Regression: raised AttributeError on beam.R_y for every beamlet."""
        DY, DZ, intensity = self._propagator().propagate_to_image(grid_size=8, detector_pixels=16)
        self.assertEqual(intensity.shape, DY.shape)
        self.assertEqual(intensity.shape, DZ.shape)
        self.assertTrue(np.all(np.isfinite(intensity)))
        self.assertGreater(float(intensity.max()), 0.0)

    def test_propagate_to_image_uses_the_passed_wavelength(self):
        """The phase term must read wavelength_mm, the actual parameter."""
        prop = self._propagator()
        _, _, at_green = prop.propagate_to_image(
            grid_size=8, detector_pixels=8, wavelength_mm=WAVELENGTH_GREEN * NM_TO_MM
        )
        _, _, at_blue = prop.propagate_to_image(
            grid_size=8, detector_pixels=8, wavelength_mm=450.0 * NM_TO_MM
        )
        # Different k, so the interference pattern must differ.
        self.assertFalse(np.allclose(at_green, at_blue))

    def test_empty_system_returns_empty_arrays(self):
        from src.analysis.beam_synthesis import BeamSynthesisPropagator

        prop = BeamSynthesisPropagator(OpticalSystem(name="Empty"))
        result = prop.propagate_to_image(grid_size=4, detector_pixels=4)
        self.assertEqual(len(result), 3)
        for arr in result:
            self.assertEqual(arr.size, 0)


if __name__ == "__main__":
    unittest.main()
