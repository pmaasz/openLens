#!/usr/bin/env python3
"""
Run all functional tests for openlens application
"""

import sys
import os

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

# Run GUI tests
print("\n" + "=" * 70)
print("PHASE 2: GUI Functionality Tests")
print("=" * 70)

try:
    from test_gui import run_gui_tests
    result2 = run_gui_tests()
    gui_passed = result2.wasSuccessful()
except Exception as e:
    print(f"Error running GUI tests: {e}")
    gui_passed = False

# Summary
print("\n" + "=" * 70)
print("TEST SUITE SUMMARY")
print("=" * 70)

if core_passed and gui_passed:
    print("\n✓✓✓ ALL TESTS PASSED! ✓✓✓")
    print("\nThe openlens application is working correctly!")
    sys.exit(0)
else:
    print("\n✗✗✗ SOME TESTS FAILED ✗✗✗")
    if not core_passed:
        print("  - Core functionality tests failed")
    if not gui_passed:
        print("  - GUI functionality tests failed")
    sys.exit(1)
