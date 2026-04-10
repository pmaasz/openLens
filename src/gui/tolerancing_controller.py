"""
Controller for Optical System Tolerancing and Yield Analysis.

Manages the UI and logic for:
- Defining tolerance operands (Radius, Thickness, Decenter, etc.)
- Running Monte Carlo simulations to estimate manufacturing yield
- Performing Inverse Sensitivity analysis to suggest tolerances
"""

import tkinter as tk
from tkinter import ttk
import logging
import threading
from typing import List, Dict, Any, Optional, Tuple, TYPE_CHECKING
import copy

if TYPE_CHECKING:
    from ..lens import Lens
    from ..optical_system import OpticalSystem
    from ..gui.main_window import LensEditorWindow

try:
    from ..tolerancing import (
        MonteCarloAnalyzer, InverseSensitivityAnalyzer, ToleranceOperand, ToleranceType, generate_yield_report
    )
except ImportError:
    try:
        from tolerancing import (
            MonteCarloAnalyzer, InverseSensitivityAnalyzer, ToleranceOperand, ToleranceType, generate_yield_report
        )
    except ImportError:
        # Fallback for dev environment
        import sys
        import os
        sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))
        from src.tolerancing import (
            MonteCarloAnalyzer, InverseSensitivityAnalyzer, ToleranceOperand, ToleranceType, generate_yield_report
        )

logger = logging.getLogger(__name__)

