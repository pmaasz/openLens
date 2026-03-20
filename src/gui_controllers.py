"""
GUI Controllers for openlens

This module provides separate controller classes to decompose the
large GUI class into manageable, focused components following the
Single Responsibility Principle.

Each controller handles a specific tab/feature:
- LensSelectionController: Manages lens library and selection
- LensEditorController: Handles lens property editing
- SimulationController: Manages ray tracing visualization
- PerformanceController: Manages aberration analysis
- ExportController: Manages export functionality
"""

import logging
import tkinter as tk
from tkinter import ttk
from typing import Optional, List, Callable, Dict, Any, TYPE_CHECKING
import json
import math

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from lens import Lens
    from gui.main_window import LensEditorWindow

# Import CopyableMessageBox for copyable error dialogs
try:
    from .dialogs import CopyableMessageBox
except ImportError:
    try:
        from dialogs import CopyableMessageBox
    except ImportError:
        # Fallback to standard messagebox if CopyableMessageBox not available
        from tkinter import messagebox as _mb
        class CopyableMessageBox:
            @staticmethod
            def showerror(parent, title, msg): _mb.showerror(title, msg)
            @staticmethod
            def showwarning(parent, title, msg): _mb.showwarning(title, msg)
            @staticmethod
            def showinfo(parent, title, msg): _mb.showinfo(title, msg)


class LensSelectionController:
    """
    Controller for lens selection and management in the selection tab.
    
    Responsibilities:
    - Manage lens list display
    - Handle lens selection
    - Create/delete/duplicate lenses
    - Update selection info panel
    """
    
    def __init__(self, parent_window, lens_list, colors, on_lens_selected, on_create_new, on_create_system, on_delete, on_lens_updated, on_export=None):
        """
        Initialize the lens selection controller.
        
        Args:
            parent_window: Reference to main window
            lens_list: List of Lens objects
            colors: Color scheme dictionary
            on_lens_selected: Callback when lens is selected
            on_create_new: Callback when creating new lens
            on_create_system: Callback when creating new optical system
            on_delete: Callback when deleting lens
            on_lens_updated: Callback when lens is updated
            on_export: Callback when exporting lens (optional)
        """
        self.window = parent_window
        self.lens_list = lens_list
        self.colors = colors
        self.on_lens_selected_callback = on_lens_selected
        self.on_create_new_callback = on_create_new
        self.on_create_system_callback = on_create_system
        self.on_delete_callback = on_delete
        self.on_lens_updated_callback = on_lens_updated
        self.on_export_callback = on_export
        self.selected_lens = None
        self.listbox = None
        self.info_text = None
        self.save_system_btn = None
        
    def setup_ui(self, parent_frame):
        """Set up the selection tab UI"""
        # Import constants
        try:
            from .constants import FONT_FAMILY, PADDING_XLARGE, PADDING_SMALL, FONT_SIZE_LARGE, FONT_SIZE_NORMAL
        except ImportError:
            try:
                from constants import FONT_FAMILY, PADDING_XLARGE, PADDING_SMALL, FONT_SIZE_LARGE, FONT_SIZE_NORMAL
            except ImportError:
                # Fallback values
                FONT_FAMILY = "Segoe UI"
                PADDING_XLARGE = 20
                PADDING_SMALL = 5
                FONT_SIZE_LARGE = 11
                FONT_SIZE_NORMAL = 10
        
        # Main content frame
        content_frame = ttk.Frame(parent_frame, padding="20")
        content_frame.grid(row=0, column=0, sticky="nsew")
        content_frame.columnconfigure(0, weight=1)
        content_frame.rowconfigure(1, weight=1)
        
        # Title
        title_label = ttk.Label(content_frame, text="Lens Library", 
                               font=(FONT_FAMILY, 16, 'bold'))
        title_label.grid(row=0, column=0, pady=(0, PADDING_XLARGE))
        
        # Create a frame for the lens list and buttons
        list_frame = ttk.LabelFrame(content_frame, text="Available Lenses (Hold Ctrl/Shift to select multiple)", padding="10")
        list_frame.grid(row=1, column=0, sticky="nsew")
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)
        
        # Lens listbox with scrollbar
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.grid(row=0, column=1, sticky="ns")
        
        self.listbox = tk.Listbox(list_frame, 
                                   yscrollcommand=scrollbar.set,
                                   bg=self.colors['entry_bg'],
                                   fg=self.colors['fg'],
                                   selectbackground=self.colors['accent'],
                                   selectforeground=self.colors['fg'],
                                   font=(FONT_FAMILY, FONT_SIZE_LARGE),
                                   height=15,
                                   borderwidth=1,
                                   relief=tk.SOLID,
                                   selectmode=tk.EXTENDED)
        self.listbox.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        scrollbar.config(command=self.listbox.yview)
        
        # Bind events
        self.listbox.bind('<Double-Button-1>', lambda e: self.select_lens())
        self.listbox.bind('<<ListboxSelect>>', self.update_info)
        
        # Lens info panel
        info_frame = ttk.LabelFrame(content_frame, text="Lens Information", padding="10")
        info_frame.grid(row=2, column=0, sticky="ew", pady=PADDING_XLARGE)
        
        self.info_text = tk.Text(info_frame, 
                                 height=9, 
                                 bg=self.colors['entry_bg'],
                                 fg=self.colors['fg'],
                                 font=(FONT_FAMILY, FONT_SIZE_NORMAL),
                                 wrap=tk.WORD,
                                 borderwidth=1,
                                 relief=tk.SOLID,
                                 state='disabled')
        self.info_text.pack(fill=tk.BOTH, expand=True)
        
        # Button frame
        button_frame = ttk.Frame(content_frame)
        button_frame.grid(row=3, column=0, pady=PADDING_XLARGE)
        
        ttk.Button(button_frame, text="Create New Lens", 
                  command=self.create_new_lens,
                  width=18).pack(side=tk.LEFT, padx=PADDING_SMALL)
        
        ttk.Button(button_frame, text="Create System", 
                  command=self.create_new_system,
                  width=18).pack(side=tk.LEFT, padx=PADDING_SMALL)
        
        ttk.Button(button_frame, text="Select / Simulate", 
                  command=self.select_lens,
                  width=20).pack(side=tk.LEFT, padx=PADDING_SMALL)
        
        self.save_system_btn = ttk.Button(button_frame, text="Save System", 
                  command=self.save_current_system,
                  width=18, state='disabled')
        self.save_system_btn.pack(side=tk.LEFT, padx=PADDING_SMALL)
        
        ttk.Button(button_frame, text="Delete", 
                  command=self.delete_lens,
                  width=15).pack(side=tk.LEFT, padx=PADDING_SMALL)
        
        if self.on_export_callback:
            ttk.Button(button_frame, text="Export STL", 
                      command=self.export_lens,
                      width=15).pack(side=tk.LEFT, padx=PADDING_SMALL)
        
        # Load initial data
        self.refresh_lens_list()
    
    
    def refresh_lens_list(self):
        """Refresh the lens listbox with current lenses"""
        if not self.listbox:
            return
        self.listbox.delete(0, tk.END)
        for lens in self.lens_list:
            # Handle both Lens objects and dicts
            if isinstance(lens, dict):
                name = lens.get('name', 'Unknown')
                lens_type = lens.get('type', 'Unknown')
            else:
                name = lens.name
                lens_type = lens.lens_type
            display_text = f"{name} ({lens_type})"
            self.listbox.insert(tk.END, display_text)
    
    def update_info(self, event=None):
        """Update the lens information panel when selection changes"""
        if not self.listbox or not self.info_text:
            return
            
        selection = self.listbox.curselection()
        if not selection:
            self.info_text.config(state='normal')
            self.info_text.delete(1.0, tk.END)
            self.info_text.insert(1.0, "Select a lens to view details")
            self.info_text.config(state='disabled')
            return
        
        if len(selection) > 1:
            # Multiple selection info
            self.info_text.config(state='normal')
            self.info_text.delete(1.0, tk.END)
            info = f"Multi-Lens System Selected ({len(selection)} lenses)\n\n"
            info += "Lenses in system:\n"
            
            for i, idx in enumerate(selection):
                if 0 <= idx < len(self.lens_list):
                    lens = self.lens_list[idx]
                    name = lens.get('name', 'Unknown') if isinstance(lens, dict) else lens.name
                    info += f"{i+1}. {name}\n"
            
            info += "\nClick 'Select / Simulate' to simulate as a temporary system.\n"
            info += "Click 'Save System' to save as a new Optical System."
            self.info_text.insert(1.0, info)
            self.info_text.config(state='disabled')
            
            if self.save_system_btn:
                self.save_system_btn.config(state='normal')
            return
        
        if self.save_system_btn:
            self.save_system_btn.config(state='disabled')
        
        index = selection[0]
        if 0 <= index < len(self.lens_list):
            lens = self.lens_list[index]
            
            # Handle both Lens objects and dicts
            if isinstance(lens, dict):
                focal_length = 0  # Simplified for dicts
                info = f"""Name: {lens.get('name', 'Unknown')}
Type: {lens.get('type', 'Unknown')}
Material: {lens.get('material', 'Unknown')}
Radius 1: {lens.get('radius1', 0):.3f} mm
Radius 2: {lens.get('radius2', 0):.3f} mm
Center Thickness: {lens.get('thickness', 0):.3f} mm
Diameter: {lens.get('diameter', 0):.3f} mm
Refractive Index: {lens.get('refractive_index', 1.5):.3f}"""
            else:
                focal_length = lens.calculate_focal_length() or 0
                info = f"""ID: {lens.id}
Name: {lens.name}
Type: {lens.lens_type}
Material: {lens.material}
Radius 1: {lens.radius_of_curvature_1:.3f} mm
Radius 2: {lens.radius_of_curvature_2:.3f} mm
Center Thickness: {lens.thickness:.3f} mm
Diameter: {lens.diameter:.3f} mm
Refractive Index: {lens.refractive_index:.3f}
Focal Length: {focal_length:.3f} mm
Created: {lens.created_at}
Modified: {lens.modified_at}"""
            
            self.info_text.config(state='normal')
            self.info_text.delete(1.0, tk.END)
            self.info_text.insert(1.0, info)
            self.info_text.config(state='disabled')
    
    def select_lens(self):
        """Select a lens and notify parent"""
        if not self.listbox:
            return
            
        selection = self.listbox.curselection()
        if not selection:
            return
        
        # Handle multiple selection
        if len(selection) > 1:
            try:
                # Import here to avoid circular imports or import errors
                try:
                    from .optical_system import OpticalSystem
                except ImportError:
                    from optical_system import OpticalSystem
                
                # Create a temporary system from selected lenses
                system = OpticalSystem(name="Multi-Lens System")
                
                for i, index in enumerate(selection):
                    if 0 <= index < len(self.lens_list):
                        lens = self.lens_list[index]
                        # Add lens with default 5mm air gap before (except for first lens)
                        air_gap = 5.0 if i > 0 else 0.0
                        system.add_lens(lens, air_gap_before=air_gap)
                
                self.selected_lens = system
                if self.on_lens_selected_callback:
                    self.on_lens_selected_callback(self.selected_lens)
                    
            except Exception as e:
                logger.error(f"Could not create OpticalSystem: {e}")
                # Fallback to single selection of first item
                index = selection[0]
                if 0 <= index < len(self.lens_list):
                    self.selected_lens = self.lens_list[index]
                    if self.on_lens_selected_callback:
                        self.on_lens_selected_callback(self.selected_lens)
            return

        index = selection[0]
        if 0 <= index < len(self.lens_list):
            self.selected_lens = self.lens_list[index]
            if self.on_lens_selected_callback:
                self.on_lens_selected_callback(self.selected_lens)
    
    def create_new_lens(self):
        """Create a new lens and notify parent"""
        if self.on_create_new_callback:
            self.on_create_new_callback()
    
    def delete_lens(self):
        """Delete selected lens and notify parent"""
        if not self.listbox:
            return
            
        selection = self.listbox.curselection()
        if not selection:
            return
        
        index = selection[0]
        if 0 <= index < len(self.lens_list):
            lens = self.lens_list[index]
            if self.on_delete_callback:
                self.on_delete_callback(lens)
                self.refresh_lens_list()
                
                # Clear info panel
                if self.info_text:
                    self.info_text.config(state='normal')
                    self.info_text.delete(1.0, tk.END)
                    self.info_text.insert(1.0, "Select a lens to view details")
                    self.info_text.config(state='disabled')
    
    def export_lens(self):
        """Export selected lens via callback"""
        if self.on_export_callback:
            if not self.listbox:
                if self.selected_lens:
                    self.on_export_callback(self.selected_lens)
                return

            selection = self.listbox.curselection()
            if not selection:
                # If no selection in listbox, try using selected_lens
                if self.selected_lens:
                    self.on_export_callback(self.selected_lens)
                return
            
            index = selection[0]
            if 0 <= index < len(self.lens_list):
                lens = self.lens_list[index]
                self.on_export_callback(lens)
    
    def create_new_system(self):
        """Create a new optical system and notify parent"""
        if self.on_create_system_callback:
            self.on_create_system_callback()

    def save_current_system(self):
        """Save the currently selected temporary system as a permanent one"""
        if not self.selected_lens or not hasattr(self.selected_lens, 'elements'):
            return

        # It's a system.
        # Ensure it has an ID (it should from OpticalSystem.__init__)
        if not hasattr(self.selected_lens, 'id'):
            from datetime import datetime
            self.selected_lens.id = datetime.now().strftime("%Y%m%d%H%M%S%f")
            
        # Give it a name if it's default
        if self.selected_lens.name == "Multi-Lens System":
             self.selected_lens.name = f"System {self.selected_lens.id[-4:]}"
             
        # Add to list via callback
        if self.on_lens_updated_callback:
            self.on_lens_updated_callback(self.selected_lens)
            self.refresh_lens_list()
            
            # Try to select it in the list
            # Find index by ID
            if self.listbox:
                for i, item in enumerate(self.lens_list):
                     if hasattr(item, 'id') and item.id == self.selected_lens.id:
                          self.listbox.selection_clear(0, tk.END)
                          self.listbox.selection_set(i)
                          self.listbox.see(i)
                          self.update_info() # Update buttons state
                          break


