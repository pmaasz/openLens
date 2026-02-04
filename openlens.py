#!/usr/bin/env python3
"""
openlens - Main Entry Point
Launches the optical lens design application
"""

import sys
import os

# Add src to path so imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from lens_editor_gui import main

if __name__ == "__main__":
    main()
