"""Tests for the optional MCP server and its database-backed tools."""

import os
import tempfile
import unittest
from unittest import mock

from openlens.database import DatabaseManager
from openlens.lens import Lens
from openlens.mcp_server import MCP_AVAILABLE, OpenLensTools, create_server
from openlens.validation import ValidationError


class TestOpenLensTools(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        database = DatabaseManager(os.path.join(self.tempdir.name, "lenses.db"))
        self.tools = OpenLensTools(database)

    def _create_singlet(self, **overrides):
        arguments = {
            "name": "MCP singlet",
            "radius_of_curvature_1": 50.0,
            "radius_of_curvature_2": -50.0,
            "thickness": 5.0,
            "diameter": 25.0,
        }
        arguments.update(overrides)
        return self.tools.create_lens(**arguments)

    def test_create_list_get_and_delete_a_lens(self):
        created = self._create_singlet()

        self.assertEqual(created["name"], "MCP singlet")
        self.assertTrue(created["id"])
        self.assertEqual([row["id"] for row in self.tools.list_lenses()], [created["id"]])
        self.assertEqual(self.tools.get_lens(created["id"])["name"], "MCP singlet")

        self.assertTrue(self.tools.delete_lens(created["id"]))
        self.assertIsNone(self.tools.get_lens(created["id"]))
        self.assertFalse(self.tools.delete_lens(created["id"]))

    def test_calculate_metrics_returns_real_values(self):
        created = self._create_singlet()

        metrics = self.tools.calculate_metrics(created["id"])

        self.assertIsNotNone(metrics)
        self.assertIn("effective_focal_length", metrics)
        self.assertGreater(metrics["effective_focal_length"], 0.0)
        self.assertIn("f_number", metrics)
        self.assertIn("airy_disk_radius_mm", metrics)

    def test_calculate_metrics_for_a_missing_lens_returns_none(self):
        self.assertIsNone(self.tools.calculate_metrics("does-not-exist"))

    def test_invalid_parameters_are_rejected_before_saving(self):
        with self.assertRaises(ValidationError):
            self._create_singlet(diameter=0.0)
        self.assertEqual(self.tools.list_lenses(), [])

    def test_a_flat_radius_is_json_safe_and_still_measurable(self):
        created = self._create_singlet(radius_of_curvature_1=float("inf"))

        self.assertIsNone(created["radius_of_curvature_1"])
        self.assertIsNone(self.tools.get_lens(created["id"])["radius_of_curvature_1"])
        self.assertIsNotNone(self.tools.calculate_metrics(created["id"]))

    def test_create_lens_resolves_the_material_index(self):
        created = self._create_singlet(material="SF11")

        self.assertEqual(created["material"], "SF11")
        self.assertAlmostEqual(
            created["refractive_index"], Lens.for_material("SF11").refractive_index
        )

    def test_create_lens_keeps_an_explicit_index(self):
        created = self._create_singlet(material="SF11", refractive_index=1.6)

        self.assertAlmostEqual(created["refractive_index"], 1.6)

    def test_list_and_load_presets(self):
        presets = self.tools.list_presets()

        self.assertTrue(presets)
        self.assertTrue(all("name" in preset for preset in presets))
        name = presets[0]["name"]
        lens = self.tools.load_preset(name)
        self.assertIsNotNone(lens)
        self.assertEqual(lens["name"], name)

    def test_a_preset_can_be_saved_as_a_library_lens(self):
        name = self.tools.list_presets()[0]["name"]

        saved = self.tools.load_preset(name, save=True)

        self.assertIsNotNone(saved)
        self.assertIn(saved["id"], [row["id"] for row in self.tools.list_lenses()])

    def test_an_unknown_preset_returns_none(self):
        self.assertIsNone(self.tools.load_preset("not a real preset"))


class TestServerGuard(unittest.TestCase):
    def test_create_server_names_the_optional_extra(self):
        with mock.patch("openlens.mcp_server.MCP_AVAILABLE", False):
            with self.assertRaisesRegex(ImportError, "openlens\\[mcp\\]"):
                create_server()

    def test_main_reports_a_missing_dependency(self):
        import openlens.mcp_server as server

        with mock.patch.object(server, "MCP_AVAILABLE", False):
            with self.assertLogs("openlens.mcp_server", level="ERROR") as logs:
                self.assertEqual(server.main(), 1)

        self.assertIn("openlens[mcp]", "\n".join(logs.output))

    @unittest.skipUnless(MCP_AVAILABLE, "mcp package not installed")
    def test_create_server_returns_a_server(self):
        with tempfile.TemporaryDirectory() as tmp:
            tools = OpenLensTools(DatabaseManager(os.path.join(tmp, "test.db")))
            self.assertIsNotNone(create_server(tools))


class TestCliDispatch(unittest.TestCase):
    def test_the_cli_runs_the_mcp_server_for_the_mcp_argument(self):
        import openlens.lens_editor as cli

        with mock.patch.object(cli.sys, "argv", ["openlens-cli", "mcp"]):
            with mock.patch("openlens.mcp_server.main", return_value=0) as dispatch:
                with self.assertRaises(SystemExit) as caught:
                    cli.main()

        self.assertEqual(caught.exception.code, 0)
        dispatch.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
