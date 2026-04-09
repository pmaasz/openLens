#!/usr/bin/env python3
"""
Run all functional tests for openlens application
"""

import sys
import os
import unittest

# Add project directory to path
project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_dir)

print("=" * 70)
print("openlens - Complete Test Suite")
print("=" * 70)
print()

# Run core tests
print("\n" + "=" * 70)
print("PHASE 1: Core Functionality Tests")
print("=" * 70)

try:
    from test_lens_editor import run_tests
    result1 = run_tests()
    core_passed = result1.wasSuccessful()
except Exception as e:
    print(f"Error running core tests: {e}")
    core_passed = False

# Run System Tracer tests
print("\n" + "=" * 70)
print("PHASE 1.5: System Tracer Tests")
print("=" * 70)

try:
    import unittest
    import test_system_tracer
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(test_system_tracer)
    runner = unittest.TextTestRunner(verbosity=2)
    result_sys = runner.run(suite)
    sys_passed = result_sys.wasSuccessful()
except Exception as e:
    print(f"Error running system tracer tests: {e}")
    import traceback
    traceback.print_exc()
    sys_passed = False

# Run 3D Ray Tracer tests
print("\n" + "=" * 70)
print("PHASE 1.6: 3D Ray Tracer Tests")
print("=" * 70)

try:
    import test_ray_tracer_3d
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(test_ray_tracer_3d)
    runner = unittest.TextTestRunner(verbosity=2)
    result_3d = runner.run(suite)
    r3d_passed = result_3d.wasSuccessful()
except Exception as e:
    print(f"Error running 3D ray tracer tests: {e}")
    import traceback
    traceback.print_exc()
    r3d_passed = False

# Run Analysis & Tolerancing tests
print("\n" + "=" * 70)
print("PHASE 1.7: Analysis & Tolerancing Tests")
print("=" * 70)

try:
    import test_analysis
    import test_tolerancing
    import test_environmental
    import test_spot_diagram_chromatic
    import test_polarization_ray_tracing
    import test_material_cache
    
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromModule(test_analysis))
    suite.addTests(loader.loadTestsFromModule(test_tolerancing))
    suite.addTests(loader.loadTestsFromModule(test_environmental))
    suite.addTests(loader.loadTestsFromModule(test_spot_diagram_chromatic))
    suite.addTests(loader.loadTestsFromModule(test_polarization_ray_tracing))
    suite.addTests(loader.loadTestsFromModule(test_material_cache))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result_analysis = runner.run(suite)
    analysis_passed = result_analysis.wasSuccessful()
except Exception as e:
    print(f"Error running analysis tests: {e}")
    import traceback
    traceback.print_exc()
    analysis_passed = False

# Run GUI tests
print("\n" + "=" * 70)
print("PHASE 2: GUI Functionality Tests")
print("=" * 70)

try:
    os.environ['OPENLENS_TESTING'] = '1'
    from test_gui import run_gui_tests
    result2 = run_gui_tests()
    gui_passed = result2.wasSuccessful()
except Exception as e:
    print(f"Error running GUI tests: {e}")
    gui_passed = False

# Run Export tests
print("\n" + "=" * 70)
print("PHASE 4: Export Functionality Tests")
print("=" * 70)

try:
    import test_stl_export
    import test_drawing_export
    import test_step_export
    
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromModule(test_stl_export))
    suite.addTests(loader.loadTestsFromModule(test_drawing_export))
    suite.addTests(loader.loadTestsFromModule(test_step_export))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result_export = runner.run(suite)
    export_passed = result_export.wasSuccessful()
except Exception as e:
    print(f"Error running export tests: {e}")
    import traceback
    traceback.print_exc()
    export_passed = False

# Summary
print("\n" + "=" * 70)
print("TEST SUITE SUMMARY")
print("=" * 70)

if core_passed and sys_passed and r3d_passed and analysis_passed and gui_passed and export_passed:
    print("\n✓✓✓ ALL TESTS PASSED! ✓✓✓")
    print("\nThe openlens application is working correctly!")
    sys.exit(0)
else:
    print("\n✗✗✗ SOME TESTS FAILED ✗✗✗")
    if not core_passed:
        print("  - Core functionality tests failed")
    if not sys_passed:
        print("  - System tracer tests failed")
    if not r3d_passed:
        print("  - 3D ray tracer tests failed")
    if not analysis_passed:
        print("  - Analysis & Tolerancing tests failed")
    if not gui_passed:
        print("  - GUI functionality tests failed")
    if not export_passed:
        print("  - Export functionality tests failed")
    sys.exit(1)
