#!/usr/bin/env python3
"""Preset/stock lens browser (#782)."""

import os
import sys
import tempfile
import unittest
from unittest import mock

if os.environ.get("DISPLAY", "") == "" and sys.platform.startswith("linux"):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication

    PYSIDE_AVAILABLE = True
except ImportError:  # pragma: no cover - environment guard
    QApplication = None  # type: ignore
    PYSIDE_AVAILABLE = False

from openlens.preset_library import get_preset_library


class TestPresetLibraryUsage(unittest.TestCase):
    def test_listing_and_filtering(self):
        library = get_preset_library()
        categories = library.list_categories()
        self.assertTrue(categories)
        all_presets = library.list_presets()
        self.assertTrue(all_presets)

        first_category = categories[0]
        filtered = library.list_presets(first_category)
        self.assertTrue(filtered)
        self.assertTrue(all(p.category == first_category for p in filtered))

        query = all_presets[0].name.split()[0]
        searched = library.search_presets(query)
        self.assertTrue(any(p.name == all_presets[0].name for p in searched))

    def test_copy_independence(self):
        library = get_preset_library()
        preset = library.list_presets()[0]
        copy1 = library.get_lens_copy(preset.name)
        copy2 = library.get_lens_copy(preset.name)
        self.assertIsNotNone(copy1)
        self.assertIsNotNone(copy2)
        self.assertNotEqual(copy1.id, preset.lens.id)
        self.assertNotEqual(copy2.id, preset.lens.id)
        self.assertNotEqual(copy1.id, copy2.id)

        original_name = preset.lens.name
        original_r1 = preset.lens.radius_of_curvature_1
        copy1.name = "Edited Copy"
        copy1.radius_of_curvature_1 = original_r1 + 7.0
        self.assertEqual(preset.lens.name, original_name)
        self.assertEqual(preset.lens.radius_of_curvature_1, original_r1)
        # A second copy is unaffected by edits to the first.
        self.assertNotEqual(copy2.radius_of_curvature_1, copy1.radius_of_curvature_1)


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 not available")
class TestPresetBrowserGui(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        from openlens.gui.dialogs.preset_browser import PresetBrowserDialog
        from openlens.__main__ import OpenLensWindow
        from openlens.gui.storage import LensStorage

        self.PresetBrowserDialog = PresetBrowserDialog
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
        self.storage = LensStorage(self.temp_db)
        self.window = OpenLensWindow()
        self.window._storage = self.storage
        self.window._db_path = self.temp_db
        self.window._lenses = []
        self.window._assemblies = []
        self.window._current_lens = None
        self.window._current_assembly = None
        self.window._load_default_lens()

    def tearDown(self):
        self.window.close()
        for path in [self.temp_db, self.temp_db + "-shm", self.temp_db + "-wal"]:
            if os.path.exists(path):
                os.remove(path)

    def test_dialog_lists_and_shows_summary(self):
        dialog = self.PresetBrowserDialog(self.window)
        self.assertGreater(dialog._list.count(), 0)
        dialog._list.setCurrentRow(0)
        summary = dialog._details.toPlainText()
        self.assertIn("Name:", summary)
        self.assertIn("Category:", summary)
        self.assertIn("Focal length:", summary)
        self.assertIn("Diameter:", summary)
        self.assertIn("Material:", summary)
        dialog.close()

    def test_dialog_creates_independent_copy(self):
        library = get_preset_library()
        preset = library.list_presets()[0]
        dialog = self.PresetBrowserDialog(self.window)
        # Select matching preset.
        for i in range(dialog._list.count()):
            item = dialog._list.item(i)
            if item.data(0x0100) == preset.name or item.text() == preset.name:
                dialog._list.setCurrentItem(item)
                break
        copy = dialog.selected_copy()
        self.assertIsNotNone(copy)
        self.assertNotEqual(copy.id, preset.lens.id)
        copy.name = "Mutated"
        self.assertNotEqual(preset.lens.name, "Mutated")
        dialog.close()

    def test_gui_action_adds_independent_lens(self):
        library = get_preset_library()
        preset = library.list_presets()[0]
        created = library.get_lens_copy(preset.name)

        class FakeDialog:
            DialogCode = self.PresetBrowserDialog.DialogCode

            def __init__(self, *a, **k):
                pass

            def exec(self):
                return self.DialogCode.Accepted

            def selected_copy(self):
                return created

        before = len(self.window._lenses)
        with mock.patch("openlens.gui.dialogs.preset_browser.PresetBrowserDialog", FakeDialog):
            self.window._on_new_from_preset()

        self.assertEqual(len(self.window._lenses), before + 1)
        self.assertIs(self.window._current_lens, created)
        self.assertIsNone(self.window._current_assembly)
        self.assertIn(created, self.window._lenses)
        # Independence from preset library.
        created.radius_of_curvature_1 = created.radius_of_curvature_1 + 5.0
        self.assertNotEqual(preset.lens.radius_of_curvature_1, created.radius_of_curvature_1)


if __name__ == "__main__":
    unittest.main()
