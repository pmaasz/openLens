"""Conic aspheric surface support (#74).

A conic surface is a sphere (K=0), parabola (K=-1), ellipse, or
hyperbola.  These tests pin the sag, rim feasibility, and both ray
tracers before the editor or Zemax round-trip are involved.
"""

import math
import os
import sqlite3
import tempfile
import unittest

from openlens.database import DatabaseManager
from openlens.lens import Lens
from openlens.optical_system import OpticalSystem
from openlens.ray import OpticalIntersector, Ray, Ray3D
from openlens.tracer_2d import LensRayTracer
from openlens.tracer_3d import LensRayTracer3D
from openlens.validation import ValidationError, validate_lens_parameters
from openlens.vector3 import vec3


def _conic_lens(**kwargs):
    """A 50 mm vertex-radius front surface with a 60 mm aperture."""
    values = dict(
        radius_of_curvature_1=50.0,
        radius_of_curvature_2=0.0,
        thickness=5.0,
        diameter=60.0,
        material="BK7",
    )
    values.update(kwargs)
    return Lens(**values)


class TestConicSag(unittest.TestCase):
    def test_zero_conic_constant_matches_sphere(self):
        lens = _conic_lens(conic_constant_1=0.0)
        y = 10.0
        expected = 50.0 - math.sqrt(50.0**2 - y**2)
        self.assertAlmostEqual(lens.get_sag_1(y), expected, places=9)

    def test_minus_one_conic_constant_is_a_parabola(self):
        lens = _conic_lens(conic_constant_1=-1.0)
        self.assertAlmostEqual(lens.get_sag_1(10.0), 10.0**2 / (2.0 * 50.0), places=9)
        self.assertAlmostEqual(lens.get_effective_radius_1(), 50.0)

    def test_oblate_conic_uses_the_conic_sag_formula(self):
        lens = _conic_lens(conic_constant_1=1.0)
        c = 1.0 / 50.0
        y = 10.0
        expected = c * y * y / (1.0 + math.sqrt(1.0 - 2.0 * c * c * y * y))
        self.assertAlmostEqual(lens.get_sag_1(y), expected, places=9)
        self.assertNotAlmostEqual(lens.get_sag_1(y), 50.0 - math.sqrt(50.0**2 - y * y))

    def test_conic_constants_survive_dict_round_trip(self):
        lens = _conic_lens(conic_constant_1=-0.5, conic_constant_2=0.25)
        rebuilt = Lens.from_dict(lens.to_dict())
        self.assertAlmostEqual(rebuilt.conic_constant_1, -0.5)
        self.assertAlmostEqual(rebuilt.conic_constant_2, 0.25)


class TestConicFeasibility(unittest.TestCase):
    def test_oblate_surface_beyond_its_real_domain_has_no_rim(self):
        lens = _conic_lens(conic_constant_1=1.0, diameter=100.0)
        # Real-domain radius is 1/(|c|*sqrt(1+K)) = 35.36 mm < 50 mm.
        self.assertIsNone(lens.calculate_edge_thickness())

    def test_validate_lens_parameters_rejects_unrealizable_conic(self):
        with self.assertRaises(ValidationError):
            validate_lens_parameters(
                radius1=50.0,
                radius2=-50.0,
                thickness=5.0,
                diameter=100.0,
                refractive_index=1.5168,
                conic_constant_1=1.0,
            )


class TestConicPersistence(unittest.TestCase):
    def test_conic_constants_round_trip_through_sqlite(self):
        lens = _conic_lens(conic_constant_1=-0.5, conic_constant_2=0.25)
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        try:
            db = DatabaseManager(tmp.name)
            db.save_lens(lens.to_dict())
            rows = [row for row in db.load_all() if row.get("row_type") == "Lens"]
            rebuilt = Lens.from_dict(rows[0])
            stored = (
                sqlite3.connect(tmp.name)
                .execute(
                    "SELECT conic_constant_1, conic_constant_2 FROM lenses WHERE id = ?",
                    (lens.id,),
                )
                .fetchone()
            )
        finally:
            os.unlink(tmp.name)

        self.assertEqual(stored, (-0.5, 0.25))
        self.assertAlmostEqual(rebuilt.conic_constant_1, -0.5)
        self.assertAlmostEqual(rebuilt.conic_constant_2, 0.25)

    def test_conic_constants_round_trip_inside_an_assembly(self):
        lens = _conic_lens(conic_constant_1=-0.5, conic_constant_2=0.25)
        system = OpticalSystem(name="Conic Assembly")
        system.add_lens(lens)
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        try:
            db = DatabaseManager(tmp.name)
            db.save_assembly(system.to_dict())
            rows = [row for row in db.load_all() if row.get("row_type") == "OpticalSystem"]
            element_lens = Lens.from_dict(rows[0]["elements"][0]["lens"])
        finally:
            os.unlink(tmp.name)

        self.assertAlmostEqual(element_lens.conic_constant_1, -0.5)
        self.assertAlmostEqual(element_lens.conic_constant_2, 0.25)


