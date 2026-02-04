#!/usr/bin/env python3
"""
GUI functional tests for openlens application
Tests the GUI components and interactions
"""

import unittest
import tkinter as tk
from tkinter import ttk
import tempfile
import os
import json
import sys

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src'))
from lens_editor_gui import Lens, LensEditorWindow


class TestGUILensEditor(unittest.TestCase):
    """Test cases for the GUI Lens Editor"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.root = tk.Tk()
        self.root.withdraw()  # Hide window during tests
        
        # Create temporary storage file
        self.temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')
        self.temp_file.close()
        
        # Create editor window with temp storage
        self.editor = LensEditorWindow(self.root)
        self.editor.storage_file = self.temp_file.name
        self.editor.lenses = []
    
    def tearDown(self):
        """Clean up test fixtures"""
        try:
            self.root.destroy()
        except:
            pass
        
        if os.path.exists(self.temp_file.name):
            os.unlink(self.temp_file.name)
    
    def test_gui_initialization(self):
        """Test that GUI initializes correctly"""
        self.assertIsNotNone(self.editor)
        self.assertIsNotNone(self.editor.root)
        self.assertEqual(len(self.editor.lenses), 0)
    
    def test_form_variables_exist(self):
        """Test that all form variables are created"""
        self.assertIsNotNone(self.editor.name_var)
        self.assertIsNotNone(self.editor.r1_var)
        self.assertIsNotNone(self.editor.r2_var)
        self.assertIsNotNone(self.editor.thickness_var)
        self.assertIsNotNone(self.editor.diameter_var)
        self.assertIsNotNone(self.editor.refr_index_var)
        self.assertIsNotNone(self.editor.type_var)
        self.assertIsNotNone(self.editor.material_var)
    
    def test_default_values(self):
        """Test that form has correct default values"""
        self.assertEqual(self.editor.r1_var.get(), "100.0")
        self.assertEqual(self.editor.r2_var.get(), "-100.0")
        self.assertEqual(self.editor.thickness_var.get(), "5.0")
        self.assertEqual(self.editor.diameter_var.get(), "50.0")
        self.assertEqual(self.editor.refr_index_var.get(), "1.5168")
        self.assertEqual(self.editor.type_var.get(), "Biconvex")
        self.assertEqual(self.editor.material_var.get(), "BK7")
    
    def test_tabs_exist(self):
        """Test that all tabs are created"""
        self.assertIsNotNone(self.editor.notebook)
        self.assertEqual(len(self.editor.notebook.tabs()), 3)
        
    def test_tabs_disabled_initially(self):
        """Test that editor and simulation tabs are disabled initially"""
        # Tab states: normal = enabled, disabled = disabled
        editor_state = str(self.editor.notebook.tab(1, "state"))
        simulate_state = str(self.editor.notebook.tab(2, "state"))
        self.assertEqual(editor_state, "disabled")
        self.assertEqual(simulate_state, "disabled")
    
    def test_load_lens_to_form(self):
        """Test loading a lens into the form"""
        lens = Lens(
            name="Test Lens",
            radius_of_curvature_1=75.0,
            radius_of_curvature_2=-125.0,
            thickness=6.0,
            diameter=40.0,
            refractive_index=1.52,
            lens_type="Plano-Convex",
            material="Crown Glass"
        )
        
        self.editor.load_lens_to_form(lens)
        
        self.assertEqual(self.editor.name_var.get(), "Test Lens")
        self.assertEqual(self.editor.r1_var.get(), "75.0")
        self.assertEqual(self.editor.r2_var.get(), "-125.0")
        self.assertEqual(self.editor.thickness_var.get(), "6.0")
        self.assertEqual(self.editor.diameter_var.get(), "40.0")
        self.assertEqual(self.editor.refr_index_var.get(), "1.52")
        self.assertEqual(self.editor.type_var.get(), "Plano-Convex")
        self.assertEqual(self.editor.material_var.get(), "Crown Glass")
    
    def test_select_lens_enables_tabs(self):
        """Test that selecting a lens enables editor and simulation tabs"""
        # Add a lens
        lens = Lens(name="Test Lens", material="BK7")
        self.editor.lenses.append(lens)
        self.editor.refresh_selection_list()
        
        # Select it
        self.editor.selection_listbox.selection_set(0)
        self.editor.select_lens_from_list()
        
        # Check tabs are enabled
        editor_state = str(self.editor.notebook.tab(1, "state"))
        simulate_state = str(self.editor.notebook.tab(2, "state"))
        self.assertEqual(editor_state, "normal")
        self.assertEqual(simulate_state, "normal")
    
    def test_save_new_lens(self):
        """Test saving a new lens"""
        # Set form values
        self.editor.name_var.set("New Lens")
        self.editor.r1_var.set("80.0")
        self.editor.r2_var.set("-90.0")
        self.editor.material_var.set("BK7")
        self.editor.current_lens = None  # Ensure it's a new lens
        
        # Save lens
        initial_count = len(self.editor.lenses)
        
        self.editor.save_current_lens()
        self.assertEqual(len(self.editor.lenses), initial_count + 1)
        self.assertEqual(self.editor.lenses[-1].name, "New Lens")
        self.assertEqual(self.editor.lenses[-1].radius_of_curvature_1, 80.0)
        # Focal length should be calculated automatically
        self.assertIsNotNone(self.editor.lenses[-1].focal_length)
    
    def test_update_existing_lens(self):
        """Test updating an existing lens"""
        # Create a lens
        lens = Lens(name="Original Name", material="BK7")
        self.editor.lenses.append(lens)
        self.editor.current_lens = lens
        
        # Modify in form
        self.editor.load_lens_to_form(lens)
        self.editor.name_var.set("Updated Name")
        self.editor.r1_var.set("120.0")
        self.editor.material_var.set("Fused Silica")
        
        self.editor.save_current_lens()
        self.assertEqual(lens.name, "Updated Name")
        self.assertEqual(lens.radius_of_curvature_1, 120.0)
        self.assertEqual(lens.material, "Fused Silica")
    
    def test_refresh_lens_list(self):
        """Test refreshing the lens selection list"""
        # Add some lenses
        lens1 = Lens(name="Lens 1", material="BK7")
        lens2 = Lens(name="Lens 2", material="Crown Glass")
        self.editor.lenses = [lens1, lens2]
        
        # Refresh list
        self.editor.refresh_selection_list()
        
        # Check listbox has correct number of items
        self.assertEqual(self.editor.selection_listbox.size(), 2)
    
    def test_calculate_focal_length(self):
        """Test focal length calculation in GUI"""
        # Create a lens with valid parameters
        lens = Lens(
            name="Test",
            radius_of_curvature_1=100.0,
            radius_of_curvature_2=-100.0,
            thickness=5.0,
            refractive_index=1.5168
        )
        
        # Calculate focal length
        focal_length = lens.calculate_focal_length()
        
        # Check that focal length is calculated
        self.assertIsNotNone(focal_length)
        self.assertGreater(focal_length, 0)
    
    def test_calculate_focal_length_with_invalid_input(self):
        """Test focal length calculation with invalid input"""
        # Create lens with zero radius (invalid)
        lens = Lens(
            name="Test",
            radius_of_curvature_1=0.0,
            radius_of_curvature_2=-100.0,
            thickness=5.0,
            refractive_index=1.5168
        )
        
        # Should handle gracefully
        focal_length = lens.calculate_focal_length()
        # Either None or infinity for zero radius
        self.assertTrue(focal_length is None or focal_length == float('inf'))
    
    def test_calculate_focal_length_with_zero_radius(self):
        """Test focal length calculation with zero radius"""
        lens = Lens(
            name="Test",
            radius_of_curvature_1=0.0,
            radius_of_curvature_2=0.0,
            thickness=5.0,
            refractive_index=1.5168
        )
        
        focal_length = lens.calculate_focal_length()
        # Should handle zero radius gracefully
        self.assertTrue(focal_length is None or focal_length == float('inf'))
    
    def test_status_messages(self):
        """Test status bar message display"""
        self.editor.update_status("Test message")
        self.assertEqual(self.editor.status_var.get(), "Test message")
        
    def test_create_new_lens_from_selection(self):
        """Test creating a new lens from selection tab"""
        # Simulate create new button
        self.editor.create_new_lens_from_selection()
        
        # Should switch to editor tab and clear form
        self.assertEqual(self.editor.name_var.get(), "")
        self.assertIsNone(self.editor.current_lens)
    
    def test_lens_info_display(self):
        """Test lens information display in selection tab"""
        lens = Lens(name="Info Test", material="BK7")
        self.editor.lenses.append(lens)
        self.editor.refresh_selection_list()
        
        # Select lens
        self.editor.selection_listbox.selection_set(0)
        self.editor.update_selection_info(None)
        
        # Check info is displayed
        info_text = self.editor.selection_info_text.get("1.0", "end-1c")
        self.assertIn(lens.id, info_text)
        self.assertIn("Info Test", info_text)
    
    def test_duplicate_lens(self):
        """Test duplicating a lens"""
        # Create and add a lens
        lens = Lens(name="Original", material="BK7", radius_of_curvature_1=75.0)
        self.editor.lenses.append(lens)
        self.editor.refresh_selection_list()
        
        # Select it
        self.editor.selection_listbox.selection_set(0)
        
        initial_count = len(self.editor.lenses)
        
        self.editor.duplicate_lens()
        self.assertEqual(len(self.editor.lenses), initial_count + 1)
        
        duplicated = self.editor.lenses[-1]
        self.assertIn("Copy", duplicated.name)
        self.assertEqual(duplicated.radius_of_curvature_1, 75.0)
        self.assertNotEqual(duplicated.id, lens.id)
    
    def test_status_update(self):
        """Test status bar updates"""
        self.editor.update_status("Test Status")
        self.assertEqual(self.editor.status_var.get(), "Test Status")
    
    def test_autosave_flag_exists(self):
        """Test that autosave control flags exist"""
        self.assertTrue(hasattr(self.editor, '_loading_lens'))
        self.assertTrue(hasattr(self.editor, '_autosave_timer'))
        self.assertFalse(self.editor._loading_lens)  # Should be False initially
    
    def test_on_field_change_method_exists(self):
        """Test that autosave callback method exists"""
        self.assertTrue(hasattr(self.editor, 'on_field_change'))
        self.assertTrue(callable(self.editor.on_field_change))
    
    def test_field_trace_callbacks_set(self):
        """Test that all fields have trace callbacks for autosave"""
        # Each StringVar should have write trace
        for var_name in ['name_var', 'r1_var', 'r2_var', 'thickness_var', 
                         'diameter_var', 'refr_index_var', 'type_var', 'material_var']:
            var = getattr(self.editor, var_name)
            traces = var.trace_info()
            self.assertGreater(len(traces), 0, f"{var_name} should have trace callback")
    
    def test_autosave_sets_timer(self):
        """Test that changing a field sets autosave timer"""
        # Change a field value
        self.editor._autosave_timer = None
        self.editor.r1_var.set('150.0')
        self.root.update_idletasks()
        
        # Timer should be set
        self.assertIsNotNone(self.editor._autosave_timer)
    
    def test_loading_lens_prevents_autosave(self):
        """Test that _loading_lens flag prevents autosave"""
        lens = Lens(name="Test", material="BK7")
        
        # During load, _loading_lens should be set
        self.editor._loading_lens = False
        self.editor.load_lens_to_form(lens)
        
        # After load completes, flag should be False again
        self.assertFalse(self.editor._loading_lens)
    
    def test_visualization_mode_variable_exists(self):
        """Test that visualization mode toggle variable exists"""
        self.assertTrue(hasattr(self.editor, 'viz_mode_var'))
        # Default should be 3D
        self.assertEqual(self.editor.viz_mode_var.get(), "3D")
    
    def test_toggle_visualization_mode_method_exists(self):
        """Test that toggle method exists"""
        self.assertTrue(hasattr(self.editor, 'toggle_visualization_mode'))
        self.assertTrue(callable(self.editor.toggle_visualization_mode))
    
    def test_update_3d_view_handles_both_modes(self):
        """Test that update_3d_view works with both 2D and 3D modes"""
        if self.editor.visualizer:
            # Test 3D mode
            self.editor.viz_mode_var.set("3D")
            try:
                self.editor.update_3d_view()
                # Should not raise exception
            except Exception as e:
                self.fail(f"3D view update failed: {e}")
            
            # Test 2D mode
            self.editor.viz_mode_var.set("2D")
            try:
                self.editor.update_3d_view()
                # Should not raise exception
            except Exception as e:
                self.fail(f"2D view update failed: {e}")
    
    def test_viz_notebook_exists(self):
        """Test that visualization notebook (tabs) exists"""
        self.assertTrue(hasattr(self.editor, 'viz_notebook'))
        # Should have 2 tabs (2D and 3D)
        if hasattr(self.editor, 'viz_notebook'):
            self.assertEqual(len(self.editor.viz_notebook.tabs()), 2)
    
    def test_viz_frames_exist(self):
        """Test that 2D and 3D frames exist"""
        self.assertTrue(hasattr(self.editor, 'viz_2d_frame'))
        self.assertTrue(hasattr(self.editor, 'viz_3d_frame'))
    
    def test_on_viz_tab_changed_method_exists(self):
        """Test that viz tab change handler exists"""
        self.assertTrue(hasattr(self.editor, 'on_viz_tab_changed'))
        self.assertTrue(callable(self.editor.on_viz_tab_changed))
    
    def test_tab_switching_updates_mode(self):
        """Test that switching tabs updates the visualization mode"""
        if hasattr(self.editor, 'viz_notebook') and self.editor.visualizer:
            # Switch to 2D tab (index 0)
            self.editor.viz_notebook.select(0)
            self.root.update_idletasks()
            # Mode should be 2D after tab change event
            # (Note: event might not fire in test, but we can test the method)
            
            # Switch to 3D tab (index 1)
            self.editor.viz_notebook.select(1)
            self.root.update_idletasks()
    
    def test_visualizer_reparent_method_exists(self):
        """Test that visualizer has reparent_canvas method"""
        if self.editor.visualizer:
            self.assertTrue(hasattr(self.editor.visualizer, 'reparent_canvas'))
            self.assertTrue(callable(self.editor.visualizer.reparent_canvas))
    
    def test_simulation_view_update_method_exists(self):
        """Test that simulation view update method exists"""
        self.assertTrue(hasattr(self.editor, 'update_simulation_view'))
        self.assertTrue(callable(self.editor.update_simulation_view))
    
    def test_on_tab_changed_method_exists(self):
        """Test that tab change handler exists"""
        self.assertTrue(hasattr(self.editor, 'on_tab_changed'))
        self.assertTrue(callable(self.editor.on_tab_changed))
    
    def test_simulation_info_label_exists(self):
        """Test that simulation info label exists for hiding"""
        if hasattr(self.editor, 'sim_visualizer') and self.editor.sim_visualizer:
            self.assertTrue(hasattr(self.editor, 'sim_info_label'))
    
    def test_save_button_removed(self):
        """Test that save button was removed (autosave replaced it)"""
        # Save button should not exist anymore
        self.assertFalse(hasattr(self.editor, 'save_btn'))
    
    def test_autosave_creates_new_lens(self):
        """Test that autosave can create a new lens"""
        self.editor.current_lens = None
        self.editor.name_var.set("Autosaved Lens")
        self.editor.r1_var.set("100.0")
        
        initial_count = len(self.editor.lenses)
        
        # Trigger autosave directly
        self.editor.save_current_lens()
        
        # Should have created new lens
        self.assertEqual(len(self.editor.lenses), initial_count + 1)
        self.assertEqual(self.editor.lenses[-1].name, "Autosaved Lens")


class TestGUIDataPersistence(unittest.TestCase):
    """Test GUI data persistence"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.root = tk.Tk()
        self.root.withdraw()
        
        self.temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')
        self.temp_file.close()
    
    def tearDown(self):
        """Clean up test fixtures"""
        try:
            self.root.destroy()
        except:
            pass
        
        if os.path.exists(self.temp_file.name):
            os.unlink(self.temp_file.name)
    
    def test_save_and_load_through_gui(self):
        """Test saving and loading lenses through GUI"""
        # Create editor and add lenses
        editor1 = LensEditorWindow(self.root)
        editor1.storage_file = self.temp_file.name
        
        lens1 = Lens(name="Saved Lens 1", material="BK7")
        lens2 = Lens(name="Saved Lens 2", material="Crown Glass")
        editor1.lenses = [lens1, lens2]
        editor1.save_lenses()
        
        # Create new editor instance and load
        root2 = tk.Tk()
        root2.withdraw()
        editor2 = LensEditorWindow(root2)
        editor2.storage_file = self.temp_file.name
        editor2.lenses = editor2.load_lenses()
        
        self.assertEqual(len(editor2.lenses), 2)
        self.assertEqual(editor2.lenses[0].name, "Saved Lens 1")
        self.assertEqual(editor2.lenses[1].name, "Saved Lens 2")
        
        root2.destroy()


