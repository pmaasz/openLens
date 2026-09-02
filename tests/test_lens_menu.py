#!/usr/bin/env python3
"""
Lens quick-switch menu behaviour (review item 1.6).

The menu must reflect library state every time it opens - including the
deferred database load at startup and any create/delete afterwards -
instead of being populated once from an empty list.
"""

import os
import sys
import unittest

if os.environ.get("DISPLAY", "") == "" and sys.platform.startswith("linux"):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication
    from openlens import OpenLensWindow

    PYSIDE_AVAILABLE = True
except ImportError as _e:
    QApplication = None  # type: ignore
    OpenLensWindow = None  # type: ignore
    PYSIDE_AVAILABLE = False
    _PYSIDE_ERROR = _e

if not PYSIDE_AVAILABLE:

    class TestLensMenu(unittest.TestCase):
        @unittest.skip(f"PySide6 not available: {_PYSIDE_ERROR}")
        def test_skip(self):
            pass

else:

    class TestLensMenu(unittest.TestCase):
        """Dynamic rebuild of the Lens menu via aboutToShow"""

        @classmethod
        def setUpClass(cls):
            cls.app = QApplication.instance() or QApplication(sys.argv)

        def setUp(self):
            self.window = OpenLensWindow()
            # Detach from real user data: tests drive the lists directly.
            self.window._lenses = []
            self.window._assemblies = []
            self.window._current_lens = None
            self.window._current_assembly = None

        def tearDown(self):
            self.window.close()

        def _texts(self):
            return [a.text() for a in self.window._lens_menu.actions()]

        def test_empty_library_shows_placeholder(self):
            """No lenses/assemblies -> single disabled placeholder entry"""
            self.window._rebuild_lens_menu()
            texts = self._texts()
            self.assertEqual(len(texts), 1)
            self.assertFalse(self.window._lens_menu.actions()[0].isEnabled())

        def test_rebuild_reflects_current_library(self):
            """Lenses and assemblies appear without any manual refresh"""
            self.window._on_new_lens()
            self.window._on_new_lens()
            self.window._on_new_assembly()

            self.window._rebuild_lens_menu()
            texts = self._texts()
            self.assertIn("Lens 1", texts)
            self.assertIn("Lens 2", texts)
            self.assertIn("[Assembly 1]", texts)

        def test_current_selection_is_checked(self):
            """The active lens carries the checkmark"""
            self.window._on_new_lens()
            self.window._on_new_lens()
            self.window._rebuild_lens_menu()

            checked = [
                a.text()
                for a in self.window._lens_menu.actions()
                if a.isCheckable() and a.isChecked()
            ]
            self.assertEqual(checked, ["Lens 2"])

        def test_delete_shrinks_next_open(self):
            """Deleting the current lens shrinks the next menu build"""
            self.window._on_new_lens()
            self.window._on_new_lens()
            self.window._on_delete_lens()

            self.window._rebuild_lens_menu()
            texts = self._texts()
            self.assertNotIn("Lens 2", texts)
            self.assertIn("Lens 1", texts)

        def test_action_switches_active_item(self):
            """Triggering a lens action loads it into the editor"""
            self.window._on_new_lens()
            self.window._on_new_lens()
            self.window._rebuild_lens_menu()

            action = next(a for a in self.window._lens_menu.actions() if a.text() == "Lens 1")
            action.triggered.emit()
            self.assertEqual(self.window._current_lens.name, "Lens 1")
            self.assertIsNone(self.window._current_assembly)


if __name__ == "__main__":
    unittest.main()
