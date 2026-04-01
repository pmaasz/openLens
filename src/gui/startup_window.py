#!/usr/bin/env python3
"""
openlens - Startup Window
Shows a welcome screen for selecting action on startup
"""

import tkinter as tk
from tkinter import ttk


class StartupWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("OpenLens")
        
        # Center window on screen
        window_width = 450
        window_height = 500
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")
        self.root.resizable(False, False)
        
        self.selected_action = None
        self.selected_item = None
        
        self._setup_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
    
    def _setup_ui(self):
        main_frame = ttk.Frame(self.root, padding="30")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        title_label = ttk.Label(main_frame, text="Welcome to OpenLens", 
                                font=("Segoe UI", 18, "bold"))
        title_label.pack(pady=(0, 20))
        
        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=(0, 20))
        
        button_width = 22
        
        ttk.Button(button_frame, text="Create New Lens", 
                   command=self._create_new_lens,
                   width=button_width).pack(pady=5)
        
        ttk.Button(button_frame, text="Create New Assembly", 
                   command=self._create_new_assembly,
                   width=button_width).pack(pady=5)
        
        ttk.Button(button_frame, text="Open Existing Lens", 
                   command=self._show_lens_list,
                   width=button_width).pack(pady=5)
        
        ttk.Button(button_frame, text="Open Existing Assembly", 
                   command=self._show_assembly_list,
                   width=button_width).pack(pady=5)
        
        # List frame container
        self.list_container = ttk.Frame(main_frame)
        self.list_frame = None
        self.listbox = None
        self.current_list_type = None
    
    def _create_new_lens(self):
        self.selected_action = "create_lens"
        self.root.destroy()
    
    def _create_new_assembly(self):
        self.selected_action = "create_assembly"
        self.root.destroy()
    
    def _show_lens_list(self):
        from gui.storage import LensStorage
        storage = LensStorage("lenses.json", lambda x: None)
        lenses = storage.load_lenses()
        
        # Filter to only Lens objects (not OpticalSystem)
        lens_items = [l for l in lenses if not (hasattr(l, 'elements') and hasattr(l, 'air_gaps'))]
        
        self._show_list("lens", lens_items)
    
    def _show_assembly_list(self):
        from gui.storage import LensStorage
        storage = LensStorage("lenses.json", lambda x: None)
        lenses = storage.load_lenses()
        
        # Filter to only OpticalSystem objects
        assembly_items = [l for l in lenses if hasattr(l, 'elements') and hasattr(l, 'air_gaps')]
        
        self._show_list("assembly", assembly_items)
    
    def _show_list(self, list_type, items):
        # Clear previous list
        for widget in self.list_container.winfo_children():
            widget.destroy()
        
        if list_type == "lens":
            frame_text = "Available Lenses"
            action = "open_lens"
        else:
            frame_text = "Available Assemblies"
            action = "open_assembly"
        
        self.list_frame = ttk.LabelFrame(self.list_container, text=frame_text, padding="10")
        self.list_frame.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(self.list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.listbox = tk.Listbox(self.list_frame, yscrollcommand=scrollbar.set, height=10, width=40)
        scrollbar.config(command=self.listbox.yview)
        
        for item in items:
            self.listbox.insert(tk.END, item.name)
        
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Bind double-click to select and open
        self.listbox.bind('<Double-Button-1>', lambda e: self._open_selected(action))
        
        self.list_container.pack(fill=tk.BOTH, expand=True)
        self.current_list_type = list_type
        
        # Add Open button
        open_btn = ttk.Button(self.list_container, text="Open Selected", 
                             command=lambda: self._open_selected(action))
        open_btn.pack(pady=5)
    
    def _open_selected(self, action):
        selection = self.listbox.curselection()
        if selection:
            idx = selection[0]
            self.selected_item = self.listbox.get(idx)
            self.selected_action = action
            self.root.destroy()
    
    def _on_close(self):
        self.selected_action = None
        self.root.destroy()
    
    def show(self):
        self.root.mainloop()
        return self.selected_action, self.selected_item


def get_startup_action():
    window = StartupWindow()
    return window.show()
