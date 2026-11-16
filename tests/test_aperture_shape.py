"""Aperture stop shapes: clipping, pupil mask, persistence and bokeh."""

import math
import os
import sys
import tempfile
import unittest

try:
    import numpy as np

    HAS_NUMPY = True
except ImportError:
    np = None  # type: ignore[assignment]
    HAS_NUMPY = False

from openlens.aperture_shape import ApertureShape
from openlens.database import DatabaseManager
from openlens.lens import Lens
from openlens.optical_system import OpticalSystem, create_doublet
from openlens.ray import Ray, Ray3D
from openlens.ray_tracer import SystemRayTracer3D
from openlens.tracer_2d import SystemRayTracer
from openlens.vector3 import vec3


def _flat_system(shape=None, stop_diameter=10.0):
    """Two flat surfaces, so a stop hit keeps the launch height."""
    system = OpticalSystem(name="Flat")
    for index in range(2):
        system.add_lens(
            Lens(
                name=f"L{index}",
                radius_of_curvature_1=0.0,
                radius_of_curvature_2=0.0,
                thickness=1.0,
                diameter=20.0,
                material="BK7",
            ),
            air_gap_before=5.0 if index else 0.0,
        )
    system.set_aperture_stop(0, stop_diameter, shape=shape)
    return system


def _make_db():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    return DatabaseManager(tmp.name), tmp.name


