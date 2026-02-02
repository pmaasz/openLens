#!/usr/bin/env python3
"""
Unit tests for lens visualization module
Tests both 2D and 3D rendering capabilities
"""

import unittest
import tkinter as tk
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from lens_visualizer import LensVisualizer
    VISUALIZATION_AVAILABLE = True
except ImportError:
    VISUALIZATION_AVAILABLE = False
    print("Warning: Visualization not available for testing")


@unittest.skipIf(not VISUALIZATION_AVAILABLE, "Visualization dependencies not available")
class TestLensVisualizer(unittest.TestCase):
    """Test cases for LensVisualizer"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.root = tk.Tk()
        self.root.withdraw()
        self.frame = tk.Frame(self.root)
        
    def tearDown(self):
        """Clean up test fixtures"""
        try:
            self.root.destroy()
        except:
            pass
    
    def test_visualizer_initialization(self):
        """Test that visualizer initializes correctly"""
        viz = LensVisualizer(self.frame, width=6, height=5)
        self.assertIsNotNone(viz)
        self.assertIsNotNone(viz.figure)
        self.assertIsNotNone(viz.ax)
        self.assertIsNotNone(viz.canvas)
    
    def test_draw_lens_3d(self):
        """Test 3D lens drawing"""
        viz = LensVisualizer(self.frame, width=6, height=5)
        
        # Should not raise exception
        try:
            viz.draw_lens(r1=100.0, r2=-100.0, thickness=5.0, diameter=50.0)
        except Exception as e:
            self.fail(f"3D draw_lens raised exception: {e}")
    
    def test_draw_lens_2d(self):
        """Test 2D lens drawing"""
        viz = LensVisualizer(self.frame, width=6, height=5)
        
        # Test that draw_lens_2d method exists
        self.assertTrue(hasattr(viz, 'draw_lens_2d'))
        
        # Should not raise exception
        try:
            viz.draw_lens_2d(r1=100.0, r2=-100.0, thickness=5.0, diameter=50.0)
        except Exception as e:
            self.fail(f"2D draw_lens_2d raised exception: {e}")
    
    def test_draw_biconvex_lens_3d(self):
        """Test drawing biconvex lens in 3D"""
        viz = LensVisualizer(self.frame, width=6, height=5)
        viz.draw_lens(r1=100.0, r2=-100.0, thickness=5.0, diameter=50.0)
        # Test passes if no exception
    
    def test_draw_biconvex_lens_2d(self):
        """Test drawing biconvex lens in 2D"""
        viz = LensVisualizer(self.frame, width=6, height=5)
        viz.draw_lens_2d(r1=100.0, r2=-100.0, thickness=5.0, diameter=50.0)
        # Test passes if no exception
    
    def test_draw_plano_convex_lens_3d(self):
        """Test drawing plano-convex lens in 3D"""
        viz = LensVisualizer(self.frame, width=6, height=5)
        viz.draw_lens(r1=100.0, r2=10000.0, thickness=5.0, diameter=50.0)
        # Test passes if no exception
    
    def test_draw_plano_convex_lens_2d(self):
        """Test drawing plano-convex lens in 2D"""
        viz = LensVisualizer(self.frame, width=6, height=5)
        viz.draw_lens_2d(r1=100.0, r2=10000.0, thickness=5.0, diameter=50.0)
        # Test passes if no exception
    
    def test_draw_biconcave_lens_3d(self):
        """Test drawing biconcave lens in 3D"""
        viz = LensVisualizer(self.frame, width=6, height=5)
        viz.draw_lens(r1=-100.0, r2=100.0, thickness=5.0, diameter=50.0)
        # Test passes if no exception
    
    def test_draw_biconcave_lens_2d(self):
        """Test drawing biconcave lens in 2D"""
        viz = LensVisualizer(self.frame, width=6, height=5)
        viz.draw_lens_2d(r1=-100.0, r2=100.0, thickness=5.0, diameter=50.0)
        # Test passes if no exception
    
    def test_clear_visualization(self):
        """Test clearing the visualization"""
        viz = LensVisualizer(self.frame, width=6, height=5)
        viz.draw_lens(r1=100.0, r2=-100.0, thickness=5.0, diameter=50.0)
        
        try:
            viz.clear()
        except Exception as e:
            self.fail(f"Clear raised exception: {e}")
    
    def test_switch_between_2d_and_3d(self):
        """Test switching between 2D and 3D views"""
        viz = LensVisualizer(self.frame, width=6, height=5)
        
        # Draw 3D
        viz.draw_lens(r1=100.0, r2=-100.0, thickness=5.0, diameter=50.0)
        
        # Switch to 2D
        viz.draw_lens_2d(r1=100.0, r2=-100.0, thickness=5.0, diameter=50.0)
        
        # Switch back to 3D
        viz.draw_lens(r1=100.0, r2=-100.0, thickness=5.0, diameter=50.0)
        
        # Test passes if no exception
    
    def test_various_lens_parameters_3d(self):
        """Test 3D rendering with various parameters"""
        viz = LensVisualizer(self.frame, width=6, height=5)
        
        test_cases = [
            (50.0, -50.0, 3.0, 25.0),
            (200.0, -200.0, 10.0, 75.0),
            (75.0, -125.0, 6.0, 40.0),
        ]
        
        for r1, r2, thickness, diameter in test_cases:
            with self.subTest(r1=r1, r2=r2, thickness=thickness, diameter=diameter):
                viz.draw_lens(r1, r2, thickness, diameter)
    
    def test_various_lens_parameters_2d(self):
        """Test 2D rendering with various parameters"""
        viz = LensVisualizer(self.frame, width=6, height=5)
        
        test_cases = [
            (50.0, -50.0, 3.0, 25.0),
            (200.0, -200.0, 10.0, 75.0),
            (75.0, -125.0, 6.0, 40.0),
        ]
        
        for r1, r2, thickness, diameter in test_cases:
            with self.subTest(r1=r1, r2=r2, thickness=thickness, diameter=diameter):
                viz.draw_lens_2d(r1, r2, thickness, diameter)
    
    def test_dark_mode_colors(self):
        """Test that dark mode colors are defined"""
        viz = LensVisualizer(self.frame, width=6, height=5)
        
        self.assertIsNotNone(viz.COLORS_3D)
        self.assertIn('bg', viz.COLORS_3D)
        self.assertIn('surface_front', viz.COLORS_3D)
        self.assertIn('surface_back', viz.COLORS_3D)
        self.assertIn('axis', viz.COLORS_3D)


def run_visualization_tests():
    """Run all visualization tests and return results"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    suite.addTests(loader.loadTestsFromTestCase(TestLensVisualizer))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result


if __name__ == "__main__":
    print("=" * 70)
    print("openlens Visualization Unit Tests")
    print("=" * 70)
    print()
    
    if not VISUALIZATION_AVAILABLE:
        print("Visualization dependencies not available. Skipping tests.")
        sys.exit(0)
    
    result = run_visualization_tests()
    
    print()
    print("=" * 70)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped)}")
    
    if result.wasSuccessful():
        print("\n✓ ALL VISUALIZATION TESTS PASSED!")
        sys.exit(0)
    else:
        print("\n✗ SOME VISUALIZATION TESTS FAILED!")
        sys.exit(1)
