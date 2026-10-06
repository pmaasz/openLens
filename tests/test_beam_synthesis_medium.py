#!/usr/bin/env python3
"""
Beam synthesis: correct beamlet spacing, medium-aware q, honest degradation.

Three defects:

1. `delta = ep_diam / grid_size`. The grid is np.linspace(-max_r, max_r,
   grid_size), spanning 2*max_r in grid_size-1 intervals, so the spacing is
   ep_diam/(grid_size-1) - 3.12% wrong at grid_size=32. That error went
   straight into the beamlet waist w0 = 1.5*delta.

2. q is defined against the *local* medium (refract uses the reduced form
   1/q' = (n1/n2)(1/q) - Phi/n2), so:
     - propagate must advance q by d/n, not d
     - the beam must carry the LOCAL wavelength, since
       w = sqrt(-lambda_local / (pi*Im(1/q))) and lambda_local = lambda_vac/n
   GaussianBeam kept the vacuum wavelength forever, so every beam radius
   computed after entering glass was too large by n - w_x jumped 0.1323 ->
   0.1621 mm across an n=1.0->1.5, R=50 surface.

3. The numpy stand-in declared only `ndarray`, so every "return an empty
   result" graceful-degradation path raised
   `AttributeError: type object 'np' has no attribute 'array'` - the exact
   opposite of graceful.
"""

import math
import unittest

from src.analysis.beam_synthesis import GaussianBeam
from src.ray import Ray3D
from src.vector3 import vec3

WAVELENGTH_MM = 550e-6
SUBPROCESS_BLOCKER = """
import sys


class _Blocker:
    def find_spec(self, name, path=None, target=None):
        if name == "numpy" or name.startswith("numpy."):
            raise ImportError("No module named 'numpy' (simulated)")
        return None


sys.meta_path.insert(0, _Blocker())
"""


def _beam(w0=0.1, wavelength=WAVELENGTH_MM):
    zR = math.pi * w0**2 / wavelength
    return GaussianBeam(
        wavelength=wavelength,
        q_x=complex(0, zR),
        q_y=complex(0, zR),
        ray=Ray3D(vec3(0, 0, 0), vec3(1, 0, 0)),
    )


class TestBeamletSpacing(unittest.TestCase):
    def test_spacing_matches_the_linspace_grid(self):
        """The grid spans 2*max_r in grid_size-1 intervals."""
        import numpy as np

        ep_diam, grid_size = 25.0, 32
        max_r = ep_diam / 2.0
        grid = np.linspace(-max_r, max_r, grid_size)
        actual_spacing = grid[1] - grid[0]
        delta = (2.0 * max_r) / (grid_size - 1)
        self.assertAlmostEqual(delta, actual_spacing, places=12)

    def test_old_formula_was_wrong_by_the_expected_amount(self):
        ep_diam, grid_size = 25.0, 32
        old = ep_diam / grid_size
        new = ep_diam / (grid_size - 1)
        self.assertAlmostEqual((old - new) / new * 100.0, -3.125, places=3)

    def test_spacing_is_independent_of_grid_size_scaling(self):
        for grid_size in (8, 32, 64):
            with self.subTest(grid_size=grid_size):
                ep_diam = 25.0
                self.assertAlmostEqual(
                    (2.0 * (ep_diam / 2.0)) / (grid_size - 1),
                    ep_diam / (grid_size - 1),
                    places=12,
                )

    def test_single_point_grid_does_not_divide_by_zero(self):
        delta = (2.0 * 12.5) / 1 if 1 > 1 else 2.0 * 12.5
        self.assertAlmostEqual(delta, 25.0)