class TestApertureShapeGeometry(unittest.TestCase):
    def test_default_shape_is_circular(self):
        self.assertTrue(ApertureShape().is_circular)
        self.assertTrue(ApertureShape(rotation_deg=30.0).is_circular)

    def test_invalid_shapes_are_rejected(self):
        for kwargs in (
            {"blades": 1},
            {"blades": 2},
            {"blades": -1},
            {"obscuration_ratio": 1.0},
            {"obscuration_ratio": -0.1},
            {"spider_vanes": -1},
            {"spider_width_mm": -0.1},
            {"rotation_deg": float("nan")},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                ApertureShape(**kwargs)

    def test_six_blade_polygon_keeps_the_inscribed_circle(self):
        shape = ApertureShape(blades=6)
        radius = 5.0
        inscribed = radius * math.cos(math.pi / 6)
        self.assertTrue(shape.contains(0.0, inscribed - 0.01, radius))
        self.assertFalse(shape.contains(0.0, inscribed + 0.2, radius))
        # A vertex lies on the circumscribed circle the diameter names.
        self.assertTrue(shape.contains(radius - 0.01, 0.0, radius))

    def test_rotation_moves_the_flats(self):
        radius = 5.0
        self.assertTrue(ApertureShape(blades=6).contains(4.5, 0.0, radius))
        self.assertFalse(ApertureShape(blades=6, rotation_deg=30.0).contains(4.5, 0.0, radius))

    def test_annular_stop_removes_the_centre(self):
        shape = ApertureShape(obscuration_ratio=0.5)
        self.assertFalse(shape.contains(0.0, 0.0, 5.0))
        self.assertTrue(shape.contains(0.0, 4.0, 5.0))
        self.assertFalse(shape.contains(0.0, 5.5, 5.0))

    def test_spider_vanes_cut_narrow_strips(self):
        shape = ApertureShape(spider_vanes=2, spider_width_mm=1.0)
        self.assertFalse(shape.contains(0.0, 3.0, 5.0))
        self.assertTrue(shape.contains(2.0, 2.0, 5.0))
        self.assertTrue(shape.contains(0.0, 3.0, 5.0, include_spiders=False))

    def test_pupil_mask_matches_contains(self):
        shape = ApertureShape(obscuration_ratio=0.5)
        mask = shape.pupil_mask([[0.0, 0.0, 0.0]], [[-4.0, 0.0, 4.0]], 5.0)
        self.assertEqual(len(mask), 1)
        self.assertEqual(len(mask[0]), 3)
        self.assertEqual(mask[0], [True, False, True])

    def test_outline_has_one_point_per_blade(self):
        self.assertEqual(len(ApertureShape(blades=6).outline(5.0)), 6)
        self.assertEqual(len(ApertureShape().outline(5.0, points=16)), 16)


class TestStopShapeModel(unittest.TestCase):
    def test_set_and_get_carry_the_shape(self):
        shape = ApertureShape(blades=6, rotation_deg=15.0, obscuration_ratio=0.3)
        system = _flat_system(shape)
        self.assertEqual(system.get_aperture_stop()["shape"], shape)

    def test_shape_can_be_given_as_a_dict(self):
        system = _flat_system()
        system.set_aperture_stop(0, 10.0, shape={"blades": 8})
        self.assertEqual(system.get_aperture_stop()["shape"].blades, 8)

    def test_dict_round_trip_preserves_the_shape(self):
        shape = ApertureShape(
            blades=9,
            rotation_deg=12.5,
            obscuration_ratio=0.25,
            spider_vanes=3,
            spider_width_mm=0.8,
        )
        system = _flat_system(shape)
        clone = OpticalSystem.from_dict(system.to_dict())
        self.assertEqual(clone.get_aperture_stop()["shape"], shape)

    def test_an_invalid_serialized_shape_falls_back_to_circular(self):
        data = _flat_system().to_dict()
        data["aperture_stop_shape"] = {"blades": 2}
        clone = OpticalSystem.from_dict(data)
        self.assertTrue(clone.get_aperture_stop()["shape"].is_circular)

    def test_a_non_mapping_shape_falls_back_to_circular(self):
        data = _flat_system().to_dict()
        data["aperture_stop_shape"] = "hexagon"
        clone = OpticalSystem.from_dict(data)
        self.assertTrue(clone.get_aperture_stop()["shape"].is_circular)

    def test_clear_resets_the_shape(self):
        system = _flat_system(ApertureShape(blades=6))
        system.clear_aperture_stop()
        self.assertTrue(system.aperture_stop_shape.is_circular)

    def test_sqlite_round_trip_preserves_the_shape(self):
        shape = ApertureShape(blades=6, obscuration_ratio=0.4)
        system = _flat_system(shape)
        db, path = _make_db()
        try:
            db.save_assembly(system.to_dict())
            rows = [r for r in db.load_all() if r.get("row_type") == "OpticalSystem"]
            self.assertEqual(len(rows), 1)
            rebuilt = OpticalSystem.from_dict(rows[0])
            self.assertEqual(rebuilt.get_aperture_stop()["shape"], shape)
        finally:
            os.unlink(path)


class TestStopShapeClipping(unittest.TestCase):
    def test_3d_polygon_clips_outside_the_inscribed_circle(self):
        system = _flat_system(ApertureShape(blades=6))
        tracer = SystemRayTracer3D(system)
        for y, z, blocked in ((0.0, 4.0, False), (0.0, 4.5, True), (4.9, 0.0, False)):
            with self.subTest(y=y, z=z):
                ray = tracer.trace_ray(Ray3D(vec3(-10.0, y, z), vec3(1.0, 0.0, 0.0)))
                self.assertEqual(ray.terminated, blocked)

    def test_2d_polygon_honours_rotation(self):
        radius = 4.5
        centred = SystemRayTracer(_flat_system(ApertureShape(blades=6)))
        rotated = SystemRayTracer(_flat_system(ApertureShape(blades=6, rotation_deg=30.0)))
        self.assertFalse(centred.trace_ray(Ray(-10.0, radius, 0.0)).terminated)
        self.assertTrue(rotated.trace_ray(Ray(-10.0, radius, 0.0)).terminated)

    def test_annular_stop_blocks_the_axis_and_passes_the_ring(self):
        system = _flat_system(ApertureShape(obscuration_ratio=0.5))
        tracer_3d = SystemRayTracer3D(system)
        tracer_2d = SystemRayTracer(system)
        self.assertTrue(tracer_3d.trace_ray(Ray3D(vec3(-10.0, 0.0, 0.0), vec3(1, 0, 0))).terminated)
        self.assertTrue(tracer_2d.trace_ray(Ray(-10.0, 0.0, 0.0)).terminated)
        self.assertFalse(
            tracer_3d.trace_ray(Ray3D(vec3(-10.0, 0.0, 4.0), vec3(1, 0, 0))).terminated
        )
        self.assertFalse(tracer_2d.trace_ray(Ray(-10.0, 4.0, 0.0)).terminated)

    def test_spider_vanes_clip_in_3d_only(self):
        system = _flat_system(ApertureShape(spider_vanes=2, spider_width_mm=1.0))
        ray_3d = SystemRayTracer3D(system).trace_ray(Ray3D(vec3(-10.0, 3.0, 0.0), vec3(1, 0, 0)))
        ray_2d = SystemRayTracer(system).trace_ray(Ray(-10.0, 3.0, 0.0))
        self.assertTrue(ray_3d.terminated)
        self.assertFalse(ray_2d.terminated)

    def test_a_default_circular_stop_keeps_the_old_clipping(self):
        system = _flat_system()
        tracer = SystemRayTracer3D(system)
        for height, blocked in ((0.0, False), (4.9, False), (5.1, True), (8.0, True)):
            with self.subTest(height=height):
                ray = tracer.trace_ray(Ray3D(vec3(-10.0, 0.0, height), vec3(1, 0, 0)))
                self.assertEqual(ray.terminated, blocked)

    def test_an_explicit_circle_traces_like_an_omitted_shape(self):
        implicit = SystemRayTracer3D(_flat_system())
        explicit = SystemRayTracer3D(_flat_system(ApertureShape()))
        for height in (-8.0, -5.0, 0.0, 4.9, 5.0, 8.0):
            with self.subTest(height=height):
                first = implicit.trace_ray(Ray3D(vec3(-10.0, 0.0, height), vec3(1, 0, 0)))
                second = explicit.trace_ray(Ray3D(vec3(-10.0, 0.0, height), vec3(1, 0, 0)))
                self.assertEqual(first.terminated, second.terminated)
                self.assertEqual(
                    [(p.x, p.y, p.z) for p in first.path],
                    [(p.x, p.y, p.z) for p in second.path],
                )
                self.assertEqual(first.optical_path_length, second.optical_path_length)

    def test_zemax_export_keeps_a_shaped_stops_diameter(self):
        from openlens.export_formats import ZemaxSystemExporter, ZemaxSystemImporter

        system = _flat_system(ApertureShape(blades=6, obscuration_ratio=0.3))
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "shaped.zmx")
            ZemaxSystemExporter.export_system(system, path)
            imported = ZemaxSystemImporter.import_system(path)
        self.assertEqual(imported.get_aperture_stop()["diameter"], 10.0)
        self.assertEqual(imported.get_aperture_stop()["gap_index"], 0)


