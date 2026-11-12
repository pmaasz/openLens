#!/usr/bin/env python3
"""Tests for standard and user-defined lens mounts (#1).

The working flange distance is the distance from the rear lens vertex to the
sensor/film plane: the lens back focal length plus the camera mount's flange
distance. Standard mounts are fixed data; user mounts live in a JSON file under
the per-user data directory.
"""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from openlens import paths
from openlens.database import DatabaseManager
from openlens.lens import Lens
from openlens.mechanical_designer import LensMount, MechanicalDesigner
from openlens.mounts import MountCatalog
from openlens.performance_metrics import PerformanceMetrics


class TestStandardMountCatalog(unittest.TestCase):
    """The documented mirrorless and DSLR mounts are available."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.catalog = MountCatalog(Path(self.tmp.name) / "mounts.json")

    def test_new_standard_mounts_have_their_flange_distances(self):
        expected = {
            "X-mount": 17.7,
            "M-mount": 27.8,
            "EF-mount": 44.0,
            "F-mount": 46.5,
        }
        available = self.catalog.get_available_mounts()

        for name, flange in expected.items():
            with self.subTest(mount=name):
                self.assertIn(name, available)
                self.assertAlmostEqual(available[name]["flange_distance"], flange)

    def test_existing_standard_mounts_are_preserved(self):
        available = self.catalog.get_available_mounts()

        for name in ("C-mount", "CS-mount", "M42", "M39", "T-mount"):
            with self.subTest(mount=name):
                self.assertIn(name, available)

    def test_bayonet_mounts_may_have_no_thread(self):
        available = self.catalog.get_available_mounts()

        for name in ("X-mount", "M-mount", "EF-mount", "F-mount"):
            with self.subTest(mount=name):
                self.assertEqual(available[name]["thread_diameter"], 0.0)
                self.assertEqual(available[name]["thread_pitch"], 0.0)

    def test_design_mount_accepts_a_bayonet(self):
        designer = MechanicalDesigner(
            None, mount_catalog=MountCatalog(Path(self.tmp.name) / "mounts.json")
        )

        mount = designer.design_mount("X-mount")

        self.assertIsInstance(mount, LensMount)
        self.assertEqual(mount.mount_type, "X-mount")
        self.assertAlmostEqual(mount.flange_distance, 17.7)

    def test_unknown_mount_is_none(self):
        self.assertIsNone(self.catalog.get_mount("No-such-mount"))


class TestCustomMounts(unittest.TestCase):
    """Custom mounts can be added, removed and persisted."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "mounts.json"
        self.catalog = MountCatalog(self.path)

    def test_add_custom_mount_makes_it_available(self):
        self.catalog.add_custom_mount("Lab mount", 31.5)

        spec = self.catalog.get_mount("Lab mount")

        self.assertAlmostEqual(spec["flange_distance"], 31.5)
        self.assertTrue(spec["custom"])
        self.assertIn("Lab mount", self.catalog.get_available_mounts())

    def test_custom_mount_can_carry_thread_dimensions(self):
        self.catalog.add_custom_mount(
            "Threaded lab mount",
            flange_distance=31.5,
            thread_diameter=30.0,
            thread_pitch=0.75,
        )

        spec = self.catalog.get_mount("Threaded lab mount")

        self.assertAlmostEqual(spec["thread_diameter"], 30.0)
        self.assertAlmostEqual(spec["thread_pitch"], 0.75)

    def test_custom_mount_cannot_shadow_a_standard_mount(self):
        with self.assertRaises(ValueError):
            self.catalog.add_custom_mount("C-mount", 17.526)

    def test_custom_mount_rejects_non_positive_flange_distance(self):
        for value in (0.0, -1.0, float("nan"), float("inf")):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    self.catalog.add_custom_mount("Bad mount", value)

    def test_custom_mount_rejects_blank_name(self):
        with self.assertRaises(ValueError):
            self.catalog.add_custom_mount("   ", 20.0)

    def test_remove_custom_mount(self):
        self.catalog.add_custom_mount("Lab mount", 31.5)

        self.assertTrue(self.catalog.remove_custom_mount("Lab mount"))
        self.assertFalse(self.catalog.remove_custom_mount("Lab mount"))
        self.assertIsNone(self.catalog.get_mount("Lab mount"))

    def test_standard_mount_cannot_be_removed(self):
        self.assertFalse(self.catalog.remove_custom_mount("C-mount"))
        self.assertIsNotNone(self.catalog.get_mount("C-mount"))

    def test_custom_mounts_survive_save_and_reload(self):
        self.catalog.add_custom_mount("Lab mount", 31.5)
        self.catalog.save_custom_mounts()

        reloaded = MountCatalog(self.path)

        self.assertAlmostEqual(reloaded.get_mount("Lab mount")["flange_distance"], 31.5)

    def test_removed_custom_mount_stays_removed_after_reload(self):
        self.catalog.add_custom_mount("Lab mount", 31.5)
        self.catalog.save_custom_mounts()
        self.catalog.remove_custom_mount("Lab mount")
        self.catalog.save_custom_mounts()

        reloaded = MountCatalog(self.path)

        self.assertIsNone(reloaded.get_mount("Lab mount"))

    def test_malformed_config_is_ignored(self):
        self.path.write_text("{ this is not json", encoding="utf-8")

        catalog = MountCatalog(self.path)

        self.assertIsNotNone(catalog.get_mount("C-mount"))
        self.assertEqual(catalog.get_available_mounts()["C-mount"]["flange_distance"], 17.526)

    def test_invalid_entries_are_skipped_without_losing_valid_ones(self):
        self.path.write_text(
            json.dumps(
                {
                    "custom_mounts": {
                        "Good mount": {"flange_distance": 20.0},
                        "Negative mount": {"flange_distance": -1.0},
                        "C-mount": {"flange_distance": 99.0},
                    }
                }
            ),
            encoding="utf-8",
        )

        catalog = MountCatalog(self.path)

        self.assertAlmostEqual(catalog.get_mount("Good mount")["flange_distance"], 20.0)
        self.assertIsNone(catalog.get_mount("Negative mount"))
        self.assertAlmostEqual(catalog.get_mount("C-mount")["flange_distance"], 17.526)

    def test_mechanical_designer_delegates_custom_mount_management(self):
        designer = MechanicalDesigner(None, mount_catalog=self.catalog)

        designer.add_custom_mount("Lab mount", 31.5)
        mount = designer.design_mount("Lab mount")

        self.assertEqual(mount.mount_type, "Lab mount")
        self.assertAlmostEqual(mount.flange_distance, 31.5)
        self.assertIn("Lab mount", designer.get_available_mounts())
        self.assertTrue(designer.remove_custom_mount("Lab mount"))
        self.assertNotIn("Lab mount", designer.get_available_mounts())

    def test_mechanical_designer_persists_custom_mounts(self):
        designer = MechanicalDesigner(None, mount_catalog=self.catalog)
        designer.add_custom_mount("Lab mount", 31.5)
        designer.save_custom_mounts()

        reloaded = MechanicalDesigner(None, mount_catalog=MountCatalog(self.path))

        self.assertAlmostEqual(
            reloaded.get_available_mounts()["Lab mount"]["flange_distance"], 31.5
        )


