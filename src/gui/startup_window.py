#!/usr/bin/env python3
"""
openlens - Startup Window
Shows a welcome screen for selecting action on startup
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import json


class StartupWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("OpenLens")
        
        # Center window on screen
        window_width = 650
        window_height = 650
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")
        self.root.resizable(True, True)
        
        self.selected_action = None
        self.selected_item = None
        
        self._setup_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
    
    def _setup_ui(self):
        main_frame = ttk.Frame(self.root, padding="30")
        main_frame.pack(fill=tk.BOTH, expand=True)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(0, weight=1)
        
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
        self._all_items = []  # Store full items, not just names
    
    def _create_new_lens(self):
        self.selected_action = "create_lens"
        self.root.destroy()
    
    def _create_new_assembly(self):
        self.selected_action = "create_assembly"
        self.root.destroy()
    
    def _show_lens_list(self):
        from gui.storage import LensStorage
        storage = LensStorage("openlens.db", lambda x: None)
        lenses = storage.load_lenses()
        
        # Filter to only Lens objects (not OpticalSystem)
        lens_items = [l for l in lenses if not (hasattr(l, 'elements') and hasattr(l, 'air_gaps'))]
        
        self._show_list("lens", lens_items)
    
    def _show_assembly_list(self):
        from gui.storage import LensStorage
        storage = LensStorage("openlens.db", lambda x: None)
        lenses = storage.load_lenses()
        
        # Filter to only OpticalSystem objects
        assembly_items = [l for l in lenses if hasattr(l, 'elements') and hasattr(l, 'air_gaps')]
        
        self._show_list("assembly", assembly_items)
    
    def _show_list(self, list_type, items):
        # Clear previous list
        for widget in self.list_container.winfo_children():
            widget.destroy()
        
        self._all_items = items
        
        if list_type == "lens":
            frame_text = "Available Lenses"
            action = "open_lens"
        else:
            frame_text = "Available Assemblies"
            action = "open_assembly"
        
        self.list_frame = ttk.LabelFrame(self.list_container, text=frame_text, padding="10")
        self.list_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create button frame FIRST so it appears at bottom
        btn_frame = ttk.Frame(self.list_container)
        btn_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(5, 0))
        
        ttk.Button(btn_frame, text="+", width=3,
                  command=lambda: self._import_file(list_type)).pack(side=tk.RIGHT, padx=(2, 0))
        ttk.Button(btn_frame, text="-", width=3,
                  command=lambda: self._delete_item(list_type, action)).pack(side=tk.RIGHT)
        
        scrollbar = ttk.Scrollbar(self.list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.listbox = tk.Listbox(self.list_frame, yscrollcommand=scrollbar.set, height=10, width=38)
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
    
    def _import_file(self, list_type):
        """Import a lens/assembly from file."""
        file_types = [
            ("JSON files", "*.json"),
            ("STEP files", "*.step"),
            ("STL files", "*.stl"),
            ("OBJ files", "*.obj"),
            ("All files", "*.*")
        ]
        
        filename = filedialog.askopenfilename(
            title="Import Lens/Assembly",
            filetypes=file_types
        )
        
        if not filename:
            return
        
        ext = os.path.splitext(filename)[1].lower()
        
        try:
            if ext == ".json":
                self._import_json(filename, list_type)
            else:
                messagebox.showinfo("Import", f"Import of {ext} files is not yet implemented. Only JSON import is available.")
        except Exception as e:
            messagebox.showerror("Import Error", f"Failed to import file: {e}")
    
    def _import_json(self, filename: str, list_type: str):
        """Import lens/assembly from JSON file."""
        with open(filename, 'r') as f:
            data = json.load(f)
        
        from gui.storage import LensStorage
        from lens import Lens
        from optical_system import OpticalSystem
        
        storage = LensStorage("openlens.db", lambda x: None)
        
        if list_type == "lens":
            # Try to create a Lens from the JSON data
            try:
                # Check if it looks like a lens or assembly
                if 'elements' in data:
                    # It's an assembly
                    new_item = OpticalSystem.from_dict(data)
                else:
                    # It's a lens
                    new_item = Lens.from_dict(data)
            except Exception as e:
                messagebox.showerror("Import Error", f"Failed to parse lens data: {e}")
                return
            
            item_type = "lens"
        else:
            # Assembly
            try:
                new_item = OpticalSystem.from_dict(data)
            except Exception as e:
                messagebox.showerror("Import Error", f"Failed to parse assembly data: {e}")
                return
            
            item_type = "assembly"
        
        # Add to storage
        existing_lenses = storage.load_lenses()
        existing_lenses.append(new_item)
        storage.save_lenses(existing_lenses)
        
        # Refresh the list
        if list_type == "lens":
            self._show_lens_list()
        else:
            self._show_assembly_list()
        
        messagebox.showinfo("Import", f"Successfully imported {new_item.name}")
        
        messagebox.showwarning("Delete", f"Could not find '{item.name}' in storage")
    
    def _delete_item(self, list_type: str, action: str):
        """Delete the selected lens/assembly."""
        selection = self.listbox.curselection()
        if not selection:
            messagebox.showwarning("Delete", "Please select an item to delete")
            return
        
        idx = selection[0]
        item = self._all_items[idx]
        
        # Confirm deletion
        confirm = messagebox.askyesno(
            "Confirm Delete",
            f"Are you sure you want to delete '{item.name}'?\n\nThis action cannot be undone."
        )
        
        if not confirm:
            return
        
        # Delete from storage using DatabaseManager
        from gui.storage import LensStorage
        from database import DatabaseManager
        import sqlite3
        
        db_path = "openlens.db"
        
        # Check if it's an assembly or lens and delete by ID
        is_assembly = hasattr(item, 'elements') and hasattr(item, 'air_gaps')
        
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            if is_assembly:
                cursor.execute('DELETE FROM assemblies WHERE id = ?', (item.id,))
                # Also delete assembly elements and air gaps
                cursor.execute('DELETE FROM assembly_elements WHERE assembly_id = ?', (item.id,))
                cursor.execute('DELETE FROM assembly_air_gaps WHERE assembly_id = ?', (item.id,))
            else:
                cursor.execute('DELETE FROM lenses WHERE id = ?', (item.id,))
            
            conn.commit()
            deleted = cursor.rowcount > 0
            conn.close()
            
            if deleted:
                # Force refresh
                if list_type == "lens":
                    self._show_lens_list()
                else:
                    self._show_assembly_list()
                
                messagebox.showinfo("Delete", f"Deleted '{item.name}'")
            else:
                messagebox.showwarning("Delete", f"Could not find '{item.name}' in storage")
                
        except Exception as e:
            messagebox.showerror("Delete Error", f"Failed to delete: {e}")
    
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