class LensEditorController:
    """
    Controller for lens property editing.
    
    Responsibilities:
    - Manage lens property input fields
    - Validate and update lens properties
    - Calculate optical properties
    - Handle auto-update mode
    """
    
    def __init__(self, colors: dict, on_lens_updated: Optional[Callable] = None):
        """
        Initialize the lens editor controller.
        
        Args:
            colors: Color scheme dictionary
            on_lens_updated: Callback when lens is updated (lens) -> None
        """
        self.colors = colors
        self.on_lens_updated_callback = on_lens_updated
        self.parent_window: Optional['LensEditorWindow'] = None
        self.current_lens = None
        self.entry_fields = {}
        self.result_labels = {}
        self.auto_update_var = None
        self.material_var = None
        self.material_menu = None
        self._autosave_timer = None
        self._initializing = False
    
    def setup_ui(self, parent_frame):
        """Set up the editor tab UI"""
        self._initializing = True
        # Import constants with fallbacks
        try:
            from constants import (PADDING_SMALL, PADDING_MEDIUM, PADDING_LARGE,
                                 FONT_FAMILY, FONT_SIZE_NORMAL, FONT_SIZE_LARGE)
        except ImportError:
            PADDING_SMALL, PADDING_MEDIUM, PADDING_LARGE = 5, 10, 15
            FONT_FAMILY, FONT_SIZE_NORMAL, FONT_SIZE_LARGE = 'Arial', 10, 12
        
        # Main container with scrollbar
        canvas = tk.Canvas(parent_frame, bg=self.colors['bg'])
        scrollbar = ttk.Scrollbar(parent_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Properties frame
        props_frame = ttk.LabelFrame(scrollable_frame, text="Lens Properties", padding=PADDING_MEDIUM)
        props_frame.grid(row=0, column=0, sticky="nsew", padx=PADDING_SMALL, pady=PADDING_SMALL)
        
        # Create input fields
        self.create_property_fields(props_frame)
        
        # Material selection
        material_frame = ttk.LabelFrame(scrollable_frame, text="Material", padding=PADDING_MEDIUM)
        material_frame.grid(row=1, column=0, sticky="ew", padx=PADDING_SMALL, pady=PADDING_SMALL)
        self.create_material_selector(material_frame)
        
        # Fresnel lens section
        fresnel_frame = ttk.LabelFrame(scrollable_frame, text="Fresnel Properties", padding=PADDING_MEDIUM)
        fresnel_frame.grid(row=2, column=0, sticky="ew", padx=PADDING_SMALL, pady=PADDING_SMALL)
        self.create_fresnel_fields(fresnel_frame)
        
        # Results frame
        results_frame = ttk.LabelFrame(scrollable_frame, text="Calculated Properties", padding=PADDING_MEDIUM)
        results_frame.grid(row=3, column=0, sticky="ew", padx=PADDING_SMALL, pady=PADDING_SMALL)
        
        # Create result labels
        self.create_result_fields(results_frame)
        
        # Control buttons
        button_frame = ttk.Frame(scrollable_frame)
        button_frame.grid(row=4, column=0, sticky="ew", padx=PADDING_SMALL, pady=PADDING_MEDIUM)
        
        ttk.Button(button_frame, text="Calculate", 
                  command=self.calculate_properties, width=15).pack(side=tk.LEFT, padx=PADDING_SMALL)
        ttk.Button(button_frame, text="Save Changes", 
                  command=self.save_changes, width=15).pack(side=tk.LEFT, padx=PADDING_SMALL)
        ttk.Button(button_frame, text="Reset", 
                  command=self.reset_fields, width=15).pack(side=tk.LEFT, padx=PADDING_SMALL)
        
        # Auto-update checkbox
        self.auto_update_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(button_frame, text="Auto-calculate", 
                       variable=self.auto_update_var).pack(side=tk.LEFT, padx=PADDING_MEDIUM)
        
        self._initializing = False
    
    def create_property_fields(self, parent):
        """Create input fields for lens properties"""
        try:
            from constants import PADDING_SMALL
        except ImportError:
            PADDING_SMALL = 5
        
        fields = [
            ("Name:", "name", "New Lens"),
            ("Lens Type:", "lens_type", "Biconvex"),
            ("Radius 1 (mm):", "radius1", "100.0"),
            ("Radius 2 (mm):", "radius2", "-100.0"),
            ("Thickness (mm):", "thickness", "5.0"),
            ("Diameter (mm):", "diameter", "50.0"),
            ("Refractive Index:", "n", "1.5168"),
        ]
        
        for i, (label_text, key, default) in enumerate(fields):
            ttk.Label(parent, text=label_text).grid(row=i, column=0, sticky=tk.W, pady=PADDING_SMALL)
            
            if key == "lens_type":
                # Dropdown for lens type
                lens_types = ["Biconvex", "Biconcave", "Plano-Convex", "Plano-Concave", 
                             "Meniscus Convex", "Meniscus Concave"]
                combo = ttk.Combobox(parent, values=lens_types, width=18, state="readonly")
                combo.set(default)
                combo.grid(row=i, column=1, sticky="ew", padx=PADDING_SMALL, pady=PADDING_SMALL)
                combo.bind('<<ComboboxSelected>>', self.on_field_changed)
                self.entry_fields[key] = combo
            else:
                entry = ttk.Entry(parent, width=20)
                entry.grid(row=i, column=1, sticky="ew", padx=PADDING_SMALL, pady=PADDING_SMALL)
                entry.insert(0, default)
                
                # Bind auto-calculate (but not for name field)
                if key != "name":
                    entry.bind('<KeyRelease>', self.on_field_changed)
                
                self.entry_fields[key] = entry
        
        parent.columnconfigure(1, weight=1)
    
    def create_material_selector(self, parent):
        """Create material selection dropdown"""
        try:
            from constants import PADDING_SMALL
        except ImportError:
            PADDING_SMALL = 5
        
        ttk.Label(parent, text="Material:").grid(row=0, column=0, sticky=tk.W, pady=PADDING_SMALL)
        
        # Common optical materials
        materials = ["BK7", "SF11", "F2", "N-BK7", "Fused Silica", "Custom"]
        self.material_var = tk.StringVar(value="BK7")
        
        self.material_menu = ttk.Combobox(parent, textvariable=self.material_var, 
                                          values=materials, width=18, state="readonly")
        self.material_menu.grid(row=0, column=1, sticky="ew", padx=PADDING_SMALL, pady=PADDING_SMALL)
        self.material_menu.bind('<<ComboboxSelected>>', self.on_material_changed)
        
        parent.columnconfigure(1, weight=1)
    
    def create_fresnel_fields(self, parent):
        """Create input fields for Fresnel properties"""
        try:
            from constants import PADDING_SMALL
        except ImportError:
            PADDING_SMALL = 5
        
        # Fresnel toggle
        self.entry_fields['is_fresnel'] = tk.BooleanVar(value=False)
        fresnel_check = ttk.Checkbutton(parent, text="Enable Fresnel Lens", 
                                       variable=self.entry_fields['is_fresnel'],
                                       command=self.on_fresnel_toggle)
        fresnel_check.grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=PADDING_SMALL)
        
        # Groove pitch
        ttk.Label(parent, text="Groove Pitch (mm):").grid(row=1, column=0, sticky=tk.W, pady=PADDING_SMALL)
        self.entry_fields['groove_pitch'] = ttk.Entry(parent, width=20)
        self.entry_fields['groove_pitch'].grid(row=1, column=1, sticky="ew", padx=PADDING_SMALL, pady=PADDING_SMALL)
        self.entry_fields['groove_pitch'].insert(0, "0.5")
        self.entry_fields['groove_pitch'].bind('<KeyRelease>', self.on_field_changed)
        
        # Number of grooves (readonly)
        ttk.Label(parent, text="Number of Grooves:").grid(row=2, column=0, sticky=tk.W, pady=PADDING_SMALL)
        self.entry_fields['num_grooves'] = ttk.Entry(parent, width=20, state='readonly')
        self.entry_fields['num_grooves'].grid(row=2, column=1, sticky="ew", padx=PADDING_SMALL, pady=PADDING_SMALL)
        
        parent.columnconfigure(1, weight=1)
        
        # Initial state
        self.on_fresnel_toggle()
    
    def on_fresnel_toggle(self):
        """Handle Fresnel checkbox toggle"""
        is_fresnel = self.entry_fields['is_fresnel'].get()
        state = 'normal' if is_fresnel else 'disabled'
        
        if 'groove_pitch' in self.entry_fields:
            self.entry_fields['groove_pitch'].config(state=state)
        
        self.on_field_changed()
    
    def on_material_changed(self, event=None):
        """Update refractive index when material changes"""
        material_indices = {
            "BK7": 1.5168,
            "SF11": 1.7847,
            "F2": 1.6200,
            "N-BK7": 1.5168,
            "Fused Silica": 1.4585,
            "Custom": 1.5000
        }
        
        material = self.material_var.get()
        if material in material_indices:
            self.entry_fields['n'].delete(0, tk.END)
            self.entry_fields['n'].insert(0, str(material_indices[material]))
            self.on_field_changed()
    
    def create_result_fields(self, parent):
        """Create labels for calculated results"""
        try:
            from constants import PADDING_SMALL
        except ImportError:
            PADDING_SMALL = 5
        
        results = [
            ("Focal Length:", "focal_length", "mm"),
            ("Optical Power:", "power", "D"),
            ("Back Focal Length:", "bfl", "mm"),
            ("Front Focal Length:", "ffl", "mm"),
        ]
        
        for i, (label_text, key, unit) in enumerate(results):
            ttk.Label(parent, text=label_text).grid(row=i, column=0, sticky=tk.W, pady=PADDING_SMALL)
            
            value_label = ttk.Label(parent, text="N/A", font=('Arial', 10, 'bold'))
            value_label.grid(row=i, column=1, sticky=tk.W, padx=10, pady=PADDING_SMALL)
            
            ttk.Label(parent, text=unit).grid(row=i, column=2, sticky=tk.W, pady=PADDING_SMALL)
            
            self.result_labels[key] = value_label
        
        parent.columnconfigure(1, weight=1)
    
    def load_lens(self, lens):
        """Load lens data into editor fields"""
        self.current_lens = lens
        
        if lens is None:
            self.clear_fields()
            return
        
        # Handle both Lens objects and dicts
        if isinstance(lens, dict):
            name = lens.get('name', 'Unknown')
            lens_type = lens.get('type', 'Biconvex')
            radius1 = lens.get('radius1', 100)
            radius2 = lens.get('radius2', -100)
            thickness = lens.get('thickness', 10)
            diameter = lens.get('diameter', 50)
            refractive_index = lens.get('refractive_index', 1.5)
            material = lens.get('material', 'BK7')
            is_fresnel = lens.get('is_fresnel', False)
            groove_pitch = lens.get('groove_pitch', 0.5)
        else:
            name = lens.name
            lens_type = lens.lens_type if hasattr(lens, 'lens_type') else "Biconvex"
            radius1 = lens.radius_of_curvature_1
            radius2 = lens.radius_of_curvature_2
            thickness = lens.thickness
            diameter = lens.diameter
            refractive_index = lens.refractive_index
            material = lens.material if hasattr(lens, 'material') else 'BK7'
            is_fresnel = lens.is_fresnel if hasattr(lens, 'is_fresnel') else False
            groove_pitch = lens.groove_pitch if hasattr(lens, 'groove_pitch') else 0.5
        
        self.entry_fields['name'].delete(0, tk.END)
        self.entry_fields['name'].insert(0, name)
        
        if 'lens_type' in self.entry_fields:
            self.entry_fields['lens_type'].set(lens_type)
        
        self.entry_fields['radius1'].delete(0, tk.END)
        self.entry_fields['radius1'].insert(0, str(radius1))
        
        self.entry_fields['radius2'].delete(0, tk.END)
        self.entry_fields['radius2'].insert(0, str(radius2))
        
        self.entry_fields['thickness'].delete(0, tk.END)
        self.entry_fields['thickness'].insert(0, str(thickness))
        
        self.entry_fields['diameter'].delete(0, tk.END)
        self.entry_fields['diameter'].insert(0, str(diameter))
        
        self.entry_fields['n'].delete(0, tk.END)
        self.entry_fields['n'].insert(0, str(refractive_index))
        
        # Fresnel fields
        if 'is_fresnel' in self.entry_fields:
            self.entry_fields['is_fresnel'].set(is_fresnel)
            self.on_fresnel_toggle()
            
        if 'groove_pitch' in self.entry_fields:
            self.entry_fields['groove_pitch'].delete(0, tk.END)
            self.entry_fields['groove_pitch'].insert(0, str(groove_pitch))
        
        # Set material if available
        if self.material_var:
            self.material_var.set(material)
        
        self.calculate_properties()
    
    def clear_fields(self):
        """Clear all input fields"""
        for key, entry in self.entry_fields.items():
            if isinstance(entry, (tk.Entry, ttk.Entry, ttk.Combobox)):
                entry.delete(0, tk.END)
            elif isinstance(entry, tk.BooleanVar):
                entry.set(False)
            # Handle other widget types if needed
        
        for label in self.result_labels.values():
            label.config(text="N/A")
    
    def on_field_changed(self, event=None):
        """Handle field change event for auto-calculation and autosave"""
        if getattr(self, '_initializing', False):
            return

        if self.auto_update_var and self.auto_update_var.get():
            self.calculate_properties()
        
        self.start_autosave_timer()

    def start_autosave_timer(self):
        """Start or reset the autosave timer (2 seconds)"""
        # Cancel existing timer if any
        if self._autosave_timer and self.entry_fields:
            try:
                # Use any widget to cancel the timer
                widget = next(iter(self.entry_fields.values()))
                if isinstance(widget, (tk.Widget, ttk.Widget)):
                    widget.after_cancel(self._autosave_timer)
            except (tk.TclError, ValueError, StopIteration):
                pass
            self._autosave_timer = None
        
        # Start new timer
        if self.entry_fields:
            try:
                widget = next(iter(self.entry_fields.values()))
                if isinstance(widget, (tk.Widget, ttk.Widget)):
                    # Save silently after delay
                    self._autosave_timer = widget.after(2000, lambda: self.save_changes(silent=True))
            except (StopIteration, tk.TclError):
                pass
    
    def calculate_properties(self):
        """Calculate optical properties from current field values"""
        try:
            # Get values from fields
            r1 = float(self.entry_fields['radius1'].get())
            r2 = float(self.entry_fields['radius2'].get())
            t = float(self.entry_fields['thickness'].get())
            n = float(self.entry_fields['n'].get())
            
            # Calculate using lensmaker's equation
            power1 = (n - 1) / r1
            power2 = -(n - 1) / r2
            power_spacing = (n - 1) * (n - 1) * t / (n * r1 * r2)
            total_power = power1 + power2 + power_spacing
            
            if abs(total_power) < 1e-10:
                focal_length = float('inf')
                power_diopters = 0.0
            else:
                focal_length = 1.0 / total_power
                power_diopters = 1000.0 / focal_length
            
            # Calculate back and front focal lengths
            if abs(total_power) < 1e-10:
                bfl = float('inf')
                ffl = float('inf')
            else:
                bfl = (1.0 - power2 * t) / total_power
                ffl = (1.0 - power1 * t) / total_power
            
            # Update result labels
            if abs(focal_length) > 10000:
                self.result_labels['focal_length'].config(text="∞")
            else:
                self.result_labels['focal_length'].config(text=f"{focal_length:.3f}")
            
            self.result_labels['power'].config(text=f"{power_diopters:.3f}")
            
            if abs(bfl) > 10000:
                self.result_labels['bfl'].config(text="∞")
            else:
                self.result_labels['bfl'].config(text=f"{bfl:.3f}")
            
            if abs(ffl) > 10000:
                self.result_labels['ffl'].config(text="∞")
            else:
                self.result_labels['ffl'].config(text=f"{ffl:.3f}")
            
        except ValueError:
            for key in ['focal_length', 'power', 'bfl', 'ffl']:
                if key in self.result_labels:
                    self.result_labels[key].config(text="Invalid")
        except ZeroDivisionError:
            self.result_labels['focal_length'].config(text="∞")
            self.result_labels['power'].config(text="0.000")
            self.result_labels['bfl'].config(text="∞")
            self.result_labels['ffl'].config(text="∞")
    
    def save_changes(self, silent: bool = False):
        """Save changes to the current lens"""
        # If no lens selected, create a new one
        if self.current_lens is None:
            try:
                from lens import Lens
                # Create a new lens with default values which will be overwritten below
                self.current_lens = Lens()
                logger.info("Created new lens object for saving")
            except ImportError:
                if not silent:
                    try:
                        from tkinter import messagebox
                        CopyableMessageBox.showerror(self.parent_window.root if hasattr(self, "parent_window") and self.parent_window else None, "Error", "Could not import Lens class")
                    except Exception:
                        pass
                return
        
        try:
            # Validate and update lens
            self.current_lens.name = self.entry_fields['name'].get()
            if 'lens_type' in self.entry_fields:
                self.current_lens.lens_type = self.entry_fields['lens_type'].get()
            
            self.current_lens.radius_of_curvature_1 = float(self.entry_fields['radius1'].get())
            self.current_lens.radius_of_curvature_2 = float(self.entry_fields['radius2'].get())
            self.current_lens.thickness = float(self.entry_fields['thickness'].get())
            self.current_lens.diameter = float(self.entry_fields['diameter'].get())
            self.current_lens.refractive_index = float(self.entry_fields['n'].get())
            
            if self.material_var:
                self.current_lens.material = self.material_var.get()
            
            # Save Fresnel properties
            if 'is_fresnel' in self.entry_fields:
                self.current_lens.is_fresnel = self.entry_fields['is_fresnel'].get()
            
            if 'groove_pitch' in self.entry_fields:
                try:
                    self.current_lens.groove_pitch = float(self.entry_fields['groove_pitch'].get())
                    self.current_lens.calculate_num_grooves()
                    
                    # Update readonly field
                    if 'num_grooves' in self.entry_fields:
                        self.entry_fields['num_grooves'].config(state='normal')
                        self.entry_fields['num_grooves'].delete(0, tk.END)
                        self.entry_fields['num_grooves'].insert(0, str(self.current_lens.num_grooves))
                        self.entry_fields['num_grooves'].config(state='readonly')
                except ValueError:
                    pass  # Ignore invalid pitch during save (will be caught by validation)

            # Update timestamp
            from datetime import datetime
            self.current_lens.modified_at = datetime.now().isoformat()
            
            # Notify parent
            if self.on_lens_updated_callback:
                self.on_lens_updated_callback(self.current_lens)
            
            if not silent:
                try:
                    from tkinter import messagebox
                    CopyableMessageBox.showinfo(self.parent_window.root if hasattr(self, "parent_window") and self.parent_window else None, "Success", "Lens updated successfully")
                except Exception as e:
                    logger.debug(f"Failed to show success dialog: {e}")
            
        except ValueError as e:
            if not silent:
                try:
                    from tkinter import messagebox
                    CopyableMessageBox.showerror(self.parent_window.root if hasattr(self, "parent_window") and self.parent_window else None, "Invalid Input", f"Please check your input values: {e}")
                except Exception as dialog_error:
                    logger.warning(f"Failed to show error dialog: {dialog_error}")
            else:
                logger.warning(f"Autosave failed due to invalid input: {e}")
    
    def reset_fields(self):
        """Reset fields to original lens values"""
        if self.current_lens:
            self.load_lens(self.current_lens)
        else:
            self.clear_fields()