class TestLensMountModel(unittest.TestCase):
    """Lens owns a mount type and reports its working flange distance."""

    def test_default_mount_is_c_mount(self):
        self.assertEqual(Lens().mount_type, "C-mount")

    def test_working_flange_distance_adds_bfl_and_flange(self):
        lens = Lens(mount_type="M42")

        bfl = lens.calculate_back_focal_length()
        working = lens.calculate_working_flange_distance()

        self.assertAlmostEqual(working, bfl + 45.46)

    def test_working_flange_distance_uses_custom_mount(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / "mounts.json"
            catalog = MountCatalog(config)
            catalog.add_custom_mount("Lab mount", 31.5)
            catalog.save_custom_mounts()
            with mock.patch.dict(os.environ, {paths.MOUNTS_PATH_ENV_VAR: str(config)}, clear=False):
                lens = Lens(mount_type="Lab mount")
                working = lens.calculate_working_flange_distance()

        self.assertAlmostEqual(working, lens.calculate_back_focal_length() + 31.5)

    def test_unknown_mount_returns_none(self):
        self.assertIsNone(Lens(mount_type="No-such-mount").calculate_working_flange_distance())

    def test_afocal_lens_returns_none(self):
        lens = Lens(
            radius_of_curvature_1=100.0,
            radius_of_curvature_2=100.0,
            thickness=0.0,
            refractive_index=1.5168,
        )

        self.assertIsNone(lens.calculate_working_flange_distance())

    def test_mount_type_survives_serialization(self):
        lens = Lens(mount_type="EF-mount")

        data = lens.to_dict()
        restored = Lens.from_dict(data)

        self.assertEqual(data["mount_type"], "EF-mount")
        self.assertEqual(restored.mount_type, "EF-mount")

    def test_legacy_payload_defaults_to_c_mount(self):
        data = Lens().to_dict()
        data.pop("mount_type", None)

        self.assertEqual(Lens.from_dict(data).mount_type, "C-mount")

    def test_mount_type_is_not_duplicated_in_metadata(self):
        lens = Lens(mount_type="F-mount")
        data = lens.to_dict()

        restored = Lens.from_dict(data)

        self.assertNotIn("mount_type", restored.metadata)

    def test_mount_type_round_trips_through_sqlite(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = DatabaseManager(str(Path(tmp) / "lenses.db"))
            manager.save_lens(Lens(name="Nikon", mount_type="F-mount").to_dict())

            row = manager.load_all()[0]
            restored = Lens.from_dict(row)

        self.assertEqual(row["mount_type"], "F-mount")
        self.assertEqual(restored.mount_type, "F-mount")

    def test_default_mounts_path_lives_in_user_data_dir(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop(paths.MOUNTS_PATH_ENV_VAR, None)
            self.assertEqual(paths.default_mounts_path().parent, paths.user_data_dir())
            self.assertEqual(paths.default_mounts_path().name, "mounts.json")

    def test_mounts_path_override_is_honoured(self):
        with mock.patch.dict(
            os.environ, {paths.MOUNTS_PATH_ENV_VAR: "/tmp/custom-mounts.json"}, clear=False
        ):
            self.assertEqual(paths.default_mounts_path(), Path("/tmp/custom-mounts.json"))


class TestPerformanceMountMetrics(unittest.TestCase):
    """The exported metrics include the working flange distance and breakdown."""

    def test_all_metrics_include_working_flange_distance(self):
        lens = Lens(mount_type="M42")

        metrics = PerformanceMetrics(lens).get_all_metrics()

        self.assertAlmostEqual(
            metrics["working_flange_distance"],
            lens.calculate_back_focal_length() + 45.46,
        )
        self.assertEqual(metrics["mount_type"], "M42")

    def test_report_shows_working_flange_breakdown(self):
        lens = Lens(mount_type="C-mount")

        report = PerformanceMetrics(lens).format_metrics_report()

        bfl = lens.calculate_back_focal_length()
        self.assertIn("Working Flange Distance", report)
        self.assertIn("C-mount", report)
        self.assertIn(f"BFL: {bfl:.2f}mm", report)
        self.assertIn("17.53mm", report)


if __name__ == "__main__":
    unittest.main()