@unittest.skipUnless(HAS_NUMPY, "numpy not available")
class TestShapedPupilAndBokeh(unittest.TestCase):
    def test_annular_stop_leaves_a_hole_in_the_pupil(self):
        from openlens.analysis.diffraction_psf import WavefrontSensor

        system = create_doublet()
        system.set_aperture_stop(0, 10.0, shape=ApertureShape(obscuration_ratio=0.5))
        wavefront = WavefrontSensor(system).get_pupil_wavefront(grid_size=24)
        centre = wavefront.W.shape[0] // 2
        self.assertTrue(np.isnan(wavefront.W[centre, centre]))
        self.assertGreater(int(np.count_nonzero(~np.isnan(wavefront.W))), 0)

    def test_circular_stop_keeps_the_pupil_centre(self):
        from openlens.analysis.diffraction_psf import WavefrontSensor

        system = create_doublet()
        system.set_aperture_stop(0, 10.0)
        wavefront = WavefrontSensor(system).get_pupil_wavefront(grid_size=24)
        centre = wavefront.W.shape[0] // 2
        self.assertFalse(np.isnan(wavefront.W[centre, centre]))

    def test_annular_bokeh_is_a_ring(self):
        from openlens.analysis.bokeh import BokehRenderer

        system = create_doublet()
        system.set_aperture_stop(0, 10.0, shape=ApertureShape(obscuration_ratio=0.5))
        result = BokehRenderer(system).render(defocus_mm=1.0, pixels=65, rays=2000)
        image = result["image"]
        centre = image.shape[0] // 2
        self.assertLess(image[centre, centre], 0.05 * image.max())
        # The ring sits at roughly half the blur radius outwards.
        radius = result["blur_diameter_mm"] / 2.0
        pixel = (result["z_axis"][-1] - result["z_axis"][0]) / (image.shape[1] - 1)
        ring = centre + int(round(0.75 * radius / pixel))
        self.assertGreater(image[centre, ring], 0.4 * image.max())

    def test_circular_bokeh_is_a_disc(self):
        from openlens.analysis.bokeh import BokehRenderer

        system = create_doublet()
        system.set_aperture_stop(0, 10.0)
        result = BokehRenderer(system).render(defocus_mm=1.0, pixels=65, rays=2000)
        image = result["image"]
        centre = image.shape[0] // 2
        self.assertGreater(image[centre, centre], 0.2 * image.max())


try:
    from PySide6.QtCore import QRect
    from PySide6.QtGui import QPaintEvent
    from PySide6.QtWidgets import QApplication

    PYSIDE_AVAILABLE = True
except ImportError:
    PYSIDE_AVAILABLE = False


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 not available")
class TestShapedStopIsDrawn(unittest.TestCase):
    def test_the_assembly_view_paints_a_shaped_stop(self):
        if os.environ.get("DISPLAY", "") == "" and sys.platform.startswith("linux"):
            os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from openlens.gui.widgets.assembly_viz import AssemblyVisualizationWidget

        app = QApplication.instance() or QApplication(sys.argv)
        self.assertIsNotNone(app)
        system = _flat_system(
            ApertureShape(blades=6, obscuration_ratio=0.3, spider_vanes=3, spider_width_mm=0.5)
        )
        widget = AssemblyVisualizationWidget()
        widget.update_system(system)
        widget.resize(500, 400)
        try:
            widget.paintEvent(QPaintEvent(QRect(0, 0, 500, 400)))
        finally:
            widget.close()
            widget.deleteLater()


if __name__ == "__main__":
    unittest.main()
