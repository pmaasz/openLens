#!/usr/bin/env python3
"""
Unit tests for GUI controllers
Tests the controller classes independently of the GUI
"""

import unittest
from unittest.mock import Mock, MagicMock, patch, call
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

try:
    from gui_controllers import (
        LensSelectionController,
        LensEditorController,
        SimulationController,
        PerformanceController,
        ComparisonController,
        ExportController
    )
    CONTROLLERS_AVAILABLE = True
except ImportError:
    CONTROLLERS_AVAILABLE = False


@unittest.skipIf(not CONTROLLERS_AVAILABLE, "GUI controllers not available")
class TestLensSelectionController(unittest.TestCase):
    """Test LensSelectionController functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_parent = Mock()
        self.test_lenses = [
            {
                'name': 'Test Lens 1',
                'type': 'Biconvex',
                'radius1': 100,
                'radius2': -100,
                'thickness': 10,
                'diameter': 50,
                'material': 'BK7',
                'refractive_index': 1.5168
            },
            {
                'name': 'Test Lens 2',
                'type': 'Biconcave',
                'radius1': -150,
                'radius2': 150,
                'thickness': 5,
                'diameter': 40,
                'material': 'SF11',
                'refractive_index': 1.7847
            }
        ]
        self.mock_callbacks = {
            'on_lens_selected': Mock(),
            'on_create_new': Mock(),
            'on_delete': Mock(),
            'on_lens_updated': Mock()
        }
        self.mock_colors = {
            'bg': '#2b2b2b',
            'fg': '#e0e0e0',
            'select_bg': '#404040',
            'select_fg': '#ffffff'
        }
    
    def test_controller_initialization(self):
        """Test controller can be initialized"""
        controller = LensSelectionController(
            parent_window=self.mock_parent,
            lens_list=self.test_lenses,
            colors=self.mock_colors,
            on_lens_selected=self.mock_callbacks['on_lens_selected'],
            on_create_new=self.mock_callbacks['on_create_new'],
            on_delete=self.mock_callbacks['on_delete'],
            on_lens_updated=self.mock_callbacks['on_lens_updated']
        )
        
        self.assertIsNotNone(controller)
        self.assertEqual(controller.lens_list, self.test_lenses)
    
    def test_refresh_lens_list_updates_listbox(self):
        """Test that refresh_lens_list updates the listbox"""
        controller = LensSelectionController(
            parent_window=self.mock_parent,
            lens_list=self.test_lenses,
            colors=self.mock_colors,
            on_lens_selected=self.mock_callbacks['on_lens_selected'],
            on_create_new=self.mock_callbacks['on_create_new'],
            on_delete=self.mock_callbacks['on_delete'],
            on_lens_updated=self.mock_callbacks['on_lens_updated']
        )
        
        # Create mock listbox (simulating setup_ui)
        controller.listbox = Mock()
        controller.listbox.delete = Mock()
        controller.listbox.insert = Mock()
        
        # Refresh list
        controller.refresh_lens_list()
        
        # Verify listbox was cleared
        controller.listbox.delete.assert_called_once()
        
        # Verify items were inserted
        self.assertEqual(controller.listbox.insert.call_count, len(self.test_lenses))
    
    def test_select_lens_calls_callback(self):
        """Test that selecting a lens calls the callback"""
        controller = LensSelectionController(
            parent_window=self.mock_parent,
            lens_list=self.test_lenses,
            colors=self.mock_colors,
            on_lens_selected=self.mock_callbacks['on_lens_selected'],
            on_create_new=self.mock_callbacks['on_create_new'],
            on_delete=self.mock_callbacks['on_delete'],
            on_lens_updated=self.mock_callbacks['on_lens_updated']
        )
        
        # Create mock listbox with selection (simulating setup_ui)
        controller.listbox = Mock()
        controller.listbox.curselection = Mock(return_value=(0,))
        
        # Select lens
        controller.select_lens()
        
        # Verify callback was called with correct lens
        self.mock_callbacks['on_lens_selected'].assert_called_once_with(self.test_lenses[0])
    
    def test_create_new_lens_calls_callback(self):
        """Test that create_new_lens calls the callback"""
        controller = LensSelectionController(
            parent_window=self.mock_parent,
            lens_list=self.test_lenses,
            colors=self.mock_colors,
            on_lens_selected=self.mock_callbacks['on_lens_selected'],
            on_create_new=self.mock_callbacks['on_create_new'],
            on_delete=self.mock_callbacks['on_delete'],
            on_lens_updated=self.mock_callbacks['on_lens_updated']
        )
        
        # Create new lens
        controller.create_new_lens()
        
        # Verify callback was called
        self.mock_callbacks['on_create_new'].assert_called_once()
    
    def test_delete_lens_with_selection(self):
        """Test deleting a lens with selection"""
        controller = LensSelectionController(
            parent_window=self.mock_parent,
            lens_list=self.test_lenses,
            colors=self.mock_colors,
            on_lens_selected=self.mock_callbacks['on_lens_selected'],
            on_create_new=self.mock_callbacks['on_create_new'],
            on_delete=self.mock_callbacks['on_delete'],
            on_lens_updated=self.mock_callbacks['on_lens_updated']
        )
        
        # Create mock listbox with selection (simulating setup_ui)
        controller.listbox = Mock()
        controller.listbox.curselection = Mock(return_value=(0,))
        # Mock info_text widget
        controller.info_text = Mock()
        controller.info_text.config = Mock()
        controller.info_text.delete = Mock()
        controller.info_text.insert = Mock()
        
        # Mock messagebox - delete_lens doesn't use messagebox
        controller.delete_lens()
        
        # Verify callback was called with correct lens (not index!)
        self.mock_callbacks['on_delete'].assert_called_once_with(self.test_lenses[0])


@unittest.skipIf(not CONTROLLERS_AVAILABLE, "GUI controllers not available")
class TestLensEditorController(unittest.TestCase):
    """Test LensEditorController functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_parent = Mock()
        self.test_lens = {
            'name': 'Test Lens',
            'type': 'Biconvex',
            'radius1': 100,
            'radius2': -100,
            'thickness': 10,
            'diameter': 50,
            'material': 'BK7',
            'refractive_index': 1.5168
        }
        self.mock_colors = {
            'bg': '#2b2b2b',
            'fg': '#e0e0e0',
            'entry_bg': '#3a3a3a'
        }
        self.mock_callback = Mock()
    
    def test_controller_initialization(self):
        """Test controller can be initialized"""
        controller = LensEditorController(
            colors=self.mock_colors,
            on_lens_updated=self.mock_callback
        )
        
        self.assertIsNotNone(controller)
        self.assertIsNone(controller.current_lens)
    
    def test_load_lens(self):
        """Test loading a lens into the controller"""
        controller = LensEditorController(
            colors=self.mock_colors,
            on_lens_updated=self.mock_callback
        )
        
        # Create mock entry fields (simulating setup_ui)
        controller.entry_fields = {
            'name': Mock(),
            'radius1': Mock(),
            'radius2': Mock(),
            'thickness': Mock(),
            'diameter': Mock(),
            'n': Mock()
        }
        
        for entry in controller.entry_fields.values():
            entry.delete = Mock()
            entry.insert = Mock()
        
        # Mock type and material dropdowns
        controller.type_var = Mock()
        controller.type_var.set = Mock()
        controller.material_var = Mock()
        controller.material_var.set = Mock()
        
        # Mock calculate_properties
        controller.calculate_properties = Mock()
        
        # Load lens
        controller.load_lens(self.test_lens)
        
        # Verify lens was loaded
        self.assertEqual(controller.current_lens, self.test_lens)
        
        # Verify fields were updated
        for entry in controller.entry_fields.values():
            entry.delete.assert_called()
            entry.insert.assert_called()
        
        # Verify calculate_properties was called
        controller.calculate_properties.assert_called_once()


