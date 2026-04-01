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
    from gui.startup_window import get_startup_action
except ImportError:
    try:
        from src.gui.main_window import LensEditorWindow
        from src.gui.startup_window import get_startup_action
    except ImportError:
        print("Error: Could not import modules. Please run from the project root.")
        sys.exit(1)

def main() -> None:
    action, selected_item = get_startup_action()
    
    if action is None:
        return
    
    root = tk.Tk()
    app = LensEditorWindow(root, initial_action=action, initial_item=selected_item)
    root.mainloop()

if __name__ == "__main__":
    main()
