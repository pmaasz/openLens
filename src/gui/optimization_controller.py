"""
Controller for Optical System Optimization.

Manages the UI and logic for setting up and running optimizations:
- variable selection
- target definition
- execution
- result application
"""

import tkinter as tk
from tkinter import ttk
import logging
from typing import List, Dict, Any, Optional, Tuple, TYPE_CHECKING
import threading
import copy

if TYPE_CHECKING:
    from ..lens import Lens
    from ..optical_system import OpticalSystem
    from ..gui.main_window import LensEditorWindow

try:
    from ..optimizer import (
        LensOptimizer, OptimizationVariable, OptimizationTarget, OptimizationResult
    )
except ImportError:
    try:
        from optimizer import (
            LensOptimizer, OptimizationVariable, OptimizationTarget, OptimizationResult
        )
    except ImportError:
        # Fallback for dev environment or different structure
        import sys
        import os
        sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))
        from src.optimizer import (
            LensOptimizer, OptimizationVariable, OptimizationTarget, OptimizationResult
        )

logger = logging.getLogger(__name__)


class OptimizationController:
    """
    Controller for the optimization tab.
    """

    def __init__(self, colors: Dict[str, str], on_lens_updated: Optional[callable] = None):
        self.colors = colors
        self.on_lens_updated_callback = on_lens_updated
        self.parent_window: Optional['LensEditorWindow'] = None
        self.current_lens: Optional['OpticalSystem'] = None
        
        # UI Components
        self.variables_frame = None
        self.targets_frame = None
        self.results_frame = None
        self.log_text = None
        
        # State
        self.variable_vars: Dict[str, tk.BooleanVar] = {}
        self.target_vars: Dict[str, Any] = {}
        self.is_optimizing = False
        self.cancel_optimization = False
        self.temp_optimized_lens: Optional['OpticalSystem'] = None

    def setup_ui(self, parent_frame: ttk.Frame):
        """Set up the optimization tab UI"""
        
        # Create a container for scrolling
        self.canvas = tk.Canvas(parent_frame, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(parent_frame, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Make canvas width follow the window
        def _on_canvas_configure(event):
            self.canvas.itemconfig(1, width=event.width)
        self.canvas.bind("<Configure>", _on_canvas_configure)

        # Main layout: Fixed width columns using grid
        main_content = ttk.Frame(self.scrollable_frame)
        main_content.pack(fill=tk.BOTH, expand=True)

        main_content.columnconfigure(0, weight=1)
        main_content.columnconfigure(1, weight=1)
        
        left_panel = ttk.Frame(main_content, padding="10")
        left_panel.grid(row=0, column=0, sticky="nsew")
        
        right_panel = ttk.Frame(main_content, padding="10")
        right_panel.grid(row=0, column=1, sticky="nsew")

        # --- Left Panel: Configuration ---
        
        # 1. Variables Section
        self.variables_frame = ttk.LabelFrame(left_panel, text="Optimization Variables", padding="5")
        self.variables_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Variables content
        self.vars_content = ttk.Frame(self.variables_frame)
        self.vars_content.pack(fill=tk.BOTH, expand=True)

        # 2. Targets Section
        self.targets_frame = ttk.LabelFrame(left_panel, text="Optimization Targets", padding="10")
        self.targets_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Target: Focal Length
        fl_frame = ttk.Frame(self.targets_frame)
        fl_frame.pack(fill=tk.X, pady=2)
        self.target_vars['focal_length_enabled'] = tk.BooleanVar(value=True)
        ttk.Checkbutton(fl_frame, text="Target Focal Length (mm):", 
                       variable=self.target_vars['focal_length_enabled']).pack(side=tk.LEFT)
        self.target_vars['focal_length_value'] = tk.DoubleVar(value=100.0)
        ttk.Entry(fl_frame, textvariable=self.target_vars['focal_length_value'], width=10).pack(side=tk.LEFT, padx=5)

        # Target: Spot Size
        ss_frame = ttk.Frame(self.targets_frame)
        ss_frame.pack(fill=tk.X, pady=2)
        self.target_vars['spot_size_enabled'] = tk.BooleanVar(value=True)
        ttk.Checkbutton(ss_frame, text="Minimize RMS Spot Size", 
                       variable=self.target_vars['spot_size_enabled']).pack(side=tk.LEFT)

        # Target: Spherical Aberration
        sa_frame = ttk.Frame(self.targets_frame)
        sa_frame.pack(fill=tk.X, pady=2)
        self.target_vars['spherical_enabled'] = tk.BooleanVar(value=False)
        ttk.Checkbutton(sa_frame, text="Minimize Spherical Aberration", 
                       variable=self.target_vars['spherical_enabled']).pack(side=tk.LEFT)
        
        # Target: Coma
        coma_frame = ttk.Frame(self.targets_frame)
        coma_frame.pack(fill=tk.X, pady=2)
        self.target_vars['coma_enabled'] = tk.BooleanVar(value=False)
        ttk.Checkbutton(coma_frame, text="Minimize Coma", 
                       variable=self.target_vars['coma_enabled']).pack(side=tk.LEFT)

        # Target: Astigmatism
        ast_frame = ttk.Frame(self.targets_frame)
        ast_frame.pack(fill=tk.X, pady=2)
        self.target_vars['astigmatism_enabled'] = tk.BooleanVar(value=False)
        ttk.Checkbutton(ast_frame, text="Minimize Astigmatism", 
                       variable=self.target_vars['astigmatism_enabled']).pack(side=tk.LEFT)
        
        # 3. Constraints / Options
        options_frame = ttk.LabelFrame(left_panel, text="Constraints & Options", padding="10")
        options_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Physical constraints grid
        constraints_grid = ttk.Frame(options_frame)
        constraints_grid.pack(fill=tk.X, pady=5)
        
        # Center Thickness Min/Max
        ttk.Label(constraints_grid, text="Min Thickness:").grid(row=0, column=0, sticky=tk.W, padx=2)
        self.target_vars['min_thickness'] = tk.DoubleVar(value=1.0)
        ttk.Entry(constraints_grid, textvariable=self.target_vars['min_thickness'], width=6).grid(row=0, column=1, sticky=tk.W)
        
        ttk.Label(constraints_grid, text="Max Thickness:").grid(row=0, column=2, sticky=tk.W, padx=2)
        self.target_vars['max_thickness'] = tk.DoubleVar(value=100.0)
        ttk.Entry(constraints_grid, textvariable=self.target_vars['max_thickness'], width=6).grid(row=0, column=3, sticky=tk.W)

        # Edge Thickness & Air Gap
        ttk.Label(constraints_grid, text="Min Edge Thick:").grid(row=1, column=0, sticky=tk.W, padx=2, pady=2)
        self.target_vars['min_edge_thickness'] = tk.DoubleVar(value=0.5)
        ttk.Entry(constraints_grid, textvariable=self.target_vars['min_edge_thickness'], width=6).grid(row=1, column=1, sticky=tk.W)

        ttk.Label(constraints_grid, text="Min Air Gap:").grid(row=1, column=2, sticky=tk.W, padx=2, pady=2)
        self.target_vars['min_air_gap'] = tk.DoubleVar(value=0.1)
        ttk.Entry(constraints_grid, textvariable=self.target_vars['min_air_gap'], width=6).grid(row=1, column=3, sticky=tk.W)
        
        # Cemented Checkbox
        self.target_vars['maintain_cemented'] = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Maintain Cemented Interfaces", 
                       variable=self.target_vars['maintain_cemented']).pack(anchor=tk.W, pady=(5,0))

        # Algorithm Selection
        algo_frame = ttk.Frame(options_frame)
        algo_frame.pack(fill=tk.X, pady=(5, 0))
        ttk.Label(algo_frame, text="Algorithm:").pack(side=tk.LEFT)
        
        self.algorithm_var = tk.StringVar(value="Local (Simplex)")
        algo_combo = ttk.Combobox(algo_frame, textvariable=self.algorithm_var, state="readonly")
        algo_combo['values'] = ("Local (Simplex)", "Global (Simulated Annealing)", "Global (Genetic Algorithm)")
        algo_combo.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        # Robust Mode Checkbox
        self.target_vars['robust_mode'] = tk.BooleanVar(value=False)
        ttk.Checkbutton(options_frame, text="Robust Mode (Yield Optimization)", 
                       variable=self.target_vars['robust_mode']).pack(anchor=tk.W, pady=(5,0))

        # 4. Actions
        actions_frame = ttk.Frame(left_panel)
        actions_frame.pack(fill=tk.X, pady=10)
        
        self.optimize_btn = ttk.Button(actions_frame, text="Run Optimization", command=self.run_optimization)
        self.optimize_btn.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)

        self.apply_btn = ttk.Button(actions_frame, text="Apply & Keep", command=self._confirm_apply, state='disabled')
        self.apply_btn.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)
        
        # --- Right Panel: Logs & Results ---
        
        # Log Output
        log_frame = ttk.LabelFrame(right_panel, text="Optimization Log", padding="5")
        log_frame.pack(fill=tk.BOTH, expand=True)
        
        self.log_text = tk.Text(log_frame, height=10, width=40, state='disabled', font=('Consolas', 9))
        self.log_text.pack(fill=tk.BOTH, expand=True)

        # Graph Area
        graph_frame = ttk.LabelFrame(right_panel, text="Merit Function History", padding="5")
        graph_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        
        self.graph_canvas = tk.Canvas(graph_frame, height=200, bg="white")
        self.graph_canvas.pack(fill=tk.BOTH, expand=True)
        self.graph_data = [] # List of (iteration, merit)


    def load_lens(self, lens: Optional[Any]):
        """Load lens data into the optimization tab"""
        self.current_lens = lens
        self.refresh_variables_list()
        
        if lens is None:
            self.log("No lens selected.")
            return

        # Auto-detect focal length to pre-fill target
        try:
            current_fl = lens.calculate_focal_length()
            if current_fl and current_fl > 0:
                self.target_vars['focal_length_value'].set(round(current_fl, 2))
        except:
            pass
            
    def refresh_variables_list(self):
        """Populate the variables list based on current lens"""
        # Clear existing
        for widget in self.vars_content.winfo_children():
            widget.destroy()
        self.variable_vars.clear()
        
        if not self.current_lens:
            ttk.Label(self.vars_content, text="No system selected").pack(pady=10)
            return

        # Check if it's a system (has elements)
        if not hasattr(self.current_lens, 'elements'):
            # Single lens case
            self._add_variable_row("Radius 1", "radius_of_curvature_1", 0)
            self._add_variable_row("Radius 2", "radius_of_curvature_2", 0)
            self._add_variable_row("Thickness", "thickness", 0)
            return

        # Multi-element system
        for i, element in enumerate(self.current_lens.elements):
            lens_name = element.lens.name or f"Lens {i+1}"
            
            # Group for this element
            group = ttk.LabelFrame(self.vars_content, text=f"{i+1}. {lens_name}", padding=2)
            group.pack(fill=tk.X, pady=2, padx=2)
            
            # R1
            self._add_variable_checkbox(group, f"R1 ({element.lens.radius_of_curvature_1:.2f})", 
                                      f"r1_{i}", default=True)
            # R2
            self._add_variable_checkbox(group, f"R2 ({element.lens.radius_of_curvature_2:.2f})", 
                                      f"r2_{i}", default=True)
            # Thickness
            self._add_variable_checkbox(group, f"Thick ({element.lens.thickness:.2f})", 
                                      f"th_{i}", default=False)
            
            # Glass Properties
            # Get current Vd for display
            vd_display = 0.0
            nd_display = element.lens.refractive_index
            
            if element.lens.model_glass_mode:
                nd_display = element.lens.model_nd
                vd_display = element.lens.model_vd
            else:
                # Try to look up Vd from material name
                try:
                    # Import here to avoid circular deps if any
                    from ..material_database import get_material_database
                    db = get_material_database()
                    mat = db.get_material(element.lens.material)
                    if mat:
                        vd_display = mat.vd
                except:
                    pass
            
            self._add_variable_checkbox(group, f"Index ({nd_display:.4f})", 
                                      f"nd_{i}", default=False)
            self._add_variable_checkbox(group, f"Abbe ({vd_display:.1f})", 
                                      f"vd_{i}", default=False)
            
            # Air gap (if not last)
            if i < len(self.current_lens.air_gaps):
                gap = self.current_lens.air_gaps[i]
                self._add_variable_checkbox(group, f"Air Gap ({gap.thickness:.2f})", 
                                          f"gap_{i}", default=True)

    def _add_variable_checkbox(self, parent, text, key, default=False):
        var = tk.BooleanVar(value=default)
        self.variable_vars[key] = var
        ttk.Checkbutton(parent, text=text, variable=var).pack(anchor=tk.W)

    def _add_variable_row(self, label, param, index):
        # Helper for single lens mode (simplified)
        frame = ttk.Frame(self.vars_content)
        frame.pack(fill=tk.X)
        var = tk.BooleanVar(value=True)
        self.variable_vars[f"{param}_{index}"] = var
        ttk.Checkbutton(frame, text=label, variable=var).pack(side=tk.LEFT)

    def log(self, message: str):
        """Append message to log (Thread-safe)"""
        # Also log to system logger (safe from any thread)
        logger.info(message)
        
        # Schedule UI update on main thread if needed
        if threading.current_thread() is not threading.main_thread():
            if self.parent_window:
                self.parent_window.root.after(0, lambda: self._log_to_ui(message))
            return

        self._log_to_ui(message)

    def _log_to_ui(self, message: str):
        if not self.log_text:
            return
            
        try:
            self.log_text.config(state='normal')
            self.log_text.insert(tk.END, message + "\n")
            self.log_text.see(tk.END)
            self.log_text.config(state='disabled')
        except tk.TclError:
            pass # Window destroyed

    def _update_graph(self):
        """Redraw the graph with current data"""
        if not self.graph_data:
            return
            
        w = self.graph_canvas.winfo_width()
        h = self.graph_canvas.winfo_height()
        # Fallback if unmapped
        if w <= 1: w = 300
        if h <= 1: h = 200
        
        self.graph_canvas.delete("all")
        
        # Margins
        pad_x = 30
        pad_y = 20
        plot_w = w - 2*pad_x
        plot_h = h - 2*pad_y
        
        # Axis lines
        self.graph_canvas.create_line(pad_x, h-pad_y, w-pad_x, h-pad_y, width=2) # X
        self.graph_canvas.create_line(pad_x, h-pad_y, pad_x, pad_y, width=2) # Y
        
        # Data range
        iterations = [d[0] for d in self.graph_data]
        merits = [d[1] for d in self.graph_data]
        
        if not iterations: return
        
        max_iter = max(iterations) if iterations else 1
        max_merit = max(merits) if merits else 1.0
        min_merit = min(merits) if merits else 0.0
        
        # Scaling
        # Avoid div by zero
        x_scale = plot_w / max_iter if max_iter > 0 else 1
        
        merit_range = max_merit - min_merit
        if merit_range < 1e-9: merit_range = 1.0
        y_scale = plot_h / merit_range
        
        # Draw points
        points = []
        for it, val in self.graph_data:
            x = pad_x + it * x_scale
            # Y is inverted (0 at top)
            # Normalized value from 0 to 1 (0 being min_merit)
            norm_val = (val - min_merit)
            y = (h - pad_y) - (norm_val * y_scale)
            points.append((x, y))
            
        if len(points) > 1:
            self.graph_canvas.create_line(points, fill="blue", width=2, smooth=True)
            
        # Draw labels
        # Min/Max Y
        self.graph_canvas.create_text(pad_x - 5, pad_y, text=f"{max_merit:.2g}", anchor="e", font=("Arial", 8))
        self.graph_canvas.create_text(pad_x - 5, h-pad_y, text=f"{min_merit:.2g}", anchor="e", font=("Arial", 8))
        
        # Max X
        self.graph_canvas.create_text(w-pad_x, h-pad_y+10, text=f"{max_iter}", anchor="n", font=("Arial", 8))


    def run_optimization(self):
        """Execute the optimization process"""
        if not self.current_lens:
            return
            
        # Validate inputs before starting (Handle TclError for non-numeric input)
        try:
            config = {
                'variables': {k: v.get() for k, v in self.variable_vars.items()},
                'targets': {
                    'focal_length_enabled': self.target_vars['focal_length_enabled'].get(),
                    'focal_length_value': self.target_vars['focal_length_value'].get(),
                    'spot_size_enabled': self.target_vars['spot_size_enabled'].get(),
                    'spherical_enabled': self.target_vars['spherical_enabled'].get(),
                    'coma_enabled': self.target_vars['coma_enabled'].get(),
                    'astigmatism_enabled': self.target_vars['astigmatism_enabled'].get(),
                    'min_thickness': self.target_vars['min_thickness'].get(),
                    'max_thickness': self.target_vars['max_thickness'].get(),
                    'min_air_gap': self.target_vars['min_air_gap'].get(),
                    'min_edge_thickness': self.target_vars['min_edge_thickness'].get(),
                    'maintain_cemented': self.target_vars['maintain_cemented'].get(),
                    'robust_mode': self.target_vars['robust_mode'].get(),
                },
                'algorithm': self.algorithm_var.get() if hasattr(self, 'algorithm_var') else "Local (Simplex)"
            }
        except (tk.TclError, ValueError) as e:
            from tkinter import messagebox
            messagebox.showerror("Input Error", f"Invalid numeric input in optimization settings.\n\nPlease ensure all targets and constraints are valid numbers.\n\nDetails: {str(e)}")
            return

        self.optimize_btn.config(state='disabled', text="Optimizing...")
        self.log_text.config(state='normal')
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state='disabled')
        self.log("Starting optimization...")
        
        # Reset graph
        self.graph_data = []
        self.graph_canvas.delete("all")
        
        # Deepcopy lens for thread safety
        try:
            lens_copy = copy.deepcopy(self.current_lens)
        except Exception as e:
            self.log(f"Error copying lens: {e}")
            self._optimization_finished(False)
            return

        # Run in thread to keep UI responsive
        threading.Thread(target=self._optimization_worker, args=(lens_copy, config), daemon=True).start()

    def _optimization_worker(self, current_lens_copy, config):
        try:
            # Use local copy instead of self.current_lens
            current_lens = current_lens_copy
            
            # Callback for live updates
            def update_ui(iteration, merit, values):
                self.graph_data.append((iteration, merit))
                if iteration % 5 == 0: # Throttle UI updates
                    if self.parent_window:
                        self.parent_window.root.after(0, self._update_graph_and_log, iteration, merit)

            # 1. Collect Variables
            variables: List[OptimizationVariable] = []
            
            # Get constraints from config
            min_thickness = config['targets']['min_thickness']
            max_thickness = config['targets']['max_thickness']
            min_air_gap = config['targets']['min_air_gap']
            min_edge_thickness = config['targets']['min_edge_thickness']
            
            # Package constraints for optimizer
            constraints = {
                'min_center_thickness': min_thickness,
                'max_center_thickness': max_thickness,
                'min_edge_thickness': min_edge_thickness,
                'min_air_gap': min_air_gap,
                'min_edge_clearance': 0.1 # Default, maybe add UI later
            }

            is_single_lens_optimization = False
            temp_system = None
            
            # Identify cemented interfaces first if option enabled
            cemented_pairs = [] # List of (index_prev, index_next)
            if config['targets']['maintain_cemented'] and hasattr(current_lens, 'elements'):
                 for i in range(len(current_lens.elements) - 1):
                    # Check if air gap is effectively zero (cemented)
                    if i < len(current_lens.air_gaps):
                        gap = current_lens.air_gaps[i].thickness
                        if gap < 0.01: # Threshold for "cemented"
                            # Check if radii match (R2 of first == R1 of second)
                            r2_prev = current_lens.elements[i].lens.radius_of_curvature_2
                            r1_next = current_lens.elements[i+1].lens.radius_of_curvature_1
                            if abs(r2_prev - r1_next) < 0.1: # Tolerance
                                cemented_pairs.append((i, i+1))
                                self.log(f"Detected cemented interface between Element {i+1} and {i+2}")

            # Collect from UI selections using config['variables']
            if hasattr(current_lens, 'elements'):
                num_elements = len(current_lens.elements)
                
                for i in range(num_elements):
                    # R1
                    if config['variables'].get(f"r1_{i}", False):
                        # Check if this is the SECOND part of a cemented pair
                        is_cemented_secondary = any(pair[1] == i for pair in cemented_pairs)
                        if not is_cemented_secondary:
                            current_val = current_lens.elements[i].lens.radius_of_curvature_1
                            var = OptimizationVariable(
                                name=f"R1_Elem{i+1}",
                                element_index=i,
                                parameter="radius_of_curvature_1",
                                current_value=current_val,
                                min_value=-1000, max_value=1000
                            )
                            variables.append(var)
                        
                    # R2
                    if config['variables'].get(f"r2_{i}", False):
                        current_val = current_lens.elements[i].lens.radius_of_curvature_2
                        var = OptimizationVariable(
                            name=f"R2_Elem{i+1}",
                            element_index=i,
                            parameter="radius_of_curvature_2",
                            current_value=current_val,
                            min_value=-1000, max_value=1000
                        )
                        
                        # Check if this forms a cemented interface with next element
                        for pair in cemented_pairs:
                            if pair[0] == i: # This is the first element of pair
                                next_idx = pair[1]
                                # Link R1 of next element to this variable
                                var.linked_targets.append((next_idx, "radius_of_curvature_1"))
                                self.log(f"  Linking R1 of Element {next_idx+1} to {var.name}")
                        
                        variables.append(var)

                    # Thickness
                    if config['variables'].get(f"th_{i}", False):
                        current_val = current_lens.elements[i].lens.thickness
                        var = OptimizationVariable(
                            name=f"Th_Elem{i+1}",
                            element_index=i,
                            parameter="thickness",
                            current_value=current_val,
                            min_value=min_thickness, max_value=max_thickness
                        )
                        variables.append(var)

                    # Refractive Index (Nd)
                    if config['variables'].get(f"nd_{i}", False):
                         elem_lens = current_lens.elements[i].lens
                         val = elem_lens.model_nd if elem_lens.model_glass_mode else elem_lens.refractive_index
                         
                         var = OptimizationVariable(
                            name=f"Nd_Elem{i+1}",
                            element_index=i,
                            parameter="refractive_index",
                            current_value=val,
                            min_value=1.3, max_value=2.4,
                            step_size=0.01
                         )
                         variables.append(var)

                    # Abbe Number (Vd)
                    if config['variables'].get(f"vd_{i}", False):
                         elem_lens = current_lens.elements[i].lens
                         val = 64.17 # Default fallback
                         
                         if elem_lens.model_glass_mode:
                             val = elem_lens.model_vd
                         else:
                             try:
                                 from ..material_database import get_material_database
                                 db = get_material_database()
                                 mat = db.get_material(elem_lens.material)
                                 if mat: val = mat.vd
                             except: pass
                             
                         var = OptimizationVariable(
                            name=f"Vd_Elem{i+1}",
                            element_index=i,
                            parameter="abbe_number",
                            current_value=val,
                            min_value=10.0, max_value=100.0,
                            step_size=1.0
                         )
                         variables.append(var)

                    # Air Gap
                    if i < num_elements - 1:
                        if config['variables'].get(f"gap_{i}", False):
                            # Check if it's cemented -> if so, DON'T optimize gap usually? 
                            is_cemented = any(pair[0] == i for pair in cemented_pairs)
                            if not is_cemented:
                                current_val = current_lens.air_gaps[i].thickness
                                var = OptimizationVariable(
                                    name=f"Gap_{i+1}-{i+2}",
                                    element_index=i,
                                    parameter="air_gap",
                                    current_value=current_val,
                                    min_value=min_air_gap, max_value=100.0
                                )
                                variables.append(var)
            else:
                # Single lens logic
                # Create temporary OpticalSystem to wrap the lens
                try:
                    from ..optical_system import OpticalSystem
                except ImportError:
                    try:
                        from optical_system import OpticalSystem
                    except ImportError:
                        logger.error("Could not import OpticalSystem for single lens optimization")
                        self.log("Error: OpticalSystem class missing")
                        self._optimization_finished(False)
                        return
                        
                # Ensure constraints are valid for single lens too
                temp_system = OpticalSystem()
                temp_system.add_lens(current_lens)
                
                # R1
                if config['variables'].get("radius_of_curvature_1_0", False):
                    var = OptimizationVariable(
                        name="R1",
                        element_index=0,
                        parameter="radius_of_curvature_1",
                        current_value=current_lens.radius_of_curvature_1,
                        min_value=-1000, max_value=1000
                    )
                    variables.append(var)

                # R2
                if config['variables'].get("radius_of_curvature_2_0", False):
                    var = OptimizationVariable(
                        name="R2",
                        element_index=0,
                        parameter="radius_of_curvature_2",
                        current_value=current_lens.radius_of_curvature_2,
                        min_value=-1000, max_value=1000
                    )
                    variables.append(var)

                # Thickness
                if config['variables'].get("thickness_0", False):
                    var = OptimizationVariable(
                        name="Thickness",
                        element_index=0,
                        parameter="thickness",
                        current_value=current_lens.thickness,
                        min_value=min_thickness, max_value=max_thickness
                    )
                    variables.append(var)

                # Optimization requires a system, so we use temp_system
                is_single_lens_optimization = True

            if not variables:
                self.log("No variables selected!")
                self._optimization_finished(False)
                return

            # 2. Collect Targets
            targets: List[OptimizationTarget] = []
            
            if config['targets']['focal_length_enabled']:
                target_val = config['targets']['focal_length_value']
                targets.append(OptimizationTarget("focal_length", target_val, weight=10.0))
            
            if config['targets']['spot_size_enabled']:
                targets.append(OptimizationTarget("rms_spot_radius", 0.0, weight=100.0, target_type="minimize"))
                
            if config['targets']['spherical_enabled']:
                targets.append(OptimizationTarget("spherical_aberration", 0.0, weight=5.0, target_type="minimize"))

            if config['targets']['coma_enabled']:
                targets.append(OptimizationTarget("coma", 0.0, weight=5.0, target_type="minimize"))

            if config['targets']['astigmatism_enabled']:
                targets.append(OptimizationTarget("astigmatism", 0.0, weight=5.0, target_type="minimize"))

            if not targets:
                self.log("No targets selected!")
                self._optimization_finished(False)
                return

            # Check robust mode
            robust_mode = config['targets']['robust_mode']
            
            # Create Optimizer
            system_to_optimize = temp_system if is_single_lens_optimization and temp_system else current_lens
            
            # Check selected algorithm
            algorithm = config['algorithm']
            
            # Robust Optimization Setup
            if robust_mode:
                try:
                    from ..desensitization import DesensitizationOptimizer
                    from ..tolerancing import ToleranceOperand, ToleranceType
                except ImportError:
                    try:
                        from desensitization import DesensitizationOptimizer
                        from tolerancing import ToleranceOperand, ToleranceType
                    except ImportError:
                        self.log("Robust optimizer not found.")
                        robust_mode = False
            
            optimizer = None
            if robust_mode and 'DesensitizationOptimizer' in locals():
                optimizer = DesensitizationOptimizer(system_to_optimize, variables, targets, constraints=constraints)
                self.log("Using Robust Optimizer (Desensitization)")
                
                # Create default tolerances based on variables
                tolerances = []
                for var in variables:
                    # Map variable to tolerance type
                    tol_type = None
                    if var.parameter == "radius_of_curvature_1": tol_type = ToleranceType.RADIUS_1
                    elif var.parameter == "radius_of_curvature_2": tol_type = ToleranceType.RADIUS_2
                    elif var.parameter == "thickness": tol_type = ToleranceType.THICKNESS
                    elif var.parameter == "refractive_index": tol_type = ToleranceType.REFRACTIVE_INDEX
                    
                    if tol_type:
                        val = 0.1
                        if tol_type == ToleranceType.REFRACTIVE_INDEX: val = 0.001
                        
                        tolerances.append(ToleranceOperand(
                            element_index=var.element_index,
                            param_type=tol_type,
                            min_val=-val, max_val=val
                        ))
                
                self.log(f"Generated {len(tolerances)} tolerances for robust optimization")
                
                result = optimizer.optimize_robust(tolerances, sensitivity_weight=1.0, max_iterations=50, callback=update_ui)
                
            else:
                # Standard Global/Local
                if "Global" in algorithm:
                    try:
                        from ..global_optimizer import GlobalOptimizer
                    except ImportError:
                        try:
                            from global_optimizer import GlobalOptimizer
                        except ImportError:
                            self.log("Global optimizer not found, falling back to local.")
                            optimizer = LensOptimizer(system_to_optimize, variables, targets, constraints=constraints)
                            algorithm = "Local (Simplex)"
                        else:
                            optimizer = GlobalOptimizer(system_to_optimize, variables, targets, constraints=constraints)
                    else:
                        optimizer = GlobalOptimizer(system_to_optimize, variables, targets, constraints=constraints)
                else:
                    optimizer = LensOptimizer(system_to_optimize, variables, targets, constraints=constraints)
                
                # 4. Run
                self.log(f"Starting optimization with {len(variables)} variables and {len(targets)} targets...")
                self.log(f"Algorithm: {algorithm}")
                
                if "Simulated Annealing" in algorithm and hasattr(optimizer, 'optimize_simulated_annealing'):
                    result = optimizer.optimize_simulated_annealing(max_iterations=1000, initial_temperature=50.0, callback=update_ui)
                elif "Genetic Algorithm" in algorithm and hasattr(optimizer, 'optimize_genetic'):
                    result = optimizer.optimize_genetic(population_size=30, generations=20, callback=update_ui)
                else:
                    result = optimizer.optimize(max_iterations=50, callback=update_ui)
            
            if result.success:
                self.log(f"Success! Merit improved from {result.initial_merit:.4f} to {result.final_merit:.4f}")
                
                if is_single_lens_optimization:
                    # Extract the optimized lens from the system result
                    result.optimized_system = result.optimized_system.elements[0].lens
                
                # Update current_lens in controller to the NEW optimized one
                # Note: This is the result object which will be passed to UI
                self.current_lens = result.optimized_system
                
                # Update UI in main thread
                if self.parent_window:
                    self.parent_window.root.after(0, lambda: self._apply_results(result))
            else:
                self.log(f"Optimization finished. {result.message}")
                if self.parent_window:
                    self.parent_window.root.after(0, lambda: self._apply_results(result))

        except Exception as e:
            logger.error(f"Optimization failed: {e}", exc_info=True)
            self.log(f"Error: {e}")
            self._optimization_finished(False)

    def _apply_results(self, result: OptimizationResult):
        """Show results and enable Apply button"""
        if result.success:
            self.temp_optimized_lens = result.optimized_system
            self.apply_btn.config(state='normal')
            
            self.log("Optimization complete. Improvements summary:")
            
            # Show parameter changes if available in history
            if result.variable_history and len(result.variable_history) > 0:
                final_vars = result.variable_history[-1]
                initial_vars = result.variable_history[0]
                
                self.log("Parameter changes:")
                for name, final_val in final_vars.items():
                    init_val = initial_vars.get(name, 0.0)
                    if abs(final_val - init_val) > 1e-6:
                        self.log(f"  {name}: {init_val:.4f} -> {final_val:.4f} (diff: {final_val-init_val:+.4f})")
            
            self.log("Click 'Apply & Keep' to save these changes to the system.")
        
        self._optimization_finished(result.success)

    def _confirm_apply(self):
        """Finalize and apply the optimization"""
        if self.temp_optimized_lens:
            self.current_lens = self.temp_optimized_lens
            if self.on_lens_updated_callback:
                self.on_lens_updated_callback(self.current_lens)
            
            # Persist to disk if parent window has save functionality
            if self.parent_window and hasattr(self.parent_window, 'save_lenses'):
                self.parent_window.save_lenses()
                self.log("Changes saved to disk.")
            
            self.log("Optimized system applied successfully.")
            self.apply_btn.config(state='disabled')
            self.temp_optimized_lens = None

    def _update_graph_and_log(self, iteration, merit):
        """Update UI from main thread"""
        self.log_text.config(state='normal')
        self.log_text.insert(tk.END, f"Iter {iteration}: Merit {merit:.4f}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state='disabled')
        
        # Redraw graph
        # Clear
        self.graph_canvas.delete("all")
        
        w = self.graph_canvas.winfo_width()
        h = self.graph_canvas.winfo_height()
        # Fallback
        if w <= 1: w = 300
        if h <= 1: h = 200
        
        pad_x = 30
        pad_y = 20
        plot_w = w - 2*pad_x
        plot_h = h - 2*pad_y
        
        # Draw Axes
        self.graph_canvas.create_line(pad_x, h-pad_y, w-pad_x, h-pad_y, width=2)
        self.graph_canvas.create_line(pad_x, h-pad_y, pad_x, pad_y, width=2)
        
        if not self.graph_data: return
        
        iterations = [d[0] for d in self.graph_data]
        merits = [d[1] for d in self.graph_data]
        
        max_iter = max(iterations) if iterations else 1
        # Start X from 0 if possible
        min_iter = min(iterations) if iterations else 0
        iter_range = max_iter - min_iter
        if iter_range == 0: iter_range = 1
        
        max_merit = max(merits) if merits else 1.0
        min_merit = min(merits) if merits else 0.0
        merit_range = max_merit - min_merit
        if merit_range < 1e-9: merit_range = 1.0
        
        x_scale = plot_w / iter_range
        y_scale = plot_h / merit_range
        
        points = []
        for it, val in self.graph_data:
            x = pad_x + (it - min_iter) * x_scale
            y = (h - pad_y) - ((val - min_merit) * y_scale)
            points.append(x)
            points.append(y)
            
        if len(points) >= 4:
            self.graph_canvas.create_line(points, fill="blue", width=2)
            
        # Labels
        self.graph_canvas.create_text(pad_x-2, pad_y, text=f"{max_merit:.2g}", anchor="e", font=("Arial", 8))
        self.graph_canvas.create_text(pad_x-2, h-pad_y, text=f"{min_merit:.2g}", anchor="e", font=("Arial", 8))
        self.graph_canvas.create_text(w-pad_x, h-pad_y+2, text=f"{max_iter}", anchor="n", font=("Arial", 8))

    def _optimization_finished(self, success):
        if self.parent_window:
            def update_ui():
                self.optimize_btn.config(state='normal', text="Run Optimization")
                if not success:
                    self.apply_btn.config(state='disabled')
            
            self.parent_window.root.after(0, update_ui)