class SimulationController:
    """
    Controller for ray tracing and simulation visualization.
    
    Responsibilities:
    - Manage ray tracing simulation
    - Control simulation parameters
    - Display ray tracing results
    - Update visualization
    """
    
    def __init__(self, colors: dict, visualization_available: bool = True):
        """
        Initialize the simulation controller.
        
        Args:
            colors: Color scheme dictionary
            visualization_available: Whether matplotlib is available
        """
        self.colors = colors
        self.visualization_available = visualization_available
        self.parent_window: Optional['LensEditorWindow'] = None
        self.current_lens = None
        self.ray_tracer = None
        
        # UI elements
        self.sim_figure = None
        self.sim_ax = None
        self.sim_canvas = None
        self.sim_canvas_widget = None
        self.num_rays_var = None
        self.ray_angle_var = None
        self.system_builder_frame = None
        self.element_listbox = None
    
    def setup_ui(self, parent_frame):
        """Set up the simulation tab UI"""
        # Import constants with fallbacks
        try:
            from constants import (PADDING_SMALL, PADDING_MEDIUM, PADDING_LARGE,
                                 FONT_FAMILY, FONT_SIZE_NORMAL, FONT_SIZE_TITLE,
                                 COLOR_BG_DARK, COLOR_BG_LIGHT, COLOR_FG,
                                 DEFAULT_NUM_RAYS)
        except ImportError:
            PADDING_SMALL, PADDING_MEDIUM, PADDING_LARGE = 5, 10, 15
            FONT_FAMILY, FONT_SIZE_NORMAL, FONT_SIZE_TITLE = 'Arial', 10, 14
            COLOR_BG_DARK, COLOR_BG_LIGHT, COLOR_FG = '#2b2b2b', '#3f3f3f', '#e0e0e0'
            DEFAULT_NUM_RAYS = 11
        
        # Configure parent frame
        parent_frame.columnconfigure(0, weight=1)
        parent_frame.rowconfigure(1, weight=1)
        
        # Title
        title_label = ttk.Label(parent_frame, text="Optical Simulation", 
                               font=(FONT_FAMILY, 14, 'bold'))
        title_label.grid(row=0, column=0, pady=PADDING_MEDIUM)
        
        # Simulation canvas area
        sim_frame = ttk.LabelFrame(parent_frame, text="Ray Tracing Simulation", 
                                  padding=PADDING_MEDIUM, height=450)
        sim_frame.grid(row=1, column=0, sticky="nsew", pady=PADDING_MEDIUM)
        sim_frame.columnconfigure(0, weight=1)
        sim_frame.rowconfigure(0, weight=1)
        sim_frame.grid_propagate(False)
        
        # Create visualization if available
        if self.visualization_available:
            try:
                from matplotlib.figure import Figure
                from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
                
                self.sim_figure = Figure(figsize=(12, 6), dpi=100, facecolor=COLOR_BG_DARK)
                self.sim_figure.subplots_adjust(left=0.08, right=0.95, top=0.93, bottom=0.10)
                self.sim_ax = self.sim_figure.add_subplot(111, facecolor=COLOR_BG_DARK)
                
                # Configure axes
                self.sim_ax.set_xlim(-100, 150)
                self.sim_ax.set_ylim(-30, 30)
                self.sim_ax.axhline(y=0, color='gray', linestyle='--', linewidth=1, alpha=0.3)
                self.sim_ax.set_xlabel('Position (mm)', fontsize=FONT_SIZE_NORMAL, color=COLOR_FG)
                self.sim_ax.set_ylabel('Height (mm)', fontsize=FONT_SIZE_NORMAL, color=COLOR_FG)
                self.sim_ax.set_title('Ray Tracing Simulation\n(Select a lens and click "Run Simulation")', 
                                    fontsize=FONT_SIZE_TITLE, color=COLOR_FG)
                self.sim_ax.grid(True, alpha=0.2, color=COLOR_BG_LIGHT)
                self.sim_ax.set_aspect('equal')
                
                # Style the plot
                self.sim_ax.tick_params(colors=COLOR_FG, labelsize=9)
                for spine in self.sim_ax.spines.values():
                    spine.set_color(COLOR_BG_LIGHT)
                
                # Create canvas
                self.sim_canvas = FigureCanvasTkAgg(self.sim_figure, sim_frame)
                self.sim_canvas_widget = self.sim_canvas.get_tk_widget()
                self.sim_canvas_widget.pack(fill='both', expand=True)
                self.sim_canvas.draw()
                
            except Exception as e:
                ttk.Label(sim_frame, text=f"Simulation error: {e}", 
                         wraplength=400).pack(pady=PADDING_LARGE)
        else:
            msg = "Simulation not available.\n\nInstall dependencies:\n  pip install matplotlib numpy"
            ttk.Label(sim_frame, text=msg, justify=tk.CENTER, 
                     font=(FONT_FAMILY, FONT_SIZE_NORMAL)).pack(pady=PADDING_SMALL)
        
        # Simulation controls
        controls_frame = ttk.LabelFrame(parent_frame, text="Simulation Controls", 
                                       padding=PADDING_MEDIUM)
        controls_frame.grid(row=2, column=0, sticky="ew", pady=PADDING_MEDIUM)
        
        # Ray parameters
        ttk.Label(controls_frame, text="Number of Rays:").grid(
            row=0, column=0, sticky=tk.W, padx=PADDING_SMALL, pady=PADDING_SMALL)
        self.num_rays_var = tk.StringVar(value=str(DEFAULT_NUM_RAYS))
        ttk.Entry(controls_frame, textvariable=self.num_rays_var, width=10).grid(
            row=0, column=1, sticky=tk.W, padx=PADDING_SMALL, pady=PADDING_SMALL)
        
        ttk.Label(controls_frame, text="Ray Angle (degrees):").grid(
            row=0, column=2, sticky=tk.W, padx=PADDING_SMALL, pady=PADDING_SMALL)
        self.ray_angle_var = tk.StringVar(value="0")
        ttk.Entry(controls_frame, textvariable=self.ray_angle_var, width=10).grid(
            row=0, column=3, sticky=tk.W, padx=PADDING_SMALL, pady=PADDING_SMALL)
        
        # Buttons
        btn_frame = ttk.Frame(controls_frame)
        btn_frame.grid(row=1, column=0, columnspan=4, pady=PADDING_MEDIUM)
        
        ttk.Button(btn_frame, text="Run Simulation", 
                  command=self.run_simulation).pack(side=tk.LEFT, padx=PADDING_SMALL)
        ttk.Button(btn_frame, text="Clear Simulation", 
                  command=self.clear_simulation).pack(side=tk.LEFT, padx=PADDING_SMALL)
    
    def load_lens(self, lens):
        """Load lens for simulation"""
        self.current_lens = lens
        
        # Clear previous system builder if exists
        if hasattr(self, 'system_builder_frame') and self.system_builder_frame:
            self.system_builder_frame.destroy()
            del self.system_builder_frame

        # Check if it's an OpticalSystem
        is_system = hasattr(lens, 'elements') and hasattr(lens, 'air_gaps')
        
        # Create ray tracer if dependencies available
        try:
            if is_system:
                from ray_tracer import SystemRayTracer
                self.ray_tracer = SystemRayTracer(lens)
                self.create_system_builder_ui()
            else:
                from ray_tracer import LensRayTracer
                if lens:
                    self.ray_tracer = LensRayTracer(lens)
                else:
                    self.ray_tracer = None
        except (ImportError, AttributeError):
            # ImportError: ray_tracer module not available
            # AttributeError: lens is not proper Lens object
            self.ray_tracer = None

    def create_system_builder_ui(self):
        """Create UI for editing optical system (reorder, air gaps)"""
        # Find the parent frame (simulation tab)
        # We need to access the parent frame passed in setup_ui. 
        # Since we didn't save it, we can look at sim_frame's parent.
        if not self.sim_canvas_widget:
            return
            
        parent = self.sim_canvas_widget.master.master # Canvas -> Frame -> Parent
        
        self.system_builder_frame = ttk.LabelFrame(parent, text="System Builder", padding="10")
        self.system_builder_frame.grid(row=1, column=1, sticky="nsew", padx=10, pady=10)
        
        # List of elements
        self.element_listbox = tk.Listbox(self.system_builder_frame, height=10, width=30)
        self.element_listbox.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.element_listbox.bind('<<ListboxSelect>>', self.on_element_selected)
        
        # Controls
        btn_frame = ttk.Frame(self.system_builder_frame)
        btn_frame.pack(side=tk.TOP, fill=tk.X, pady=5)
        
        ttk.Button(btn_frame, text="Add Lens", command=self.add_element).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Remove", command=self.remove_element).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Move Up", command=self.move_element_up).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Move Down", command=self.move_element_down).pack(side=tk.LEFT, padx=2)
        
        # Air Gap Control
        gap_frame = ttk.Frame(self.system_builder_frame)
        gap_frame.pack(side=tk.TOP, fill=tk.X, pady=10)
        
        ttk.Label(gap_frame, text="Air Gap (mm):").pack(side=tk.LEFT)
        self.gap_var = tk.StringVar()
        self.gap_entry = ttk.Entry(gap_frame, textvariable=self.gap_var, width=8)
        self.gap_entry.pack(side=tk.LEFT, padx=5)
        self.gap_entry.bind('<Return>', self.update_air_gap)
        ttk.Button(gap_frame, text="Set", command=self.update_air_gap).pack(side=tk.LEFT)
        
        self.refresh_system_list()

    def refresh_system_list(self):
        """Refresh the list of elements in system builder"""
        if not self.element_listbox or not self.current_lens:
            return
        
        self.element_listbox.delete(0, tk.END)
        for i, element in enumerate(self.current_lens.elements):
            name = element.lens.name
            gap = 0.0
            if i > 0 and i-1 < len(self.current_lens.air_gaps):
                 gap = self.current_lens.air_gaps[i-1].thickness
            
            if i == 0:
                text = f"{i+1}. {name}"
            else:
                text = f"{i+1}. {name} (Gap: {gap:.2f}mm)"
            self.element_listbox.insert(tk.END, text)

    def add_element(self):
        """Open dialog to add a lens to the system"""
        if not self.parent_window or not hasattr(self.parent_window, 'lenses'):
            return
            
        # Create dialog
        dialog = tk.Toplevel(self.parent_window.root)
        dialog.title("Add Lens to System")
        # Center dialog
        x = self.parent_window.root.winfo_x() + 100
        y = self.parent_window.root.winfo_y() + 100
        dialog.geometry(f"300x150+{x}+{y}")
        dialog.transient(self.parent_window.root)
        dialog.grab_set()
        
        ttk.Label(dialog, text="Select Lens to Add:").pack(pady=10)
        
        # Filter available lenses (exclude systems to prevent recursion)
        available_lenses = []
        lens_map = {} # map name -> lens object
        
        for item in self.parent_window.lenses:
            # Check if it's a single lens (has no elements attribute)
            if not hasattr(item, 'elements'):
                name = item.name
                available_lenses.append(name)
                lens_map[name] = item
                
        if not available_lenses:
             ttk.Label(dialog, text="No single lenses available.\nCreate a lens first.").pack()
             ttk.Button(dialog, text="Close", command=dialog.destroy).pack(pady=10)
             return

        combo = ttk.Combobox(dialog, values=available_lenses, state="readonly")
        combo.pack(pady=5, padx=20, fill=tk.X)
        if available_lenses:
            combo.set(available_lenses[0])
            
        def on_add():
            name = combo.get()
            if name in lens_map:
                lens = lens_map[name]
                # Add to system with default gap
                if self.current_lens and hasattr(self.current_lens, 'add_lens'):
                    self.current_lens.add_lens(lens, air_gap_before=5.0)
                    self.refresh_system_list()
                    self.run_simulation()
                    
                    # Also notify parent window that lens was updated (to save)
                    if hasattr(self.parent_window, 'save_lenses'):
                        self.parent_window.save_lenses()
                        
                dialog.destroy()
                
        ttk.Button(dialog, text="Add", command=on_add).pack(pady=10)

    def remove_element(self):
        """Remove selected element from system"""
        if not self.element_listbox or not self.current_lens:
            return
            
        selection = self.element_listbox.curselection()
        if not selection:
            return
            
        index = selection[0]
        if hasattr(self.current_lens, 'remove_lens'):
            if self.current_lens.remove_lens(index):
                self.refresh_system_list()
                self.run_simulation()
                
                # Notify parent to save
                if self.parent_window and hasattr(self.parent_window, 'save_lenses'):
                    self.parent_window.save_lenses()

    def on_element_selected(self, event):
        """Update gap entry when element selected"""
        if not self.element_listbox:
            return
            
        selection = self.element_listbox.curselection()
        if not selection:
            return
            
        index = selection[0]
        # Show gap BEFORE this element
        if index > 0 and index-1 < len(self.current_lens.air_gaps):
            gap = self.current_lens.air_gaps[index-1].thickness
            self.gap_var.set(str(gap))
            self.gap_entry.config(state='normal')
        else:
            self.gap_var.set("")
            self.gap_entry.config(state='disabled')

    def update_air_gap(self, event=None):
        """Update air gap based on entry"""
        if not self.element_listbox:
            return
            
        selection = self.element_listbox.curselection()
        if not selection:
            return
            
        index = selection[0]
        if index > 0:
            try:
                new_gap = float(self.gap_var.get())
                if index-1 < len(self.current_lens.air_gaps):
                    self.current_lens.air_gaps[index-1].thickness = new_gap
                    self.current_lens._update_positions()
                    self.refresh_system_list()
                    # Re-run simulation automatically
                    self.run_simulation()
            except ValueError:
                pass

    def move_element_up(self):
        """Move selected element up in the sequence"""
        if not self.element_listbox:
            return

        selection = self.element_listbox.curselection()
        if not selection:
            return
        
        index = selection[0]
        if index > 0:
            # Swap elements
            self.current_lens.elements[index], self.current_lens.elements[index-1] = \
                self.current_lens.elements[index-1], self.current_lens.elements[index]
            
            # Rebuild air gaps to match new order (preserve gaps or reset? Let's preserve sequence of gaps)
            # Actually, gaps are between positions. If we move element, does it take its gap with it?
            # Simplest approach: gaps stay as structural positions.
            # Or: Gap is "gap before lens".
            
            # Let's just update positions and refresh
            self.current_lens._update_positions()
            self.refresh_system_list()
            self.element_listbox.selection_set(index-1)
            self.run_simulation()

    def move_element_down(self):
        """Move selected element down in the sequence"""
        if not self.element_listbox:
            return

        selection = self.element_listbox.curselection()
        if not selection:
            return
        
        index = selection[0]
        if index < len(self.current_lens.elements) - 1:
            # Swap elements
            self.current_lens.elements[index], self.current_lens.elements[index+1] = \
                self.current_lens.elements[index+1], self.current_lens.elements[index]
            
            self.current_lens._update_positions()
            self.refresh_system_list()
            self.element_listbox.selection_set(index+1)
            self.run_simulation()
    
    def run_simulation(self):
        """Run ray tracing simulation"""
        if self.current_lens is None:
            try:
                from tkinter import messagebox
                CopyableMessageBox.showwarning(self.parent_window.root if hasattr(self, "parent_window") and self.parent_window else None, "No Lens", "Please select a lens first")
            except Exception as e:
                logger.warning(f"Failed to show warning dialog: {e}")
            return
        
        if self.ray_tracer is None:
            try:
                from tkinter import messagebox
                CopyableMessageBox.showerror(self.parent_window.root if hasattr(self, "parent_window") and self.parent_window else None, "Unavailable", 
                                   "Ray tracing requires numpy. Install with: pip install numpy")
            except Exception as e:
                logger.warning(f"Failed to show error dialog: {e}")
            return
        
        try:
            num_rays = int(self.num_rays_var.get())
            ray_angle = float(self.ray_angle_var.get())
            
            # Trace rays
            rays = self.ray_tracer.trace_parallel_rays(num_rays=num_rays, angle=ray_angle)
            self.draw_rays(rays)
            
        except ValueError as e:
            try:
                from tkinter import messagebox
                CopyableMessageBox.showerror(self.parent_window.root if hasattr(self, "parent_window") and self.parent_window else None, "Invalid Input", f"Please check your input values: {e}")
            except Exception as dialog_error:
                logger.warning(f"Failed to show error dialog: {dialog_error}")
        except Exception as e:
            try:
                from tkinter import messagebox
                CopyableMessageBox.showerror(self.parent_window.root if hasattr(self, "parent_window") and self.parent_window else None, "Simulation Error", f"Error during simulation: {e}")
            except Exception as dialog_error:
                logger.error(f"Simulation failed: {e}, dialog error: {dialog_error}")
    
    def draw_rays(self, rays):
        """Draw ray paths on canvas"""
        if not self.sim_ax or not self.sim_canvas:
            return
        
        # Clear previous rays
        self.sim_ax.clear()
        
        # Import constants
        try:
            from constants import COLOR_BG_DARK, COLOR_BG_LIGHT, COLOR_FG, FONT_SIZE_NORMAL
        except ImportError:
            COLOR_BG_DARK, COLOR_BG_LIGHT, COLOR_FG = '#2b2b2b', '#3f3f3f', '#e0e0e0'
            FONT_SIZE_NORMAL = 10
        
        # Calculate bounds based on system
        is_system = hasattr(self.current_lens, 'elements')
        if is_system:
            total_length = self.current_lens.get_total_length()
            x_max = total_length + 50
            x_min = -50
            name = self.current_lens.name
        else:
            x_max = 150
            x_min = -100
            name = self.current_lens.name

        # Redraw axes
        self.sim_ax.set_xlim(x_min, x_max)
        self.sim_ax.set_ylim(-30, 30)
        self.sim_ax.axhline(y=0, color='gray', linestyle='--', linewidth=1, alpha=0.3)
        self.sim_ax.set_xlabel('Position (mm)', fontsize=FONT_SIZE_NORMAL, color=COLOR_FG)
        self.sim_ax.set_ylabel('Height (mm)', fontsize=FONT_SIZE_NORMAL, color=COLOR_FG)
        self.sim_ax.set_title(f'Ray Tracing - {name}', 
                            fontsize=12, color=COLOR_FG)
        self.sim_ax.grid(True, alpha=0.2, color=COLOR_BG_LIGHT)
        self.sim_ax.set_aspect('equal')
        self.sim_ax.tick_params(colors=COLOR_FG, labelsize=9)
        for spine in self.sim_ax.spines.values():
            spine.set_color(COLOR_BG_LIGHT)
        
        # Draw lens surfaces
        if is_system:
            self._draw_system()
        else:
            self._draw_lens()
        
        # Draw rays
        for ray in rays:
            if hasattr(ray, 'path') and ray.path:
                # Extract x and y coordinates from path list of tuples
                x_coords = [p[0] for p in ray.path]
                y_coords = [p[1] for p in ray.path]
                self.sim_ax.plot(x_coords, y_coords, 'b-', alpha=0.6, linewidth=1)
            elif isinstance(ray, dict) and 'segments' in ray:
                # Handle legacy dictionary format if present
                for segment in ray['segments']:
                    x_coords = [segment['start'][0], segment['end'][0]]
                    y_coords = [segment['start'][1], segment['end'][1]]
                    self.sim_ax.plot(x_coords, y_coords, 'b-', alpha=0.6, linewidth=1)
        
        # Redraw canvas
        self.sim_canvas.draw()
    
    def _draw_system(self):
        """Draw all lenses in the system"""
        if not self.current_lens:
            return
            
        for element in self.current_lens.elements:
            self._draw_single_lens_element(element.lens, element.position)

    def _draw_single_lens_element(self, lens, offset):
        """Helper to draw a single lens at an offset"""
        try:
            from ray_tracer import LensRayTracer
            tracer = LensRayTracer(lens, x_offset=offset)
            points = tracer.get_lens_outline(num_points=100)
            
            poly_x = [p[0] for p in points]
            poly_y = [p[1] for p in points]
            
            self.sim_ax.fill(poly_x, poly_y, facecolor='#e6f3ff', edgecolor='none', alpha=0.4)
            self.sim_ax.plot(poly_x, poly_y, 'k-', linewidth=1.5)
            
            # Draw center line (approximate from bounds)
            if poly_x:
                min_x = min(poly_x)
                max_x = max(poly_x)
                center_x = (min_x + max_x) / 2
                self.sim_ax.plot([center_x, center_x], [0, 0], 'k+', markersize=5, alpha=0.5)
                
        except ImportError:
            # Fallback to manual drawing if ray_tracer not available
            r1 = lens.radius_of_curvature_1
            r2 = lens.radius_of_curvature_2
            thickness = lens.thickness
            diameter = lens.diameter
            
            # Generate y coordinates for the lens aperture
            num_points = 100
            half_diam = diameter / 2.0
            y = [(-half_diam + i * diameter / (num_points - 1)) for i in range(num_points)]
            
            # Helper function
            def calculate_surface_x(r, y_val, is_front):
                if abs(r) > 10000 or abs(r) < 1e-10:
                    return offset if is_front else offset + float(thickness)
                
                r_abs = abs(r)
                if abs(y_val) >= r_abs:
                    sag_term = 0.0
                else:
                    sag_term = math.sqrt(r_abs**2 - y_val**2)
                
                if is_front:
                    if r > 0:
                        return offset - r_abs + sag_term
                    else:
                        return offset + r_abs - sag_term
                else:
                    if r > 0:
                        return offset + thickness + r_abs - sag_term
                    else:
                        return offset + thickness - r_abs + sag_term

            # Surface 1
            x1 = [calculate_surface_x(r1, y_val, is_front=True) for y_val in y]
            
            # Surface 2
            x2 = [calculate_surface_x(r2, y_val, is_front=False) for y_val in y]
            
            # Draw filled polygon
            poly_x = x1 + x2[::-1]
            poly_y = y + y[::-1]
            
            self.sim_ax.fill(poly_x, poly_y, facecolor='#e6f3ff', edgecolor='none', alpha=0.4)
            self.sim_ax.plot(poly_x, poly_y, 'k-', linewidth=1.5)

    def _draw_lens(self):
        """Draw lens outline on the plot (legacy wrapper)"""
        if not self.current_lens:
            return
        self._draw_single_lens_element(self.current_lens, 0.0)


    
    def clear_simulation(self):
        """Clear simulation canvas"""
        if not self.sim_ax or not self.sim_canvas:
            return
        
        self.sim_ax.clear()
        
        try:
            from constants import COLOR_BG_DARK, COLOR_BG_LIGHT, COLOR_FG, FONT_SIZE_NORMAL
        except ImportError:
            COLOR_BG_DARK, COLOR_BG_LIGHT, COLOR_FG = '#2b2b2b', '#3f3f3f', '#e0e0e0'
            FONT_SIZE_NORMAL = 10
        
        self.sim_ax.set_xlim(-100, 150)
        self.sim_ax.set_ylim(-30, 30)
        self.sim_ax.axhline(y=0, color='gray', linestyle='--', linewidth=1, alpha=0.3)
        self.sim_ax.set_xlabel('Position (mm)', fontsize=FONT_SIZE_NORMAL, color=COLOR_FG)
        self.sim_ax.set_ylabel('Height (mm)', fontsize=FONT_SIZE_NORMAL, color=COLOR_FG)
        self.sim_ax.set_title('Ray Tracing Simulation\n(Select a lens and click "Run Simulation")', 
                            fontsize=12, color=COLOR_FG)
        self.sim_ax.grid(True, alpha=0.2, color=COLOR_BG_LIGHT)
        self.sim_ax.set_aspect('equal')
        self.sim_ax.tick_params(colors=COLOR_FG, labelsize=9)
        for spine in self.sim_ax.spines.values():
            spine.set_color(COLOR_BG_LIGHT)
        
        self.sim_canvas.draw()


