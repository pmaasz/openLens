#!/usr/bin/env python3
"""Zemax .zmx GUI import/export (#783)."""

import os
import sys
import tempfile
import unittest
from unittest import mock

if os.environ.get("DISPLAY", "") == "" and sys.platform.startswith("linux"):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication

    from openlens.__main__ import OpenLensWindow

    PYSIDE_AVAILABLE = True
except ImportError:
    QApplication = None  # type: ignore
    OpenLensWindow = None  # type: ignore
    PYSIDE_AVAILABLE = False

from openlens.lens import Lens
from openlens.optical_system import create_doublet


class _Signal:
    def __init__(self):
        self._slots = []

    def connect(self, slot):
        self._slots.append(slot)

    def emit(self, *args):
        for slot in list(self._slots):
            slot(*args)


class _InlineWorker:
    def __init__(self, compute, parent=None):
        self._compute = compute
        self.done = _Signal()
        self.failed = _Signal()
        self.finished = _Signal()

    def isRunning(self):
        return False

    def start(self):
        try:
            result = self._compute()
        except Exception as exc:  # noqa: BLE001 - mirrors AnalysisWorker
            self.failed.emit(str(exc))
        else:
            self.done.emit(result)
        self.finished.emit()


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 not available")
class TestZemaxGui(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        from openlens.gui.storage import LensStorage

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
        handle, self.zmx_path = tempfile.mkstemp(suffix=".zmx")
        os.close(handle)
        os.remove(self.zmx_path)

    def tearDown(self):
        self.window.close()
        for path in [self.temp_db, self.temp_db + "-shm", self.temp_db + "-wal", self.zmx_path]:
            if os.path.exists(path):
                os.remove(path)

    def _find_action(self, menu, text_contains):
        for action in menu.actions():
            if text_contains in action.text():
                return action
            submenu = action.menu()
            if submenu is not None:
                found = self._find_action(submenu, text_contains)
                if found is not None:
                    return found
        return None

    def test_menu_wiring_has_zemax_import_and_export(self):
        # Handlers exist (wired from menu actions).
        self.assertTrue(callable(getattr(self.window, "_on_import_zemax", None)))
        self.assertTrue(callable(getattr(self.window, "_on_export_zemax", None)))

        # Menu text present in File > Import / Export.
        texts = []
        for action in self.window.menuBar().actions():
            menu = action.menu()
            if menu is None:
                continue
            for item in menu.actions():
                texts.append(item.text())
                sub = item.menu()
                if sub is not None:
                    texts.extend(a.text() for a in sub.actions())
        self.assertIn("Zemax Prescription (.zmx, simplified dialect)...", texts)
        self.assertGreaterEqual(texts.count("Zemax Prescription (.zmx, simplified dialect)..."), 2)

    def test_export_writes_simplified_zmx(self):
        system = create_doublet(diameter=25.0)
        system.name = "ExportTest"
        self.window._current_assembly = system
        self.window._current_lens = None
        with mock.patch(
            "openlens.__main__.QFileDialog.getSaveFileName",
            return_value=(self.zmx_path, ""),
        ), mock.patch("openlens.__main__.QMessageBox.critical") as critical:
            self.window._on_export_zemax()
        self.assertFalse(critical.called)
        self.assertTrue(os.path.exists(self.zmx_path))
        with open(self.zmx_path) as fh:
            content = fh.read()
        self.assertIn("VERS 140000", content)
        self.assertIn("MODE SEQ", content)

    def test_import_roundtrip_preserves_system(self):
        system = create_doublet(diameter=25.0)
        system.name = "RoundTrip"
        system.set_aperture_stop(0, diameter=20.0)
        self.window._current_assembly = system
        self.window._current_lens = None
        with mock.patch(
            "openlens.__main__.QFileDialog.getSaveFileName",
            return_value=(self.zmx_path, ""),
        ):
            self.window._on_export_zemax()

        self.window._current_assembly = None
        self.window._current_lens = None
        with mock.patch(
            "openlens.__main__.QFileDialog.getOpenFileName",
            return_value=(self.zmx_path, ""),
        ), mock.patch("openlens.__main__.AnalysisWorker", _InlineWorker), mock.patch(
            "openlens.__main__.QMessageBox.critical"
        ) as critical, mock.patch(
            "openlens.__main__.QMessageBox.warning"
        ):
            self.window._on_import_zemax()

        self.assertFalse(critical.called)
        imported = self.window._current_assembly
        self.assertIsNotNone(imported)
        self.assertEqual(len(imported.elements), len(system.elements))
        self.assertIsNotNone(imported.get_aperture_stop())
        self.assertEqual(imported.get_aperture_stop()["gap_index"], 0)
        # Focal length preserved within model tolerance.
        self.assertAlmostEqual(
            imported.get_system_focal_length(),
            system.get_system_focal_length(),
            delta=0.5,
        )

    def test_import_failure_does_not_replace_target(self):
        original = Lens(name="KeepMe")
        self.window._current_lens = original
        self.window._current_assembly = None
        with mock.patch(
            "openlens.__main__.QFileDialog.getOpenFileName",
            return_value=("/tmp/does-not-exist-zemax-783.zmx", ""),
        ), mock.patch("openlens.__main__.AnalysisWorker", _InlineWorker), mock.patch(
            "openlens.__main__.QMessageBox.critical"
        ) as critical:
            self.window._on_import_zemax()
        self.assertTrue(critical.called)
        self.assertIs(self.window._current_lens, original)
        self.assertIsNone(self.window._current_assembly)

    def test_import_warns_on_unsupported_constructs(self):
        zmx = (
            "VERS 140000\nMODE SEQ\n"
            "SURF 0\n  TYPE STANDARD\n  CURV 0.0\n  DISZ INFINITY\n\n"
            "SURF 1\n  TYPE COORDBRK\n  DISZ 0.0\n\n"
            "SURF 2\n  TYPE STANDARD\n\n"
        )
        with open(self.zmx_path, "w") as fh:
            fh.write(zmx)
        with mock.patch(
            "openlens.__main__.QFileDialog.getOpenFileName",
            return_value=(self.zmx_path, ""),
        ), mock.patch("openlens.__main__.AnalysisWorker", _InlineWorker), mock.patch(
            "openlens.__main__.QMessageBox.critical"
        ) as critical, mock.patch(
            "openlens.__main__.QMessageBox.warning"
        ) as warning:
            self.window._on_import_zemax()
        self.assertFalse(critical.called)
        self.assertTrue(warning.called)
        message = warning.call_args[0][2]
        self.assertIn("Unsupported constructs", message)
        self.assertIn("unsupported surface type", message.lower())


if __name__ == "__main__":
    unittest.main()
