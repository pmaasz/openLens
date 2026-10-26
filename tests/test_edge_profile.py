#!/usr/bin/env python3
"""Custom meridional edge profiles (#45)."""

import math
import os
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from openlens.database import DatabaseManager
from openlens.geometry import LensGeometry
from openlens.lens import Lens
from openlens.stl_export import STLExporter, export_lens_stl
from openlens.validation import ValidationError


def _lens() -> Lens:
    return Lens(
        name="Edge",
        radius_of_curvature_1=100.0,
        radius_of_curvature_2=-100.0,
        thickness=10.0,
        diameter=50.0,
    )


def _flanged(lens: Lens, flange: float = 5.0):
    front, back = LensGeometry.rim_points(lens)
    return [
        front,
        ((front[0] + back[0]) / 2.0, front[1] + flange),
        back,
    ]


class TestEdgeProfileModel(unittest.TestCase):
    def test_default_edge_is_the_straight_rim(self):
        lens = _lens()
        front, back = LensGeometry.rim_points(lens)

        self.assertEqual(LensGeometry.edge_profile_points(lens), [front, back])
        self.assertEqual(
            LensGeometry.get_lens_polyline(lens),
            LensGeometry.lens_outline(lens)["front"] + LensGeometry.lens_outline(lens)["back"],
        )

    def test_profile_round_trips_through_dict(self):
        lens = _lens()
        lens.set_edge_profile(_flanged(lens))

        restored = Lens.from_dict(lens.to_dict())

        self.assertEqual(restored.edge_profile, lens.edge_profile)
        self.assertEqual(
            LensGeometry.edge_profile_points(restored),
            LensGeometry.edge_profile_points(lens),
        )

    def test_profile_round_trips_through_sqlite(self):
        lens = _lens()
        lens.set_edge_profile(_flanged(lens))
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            path = tmp.name
        try:
            db = DatabaseManager(path)
            db.save_lens(lens.to_dict())
            rows = [row for row in db.load_all() if row.get("row_type") == "Lens"]
            restored = Lens.from_dict(rows[0])
            self.assertEqual(restored.edge_profile, lens.edge_profile)
        finally:
            os.remove(path)

    def test_polyline_contains_the_profile_flange(self):
        lens = _lens()
        lens.set_edge_profile(_flanged(lens))

        outline = LensGeometry.lens_outline(lens)
        polyline = LensGeometry.get_lens_polyline(lens)

        self.assertEqual(len(outline["edge"]), 3)
        self.assertIn((outline["edge"][1][0], outline["edge"][1][1]), polyline)
        self.assertIn((outline["edge"][1][0], -outline["edge"][1][1]), polyline)

    def test_sync_moves_endpoints_with_the_optical_rims(self):
        lens = _lens()
        lens.set_edge_profile(_flanged(lens))
        lobe = lens.edge_profile[1]

        lens.radius_of_curvature_1 = 60.0
        lens.sync_edge_profile()

        front, _back = LensGeometry.rim_points(lens)
        self.assertEqual(lens.edge_profile[0], front)
        self.assertEqual(lens.edge_profile[1], lobe)


class TestEdgeProfileValidation(unittest.TestCase):
    def setUp(self):
        self.lens = _lens()
        self.front, self.back = LensGeometry.rim_points(self.lens)

    def _profile(self, middle):
        return [self.front, middle, self.back]

    def test_too_few_points_are_rejected(self):
        with self.assertRaises(ValidationError):
            self.lens.set_edge_profile([self.front, self.back])

    def test_non_finite_coordinate_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.lens.set_edge_profile(
                self._profile(((self.front[0] + self.back[0]) / 2.0, math.inf))
            )

    def test_negative_radius_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.lens.set_edge_profile(self._profile(((self.front[0] + self.back[0]) / 2.0, -30.0)))

    def test_duplicate_consecutive_point_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.lens.set_edge_profile(
                [self.front, self.front, ((self.front[0] + self.back[0]) / 2.0, 30.0), self.back]
            )

    def test_clear_aperture_intrusion_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.lens.set_edge_profile(self._profile(((self.front[0] + self.back[0]) / 2.0, 20.0)))

    def test_wrong_start_end_are_rejected(self):
        with self.assertRaises(ValidationError):
            self.lens.set_edge_profile([(0.0, 30.0), ((0.0 + 1.0), 31.0), self.back])

    def test_self_intersection_is_rejected(self):
        middle_x = (self.front[0] + self.back[0]) / 2.0
        points = [
            self.front,
            (middle_x + 2.0, 30.0),
            (middle_x - 2.0, 27.0),
            (middle_x + 2.0, 30.0),
            self.back,
        ]
        with self.assertRaises(ValidationError):
            self.lens.set_edge_profile(points)

    def test_invalid_edit_keeps_the_last_valid_profile(self):
        valid = _flanged(self.lens)
        self.lens.set_edge_profile(valid)
        with self.assertRaises(ValidationError):
            self.lens.set_edge_profile(self._profile(((self.front[0] + self.back[0]) / 2.0, 1.0)))
        self.assertEqual(list(self.lens.edge_profile), valid)

    def test_clear_removes_the_profile(self):
        lens = _lens()
        lens.set_edge_profile(_flanged(lens))
        lens.clear_edge_profile()
        self.assertIsNone(lens.edge_profile)


