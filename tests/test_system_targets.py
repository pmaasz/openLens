#!/usr/bin/env python3
"""One definition for "the active model" and "as an OpticalSystem" (#562).

The window repeated `assembly if assembly else lens` in every handler, and the
lens-to-system wrapper existed three times with different copy behaviour. The
tests cover the shared helper, the window's precedence, and that the tabs defer
to the window instead of re-deriving it.
"""

import os
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

# Headless environments (CI): fall back to Qt's offscreen platform before
# any QApplication is created. A real DISPLAY always wins.
if os.environ.get("DISPLAY", "") == "" and sys.platform.startswith("linux"):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from openlens import optical_system
from openlens.lens import Lens
from openlens.optical_system import OpticalSystem

try:
    from PySide6.QtWidgets import QApplication

    from openlens.__main__ import OpenLensWindow
    from openlens.gui.tabs import performance_tab, simulation_tab, tolerancing_tab

    PYSIDE_AVAILABLE = True
except ImportError as _pyside_error:  # pragma: no cover - depends on install
    QApplication = None  # type: ignore
    OpenLensWindow = None  # type: ignore
    performance_tab = simulation_tab = tolerancing_tab = None  # type: ignore
    PYSIDE_AVAILABLE = False


def _ensure_app():
    """Create (once) and return the QApplication every widget needs."""
    from tests import ensure_qapp

    return ensure_qapp()


def _lens(name="Test Lens"):
    """A minimal valid lens for the wrapper tests."""
    return Lens(
        name=name,
        radius_of_curvature_1=100.0,
        radius_of_curvature_2=-100.0,
        thickness=5.0,
        diameter=40.0,
    )


class TestAsSystem(unittest.TestCase):
    """The shared wrapper keeps the call sites' copy semantics."""

    def test_lens_is_wrapped_and_keeps_its_name(self):
        lens = _lens("Crown")
        system = optical_system.as_system(lens)

        self.assertIsInstance(system, OpticalSystem)
        self.assertEqual(system.name, "Crown")
        self.assertEqual(len(system.elements), 1)
        self.assertIs(system.elements[0].lens, lens)

    def test_wrapper_name_can_be_overridden(self):
        system = optical_system.as_system(_lens(), name="Tolerancing")
        self.assertEqual(system.name, "Tolerancing")

    def test_existing_system_is_passed_through(self):
        system = OpticalSystem(name="Assembly")
        system.add_lens(_lens())
        self.assertIs(optical_system.as_system(system), system)

    def test_copy_mode_copies_a_system_and_its_elements(self):
        system = OpticalSystem(name="Assembly")
        system.add_lens(_lens())

        copied = optical_system.as_system(system, copy_system=True)

        self.assertIsNot(copied, system)
        self.assertEqual(copied.name, system.name)
        self.assertEqual(len(copied.elements), 1)
        self.assertIsNot(copied.elements[0].lens, system.elements[0].lens)
        copied.elements[0].lens.radius_of_curvature_1 = 12.0
        self.assertNotEqual(system.elements[0].lens.radius_of_curvature_1, 12.0)

    def test_copy_mode_copies_a_bare_lens(self):
        lens = _lens()
        system = optical_system.as_system(lens, copy_system=True)

        self.assertIsNot(system.elements[0].lens, lens)
        self.assertEqual(system.elements[0].lens.name, lens.name)

    def test_invalid_target_raises_type_error(self):
        with self.assertRaises(TypeError):
            optical_system.as_system(object())


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 is not installed")
class TestActiveTarget(unittest.TestCase):
    """The window owns the precedence and the tabs defer to it."""

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
        QApplication.processEvents()

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        QApplication.processEvents()
        self._env.stop()
        self._tmpdir.cleanup()

    def test_prefers_the_assembly_and_falls_back_to_the_lens(self):
        self.assertIs(self.window._active_target(), self.window._current_lens)

        self.window._on_new_assembly()
        QApplication.processEvents()
        self.assertIs(self.window._active_target(), self.window._current_assembly)

        self.window._switch_to_lens(0)
        QApplication.processEvents()
        self.assertIs(self.window._active_target(), self.window._current_lens)

    def test_ensure_system_matches_the_shared_helper(self):
        lens = self.window._current_lens
        system = self.window._ensure_system(lens)
        self.assertIsInstance(system, OpticalSystem)
        self.assertIs(system.elements[0].lens, lens)

        self.window._on_new_assembly()
        assembly = self.window._current_assembly
        self.assertIs(self.window._ensure_system(assembly), assembly)

    def test_performance_tab_uses_the_parent_helper(self):
        tab = performance_tab.PerformanceTab()
        try:
            sentinel = object()
            tab._parent = SimpleNamespace(
                _current_assembly=object(),
                _current_lens=object(),
                _active_target=lambda: sentinel,
            )
            self.assertIs(tab._current_system(), sentinel)
        finally:
            tab.close()
            tab.deleteLater()

    def test_performance_tab_falls_back_for_partial_parents(self):
        tab = performance_tab.PerformanceTab()
        try:
            lens = _lens()
            tab._parent = SimpleNamespace(_current_assembly=None, _current_lens=lens)
            self.assertIs(tab._current_system(), lens)
        finally:
            tab.close()
            tab.deleteLater()

    def test_simulation_and_tolerancing_share_the_proxy(self):
        sentinel = object()
        parent = SimpleNamespace(
            _current_assembly=object(),
            _current_lens=object(),
            _active_target=lambda: sentinel,
        )

        sim = simulation_tab.SimulationTab()
        tol = tolerancing_tab.TolerancingTab()
        try:
            sim._parent = parent
            tol._parent = parent
            self.assertIs(sim._active_target(), sentinel)
            self.assertIs(tol._resolve_target(), sentinel)
        finally:
            sim.close()
            sim.deleteLater()
            tol.close()
            tol.deleteLater()
        QApplication.processEvents()


if __name__ == "__main__":
    unittest.main()
