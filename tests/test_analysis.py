import unittest
import math
import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.analysis import SpotDiagram
from src.optical_system import OpticalSystem, create_doublet
from src.lens import Lens
from src.constants import NM_TO_MM


class TestSpotDiagram(unittest.TestCase):
    def setUp(self):
        # Create a simple singlet system (perfect paraxial lens approx)
        self.lens = Lens(
            radius_of_curvature_1=100.0,
            radius_of_curvature_2=-100.0,
            thickness=5.0,
            diameter=25.0,
            refractive_index=1.5,
        )
        self.system = OpticalSystem()
        self.system.add_lens(self.lens)

        self.spot = SpotDiagram(self.system)

    def test_hexapolar_grid(self):
        """Test hexapolar grid generation"""
        points = self.spot.generate_hexapolar_grid(rings=2, diameter=10.0)
        # Expected points: 1 (center) + 6 (ring 1) + 12 (ring 2) = 19
        self.assertEqual(len(points), 19)

        # Check center
        self.assertEqual(points[0], (0.0, 0.0))

        # Check radius of last point (should be on the edge radius 5.0)
        # The points are generated in order of rings
        last_pt = points[-1]
        dist = math.sqrt(last_pt[0] ** 2 + last_pt[1] ** 2)
        self.assertAlmostEqual(dist, 5.0, places=4)

    def test_on_axis_spot(self):
        """Test on-axis spot diagram"""
        results = self.spot.trace_spot(field_angle_x_deg=0, field_angle_y_deg=0, num_rings=3)

        # For a symmetric lens on axis, centroid should be at (0,0)
        cent_y, cent_z = results["centroid"]
        self.assertAlmostEqual(cent_y, 0.0, places=3)
        self.assertAlmostEqual(cent_z, 0.0, places=3)

        # RMS radius should be small (but not zero due to spherical aberration)
        self.assertGreater(results["rms_radius"], 0.0)
        self.assertLess(results["rms_radius"], 0.3)  # Expect decent focus (RMS ~0.24)

    def test_defocus(self):
        """Test that spot size increases with defocus"""
        # Best focus
        res_focus = self.spot.trace_spot(focus_shift_mm=0.0)

        # Defocus by 1mm
        res_defocus = self.spot.trace_spot(focus_shift_mm=1.0)

        self.assertGreater(res_defocus["rms_radius"], res_focus["rms_radius"])

    def test_off_axis_spot(self):
        """Test off-axis spot diagram"""
        # 5 degrees off-axis in Y
        results = self.spot.trace_spot(field_angle_y_deg=5.0, num_rings=3)

        # Centroid should be shifted in Y
        cent_y, cent_z = results["centroid"]
        self.assertNotAlmostEqual(cent_y, 0.0)
        self.assertAlmostEqual(cent_z, 0.0, places=3)  # Symmetry in Z preserved

        # RMS should likely be worse than on-axis due to coma/astigmatism
        on_axis = self.spot.trace_spot(field_angle_y_deg=0.0, num_rings=3)
        self.assertGreater(results["rms_radius"], on_axis["rms_radius"])


class TestSpotDiagramFailureModes(unittest.TestCase):
    """trace_spot must surface its real failures, not synthesise a result.

    Two defects lived in the same try/finally: spot_points was bound inside
    the try while the statistics block read it from the finally, and a return
    in the finally discarded any in-flight exception.
    """

    def setUp(self):
        self.system = OpticalSystem(name="FailureModes")
        self.lens = Lens(
            radius_of_curvature_1=50.0,
            radius_of_curvature_2=-50.0,
            thickness=5.0,
            diameter=20.0,
            refractive_index=1.5,
        )
        self.system.add_lens(self.lens)

    def test_empty_system_raises_index_error_not_unbound_local(self):
        """Regression: the real IndexError was masked as UnboundLocalError."""
        empty = SpotDiagram(OpticalSystem(name="empty"))
        with self.assertRaises(IndexError):
            empty.trace_spot()

    def test_tracer_failure_propagates_instead_of_returning_zero_radius(self):
        """A return in finally turned a tracer bug into rms_radius 0.0."""
        spot = SpotDiagram(self.system)
        real_trace = spot.tracer.trace_ray
        calls = {"n": 0}

        def failing(ray):
            calls["n"] += 1
            if calls["n"] >= 2:
                # Fail before any spot point lands, which is the case the
                # finally-return used to swallow.
                raise RuntimeError("tracer exploded")
            return real_trace(ray)

        spot.tracer.trace_ray = failing
        with self.assertRaises(RuntimeError):
            spot.trace_spot(num_rings=3)

    def test_tracer_failure_propagates_even_after_points_landed(self):
        """Failing mid-loop must not be reported as a completed analysis."""
        spot = SpotDiagram(self.system)
        real_trace = spot.tracer.trace_ray
        calls = {"n": 0}

        def failing(ray):
            calls["n"] += 1
            if calls["n"] > 6:
                raise RuntimeError("tracer exploded mid-loop")
            return real_trace(ray)

        spot.tracer.trace_ray = failing
        with self.assertRaises(RuntimeError):
            spot.trace_spot(num_rings=3)

    def test_lens_state_restored_when_tracer_raises(self):
        """The finally must still restore state on the propagating path."""
        self.lens.wavelength = 486.1
        self.lens.refractive_index = 1.52238

        spot = SpotDiagram(self.system)

        def failing(ray):
            raise RuntimeError("kaboom")

        spot.tracer.trace_ray = failing
        with self.assertRaises(RuntimeError):
            spot.trace_spot(wavelength_nm=656.3, num_rings=2)

        self.assertAlmostEqual(self.lens.wavelength, 486.1)
        self.assertAlmostEqual(self.lens.refractive_index, 1.52238)

    def test_genuine_no_rays_still_returns_empty_stats(self):
        """The legitimate blocked/TIR outcome keeps its graceful result."""
        spot = SpotDiagram(self.system)

        def terminating(ray):
            ray.terminated = True
            return ray

        spot.tracer.trace_ray = terminating
        result = spot.trace_spot(num_rings=2)

        self.assertEqual(result["valid_rays"], 0)
        self.assertEqual(result["rms_radius"], 0.0)
        self.assertEqual(result["points"], [])
        self.assertEqual(result["centroid"], (0.0, 0.0))
        self.assertIn("No rays", result["error"])

    def test_normal_run_unaffected(self):
        """Sanity: a real system still produces real statistics."""
        result = SpotDiagram(self.system).trace_spot(num_rings=3)
        self.assertGreater(result["valid_rays"], 0)
        self.assertGreater(result["rms_radius"], 0.0)
        self.assertEqual(len(result["points"]), result["valid_rays"])
        self.assertNotIn("error", result)


if __name__ == "__main__":
    unittest.main()