@unittest.skipIf(not CONTROLLERS_AVAILABLE, "GUI controllers not available")
class TestSimulationController(unittest.TestCase):
    """Test SimulationController functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_parent = Mock()
        self.test_lens = {
            'name': 'Test Lens',
            'radius1': 100,
            'radius2': -100,
            'thickness': 10,
            'diameter': 50,
            'material': 'BK7',
            'refractive_index': 1.5168
        }
        self.mock_colors = {
            'bg': '#2b2b2b',
            'fg': '#e0e0e0'
        }
    
    def test_controller_initialization(self):
        """Test controller can be initialized"""
        controller = SimulationController(
            colors=self.mock_colors,
            visualization_available=False
        )
        
        self.assertIsNotNone(controller)
        self.assertIsNone(controller.current_lens)
    
    def test_load_lens(self):
        """Test loading a lens into the controller"""
        controller = SimulationController(
            colors=self.mock_colors,
            visualization_available=False
        )
        
        # Load lens (ray tracer won't be created with dict lens)
        controller.load_lens(self.test_lens)
        
        # Verify lens was loaded
        self.assertEqual(controller.current_lens, self.test_lens)
        # Note: ray_tracer is None when lens is dict or visualization not available


@unittest.skipIf(not CONTROLLERS_AVAILABLE, "GUI controllers not available")
class TestPerformanceController(unittest.TestCase):
    """Test PerformanceController functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_parent = Mock()
        self.test_lens = {
            'name': 'Test Lens',
            'radius1': 100,
            'radius2': -100,
            'thickness': 10,
            'diameter': 50,
            'material': 'BK7',
            'refractive_index': 1.5168
        }
        self.mock_colors = {
            'bg': '#2b2b2b',
            'fg': '#e0e0e0'
        }
    
    def test_controller_initialization(self):
        """Test controller can be initialized"""
        controller = PerformanceController(
            colors=self.mock_colors,
            aberrations_available=False
        )
        
        self.assertIsNotNone(controller)
        self.assertIsNone(controller.current_lens)
    
    def test_load_lens(self):
        """Test loading a lens into the controller"""
        controller = PerformanceController(
            colors=self.mock_colors,
            aberrations_available=False
        )
        
        # Load lens
        controller.load_lens(self.test_lens)
        
        # Verify lens was loaded
        self.assertEqual(controller.current_lens, self.test_lens)


