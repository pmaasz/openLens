#!/usr/bin/env python3
"""
Refactored GUI functional tests for OpenLens using PySide6 and QtTest.
"""

import unittest
import sys
import os
import tempfile
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from PySide6.QtCore import Qt

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from openlens import OpenLensWindow
from src.lens import Lens
from src.optical_system import OpticalSystem

# Ensure a QApplication instance exists
app = QApplication.instance()
if not app:
    app = QApplication(sys.argv)

class TestOpenLensGUI(unittest.TestCase):
    """Test cases for the PySide6 OpenLens GUI"""

    def setUp(self):
        """Set up test fixtures"""
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False).name
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
        for ext in ['-shm', '-wal']:
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
        self.window._on_new_lens() # Lens 2
        self.window._on_new_lens() # Lens 3
        
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
        self.window._editor_tabs.setCurrentIndex(2) # Simulation tab
        QApplication.processEvents()
        
        viz = self.window._sim_tab._sim_viz
        # Force a simulation run with direct params if the UI bound one is failing in headless
        active_system = self.window._current_assembly if self.window._current_assembly else self.window._current_lens
        viz.run_simulation(active_system, num_rays=5)
        self.assertGreater(len(viz._rays), 0)

def run_gui_tests():
    """Run all GUI tests and return results"""
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestOpenLensGUI)
    runner = unittest.TextTestRunner(verbosity=2)
    return runner.run(suite)

if __name__ == "__main__":
    unittest.main()