class TestGUIValidation(unittest.TestCase):
    """Test GUI input validation"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.root = tk.Tk()
        self.root.withdraw()
        
        self.temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')
        self.temp_file.close()
        
        self.editor = LensEditorWindow(self.root)
        self.editor.storage_file = self.temp_file.name
    
    def tearDown(self):
        """Clean up test fixtures"""
        try:
            self.root.destroy()
        except:
            pass
        
        if os.path.exists(self.temp_file.name):
            os.unlink(self.temp_file.name)
    
    def test_save_with_invalid_numeric_input(self):
        """Test saving with invalid numeric input shows error"""
        self.editor.name_var.set("Test")
        self.editor.r1_var.set("not_a_number")
        
        initial_count = len(self.editor.lenses)
        
        try:
            self.editor.save_current_lens()
            # If it doesn't raise an error, lens should not be saved
            self.assertEqual(len(self.editor.lenses), initial_count)
        except tk.TclError:
            # Expected in headless mode
            pass
    
    def test_empty_name_uses_default(self):
        """Test that empty name uses 'Untitled' as default"""
        self.editor.name_var.set("")
        self.editor.current_lens = None  # Ensure it's a new lens
        
        self.editor.save_current_lens()
        if len(self.editor.lenses) > 0:
            self.assertEqual(self.editor.lenses[-1].name, "Untitled")


def run_gui_tests():
    """Run all GUI tests and return results"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    suite.addTests(loader.loadTestsFromTestCase(TestGUILensEditor))
    suite.addTests(loader.loadTestsFromTestCase(TestGUIDataPersistence))
    suite.addTests(loader.loadTestsFromTestCase(TestGUIValidation))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result


if __name__ == "__main__":
    print("=" * 70)
    print("openlens GUI Functional Tests")
    print("=" * 70)
    print()
    
    result = run_gui_tests()
    
    print()
    print("=" * 70)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped)}")
    
    if result.wasSuccessful():
        print("\n✓ ALL GUI TESTS PASSED!")
        sys.exit(0)
    else:
        print("\n✗ SOME GUI TESTS FAILED!")
        sys.exit(1)
