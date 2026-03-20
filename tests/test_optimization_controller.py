#!/usr/bin/env python3
"""
Tests for OptimizationController
"""

import unittest
import tkinter as tk
from unittest.mock import MagicMock, patch, ANY
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src'))

from gui.optimization_controller import OptimizationController
from optical_system import OpticalSystem
from lens import Lens

class TestOptimizationController(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.controller = OptimizationController(colors={})
        
        # Create a dummy frame for setup_ui
        self.frame = tk.Frame(self.root)
        self.controller.setup_ui(self.frame)
        
    def tearDown(self):
        self.root.destroy()
        
    def test_initialization(self):
        self.assertIsNotNone(self.controller.variables_frame)
        self.assertIsNotNone(self.controller.targets_frame)
        self.assertTrue(self.controller.target_vars['focal_length_enabled'].get())
        self.assertTrue(self.controller.target_vars['maintain_cemented'].get())
        
    def test_load_optical_system(self):
        # Create a doublet system
        sys = OpticalSystem()
        l1 = Lens(name="L1", radius_of_curvature_1=100, radius_of_curvature_2=-100, thickness=5)
        l2 = Lens(name="L2", radius_of_curvature_1=-100, radius_of_curvature_2=200, thickness=3)
        sys.add_lens(l1)
        sys.add_lens(l2, air_gap_before=0.0) # Cemented
        
        self.controller.load_lens(sys)
        
        # Check if variables are populated
        # We expect checkboxes for R1, R2, Thickness for each lens
        # keys like 'r1_0', 'r2_0', 'th_0', 'gap_0', 'r1_1', ...
        
        self.assertIn('r1_0', self.controller.variable_vars)
        self.assertIn('r2_0', self.controller.variable_vars)
        self.assertIn('th_0', self.controller.variable_vars)
        self.assertIn('gap_0', self.controller.variable_vars)
        self.assertIn('r1_1', self.controller.variable_vars)
        
        # Verify defaults (R1, R2, Gap are checked by default, Thickness unchecked)
        self.assertTrue(self.controller.variable_vars['r1_0'].get())
        self.assertFalse(self.controller.variable_vars['th_0'].get())
        
    def _get_config(self):
        return {
            'variables': {k: v.get() for k, v in self.controller.variable_vars.items()},
            'targets': {
                'focal_length_enabled': self.controller.target_vars['focal_length_enabled'].get(),
                'focal_length_value': self.controller.target_vars['focal_length_value'].get(),
                'spot_size_enabled': self.controller.target_vars['spot_size_enabled'].get(),
                'spherical_enabled': self.controller.target_vars['spherical_enabled'].get(),
                'coma_enabled': self.controller.target_vars['coma_enabled'].get(),
                'astigmatism_enabled': self.controller.target_vars['astigmatism_enabled'].get(),
                'min_thickness': self.controller.target_vars['min_thickness'].get(),
                'max_thickness': self.controller.target_vars['max_thickness'].get(),
                'min_air_gap': self.controller.target_vars['min_air_gap'].get(),
                'min_edge_thickness': self.controller.target_vars['min_edge_thickness'].get(),
                'maintain_cemented': self.controller.target_vars['maintain_cemented'].get(),
                'robust_mode': self.controller.target_vars['robust_mode'].get(),
            },
            'algorithm': self.controller.algorithm_var.get()
        }

    @patch('gui.optimization_controller.LensOptimizer')
    def test_run_optimization_cemented_linking(self, MockOptimizer):
        # Setup cemented doublet
        sys = OpticalSystem()
        l1 = Lens(radius_of_curvature_1=50, radius_of_curvature_2=-50, thickness=5)
        l2 = Lens(radius_of_curvature_1=-50, radius_of_curvature_2=100, thickness=3)
        sys.add_lens(l1)
        sys.add_lens(l2, air_gap_before=0.001) # Very small gap -> cemented
        
        self.controller.load_lens(sys)
        self.controller.target_vars['maintain_cemented'].set(True)
        
        # Mock the worker logic by running it synchronously
        # We need to bypass the thread start and call _optimization_worker directly
        # But _optimization_worker is an instance method.
        
        # Configure MockOptimizer instance
        mock_instance = MockOptimizer.return_value
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.initial_merit = 1.0
        mock_result.final_merit = 0.1
        mock_result.optimized_system = sys
        mock_instance.optimize.return_value = mock_result
        
        # Run worker directly
        self.controller._optimization_worker(self.controller.current_lens, self._get_config())
        
        # Verify OptimizationVariable construction
        # We expect R2 of lens 0 to have linked_target to R1 of lens 1
        # And R1 of lens 1 should NOT be an independent variable (or at least handled)
        
        call_args = MockOptimizer.call_args
        self.assertIsNotNone(call_args)
        variables_passed = call_args[0][1] # 2nd arg is variables list
        
        # Find R2 of elem 0
        r2_var = next((v for v in variables_passed if v.name == "R2_Elem1"), None)
        self.assertIsNotNone(r2_var)
        
        # Verify it has linked targets
        # linked_targets format: List[Tuple[int, str]] -> [(element_index, parameter_name)]
        # Should link to Element 1 (index 1), parameter 'radius_of_curvature_1'
        self.assertTrue(len(r2_var.linked_targets) > 0)
        self.assertEqual(r2_var.linked_targets[0], (1, 'radius_of_curvature_1'))
        
        # Find R1 of elem 1
        r1_var = next((v for v in variables_passed if v.name == "R1_Elem2"), None)
        # It SHOULD NOT be in the variables list because it is driven by R2_Elem1
        self.assertIsNone(r1_var, "R1 of second cemented element should not be an independent variable")

    @patch('gui.optimization_controller.LensOptimizer')
    def test_run_optimization_single_lens(self, MockOptimizer):
        # Setup single lens
        lens = Lens(name="Single", radius_of_curvature_1=50, radius_of_curvature_2=-50, thickness=5)
        
        self.controller.load_lens(lens)
        
        # Verify variables loaded
        self.assertIn('radius_of_curvature_1_0', self.controller.variable_vars)
        
        # Setup mock result
        mock_instance = MockOptimizer.return_value
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.initial_merit = 1.0
        mock_result.final_merit = 0.1
        
        # Mock the optimized system to contain a lens
        optimized_sys = OpticalSystem()
        optimized_lens = Lens(name="Optimized", radius_of_curvature_1=55, radius_of_curvature_2=-55, thickness=5)
        optimized_sys.add_lens(optimized_lens)
        
        mock_result.optimized_system = optimized_sys
        mock_instance.optimize.return_value = mock_result
        
        # Run worker
        self.controller._optimization_worker(self.controller.current_lens, self._get_config())
        
        # Verify that controller.current_lens is updated to the LENS object, not the system
        self.assertIsInstance(self.controller.current_lens, Lens)
        self.assertEqual(self.controller.current_lens.radius_of_curvature_1, 55)

    def test_glass_variables_ui(self):
        """Test that Glass (Index/Abbe) variables appear in UI"""
        # Create a system (glass vars only appear for system optimization currently, or should check logic)
        # Logic says: if hasattr(elements)... else single lens mode.
        # Single lens mode logic (lines 507+) in controller only adds R1, R2, Th.
        # Glass vars were added only in the 'Multi-element system' block (lines 251+).
        # So we must use OpticalSystem.
        
        sys_obj = OpticalSystem()
        l1 = Lens(name="L1", material="BK7")
        sys_obj.add_lens(l1)
        
        self.controller.load_lens(sys_obj)
        
        # Check for Index/Abbe checkboxes
        self.assertIn('nd_0', self.controller.variable_vars)
        self.assertIn('vd_0', self.controller.variable_vars)
        
        # Defaults should be False
        self.assertFalse(self.controller.variable_vars['nd_0'].get())
        self.assertFalse(self.controller.variable_vars['vd_0'].get())

    @patch('gui.optimization_controller.LensOptimizer')
    def test_run_optimization_glass_variables(self, MockOptimizer):
        sys_obj = OpticalSystem()
        l1 = Lens(name="L1", material="BK7")
        sys_obj.add_lens(l1)
        self.controller.load_lens(sys_obj)
        
        # Enable Glass Variables
        if 'nd_0' in self.controller.variable_vars:
            self.controller.variable_vars['nd_0'].set(True)
        if 'vd_0' in self.controller.variable_vars:
            self.controller.variable_vars['vd_0'].set(True)
        
        # Mock Optimizer
        mock_instance = MockOptimizer.return_value
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.initial_merit = 1.0
        mock_result.final_merit = 0.5
        mock_result.optimized_system = sys_obj
        mock_instance.optimize.return_value = mock_result
        
        # Run worker
        self.controller._optimization_worker(self.controller.current_lens, self._get_config())
        
        # Verify variables passed to optimizer
        call_args = MockOptimizer.call_args
        if call_args:
            variables_passed = call_args[0][1]
            
            nd_var = next((v for v in variables_passed if v.parameter == "refractive_index"), None)
            vd_var = next((v for v in variables_passed if v.parameter == "abbe_number"), None)
            
            self.assertIsNotNone(nd_var)
            self.assertIsNotNone(vd_var)
            
            self.assertEqual(nd_var.element_index, 0)
            self.assertEqual(vd_var.element_index, 0)

if __name__ == '__main__':
    unittest.main()
