#!/usr/bin/env python3
"""
Optimization tab variable selection must survive a refresh.

refresh() tears down and rebuilds every variable checkbox from a hard-coded
default, and it is reached from _update_all_tabs() on *any* model change. So
one keystroke in an unrelated field silently undid the user's variable
selection:

    before typing:            ['r1_0']
    after a name keystroke:   ['r1_0', 'r2_0', 'th_0']
"""

import os
import sys
import tempfile
import unittest

if os.environ.get("DISPLAY", "") == "" and sys.platform.startswith("linux"):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication

    PYSIDE_AVAILABLE = True
except ImportError as _e:
    QApplication = None  # type: ignore
    PYSIDE_AVAILABLE = False
    _PYSIDE_ERROR = _e

from src.lens import Lens
from src.optical_system import OpticalSystem

if not PYSIDE_AVAILABLE:  # pragma: no cover - environment guard

    class TestOptimizationVariableSelection(unittest.TestCase):
        @unittest.skip(f"PySide6 not available: {_PYSIDE_ERROR}")
        def test_skip(self):
            pass


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 not available")
class TestOptimizationVariableSelection(unittest.TestCase):
    def setUp(self):
        self.app = QApplication.instance() or QApplication(sys.argv)
        import openlens

        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)

        self.window = openlens.OpenLensWindow()
        from src.gui.storage import LensStorage

        self.window._storage = LensStorage(self.db_path)
        self.window._db_path = self.db_path
        self.window._lenses = []
        self.window._assemblies = []

        self.lens = Lens(
            name="Test",
            radius_of_curvature_1=50.0,
            radius_of_curvature_2=-50.0,
            thickness=5.0,
            diameter=20.0,
        )
        self.window._lenses = [self.lens]
        self.window._current_lens = self.lens
        self.window._current_assembly = None
        self.window._update_all_tabs()

    def tearDown(self):
        self.window.close()
        for suffix in ("", "-shm", "-wal"):
            if os.path.exists(self.db_path + suffix):
                os.unlink(self.db_path + suffix)

    def _selected(self):
        tab = self.window._opt_tab
        return sorted(key for key, cb in tab._opt_check_vars.items() if cb.isChecked())

    def _select_only(self, keys):
        tab = self.window._opt_tab
        for cb in tab._opt_check_vars.values():
            cb.setChecked(False)
        for key in keys:
            tab._opt_check_vars[key].setChecked(True)

    def test_defaults_apply_on_first_build(self):
        self.assertIn("r1_0", self._selected())

    def test_unrelated_edit_preserves_selection(self):
        """The reported regression."""
        self._select_only(["r1_0"])
        self.assertEqual(self._selected(), ["r1_0"])

        self.lens.name = "Renamed"
        self.window._update_all_tabs()

        self.assertEqual(self._selected(), ["r1_0"])

    def test_repeated_edits_keep_preserving(self):
        self._select_only(["r1_0"])
        for value in ("A", "B", "C"):
            self.lens.name = value
            self.window._update_all_tabs()
        self.assertEqual(self._selected(), ["r1_0"])

    def test_explicitly_unticked_variables_stay_unticked(self):
        """Preserving must keep unticked as well as ticked."""
        self._select_only(["r2_0"])
        self.lens.thickness = 6.0
        self.window._update_all_tabs()
        self.assertEqual(self._selected(), ["r2_0"])

    def test_geometry_edit_preserves_selection(self):
        self._select_only(["th_0"])
        self.lens.radius_of_curvature_1 = 75.0
        self.window._update_all_tabs()
        self.assertEqual(self._selected(), ["th_0"])

    def test_switching_lens_gives_fresh_defaults(self):
        """A different subject is a deliberate change, not an unrelated edit."""
        self._select_only(["r1_0"])

        other = Lens(
            name="Other",
            radius_of_curvature_1=80.0,
            radius_of_curvature_2=-80.0,
            thickness=4.0,
            diameter=20.0,
        )
        self.window._lenses = [self.lens, other]
        self.window._current_lens = other
        self.window._update_all_tabs()

        selected = self._selected()
        self.assertNotEqual(selected, ["r1_0"])
        self.assertIn("r1_0", selected)

    def test_preserve_selection_false_rebuilds_defaults(self):
        """The escape hatch the parameter exists for."""
        self._select_only(["r1_0"])
        self.window._opt_tab.refresh(preserve_selection=False)
        self.assertNotEqual(self._selected(), ["r1_0"])

    def test_selection_survives_for_assemblies(self):
        system = OpticalSystem(name="Asm")
        for index in range(2):
            system.add_lens(
                Lens(
                    name=f"L{index}",
                    radius_of_curvature_1=50.0 + index,
                    radius_of_curvature_2=-50.0 - index,
                    thickness=5.0,
                    diameter=20.0,
                ),
                air_gap_before=0 if index == 0 else 2.0,
            )
        self.window._assemblies = [system]
        self.window._current_lens = None
        self.window._current_assembly = system
        self.window._update_all_tabs()

        self._select_only(["r2_1"])
        self.assertEqual(self._selected(), ["r2_1"])

        system.name = "Renamed"
        self.window._update_all_tabs()
        self.assertEqual(self._selected(), ["r2_1"])


if __name__ == "__main__":
    unittest.main()
