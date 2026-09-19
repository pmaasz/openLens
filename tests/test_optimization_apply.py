"""Regression: Apply&Keep must update the editor, library, and database."""

import copy
import os
import sys
import tempfile
import unittest

from PySide6.QtWidgets import QApplication

from openlens import OpenLensWindow
from src.lens import Lens
from src.optical_system import OpticalSystem

app = QApplication.instance()
if not app:
    app = QApplication(sys.argv)


class _HermeticWindow(unittest.TestCase):
    """Window wired to a temp database (mirrors test_gui hermetic pattern)."""

    def setUp(self):
        from src.gui.storage import LensStorage

        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
        self.window = OpenLensWindow()
        self.window._storage = LensStorage(self.temp_db)
        self.window._db_path = self.temp_db
        self.window._lenses = []
        self.window._assemblies = []
        self.window._current_lens = None
        self.window._current_assembly = None

    def tearDown(self):
        self.window.close()
        if os.path.exists(self.temp_db):
            os.remove(self.temp_db)
        for ext in ["-shm", "-wal"]:
            if os.path.exists(self.temp_db + ext):
                os.remove(self.temp_db + ext)

    def _rows_for(self, lens_id):
        from src.gui.storage import LensStorage

        return [x for x in LensStorage(self.temp_db).load_lenses() if x.id == lens_id]


class TestApplyKeepSingleLens(_HermeticWindow):
    def test_apply_updates_editor_library_and_db(self):
        """Optimized single lens must land in editor, list, and storage."""
        lens = Lens(
            name="Opt Lens",
            radius_of_curvature_1=100.0,
            radius_of_curvature_2=-100.0,
            thickness=5.0,
            diameter=40.0,
            material="BK7",
        )
        self.window._lenses = [lens]
        self.window._current_lens = lens
        self.window._lens_editor.load_lens(lens)

        # Mimic the worker: 1-element system around a deep copy, radius changed.
        pending = OpticalSystem(name="Optimization")
        changed = copy.deepcopy(lens)
        changed.radius_of_curvature_1 = 80.0
        pending.add_lens(changed)

        tab = self.window._opt_tab
        tab._opt_original_target = lens
        tab._opt_pending_target = pending
        tab._on_apply_optimization()

        # Editor shows the new value.
        self.assertAlmostEqual(self.window._lens_editor._r1_input.value(), 80.0)
        # Library member carries the new value under the same id.
        self.assertEqual(len(self.window._lenses), 1)
        self.assertAlmostEqual(self.window._lenses[0].radius_of_curvature_1, 80.0)
        self.assertEqual(self.window._lenses[0].id, lens.id)
        self.assertIs(self.window._current_lens, self.window._lenses[0])
        # And it persisted (reconciling save must not drop it).
        rows = self._rows_for(lens.id)
        self.assertEqual(len(rows), 1)
        self.assertAlmostEqual(rows[0].radius_of_curvature_1, 80.0)


class TestApplyKeepAssembly(_HermeticWindow):
    def test_apply_updates_assembly_library_and_db(self):
        """Optimized assembly must replace its library member and persist."""
        system = OpticalSystem(name="Opt Assembly")
        system.add_lens(Lens(name="A", diameter=25.0))
        system.add_lens(Lens(name="B", diameter=25.0), air_gap_before=5.0)
        self.window._assemblies = [system]
        self.window._current_assembly = system

        pending = copy.deepcopy(system)
        pending.elements[0].lens.thickness = 9.0
        pending._update_positions()

        tab = self.window._opt_tab
        tab._opt_original_target = system
        tab._opt_pending_target = pending
        tab._on_apply_optimization()

        self.assertEqual(len(self.window._assemblies), 1)
        self.assertIs(self.window._current_assembly, self.window._assemblies[0])
        self.assertAlmostEqual(self.window._current_assembly.elements[0].lens.thickness, 9.0)
        rows = self._rows_for(pending.elements[0].lens.id)
        self.assertEqual(len(rows), 1)
        self.assertAlmostEqual(rows[0].thickness, 9.0)


if __name__ == "__main__":
    unittest.main()
