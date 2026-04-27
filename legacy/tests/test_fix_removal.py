
import unittest
import tkinter as tk
from tkinter import ttk
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'src'))

from optical_system import OpticalSystem
from lens import Lens
from gui_controllers import LensEditorController

class TestAssemblyLensRemoval(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.colors = {"bg": "white", "fg": "black", "accent": "blue"}
        mock_cb = lambda *args: None
        self.controller = LensEditorController(
            colors=self.colors,
            on_lens_updated=mock_cb
        )
        self.controller.parent_window = type('MockWindow', (), {
            'root': self.root,
            'update_status': lambda m: print(f"Status: {m}"),
            'simulation_controller': type('MockSim', (), {'run_simulation': lambda: None})()
        })()
        # Mocking necessary frames for _show_assembly_editor
        self.controller._scrollable_frame = ttk.Frame(self.root)
        self.controller._scrollable_frame.pack()
        self.controller.on_lens_updated_callback = mock_cb

    def test_remove_lens_updates_listbox(self):
        """Test that removing a lens through the controller updates the UI and model."""
        system = OpticalSystem(name="Test Assembly")
        lens1 = Lens(name="Lens1")
        lens2 = Lens(name="Lens2")
        
        system.add_lens(lens1)
        system.add_lens(lens2)
        
        self.assertEqual(len(system.elements), 2)
        
        # Invoke the editor
        self.controller._show_assembly_editor([lens1, lens2], [lens1, lens2], system)
        
        # Get the listbox from the controller
        available_lb, current_lb = self.controller._assembly_listboxes
        
        # Verify initial state
        self.assertEqual(current_lb.size(), 2)

        
        # Select the second lens (index 1)
        current_lb.selection_clear(0, tk.END)
        current_lb.selection_set(1)
        
        # Trigger the command
        # Instead of finding button, find the command function in the closure
        # We need to find the function named 'remove_lens_from_assembly'
        # Actually, let's just find the button more robustly
        def find_btn(parent, text):
            for child in parent.winfo_children():
                if isinstance(child, ttk.Button) and child.cget('text') == text:
                    return child
                res = find_btn(child, text)
                if res: return res
            return None
            
        remove_btn = find_btn(self.root, "<- Remove")
        self.assertIsNotNone(remove_btn, "Could not find Remove button in UI")
        
        # Trigger the command
        remove_btn.invoke()
        
        # Verify model updated
        self.assertEqual(len(system.elements), 1)
        self.assertEqual(system.elements[0].lens.name, "Lens1")
        
        # Verify UI updated
        self.assertEqual(current_lb.size(), 1)
        self.assertIn("Lens1", current_lb.get(0))

if __name__ == "__main__":
    unittest.main()