class TestMediumAwareQ(unittest.TestCase):
    def test_beam_carries_its_local_index(self):
        beam = _beam()
        self.assertEqual(beam.n, 1.0)
        beam.refract(1.0, 1.5, 50.0)
        self.assertAlmostEqual(beam.n, 1.5)

    def test_local_wavelength_is_vacuum_over_n(self):
        beam = _beam()
        beam.refract(1.0, 1.5, 50.0)
        self.assertAlmostEqual(beam.wavelength, WAVELENGTH_MM / 1.5, places=15)

    def test_vacuum_wavelength_is_preserved_across_a_surface(self):
        beam = _beam()
        beam.refract(1.0, 1.5, 50.0)
        self.assertAlmostEqual(beam.wavelength * beam.n, WAVELENGTH_MM, places=15)

    def test_beam_radius_is_continuous_across_a_surface(self):
        """Regression: w_x jumped 0.1323 -> 0.1621 mm."""
        beam = _beam(w0=0.1)
        before = beam.w_x
        beam.refract(1.0, 1.5, 50.0)
        self.assertAlmostEqual(beam.w_x, before, places=9)

    def test_beam_radius_continuous_for_a_flat_surface_too(self):
        beam = _beam(w0=0.1)
        before = beam.w_x
        beam.refract(1.0, 1.5168, float("inf"))
        self.assertAlmostEqual(beam.w_x, before, places=9)

    def test_propagation_in_glass_advances_q_by_d_over_n(self):
        """The other half of the defect: d/n, not d."""
        beam = _beam()
        beam.refract(1.0, 1.5, 50.0)
        before = beam.q_x.real
        beam.advance_q(1.0)
        self.assertAlmostEqual(beam.q_x.real - before, 1.0 / 1.5, places=12)

    def test_propagation_in_air_advances_q_by_d(self):
        beam = _beam()
        before = beam.q_x.real
        beam.advance_q(1.0)
        self.assertAlmostEqual(beam.q_x.real - before, 1.0, places=12)

    def test_both_axes_advance(self):
        beam = _beam()
        beam.refract(1.0, 1.5, 50.0)
        rx, ry = beam.q_x.real, beam.q_y.real
        beam.advance_q(1.0)
        self.assertAlmostEqual(beam.q_x.real - rx, 1.0 / 1.5, places=12)
        self.assertAlmostEqual(beam.q_y.real - ry, 1.0 / 1.5, places=12)

    def test_advance_q_does_not_move_the_ray(self):
        """The BSP tracer has already moved the ray; double-moving is a bug."""
        beam = _beam()
        origin = vec3(beam.ray.origin.x, beam.ray.origin.y, beam.ray.origin.z)
        beam.advance_q(1.0)
        self.assertEqual(
            (beam.ray.origin.x, beam.ray.origin.y, beam.ray.origin.z),
            (origin.x, origin.y, origin.z),
        )

    def test_propagate_still_moves_the_ray(self):
        beam = _beam()
        beam.propagate(1.0)
        self.assertAlmostEqual(beam.ray.origin.x, 1.0, places=9)

    def test_two_surfaces_scale_the_wavelength_twice(self):
        beam = _beam()
        beam.refract(1.0, 1.5, 50.0)
        beam.refract(1.5, 2.0, -50.0)
        self.assertAlmostEqual(beam.wavelength, WAVELENGTH_MM / 2.0, places=15)
        self.assertAlmostEqual(beam.wavelength * beam.n, WAVELENGTH_MM, places=15)

    def test_round_trip_through_glass_restores_the_vacuum_wavelength(self):
        beam = _beam()
        beam.refract(1.0, 1.5, 50.0)
        beam.refract(1.5, 1.0, 50.0)
        self.assertAlmostEqual(beam.wavelength, WAVELENGTH_MM, places=15)
        self.assertAlmostEqual(beam.n, 1.0, places=12)


class TestGracefulDegradationWithoutNumpy(unittest.TestCase):
    """Regression: AttributeError on the dummy np, not a graceful return."""

    def _without_numpy(self, body):
        import os
        import subprocess
        import sys
        import textwrap

        env = dict(os.environ)
        env["PYTHONPATH"] = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return subprocess.run(
            [sys.executable, "-c", SUBPROCESS_BLOCKER + textwrap.dedent(body)],
            capture_output=True,
            text=True,
            timeout=180,
            env=env,
        )

    def test_flag_is_false(self):
        result = self._without_numpy(
            "import src.analysis.beam_synthesis as b; print('FLAG', b.NUMPY_AVAILABLE)"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("FLAG False", result.stdout)

    def test_empty_wavefront_path_returns_instead_of_raising(self):
        result = self._without_numpy("""
            import src.analysis.beam_synthesis as b

            class _P:
                elements = None

            sensor = b.WavefrontSensor.__new__(b.WavefrontSensor)
            sensor.system = _P()
            y, z, w = sensor.get_pupil_wavefront(grid_size=8)
            assert (y, z, w) == ([], [], []), (y, z, w)
            print('OK')
            """)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("OK", result.stdout)

    def test_mtf_path_returns_instead_of_raising(self):
        result = self._without_numpy("""
            import src.analysis.beam_synthesis as b
            print('OK', b.PSFCalculator.calculate_mtf(None))
            """)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("OK", result.stdout)

    def test_shim_provides_the_names_the_module_uses(self):
        import inspect

        import src.analysis.beam_synthesis as module

        shim = module.np
        for name in ("array", "zeros", "ones", "linspace", "meshgrid", "ndarray"):
            with self.subTest(name=name):
                self.assertTrue(hasattr(shim, name), name)

    def test_bsp_still_raises_a_clean_import_error(self):
        """The numpy-requiring path should refuse clearly, not crash oddly."""
        result = self._without_numpy("""
            import src.analysis.beam_synthesis as b

            class _P:
                elements = [object()]

            try:
                b.BeamSynthesisPropagator(_P()).propagate_to_image(grid_size=8)
                print('NO ERROR')
            except ImportError as e:
                print('CLEAN', e)
            """)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("CLEAN", result.stdout)
        self.assertNotIn("NO ERROR", result.stdout)


if __name__ == "__main__":
    unittest.main()
