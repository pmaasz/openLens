#!/usr/bin/env python3
"""
Refactored GUI functional tests for OpenLens using PySide6 and QtTest.
"""

import unittest
import sys
import os
import tempfile

# Headless environments (CI): fall back to Qt's offscreen platform before
# any QApplication is created. A real DISPLAY always wins.
if os.environ.get("DISPLAY", "") == "" and sys.platform.startswith("linux"):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication
    from PySide6.QtTest import QTest
    from PySide6.QtCore import Qt
    from openlens import OpenLensWindow

    PYSIDE_AVAILABLE = True
except ImportError as _e:
    QApplication = QTest = Qt = None  # type: ignore
    OpenLensWindow = None  # type: ignore
    PYSIDE_AVAILABLE = False
    _PYSIDE_ERROR = _e

from src.lens import Lens
from src.optical_system import OpticalSystem

if not PYSIDE_AVAILABLE:

    class TestOpenLensGUI(unittest.TestCase):
        @unittest.skip(f"PySide6 not available: {_PYSIDE_ERROR}")
        def test_skip(self):
            pass

else:
    # Ensure a QApplication instance exists
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)

    class TestOpenLensGUI(unittest.TestCase):
        """Test cases for the PySide6 OpenLens GUI"""

        def setUp(self):
            """Set up test fixtures"""
            self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
            # Override DB path for testing
            # We'll initialize the window with no specific action to test defaults
            self.window = OpenLensWindow()
            self.window._db_path = self.temp_db
            self.window.show()

        def tearDown(self):
            """Clean up test fixtures"""
            self.window.close()
            if os.path.exists(self.temp_db):
                os.remove(self.temp_db)
            for ext in ["-shm", "-wal"]:
                if os.path.exists(self.temp_db + ext):
                    os.remove(self.temp_db + ext)

        def test_initial_state(self):
            """Test that the window initializes with a default lens"""
            self.assertIsNotNone(self.window._current_lens)
            self.assertEqual(self.window._editor_tabs.count(), 6)
            # Lens Editor should be the first tab and visible
            self.assertEqual(self.window._editor_tabs.currentIndex(), 0)

        def test_new_lens_action(self):
            """Test creating a new lens via the action"""
            initial_count = len(self.window._lenses)
            self.window._on_new_lens()
            self.assertEqual(len(self.window._lenses), initial_count + 1)
            self.assertIn("Lens", self.window._current_lens.name)

        def test_new_assembly_action(self):
            """Test creating a new assembly"""
            initial_asm_count = len(self.window._assemblies)
            self.window._on_new_assembly()
            self.assertEqual(len(self.window._assemblies), initial_asm_count + 1)
            self.assertIsNotNone(self.window._current_assembly)
            # Assembly tab should be visible and active
            self.assertTrue(self.window._editor_tabs.isTabVisible(1))
            self.assertEqual(self.window._editor_tabs.currentIndex(), 1)

        def test_switch_to_lens(self):
            """Test switching between multiple lenses"""
            self.window._on_new_lens()  # Lens 2
            self.window._on_new_lens()  # Lens 3

            self.window._switch_to_lens(0)
            self.assertEqual(self.window._current_lens, self.window._lenses[0])

            self.window._switch_to_lens(1)
            self.assertEqual(self.window._current_lens, self.window._lenses[1])

        def test_add_lens_to_system(self):
            """Test the assembly builder: adding a lens to a system"""
            self.window._on_new_assembly()
            # Mock lens list selection
            tab = self.window._assembly_tab_widget
            tab._assembly_lens_list.setCurrentRow(0)
            tab._on_add_lens_to_system()

            self.assertEqual(len(tab._optical_system.elements), 1)
            self.assertEqual(tab._system_list.count(), 1)

        def test_simulation_run(self):
            """Test running a simulation updates the viz widget"""
            self.window._editor_tabs.setCurrentIndex(2)  # Simulation tab
            QApplication.processEvents()

            viz = self.window._sim_tab._sim_viz
            # Force a simulation run with direct params if the UI bound one is failing in headless
            active_system = (
                self.window._current_assembly
                if self.window._current_assembly
                else self.window._current_lens
            )
            viz.run_simulation(active_system, num_rays=5)
            self.assertGreater(len(viz._rays), 0)

    class TestLensEditorWidget(unittest.TestCase):
        """Tests for the lens editor panel (edge lock, load integrity)."""

        def setUp(self):
            """Create a standalone editor widget."""
            from src.gui.widgets.lens_editor import LensEditorWidget

            self.widget = LensEditorWidget()

        def _load(
            self,
            r1=100.0,
            r2=-100.0,
            thickness=5.0,
            diameter=40.0,
            lock=True,
        ):
            """Load a lens with the edge lock in a known state."""
            self.widget._lock_edge_check.setChecked(lock)
            self.widget.load_lens(
                Lens(
                    name="T",
                    radius_of_curvature_1=r1,
                    radius_of_curvature_2=r2,
                    thickness=thickness,
                    diameter=diameter,
                )
            )
            return self.widget._lens

        def test_load_lens_preserves_all_fields(self):
            """Loading must not clobber fields with stale spinbox values."""
            for lock in (False, True):
                lens = self._load(r1=86.63, r2=-109.97, thickness=5.0, diameter=50.0, lock=lock)
                self.assertAlmostEqual(lens.radius_of_curvature_1, 86.63)
                self.assertAlmostEqual(lens.radius_of_curvature_2, -109.97)
                self.assertAlmostEqual(lens.thickness, 5.0)
                self.assertAlmostEqual(lens.diameter, 50.0)
                self.assertAlmostEqual(self.widget._r2_input.value(), -109.97)
                self.assertAlmostEqual(self.widget._diameter_input.value(), 50.0)

        def test_edge_lock_preserves_rim(self):
            """Steepening a radius with the lock on compensates thickness."""
            lens = self._load(lock=True)
            edge_before = lens.calculate_edge_thickness()
            self.widget._r1_input.setValue(60.0)
            self.assertAlmostEqual(lens.calculate_edge_thickness(), edge_before, places=6)
            self.assertGreater(lens.thickness, 5.0)

        def test_edge_lock_off_keeps_center(self):
            """With the lock off, radii edits leave thickness alone."""
            lens = self._load(lock=False)
            self.widget._r1_input.setValue(60.0)
            self.assertAlmostEqual(lens.thickness, 5.0)
            self.assertLess(
                lens.calculate_edge_thickness(),
                0.959,
            )

        def test_infeasible_load_warns(self):
            """An intersecting spec loads intact and shows the warning."""
            self._load(r1=86.63, r2=-109.97, thickness=5.0, diameter=50.0, lock=False)
            self.assertIn("-1.5", self.widget._edge_label.text())
            self.assertFalse(self.widget._feas_warning_label.isHidden())

        def test_parabolic_drag_is_ignored(self):
            """Radius drags on a parabolic surface change nothing."""
            lens = self._load(lock=True)
            lens.is_parabolic_1 = True
            lens.parabolic_sag_1 = 2.0
            self.widget._on_interactive_property_changed("r1", 5.0)
            self.assertEqual(lens.radius_of_curvature_1, 100.0)
            self.assertEqual(lens.parabolic_sag_1, 2.0)

        def test_sag_ranges_track_diameter(self):
            """Sag spinbox limits follow the physics-scaled bound."""
            self._load(lock=True)
            self.assertAlmostEqual(self.widget._para1_sag_input.maximum(), 20.0)
            self.assertAlmostEqual(self.widget._para1_sag_input.minimum(), -20.0)
            self.widget._diameter_input.setValue(10.0)
            self.assertAlmostEqual(self.widget._para1_sag_input.maximum(), 5.0)

        def test_sag_clamp_syncs_model(self):
            """Shrinking the aperture clamps sag in spinbox and model."""
            self._load(lock=True)
            self.widget._para1_check.setChecked(True)
            self.widget._para1_sag_input.setValue(15.0)
            self.assertEqual(self.widget._lens.parabolic_sag_1, 15.0)
            self.widget._diameter_input.setValue(10.0)
            self.assertEqual(self.widget._para1_sag_input.value(), 5.0)
            self.assertEqual(self.widget._lens.parabolic_sag_1, 5.0)

        def test_load_preserves_over_limit_sag(self):
            """Loading never silently normalizes; the warning flags it."""
            widget_lens = Lens(
                name="T",
                thickness=5.0,
                diameter=10.0,
                is_parabolic_1=True,
                parabolic_sag_1=15.0,
            )
            self.widget._lock_edge_check.setChecked(True)
            self.widget.load_lens(widget_lens)
            self.assertEqual(self.widget._lens.parabolic_sag_1, 15.0)
            self.assertEqual(self.widget._para1_sag_input.value(), 5.0)
            self.assertFalse(self.widget._feas_warning_label.isHidden())

        def test_calculated_labels_match_lens_model(self):
            """Focal/power labels delegate to Lens (no widget-side lensmaker)."""
            self._load(lock=True)
            self.assertEqual(self.widget._focal_label.text(), "97.58 mm")
            self.assertEqual(self.widget._power_label.text(), "10.25 D")

        def test_parabolic_infeasible_warns(self):
            """Feasibility covers parabolic surfaces, not just radii."""
            widget_lens = Lens(
                name="T",
                thickness=5.0,
                diameter=40.0,
                is_parabolic_1=True,
                parabolic_sag_1=30.0,
            )
            self.widget._lock_edge_check.setChecked(False)
            self.widget.load_lens(widget_lens)
            self.assertFalse(self.widget._feas_warning_label.isHidden())

        def test_external_latch_heals_panel(self):
            """Optimizer-style flag mutation snaps the panel on next edit."""
            self._load(lock=True)
            self.widget._lens.is_parabolic_1 = True
            self.widget._lens.parabolic_sag_1 = 8.0
            self.assertFalse(self.widget._para1_check.isChecked())
            self.widget._diameter_input.setValue(30.0)
            self.assertTrue(self.widget._para1_check.isChecked())
            self.assertFalse(self.widget._r1_input.isEnabled())
            self.assertEqual(self.widget._para1_sag_input.value(), 8.0)
            self.widget._on_interactive_property_changed("r1", 5.0)
            self.assertEqual(self.widget._lens.radius_of_curvature_1, 100.0)

        def test_uncheck_parabolic_zeroes_sag(self):
            """Unchecking a parabolic surface resets its sag to zero."""
            self._load(lock=True)
            self.widget._para1_check.setChecked(True)
            self.widget._para1_sag_input.setValue(3.0)
            self.assertEqual(self.widget._lens.parabolic_sag_1, 3.0)
            self.widget._para1_check.setChecked(False)
            self.assertEqual(self.widget._lens.parabolic_sag_1, 0.0)
            self.assertEqual(self.widget._para1_sag_input.value(), 0.0)
            self.assertFalse(self.widget._lens.is_parabolic_1)

    class TestOutlineRenderingSmoke(unittest.TestCase):
        """Every 2D renderer draws every geometry without crashing."""

        def _battery(self):
            """Geometries incl. former NaN cases (plano/inf, overhang)."""
            return [
                Lens(
                    radius_of_curvature_1=100.0,
                    radius_of_curvature_2=-100.0,
                    thickness=5.0,
                    diameter=40.0,
                ),
                Lens(
                    radius_of_curvature_1=100.0,
                    radius_of_curvature_2=float("inf"),
                    thickness=5.0,
                    diameter=40.0,
                ),
                Lens(
                    radius_of_curvature_1=86.63,
                    radius_of_curvature_2=-109.97,
                    thickness=5.0,
                    diameter=50.0,
                ),
                Lens(
                    radius_of_curvature_1=100.0,
                    radius_of_curvature_2=-100.0,
                    thickness=5.0,
                    diameter=40.0,
                    is_parabolic_1=True,
                    parabolic_sag_1=2.0,
                ),
            ]

        def _grab(self, widget):
            """Show, paint offscreen, and assert something was drawn."""
            widget.resize(400, 300)
            widget.show()
            QApplication.processEvents()
            pixmap = widget.grab()
            self.assertFalse(pixmap.isNull())
            widget.close()

        def test_editor_viz_renders(self):
            """Lens editor 2D view renders the whole battery."""
            from src.gui.widgets.lens_viz_2d import LensViz2DWidget

            for lens in self._battery():
                widget = LensViz2DWidget()
                widget.update_lens(lens)
                self._grab(widget)

        def test_parabolic_hides_radius_handles(self):
            """No r1/r2 drag handles while the surface is parabolic."""
            from src.gui.widgets.lens_viz_2d import LensViz2DWidget

            widget = LensViz2DWidget()
            widget.resize(400, 300)
            widget.update_lens(
                Lens(
                    radius_of_curvature_1=100.0,
                    radius_of_curvature_2=-100.0,
                    thickness=5.0,
                    diameter=40.0,
                    is_parabolic_1=True,
                    parabolic_sag_1=2.0,
                )
            )
            widget.show()
            QApplication.processEvents()
            widget.grab()
            self.assertNotIn("r1", widget._handles)
            self.assertIn("r2", widget._handles)
            self.assertIn("thickness", widget._handles)
            self.assertIn("diameter", widget._handles)
            widget.close()

        def test_simulation_viz_renders(self):
            """Simulation view renders single lenses and systems."""
            from src.gui.widgets.simulation_viz import SimulationVisualizationWidget

            for lens in self._battery():
                widget = SimulationVisualizationWidget()
                widget.run_simulation(lens, num_rays=3)
                self._grab(widget)

            system = OpticalSystem(name="Smoke System")
            for lens in self._battery():
                system.add_lens(lens, air_gap_before=5.0)
            widget = SimulationVisualizationWidget()
            widget.run_simulation(system, num_rays=3)
            self._grab(widget)

        def test_assembly_viz_renders(self):
            """Assembly view renders a mixed system."""
            from src.gui.widgets.assembly_viz import AssemblyVisualizationWidget

            system = OpticalSystem(name="Smoke System")
            for lens in self._battery():
                system.add_lens(lens, air_gap_before=5.0)
            widget = AssemblyVisualizationWidget()
            widget.update_system(system)
            self._grab(widget)

    class TestDatabaseRoundTrip(unittest.TestCase):
        """Spinbox edits must reach the SQLite database."""

        def setUp(self):
            """Window wired to a hermetic temp database.

            Startup already creates the default lens synchronously; the
            deferred library load is left to fire (or not) on its own so
            the adoption guard is exercised the way production hits it.
            """
            from src.gui.storage import LensStorage

            self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
            self.window = OpenLensWindow()
            self.window._storage = LensStorage(self.temp_db)
            self.window._db_path = self.temp_db

        def tearDown(self):
            """Close the window and remove the temp database."""
            self.window.close()
            if os.path.exists(self.temp_db):
                os.remove(self.temp_db)
            for ext in ["-shm", "-wal"]:
                if os.path.exists(self.temp_db + ext):
                    os.remove(self.temp_db + ext)

        def _rows_for(self, lens_id):
            """Fresh-read rows for one lens id from the temp database."""
            from src.gui.storage import LensStorage

            return [x for x in LensStorage(self.temp_db).load_lenses() if x.id == lens_id]

        def test_deferred_load_adopts_working_lens(self):
            """Firing the deferred library load must not orphan the editor.

            Regression: the startup default was wiped from the library list
            while the editor still showed it, so edits never reached the DB.
            """
            QApplication.processEvents()  # fires singleShot _load_from_database
            lens = self.window._current_lens
            self.assertIsNotNone(lens)
            self.assertIn(lens.id, [x.id for x in self.window._lenses])
            self.window._lens_editor._r1_input.setValue(60.0)
            rows = self._rows_for(lens.id)
            self.assertEqual(len(rows), 1)
            self.assertAlmostEqual(rows[0].radius_of_curvature_1, 60.0)

        def test_spinbox_edit_persists(self):
            """Editing radius/diameter writes through to the database row."""
            lens = self.window._current_lens
            self.window._lens_editor._r1_input.setValue(60.0)
            self.window._lens_editor._diameter_input.setValue(30.0)

            rows = self._rows_for(lens.id)
            self.assertEqual(len(rows), 1)
            self.assertAlmostEqual(rows[0].radius_of_curvature_1, 60.0)
            self.assertAlmostEqual(rows[0].diameter, 30.0)
            # Edge-lock compensation in the model reaches the row too.
            self.assertAlmostEqual(rows[0].thickness, lens.thickness)

        def test_repeated_edits_upsert_same_row(self):
            """Two edits update one row instead of inserting duplicates."""
            lens = self.window._current_lens
            self.window._lens_editor._r1_input.setValue(60.0)
            self.window._lens_editor._r1_input.setValue(80.0)
            QApplication.processEvents()

            rows = self._rows_for(lens.id)
            self.assertEqual(len(rows), 1)
            self.assertAlmostEqual(rows[0].radius_of_curvature_1, 80.0)

        def test_modified_at_bumps_on_edit(self):
            """The persisted modified stamp advances past construction time."""
            import datetime

            lens = self.window._current_lens
            before = lens.modified_at
            self.window._lens_editor._thickness_input.setValue(6.0)
            QApplication.processEvents()

            self.assertNotEqual(lens.modified_at, before)
            datetime.datetime.fromisoformat(lens.modified_at)
            rows = self._rows_for(lens.id)
            self.assertEqual(rows[0].modified_at, lens.modified_at)

    class TestOptimizationCollection(unittest.TestCase):
        """Variable collection is crash-free and flag-aware."""

        def setUp(self):
            """Standalone optimization tab (no parent refresh needed)."""
            from src.gui.tabs.optimization_tab import OptimizationTab

            self.tab = OptimizationTab()

        def _box(self, checked=True):
            """Real checkbox mimicking a refresh-built entry."""
            from PySide6.QtWidgets import QCheckBox

            box = QCheckBox()
            box.setChecked(checked)
            return box

        def _lens(self, **kwargs):
            """Spherical singlet with sane defaults."""
            params = {
                "radius_of_curvature_1": 100.0,
                "radius_of_curvature_2": -100.0,
                "thickness": 5.0,
                "diameter": 40.0,
                "refractive_index": 1.5168,
            }
            params.update(kwargs)
            return Lens(**params)

        def test_refresh_builds_exclusive_keys(self):
            """Refresh emits exactly one of ps/r per surface, matching flags."""
            import types

            lens = self._lens(is_parabolic_1=True, parabolic_sag_1=2.0)
            self.tab._parent = types.SimpleNamespace(_current_lens=lens, _current_assembly=None)
            self.tab.refresh()
            keys = set(self.tab._opt_check_vars)
            self.assertIn("ps1_0", keys)
            self.assertNotIn("r1_0", keys)
            self.assertIn("r2_0", keys)
            self.assertNotIn("ps2_0", keys)

        def test_key_builder(self):
            """Single format site produces the legacy key strings."""
            from src.gui.tabs.optimization_tab import OptVarKey

            self.assertEqual(OptVarKey.SAG1.at(2), "ps1_2")
            self.assertEqual(OptVarKey.R1.at(0), "r1_0")
            self.assertEqual(OptVarKey.THICKNESS.at(1), "th_1")
            self.assertEqual(OptVarKey.GAP.at(0), "gap_0")
            self.assertEqual(OptVarKey.DIAMETER.at(0), "d_0")

        def test_collect_before_refresh_returns_empty(self):
            """Run-before-refresh yields no variables, not a crash."""
            lens = self._lens()
            self.assertEqual(self.tab._collect_variables(lens), [])
            system = OpticalSystem(name="Empty System")
            system.add_lens(lens)
            self.assertEqual(self.tab._collect_variables(system), [])

        def test_stale_radius_key_skipped_when_parabolic(self):
            """Checked r1 box + parabolic flag must not make a radius var."""
            lens = self._lens(is_parabolic_1=True, parabolic_sag_1=2.0)
            self.tab._opt_check_vars = {
                "r1_0": self._box(True),
                "th_0": self._box(False),
            }
            params = [v.parameter for v in self.tab._collect_variables(lens)]
            self.assertNotIn("radius_of_curvature_1", params)
            self.assertNotIn("parabolic_sag_1", params)

        def test_stale_sag_key_skipped_when_spherical(self):
            """Checked ps1 box + spherical flag must not latch parabolic."""
            lens = self._lens()
            self.tab._opt_check_vars = {
                "ps1_0": self._box(True),
                "r1_0": self._box(False),
            }
            params = [v.parameter for v in self.tab._collect_variables(lens)]
            self.assertNotIn("parabolic_sag_1", params)
            self.assertNotIn("radius_of_curvature_1", params)

        def test_fresh_keys_collected_with_live_values(self):
            """Fresh panel collects radius/thickness with current values."""
            lens = self._lens()
            self.tab._opt_check_vars = {
                "r1_0": self._box(True),
                "th_0": self._box(True),
            }
            by_param = {v.parameter: v for v in self.tab._collect_variables(lens)}
            self.assertEqual(by_param["radius_of_curvature_1"].current_value, 100.0)
            self.assertEqual(by_param["thickness"].current_value, 5.0)

        def test_system_sag_bounds_scaled(self):
            """System sag variables use diameter-scaled bounds."""
            lens = self._lens(diameter=200.0, is_parabolic_1=True, parabolic_sag_1=2.0)
            system = OpticalSystem(name="Wide System")
            system.add_lens(lens)
            self.tab._opt_check_vars = {"ps1_0": self._box(True)}
            variables = self.tab._collect_variables(system)
            self.assertEqual(len(variables), 1)
            self.assertEqual(variables[0].parameter, "parabolic_sag_1")
            self.assertEqual(variables[0].min_value, -100.0)
            self.assertEqual(variables[0].max_value, 100.0)

    def run_gui_tests():
        """Run all GUI tests and return results"""
        loader = unittest.TestLoader()
        suite = unittest.TestSuite()
        suite.addTests(loader.loadTestsFromTestCase(TestOpenLensGUI))
        suite.addTests(loader.loadTestsFromTestCase(TestLensEditorWidget))
        suite.addTests(loader.loadTestsFromTestCase(TestOutlineRenderingSmoke))
        suite.addTests(loader.loadTestsFromTestCase(TestDatabaseRoundTrip))
        suite.addTests(loader.loadTestsFromTestCase(TestOptimizationCollection))
        runner = unittest.TextTestRunner(verbosity=2)
        return runner.run(suite)


if __name__ == "__main__":
    unittest.main()
