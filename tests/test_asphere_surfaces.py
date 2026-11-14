"""Even-order polynomial asphere surfaces (#795).

Pins the sag convention, both ray tracers, serialization, the .zmx
round-trip and the optimizer hook.
"""

import math
import os
import tempfile
import unittest

from openlens.database import DatabaseManager
from openlens.export_formats import ZemaxSystemExporter, ZemaxSystemImporter
from openlens.lens import Lens
from openlens.optical_system import OpticalSystem
from openlens.optimizer import LensOptimizer, OptimizationVariable
from openlens.ray import OpticalIntersector, Ray, Ray3D
from openlens.tracer_2d import LensRayTracer
from openlens.tracer_3d import LensRayTracer3D
from openlens.validation import (
    ValidationError,
    validate_asphere_coefficients,
    validate_lens_parameters,
)
from openlens.vector3 import vec3


def _asphere_lens(**kwargs):
    values = dict(
        radius_of_curvature_1=50.0,
        radius_of_curvature_2=0.0,
        thickness=5.0,
        diameter=60.0,
        material="BK7",
    )
    values.update(kwargs)
    return Lens(**values)


class TestAsphereSag(unittest.TestCase):
    def test_even_terms_add_to_the_spherical_base(self):
        lens = _asphere_lens(asphere_coefficients_1=[-1e-6, 2e-9])
        y = 10.0
        base = 50.0 - math.sqrt(50.0**2 - y**2)
        expected = base - 1e-6 * y**4 + 2e-9 * y**6
        self.assertAlmostEqual(lens.get_sag_1(y), expected, places=12)

    def test_flat_base_uses_the_polynomial_alone(self):
        lens = _asphere_lens(radius_of_curvature_1=0.0, asphere_coefficients_1=[1e-4])
        self.assertAlmostEqual(lens.get_sag_1(10.0), 1e-4 * 10.0**4, places=12)

    def test_conic_base_and_polynomial_combine(self):
        lens = _asphere_lens(conic_constant_1=-1.0, asphere_coefficients_1=[-1e-6])
        y = 10.0
        expected = y * y / (2.0 * 50.0) - 1e-6 * y**4
        self.assertAlmostEqual(lens.get_sag_1(y), expected, places=12)

    def test_zero_coefficients_are_a_sphere(self):
        conic = _asphere_lens(conic_constant_1=-0.5)
        asphere = _asphere_lens(conic_constant_1=-0.5, asphere_coefficients_1=[0.0, 0.0])
        self.assertEqual(asphere.asphere_coefficients_1, [])
        self.assertAlmostEqual(conic.get_sag_1(12.0), asphere.get_sag_1(12.0), places=12)


class TestAsphereValidation(unittest.TestCase):
    def test_non_finite_coefficients_are_rejected(self):
        with self.assertRaises(ValidationError):
            validate_asphere_coefficients([float("nan")])
        with self.assertRaises(ValidationError):
            validate_asphere_coefficients([float("inf")])

    def test_too_many_coefficients_are_rejected(self):
        with self.assertRaises(ValidationError):
            validate_asphere_coefficients([0.0] * 8)

    def test_lens_model_rejects_non_finite_coefficients(self):
        with self.assertRaises(ValueError):
            Lens(asphere_coefficients_1=[float("nan")])

    def test_validate_lens_parameters_returns_the_coefficients(self):
        validated = validate_lens_parameters(
            radius1=50.0,
            radius2=-50.0,
            thickness=5.0,
            diameter=30.0,
            refractive_index=1.5168,
            asphere_coefficients_1=[-1e-5, 2e-8],
        )
        self.assertEqual(validated["asphere_coefficients_1"], [-1e-5, 2e-8])


class TestAspherePersistence(unittest.TestCase):
    def test_dict_round_trip(self):
        lens = _asphere_lens(asphere_coefficients_1=[-1e-5, 2e-8], asphere_coefficients_2=[1e-6])
        rebuilt = Lens.from_dict(lens.to_dict())
        self.assertEqual(rebuilt.asphere_coefficients_1, [-1e-5, 2e-8])
        self.assertEqual(rebuilt.asphere_coefficients_2, [1e-6])

    def test_sqlite_round_trip(self):
        lens = _asphere_lens(asphere_coefficients_1=[-1e-5, 2e-8])
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        try:
            db = DatabaseManager(tmp.name)
            db.save_lens(lens.to_dict())
            rows = [row for row in db.load_all() if row.get("row_type") == "Lens"]
            rebuilt = Lens.from_dict(rows[0])
        finally:
            os.unlink(tmp.name)

        self.assertEqual(rebuilt.asphere_coefficients_1, [-1e-5, 2e-8])

    def test_zemax_round_trip(self):
        lens = _asphere_lens(asphere_coefficients_1=[-1e-5, 2e-8], asphere_coefficients_2=[1e-6])
        system = OpticalSystem(name="Asphere")
        system.add_lens(lens)
        tmp = tempfile.NamedTemporaryFile(suffix=".zmx", delete=False)
        tmp.close()
        try:
            ZemaxSystemExporter.export_system(system, tmp.name)
            with open(tmp.name) as exported:
                text = exported.read()
            rebuilt = ZemaxSystemImporter.import_system(tmp.name).elements[0].lens
        finally:
            os.unlink(tmp.name)

        self.assertIn("TYPE EVENASPH", text)
        self.assertIn("PARM 2 -1e-05", text)
        self.assertEqual(rebuilt.asphere_coefficients_1, [-1e-5, 2e-8])
        self.assertEqual(rebuilt.asphere_coefficients_2, [1e-6])


