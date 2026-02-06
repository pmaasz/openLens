"""
GUI Controllers for openlens

This module provides separate controller classes to decompose the
large GUI class into manageable, focused components following the
Single Responsibility Principle.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional, List, Callable, Dict, Any
import json


class LensSelectionController:
    """
    Controller for lens selection and management in the selection tab.
    
    Responsibilities:
    - Manage lens list display
    - Handle lens selection
    - Create/delete/duplicate lenses
    - Update selection info panel
    """
    
    def __init__(self, parent_window, lens_manager):
        """
        Initialize the lens selection controller.
        
        Args:
            parent_window: Reference to main window
            lens_manager: LensManager instance for data operations
        """
        self.window = parent_window
        self.lens_manager = lens_manager
        self.selected_lens = None
        self.listbox = None
        self.info_labels = {}
        
    def setup_ui(self, parent_frame):
        """Set up the selection tab UI"""
        # List frame
        list_frame = ttk.Frame(parent_frame)
        list_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)
        
        # Scrollable listbox
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set,
                                   width=30, height=15)
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.listbox.yview)
        
        # Bind selection event
        self.listbox.bind('<<ListboxSelect>>', self.on_lens_selected)
        
        # Button frame
        button_frame = ttk.Frame(parent_frame)
        button_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), padx=5, pady=5)
        
        ttk.Button(button_frame, text="New", command=self.create_new_lens).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="Delete", command=self.delete_lens).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="Duplicate", command=self.duplicate_lens).pack(side=tk.LEFT, padx=2)
        
        # Info panel
        self.setup_info_panel(parent_frame)
        
        # Load initial data
        self.refresh_lens_list()
    
    def setup_info_panel(self, parent_frame):
        """Set up the information panel showing lens details"""
        info_frame = ttk.LabelFrame(parent_frame, text="Lens Information", padding=10)
        info_frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)
        
        fields = [
            ("Name:", "name"),
            ("Type:", "type"),
            ("Material:", "material"),
            ("Focal Length:", "focal_length"),
            ("Optical Power:", "power")
        ]
        
        for i, (label, key) in enumerate(fields):
            ttk.Label(info_frame, text=label).grid(row=i, column=0, sticky=tk.W, pady=2)
            value_label = ttk.Label(info_frame, text="N/A")
            value_label.grid(row=i, column=1, sticky=tk.W, padx=10, pady=2)
            self.info_labels[key] = value_label
    
    def refresh_lens_list(self):
        """Refresh the lens listbox with current lenses"""
        self.listbox.delete(0, tk.END)
        lenses = self.lens_manager.list_all_lenses()
        for lens in lenses:
            display_text = f"{lens.name} ({lens.lens_type})"
            self.listbox.insert(tk.END, display_text)
    
    def on_lens_selected(self, event=None):
        """Handle lens selection from listbox"""
        selection = self.listbox.curselection()
        if not selection:
            self.selected_lens = None
            self.update_info_panel(None)
            return
        
        index = selection[0]
        lenses = self.lens_manager.list_all_lenses()
        if 0 <= index < len(lenses):
            self.selected_lens = lenses[index]
            self.update_info_panel(self.selected_lens)
            
            # Notify parent window
            if hasattr(self.window, 'on_lens_selected'):
                self.window.on_lens_selected(self.selected_lens)
    
    def update_info_panel(self, lens):
        """Update the information panel with lens details"""
        if lens is None:
            for label in self.info_labels.values():
                label.config(text="N/A")
            return
        
        try:
            focal_length = lens.calculate_focal_length()
            power = lens.calculate_optical_power()
            
            self.info_labels['name'].config(text=lens.name)
            self.info_labels['type'].config(text=lens.lens_type)
            self.info_labels['material'].config(text=lens.material)
            self.info_labels['focal_length'].config(text=f"{focal_length:.2f} mm")
            self.info_labels['power'].config(text=f"{power:.2f} D")
        except Exception as e:
            for label in self.info_labels.values():
                label.config(text="Error")
    
    def create_new_lens(self):
        """Create a new lens and add to manager"""
        # Import here to avoid circular dependency
        from lens_editor import Lens
        
        new_lens = Lens(name=f"New Lens {len(self.lens_manager.list_all_lenses()) + 1}")
        self.lens_manager.add_lens(new_lens)
        self.refresh_lens_list()
        
        # Select the new lens
        self.listbox.selection_clear(0, tk.END)
        self.listbox.selection_set(tk.END)
        self.on_lens_selected()
    
    def delete_lens(self):
        """Delete the selected lens"""
        if self.selected_lens is None:
            messagebox.showwarning("No Selection", "Please select a lens to delete")
            return
        
        result = messagebox.askyesno("Confirm Delete", 
                                     f"Delete lens '{self.selected_lens.name}'?")
        if result:
            self.lens_manager.delete_lens(self.selected_lens.id)
            self.selected_lens = None
            self.refresh_lens_list()
            self.update_info_panel(None)
    
    def duplicate_lens(self):
        """Duplicate the selected lens"""
        if self.selected_lens is None:
            messagebox.showwarning("No Selection", "Please select a lens to duplicate")
            return
        
        # Import here to avoid circular dependency
        from lens_editor import Lens
        
        lens_data = self.selected_lens.to_dict()
        lens_data.pop('id')  # Remove ID to create new
        lens_data.pop('created_at')
        lens_data['name'] = f"{lens_data['name']} (Copy)"
        
        new_lens = Lens.from_dict(lens_data)
        self.lens_manager.add_lens(new_lens)
        self.refresh_lens_list()


class LensEditorController:
    """
    Controller for lens property editing.
    
    Responsibilities:
    - Manage lens property input fields
    - Validate and update lens properties
    - Calculate optical properties
    - Handle auto-update mode
    """
    
    def __init__(self, parent_window):
        """Initialize the lens editor controller"""
        self.window = parent_window
        self.current_lens = None
        self.entry_fields = {}
        self.result_labels = {}
        self.auto_update_var = None
    
    def setup_ui(self, parent_frame):
        """Set up the editor tab UI"""
        # Properties frame
        props_frame = ttk.LabelFrame(parent_frame, text="Lens Properties", padding=10)
        props_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)
        
        # Create input fields
        self.create_property_fields(props_frame)
        
        # Results frame
        results_frame = ttk.LabelFrame(parent_frame, text="Calculated Properties", padding=10)
        results_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), padx=5, pady=5)
        
        # Create result labels
        self.create_result_fields(results_frame)
        
        # Control buttons
        button_frame = ttk.Frame(parent_frame)
        button_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), padx=5, pady=5)
        
        ttk.Button(button_frame, text="Calculate", 
                  command=self.calculate_properties).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="Save Changes", 
                  command=self.save_changes).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="Reset", 
                  command=self.reset_fields).pack(side=tk.LEFT, padx=2)
        
        # Auto-update checkbox
        self.auto_update_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(button_frame, text="Auto-calculate", 
                       variable=self.auto_update_var).pack(side=tk.LEFT, padx=10)
    
    def create_property_fields(self, parent):
        """Create input fields for lens properties"""
        fields = [
            ("Name:", "name", ""),
            ("Radius 1 (mm):", "radius1", "100.0"),
            ("Radius 2 (mm):", "radius2", "-100.0"),
            ("Thickness (mm):", "thickness", "5.0"),
            ("Diameter (mm):", "diameter", "50.0"),
            ("Refractive Index:", "n", "1.5168"),
        ]
        
        for i, (label, key, default) in enumerate(fields):
            ttk.Label(parent, text=label).grid(row=i, column=0, sticky=tk.W, pady=2)
            
            entry = ttk.Entry(parent, width=20)
            entry.grid(row=i, column=1, sticky=(tk.W, tk.E), padx=5, pady=2)
            entry.insert(0, default)
            
            # Bind auto-calculate
            entry.bind('<KeyRelease>', self.on_field_changed)
            
            self.entry_fields[key] = entry
    
    def create_result_fields(self, parent):
        """Create labels for calculated results"""
        results = [
            ("Focal Length:", "focal_length"),
            ("Optical Power:", "power"),
        ]
        
        for i, (label, key) in enumerate(results):
            ttk.Label(parent, text=label).grid(row=i, column=0, sticky=tk.W, pady=2)
            
            value_label = ttk.Label(parent, text="N/A", font=('Arial', 10, 'bold'))
            value_label.grid(row=i, column=1, sticky=tk.W, padx=10, pady=2)
            
            self.result_labels[key] = value_label
    
    def load_lens(self, lens):
        """Load lens data into editor fields"""
        self.current_lens = lens
        
        if lens is None:
            self.clear_fields()
            return
        
        self.entry_fields['name'].delete(0, tk.END)
        self.entry_fields['name'].insert(0, lens.name)
        
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
            
            # Update result labels
            if abs(focal_length) > 10000:
                self.result_labels['focal_length'].config(text="∞ mm")
            else:
                self.result_labels['focal_length'].config(text=f"{focal_length:.2f} mm")
            
            self.result_labels['power'].config(text=f"{power_diopters:.2f} D")
            
        except ValueError:
            self.result_labels['focal_length'].config(text="Invalid")
            self.result_labels['power'].config(text="Invalid")
        except ZeroDivisionError:
            self.result_labels['focal_length'].config(text="∞ mm")
            self.result_labels['power'].config(text="0.00 D")
    
    def save_changes(self):
        """Save changes to the current lens"""
        if self.current_lens is None:
            messagebox.showwarning("No Lens", "No lens selected to save changes")
            return
        
        try:
            # Validate and update lens
            self.current_lens.name = self.entry_fields['name'].get()
            self.current_lens.radius_of_curvature_1 = float(self.entry_fields['radius1'].get())
            self.current_lens.radius_of_curvature_2 = float(self.entry_fields['radius2'].get())
            self.current_lens.thickness = float(self.entry_fields['thickness'].get())
            self.current_lens.diameter = float(self.entry_fields['diameter'].get())
            self.current_lens.refractive_index = float(self.entry_fields['n'].get())
            
            # Notify parent
            if hasattr(self.window, 'on_lens_updated'):
                self.window.on_lens_updated(self.current_lens)
            
            messagebox.showinfo("Success", "Lens updated successfully")
            
        except ValueError as e:
            messagebox.showerror("Invalid Input", f"Please check your input values: {e}")
    
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
    
    def __init__(self, parent_window):
        """Initialize the simulation controller"""
        self.window = parent_window
        self.current_lens = None
        self.ray_tracer = None
        self.canvas = None
    
    def setup_ui(self, parent_frame):
        """Set up the simulation tab UI"""
        # Parameter frame
        param_frame = ttk.LabelFrame(parent_frame, text="Simulation Parameters", padding=10)
        param_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=5, pady=5)
        
        ttk.Label(param_frame, text="Number of rays:").grid(row=0, column=0, sticky=tk.W)
        self.num_rays_var = tk.IntVar(value=11)
        ttk.Spinbox(param_frame, from_=3, to=51, textvariable=self.num_rays_var,
                   width=10).grid(row=0, column=1, padx=5)
        
        ttk.Button(param_frame, text="Run Simulation", 
                  command=self.run_simulation).grid(row=0, column=2, padx=5)
        
        # Canvas for visualization
        canvas_frame = ttk.Frame(parent_frame)
        canvas_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)
        
        self.canvas = tk.Canvas(canvas_frame, width=800, height=400, bg='white')
        self.canvas.pack(fill=tk.BOTH, expand=True)
    
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
            messagebox.showwarning("No Lens", "Please select a lens first")
            return
        
        if self.ray_tracer is None:
            messagebox.showerror("Unavailable", 
                               "Ray tracing requires numpy. Install with: pip install numpy")
            return
        
        try:
            num_rays = self.num_rays_var.get()
            rays = self.ray_tracer.trace_parallel_rays(num_rays=num_rays)
            self.draw_rays(rays)
        except Exception as e:
            messagebox.showerror("Simulation Error", f"Error during simulation: {e}")
    
    def draw_rays(self, rays):
        """Draw ray paths on canvas"""
        self.canvas.delete("all")
        
        # Scale and draw (simplified)
        # TODO: Implement proper scaling and drawing
        self.canvas.create_text(400, 200, text="Ray Tracing Visualization\n(Under construction)",
                               font=('Arial', 14))


# Export controllers
__all__ = [
    'LensSelectionController',
    'LensEditorController',
    'SimulationController'
]