class TestEdgeProfileExport(unittest.TestCase):
    def test_stl_default_edge_stays_within_the_diameter(self):
        lens = _lens()
        exporter = STLExporter()
        with tempfile.NamedTemporaryFile(suffix=".stl", delete=False) as tmp:
            path = tmp.name
        try:
            exporter.export_lens_to_stl(100.0, -100.0, 10.0, 50.0, path, lens=lens)
        finally:
            os.remove(path)
        radii = [
            math.hypot(point[0], point[1]) for triangle in exporter.triangles for point in triangle
        ]
        self.assertAlmostEqual(max(radii), 25.0, places=6)

    def test_stl_follows_the_custom_flange(self):
        lens = _lens()
        lens.set_edge_profile(_flanged(lens))
        exporter = STLExporter()
        with tempfile.NamedTemporaryFile(suffix=".stl", delete=False) as tmp:
            path = tmp.name
        try:
            exporter.export_lens_to_stl(100.0, -100.0, 10.0, 50.0, path, lens=lens)
        finally:
            os.remove(path)
        radii = [
            math.hypot(point[0], point[1]) for triangle in exporter.triangles for point in triangle
        ]
        self.assertAlmostEqual(max(radii), 30.0, places=6)

    def test_assembly_stl_uses_the_custom_edge(self):
        from openlens.optical_system import OpticalSystem

        counts = []
        for custom in (False, True):
            lens = _lens()
            if custom:
                lens.set_edge_profile(_flanged(lens))
            system = OpticalSystem(name="Assembly")
            system.add_lens(lens)
            with tempfile.NamedTemporaryFile(suffix=".stl", delete=False) as tmp:
                path = tmp.name
            try:
                counts.append(export_lens_stl(system, path, resolution=12))
            finally:
                os.remove(path)
        self.assertGreater(counts[1], counts[0])

    def test_step_writes_the_profile_as_a_revolved_polyline(self):
        from openlens.io.step_export import StepExporter

        lens = _lens()
        lens.set_edge_profile(_flanged(lens))
        with tempfile.NamedTemporaryFile(suffix=".step", delete=False) as tmp:
            path = tmp.name
        try:
            StepExporter(lens).export(path)
            with open(path, "r", encoding="utf-8") as handle:
                content = handle.read()
        finally:
            os.remove(path)

        self.assertIn("SURFACE_OF_REVOLUTION", content)
        self.assertIn("POLYLINE", content)
        self.assertIn("30.000000", content)

    def test_step_default_edge_is_still_a_cylinder(self):
        from openlens.io.step_export import StepExporter

        lens = _lens()
        with tempfile.NamedTemporaryFile(suffix=".step", delete=False) as tmp:
            path = tmp.name
        try:
            StepExporter(lens).export(path)
            with open(path, "r", encoding="utf-8") as handle:
                content = handle.read()
        finally:
            os.remove(path)

        self.assertIn("CYLINDRICAL_SURFACE", content)
        self.assertNotIn("SURFACE_OF_REVOLUTION", content)


try:
    from PySide6.QtCore import QPoint
    from PySide6.QtWidgets import QApplication

    from openlens.gui.widgets.lens_editor import LensEditorWidget
    from openlens.gui.widgets.lens_viz_2d import LensViz2DWidget

    HAS_PYSIDE = True
except ImportError:  # pragma: no cover - depends on install
    HAS_PYSIDE = False


@unittest.skipUnless(HAS_PYSIDE, "PySide6 is not installed")
class TestEdgeProfileEditor(unittest.TestCase):
    def setUp(self):
        from tests import ensure_qapp

        ensure_qapp()
        self.editor = LensEditorWidget()
        self.lens = _lens()
        self.editor.load_lens(self.lens)

    def tearDown(self):
        self.editor.close()
        self.editor.deleteLater()
        QApplication.processEvents()

    def test_toggle_creates_a_profile_and_off_clears_it(self):
        self.editor._edge_check.setChecked(True)
        self.assertTrue(self.lens.edge_profile)
        self.assertTrue(self.editor._viz_widget._2d_widget._edge_editing)

        self.editor._edge_check.setChecked(False)
        self.assertIsNone(self.lens.edge_profile)

    def test_numeric_entry_sets_the_profile(self):
        self.editor._edge_check.setChecked(True)
        points = _flanged(self.lens)
        self.editor._edge_points_input.setText("; ".join(f"{x}, {radius}" for x, radius in points))
        self.editor._on_edge_points_entered()

        self.assertEqual(list(self.lens.edge_profile), points)

    def test_invalid_numeric_entry_keeps_the_previous_profile(self):
        self.editor._edge_check.setChecked(True)
        previous = list(self.lens.edge_profile)
        self.editor._edge_points_input.setText("0, 1; 2, 2")
        self.editor._on_edge_points_entered()

        self.assertEqual(list(self.lens.edge_profile), previous)

    def test_viz_adds_a_vertex_on_click(self):
        widget = LensViz2DWidget()
        widget.update_lens(self.lens)
        widget._scale = 1.0
        widget._cx = 0.0
        widget._cy = 0.0
        received = []
        widget.edge_profile_changed.connect(received.append)

        widget._add_edge_point(QPoint(5, 30))

        self.assertEqual(len(received), 1)
        self.assertEqual(len(received[0]), 3)
        widget.deleteLater()
        QApplication.processEvents()