class TolerancingController:
    """
    Controller for the tolerancing tab.
    """

    def __init__(self, colors: Dict[str, str]):
        self.colors = colors
        self.parent_window: Optional['LensEditorWindow'] = None
        self.current_lens: Optional['OpticalSystem'] = None
        
        # UI Components
        self.operands_tree = None
        self.results_text = None
        self.progress_bar = None
        
        # State
        self.operands: List[ToleranceOperand] = []
        self.is_running = False

    def setup_ui(self, parent_frame: ttk.Frame):
        """Set up the tolerancing tab UI"""
        
        # Main layout: Left (Operands) and Right (Results)
        paned = ttk.PanedWindow(parent_frame, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # --- Left Panel: Operands ---
        left_panel = ttk.Frame(paned, padding="5")
        paned.add(left_panel, weight=1)
        
        ttk.Label(left_panel, text="Tolerance Operands", font=('Arial', 12, 'bold')).pack(anchor=tk.W, pady=(0, 10))
        
        # Toolbar for operands
        toolbar = ttk.Frame(left_panel)
        toolbar.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Button(toolbar, text="Add Tolerance", command=self._add_operand_dialog, width=15).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Remove", command=self._remove_operand, width=10).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Clear All", command=self._clear_operands, width=10).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Default Set", command=self._add_default_operands, width=12).pack(side=tk.LEFT, padx=2)
        
        # Treeview for operands
        columns = ("Element", "Type", "Min", "Max", "Distribution")
        self.operands_tree = ttk.Treeview(left_panel, columns=columns, show="headings", height=15)
        
        self.operands_tree.heading("Element", text="Element #")
        self.operands_tree.heading("Type", text="Type")
        self.operands_tree.heading("Min", text="Min (mm/nd)")
        self.operands_tree.heading("Max", text="Max (mm/nd)")
        self.operands_tree.heading("Distribution", text="Distribution")
        
        self.operands_tree.column("Element", width=70, anchor=tk.CENTER)
        self.operands_tree.column("Type", width=120)
        self.operands_tree.column("Min", width=80, anchor=tk.E)
        self.operands_tree.column("Max", width=80, anchor=tk.E)
        self.operands_tree.column("Distribution", width=100)
        
        tree_scroll = ttk.Scrollbar(left_panel, orient="vertical", command=self.operands_tree.yview)
        self.operands_tree.configure(yscrollcommand=tree_scroll.set)
        
        self.operands_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # --- Right Panel: Analysis ---
        right_panel = ttk.Frame(paned, padding="5")
        paned.add(right_panel, weight=1)
        
        ttk.Label(right_panel, text="Analysis & Yield", font=('Arial', 12, 'bold')).pack(anchor=tk.W, pady=(0, 10))
        
        # Settings
        settings_frame = ttk.LabelFrame(right_panel, text="Monte Carlo Settings", padding="10")
        settings_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(settings_frame, text="Number of Trials:").grid(row=0, column=0, sticky=tk.W)
        self.num_trials_var = tk.IntVar(value=100)
        ttk.Entry(settings_frame, textvariable=self.num_trials_var, width=10).grid(row=0, column=1, padx=5, sticky=tk.W)
        
        ttk.Label(settings_frame, text="Criterion Limit (RMS mm):").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.limit_var = tk.DoubleVar(value=0.05)
        ttk.Entry(settings_frame, textvariable=self.limit_var, width=10).grid(row=1, column=1, padx=5, sticky=tk.W)
        
        # Action Buttons
        actions_frame = ttk.Frame(right_panel)
        actions_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.run_mc_btn = ttk.Button(actions_frame, text="Run Monte Carlo", command=self.run_monte_carlo)
        self.run_mc_btn.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)
        
        self.run_inv_btn = ttk.Button(actions_frame, text="Inverse Sensitivity", command=self.run_inverse_sensitivity)
        self.run_inv_btn.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)
        
        # Progress
        self.progress_bar = ttk.Progressbar(right_panel, mode='determinate')
        self.progress_bar.pack(fill=tk.X, pady=(0, 10))
        
        # Results Output
        results_tab_control = ttk.Notebook(right_panel)
        results_tab_control.pack(fill=tk.BOTH, expand=True)
        
        # Text Report Tab
        report_tab = ttk.Frame(results_tab_control)
        results_tab_control.add(report_tab, text="Report")
        
        self.results_text = tk.Text(report_tab, height=15, width=40, state='disabled', font=('Consolas', 10))
        self.results_text.pack(fill=tk.BOTH, expand=True)
        
        results_scroll = ttk.Scrollbar(self.results_text, orient="vertical", command=self.results_text.yview)
        self.results_text.configure(yscrollcommand=results_scroll.set)
        results_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Graph Tab
        graph_tab = ttk.Frame(results_tab_control)
        results_tab_control.add(graph_tab, text="Yield Histogram")
        
        self.graph_canvas = tk.Canvas(graph_tab, bg="white", height=200)
        self.graph_canvas.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.yield_data: List[float] = []  # List of trial values
        self.yield_limit: float = 0.05

    def load_lens(self, lens: Optional[Any]):
        """Load lens data into the tolerancing tab"""
        self.current_lens = lens
        if not lens:
            self._log("No system selected.")
            return
        
        # Refresh or clear operands if needed? 
        # Usually we keep operands unless system architecture changes significantly.
        # For now, just log.
        self._log(f"Loaded system '{lens.name}' for tolerancing analysis.")

    def _add_operand_dialog(self):
        """Show dialog to add a new tolerance operand"""
        if not self.current_lens:
            return
            
        dialog = tk.Toplevel(self.parent_window.root)
        dialog.title("Add Tolerance Operand")
        dialog.geometry("350x300")
        dialog.transient(self.parent_window.root)
        dialog.grab_set()
        
        # Element selection
        ttk.Label(dialog, text="Element Index:").grid(row=0, column=0, padx=10, pady=10, sticky=tk.W)
        # Determine number of elements
        num_elements = 1
        if hasattr(self.current_lens, 'elements'):
            num_elements = len(self.current_lens.elements)
            
        elem_var = tk.IntVar(value=0)
        elem_combo = ttk.Combobox(dialog, textvariable=elem_var, values=list(range(num_elements)), width=5)
        elem_combo.grid(row=0, column=1, padx=10, pady=10, sticky=tk.W)
        
        # Type selection
        ttk.Label(dialog, text="Parameter Type:").grid(row=1, column=0, padx=10, pady=5, sticky=tk.W)
        type_var = tk.StringVar(value=ToleranceType.RADIUS_1.value)
        type_combo = ttk.Combobox(dialog, textvariable=type_var, values=[t.value for t in ToleranceType], width=20, state="readonly")
        type_combo.grid(row=1, column=1, padx=10, pady=5, sticky=tk.W)
        
        # Min/Max
        ttk.Label(dialog, text="Min Deviation:").grid(row=2, column=0, padx=10, pady=5, sticky=tk.W)
        min_var = tk.DoubleVar(value=-0.1)
        ttk.Entry(dialog, textvariable=min_var, width=10).grid(row=2, column=1, padx=10, pady=5, sticky=tk.W)
        
        ttk.Label(dialog, text="Max Deviation:").grid(row=3, column=0, padx=10, pady=5, sticky=tk.W)
        max_var = tk.DoubleVar(value=0.1)
        ttk.Entry(dialog, textvariable=max_var, width=10).grid(row=3, column=1, padx=10, pady=5, sticky=tk.W)
        
        # Distribution
        ttk.Label(dialog, text="Distribution:").grid(row=4, column=0, padx=10, pady=5, sticky=tk.W)
        dist_var = tk.StringVar(value="uniform")
        dist_combo = ttk.Combobox(dialog, textvariable=dist_var, values=["uniform", "gaussian"], width=10, state="readonly")
        dist_combo.grid(row=4, column=1, padx=10, pady=5, sticky=tk.W)
        
        def on_ok():
            # Find enum member by value
            p_type = None
            for member in ToleranceType:
                if member.value == type_var.get():
                    p_type = member
                    break
            
            op = ToleranceOperand(
                element_index=elem_var.get(),
                param_type=p_type,
                min_val=min_var.get(),
                max_val=max_var.get(),
                distribution=dist_var.get()
            )
            self.operands.append(op)
            self._refresh_operands_tree()
            dialog.destroy()
            
        ttk.Button(dialog, text="Add", command=on_ok).grid(row=5, column=0, columnspan=2, pady=20)

    def _remove_operand(self):
        selected = self.operands_tree.selection()
        if not selected:
            return
        
        # Indices in tree match self.operands? Yes if we always refresh.
        # Get index from the tree item id if we used sequence
        for item in selected:
            idx = int(self.operands_tree.index(item))
            if 0 <= idx < len(self.operands):
                self.operands.pop(idx)
        
        self._refresh_operands_tree()

    def _clear_operands(self):
        self.operands.clear()
        self._refresh_operands_tree()

    def _add_default_operands(self):
        """Add a standard set of tolerances for the current system"""
        if not self.current_lens:
            return
            
        num_elements = 1
        if hasattr(self.current_lens, 'elements'):
            num_elements = len(self.current_lens.elements)
            
        for i in range(num_elements):
            # Radius 1 & 2: +/- 0.1 mm
            self.operands.append(ToleranceOperand(i, ToleranceType.RADIUS_1, -0.1, 0.1))
            self.operands.append(ToleranceOperand(i, ToleranceType.RADIUS_2, -0.1, 0.1))
            # Thickness: +/- 0.05 mm
            self.operands.append(ToleranceOperand(i, ToleranceType.THICKNESS, -0.05, 0.05))
            # Decenter: +/- 0.05 mm
            self.operands.append(ToleranceOperand(i, ToleranceType.DECENTER_Y, -0.05, 0.05))
            # Tilt: +/- 0.1 deg
            self.operands.append(ToleranceOperand(i, ToleranceType.TILT_X, -0.1, 0.1))
            
        self._refresh_operands_tree()

    def _refresh_operands_tree(self):
        # Clear
        for item in self.operands_tree.get_children():
            self.operands_tree.delete(item)
            
        # Add
        for op in self.operands:
            self.operands_tree.insert("", tk.END, values=(
                op.element_index,
                op.param_type.value,
                f"{op.min_val:+.4f}",
                f"{op.max_val:+.4f}",
                op.distribution
            ))

        # Bind events for editing
        self.operands_tree.bind("<Double-1>", self._on_tree_double_click)

    def _on_tree_double_click(self, event):
        """Handle double-click for editing a value in the treeview"""
        region = self.operands_tree.identify_region(event.x, event.y)
        if region != "cell":
            return
            
        column = self.operands_tree.identify_column(event.x)
        item_id = self.operands_tree.identify_row(event.y)
        if not item_id or column not in ("#3", "#4"): # Only Min/Max
            return
            
        # Get coordinates of the cell
        x, y, w, h = self.operands_tree.bbox(item_id, column)
        
        # Create an entry widget on top
        entry_var = tk.StringVar()
        entry = ttk.Entry(self.operands_tree, textvariable=entry_var)
        
        # Get current value
        current_val = self.operands_tree.item(item_id, 'values')[int(column[1:])-1]
        entry_var.set(current_val.replace("+", ""))
        
        entry.place(x=x, y=y, width=w, height=h)
        entry.focus_set()
        entry.select_range(0, tk.END)
        
        def save_edit(event=None):
            try:
                new_val = float(entry_var.get())
                idx = int(self.operands_tree.index(item_id))
                if column == "#3": # Min
                    self.operands[idx].min_val = new_val
                else: # Max
                    self.operands[idx].max_val = new_val
                
                self._refresh_operands_tree()
            except ValueError:
                pass
            entry.destroy()
            
        def cancel_edit(event=None):
            entry.destroy()
            
        entry.bind("<Return>", save_edit)
        entry.bind("<FocusOut>", save_edit)
        entry.bind("<Escape>", cancel_edit)

    def run_monte_carlo(self):
        if self.is_running or not self.current_lens:
            return
            
        if not self.operands:
            self._log("Error: No tolerance operands defined.")
            return
            
        self.is_running = True
        self.run_mc_btn.config(state='disabled')
        self.results_text.config(state='normal')
        self.results_text.delete(1.0, tk.END)
        self.results_text.config(state='disabled')
        
        num_trials = self.num_trials_var.get()
        limit = self.limit_var.get()
        
        self._log(f"Starting Monte Carlo analysis with {num_trials} trials...")
        self.progress_bar['value'] = 0
        self.progress_bar['maximum'] = num_trials
        
        # Run in thread
        self.yield_data = []
        self.yield_limit = limit
        self.graph_canvas.delete("all")
        
        threading.Thread(target=self._mc_worker, args=(num_trials, limit), daemon=True).start()

    def _mc_worker(self, num_trials, limit):
        try:
            # We need to deepcopy the system because MC modifies it
            # But the analyzer handles it in its run() method.
            # However, for safety in multi-threading, we copy once here.
            sys_copy = copy.deepcopy(self.current_lens)
            
            analyzer = MonteCarloAnalyzer(sys_copy, self.operands)
            
            # Since MonteCarloAnalyzer.run() is synchronous, we'd ideally want 
            # to modify it to support callbacks for progress.
            # For now, let's run it and update progress at the end or split it.
            
            stats = analyzer.run(num_trials=num_trials, criterion_limit=limit)
            
            # Store data for histogram
            self.yield_data = [r['value'] for r in analyzer.results]
            
            report = generate_yield_report(stats)
            
            if self.parent_window:
                self.parent_window.root.after(0, lambda: self._analysis_finished(report))
                self.parent_window.root.after(0, self._update_histogram)
                
        except Exception as e:
            logger.error(f"MC Analysis failed: {e}", exc_info=True)
            self._log(f"Error: {e}")
            if self.parent_window:
                self.parent_window.root.after(0, lambda: self._analysis_finished(None))

    def _update_histogram(self):
        """Redraw the yield histogram with current data"""
        if not self.yield_data:
            return
            
        w = self.graph_canvas.winfo_width()
        h = self.graph_canvas.winfo_height()
        if w <= 1: w = 400
        if h <= 1: h = 250
        
        self.graph_canvas.delete("all")
        
        pad_x = 40
        pad_y = 30
        plot_w = w - 2*pad_x
        plot_h = h - 2*pad_y
        
        # Draw axes
        self.graph_canvas.create_line(pad_x, h-pad_y, w-pad_x, h-pad_y, width=2) # X
        self.graph_canvas.create_line(pad_x, h-pad_y, pad_x, pad_y, width=2) # Y
        
        # Bin data
        num_bins = 20
        min_v = min(self.yield_data)
        max_v = max(self.yield_data)
        
        # Ensure we show the limit even if max_v is smaller
        max_v = max(max_v, self.yield_limit * 1.2)
        
        if max_v == min_v: max_v += 0.01
        
        bin_size = (max_v - min_v) / num_bins
        bins = [0] * num_bins
        for val in self.yield_data:
            idx = int((val - min_v) / bin_size)
            if idx >= num_bins: idx = num_bins - 1
            bins[idx] += 1
            
        max_count = max(bins) if bins else 1
        
        # Draw bars
        bar_w = plot_w / num_bins
        for i, count in enumerate(bins):
            bar_h = (count / max_count) * plot_h
            x0 = pad_x + i * bar_w
            y0 = h - pad_y - bar_h
            x1 = x0 + bar_w - 2
            y1 = h - pad_y
            
            # Color based on pass/fail (approximate bin center)
            bin_center = min_v + (i + 0.5) * bin_size
            color = "#4CAF50" if bin_center <= self.yield_limit else "#F44336"
            
            self.graph_canvas.create_rectangle(x0, y0, x1, y1, fill=color, outline="#333")
            
        # Draw limit line
        limit_x = pad_x + ((self.yield_limit - min_v) / (max_v - min_v)) * plot_w
        if pad_x <= limit_x <= w - pad_x:
            self.graph_canvas.create_line(limit_x, h-pad_y, limit_x, pad_y, fill="red", dash=(4, 4), width=2)
            self.graph_canvas.create_text(limit_x, pad_y-5, text=f"Limit: {self.yield_limit:.3f}", fill="red", anchor="s")
            
        # Labels
        self.graph_canvas.create_text(pad_x, h-pad_y+15, text=f"{min_v:.3f}", anchor="n")
        self.graph_canvas.create_text(w-pad_x, h-pad_y+15, text=f"{max_v:.3f}", anchor="n")
        self.graph_canvas.create_text(w/2, h-5, text="RMS Spot Radius (mm)", anchor="s")
        self.graph_canvas.create_text(5, h/2, text="Frequency", angle=90, anchor="n")
        self.graph_canvas.create_text(pad_x-5, pad_y, text=f"{max_count}", anchor="e")

    def run_inverse_sensitivity(self):
        if self.is_running or not self.current_lens:
            return
            
        if not self.operands:
            self._log("Error: No tolerance operands defined.")
            return
            
        self.is_running = True
        self.run_inv_btn.config(state='disabled')
        
        self._log("Starting Inverse Sensitivity analysis...")
        
        threading.Thread(target=self._inv_worker, daemon=True).start()

    def _inv_worker(self):
        try:
            sys_copy = copy.deepcopy(self.current_lens)
            analyzer = InverseSensitivityAnalyzer(sys_copy, self.operands)
            
            sensitivities = analyzer.calculate_sensitivities()
            
            # Generate report
            lines = ["=== Inverse Sensitivity Report ===", ""]
            lines.append(f"{'Elem':<5} {'Type':<18} {'Sens':<12} {'Change':<12}")
            lines.append("-" * 55)
            
            for s in sensitivities:
                lines.append(f"{s['element']:<5} {s['type']:<18} {s['sensitivity']:<12.4f} {s['change']:<12.6f}")
            
            lines.append("")
            lines.append("Suggested Limits (RSS budget 0.05):")
            lines.append(f"{'Elem':<5} {'Type':<18} {'Limit (+/-)':<12}")
            lines.append("-" * 35)
            new_tols = analyzer.optimize_limits(target_yield_criterion=0.05)
            for nt in new_tols:
                lines.append(f" {nt.element_index:<4} {nt.param_type.name:<18} {nt.max_val:<12.4f}")
                
            report = "\n".join(lines)
            
            if self.parent_window:
                self.parent_window.root.after(0, lambda: self._analysis_finished(report))
                
        except Exception as e:
            logger.error(f"Inverse Sensitivity failed: {e}", exc_info=True)
            self._log(f"Error: {e}")
            if self.parent_window:
                self.parent_window.root.after(0, lambda: self._analysis_finished(None))

    def _analysis_finished(self, report: Optional[str]):
        self.is_running = False
        self.run_mc_btn.config(state='normal')
        self.run_inv_btn.config(state='normal')
        self.progress_bar['value'] = self.progress_bar['maximum']
        
        if report:
            self.results_text.config(state='normal')
            self.results_text.insert(tk.END, report)
            self.results_text.see(tk.END)
            self.results_text.config(state='disabled')
            self._log("Analysis complete.")
        else:
            self._log("Analysis failed.")

    def _log(self, message: str):
        """Append message to results report or status"""
        if threading.current_thread() is not threading.main_thread():
            if self.parent_window:
                self.parent_window.root.after(0, lambda: self._log(message))
            return

        if not self.results_text:
            return
            
        self.results_text.config(state='normal')
        self.results_text.insert(tk.END, message + "\n")
        self.results_text.see(tk.END)
        self.results_text.config(state='disabled')
