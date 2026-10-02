import unittest
import math

from src.constants import RAY_EXIT_PROPAGATION_2D_MM
from src.optical_system import OpticalSystem, create_doublet
from src.lens import Lens
from src.ray import Ray, Ray3D
from src.tracer_2d import SystemRayTracer
from src.tracer_3d import SystemRayTracer3D
from src.vector3 import vec3


class TestSystemRayTracer(unittest.TestCase):
    def setUp(self):
        # Create two lenses
        self.lens1 = Lens(
            name="Lens 1",
            radius_of_curvature_1=100,
            radius_of_curvature_2=-100,
            thickness=10,
            diameter=50,
        )
        self.lens2 = Lens(
            name="Lens 2",
            radius_of_curvature_1=100,
            radius_of_curvature_2=-100,
            thickness=10,
            diameter=50,
        )

        # Create system
        self.system = OpticalSystem(name="Test System")
        self.system.add_lens(self.lens1, air_gap_before=0)
        self.system.add_lens(self.lens2, air_gap_before=20)  # 20mm gap

        self.tracer = SystemRayTracer(self.system)

    def test_system_structure(self):
        """Verify system structure"""
        self.assertEqual(len(self.system.elements), 2)
        self.assertEqual(len(self.system.air_gaps), 1)
        self.assertEqual(self.system.air_gaps[0].thickness, 20.0)

        # Check positions
        # Lens 1 at 0.0, thickness 10.0
        # Gap starts at 10.0, thickness 20.0
        # Lens 2 starts at 30.0
        self.assertEqual(self.system.elements[0].position, 0.0)
        self.assertEqual(self.system.elements[1].position, 30.0)

    def test_trace_parallel_rays(self):
        """Test tracing parallel rays through system"""
        rays = self.tracer.trace_parallel_rays(num_rays=3, angle_deg=0.0)

        self.assertEqual(len(rays), 3)

        for ray in rays:
            # Ray should have multiple points in path
            self.assertGreater(len(ray.path), 2)

            # Final x should be beyond the last lens
            # Last lens ends at 30 + 10 = 40
            # Ray propagates 100mm after
            final_x = ray.path[-1][0]
            self.assertGreater(final_x, 40.0)

    def test_missed_ray_does_not_teleport(self):
        """A ray missing an aperture must terminate, never jump downstream."""
        narrow = Lens(
            radius_of_curvature_1=100,
            radius_of_curvature_2=-100,
            thickness=10,
            diameter=20,
        )
        wide = Lens(
            radius_of_curvature_1=100,
            radius_of_curvature_2=-100,
            thickness=10,
            diameter=50,
        )
        system = OpticalSystem(name="Teleport Test")
        system.add_lens(narrow, air_gap_before=0)
        system.add_lens(wide, air_gap_before=20)
        tracer = SystemRayTracer(system)

        # Outside lens 1 (h=10) but inside lens 2 (h=25): must still stop.
        ray = Ray(x=-100.0, y=15.0, angle_rad=0.0)
        tracer.trace_ray(ray)

        self.assertFalse(ray.hit)
        self.assertTrue(ray.terminated)
        for x, _ in ray.path:
            self.assertLess(x, 30.0)  # never reaches lens 2 at x=30

    def test_tracers_sync_after_mutation(self):
        """Hoisted tracers must pick up lens edits between trace calls."""
        tracer = SystemRayTracer(self.system)
        before = [t.d for t in tracer._tracers]
        self.assertEqual(before, [10, 10])

        self.lens1.thickness = 25.0
        self.system.refresh_references({self.lens1.id: self.lens1})
        tracer.trace_parallel_rays(num_rays=1)

        after = [t.d for t in tracer._tracers]
        self.assertEqual(after, [25.0, 10])
        # Second element shifted by the new thickness (25 + 20 gap).
        self.assertEqual(self.system.elements[1].position, 45.0)