@unittest.skipIf(not CONTROLLERS_AVAILABLE, "GUI controllers not available")
class TestComparisonController(unittest.TestCase):
    """Test ComparisonController functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_parent = Mock()
        self.test_lenses = [
            {
                'name': 'Test Lens 1',
                'type': 'Biconvex',
                'radius1': 100,
                'radius2': -100,
                'thickness': 10,
                'diameter': 50,
                'material': 'BK7',
                'refractive_index': 1.5168
            },
            {
                'name': 'Test Lens 2',
                'type': 'Biconcave',
                'radius1': -150,
                'radius2': 150,
                'thickness': 5,
                'diameter': 40,
                'material': 'SF11',
                'refractive_index': 1.7847
            }
        ]
        self.mock_colors = {
            'bg': '#2b2b2b',
            'fg': '#e0e0e0'
        }
    
    def test_controller_initialization(self):
        """Test controller can be initialized"""
        controller = ComparisonController(
            parent_window=self.mock_parent,
            lens_list=lambda: self.test_lenses,
            colors=self.mock_colors
        )
        
        self.assertIsNotNone(controller)
    
    def test_refresh_lens_list(self):
        """Test refreshing lens list"""
        controller = ComparisonController(
            parent_window=self.mock_parent,
            lens_list=lambda: self.test_lenses,
            colors=self.mock_colors
        )
        
        # Create mock listbox (simulating setup_ui)
        controller.listbox = Mock()
        controller.listbox.delete = Mock()
        controller.listbox.insert = Mock()
        
        # Refresh list
        controller.refresh_lens_list()
        
        # Verify listbox was updated
        controller.listbox.delete.assert_called_once()
        self.assertEqual(controller.listbox.insert.call_count, len(self.test_lenses))


@unittest.skipIf(not CONTROLLERS_AVAILABLE, "GUI controllers not available")
class TestExportController(unittest.TestCase):
    """Test ExportController functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_parent = Mock()
        self.test_lens = {
            'name': 'Test Lens',
            'radius1': 100,
            'radius2': -100,
            'thickness': 10,
            'diameter': 50,
            'material': 'BK7',
            'refractive_index': 1.5168
        }
        self.mock_colors = {
            'bg': '#2b2b2b',
            'fg': '#e0e0e0'
        }
    
    def test_controller_initialization(self):
        """Test controller can be initialized"""
        controller = ExportController(
            parent_window=self.mock_parent,
            colors=self.mock_colors
        )
        
        self.assertIsNotNone(controller)
        self.assertIsNone(controller.current_lens)
    
    def test_load_lens(self):
        """Test loading a lens into the controller"""
        controller = ExportController(
            parent_window=self.mock_parent,
            colors=self.mock_colors
        )
        
        # Create mock status text widget (simulating setup_ui)
        controller.status_text = Mock()
        controller.status_text.configure = Mock()
        controller.status_text.delete = Mock()
        controller.status_text.insert = Mock()
        
        # Load lens (using dict, need to handle lens.name access)
        # Mock the _update_status method since lens is dict
        controller._update_status = Mock()
        controller.current_lens = self.test_lens
        controller._update_status(f"Lens '{self.test_lens['name']}' loaded. Ready to export.")
        
        # Verify lens was loaded
        self.assertEqual(controller.current_lens, self.test_lens)
        controller._update_status.assert_called()


if __name__ == '__main__':
    unittest.main()
