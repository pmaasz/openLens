#!/usr/bin/env python3
"""GUI tests for lens-mount selection and custom-mount management (#1)."""

import os
import sys
import tempfile
import unittest
from pathlib import Path

if os.environ.get("DISPLAY", "") == "" and sys.platform.startswith("linux"):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication

    from openlens.gui.dialogs.mount_manager import MountManagerDialog
    from openlens.gui.widgets.lens_editor import LensEditorWidget
    from openlens.lens import Lens
    from openlens.mounts import MountCatalog

    PYSIDE_AVAILABLE = True
except ImportError:  # pragma: no cover - depends on install
    QApplication = MountManagerDialog = LensEditorWidget = None  # type: ignore
    Lens = MountCatalog = None  # type: ignore
    PYSIDE_AVAILABLE = False


def _ensure_app():
    from tests import ensure_qapp

    return ensure_qapp()


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 is not installed")
class TestLensEditorMountControls(unittest.TestCase):
    """The editor owns the per-lens mount and shows its working flange."""

    def setUp(self):
        _ensure_app()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.catalog = MountCatalog(Path(self.tmp.name) / "mounts.json")
        self.editor = LensEditorWidget(mount_catalog=self.catalog)

    def tearDown(self):
        self.editor.close()
        self.editor.deleteLater()
        QApplication.processEvents()

    def test_all_standard_mounts_are_listed(self):
        names = [
            self.editor._mount_combo.itemText(i) for i in range(self.editor._mount_combo.count())
        ]

        for mount in ("C-mount", "M42", "X-mount", "EF-mount", "F-mount"):
            with self.subTest(mount=mount):
                self.assertIn(mount, names)

    def test_loading_a_lens_selects_its_mount(self):
        self.editor.load_lens(Lens(mount_type="M42"))

        self.assertEqual(self.editor._mount_combo.currentText(), "M42")

    def test_working_flange_breakdown_is_displayed(self):
        lens = Lens(mount_type="M42")
        self.editor.load_lens(lens)

        text = self.editor._working_flange_label.text()

        self.assertIn("45.46", text)
        self.assertIn("BFL", text)
        self.assertIn(f"{lens.calculate_working_flange_distance():.2f}", text)

    def test_changing_the_mount_updates_and_undoes_the_model(self):
        lens = Lens(mount_type="M42")
        self.editor.load_lens(lens)

        self.editor._mount_combo.setCurrentText("EF-mount")

        self.assertEqual(lens.mount_type, "EF-mount")
        self.assertIn("44.00", self.editor._working_flange_label.text())

        self.editor.undo_stack.undo()

        self.assertEqual(lens.mount_type, "M42")

    def test_unknown_mount_is_shown_and_flagged(self):
        lens = Lens(mount_type="Removed mount")
        self.editor.load_lens(lens)

        self.assertEqual(self.editor._mount_combo.currentText(), "Removed mount")
        self.assertEqual(self.editor._working_flange_label.text(), "--")

    def test_custom_mount_from_catalog_is_available(self):
        self.catalog.add_custom_mount("Lab mount", 31.5)

        self.editor._refresh_mount_combo("Lab mount")

        self.assertEqual(self.editor._mount_combo.currentText(), "Lab mount")


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 is not installed")
class TestMountManagerDialog(unittest.TestCase):
    """The dialog adds and removes persisted custom mounts."""

    def setUp(self):
        _ensure_app()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "mounts.json"
        self.catalog = MountCatalog(self.path)
        self.dialog = MountManagerDialog(catalog=self.catalog)

    def tearDown(self):
        self.dialog.close()
        self.dialog.deleteLater()
        QApplication.processEvents()

    def test_adding_a_mount_persists_it(self):
        self.dialog._name_input.setText("Lab mount")
        self.dialog._flange_input.setValue(31.5)

        self.dialog._on_add()

        self.assertAlmostEqual(self.catalog.get_mount("Lab mount")["flange_distance"], 31.5)
        self.assertTrue(self.path.exists())
        self.assertEqual(self.dialog._custom_list.count(), 1)

    def test_removing_the_selected_mount_persists_the_change(self):
        self.catalog.add_custom_mount("Lab mount", 31.5)
        self.catalog.save_custom_mounts()
        self.dialog._refresh()

        self.dialog._custom_list.setCurrentRow(0)
        self.dialog._on_remove()

        self.assertIsNone(self.catalog.get_mount("Lab mount"))
        self.assertEqual(self.dialog._custom_list.count(), 0)
        self.assertIsNone(MountCatalog(self.path).get_mount("Lab mount"))


if __name__ == "__main__":
    unittest.main()
