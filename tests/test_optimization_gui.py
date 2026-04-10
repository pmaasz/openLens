
import unittest
import tkinter as tk
from tkinter import ttk
from src.gui.main_window import LensEditorWindow
from src.lens import Lens
from src.optical_system import OpticalSystem

class TestOptimizationIntegration(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        # Headless mock/stubbing if needed, but here we just check logic
        self.app = LensEditorWindow(self.root)
        
    def tearDown(self):
        self.root.destroy()

    def test_optimization_tab_exists(self):
        """Verify the optimization tab is created in the notebook."""
        tabs = [self.app.notebook.tab(i, "text") for i in range(self.app.notebook.index("end"))]
        self.assertIn("Optimization", tabs)

    def test_optimization_controller_initialized(self):
        """Verify OptimizationController is initialized and assigned to the tab."""
        self.assertIsNotNone(self.app.optimization_controller)
        self.assertEqual(self.app.optimization_controller.parent_window, self.app)

    def test_select_lens_enables_optimization_tab(self):
        """Verify that selecting a lens enables the optimization tab."""
        # Initially disabled
        idx = self._get_tab_index("Optimization")
        self.assertEqual(self.app.notebook.tab(idx, "state"), "disabled")
        
        # Create a dummy lens
        lens = Lens(
            name="Test Lens", 
            radius_of_curvature_1=100.0, 
            radius_of_curvature_2=-100.0, 
            thickness=10.0
        )
        self.app.on_lens_selected_callback(lens)
        
        # Now should be normal
        self.assertEqual(self.app.notebook.tab(idx, "state"), "normal")
        self.assertEqual(self.app.optimization_controller.current_lens, lens)

    def test_select_system_enables_optimization_tab(self):
        """Verify that selecting an optical system enables the optimization tab."""
        system = OpticalSystem(name="Test System")
        self.app.on_lens_selected_callback(system)
        
        idx = self._get_tab_index("Optimization")
        self.assertEqual(self.app.notebook.tab(idx, "state"), "normal")
        self.assertEqual(self.app.optimization_controller.current_lens, system)

    def test_optimization_run_flow(self):
        """Verify the full optimization flow: Load -> Run -> Apply."""
        lens = Lens(
            name="Optimize Test", 
            radius_of_curvature_1=100.0, 
            radius_of_curvature_2=-100.0, 
            thickness=5.0
        )
        self.app.on_lens_selected_callback(lens)
        
        ctrl = self.app.optimization_controller
        self.assertEqual(ctrl.current_lens, lens)
        
        # Configure a target focal length of 50mm (currently ~100mm)
        ctrl.target_vars['focal_length_enabled'].set(True)
        ctrl.target_vars['focal_length_value'].set(50.0)
        
        # Select variables
        ctrl.variable_vars['radius_of_curvature_1_0'].set(True)
        ctrl.variable_vars['radius_of_curvature_2_0'].set(True)
        
        # Run optimization synchronously for testing
        # We'll bypass the thread by calling the worker directly or mocking it
        # However, it uses root.after(0, ...) so we need to process events
        import threading
        original_thread = threading.Thread
        
        # Simple mock to run synchronously
        class MockThread:
            def __init__(self, target, args=(), kwargs={}, daemon=False):
                self.target = target
                self.args = args
            def start(self):
                self.target(*self.args)
        
        threading.Thread = MockThread
        try:
            # First, check the initial focal length
            initial_fl = lens.calculate_focal_length()
            self.assertIsNotNone(initial_fl)
            
            # Setup optimization
            ctrl.target_vars['focal_length_enabled'].set(True)
            ctrl.target_vars['focal_length_value'].set(50.0)
            
            # R1 and R2 both variable
            ctrl.variable_vars['radius_of_curvature_1_0'].set(True)
            ctrl.variable_vars['radius_of_curvature_2_0'].set(True)
            
            # Mock apply_results to capture result
            applied_results = []
            original_apply = ctrl._apply_results
            ctrl._apply_results = lambda res: applied_results.append(res) or original_apply(res)
            
            # Run optimization
            ctrl.run_optimization()
            self.root.update()
            
            # Verify result
            self.assertTrue(len(applied_results) > 0)
            res = applied_results[0]
            self.assertTrue(res.success)
            
            new_fl = res.optimized_system.calculate_focal_length()
            # Merit should have improved
            self.assertLess(res.final_merit, res.initial_merit)
            # Focal length should be closer to 50.0
            self.assertLess(abs(new_fl - 50.0), abs(initial_fl - 50.0))
            
            # Actually apply
            ctrl._confirm_apply()
            # Should have updated the current lens in main window
            self.assertAlmostEqual(self.app.current_lens.calculate_focal_length(), new_fl)
            
        finally:
            threading.Thread = original_thread

    def test_assembly_optimization_flow(self):
        """Verify optimization flow for multi-element assemblies."""
        system = OpticalSystem(name="Triplet")
        l1 = Lens(name="L1", radius_of_curvature_1=50, radius_of_curvature_2=-50, thickness=5)
        l2 = Lens(name="L2", radius_of_curvature_1=-50, radius_of_curvature_2=50, thickness=3)
        l3 = Lens(name="L3", radius_of_curvature_1=50, radius_of_curvature_2=-50, thickness=5)
        
        system.add_lens(l1)
        system.add_lens(l2, air_gap_before=2.0)
        system.add_lens(l3, air_gap_before=2.0)
        
        self.app.on_lens_selected_callback(system)
        ctrl = self.app.optimization_controller
        
        # Verify variables list populated for assembly
        self.assertIn('r1_0', ctrl.variable_vars)
        self.assertIn('r2_1', ctrl.variable_vars)
        self.assertIn('gap_0', ctrl.variable_vars)
        
        # Target focal length
        initial_fl = system.get_system_focal_length()
        ctrl.target_vars['focal_length_enabled'].set(True)
        ctrl.target_vars['focal_length_value'].set(100.0)
        
        # Variables: R1 of first lens and first air gap
        ctrl.variable_vars['r1_0'].set(True)
        ctrl.variable_vars['gap_0'].set(True)
        
        import threading
        original_thread = threading.Thread
        class MockThread:
            def __init__(self, target, args=(), kwargs={}, daemon=False):
                self.target = target
                self.args = args
            def start(self):
                self.target(*self.args)
        
        threading.Thread = MockThread
        try:
            # Capture initial merit if possible or just check that result is success
            ctrl.run_optimization()
            self.root.update()
            
            self.assertIsNotNone(ctrl.temp_optimized_lens)
            
            # Apply
            ctrl._confirm_apply()
            # Verify that the main window's current_lens was updated
            self.assertEqual(self.app.current_lens.name, system.name)
            # The object identity might change due to deepcopy in optimizer
            self.assertIsNotNone(self.app.current_lens)
            
        finally:
            threading.Thread = original_thread

    def _get_tab_index(self, text):
        for i in range(self.app.notebook.index("end")):
            if self.app.notebook.tab(i, "text") == text:
                return i
        return -1

if __name__ == "__main__":
    unittest.main()
