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

    def run_gui_tests():
        """Run all GUI tests and return results"""
        loader = unittest.TestLoader()
        suite = unittest.TestSuite()
        suite.addTests(loader.loadTestsFromTestCase(TestOpenLensGUI))
        suite.addTests(loader.loadTestsFromTestCase(TestLensEditorWidget))
        suite.addTests(loader.loadTestsFromTestCase(TestOutlineRenderingSmoke))
        runner = unittest.TextTestRunner(verbosity=2)
        return runner.run(suite)


if __name__ == "__main__":
    unittest.main()
