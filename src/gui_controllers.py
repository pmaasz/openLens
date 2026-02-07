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


class PerformanceController:
    """
    Controller for aberration analysis and performance metrics.
    
    Responsibilities:
    - Display aberration calculations
    - Show performance metrics
    - Analyze lens quality
    """
    
    def __init__(self, parent_window):
        """Initialize the performance controller"""
        self.window = parent_window
        self.current_lens = None
        self.result_text = None
    
    def setup_ui(self, parent_frame):
        """Set up the performance tab UI"""
        # Instructions
        info_frame = ttk.Frame(parent_frame, padding=10)
        info_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=5, pady=5)
        
        ttk.Label(info_frame, text="Aberration Analysis", 
                 font=('Arial', 12, 'bold')).pack(anchor=tk.W)
        ttk.Label(info_frame, text="Analyze optical aberrations and performance metrics",
                 font=('Arial', 9)).pack(anchor=tk.W, pady=5)
        
        # Results display
        results_frame = ttk.LabelFrame(parent_frame, text="Analysis Results", padding=10)
        results_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)
        
        scrollbar = ttk.Scrollbar(results_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.result_text = tk.Text(results_frame, height=20, width=80,
                                   yscrollcommand=scrollbar.set, wrap=tk.WORD)
        self.result_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.result_text.yview)
        
        # Analysis button
        button_frame = ttk.Frame(parent_frame, padding=10)
        button_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), padx=5, pady=5)
        
        ttk.Button(button_frame, text="Run Analysis", 
                  command=self.run_analysis).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Export Report", 
                  command=self.export_report).pack(side=tk.LEFT, padx=5)
    
    def load_lens(self, lens):
        """Load lens for analysis"""
        self.current_lens = lens
        if lens:
            self.run_analysis()
    
    def run_analysis(self):
        """Run aberration analysis on current lens"""
        if self.current_lens is None:
            messagebox.showwarning("No Lens", "Please select a lens first")
            return
        
        try:
            # Check if aberrations module available
            try:
                from aberrations import AberrationsCalculator, analyze_lens_quality
                
                calc = AberrationsCalculator(self.current_lens)
                spherical = calc.spherical_aberration()
                coma = calc.coma()
                chromatic = calc.chromatic_aberration()
                quality = analyze_lens_quality(self.current_lens)
                
                # Format results
                result = f"Aberration Analysis for: {self.current_lens.name}\n"
                result += "=" * 60 + "\n\n"
                result += f"Spherical Aberration: {spherical:.6f} mm\n"
                result += f"Coma: {coma:.6f} mm\n"
                result += f"Chromatic Aberration: {chromatic:.6f} mm\n\n"
                result += f"Overall Quality: {quality['quality']}\n"
                result += f"Quality Score: {quality['score']:.2f}/100\n"
                
            except ImportError:
                result = "Aberration analysis requires numpy and scipy.\n"
                result += "Install with: pip install numpy scipy\n"
            
            self.result_text.delete(1.0, tk.END)
            self.result_text.insert(1.0, result)
            
        except Exception as e:
            messagebox.showerror("Analysis Error", f"Error during analysis: {e}")
    
    def export_report(self):
        """Export analysis report to file"""
        if self.current_lens is None:
            messagebox.showwarning("No Lens", "No analysis to export")
            return
        
        # Get report content
        content = self.result_text.get(1.0, tk.END)
        
        from tkinter import filedialog
        filename = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            title="Export Analysis Report"
        )
        
        if filename:
            try:
                with open(filename, 'w') as f:
                    f.write(content)
                messagebox.showinfo("Success", f"Report exported to {filename}")
            except Exception as e:
                messagebox.showerror("Export Error", f"Failed to export: {e}")


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