class TestConicRayTracing(unittest.TestCase):
    def test_2d_tracer_hits_the_conic_sag(self):
        lens = _conic_lens(conic_constant_1=-1.0)
        ray = Ray(x=0.0, y=20.0, angle_rad=0.0)
        LensRayTracer(lens).trace_ray(ray, propagate_distance=0.0)

        self.assertGreaterEqual(len(ray.path), 2)
        hit_x, hit_y = ray.path[1]
        self.assertAlmostEqual(hit_y, 20.0, places=6)
        self.assertAlmostEqual(hit_x, 20.0**2 / (2.0 * 50.0), places=6)

    def test_2d_tracer_hits_an_oblate_conic_sag(self):
        lens = _conic_lens(conic_constant_1=1.0)
        y = 10.0
        expected = 0.02 * y * y / (1.0 + math.sqrt(1.0 - 2.0 * 0.02**2 * y * y))
        ray = Ray(x=-10.0, y=y, angle_rad=0.0)
        LensRayTracer(lens).trace_ray(ray, propagate_distance=0.0)

        hit_x, hit_y = ray.path[1]
        self.assertAlmostEqual(hit_y, y, places=6)
        self.assertAlmostEqual(hit_x, expected, places=6)

    def test_2d_tracer_hits_a_conic_back_surface(self):
        lens = _conic_lens(
            radius_of_curvature_1=0.0,
            radius_of_curvature_2=-50.0,
            conic_constant_2=-1.0,
        )
        ray = Ray(x=-10.0, y=20.0, angle_rad=0.0)
        LensRayTracer(lens).trace_ray(ray, propagate_distance=0.0)

        # Front flat at x=0, back vertex at x=5 with a -4 mm parabolic sag.
        self.assertGreaterEqual(len(ray.path), 3)
        hit_x, hit_y = ray.path[2]
        self.assertAlmostEqual(hit_y, 20.0, places=6)
        self.assertAlmostEqual(hit_x, 5.0 - 20.0**2 / (2.0 * 50.0), places=6)

    def test_3d_tracer_hits_a_conic_back_surface(self):
        lens = _conic_lens(
            radius_of_curvature_1=0.0,
            radius_of_curvature_2=-50.0,
            conic_constant_2=-1.0,
        )
        ray = Ray3D(origin=vec3(0.0, 0.0, 20.0), direction=vec3(1.0, 0.0, 0.0))
        result = LensRayTracer3D(lens).trace_surface(ray, "back")

        self.assertTrue(result.name == "REFRACTED")
        self.assertAlmostEqual(ray.origin.x, 5.0 - 20.0**2 / (2.0 * 50.0), places=6)
        self.assertAlmostEqual(ray.origin.z, 20.0, places=6)

    def test_3d_conic_normal_refracts_at_the_analytic_angle(self):
        lens = _conic_lens(conic_constant_1=1.0)
        tracer = LensRayTracer3D(lens)
        ray = Ray3D(origin=vec3(-10.0, 0.0, 20.0), direction=vec3(1.0, 0.0, 0.0))
        tracer.trace_surface(ray, "front")

        x = lens.get_sag_1(20.0)
        normal = vec3((1.0 + 1.0) * x - 50.0, 0.0, 20.0).normalize()
        expected = OpticalIntersector.apply_snell(
            (1.0, 0.0, 0.0), (normal.x, normal.y, normal.z), 1.0, tracer.n
        )
        self.assertIsNotNone(expected)
        ex, ey, ez, is_tir = expected
        self.assertFalse(is_tir)
        self.assertAlmostEqual(ray.direction.x, ex, places=9)
        self.assertAlmostEqual(ray.direction.y, ey, places=9)
        self.assertAlmostEqual(ray.direction.z, ez, places=9)

    def test_3d_tracer_hits_the_conic_sag(self):
        lens = _conic_lens(conic_constant_1=-1.0)
        ray = Ray3D(origin=vec3(-10.0, 0.0, 20.0), direction=vec3(1.0, 0.0, 0.0))
        result = LensRayTracer3D(lens).trace_surface(ray, "front")

        self.assertTrue(result.name == "REFRACTED")
        self.assertAlmostEqual(ray.origin.x, 20.0**2 / (2.0 * 50.0), places=6)
        self.assertAlmostEqual(ray.origin.z, 20.0, places=6)


if __name__ == "__main__":
    unittest.main()