class TestConcaveFirstElement(unittest.TestCase):
    """Elements with R1 < 0 must trace, not be silently dropped.

    Advancing a ray to the next element's vertex plane overshoots a concave
    front surface: its sag is negative, so the whole surface sits behind that
    plane and every sphere root ends up behind the ray. That dropped the
    second element of every cemented achromat.
    """

    @staticmethod
    def _focus(paths):
        """Axis crossing of a set of traced ray paths."""
        crossings = []
        for path in paths:
            for (x1, y1), (x2, y2) in zip(path, path[1:]):
                if y1 * y2 <= 0 and abs(y2 - y1) > 1e-12:
                    crossings.append(x1 + (-y1 / (y2 - y1)) * (x2 - x1))
        return sum(crossings) / len(crossings) if crossings else None

    def test_cemented_doublet_flint_element_traces(self):
        """The app's own achromat: flint has R1 = -62 and must be traced."""
        system = create_doublet(100.0, 25.0)
        self.assertLess(system.elements[1].lens.radius_of_curvature_1, 0.0)

        rays = SystemRayTracer(system).trace_parallel_rays(num_rays=9)

        for ray in rays:
            self.assertTrue(ray.hit, f"ray at h={ray.path[0][1]} never hit")
            self.assertFalse(ray.terminated, f"ray at h={ray.path[0][1]} terminated")

    def test_cemented_doublet_focus_matches_analytic_bfl(self):
        """Rays must converge where the analytic BFL says, not diverge."""
        system = create_doublet(100.0, 25.0)
        rays = SystemRayTracer(system).trace_parallel_rays(num_rays=9)

        focus_x = self._focus([ray.path for ray in rays])
        expected = system.elements[1].position + system.calculate_back_focal_length()

        self.assertIsNotNone(focus_x)
        self.assertGreater(focus_x, expected)  # marginal rays focus short of paraxial
        self.assertLess(focus_x, expected + 5.0)

    def test_negative_first_elements_across_air_gap(self):
        """Both elements concave-first, separated by an air gap."""
        system = OpticalSystem(name="Negative first")
        system.add_lens(
            Lens(
                radius_of_curvature_1=-40.0,
                radius_of_curvature_2=-200.0,
                thickness=5.0,
                diameter=30.0,
                refractive_index=1.5,
            )
        )
        system.add_lens(
            Lens(
                radius_of_curvature_1=-60.0,
                radius_of_curvature_2=120.0,
                thickness=4.0,
                diameter=30.0,
                refractive_index=1.6,
            ),
            air_gap_before=3.0,
        )

        rays = SystemRayTracer(system).trace_parallel_rays(num_rays=7, fill=0.8)
        for ray in rays:
            self.assertTrue(ray.hit)
            self.assertFalse(ray.terminated)
            # start, 2 surfaces per element, exit draw
            self.assertGreaterEqual(len(ray.path), 6)

    def test_air_gap_credited_to_optical_path_length(self):
        """No explicit hop between elements, but the air must still count."""
        system = OpticalSystem(name="OPL")
        system.add_lens(
            Lens(
                radius_of_curvature_1=100.0,
                radius_of_curvature_2=-100.0,
                thickness=5.0,
                diameter=30.0,
                refractive_index=1.5,
            )
        )
        system.add_lens(
            Lens(
                radius_of_curvature_1=100.0,
                radius_of_curvature_2=-100.0,
                thickness=5.0,
                diameter=30.0,
                refractive_index=1.5,
            ),
            air_gap_before=10.0,
        )
        ray = Ray(x=-100.0, y=0.0, angle_rad=0.0)
        SystemRayTracer(system).trace_ray(ray)

        # Straight through: 100mm of air to the first surface, 5mm of glass,
        # 10mm of air, 5mm of glass, then 150mm of exit draw - all at n=1
        # except the two glass legs at n=1.5. The air gap between the
        # elements must be present.
        expected = 100.0 + 5.0 * 1.5 + 10.0 + 5.0 * 1.5 + RAY_EXIT_PROPAGATION_2D_MM
        self.assertAlmostEqual(ray.optical_path_length, expected, places=6)

    def test_cemented_doublet_matches_3d_tracer(self):
        """2D and 3D must agree on every surface vertex of a negative element."""
        system = create_doublet(100.0, 25.0)
        ray2d = Ray(x=-100.0, y=12.5, angle_rad=0.0)
        SystemRayTracer(system).trace_ray(ray2d)

        ray3d = Ray3D(vec3(-100.0, 12.5, 0.0), vec3(1, 0, 0))
        SystemRayTracer3D(system).trace_ray(ray3d)

        # Without this the comparison below passes vacuously on a ray that
        # stopped early: its shorter path is still a subset of the 3D one.
        self.assertTrue(ray2d.hit)
        self.assertFalse(ray2d.terminated)

        vertices_3d = sorted({(round(p.x, 9), round(p.y, 9)) for p in ray3d.path})
        for x, y in ray2d.path[1:-1]:
            self.assertIn((round(x, 9), round(y, 9)), vertices_3d)


if __name__ == "__main__":
    unittest.main()
