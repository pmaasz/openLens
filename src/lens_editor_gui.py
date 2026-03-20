#!/usr/bin/env python3
"""
openlens - GUI Editor Window
Interactive graphical interface for optical lens creation and modification
"""

import sys
import os
import tkinter as tk

# Add src directory to path if running directly
if __name__ == "__main__":
    current_dir = os.path.dirname(os.path.abspath(__file__))
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)

try:
    from gui.main_window import LensEditorWindow
except ImportError:
    # If package structure is different (e.g. running from root with -m src.lens_editor_gui)
    try:
        from src.gui.main_window import LensEditorWindow
    except ImportError:
        print("Error: Could not import LensEditorWindow. Please run from the project root.")
        sys.exit(1)

def main() -> None:
    root = tk.Tk()
    app = LensEditorWindow(root)
    root.mainloop()

if __name__ == "__main__":
    main()
