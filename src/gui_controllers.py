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
- ComparisonController: Handles lens comparison
- ExportController: Manages export functionality
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional, List, Callable, Dict, Any, TYPE_CHECKING
import json

if TYPE_CHECKING:
    from lens_editor_gui import Lens, LensEditorWindow


class LensSelectionController:
    """
    Controller for lens selection and management in the selection tab.
    
    Responsibilities:
    - Manage lens list display
    - Handle lens selection
    - Create/delete/duplicate lenses
    - Update selection info panel
    """
    
    def __init__(self, parent_window, lens_list, colors, on_lens_selected, on_create_new, on_delete, on_lens_updated):
        """
        Initialize the lens selection controller.
        
        Args:
            parent_window: Reference to main window
            lens_list: List of Lens objects
            colors: Color scheme dictionary
            on_lens_selected: Callback when lens is selected
            on_create_new: Callback when creating new lens
            on_delete: Callback when deleting lens
            on_lens_updated: Callback when lens is updated
        """
        self.window = parent_window
        self.lens_list = lens_list
        self.colors = colors
        self.on_lens_selected_callback = on_lens_selected
        self.on_create_new_callback = on_create_new
        self.on_delete_callback = on_delete
        self.on_lens_updated_callback = on_lens_updated
        self.selected_lens = None
        self.listbox = None
        self.info_text = None
        
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
        content_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        content_frame.columnconfigure(0, weight=1)
        content_frame.rowconfigure(1, weight=1)
        
        # Title
        title_label = ttk.Label(content_frame, text="Lens Library", 
                               font=(FONT_FAMILY, 16, 'bold'))
        title_label.grid(row=0, column=0, pady=(0, PADDING_XLARGE))
        
        # Create a frame for the lens list and buttons
        list_frame = ttk.LabelFrame(content_frame, text="Available Lenses", padding="10")
        list_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)
        
        # Lens listbox with scrollbar
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        self.listbox = tk.Listbox(list_frame, 
                                   yscrollcommand=scrollbar.set,
                                   bg=self.colors['entry_bg'],
                                   fg=self.colors['fg'],
                                   selectbackground=self.colors['accent'],
                                   selectforeground=self.colors['fg'],
                                   font=(FONT_FAMILY, FONT_SIZE_LARGE),
                                   height=15,
                                   borderwidth=1,
                                   relief=tk.SOLID)
        self.listbox.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 5))
        scrollbar.config(command=self.listbox.yview)
        
        # Bind events
        self.listbox.bind('<Double-Button-1>', lambda e: self.select_lens())
        self.listbox.bind('<<ListboxSelect>>', self.update_info)
        
        # Lens info panel
        info_frame = ttk.LabelFrame(content_frame, text="Lens Information", padding="10")
        info_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=PADDING_XLARGE)
        
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
                  width=20).pack(side=tk.LEFT, padx=PADDING_SMALL)
        
        ttk.Button(button_frame, text="Select & Edit", 
                  command=self.select_lens,
                  width=20).pack(side=tk.LEFT, padx=PADDING_SMALL)
        
        ttk.Button(button_frame, text="Delete Lens", 
                  command=self.delete_lens,
                  width=20).pack(side=tk.LEFT, padx=PADDING_SMALL)
        
        # Load initial data
        self.refresh_lens_list()
    
    
    def refresh_lens_list(self):
        """Refresh the lens listbox with current lenses"""
        self.listbox.delete(0, tk.END)
        for lens in self.lens_list:
            display_text = f"{lens.name} ({lens.lens_type})"
            self.listbox.insert(tk.END, display_text)
    
    def update_info(self, event=None):
        """Update the lens information panel when selection changes"""
        selection = self.listbox.curselection()
        if not selection:
            self.info_text.config(state='normal')
            self.info_text.delete(1.0, tk.END)
            self.info_text.insert(1.0, "Select a lens to view details")
            self.info_text.config(state='disabled')
            return
        
        index = selection[0]
        if 0 <= index < len(self.lens_list):
            lens = self.lens_list[index]
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
        selection = self.listbox.curselection()
        if not selection:
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
                self.info_text.config(state='normal')
                self.info_text.delete(1.0, tk.END)
                self.info_text.insert(1.0, "Select a lens to view details")
                self.info_text.config(state='disabled')


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
        self.current_lens = None
        self.entry_fields = {}
        self.result_labels = {}
        self.auto_update_var = None
        self.material_var = None
        self.material_menu = None
    
    def setup_ui(self, parent_frame):
        """Set up the editor tab UI"""
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
        props_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=PADDING_SMALL, pady=PADDING_SMALL)
        
        # Create input fields
        self.create_property_fields(props_frame)
        
        # Material selection
        material_frame = ttk.LabelFrame(scrollable_frame, text="Material", padding=PADDING_MEDIUM)
        material_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), padx=PADDING_SMALL, pady=PADDING_SMALL)
        self.create_material_selector(material_frame)
        
        # Results frame
        results_frame = ttk.LabelFrame(scrollable_frame, text="Calculated Properties", padding=PADDING_MEDIUM)
        results_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), padx=PADDING_SMALL, pady=PADDING_SMALL)
        
        # Create result labels
        self.create_result_fields(results_frame)
        
        # Control buttons
        button_frame = ttk.Frame(scrollable_frame)
        button_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), padx=PADDING_SMALL, pady=PADDING_MEDIUM)
        
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
                combo.grid(row=i, column=1, sticky=(tk.W, tk.E), padx=PADDING_SMALL, pady=PADDING_SMALL)
                combo.bind('<<ComboboxSelected>>', self.on_field_changed)
                self.entry_fields[key] = combo
            else:
                entry = ttk.Entry(parent, width=20)
                entry.grid(row=i, column=1, sticky=(tk.W, tk.E), padx=PADDING_SMALL, pady=PADDING_SMALL)
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
        self.material_menu.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=PADDING_SMALL, pady=PADDING_SMALL)
        self.material_menu.bind('<<ComboboxSelected>>', self.on_material_changed)
        
        parent.columnconfigure(1, weight=1)
    
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
        
        self.entry_fields['name'].delete(0, tk.END)
        self.entry_fields['name'].insert(0, lens.name)
        
        if 'lens_type' in self.entry_fields:
            self.entry_fields['lens_type'].set(lens.lens_type if hasattr(lens, 'lens_type') else "Biconvex")
        
        self.entry_fields['radius1'].delete(0, tk.END)
        self.entry_fields['radius1'].insert(0, str(lens.radius_of_curvature_1))
        
        self.entry_fields['radius2'].delete(0, tk.END)
        self.entry_fields['radius2'].insert(0, str(lens.radius_of_curvature_2))
        
        self.entry_fields['thickness'].delete(0, tk.END)
        self.entry_fields['thickness'].insert(0, str(lens.thickness))
        
        self.entry_fields['diameter'].delete(0, tk.END)
        self.entry_fields['diameter'].insert(0, str(lens.diameter))
        
        self.entry_fields['n'].delete(0, tk.END)
        self.entry_fields['n'].insert(0, str(lens.refractive_index))
        
        # Set material if available
        if self.material_var and hasattr(lens, 'material'):
            self.material_var.set(lens.material)
        
        self.calculate_properties()
    
    def clear_fields(self):
        """Clear all input fields"""
        for entry in self.entry_fields.values():
            entry.delete(0, tk.END)
        
        for label in self.result_labels.values():
            label.config(text="N/A")
    
    def on_field_changed(self, event=None):
        """Handle field change event for auto-calculation"""
        if self.auto_update_var and self.auto_update_var.get():
            self.calculate_properties()
    
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
    
    def save_changes(self):
        """Save changes to the current lens"""
        if self.current_lens is None:
            try:
                from tkinter import messagebox
                messagebox.showwarning("No Lens", "No lens selected to save changes")
            except:
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
            
            # Update timestamp
            from datetime import datetime
            self.current_lens.modified_at = datetime.now().isoformat()
            
            # Notify parent
            if self.on_lens_updated_callback:
                self.on_lens_updated_callback(self.current_lens)
            
            try:
                from tkinter import messagebox
                messagebox.showinfo("Success", "Lens updated successfully")
            except:
                pass
            
        except ValueError as e:
            try:
                from tkinter import messagebox
                messagebox.showerror("Invalid Input", f"Please check your input values: {e}")
            except:
                pass
    
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
        self.current_lens = None
        self.ray_tracer = None
        
        # UI elements
        self.sim_figure = None
        self.sim_ax = None
        self.sim_canvas = None
        self.sim_canvas_widget = None
        self.num_rays_var = None
        self.ray_angle_var = None
    
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
        sim_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=PADDING_MEDIUM)
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
        controls_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=PADDING_MEDIUM)
        
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
        
        # Create ray tracer if dependencies available
        try:
            from ray_tracer import LensRayTracer
            if lens:
                self.ray_tracer = LensRayTracer(lens)
        except ImportError:
            self.ray_tracer = None
    
    def run_simulation(self):
        """Run ray tracing simulation"""
        if self.current_lens is None:
            try:
                from tkinter import messagebox
                messagebox.showwarning("No Lens", "Please select a lens first")
            except:
                pass
            return
        
        if self.ray_tracer is None:
            try:
                from tkinter import messagebox
                messagebox.showerror("Unavailable", 
                                   "Ray tracing requires numpy. Install with: pip install numpy")
            except:
                pass
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
                messagebox.showerror("Invalid Input", f"Please check your input values: {e}")
            except:
                pass
        except Exception as e:
            try:
                from tkinter import messagebox
                messagebox.showerror("Simulation Error", f"Error during simulation: {e}")
            except:
                pass
    
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
        
        # Redraw axes
        self.sim_ax.set_xlim(-100, 150)
        self.sim_ax.set_ylim(-30, 30)
        self.sim_ax.axhline(y=0, color='gray', linestyle='--', linewidth=1, alpha=0.3)
        self.sim_ax.set_xlabel('Position (mm)', fontsize=FONT_SIZE_NORMAL, color=COLOR_FG)
        self.sim_ax.set_ylabel('Height (mm)', fontsize=FONT_SIZE_NORMAL, color=COLOR_FG)
        self.sim_ax.set_title(f'Ray Tracing - {self.current_lens.name}', 
                            fontsize=12, color=COLOR_FG)
        self.sim_ax.grid(True, alpha=0.2, color=COLOR_BG_LIGHT)
        self.sim_ax.set_aspect('equal')
        self.sim_ax.tick_params(colors=COLOR_FG, labelsize=9)
        for spine in self.sim_ax.spines.values():
            spine.set_color(COLOR_BG_LIGHT)
        
        # Draw lens surfaces
        self._draw_lens()
        
        # Draw rays
        for i, ray_data in enumerate(rays):
            if ray_data and 'segments' in ray_data:
                for segment in ray_data['segments']:
                    x_coords = [segment['start'][0], segment['end'][0]]
                    y_coords = [segment['start'][1], segment['end'][1]]
                    self.sim_ax.plot(x_coords, y_coords, 'b-', alpha=0.6, linewidth=1)
        
        # Redraw canvas
        self.sim_canvas.draw()
    
    def _draw_lens(self):
        """Draw lens outline on the plot"""
        if not self.current_lens:
            return
        
        # Simple lens representation - two curved lines
        import numpy as np
        
        r1 = self.current_lens.radius_of_curvature_1
        r2 = self.current_lens.radius_of_curvature_2
        thickness = self.current_lens.thickness
        diameter = self.current_lens.diameter
        
        # Draw first surface
        if abs(r1) < 10000:
            theta = np.linspace(-np.pi/4, np.pi/4, 50)
            x1 = r1 * (1 - np.cos(theta))
            y1 = r1 * np.sin(theta)
            y1 = y1[np.abs(y1) <= diameter/2]
            x1 = x1[:len(y1)]
            self.sim_ax.plot(x1, y1, 'k-', linewidth=2)
        else:
            # Flat surface
            self.sim_ax.plot([0, 0], [-diameter/2, diameter/2], 'k-', linewidth=2)
        
        # Draw second surface
        if abs(r2) < 10000:
            theta = np.linspace(-np.pi/4, np.pi/4, 50)
            x2 = thickness + r2 * (1 - np.cos(theta))
            y2 = r2 * np.sin(theta)
            y2 = y2[np.abs(y2) <= diameter/2]
            x2 = x2[:len(y2)]
            self.sim_ax.plot(x2, y2, 'k-', linewidth=2)
        else:
            # Flat surface
            self.sim_ax.plot([thickness, thickness], [-diameter/2, diameter/2], 'k-', linewidth=2)
    
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
        metrics_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=PADDING_MEDIUM)
        metrics_frame.columnconfigure(0, weight=1)
        metrics_frame.rowconfigure(0, weight=1)
        
        # Text widget for metrics display
        metrics_scroll = ttk.Scrollbar(metrics_frame)
        metrics_scroll.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        self.metrics_text = tk.Text(metrics_frame, height=20, width=80,
                                   wrap=tk.WORD,
                                   bg=self.colors.get('entry_bg', '#2b2b2b'),
                                   fg=self.colors.get('fg', '#e0e0e0'),
                                   font=('Courier', 10),
                                   yscrollcommand=metrics_scroll.set)
        self.metrics_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        metrics_scroll.config(command=self.metrics_text.yview)
        
        self.metrics_text.insert('1.0', "Select a lens and click 'Calculate Metrics' to view performance data.")
        self.metrics_text.config(state='disabled')
        
        # Controls
        controls_frame = ttk.LabelFrame(parent_frame, text="Calculation Parameters", 
                                       padding=PADDING_MEDIUM)
        controls_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=PADDING_MEDIUM)
        
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
        ttk.Button(btn_frame, text="Export Report", 
                  command=self.export_report).pack(side=tk.LEFT, padx=PADDING_SMALL)
    
    def load_lens(self, lens):
        """Load lens for analysis"""
        self.current_lens = lens
    
    def calculate_metrics(self):
        """Calculate performance metrics for current lens"""
        if self.current_lens is None:
            try:
                from tkinter import messagebox
                messagebox.showwarning("No Lens", "Please select a lens first")
            except:
                pass
            return
        
        if not self.aberrations_available:
            result = "Performance analysis requires numpy and scipy.\n"
            result += "Install with: pip install numpy scipy\n"
            self.metrics_text.config(state='normal')
            self.metrics_text.delete(1.0, tk.END)
            self.metrics_text.insert(1.0, result)
            self.metrics_text.config(state='disabled')
            return
        
        try:
            # Get parameters
            entrance_pupil = float(self.entrance_pupil_var.get())
            wavelength = float(self.wavelength_var.get())
            object_distance = float(self.object_distance_var.get())
            sensor_size = float(self.sensor_size_var.get())
            
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
                messagebox.showerror("Invalid Input", f"Please check your input values: {e}")
            except:
                pass
        except Exception as e:
            try:
                from tkinter import messagebox
                messagebox.showerror("Calculation Error", f"Error during calculation: {e}")
            except:
                pass
    
    def export_report(self):
        """Export performance report to file"""
        if self.current_lens is None:
            try:
                from tkinter import messagebox
                messagebox.showwarning("No Lens", "No analysis to export")
            except:
                pass
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
                messagebox.showinfo("Success", f"Report exported to {filename}")
        except Exception as e:
            try:
                from tkinter import messagebox
                messagebox.showerror("Export Error", f"Failed to export: {e}")
            except:
                pass


