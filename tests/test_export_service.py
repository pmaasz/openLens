#!/usr/bin/env python3
"""Headless tests for the Qt-free export orchestration (#582).

The window keeps the file dialogs, status messages and error boxes; the
service only wraps models, calls the exporters, writes the files and reports
success or failure. These tests therefore need no QApplication.
"""

import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from openlens.gui.services.export_service import ExportResult, ExportService
from openlens.lens import Lens
from openlens.optical_system import create_doublet

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestExportService(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.lens = Lens(
            name="Report Lens",
            radius_of_curvature_1=100.0,
            radius_of_curvature_2=-100.0,
            thickness=5.0,
            diameter=50.0,
            material="BK7",
        )

    def test_save_lens_json_writes_the_lens_dict(self):
        path = self.tmp / "lens.json"

        result = ExportService().save_lens_json(self.lens, str(path))

        self.assertIsInstance(result, ExportResult)
        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.kind, "json")
        self.assertEqual(result.path, str(path))
        self.assertGreater(result.bytes_written, 0)
        self.assertIsNone(result.error)
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(data["name"], "Report Lens")
        self.assertEqual(data["radius_of_curvature_1"], 100.0)

    def test_save_lens_json_writes_a_flat_surface_as_null(self):
        """A flat surface is null in the exported JSON, not a bare Infinity"""
        path = self.tmp / "plano.json"
        plano = Lens(
            name="Plano Lens",
            radius_of_curvature_1=float("inf"),
            radius_of_curvature_2=-100.0,
            thickness=5.0,
            diameter=50.0,
            material="BK7",
        )

        result = ExportService().save_lens_json(plano, str(path))

        self.assertTrue(result.ok, result.error)
        text = path.read_text(encoding="utf-8")
        self.assertNotIn("Infinity", text)
        data = json.loads(text)
        self.assertIsNone(data["radius_of_curvature_1"])
        self.assertEqual(data["radius_of_curvature_2"], -100.0)

    def test_export_stl_writes_a_non_empty_file(self):
        path = self.tmp / "lens.stl"

        result = ExportService().export_stl(self.lens, str(path))

        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.kind, "stl")
        self.assertGreater(path.stat().st_size, 0)
        self.assertGreater(result.details["triangles"], 0)

    def test_export_step_writes_a_file_and_returns_the_summary(self):
        path = self.tmp / "lens.step"

        result = ExportService().export_step(self.lens, str(path))

        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.kind, "step")
        self.assertGreater(path.stat().st_size, 0)
        self.assertGreaterEqual(result.details["shapes"], 1)
        self.assertIn("skipped", result.details)

    def test_export_step_import_error_is_reported_as_missing_dependency(self):
        path = self.tmp / "lens.step"

        def missing_occ(system):
            raise ImportError("pythonocc-core is not installed")

        result = ExportService(housing_factory=missing_occ).export_step(self.lens, str(path))

        self.assertFalse(result.ok)
        self.assertTrue(result.dependency_missing)
        self.assertIn("pythonocc-core", result.error)
        self.assertFalse(path.exists())

    def test_export_iso10110_writes_svg(self):
        system = create_doublet(focal_length=100.0, diameter=40.0)
        path = self.tmp / "drawing.svg"

        result = ExportService().export_iso10110(system, str(path))

        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.kind, "iso10110")
        svg = path.read_text(encoding="utf-8")
        self.assertIn("<svg", svg)
        self.assertGreater(result.bytes_written, 0)

    def test_export_report_for_a_lens_keeps_the_existing_format(self):
        clock = lambda: datetime(2026, 10, 20, 12, 34, 56)  # noqa: E731
        path = self.tmp / "lens.txt"

        result = ExportService(clock=clock).export_report(self.lens, str(path))

        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.kind, "report")
        text = path.read_text(encoding="utf-8")
        self.assertIn("OpenLens Design Report", text)
        self.assertIn("Name: Report Lens", text)
        self.assertIn("Date: 2026-10-20 12:34:56", text)
        self.assertIn("Type: Single Lens Element", text)
        self.assertIn("Radius 1: 100.0 mm", text)
        self.assertIn("Material: BK7", text)

    def test_export_report_for_an_assembly_lists_every_element(self):
        system = create_doublet(focal_length=100.0, diameter=40.0)
        path = self.tmp / "assembly.txt"

        result = ExportService().export_report(system, str(path))

        self.assertTrue(result.ok, result.error)
        text = path.read_text(encoding="utf-8")
        self.assertIn("Type: Optical Assembly (2 elements)", text)
        self.assertIn("Element 1:", text)
        self.assertIn("Element 2:", text)
        self.assertIn("Position:", text)

    def test_failures_return_a_result_instead_of_raising(self):
        missing = self.tmp / "missing" / "lens.json"

        result = ExportService().save_lens_json(self.lens, str(missing))

        self.assertFalse(result.ok)
        self.assertFalse(result.dependency_missing)
        self.assertIsNotNone(result.error)
        self.assertEqual(result.bytes_written, 0)

    def test_report_to_a_directory_returns_a_failure(self):
        result = ExportService().export_report(self.lens, str(self.tmp))

        self.assertFalse(result.ok)
        self.assertTrue(result.error)

    def test_the_service_runs_without_pyside6(self):
        # Import and use the service with PySide6 blocked. The GUI package
        # catches the ImportError for its widgets, and the service itself must
        # not need Qt at all.
        code = """
import json
import sys
import tempfile
from pathlib import Path


class _BlockPySide6:
    def find_spec(self, name, path=None, target=None):
        if name == "PySide6" or name.startswith("PySide6."):
            raise ImportError("PySide6 blocked for the headless service test")
        return None


sys.meta_path.insert(0, _BlockPySide6())

from openlens.gui.services.export_service import ExportService
from openlens.lens import Lens

with tempfile.TemporaryDirectory() as tmp:
    path = Path(tmp) / "lens.json"
    result = ExportService().save_lens_json(Lens(name="Headless"), str(path))
    assert result.ok, result.error
    assert json.loads(path.read_text())["name"] == "Headless"

assert "PySide6" not in sys.modules, sorted(
    name for name in sys.modules if name.startswith("PySide6")
)
"""
        completed = subprocess.run(
            [sys.executable, "-c", code],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)


if __name__ == "__main__":
    unittest.main()