class PerformanceController:
    """
    Controller for aberration analysis and performance metrics.
    
    Responsibilities:
    - Display aberration calculations
    - Show performance metrics
    - Analyze lens quality
    - Export performance reports
    """
    
    def __init__(self, colors: dict, aberrations_available: bool = True):
        """
        Initialize the performance controller.
        
        Args:
            colors: Color scheme dictionary
            aberrations_available: Whether aberrations module is available
        """
        self.colors = colors
        self.aberrations_available = aberrations_available
        self.current_lens = None
        self.metrics_text = None
        
        # Parameter variables
        self.entrance_pupil_var = None
        self.wavelength_var = None
        self.object_distance_var = None
        self.sensor_size_var = None
    
    def setup_ui(self, parent_frame):
        """Set up the performance tab UI"""
        # Import constants with fallbacks
        try:
            from constants import (PADDING_SMALL, PADDING_MEDIUM,
                                 FONT_FAMILY, FONT_SIZE_NORMAL,
                                 WAVELENGTH_GREEN)
        except ImportError:
            PADDING_SMALL, PADDING_MEDIUM = 5, 10
            FONT_FAMILY, FONT_SIZE_NORMAL = 'Arial', 10
            WAVELENGTH_GREEN = 550
        
        # Configure parent frame
        parent_frame.columnconfigure(0, weight=1)
        parent_frame.rowconfigure(1, weight=1)
        
        # Title
        title_label = ttk.Label(parent_frame, text="Performance Metrics Dashboard", 
                               font=(FONT_FAMILY, 14, 'bold'))
        title_label.grid(row=0, column=0, pady=PADDING_MEDIUM)
        
        # Metrics display area
        metrics_frame = ttk.LabelFrame(parent_frame, text="Optical Performance Metrics", 
                                      padding=PADDING_MEDIUM)
        metrics_frame.grid(row=1, column=0, sticky="nsew", pady=PADDING_MEDIUM)
        metrics_frame.columnconfigure(0, weight=1)
        metrics_frame.rowconfigure(0, weight=1)
        
        # Text widget for metrics display
        metrics_scroll = ttk.Scrollbar(metrics_frame)
        metrics_scroll.grid(row=0, column=1, sticky="ns")
        
        self.metrics_text = tk.Text(metrics_frame, height=20, width=80,
                                   wrap=tk.WORD,
                                   bg=self.colors.get('entry_bg', '#2b2b2b'),
                                   fg=self.colors.get('fg', '#e0e0e0'),
                                   font=('Courier', 10),
                                   yscrollcommand=metrics_scroll.set)
        self.metrics_text.grid(row=0, column=0, sticky="nsew")
        metrics_scroll.config(command=self.metrics_text.yview)
        
        self.metrics_text.insert('1.0', "Select a lens and click 'Calculate Metrics' to view performance data.")
        self.metrics_text.config(state='disabled')
        
        # Controls
        controls_frame = ttk.LabelFrame(parent_frame, text="Calculation Parameters", 
                                       padding=PADDING_MEDIUM)
        controls_frame.grid(row=2, column=0, sticky="ew", pady=PADDING_MEDIUM)
        
        # Parameter inputs
        ttk.Label(controls_frame, text="Entrance Pupil Diameter (mm):").grid(
            row=0, column=0, sticky=tk.W, padx=PADDING_SMALL, pady=PADDING_SMALL)
        self.entrance_pupil_var = tk.StringVar(value="10.0")
        ttk.Entry(controls_frame, textvariable=self.entrance_pupil_var, width=15).grid(
            row=0, column=1, sticky=tk.W, padx=PADDING_SMALL, pady=PADDING_SMALL)
        
        ttk.Label(controls_frame, text="Wavelength (nm):").grid(
            row=0, column=2, sticky=tk.W, padx=PADDING_SMALL, pady=PADDING_SMALL)
        self.wavelength_var = tk.StringVar(value=str(int(WAVELENGTH_GREEN)))
        ttk.Entry(controls_frame, textvariable=self.wavelength_var, width=15).grid(
            row=0, column=3, sticky=tk.W, padx=PADDING_SMALL, pady=PADDING_SMALL)
        
        ttk.Label(controls_frame, text="Object Distance (mm):").grid(
            row=1, column=0, sticky=tk.W, padx=PADDING_SMALL, pady=PADDING_SMALL)
        self.object_distance_var = tk.StringVar(value="1000")
        ttk.Entry(controls_frame, textvariable=self.object_distance_var, width=15).grid(
            row=1, column=1, sticky=tk.W, padx=PADDING_SMALL, pady=PADDING_SMALL)
        
        ttk.Label(controls_frame, text="Sensor Size (mm):").grid(
            row=1, column=2, sticky=tk.W, padx=PADDING_SMALL, pady=PADDING_SMALL)
        self.sensor_size_var = tk.StringVar(value="36")
        ttk.Entry(controls_frame, textvariable=self.sensor_size_var, width=15).grid(
            row=1, column=3, sticky=tk.W, padx=PADDING_SMALL, pady=PADDING_SMALL)
        
        # Buttons
        btn_frame = ttk.Frame(controls_frame)
        btn_frame.grid(row=2, column=0, columnspan=4, pady=PADDING_MEDIUM)
        
        ttk.Button(btn_frame, text="Calculate Metrics", 
                  command=self.calculate_metrics).pack(side=tk.LEFT, padx=PADDING_SMALL)
        ttk.Button(btn_frame, text="Spot Diagram", 
                  command=self.show_spot_diagram).pack(side=tk.LEFT, padx=PADDING_SMALL)
        ttk.Button(btn_frame, text="Ghost Analysis", 
                  command=self.show_ghost_analysis).pack(side=tk.LEFT, padx=PADDING_SMALL)
        ttk.Button(btn_frame, text="PSF Analysis", 
                  command=self.show_psf).pack(side=tk.LEFT, padx=PADDING_SMALL)
        ttk.Button(btn_frame, text="MTF Analysis", 
                  command=self.show_mtf).pack(side=tk.LEFT, padx=PADDING_SMALL)
        ttk.Button(btn_frame, text="Wavefront Map", 
                  command=self.show_wavefront_map).pack(side=tk.LEFT, padx=PADDING_SMALL)
        ttk.Button(btn_frame, text="Image Simulation", 
                  command=self.show_image_simulation).pack(side=tk.LEFT, padx=PADDING_SMALL)
        ttk.Button(btn_frame, text="Export Report", 
                  command=self.export_report).pack(side=tk.LEFT, padx=PADDING_SMALL)
    
    def load_lens(self, lens):
        """Load lens for analysis"""
        self.current_lens = lens
    
    def show_spot_diagram(self):
        """Display Spot Diagram in a new window with multi-field/wavelength support"""
        if self.current_lens is None:
            root = self.parent_window.root if hasattr(self, "parent_window") and self.parent_window else None
            CopyableMessageBox.showwarning(root, "No Lens", "Please select a lens first")
            return

        try:
            import matplotlib.pyplot as plt
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            from matplotlib.figure import Figure
            import numpy as np
            
            # Import Analysis
            try:
                from .analysis import SpotDiagram
                from .optical_system import OpticalSystem
            except ImportError:
                # Fallback
                import sys
                import os
                sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
                from src.analysis import SpotDiagram
                from src.optical_system import OpticalSystem
        except ImportError:
            root = self.parent_window.root if hasattr(self, "parent_window") and self.parent_window else None
            CopyableMessageBox.showerror(root, "Missing Dependency", "Spot Diagram requires matplotlib and numpy.\nInstall with: pip install matplotlib numpy")
            return

        # Prepare System
        system = None
        if isinstance(self.current_lens, OpticalSystem):
            system = self.current_lens
        else:
            # Wrap in system
            system = OpticalSystem(name=getattr(self.current_lens, 'name', 'Lens System'))
            system.add_lens(self.current_lens)
            
        # Create Window
        window = tk.Toplevel()
        window.title(f"Spot Diagram - {system.name}")
        window.geometry("800x900")
        
        # Control Frame
        control_frame = ttk.Frame(window)
        control_frame.pack(side=tk.TOP, fill=tk.X, pady=PADDING_MEDIUM)
        
        # Max Field Angle
        tk.Label(control_frame, text="Max Field (deg):").pack(side=tk.LEFT, padx=5)
        field_var = tk.StringVar(value="0.0")
        tk.Entry(control_frame, textvariable=field_var, width=8).pack(side=tk.LEFT, padx=5)
        
        # Focus Shift
        tk.Label(control_frame, text="Focus Shift (mm):").pack(side=tk.LEFT, padx=5)
        shift_var = tk.StringVar(value="0.0")
        tk.Entry(control_frame, textvariable=shift_var, width=8).pack(side=tk.LEFT, padx=5)
        
        # Canvas Frame
        canvas_frame = ttk.Frame(window)
        canvas_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        
        def update_plot():
            # Clear previous
            for widget in canvas_frame.winfo_children():
                widget.destroy()
                
            try:
                max_field = float(field_var.get())
                focus_shift = float(shift_var.get())
            except ValueError:
                return

            analyzer = SpotDiagram(system)
            
            # Wavelengths: F (Blue), d (Green/Yellow), C (Red)
            wavelengths = [
                (486.1, 'b', 'F (486nm)'),
                (587.6, 'g', 'd (588nm)'),
                (656.3, 'r', 'C (656nm)')
            ]
            
            # Fields: 0, 0.7*Max, Max
            fields = [0.0]
            if max_field > 0.001:
                fields.append(0.707 * max_field)
                fields.append(max_field)
            
            # Calculate common image plane (using d-line on-axis)
            ref_result = analyzer.trace_spot(wavelength=587.6, field_angle_y=0.0, focus_shift=focus_shift)
            image_plane_x = ref_result['image_plane_x']
            
            # Create subplots
            fig = Figure(figsize=(8, 3 * len(fields)), dpi=100)
            fig.subplots_adjust(left=0.1, right=0.8, hspace=0.4, top=0.95, bottom=0.05)
            
            # Airy Disk Radius (at d-line)
            f_num = system.get_system_f_number() or 10.0
            airy_r_microns = 1.22 * (587.6 * 1e-6) * f_num * 1000
            
            # Find global max scale for consistent axes
            max_extent = airy_r_microns * 2 # Min extent
            
            # Store all results first to find scale
            all_spots = []
            
            for i, field_angle in enumerate(fields):
                field_data = []
                for wl, color, name in wavelengths:
                    res = analyzer.trace_spot(
                        wavelength=wl, 
                        field_angle_y=field_angle,
                        image_plane_x=image_plane_x, # Use fixed plane
                        num_rings=6
                    )
                    points_um = [(p[0]*1000, p[1]*1000) for p in res['points']]
                    
                    # Update max extent
                    if points_um:
                        local_max = max(max([abs(p[0]) for p in points_um]), max([abs(p[1]) for p in points_um]))
                        max_extent = max(max_extent, local_max)
                        
                    field_data.append({
                        'wl': wl, 'color': color, 'name': name,
                        'points': points_um,
                        'rms': res['rms_radius']*1000,
                        'geo': res['geo_radius']*1000
                    })
                all_spots.append((field_angle, field_data))
            
            limit = max_extent * 1.2
            
            # Plot
            for i, (field_angle, data_list) in enumerate(all_spots):
                ax = fig.add_subplot(len(fields), 1, i+1)
                
                # Plot spots
                rms_texts = []
                for data in data_list:
                    pts = data['points']
                    if pts:
                        y = [p[0] for p in pts]
                        z = [p[1] for p in pts]
                        ax.scatter(y, z, c=data['color'], marker='.', s=10, alpha=0.6, label=data['name'])
                    rms_texts.append(f"{data['name'][0]}: RMS {data['rms']:.1f}µm")
                
                # Airy Disk
                circle = plt.Circle((0, 0), airy_r_microns, color='k', fill=False, linestyle='--', label='Airy Disk')
                ax.add_patch(circle)
                
                ax.set_aspect('equal')
                ax.set_xlim(-limit, limit)
                ax.set_ylim(-limit, limit)
                ax.grid(True, alpha=0.3)
                ax.set_title(f"Field: {field_angle:.2f}°")
                if i == len(fields)-1:
                    ax.set_xlabel("Y (μm)")
                ax.set_ylabel("Z (μm)")
                
                # Add text box for stats
                stats = "\n".join(rms_texts)
                ax.text(1.02, 0.5, stats, transform=ax.transAxes, va='center', fontsize=9, 
                       bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
                
                if i == 0:
                    ax.legend(loc='upper right', bbox_to_anchor=(1.35, 1.0), fontsize='small')

            canvas = FigureCanvasTkAgg(fig, master=canvas_frame)
            canvas.draw()
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        ttk.Button(control_frame, text="Update", command=update_plot).pack(side=tk.LEFT, padx=10)
        
        # Initial Plot
        update_plot()

    def show_ghost_analysis(self):
        """Display Ghost Analysis in a new window"""
        if self.current_lens is None:
            root = self.parent_window.root if hasattr(self, "parent_window") and self.parent_window else None
            CopyableMessageBox.showwarning(root, "No Lens", "Please select a lens first")
            return

        try:
            import matplotlib.pyplot as plt
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            from matplotlib.figure import Figure
            
            # Import Analysis
            try:
                from .analysis.ghost import GhostAnalyzer
                from .optical_system import OpticalSystem
                from .ray_tracer import Ray3D
            except ImportError:
                # Fallback
                import sys
                import os
                sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
                from src.analysis.ghost import GhostAnalyzer
                from src.optical_system import OpticalSystem
                from src.ray_tracer import Ray3D
        except ImportError:
            root = self.parent_window.root if hasattr(self, "parent_window") and self.parent_window else None
            CopyableMessageBox.showerror(root, "Missing Dependency", "Ghost Analysis requires matplotlib and numpy.\nInstall with: pip install matplotlib numpy")
            return

        # Prepare System
        system = None
        if isinstance(self.current_lens, OpticalSystem):
            system = self.current_lens
        else:
            # Wrap in system
            system = OpticalSystem(name=getattr(self.current_lens, 'name', 'Lens System'))
            system.add_lens(self.current_lens)
            
        # Create Window
        window = tk.Toplevel()
        window.title(f"Ghost Analysis - {system.name}")
        window.geometry("900x600")
        
        # Frame for controls and plot
        main_frame = ttk.Frame(window)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Plot Frame
        plot_frame = ttk.Frame(main_frame)
        plot_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        
        # Analysis Logic
        try:
            analyzer = GhostAnalyzer(system)
            
            # Trace ghosts (using default num_rays=3 for now)
            ghosts = analyzer.trace_ghosts(num_rays=5)
            
            # Create Plot
            fig = Figure(figsize=(8, 5), dpi=100)
            ax = fig.add_subplot(111)
            
            # Draw Lenses (Reuse logic essentially)
            for element in system.elements:
                self._draw_lens_on_ax(ax, element.lens, element.position)
                
            # Draw Ghost Rays
            if ghosts:
                count = 0
                for ghost in ghosts:
                    # Color based on intensity or just distinct color
                    # GhostPath has .rays (list of Ray3D) and .intensity
                    alpha = min(1.0, max(0.1, ghost.intensity * 5)) # Scale intensity for visibility
                    
                    for ray in ghost.rays:
                        # ray.path is list of Vector3
                        x_coords = [p.x for p in ray.path]
                        y_coords = [p.y for p in ray.path]
                        ax.plot(x_coords, y_coords, 'r-', alpha=0.3, linewidth=0.8)
                    count += 1
                
                status_text = f"Found {count} ghost paths (2nd order reflections)."
            else:
                status_text = "No significant 2nd order ghosts found."
            
            # Setup Axes
            ax.set_xlabel('Z Position (mm)')
            ax.set_ylabel('Y Height (mm)')
            ax.set_title(f'Ghost Analysis (2nd Order Reflections)\n{status_text}')
            ax.grid(True, alpha=0.3)
            ax.set_aspect('equal')
            
            # Auto-scale
            ax.autoscale()
            # Ensure some padding
            xlim = ax.get_xlim()
            ylim = ax.get_ylim()
            x_range = xlim[1] - xlim[0]
            y_range = ylim[1] - ylim[0]
            ax.set_xlim(xlim[0] - x_range*0.1, xlim[1] + x_range*0.1)
            # Ensure Y shows at least +/- 10mm
            if y_range < 20:
                ax.set_ylim(-10, 10)
            
            canvas = FigureCanvasTkAgg(fig, master=plot_frame)
            canvas.draw()
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            
            # Info Label
            tk.Label(window, text=status_text, font=('Arial', 10)).pack(pady=5)
            
        except Exception as e:
            tk.Label(window, text=f"Error running ghost analysis: {e}", fg="red").pack()
            logger.error(f"Ghost analysis error: {e}")

    def show_psf(self):
        """Display Point Spread Function (PSF) Analysis"""
        if self.current_lens is None:
            root = self.parent_window.root if hasattr(self, "parent_window") and self.parent_window else None
            CopyableMessageBox.showwarning(root, "No Lens", "Please select a lens first")
            return

        try:
            import matplotlib.pyplot as plt
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            from matplotlib.figure import Figure
            import numpy as np
            
            try:
                from .analysis.psf_mtf import ImageQualityAnalyzer
                from .optical_system import OpticalSystem
            except ImportError:
                import sys
                import os
                sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
                from src.analysis.psf_mtf import ImageQualityAnalyzer
                from src.optical_system import OpticalSystem
        except ImportError:
            root = self.parent_window.root if hasattr(self, "parent_window") and self.parent_window else None
            CopyableMessageBox.showerror(root, "Missing Dependency", "PSF Analysis requires matplotlib and numpy.\nInstall with: pip install matplotlib numpy")
            return

        # Prepare System
        system = None
        if isinstance(self.current_lens, OpticalSystem):
            system = self.current_lens
        else:
            system = OpticalSystem(name=getattr(self.current_lens, 'name', 'Lens System'))
            system.add_lens(self.current_lens)
            
        # Create Window
        window = tk.Toplevel()
        window.title(f"PSF Analysis - {system.name}")
        window.geometry("800x700")
        
        # Control Frame
        control_frame = ttk.Frame(window)
        control_frame.pack(side=tk.TOP, fill=tk.X, pady=5)
        
        tk.Label(control_frame, text="Field (deg):").pack(side=tk.LEFT, padx=5)
        field_var = tk.StringVar(value="0.0")
        tk.Entry(control_frame, textvariable=field_var, width=6).pack(side=tk.LEFT, padx=5)
        
        tk.Label(control_frame, text="Focus Shift (mm):").pack(side=tk.LEFT, padx=5)
        shift_var = tk.StringVar(value="0.0")
        tk.Entry(control_frame, textvariable=shift_var, width=6).pack(side=tk.LEFT, padx=5)
        
        tk.Label(control_frame, text="Size (μm):").pack(side=tk.LEFT, padx=5)
        size_var = tk.StringVar(value="100.0") # 100 microns
        tk.Entry(control_frame, textvariable=size_var, width=6).pack(side=tk.LEFT, padx=5)
        
        diff_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(control_frame, text="Diffraction", variable=diff_var).pack(side=tk.LEFT, padx=5)
        
        # Plot Frame
        plot_frame = ttk.Frame(window)
        plot_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        
        def update_plot():
            for widget in plot_frame.winfo_children():
                widget.destroy()
            
            try:
                field = float(field_var.get())
                shift = float(shift_var.get())
                size_mm = float(size_var.get()) / 1000.0
                use_diff = diff_var.get()
            except ValueError:
                return
                
            analyzer = ImageQualityAnalyzer(system)
            
            # Wavelengths (F, d, C)
            wavelengths = [
                (486.1, 'Blues', 'F (486nm)'),
                (587.6, 'Greens', 'd (588nm)'),
                (656.3, 'Reds', 'C (656nm)')
            ]
            
            fig = Figure(figsize=(10, 4), dpi=100)
            
            for i, (wl, cmap, name) in enumerate(wavelengths):
                ax = fig.add_subplot(1, 3, i+1)
                
                res = analyzer.calculate_psf(
                    field_angle=field,
                    wavelength=wl,
                    focus_shift=shift,
                    sensor_size=size_mm,
                    pixels=64,
                    use_diffraction=use_diff
                )
                
                img = res['image']
                extent = [-size_mm*500, size_mm*500, -size_mm*500, size_mm*500] # mm to microns / 2
                
                im = ax.imshow(img, extent=extent, cmap=cmap, origin='lower', interpolation='bicubic')
                ax.set_title(f"{name}")
                ax.set_xlabel("Z (μm)") # Sagittal
                if i==0: ax.set_ylabel("Y (μm)") # Tangential
            
            mode = "Diffraction" if use_diff else "Geometric"
            fig.suptitle(f"{mode} PSF (Field: {field}°, Defocus: {shift}mm)")
            fig.tight_layout()
            
            canvas = FigureCanvasTkAgg(fig, master=plot_frame)
            canvas.draw()
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        ttk.Button(control_frame, text="Update", command=update_plot).pack(side=tk.LEFT, padx=10)
        update_plot()

    def show_mtf(self):
        """Display Modulation Transfer Function (MTF) Analysis"""
        if self.current_lens is None:
            root = self.parent_window.root if hasattr(self, "parent_window") and self.parent_window else None
            CopyableMessageBox.showwarning(root, "No Lens", "Please select a lens first")
            return

        try:
            import matplotlib.pyplot as plt
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            from matplotlib.figure import Figure
            import numpy as np
            
            try:
                from .analysis.psf_mtf import ImageQualityAnalyzer
                from .optical_system import OpticalSystem
            except ImportError:
                import sys
                import os
                sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
                from src.analysis.psf_mtf import ImageQualityAnalyzer
                from src.optical_system import OpticalSystem
        except ImportError:
            root = self.parent_window.root if hasattr(self, "parent_window") and self.parent_window else None
            CopyableMessageBox.showerror(root, "Missing Dependency", "MTF Analysis requires matplotlib and numpy.\nInstall with: pip install matplotlib numpy")
            return

        # Prepare System
        system = None
        if isinstance(self.current_lens, OpticalSystem):
            system = self.current_lens
        else:
            system = OpticalSystem(name=getattr(self.current_lens, 'name', 'Lens System'))
            system.add_lens(self.current_lens)
            
        # Create Window
        window = tk.Toplevel()
        window.title(f"MTF Analysis - {system.name}")
        window.geometry("800x600")
        
        # Control Frame
        control_frame = ttk.Frame(window)
        control_frame.pack(side=tk.TOP, fill=tk.X, pady=5)
        
        tk.Label(control_frame, text="Field (deg):").pack(side=tk.LEFT, padx=5)
        field_var = tk.StringVar(value="0.0")
        tk.Entry(control_frame, textvariable=field_var, width=6).pack(side=tk.LEFT, padx=5)
        
        tk.Label(control_frame, text="Focus Shift (mm):").pack(side=tk.LEFT, padx=5)
        shift_var = tk.StringVar(value="0.0")
        tk.Entry(control_frame, textvariable=shift_var, width=6).pack(side=tk.LEFT, padx=5)
        
        tk.Label(control_frame, text="Max Freq (lp/mm):").pack(side=tk.LEFT, padx=5)
        freq_var = tk.StringVar(value="100.0")
        tk.Entry(control_frame, textvariable=freq_var, width=6).pack(side=tk.LEFT, padx=5)
        
        diff_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(control_frame, text="Diffraction", variable=diff_var).pack(side=tk.LEFT, padx=5)
        
        # Plot Frame
        plot_frame = ttk.Frame(window)
        plot_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        
        def update_plot():
            for widget in plot_frame.winfo_children():
                widget.destroy()
            
            try:
                field = float(field_var.get())
                shift = float(shift_var.get())
                max_f = float(freq_var.get())
                use_diff = diff_var.get()
            except ValueError:
                return
                
            analyzer = ImageQualityAnalyzer(system)
            
            # Wavelengths (F, d, C)
            wavelengths = [
                (486.1, 'b', 'F (486nm)'),
                (587.6, 'g', 'd (588nm)'),
                (656.3, 'r', 'C (656nm)')
            ]
            
            fig = Figure(figsize=(8, 6), dpi=100)
            ax = fig.add_subplot(111)
            
            for wl, color, name in wavelengths:
                res = analyzer.calculate_mtf(
                    field_angle=field,
                    wavelength=wl,
                    focus_shift=shift,
                    max_freq=max_f,
                    use_diffraction=use_diff
                )
                
                freqs = res['freq']
                tan = res['mtf_tan']
                sag = res['mtf_sag']
                
                ax.plot(freqs, tan, color=color, linestyle='-', label=f'{name} (Tan)')
                ax.plot(freqs, sag, color=color, linestyle='--', label=f'{name} (Sag)')
                
            ax.set_xlim(0, max_f)
            ax.set_ylim(0, 1.05)
            ax.set_xlabel("Spatial Frequency (lp/mm)")
            ax.set_ylabel("Modulation")
            mode = "Diffraction" if use_diff else "Geometric"
            ax.set_title(f"{mode} MTF (Field: {field}°, Defocus: {shift}mm)")
            ax.grid(True, which='both', alpha=0.3)
            ax.legend()
            
            canvas = FigureCanvasTkAgg(fig, master=plot_frame)
            canvas.draw()
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        ttk.Button(control_frame, text="Update", command=update_plot).pack(side=tk.LEFT, padx=10)
        update_plot()

    def show_wavefront_map(self):
        """Display Wavefront Map Analysis"""
        if self.current_lens is None:
            root = self.parent_window.root if hasattr(self, "parent_window") and self.parent_window else None
            CopyableMessageBox.showwarning(root, "No Lens", "Please select a lens first")
            return

        try:
            import matplotlib.pyplot as plt
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            from matplotlib.figure import Figure
            import numpy as np
            
            try:
                from .analysis.diffraction_psf import WavefrontSensor
                from .optical_system import OpticalSystem
            except ImportError:
                import sys
                import os
                sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
                from src.analysis.diffraction_psf import WavefrontSensor
                from src.optical_system import OpticalSystem
        except ImportError:
            root = self.parent_window.root if hasattr(self, "parent_window") and self.parent_window else None
            CopyableMessageBox.showerror(root, "Missing Dependency", "Wavefront Analysis requires matplotlib and numpy.\nInstall with: pip install matplotlib numpy")
            return

        # Prepare System
        system = None
        if isinstance(self.current_lens, OpticalSystem):
            system = self.current_lens
        else:
            system = OpticalSystem(name=getattr(self.current_lens, 'name', 'Lens System'))
            system.add_lens(self.current_lens)
            
        # Create Window
        window = tk.Toplevel()
        window.title(f"Wavefront Map - {system.name}")
        window.geometry("700x600")
        
        # Control Frame
        control_frame = ttk.Frame(window)
        control_frame.pack(side=tk.TOP, fill=tk.X, pady=5)
        
        tk.Label(control_frame, text="Field (deg):").pack(side=tk.LEFT, padx=5)
        field_var = tk.StringVar(value="0.0")
        tk.Entry(control_frame, textvariable=field_var, width=6).pack(side=tk.LEFT, padx=5)
        
        tk.Label(control_frame, text="Wavelength (nm):").pack(side=tk.LEFT, padx=5)
        wave_var = tk.StringVar(value="550")
        tk.Entry(control_frame, textvariable=wave_var, width=6).pack(side=tk.LEFT, padx=5)
        
        # Plot Frame
        plot_frame = ttk.Frame(window)
        plot_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        
        def update_plot():
            for widget in plot_frame.winfo_children():
                widget.destroy()
            
            try:
                field = float(field_var.get())
                wavelength_nm = float(wave_var.get())
            except ValueError:
                return
                
            sensor = WavefrontSensor(system)
            wf = sensor.get_pupil_wavefront(field_angle=field, wavelength=wavelength_nm*1e-6)
            
            fig = Figure(figsize=(8, 6), dpi=100)
            ax = fig.add_subplot(111)
            
            # wf.W is in waves
            # Mask NaNs for better plotting (or set to 0, or use masked array)
            W_masked = np.ma.masked_invalid(wf.W)
            
            if W_masked.count() == 0:
                ax.text(0.5, 0.5, "No valid rays passed the pupil.", ha='center')
            else:
                # Plot
                # extent should be physical pupil coords
                if wf.Y.size > 0:
                    y_min, y_max = wf.Y.min(), wf.Y.max()
                    z_min, z_max = wf.Z.min(), wf.Z.max()
                    extent = [y_min, y_max, z_min, z_max]
                    
                    # Compute stats
                    pv = W_masked.max() - W_masked.min()
                    rms = np.sqrt(np.mean(W_masked**2)) # Simple RMS assuming 0 mean (removed in backend)
                    
                    im = ax.imshow(W_masked, extent=extent, origin='lower', cmap='jet')
                    cb = fig.colorbar(im, ax=ax, label='OPD (waves)')
                    
                    ax.set_title(f"Wavefront Map (λ={wavelength_nm}nm, Field={field}°)\nRMS: {rms:.4f} λ, PV: {pv:.4f} λ")
                    ax.set_xlabel("Y Pupil (mm)")
                    ax.set_ylabel("Z Pupil (mm)")
                else:
                    ax.text(0.5, 0.5, "No pupil data.", ha='center')

            canvas = FigureCanvasTkAgg(fig, master=plot_frame)
            canvas.draw()
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        ttk.Button(control_frame, text="Update", command=update_plot).pack(side=tk.LEFT, padx=10)
        update_plot()

    def show_image_simulation(self):
        """Display Image Simulation Tool"""
        if self.current_lens is None:
            root = self.parent_window.root if hasattr(self, "parent_window") and self.parent_window else None
            CopyableMessageBox.showwarning(root, "No Lens", "Please select a lens first")
            return

        try:
            import matplotlib.pyplot as plt
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            from matplotlib.figure import Figure
            import numpy as np
            from PIL import Image
            import os
            
            try:
                from .analysis.psf_mtf import ImageQualityAnalyzer
                from .optical_system import OpticalSystem
            except ImportError:
                import sys
                import os
                sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
                from src.analysis.psf_mtf import ImageQualityAnalyzer
                from src.optical_system import OpticalSystem
        except ImportError as e:
            root = self.parent_window.root if hasattr(self, "parent_window") and self.parent_window else None
            CopyableMessageBox.showerror(root, "Missing Dependency", f"Image Simulation requires matplotlib, numpy, scipy and Pillow.\\nError: {e}\\nInstall with: pip install matplotlib numpy scipy Pillow")
            return

        # Prepare System
        system = None
        if isinstance(self.current_lens, OpticalSystem):
            system = self.current_lens
        else:
            system = OpticalSystem(name=getattr(self.current_lens, 'name', 'Lens System'))
            system.add_lens(self.current_lens)
            
        # Create Window
        window = tk.Toplevel()
        window.title(f"Image Simulation - {system.name}")
        window.geometry("1000x600")
        
        # Control Frame
        control_frame = ttk.Frame(window)
        control_frame.pack(side=tk.TOP, fill=tk.X, pady=5)
        
        # Load Image Button
        self.source_image = None
        self.source_image_path = None
        
        def load_image():
            from tkinter import filedialog
            file_path = filedialog.askopenfilename(
                title="Select Image",
                filetypes=[("Image files", "*.jpg *.jpeg *.png *.bmp *.tif")]
            )
            if file_path:
                try:
                    img = Image.open(file_path)
                    # Resize if too large to prevent slow simulation
                    max_size = 512
                    if img.width > max_size or img.height > max_size:
                        img.thumbnail((max_size, max_size))
                    
                    self.source_image = np.array(img).astype(float) / 255.0
                    self.source_image_path = file_path
                    
                    # Handle RGBA
                    if self.source_image.shape[2] == 4:
                         self.source_image = self.source_image[:,:,:3]
                    # Handle Grayscale
                    if len(self.source_image.shape) == 2:
                         self.source_image = np.stack((self.source_image,)*3, axis=-1)
                         
                    update_display(original_only=True)
                    status_var.set(f"Loaded: {os.path.basename(file_path)}")
                except Exception as e:
                    CopyableMessageBox.showerror(window, "Error", f"Failed to load image: {e}")

        ttk.Button(control_frame, text="Load Image", command=load_image).pack(side=tk.LEFT, padx=10)
        
        status_var = tk.StringVar(value="No image loaded")
        ttk.Label(control_frame, textvariable=status_var).pack(side=tk.LEFT, padx=5)
        
        # Parameters
        param_frame = ttk.Frame(window)
        param_frame.pack(side=tk.TOP, fill=tk.X, pady=5)
        
        tk.Label(param_frame, text="Field (deg):").pack(side=tk.LEFT, padx=5)
        field_var = tk.StringVar(value="0.0")
        tk.Entry(param_frame, textvariable=field_var, width=6).pack(side=tk.LEFT, padx=5)
        
        tk.Label(param_frame, text="Defocus (mm):").pack(side=tk.LEFT, padx=5)
        shift_var = tk.StringVar(value="0.0")
        tk.Entry(param_frame, textvariable=shift_var, width=6).pack(side=tk.LEFT, padx=5)
        
        tk.Label(param_frame, text="Pixel Size (μm):").pack(side=tk.LEFT, padx=5)
        pixel_var = tk.StringVar(value="5.0")
        tk.Entry(param_frame, textvariable=pixel_var, width=6).pack(side=tk.LEFT, padx=5)

        # Plot Frame
        plot_frame = ttk.Frame(window)
        plot_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        
        # Matplotlib Figure
        fig = Figure(figsize=(10, 5), dpi=100)
        ax1 = fig.add_subplot(121)
        ax2 = fig.add_subplot(122)
        fig.subplots_adjust(left=0.05, right=0.95, bottom=0.05, top=0.9)
        
        canvas = FigureCanvasTkAgg(fig, master=plot_frame)
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        def update_display(original_only=False, simulated_img=None):
            if self.source_image is None:
                return
                
            ax1.clear()
            ax1.imshow(self.source_image)
            ax1.set_title("Original Source")
            ax1.axis('off')
            
            ax2.clear()
            if simulated_img is not None:
                ax2.imshow(simulated_img)
                ax2.set_title("Simulated Image")
            else:
                ax2.text(0.5, 0.5, "Click 'Run Simulation'", ha='center', va='center')
                ax2.set_title("Simulated Image")
            ax2.axis('off')
            
            canvas.draw()

        def run_simulation():
            if self.source_image is None:
                CopyableMessageBox.showwarning(window, "No Image", "Please load an image first")
                return
                
            try:
                field = float(field_var.get())
                shift = float(shift_var.get())
                pixel_size_mm = float(pixel_var.get()) / 1000.0
            except ValueError:
                CopyableMessageBox.showerror(window, "Invalid Input", "Please check your parameters")
                return
                
            status_var.set("Simulating... Please wait.")
            window.update()
            
            try:
                analyzer = ImageQualityAnalyzer(system)
                
                simulated = analyzer.simulate_image(
                    self.source_image,
                    pixel_size=pixel_size_mm,
                    field_angle=field,
                    focus_shift=shift
                )
                
                update_display(simulated_img=simulated)
                status_var.set("Simulation Complete")
                
            except Exception as e:
                CopyableMessageBox.showerror(window, "Simulation Error", f"Error: {e}")
                status_var.set("Error during simulation")

        ttk.Button(param_frame, text="Run Simulation", command=run_simulation).pack(side=tk.LEFT, padx=20)
        
        # Initial draw
        ax1.text(0.5, 0.5, "No Image Loaded", ha='center')
        ax2.text(0.5, 0.5, "No Simulation", ha='center')
        ax1.axis('off')
        ax2.axis('off')
        canvas.draw()

    def _draw_lens_on_ax(self, ax, lens, offset):
        """Helper to draw a single lens on a matplotlib axis"""
        try:
            # Try to use existing ray tracer for geometry if available
            try:
                from .ray_tracer import LensRayTracer
            except ImportError:
                from src.ray_tracer import LensRayTracer
                
            tracer = LensRayTracer(lens, x_offset=offset)
            points = tracer.get_lens_outline(num_points=100)
            
            poly_x = [p[0] for p in points]
            poly_y = [p[1] for p in points]
            
            ax.fill(poly_x, poly_y, facecolor='#e6f3ff', edgecolor='k', alpha=0.4, linewidth=1.0)
                
        except Exception:
            # Fallback simple drawing (rect/approx)
            import math
            r1 = lens.radius_of_curvature_1
            r2 = lens.radius_of_curvature_2
            t = lens.thickness
            d = lens.diameter
            
            # Generate y coordinates for the lens aperture
            num_points = 100
            half_diam = d / 2.0
            y = [(-half_diam + i * d / (num_points - 1)) for i in range(num_points)]
            
            # Helper function
            def calculate_surface_x(r, y_val, is_front):
                if abs(r) > 10000 or abs(r) < 1e-10:
                    return offset if is_front else offset + float(t)
                
                r_abs = abs(r)
                if abs(y_val) >= r_abs:
                    sag_term = 0.0
                else:
                    sag_term = math.sqrt(r_abs**2 - y_val**2)
                
                if is_front:
                    if r > 0:
                        return offset - r_abs + sag_term
                    else:
                        return offset + r_abs - sag_term
                else:
                    if r > 0:
                        return offset + t + r_abs - sag_term
                    else:
                        return offset + t - r_abs + sag_term

            # Surface 1
            x1 = [calculate_surface_x(r1, y_val, is_front=True) for y_val in y]
            
            # Surface 2
            x2 = [calculate_surface_x(r2, y_val, is_front=False) for y_val in y]
            
            # Draw filled polygon
            poly_x = x1 + x2[::-1]
            poly_y = y + y[::-1]
            
            ax.fill(poly_x, poly_y, facecolor='#e6f3ff', edgecolor='k', alpha=0.4, linewidth=1.0)

    def calculate_metrics(self):
        """Calculate performance metrics for current lens"""
        if self.current_lens is None:
            try:
                from tkinter import messagebox
                CopyableMessageBox.showwarning(self.parent_window.root if hasattr(self, "parent_window") and self.parent_window else None, "No Lens", "Please select a lens first")
            except Exception as e:
                logger.warning(f"Failed to show warning dialog: {e}")
            return
        
        if not self.aberrations_available:
            result = "Performance analysis requires numpy and scipy.\n"
            result += "Install with: pip install numpy scipy\n"
            self.metrics_text.config(state='normal')
            self.metrics_text.delete(1.0, tk.END)
            self.metrics_text.insert(1.0, result)
            self.metrics_text.config(state='disabled')
            return
        
        # Check if it's a system
        is_system = hasattr(self.current_lens, 'elements')
        
        try:
            # Get parameters
            entrance_pupil = float(self.entrance_pupil_var.get())
            wavelength = float(self.wavelength_var.get())
            object_distance = float(self.object_distance_var.get())
            sensor_size = float(self.sensor_size_var.get())
            
            if is_system:
                # System Performance Analysis
                result = "=" * 70 + "\n"
                result += f"SYSTEM PERFORMANCE: {self.current_lens.name}\n"
                result += "=" * 70 + "\n\n"
                
                # Basic Properties
                f_system = self.current_lens.get_system_focal_length()
                na = self.current_lens.get_numerical_aperture()
                total_length = self.current_lens.get_total_length()
                
                result += "SYSTEM PROPERTIES:\n"
                if f_system:
                    result += f"  Effective Focal Length: {f_system:.3f} mm\n"
                    # Calculate BFL
                    bfl = self.current_lens.calculate_back_focal_length()
                    if bfl is not None:
                        result += f"  Back Focal Length: {bfl:.3f} mm\n"
                    else:
                        result += "  Back Focal Length: Undefined\n"
                        
                    f_number = abs(f_system) / entrance_pupil if entrance_pupil > 0 else 0
                    result += f"  F-Number (approx): {f_number:.2f}\n"
                    result += f"  Optical Power: {1000/f_system:.2f} D\n"
                else:
                    result += "  Effective Focal Length: Undefined (Afocal)\n"
                
                result += f"  Numerical Aperture: {na:.4f}\n"
                result += f"  Total Track Length: {total_length:.2f} mm\n"
                result += f"  Number of Elements: {len(self.current_lens.elements)}\n\n"
                
                # Chromatic Aberration
                chrom = self.current_lens.calculate_chromatic_aberration()
                result += "CHROMATIC ABERRATION:\n"
                result += f"  Longitudinal CA: {chrom['longitudinal']:.4f} mm\n"
                result += f"  Achromatic: {'Yes' if chrom['corrected'] else 'No'}\n"
                result += f"  Shift (C-F): {chrom['longitudinal']:.4f} mm\n\n"
                
                # System Elements
                result += "ELEMENTS:\n"
                for i, elem in enumerate(self.current_lens.elements):
                    result += f"  {i+1}. {elem.lens.name} (Pos: {elem.position:.2f} mm)\n"
                    f = elem.lens.calculate_focal_length()
                    result += f"     f={f:.2f} mm, Material={elem.lens.material}\n"
                
                result += "\nNote: Full Seidel aberration analysis is currently supported for single lenses only.\n"
                result += "=" * 70 + "\n"
                
            else:
                # Single Lens Analysis (Existing Code)
                # Import aberrations module
                try:
                    from aberrations import AberrationsCalculator, analyze_lens_quality
                    
                    calc = AberrationsCalculator(self.current_lens)
                    
                    # Calculate aberrations
                    spherical = calc.spherical_aberration(entrance_pupil_radius=entrance_pupil/2)
                    coma = calc.coma(field_angle=5.0)  # 5 degree field
                    chromatic = calc.chromatic_aberration()
                    distortion = calc.distortion(field_height=sensor_size/2)
                    field_curv = calc.field_curvature()
                    astigmatism = calc.astigmatism(field_angle=5.0)
                    
                    # Quality analysis
                    quality = analyze_lens_quality(self.current_lens)
                    
                    # Format results
                    result = "=" * 70 + "\n"
                    result += f"PERFORMANCE METRICS: {self.current_lens.name}\n"
                    result += "=" * 70 + "\n\n"
                    
                    result += "CALCULATION PARAMETERS:\n"
                    result += f"  Entrance Pupil: {entrance_pupil:.2f} mm\n"
                    result += f"  Wavelength: {wavelength:.1f} nm\n"
                    result += f"  Object Distance: {object_distance:.1f} mm\n"
                    result += f"  Sensor Size: {sensor_size:.1f} mm\n\n"
                    
                    result += "ABERRATIONS:\n"
                    result += f"  Spherical Aberration: {spherical:.6f} mm\n"
                    result += f"  Coma: {coma:.6f} mm\n"
                    result += f"  Chromatic Aberration: {chromatic:.6f} mm\n"
                    result += f"  Distortion: {distortion:.4f}%\n"
                    result += f"  Field Curvature: {field_curv:.6f} mm\n"
                    result += f"  Astigmatism: {astigmatism:.6f} mm\n\n"
                    
                    result += "OPTICAL PROPERTIES:\n"
                    result += f"  Focal Length: {self.current_lens.calculate_focal_length():.3f} mm\n"
                    result += f"  F-Number: {self.current_lens.calculate_f_number():.2f}\n"
                    result += f"  Back Focal Length: {self.current_lens.calculate_back_focal_length():.3f} mm\n"
                    result += f"  Front Focal Length: {self.current_lens.calculate_front_focal_length():.3f} mm\n\n"
                    
                    result += "QUALITY ASSESSMENT:\n"
                    result += f"  Overall Quality: {quality['quality']}\n"
                    result += f"  Quality Score: {quality['score']:.1f}/100\n"
                    result += f"  Issues: {', '.join(quality['issues']) if quality['issues'] else 'None'}\n\n"
                    
                    result += "DIFFRACTION LIMIT:\n"
                    airy_disk = 1.22 * (wavelength / 1e6) * self.current_lens.calculate_f_number()
                    result += f"  Airy Disk Diameter: {airy_disk*1000:.3f} μm\n"
                    result += f"  Rayleigh Criterion: {airy_disk*1000/2:.3f} μm\n\n"
                    
                    result += "=" * 70 + "\n"
                    
                except ImportError:
                    result = "Performance analysis requires numpy and scipy.\n"
                    result += "Install with: pip install numpy scipy\n"
            
            # Update display
            self.metrics_text.config(state='normal')
            self.metrics_text.delete(1.0, tk.END)
            self.metrics_text.insert(1.0, result)
            self.metrics_text.config(state='disabled')
            
        except ValueError as e:
            try:
                from tkinter import messagebox
                CopyableMessageBox.showerror(self.parent_window.root if hasattr(self, "parent_window") and self.parent_window else None, "Invalid Input", f"Please check your input values: {e}")
            except Exception as dialog_error:
                logger.warning(f"Failed to show error dialog: {dialog_error}")
        except Exception as e:
            try:
                from tkinter import messagebox
                CopyableMessageBox.showerror(self.parent_window.root if hasattr(self, "parent_window") and self.parent_window else None, "Calculation Error", f"Error during calculation: {e}")
            except Exception as dialog_error:
                logger.error(f"Calculation failed: {e}, dialog error: {dialog_error}")
    
    def export_report(self):
        """Export performance report to file"""
        if self.current_lens is None:
            try:
                from tkinter import messagebox
                CopyableMessageBox.showwarning(self.parent_window.root if hasattr(self, "parent_window") and self.parent_window else None, "No Lens", "No analysis to export")
            except Exception as e:
                logger.warning(f"Failed to show warning dialog: {e}")
            return
        
        # Get report content
        content = self.metrics_text.get(1.0, tk.END)
        
        try:
            from tkinter import filedialog, messagebox
            
            filename = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
                title="Export Performance Report"
            )
            
            if filename:
                with open(filename, 'w') as f:
                    f.write(content)
                CopyableMessageBox.showinfo(self.parent_window.root if hasattr(self, "parent_window") and self.parent_window else None, "Success", f"Report exported to {filename}")
        except Exception as e:
            try:
                from tkinter import messagebox
                CopyableMessageBox.showerror(self.parent_window.root if hasattr(self, "parent_window") and self.parent_window else None, "Export Error", f"Failed to export: {e}")
            except Exception as dialog_error:
                logger.error(f"Export failed: {e}, dialog error: {dialog_error}")