class TestAsphereRayTracing(unittest.TestCase):
    def test_2d_hit_matches_the_analytic_sag(self):
        lens = _asphere_lens(asphere_coefficients_1=[-1e-5])
        y = 20.0
        ray = Ray(x=-10.0, y=y, angle_rad=0.0)
        LensRayTracer(lens).trace_ray(ray, propagate_distance=0.0)

        hit_x, hit_y = ray.path[1]
        self.assertAlmostEqual(hit_y, y, places=6)
        self.assertAlmostEqual(hit_x, lens.get_sag_1(y), places=9)

    def test_2d_asphere_differs_from_the_base_conic(self):
        lens = _asphere_lens(asphere_coefficients_1=[-1e-4])
        ray = Ray(x=-10.0, y=20.0, angle_rad=0.0)
        LensRayTracer(lens).trace_ray(ray, propagate_distance=0.0)
        asphere_hit = ray.path[1][0]

        sphere = 50.0 - math.sqrt(50.0**2 - 20.0**2)
        self.assertNotAlmostEqual(asphere_hit, sphere, places=3)

    def test_2d_and_3d_tracers_agree_on_the_hit(self):
        lens = _asphere_lens(asphere_coefficients_1=[-1e-5, 2e-8])
        y = 18.0
        ray2d = Ray(x=-10.0, y=y, angle_rad=0.0)
        LensRayTracer(lens).trace_ray(ray2d, propagate_distance=0.0)
        ray3d = Ray3D(origin=vec3(-10.0, 0.0, y), direction=vec3(1.0, 0.0, 0.0))
        LensRayTracer3D(lens).trace_surface(ray3d, "front")

        self.assertAlmostEqual(ray3d.origin.x, ray2d.path[1][0], places=9)
        self.assertAlmostEqual(ray3d.origin.z, ray2d.path[1][1], places=9)

    def test_3d_normal_refracts_at_the_analytic_angle(self):
        lens = _asphere_lens(asphere_coefficients_1=[-1e-5])
        tracer = LensRayTracer3D(lens)
        y = 20.0
        ray = Ray3D(origin=vec3(-10.0, 0.0, y), direction=vec3(1.0, 0.0, 0.0))
        tracer.trace_surface(ray, "front")

        slope = -1e-5 * 4.0 * y**3 + y / math.sqrt(50.0**2 - y**2)
        normal = vec3(1.0, 0.0, -slope).normalize()
        expected = OpticalIntersector.apply_snell(
            (1.0, 0.0, 0.0), (normal.x, normal.y, normal.z), 1.0, tracer.n
        )
        self.assertIsNotNone(expected)
        ex, ey, ez, is_tir = expected
        self.assertFalse(is_tir)
        self.assertAlmostEqual(ray.direction.x, ex, places=9)
        self.assertAlmostEqual(ray.direction.y, ey, places=9)
        self.assertAlmostEqual(ray.direction.z, ez, places=9)

    def test_back_surface_asphere_is_traced(self):
        lens = _asphere_lens(
            radius_of_curvature_1=0.0,
            radius_of_curvature_2=-50.0,
            asphere_coefficients_2=[-1e-5],
        )
        y = 20.0
        ray = Ray(x=-10.0, y=y, angle_rad=0.0)
        LensRayTracer(lens).trace_ray(ray, propagate_distance=0.0)

        hit_x, hit_y = ray.path[2]
        self.assertAlmostEqual(hit_y, y, places=6)
        self.assertAlmostEqual(hit_x, 5.0 + lens.get_sag_2(y), places=9)


class TestAsphereOptimizer(unittest.TestCase):
    def test_asphere_coefficient_variable_is_applied(self):
        lens = _asphere_lens(asphere_coefficients_1=[-1e-5])
        system = OpticalSystem(name="Asphere")
        system.add_lens(lens)
        optimizer = LensOptimizer(
            system,
            [OptimizationVariable("A6 front", 0, "asphere_coefficient_6_1", 0.0, -1e-3, 1e-3)],
            [],
        )

        applied = optimizer._apply_variables([-2e-8])
        self.assertEqual(applied.elements[0].lens.asphere_coefficients_1, [-1e-5, -2e-8])


if __name__ == "__main__":
    unittest.main()
