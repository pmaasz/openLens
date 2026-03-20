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

    def setup_ui(self, parent_frame: ttk.Frame):
        """Set up the optimization tab UI"""
        
        # Main layout: Left for config, Right for log/results
        parent_frame.columnconfigure(0, weight=1)
        parent_frame.columnconfigure(1, weight=1)
        parent_frame.rowconfigure(0, weight=1)

        left_panel = ttk.Frame(parent_frame, padding="10")
        left_panel.grid(row=0, column=0, sticky="nsew")
        
        right_panel = ttk.Frame(parent_frame, padding="10")
        right_panel.grid(row=0, column=1, sticky="nsew")

        # --- Left Panel: Configuration ---
        
        # 1. Variables Section
        self.variables_frame = ttk.LabelFrame(left_panel, text="Optimization Variables", padding="5")
        self.variables_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Scrollable area for variables
        canvas = tk.Canvas(self.variables_frame, height=250)
        scrollbar = ttk.Scrollbar(self.variables_frame, orient="vertical", command=canvas.yview)
        self.vars_content = ttk.Frame(canvas)
        
        self.vars_content.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=self.vars_content, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

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
        """Append message to log"""
        if self.log_text:
            self.log_text.config(state='normal')
            self.log_text.insert(tk.END, message + "\n")
            self.log_text.see(tk.END)
            self.log_text.config(state='disabled')
        # Also log to system logger
        logger.info(message)

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
            
        self.optimize_btn.config(state='disabled', text="Optimizing...")
        self.log_text.config(state='normal')
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state='disabled')
        self.log("Starting optimization...")
        
        # Reset graph
        self.graph_data = []
        self.graph_canvas.delete("all")
        
        # Run in thread to keep UI responsive
        threading.Thread(target=self._optimization_worker, daemon=True).start()

    def _optimization_worker(self):
        try:
            if not self.current_lens:
                return

            # Callback for live updates
            def update_ui(iteration, merit, values):
                self.graph_data.append((iteration, merit))
                if iteration % 5 == 0: # Throttle UI updates
                    if self.parent_window:
                        self.parent_window.root.after(0, self._update_graph_and_log, iteration, merit)

            # 1. Collect Variables
            variables: List[OptimizationVariable] = []
            
            # Get constraints from UI
            min_thickness = self.target_vars.get('min_thickness', tk.DoubleVar(value=1.0)).get()
            max_thickness = self.target_vars.get('max_thickness', tk.DoubleVar(value=100.0)).get()
            min_air_gap = self.target_vars.get('min_air_gap', tk.DoubleVar(value=0.1)).get()
            min_edge_thickness = self.target_vars.get('min_edge_thickness', tk.DoubleVar(value=0.5)).get()
            
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
            if self.target_vars['maintain_cemented'].get() and hasattr(self.current_lens, 'elements'):
                 for i in range(len(self.current_lens.elements) - 1):
                    # Check if air gap is effectively zero (cemented)
                    if i < len(self.current_lens.air_gaps):
                        gap = self.current_lens.air_gaps[i].thickness
                        if gap < 0.01: # Threshold for "cemented"
                            # Check if radii match (R2 of first == R1 of second)
                            r2_prev = self.current_lens.elements[i].lens.radius_of_curvature_2
                            r1_next = self.current_lens.elements[i+1].lens.radius_of_curvature_1
                            if abs(r2_prev - r1_next) < 0.1: # Tolerance
                                cemented_pairs.append((i, i+1))
                                self.log(f"Detected cemented interface between Element {i+1} and {i+2}")

            # Collect from UI selections
            # We need to map UI keys back to actual parameters
            # Keys are like "r1_0", "r2_0", "th_0", "gap_0"
            
            processed_keys = set()
            
            if hasattr(self.current_lens, 'elements'):
                num_elements = len(self.current_lens.elements)
                
                for i in range(num_elements):
                    # R1
                    if self.variable_vars.get(f"r1_{i}", tk.BooleanVar(value=False)).get():
                        # Check if this is the SECOND part of a cemented pair
                        is_cemented_secondary = any(pair[1] == i for pair in cemented_pairs)
                        if not is_cemented_secondary:
                            current_val = self.current_lens.elements[i].lens.radius_of_curvature_1
                            var = OptimizationVariable(
                                name=f"R1_Elem{i+1}",
                                element_index=i,
                                parameter="radius_of_curvature_1",
                                current_value=current_val,
                                min_value=-1000, max_value=1000
                            )
                            # Check if this is the FIRST part of a cemented pair -> LINK IT
                            for pair in cemented_pairs:
                                if pair[0] == i and pair[1] == i + 1: # Optimization logic bug? 
                                    # Wait, R1 of elem i is unrelated to interface i/i+1 (which involves R2 of i)
                                    pass
                            variables.append(var)
                        
                    # R2
                    if self.variable_vars.get(f"r2_{i}", tk.BooleanVar(value=False)).get():
                        current_val = self.current_lens.elements[i].lens.radius_of_curvature_2
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
                    if self.variable_vars.get(f"th_{i}", tk.BooleanVar(value=False)).get():
                        current_val = self.current_lens.elements[i].lens.thickness
                        var = OptimizationVariable(
                            name=f"Th_Elem{i+1}",
                            element_index=i,
                            parameter="thickness",
                            current_value=current_val,
                            min_value=min_thickness, max_value=max_thickness
                        )
                        variables.append(var)

                    # Air Gap
                    if i < num_elements - 1:
                        if self.variable_vars.get(f"gap_{i}", tk.BooleanVar(value=False)).get():
                            # Check if it's cemented -> if so, DON'T optimize gap usually? 
                            # Or allow it to break cement? For now, if cemented, maybe don't optimize gap?
                            is_cemented = any(pair[0] == i for pair in cemented_pairs)
                            if not is_cemented:
                                current_val = self.current_lens.air_gaps[i].thickness
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
                # We need OpticalSystem class. Try to import it.
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
                # We need to make a COPY of the lens to avoid modifying the original in place until success
                # But OpticalSystem.add_lens stores the object. 
                # LensOptimizer makes a deepcopy of system anyway.
                temp_system.add_lens(self.current_lens)
                
                # R1
                if self.variable_vars.get("radius_of_curvature_1_0", tk.BooleanVar(value=False)).get():
                    var = OptimizationVariable(
                        name="R1",
                        element_index=0,
                        parameter="radius_of_curvature_1",
                        current_value=self.current_lens.radius_of_curvature_1,
                        min_value=-1000, max_value=1000
                    )
                    variables.append(var)

                # R2
                if self.variable_vars.get("radius_of_curvature_2_0", tk.BooleanVar(value=False)).get():
                    var = OptimizationVariable(
                        name="R2",
                        element_index=0,
                        parameter="radius_of_curvature_2",
                        current_value=self.current_lens.radius_of_curvature_2,
                        min_value=-1000, max_value=1000
                    )
                    variables.append(var)

                # Thickness
                if self.variable_vars.get("thickness_0", tk.BooleanVar(value=False)).get():
                    var = OptimizationVariable(
                        name="Thickness",
                        element_index=0,
                        parameter="thickness",
                        current_value=self.current_lens.thickness,
                        min_value=min_thickness, max_value=max_thickness
                    )
                    variables.append(var)

                # Optimization requires a system, so we use temp_system
                # But when result comes back, we need to extract the lens
                is_single_lens_optimization = True

            if not variables:
                self.log("No variables selected!")
                self._optimization_finished(False)
                return

            # 2. Collect Targets
            targets: List[OptimizationTarget] = []
            
            if self.target_vars['focal_length_enabled'].get():
                target_val = self.target_vars['focal_length_value'].get()
                targets.append(OptimizationTarget("focal_length", target_val, weight=10.0))
            
            if self.target_vars['spot_size_enabled'].get():
                targets.append(OptimizationTarget("rms_spot_radius", 0.0, weight=100.0, target_type="minimize"))
                
            if self.target_vars['spherical_enabled'].get():
                targets.append(OptimizationTarget("spherical_aberration", 0.0, weight=5.0, target_type="minimize"))

            if self.target_vars['coma_enabled'].get():
                targets.append(OptimizationTarget("coma", 0.0, weight=5.0, target_type="minimize"))

            if self.target_vars['astigmatism_enabled'].get():
                targets.append(OptimizationTarget("astigmatism", 0.0, weight=5.0, target_type="minimize"))

            if not targets:
                self.log("No targets selected!")
                self._optimization_finished(False)
                return

            # Check robust mode
            robust_mode = self.target_vars['robust_mode'].get()
            
            # Create Optimizer
            system_to_optimize = temp_system if is_single_lens_optimization and temp_system else self.current_lens
            
            # Check selected algorithm
            algorithm = self.algorithm_var.get() if hasattr(self, 'algorithm_var') else "Local (Simplex)"
            
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
                        # Assume 1% tolerance or fixed value
                        # For R: 0.1% or 0.05mm? Let's say 0.1mm
                        # For Th: 0.1mm
                        val = 0.1
                        if tol_type == ToleranceType.REFRACTIVE_INDEX: val = 0.001
                        
                        tolerances.append(ToleranceOperand(
                            element_index=var.element_index,
                            param_type=tol_type,
                            min_val=-val, max_val=val
                        ))
                
                self.log(f"Generated {len(tolerances)} tolerances for robust optimization")
                
                # Robust only supports simplex currently via optimize_robust
                # So we override algorithm choice implicitly or explicitly
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
                    # result.optimized_system is an OpticalSystem. We need the Lens object inside.
                    # OptimizationResult is mutable, so we can replace the field at runtime.
                    # This allows _apply_results to receive the Lens object instead of OpticalSystem wrapper.
                    result.optimized_system = result.optimized_system.elements[0].lens
                
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
        """Apply results to the system and notify parent"""
        
        # Notify parent to refresh other tabs
        if self.on_lens_updated_callback:
            self.on_lens_updated_callback(self.current_lens)
            
        self.log("System updated.")
        self._optimization_finished(True)

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
            self.parent_window.root.after(0, lambda: self.optimize_btn.config(state='normal', text="Run Optimization"))

