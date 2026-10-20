#!/usr/bin/env python3
"""The tab shortcuts the Keyboard Shortcuts dialog promises (#565).

Ctrl+1 ... Ctrl+6 were listed under "Tab Switching" but the application
created no QShortcut for them, so the keys did nothing. These tests check
that every advertised sequence exists, selects its tab, and that Ctrl+2 -
advertised even when no assembly is loaded - explains itself instead of
silently doing nothing.
"""

import os
import sys
import tempfile
import unittest
from unittest import mock

# Headless environments (CI): fall back to Qt's offscreen platform before
# any QApplication is created. A real DISPLAY always wins.
if os.environ.get("DISPLAY", "") == "" and sys.platform.startswith("linux"):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication
    from PySide6.QtTest import QTest
    from PySide6.QtCore import Qt

    from openlens import __main__ as main_window
    from openlens.__main__ import OpenLensWindow

    PYSIDE_AVAILABLE = True
except ImportError:  # pragma: no cover - depends on install
    QApplication = QTest = Qt = None  # type: ignore
    main_window = None  # type: ignore
    OpenLensWindow = None  # type: ignore
    PYSIDE_AVAILABLE = False


_app = None


def _ensure_app():
    """Create (once) and return the QApplication every widget needs."""
    global _app
    if _app is None:
        _app = QApplication.instance() or QApplication([])
    return _app


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 is not installed")
class TestTabShortcuts(unittest.TestCase):
    """The dialog's tab-switching block is backed by real shortcuts."""

    def setUp(self):
        _ensure_app()
        self._tmpdir = tempfile.TemporaryDirectory()
        self._env = mock.patch.dict(
            os.environ,
            {
                "OPENLENS_DATA_DIR": self._tmpdir.name,
                "OPENLENS_DB_PATH": os.path.join(self._tmpdir.name, "test.db"),
            },
        )
        self._env.start()

        self.window = OpenLensWindow()
        self.window.show()
        self.window.activateWindow()
        QApplication.processEvents()

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        QApplication.processEvents()
        self._env.stop()
        self._tmpdir.cleanup()

    def test_every_advertised_key_has_a_shortcut(self):
        """Each Ctrl+N in the dialog maps to one shortcut object."""
        expected = {key for _, key, _ in main_window.TAB_SHORTCUTS}
        actual = {shortcut.key().toString() for shortcut in self.window._tab_shortcuts}
        self.assertEqual(actual, expected)
        self.assertEqual(len(self.window._tab_shortcuts), 6)

    def test_shortcut_selects_its_tab(self):
        """Emitting each shortcut switches to the matching editor tab."""
        for index, _key, _name in main_window.TAB_SHORTCUTS:
            if index == 1:
                continue  # covered separately: the assembly tab starts hidden
            with self.subTest(index=index):
                self.window._editor_tabs.setCurrentIndex(0)
                self.window._tab_shortcuts[index].activated.emit()
                QApplication.processEvents()
                self.assertEqual(self.window._editor_tabs.currentIndex(), index)

    def test_key_press_really_switches_tabs(self):
        """The binding works through the real key dispatch, not just emit()."""
        self.window._editor_tabs.setCurrentIndex(0)

        QTest.keyClick(self.window, Qt.Key_3, Qt.ControlModifier)
        QApplication.processEvents()

        self.assertEqual(self.window._editor_tabs.currentIndex(), 2)
        self.assertEqual(self.window._status_bar.currentMessage(), "Simulation")

    def test_hidden_assembly_tab_reports_why(self):
        """Ctrl+2 with no assembly must say so, not look dead."""
        self.assertFalse(self.window._editor_tabs.isTabVisible(1))
        self.window._editor_tabs.setCurrentIndex(0)

        self.window._tab_shortcuts[1].activated.emit()
        QApplication.processEvents()

        self.assertEqual(self.window._editor_tabs.currentIndex(), 0)
        self.assertIn("no assembly loaded", self.window._status_bar.currentMessage())

    def test_assembly_shortcut_works_once_loaded(self):
        """After creating an assembly, Ctrl+1/Ctrl+2 both switch."""
        self.window._on_new_assembly()
        QApplication.processEvents()
        self.assertTrue(self.window._editor_tabs.isTabVisible(1))
        self.assertEqual(self.window._editor_tabs.currentIndex(), 1)

        self.window._tab_shortcuts[0].activated.emit()
        QApplication.processEvents()
        self.assertEqual(self.window._editor_tabs.currentIndex(), 0)

        self.window._tab_shortcuts[1].activated.emit()
        QApplication.processEvents()
        self.assertEqual(self.window._editor_tabs.currentIndex(), 1)


if __name__ == "__main__":
    unittest.main()