class ComparisonController:
    """
    Controller for comparing multiple lenses.
    
    Responsibilities:
    - Select lenses for comparison
    - Display comparative metrics
    - Generate comparison charts
    """
    
    def __init__(self, parent_window, lens_list):
        """Initialize the comparison controller"""
        self.window = parent_window
        self.lens_list = lens_list
        self.selected_lenses = []
        self.listbox = None
        self.comparison_text = None
    
    def setup_ui(self, parent_frame):
        """Set up the comparison tab UI"""
        # Selection frame
        select_frame = ttk.LabelFrame(parent_frame, text="Select Lenses to Compare", padding=10)
        select_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)
        
        scrollbar = ttk.Scrollbar(select_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.listbox = tk.Listbox(select_frame, selectmode=tk.MULTIPLE,
                                  yscrollcommand=scrollbar.set, height=10)
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.listbox.yview)
        
        # Button frame
        button_frame = ttk.Frame(parent_frame, padding=10)
        button_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), padx=5, pady=5)
        
        ttk.Button(button_frame, text="Compare Selected", 
                  command=self.compare_lenses).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Clear Selection", 
                  command=self.clear_selection).pack(side=tk.LEFT, padx=5)
        
        # Results frame
        results_frame = ttk.LabelFrame(parent_frame, text="Comparison Results", padding=10)
        results_frame.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)
        
        result_scrollbar = ttk.Scrollbar(results_frame)
        result_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.comparison_text = tk.Text(results_frame, height=15, width=80,
                                       yscrollcommand=result_scrollbar.set, wrap=tk.WORD)
        self.comparison_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        result_scrollbar.config(command=self.comparison_text.yview)
        
        self.refresh_lens_list()
    
    def refresh_lens_list(self):
        """Refresh the lens selection listbox"""
        self.listbox.delete(0, tk.END)
        for lens in self.lens_list():
            self.listbox.insert(tk.END, f"{lens.name} ({lens.lens_type})")
    
    def compare_lenses(self):
        """Compare selected lenses"""
        selection = self.listbox.curselection()
        if len(selection) < 2:
            messagebox.showwarning("Selection", "Please select at least 2 lenses to compare")
            return
        
        lenses = [self.lens_list()[i] for i in selection]
        
        # Build comparison table
        result = "Lens Comparison\n"
        result += "=" * 80 + "\n\n"
        result += f"{'Property':<25} " + " ".join([f"{lens.name[:15]:>15}" for lens in lenses]) + "\n"
        result += "-" * 80 + "\n"
        
        # Compare properties
        result += f"{'Type':<25} " + " ".join([f"{lens.lens_type[:15]:>15}" for lens in lenses]) + "\n"
        result += f"{'Material':<25} " + " ".join([f"{lens.material[:15]:>15}" for lens in lenses]) + "\n"
        result += f"{'Diameter (mm)':<25} " + " ".join([f"{lens.diameter:>15.2f}" for lens in lenses]) + "\n"
        result += f"{'Thickness (mm)':<25} " + " ".join([f"{lens.thickness:>15.2f}" for lens in lenses]) + "\n"
        result += f"{'R1 (mm)':<25} " + " ".join([f"{lens.radius_of_curvature_1:>15.2f}" for lens in lenses]) + "\n"
        result += f"{'R2 (mm)':<25} " + " ".join([f"{lens.radius_of_curvature_2:>15.2f}" for lens in lenses]) + "\n"
        
        # Calculated properties
        focal_lengths = []
        for lens in lenses:
            try:
                fl = lens.calculate_focal_length()
                focal_lengths.append(f"{fl:>15.2f}" if fl else f"{'N/A':>15}")
            except:
                focal_lengths.append(f"{'Error':>15}")
        
        result += f"{'Focal Length (mm)':<25} " + " ".join(focal_lengths) + "\n"
        
        self.comparison_text.delete(1.0, tk.END)
        self.comparison_text.insert(1.0, result)
    
    def clear_selection(self):
        """Clear the selection"""
        self.listbox.selection_clear(0, tk.END)
        self.comparison_text.delete(1.0, tk.END)


