#!/usr/bin/env python3
"""
OpenLense Setup Verification Script
Run this to verify your installation is ready to use
"""

import sys
import os

def check_python_version():
    """Check if Python version is sufficient"""
    version = sys.version_info
    if version.major >= 3 and version.minor >= 6:
        print(f"✓ Python {version.major}.{version.minor}.{version.micro} (3.6+ required)")
        return True
    else:
        print(f"✗ Python {version.major}.{version.minor} - Need Python 3.6 or higher")
        return False

def check_tkinter():
    """Check if tkinter is available"""
    try:
        import tkinter
        print("✓ tkinter available (GUI will work)")
        return True
    except ImportError:
        print("✗ tkinter not found (GUI will not work)")
        print("  Install with: sudo apt-get install python3-tk (Ubuntu/Debian)")
        return False

def check_project_files():
    """Check if all required project files exist"""
    required_files = [
        'lens_editor.py',
        'lens_editor_gui.py',
        'test_lens_editor.py',
        'test_gui.py',
        'run_all_tests.py'
    ]
    
    all_present = True
    for filename in required_files:
        if os.path.exists(filename):
            print(f"✓ {filename} found")
        else:
            print(f"✗ {filename} missing")
            all_present = False
    
    return all_present

def run_quick_test():
    """Run a quick test of core functionality"""
    try:
        from lens_editor import Lens
        
        # Create a test lens
        lens = Lens(
            name="Test Lens",
            radius_of_curvature_1=100.0,
            radius_of_curvature_2=-100.0,
            thickness=5.0,
            refractive_index=1.5168
        )
        
        # Calculate focal length
        focal_length = lens.calculate_focal_length()
        
        if focal_length and 95 < focal_length < 100:
            print(f"✓ Core functionality test passed (focal length: {focal_length:.2f}mm)")
            return True
        else:
            print("✗ Core functionality test failed")
            return False
    except Exception as e:
        print(f"✗ Core functionality test failed: {e}")
        return False

def main():
    print("=" * 70)
    print("OpenLense Setup Verification")
    print("=" * 70)
    print()
    
    results = []
    
    print("Checking Python version...")
    results.append(check_python_version())
    print()
    
    print("Checking tkinter (for GUI)...")
    results.append(check_tkinter())
    print()
    
    print("Checking project files...")
    results.append(check_project_files())
    print()
    
    print("Testing core functionality...")
    results.append(run_quick_test())
    print()
    
    print("=" * 70)
    if all(results):
        print("✓✓✓ ALL CHECKS PASSED! ✓✓✓")
        print()
        print("Your OpenLense installation is ready to use!")
        print()
        print("Quick start:")
        print("  • Run GUI:  python3 lens_editor_gui.py")
        print("  • Run CLI:  python3 lens_editor.py")
        print("  • Run tests: python3 run_all_tests.py")
        return 0
    else:
        print("✗✗✗ SOME CHECKS FAILED ✗✗✗")
        print()
        print("Please fix the issues above before using OpenLense.")
        print("See README.md for detailed installation instructions.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
