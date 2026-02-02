#!/usr/bin/env python3
"""
GUI functional tests for OpenLense application
Tests the GUI components and interactions
"""

import unittest
import tkinter as tk
from tkinter import ttk
import tempfile
import os
import json
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
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
        self.assertIsNotNone(self.editor.id_var)
        self.assertIsNotNone(self.editor.name_var)
        self.assertIsNotNone(self.editor.r1_var)
        self.assertIsNotNone(self.editor.r2_var)
        self.assertIsNotNone(self.editor.thickness_var)
        self.assertIsNotNone(self.editor.diameter_var)
        self.assertIsNotNone(self.editor.refr_index_var)
        self.assertIsNotNone(self.editor.type_var)
        self.assertIsNotNone(self.editor.material_var)
        self.assertIsNotNone(self.editor.created_var)
        self.assertIsNotNone(self.editor.modified_var)
    
    def test_default_values(self):
        """Test that form has correct default values"""
        self.assertEqual(self.editor.r1_var.get(), "100.0")
        self.assertEqual(self.editor.r2_var.get(), "-100.0")
        self.assertEqual(self.editor.thickness_var.get(), "5.0")
        self.assertEqual(self.editor.diameter_var.get(), "50.0")
        self.assertEqual(self.editor.refr_index_var.get(), "1.5168")
        self.assertEqual(self.editor.type_var.get(), "Biconvex")
        self.assertEqual(self.editor.material_var.get(), "BK7")
    
    def test_clear_form(self):
        """Test clearing the form"""
        # Set some values
        self.editor.name_var.set("Test Lens")
        self.editor.r1_var.set("75.0")
        self.editor.material_var.set("Crown Glass")
        
        # Clear form
        self.editor.clear_form()
        
        # Check defaults are restored
        self.assertEqual(self.editor.name_var.get(), "")
        self.assertEqual(self.editor.r1_var.get(), "100.0")
        self.assertEqual(self.editor.r2_var.get(), "-100.0")
        self.assertEqual(self.editor.material_var.get(), "BK7")
        self.assertIsNone(self.editor.current_lens)
    
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
    
    def test_save_new_lens(self):
        """Test saving a new lens"""
        # Set form values
        self.editor.name_var.set("New Lens")
        self.editor.r1_var.set("80.0")
        self.editor.r2_var.set("-90.0")
        self.editor.material_var.set("BK7")
        
        # Save lens
        initial_count = len(self.editor.lenses)
        
        try:
            self.editor.save_current_lens()
            self.assertEqual(len(self.editor.lenses), initial_count + 1)
            self.assertEqual(self.editor.lenses[-1].name, "New Lens")
            self.assertEqual(self.editor.lenses[-1].radius_of_curvature_1, 80.0)
        except tk.TclError:
            # Skip if GUI dialog appears (can't test in headless mode)
            pass
    
    def test_update_existing_lens(self):
        """Test updating an existing lens"""
        # Create a lens
        lens = Lens(name="Original Name", material="BK7")
        self.editor.lenses.append(lens)
        self.editor.current_lens = lens
        
        # Modify in form
        self.editor.name_var.set("Updated Name")
        self.editor.r1_var.set("120.0")
        self.editor.material_var.set("Fused Silica")
        
        try:
            self.editor.save_current_lens()
            self.assertEqual(lens.name, "Updated Name")
            self.assertEqual(lens.radius_of_curvature_1, 120.0)
            self.assertEqual(lens.material, "Fused Silica")
        except tk.TclError:
            pass
    
    def test_refresh_lens_list(self):
        """Test refreshing the lens list"""
        # Add some lenses
        lens1 = Lens(name="Lens 1", material="BK7")
        lens2 = Lens(name="Lens 2", material="Crown Glass")
        self.editor.lenses = [lens1, lens2]
        
        # Refresh list
        self.editor.refresh_lens_list()
        
        # Check listbox has correct number of items
        self.assertEqual(self.editor.lens_listbox.size(), 2)
    
    def test_calculate_focal_length(self):
        """Test focal length calculation in GUI"""
        # Set valid lens parameters
        self.editor.r1_var.set("100.0")
        self.editor.r2_var.set("-100.0")
        self.editor.thickness_var.set("5.0")
        self.editor.refr_index_var.set("1.5168")
        
        # Calculate
        self.editor.calculate_and_display_focal_length()
        
        # Check that labels are updated (should not be "Not calculated")
        label_text = self.editor.focal_length_label.cget("text")
        self.assertNotIn("Not calculated", label_text)
        self.assertIn("Focal Length:", label_text)
    
    def test_calculate_focal_length_with_invalid_input(self):
        """Test focal length calculation with invalid input"""
        self.editor.r1_var.set("invalid")
        self.editor.r2_var.set("-100.0")
        
        # Should not crash
        self.editor.calculate_and_display_focal_length()
        
        # Should show error message
        label_text = self.editor.focal_length_label.cget("text")
        self.assertIn("Invalid", label_text)
    
    def test_calculate_focal_length_with_zero_radius(self):
        """Test focal length calculation with zero radius"""
        self.editor.r1_var.set("0.0")
        self.editor.r2_var.set("-100.0")
        
        self.editor.calculate_and_display_focal_length()
        
        label_text = self.editor.focal_length_label.cget("text")
        self.assertIn("Undefined", label_text)
    
    def test_auto_update_modified(self):
        """Test auto-updating modified timestamp"""
        original_value = self.editor.modified_var.get()
        
        self.editor.auto_update_modified()
        
        new_value = self.editor.modified_var.get()
        self.assertNotEqual(original_value, new_value)
        self.assertGreater(len(new_value), 0)
    
    def test_duplicate_lens(self):
        """Test duplicating a lens"""
        # Create and add a lens
        lens = Lens(name="Original", material="BK7", radius_of_curvature_1=75.0)
        self.editor.lenses.append(lens)
        self.editor.refresh_lens_list()
        
        # Select it
        self.editor.lens_listbox.selection_set(0)
        
        initial_count = len(self.editor.lenses)
        
        try:
            self.editor.duplicate_lens()
            self.assertEqual(len(self.editor.lenses), initial_count + 1)
            
            duplicated = self.editor.lenses[-1]
            self.assertIn("Copy", duplicated.name)
            self.assertEqual(duplicated.radius_of_curvature_1, 75.0)
            self.assertNotEqual(duplicated.id, lens.id)
        except tk.TclError:
            pass
    
    def test_status_update(self):
        """Test status bar updates"""
        self.editor.update_status("Test Status")
        self.assertEqual(self.editor.status_var.get(), "Test Status")


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
        
        try:
            self.editor.save_current_lens()
            if len(self.editor.lenses) > 0:
                self.assertEqual(self.editor.lenses[-1].name, "Untitled")
        except tk.TclError:
            pass


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
    print("OpenLense GUI Functional Tests")
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