class ExportController:
    """
    Controller for exporting lens data to various formats.
    
    Responsibilities:
    - Export to JSON
    - Export to STL
    - Export technical drawings
    - Generate reports
    """
    
    def __init__(self, parent_window):
        """Initialize the export controller"""
        self.window = parent_window
        self.current_lens = None
    
    def setup_ui(self, parent_frame):
        """Set up the export tab UI"""
        # Export options frame
        options_frame = ttk.LabelFrame(parent_frame, text="Export Options", padding=20)
        options_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=5, pady=5)
        
        row = 0
        
        # JSON Export
        ttk.Label(options_frame, text="JSON Format:", font=('Arial', 10, 'bold')).grid(
            row=row, column=0, sticky=tk.W, pady=5)
        row += 1
        ttk.Label(options_frame, text="Export lens data as JSON").grid(
            row=row, column=0, sticky=tk.W, padx=20)
        ttk.Button(options_frame, text="Export JSON", 
                  command=self.export_json).grid(row=row, column=1, padx=5)
        row += 1
        
        # STL Export
        ttk.Separator(options_frame, orient=tk.HORIZONTAL).grid(
            row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)
        row += 1
        
        ttk.Label(options_frame, text="3D Model (STL):", font=('Arial', 10, 'bold')).grid(
            row=row, column=0, sticky=tk.W, pady=5)
        row += 1
        ttk.Label(options_frame, text="Export 3D model for CAD/3D printing").grid(
            row=row, column=0, sticky=tk.W, padx=20)
        ttk.Button(options_frame, text="Export STL", 
                  command=self.export_stl).grid(row=row, column=1, padx=5)
        row += 1
        
        # Technical Report
        ttk.Separator(options_frame, orient=tk.HORIZONTAL).grid(
            row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)
        row += 1
        
        ttk.Label(options_frame, text="Technical Report:", font=('Arial', 10, 'bold')).grid(
            row=row, column=0, sticky=tk.W, pady=5)
        row += 1
        ttk.Label(options_frame, text="Generate detailed technical report").grid(
            row=row, column=0, sticky=tk.W, padx=20)
        ttk.Button(options_frame, text="Generate Report", 
                  command=self.export_report).grid(row=row, column=1, padx=5)
    
    def load_lens(self, lens):
        """Load lens for export"""
        self.current_lens = lens
    
    def export_json(self):
        """Export lens to JSON file"""
        if self.current_lens is None:
            messagebox.showwarning("No Lens", "Please select a lens first")
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
                messagebox.showinfo("Success", f"Lens exported to {filename}")
            except Exception as e:
                messagebox.showerror("Export Error", f"Failed to export: {e}")
    
    def export_stl(self):
        """Export lens to STL file"""
        if self.current_lens is None:
            messagebox.showwarning("No Lens", "Please select a lens first")
            return
        
        try:
            from stl_export import export_lens_stl
        except ImportError:
            messagebox.showerror("Not Available", 
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
                messagebox.showinfo("Success", f"3D model exported to {filename}")
            except Exception as e:
                messagebox.showerror("Export Error", f"Failed to export: {e}")
    
    def export_report(self):
        """Generate and export technical report"""
        if self.current_lens is None:
            messagebox.showwarning("No Lens", "Please select a lens first")
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
        except:
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
                messagebox.showinfo("Success", f"Report exported to {filename}")
            except Exception as e:
                messagebox.showerror("Export Error", f"Failed to export: {e}")


# Export controllers
__all__ = [
    'LensSelectionController',
    'LensEditorController',
    'SimulationController',
    'PerformanceController',
    'ComparisonController',
    'ExportController'
]