class ExportController:
    """
    Controller for exporting lens data to various formats.
    
    Responsibilities:
    - Export to JSON
    - Export to STL
    - Export technical drawings
    - Generate reports
    """
    
    def __init__(self, parent_window, colors=None):
        """
        Initialize the export controller.
        
        Args:
            parent_window: Reference to main window
            colors: Color scheme dictionary
        """
        self.window = parent_window
        self.current_lens = None
        
        # Import constants with fallback
        try:
            from constants import (
                COLOR_BG_DARK, COLOR_FG, COLOR_ACCENT,
                FONT_FAMILY, FONT_SIZE_NORMAL
            )
            self.colors = colors or {
                'bg': COLOR_BG_DARK,
                'fg': COLOR_FG,
                'accent': COLOR_ACCENT,
                'entry_bg': '#2b2b2b'
            }
        except ImportError:
            self.colors = colors or {
                'bg': '#1e1e1e',
                'fg': '#ffffff',
                'accent': '#0078d4',
                'entry_bg': '#2b2b2b'
            }
    
    def setup_ui(self, parent_frame):
        """Set up the export tab UI"""
        # Import constants
        try:
            from constants import FONT_FAMILY, FONT_SIZE_NORMAL, PADDING_MEDIUM, PADDING_XLARGE
        except ImportError:
            FONT_FAMILY = 'Arial'
            FONT_SIZE_NORMAL = 10
            PADDING_MEDIUM = 10
            PADDING_XLARGE = 20
        
        # Configure grid
        parent_frame.columnconfigure(0, weight=1)
        
        # Main content frame
        content_frame = ttk.Frame(parent_frame, padding="10")
        content_frame.grid(row=0, column=0, sticky="nsew")
        content_frame.columnconfigure(0, weight=1)
        
        # Title
        title_label = ttk.Label(content_frame, text="Professional Export Formats", 
                                font=(FONT_FAMILY, 14, 'bold'))
        title_label.grid(row=0, column=0, pady=PADDING_MEDIUM)
        
        row = 1
        
        # JSON Export
        json_frame = ttk.LabelFrame(content_frame, text="JSON Format", padding="15")
        json_frame.grid(row=row, column=0, sticky="ew", pady=PADDING_MEDIUM, padx=PADDING_XLARGE)
        ttk.Label(json_frame, text="Export lens data as JSON", font=(FONT_FAMILY, FONT_SIZE_NORMAL)).pack(side=tk.LEFT, padx=PADDING_MEDIUM)
        ttk.Button(json_frame, text="Export JSON", command=self.export_json, width=15).pack(side=tk.RIGHT, padx=PADDING_MEDIUM)
        row += 1
        
        # STL Export
        stl_frame = ttk.LabelFrame(content_frame, text="3D Model (STL)", padding="15")
        stl_frame.grid(row=row, column=0, sticky="ew", pady=PADDING_MEDIUM, padx=PADDING_XLARGE)
        ttk.Label(stl_frame, text="Export 3D model for CAD/3D printing", font=(FONT_FAMILY, FONT_SIZE_NORMAL)).pack(side=tk.LEFT, padx=PADDING_MEDIUM)
        ttk.Button(stl_frame, text="Export STL", command=self.export_stl, width=15).pack(side=tk.RIGHT, padx=PADDING_MEDIUM)
        row += 1

        # STEP Export
        step_frame = ttk.LabelFrame(content_frame, text="3D Model (STEP)", padding="15")
        step_frame.grid(row=row, column=0, sticky="ew", pady=PADDING_MEDIUM, padx=PADDING_XLARGE)
        ttk.Label(step_frame, text="Export solid geometry for CAD (ISO 10303-21)", font=(FONT_FAMILY, FONT_SIZE_NORMAL)).pack(side=tk.LEFT, padx=PADDING_MEDIUM)
        ttk.Button(step_frame, text="Export STEP", command=self.export_step, width=15).pack(side=tk.RIGHT, padx=PADDING_MEDIUM)
        row += 1
        
        # ISO 10110 Export
        iso_frame = ttk.LabelFrame(content_frame, text="Manufacturing Drawing (ISO 10110)", padding="15")
        iso_frame.grid(row=row, column=0, sticky="ew", pady=PADDING_MEDIUM, padx=PADDING_XLARGE)
        ttk.Label(iso_frame, text="Export ISO 10110 compliant SVG drawing", font=(FONT_FAMILY, FONT_SIZE_NORMAL)).pack(side=tk.LEFT, padx=PADDING_MEDIUM)
        ttk.Button(iso_frame, text="Export ISO Drawing", command=self.export_iso10110, width=15).pack(side=tk.RIGHT, padx=PADDING_MEDIUM)
        row += 1
        
        # Technical Report
        report_frame = ttk.LabelFrame(content_frame, text="Technical Report", padding="15")
        report_frame.grid(row=row, column=0, sticky="ew", pady=PADDING_MEDIUM, padx=PADDING_XLARGE)
        ttk.Label(report_frame, text="Generate detailed technical report", font=(FONT_FAMILY, FONT_SIZE_NORMAL)).pack(side=tk.LEFT, padx=PADDING_MEDIUM)
        ttk.Button(report_frame, text="Generate Report", command=self.export_report, width=15).pack(side=tk.RIGHT, padx=PADDING_MEDIUM)
        row += 1
        
        # Status area
        status_frame = ttk.LabelFrame(content_frame, text="Export Status", padding="10")
        status_frame.grid(row=row, column=0, sticky="ew", pady=PADDING_MEDIUM, padx=PADDING_XLARGE)
        
        self.status_text = tk.Text(status_frame, height=8, width=80,
                                   wrap=tk.WORD,
                                   bg=self.colors.get('entry_bg', '#2b2b2b'),
                                   fg=self.colors.get('fg', '#ffffff'),
                                   font=('Arial', 9),
                                   state='disabled')
        self.status_text.pack(fill=tk.BOTH, expand=True)
        
        # Initial status message
        self._update_status("Ready to export. Select a lens from the Selection tab.")
    
    def load_lens(self, lens):
        """Load lens for export"""
        self.current_lens = lens
        if hasattr(self, 'status_text'):
            self._update_status(f"Lens '{lens.name}' loaded. Ready to export.")
    
    def _update_status(self, message):
        """Update status text widget"""
        if hasattr(self, 'status_text'):
            self.status_text.config(state='normal')
            self.status_text.delete(1.0, tk.END)
            self.status_text.insert(1.0, message)
            self.status_text.config(state='disabled')
    
    def export_json(self):
        """Export lens to JSON file"""
        if self.current_lens is None:
            CopyableMessageBox.showwarning(self.parent_window.root if hasattr(self, "parent_window") and self.parent_window else None, "No Lens", "Please select a lens first")
            return
        
        from tkinter import filedialog
        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="Export Lens to JSON"
        )
        
        if filename:
            try:
                with open(filename, 'w') as f:
                    json.dump(self.current_lens.to_dict(), f, indent=2)
                CopyableMessageBox.showinfo(self.parent_window.root if hasattr(self, "parent_window") and self.parent_window else None, "Success", f"Lens exported to {filename}")
                self._update_status(f"✓ Successfully exported to: {filename}")
            except Exception as e:
                CopyableMessageBox.showerror(self.parent_window.root if hasattr(self, "parent_window") and self.parent_window else None, "Export Error", f"Failed to export: {e}")
                self._update_status(f"✗ Export failed: {e}")
    
    def export_stl(self):
        """Export lens to STL file"""
        if self.current_lens is None:
            CopyableMessageBox.showwarning(self.parent_window.root if hasattr(self, "parent_window") and self.parent_window else None, "No Lens", "Please select a lens first")
            return
        
        try:
            from stl_export import export_lens_stl
        except ImportError:
            CopyableMessageBox.showerror(self.parent_window.root if hasattr(self, "parent_window") and self.parent_window else None, "Not Available", 
                               "STL export requires numpy. Install with: pip install numpy")
            return
        
        from tkinter import filedialog
        filename = filedialog.asksaveasfilename(
            defaultextension=".stl",
            filetypes=[("STL files", "*.stl"), ("All files", "*.*")],
            title="Export Lens to STL"
        )
        
        if filename:
            try:
                export_lens_stl(self.current_lens, filename)
                CopyableMessageBox.showinfo(self.parent_window.root if hasattr(self, "parent_window") and self.parent_window else None, "Success", f"3D model exported to {filename}")
                self._update_status(f"✓ Successfully exported STL to: {filename}")
            except Exception as e:
                CopyableMessageBox.showerror(self.parent_window.root if hasattr(self, "parent_window") and self.parent_window else None, "Export Error", f"Failed to export: {e}")
                self._update_status(f"✗ STL export failed: {e}")

    def export_step(self):
        """Export lens to STEP file"""
        if self.current_lens is None:
            CopyableMessageBox.showwarning(self.parent_window.root if hasattr(self, "parent_window") and self.parent_window else None, "No Lens", "Please select a lens first")
            return
        
        try:
            # Try importing with different paths to handle execution context
            try:
                from .io.step_export import StepExporter
            except ImportError:
                # Fallback for direct script execution
                import sys
                import os
                # Add project root to path if needed
                current_dir = os.path.dirname(os.path.abspath(__file__))
                parent_dir = os.path.dirname(current_dir) # src/../
                if parent_dir not in sys.path:
                    sys.path.insert(0, parent_dir)
                from src.io.step_export import StepExporter
                
        except ImportError as e:
            CopyableMessageBox.showerror(self.parent_window.root if hasattr(self, "parent_window") and self.parent_window else None, "Import Error", 
                               f"Could not import StepExporter: {e}")
            return
        
        from tkinter import filedialog
        filename = filedialog.asksaveasfilename(
            defaultextension=".step",
            filetypes=[("STEP files", "*.step"), ("All files", "*.*")],
            title="Export Lens to STEP"
        )
        
        if filename:
            try:
                exporter = StepExporter(self.current_lens)
                exporter.export(filename)
                
                CopyableMessageBox.showinfo(self.parent_window.root if hasattr(self, "parent_window") and self.parent_window else None, "Success", f"STEP model exported to {filename}")
                self._update_status(f"✓ Successfully exported STEP to: {filename}")
            except Exception as e:
                CopyableMessageBox.showerror(self.parent_window.root if hasattr(self, "parent_window") and self.parent_window else None, "Export Error", f"Failed to export: {e}")
                self._update_status(f"✗ STEP export failed: {e}")

    
    def export_iso10110(self):
        """Export lens to ISO 10110 SVG drawing"""
        if self.current_lens is None:
            # Try to find window handle
            root = self.window.root if hasattr(self, "window") and hasattr(self.window, "root") else None
            if root is None and hasattr(self, "parent_window") and hasattr(self.parent_window, "root"):
                root = self.parent_window.root
                
            CopyableMessageBox.showwarning(root, "No Lens", "Please select a lens first")
            return
            
        try:
            try:
                from .io.export import ISO10110Generator
                from .optical_system import OpticalSystem
            except ImportError:
                # Absolute import fallback
                import sys
                import os
                # Add project root to path if needed
                current_dir = os.path.dirname(os.path.abspath(__file__))
                parent_dir = os.path.dirname(current_dir)
                if parent_dir not in sys.path:
                    sys.path.insert(0, parent_dir)
                from src.io.export import ISO10110Generator
                from src.optical_system import OpticalSystem
        except ImportError as e:
            root = self.window.root if hasattr(self, "window") and hasattr(self.window, "root") else None
            CopyableMessageBox.showerror(root, "Import Error", f"Could not import ISO10110Generator: {e}")
            return

        # Prepare system
        system = None
        if isinstance(self.current_lens, OpticalSystem):
            system = self.current_lens
        else:
            # Wrap single lens in OpticalSystem
            system = OpticalSystem(name=getattr(self.current_lens, 'name', 'Lens System'))
            system.add_lens(self.current_lens)
            
        from tkinter import filedialog
        filename = filedialog.asksaveasfilename(
            defaultextension=".svg",
            filetypes=[("SVG files", "*.svg"), ("All files", "*.*")],
            title="Export ISO 10110 Drawing"
        )
        
        if filename:
            try:
                generator = ISO10110Generator(system)
                generator.generate_svg(filename)
                
                root = self.window.root if hasattr(self, "window") and hasattr(self.window, "root") else None
                CopyableMessageBox.showinfo(root, "Success", f"Drawing exported to {filename}")
                self._update_status(f"✓ Successfully exported ISO drawing to: {filename}")
            except Exception as e:
                root = self.window.root if hasattr(self, "window") and hasattr(self.window, "root") else None
                CopyableMessageBox.showerror(root, "Export Error", f"Failed to export: {e}")
                self._update_status(f"✗ ISO export failed: {e}")

    def export_report(self):
        """Generate and export technical report"""
        if self.current_lens is None:
            CopyableMessageBox.showwarning(self.parent_window.root if hasattr(self, "parent_window") and self.parent_window else None, "No Lens", "Please select a lens first")
            return
        
        # Generate report
        report = f"TECHNICAL REPORT: {self.current_lens.name}\n"
        report += "=" * 80 + "\n\n"
        report += "LENS SPECIFICATIONS\n"
        report += "-" * 80 + "\n"
        report += f"Type: {self.current_lens.lens_type}\n"
        report += f"Material: {self.current_lens.material}\n"
        report += f"Diameter: {self.current_lens.diameter} mm\n"
        report += f"Thickness: {self.current_lens.thickness} mm\n"
        report += f"Radius 1: {self.current_lens.radius_of_curvature_1} mm\n"
        report += f"Radius 2: {self.current_lens.radius_of_curvature_2} mm\n"
        report += f"Refractive Index: {self.current_lens.refractive_index}\n\n"
        
        report += "CALCULATED PROPERTIES\n"
        report += "-" * 80 + "\n"
        try:
            fl = self.current_lens.calculate_focal_length()
            report += f"Focal Length: {fl:.2f} mm\n" if fl else "Focal Length: N/A\n"
        except (ValueError, ZeroDivisionError, AttributeError) as e:
            logger.debug(f"Failed to calculate focal length: {e}")
            report += "Focal Length: Error\n"
        
        from tkinter import filedialog
        filename = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            title="Export Technical Report"
        )
        
        if filename:
            try:
                with open(filename, 'w') as f:
                    f.write(report)
                CopyableMessageBox.showinfo(self.parent_window.root if hasattr(self, "parent_window") and self.parent_window else None, "Success", f"Report exported to {filename}")
                self._update_status(f"✓ Successfully exported report to: {filename}")
            except Exception as e:
                CopyableMessageBox.showerror(self.parent_window.root if hasattr(self, "parent_window") and self.parent_window else None, "Export Error", f"Failed to export: {e}")
                self._update_status(f"✗ Report export failed: {e}")


# Export controllers
__all__ = [
    'LensSelectionController',
    'LensEditorController',
    'SimulationController',
    'PerformanceController',
    'ExportController'
]
