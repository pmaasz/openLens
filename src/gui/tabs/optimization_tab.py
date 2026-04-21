"""
OpenLens PySide6 Optimization Tab
Tab for lens and system optimization
"""

import logging
import threading
import copy
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, 
                               QFormLayout, QCheckBox, QDoubleSpinBox, 
                               QComboBox, QTextEdit, QPushButton, QScrollArea, QLabel)
from PySide6.QtCore import Slot, Signal, Qt

try:
    from .base_tab import BaseTab
except ImportError:
    from src.gui.tabs.base_tab import BaseTab

try:
    from ..widgets.lens_viz_2d import _2DVisualizationWidget
    from ..widgets.assembly_viz import AssemblyVisualizationWidget
except ImportError:
    from src.gui.widgets.lens_viz_2d import _2DVisualizationWidget
    from src.gui.widgets.assembly_viz import AssemblyVisualizationWidget

from src.optimizer import LensOptimizer, OptimizationVariable, OptimizationTarget

logger = logging.getLogger(__name__)

class OptimizationTab(BaseTab):
    """Tab for lens and system optimization"""
    
    def _setup_ui(self):
        # Create scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none;")
        
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Variables Section - Now dynamic for Assemblies
        self._opt_vars_group = QGroupBox("Optimization Variables")
        self._opt_vars_container = QVBoxLayout(self._opt_vars_group)
        self._opt_vars_scroll = QScrollArea()
        self._opt_vars_scroll.setWidgetResizable(True)
        self._opt_vars_scroll.setMinimumHeight(150)
        self._opt_vars_widget = QWidget()
        self._opt_vars_layout = QVBoxLayout(self._opt_vars_widget)
        self._opt_vars_scroll.setWidget(self._opt_vars_widget)
        self._opt_vars_container.addWidget(self._opt_vars_scroll)
        
        # Targets Section
        targets_group = QGroupBox("Optimization Targets")
        targets_layout = QFormLayout(targets_group)
        
        self._opt_target_fl_enabled = QCheckBox("Target Focal Length (mm):")
        self._opt_target_fl_enabled.setChecked(True)
        self._opt_target_fl = QDoubleSpinBox()
        self._opt_target_fl.setRange(1, 10000)
        self._opt_target_fl.setValue(50)
        
        self._opt_target_fl_enabled.toggled.connect(self._opt_target_fl.setEnabled)
        targets_layout.addRow(self._opt_target_fl_enabled, self._opt_target_fl)
        
        self._opt_target_spot = QCheckBox("Minimize RMS Spot Size")
        self._opt_target_spot.setChecked(True)
        targets_layout.addRow("Spot Size:", self._opt_target_spot)
        
        self._opt_target_spherical = QCheckBox("Minimize Spherical Aberration")
        targets_layout.addRow("Spherical:", self._opt_target_spherical)
        
        self._opt_target_coma = QCheckBox("Minimize Coma")
        targets_layout.addRow("Coma:", self._opt_target_coma)
        
        self._opt_target_astig = QCheckBox("Minimize Astigmatism")
        targets_layout.addRow("Astigmatism:", self._opt_target_astig)
        
        # Layout organization
        top_row_layout = QHBoxLayout()
        top_row_layout.addWidget(self._opt_vars_group, 1)
        top_row_layout.addWidget(targets_group, 1)
        layout.addLayout(top_row_layout)
        
        # Constraints and Results side-by-side
        middle_row_layout = QHBoxLayout()
        
        # Constraints Section
        constraints_group = QGroupBox("Constraints & Options")
        constraints_layout = QFormLayout(constraints_group)
        
        self._opt_min_thickness = QDoubleSpinBox()
        self._opt_min_thickness.setRange(0.1, 50)
        self._opt_min_thickness.setValue(1.0)
        self._opt_min_thickness.setSuffix(" mm")
        constraints_layout.addRow("Min Thickness:", self._opt_min_thickness)
        
        self._opt_max_thickness = QDoubleSpinBox()
        self._opt_max_thickness.setRange(1, 500)
        self._opt_max_thickness.setValue(50)
        self._opt_max_thickness.setSuffix(" mm")
        constraints_layout.addRow("Max Thickness:", self._opt_max_thickness)
        
        self._opt_min_edge = QDoubleSpinBox()
        self._opt_min_edge.setRange(0.1, 20)
        self._opt_min_edge.setValue(0.5)
        self._opt_min_edge.setSuffix(" mm")
        constraints_layout.addRow("Min Edge Thickness:", self._opt_min_edge)
        
        self._opt_min_gap = QDoubleSpinBox()
        self._opt_min_gap.setRange(0, 100)
        self._opt_min_gap.setValue(0.1)
        self._opt_min_gap.setSuffix(" mm")
        constraints_layout.addRow("Min Air Gap:", self._opt_min_gap)
        
        self._opt_algorithm = QComboBox()
        self._opt_algorithm.addItems(["Local (Simplex)", "Global (Simulated Annealing)", "Global (Genetic Algorithm)"])
        self._opt_algorithm.setCurrentIndex(0)
        constraints_layout.addRow("Algorithm:", self._opt_algorithm)
        
        self._opt_robust = QCheckBox("Robust Mode (Yield Optimization)")
        constraints_layout.addRow("", self._opt_robust)
        
        # Results display
        results_group = QGroupBox("Optimization Results")
        results_layout = QVBoxLayout(results_group)
        
        self._opt_results_text = QTextEdit()
        self._opt_results_text.setReadOnly(True)
        self._opt_results_text.setMinimumHeight(150)
        self._opt_results_text.setStyleSheet("background-color: #2b2b2b; color: #e0e0e0; font-family: Courier; font-size: 10px;")
        results_layout.addWidget(self._opt_results_text)
        
        middle_row_layout.addWidget(constraints_group, 1)
        middle_row_layout.addWidget(results_group, 1)
        layout.addLayout(middle_row_layout)
        
        # Buttons
        btn_layout = QHBoxLayout()
        run_opt_btn = QPushButton("Run Optimization")
        run_opt_btn.clicked.connect(self._on_run_optimization)
        stop_btn = QPushButton("Stop")
        stop_btn.clicked.connect(self._on_stop_optimization)
        self._opt_apply_btn = QPushButton("Apply&Keep")
        self._opt_apply_btn.setEnabled(False)
        self._opt_apply_btn.clicked.connect(self._on_apply_optimization)
        reset_btn = QPushButton("Reset to Original")
        reset_btn.clicked.connect(self._on_reset_optimization)
        btn_layout.addWidget(run_opt_btn)
        btn_layout.addWidget(stop_btn)
        btn_layout.addWidget(self._opt_apply_btn)
        btn_layout.addWidget(reset_btn)
        layout.addLayout(btn_layout)
        
        # Visualization (Dual Support)
        self._opt_lens_viz = _2DVisualizationWidget()
        self._opt_asm_viz = AssemblyVisualizationWidget()
        self._opt_asm_viz.setVisible(False)
        layout.addWidget(self._opt_lens_viz)
        layout.addWidget(self._opt_asm_viz)
        
        layout.addStretch()
        
        scroll.setWidget(content)
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(scroll)
        
        self._opt_is_running = False
        self._opt_original_target = None
        self._opt_pending_target = None
        
        # Variables map for dynamic checkboxes
        self._opt_check_vars = {} # key -> QCheckBox

        # Connect signals from parent if needed
        if self._parent:
            self._parent.opt_finished.connect(self._on_optimization_finished)
            self._parent.opt_failed.connect(self._on_optimization_failed)

    def refresh(self):
        """Update the variables list based on current selection (Lens or Assembly)"""
        # Clear existing
        while self._opt_vars_layout.count():
            child = self._opt_vars_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self._opt_check_vars.clear()
        
        if not self._parent:
            return

        active_target = self._parent._current_assembly if self._parent._current_assembly else self._parent._current_lens
        if not active_target:
            self._opt_vars_layout.addWidget(QLabel("No system selected"))
            return

        from src.optical_system import OpticalSystem
        
        if isinstance(active_target, OpticalSystem):
            self._opt_lens_viz.setVisible(False)
            self._opt_asm_viz.setVisible(True)
            self._opt_asm_viz.update_system(active_target)
            
            for i, element in enumerate(active_target.elements):
                lens_name = element.lens.name or f"Lens {i+1}"
                group = QGroupBox(f"{i+1}. {lens_name}")
                vbox = QVBoxLayout(group)
                
                for label, param, key in [
                    ("Radius 1", "radius_of_curvature_1", f"r1_{i}"),
                    ("Radius 2", "radius_of_curvature_2", f"r2_{i}"),
                    ("Thickness", "thickness", f"th_{i}"),
                    ("Refractive Index", "refractive_index", f"n_{i}")
                ]:
                    val = getattr(element.lens, param)
                    cb = QCheckBox(f"{label} ({val:.2f})")
                    cb.setChecked(label in ["Radius 1", "Radius 2"])
                    self._opt_check_vars[key] = cb
                    vbox.addWidget(cb)
                
                # Air Gap
                if i < len(active_target.air_gaps):
                    gap_val = active_target.air_gaps[i].thickness
                    cb = QCheckBox(f"Air Gap to Next ({gap_val:.2f})")
                    self._opt_check_vars[f"gap_{i}"] = cb
                    vbox.addWidget(cb)
                    
                self._opt_vars_layout.addWidget(group)
        else:
            self._opt_lens_viz.setVisible(True)
            self._opt_asm_viz.setVisible(False)
            self._opt_lens_viz.update_lens(active_target)
            
            group = QGroupBox("Lens Properties")
            vbox = QVBoxLayout(group)
            for label, param, key in [
                ("Radius 1", "radius_of_curvature_1", "r1_0"),
                ("Radius 2", "radius_of_curvature_2", "r2_0"),
                ("Thickness", "thickness", "th_0"),
                ("Refractive Index", "refractive_index", "n_0"),
                ("Diameter", "diameter", "d_0")
            ]:
                val = getattr(active_target, param)
                cb = QCheckBox(f"{label} ({val:.2f})")
                cb.setChecked(label in ["Radius 1", "Radius 2", "Thickness"])
                self._opt_check_vars[key] = cb
                vbox.addWidget(cb)
            self._opt_vars_layout.addWidget(group)
            
        self._opt_vars_layout.addStretch()

    def _on_stop_optimization(self):
        """Stop the currently running optimization"""
        if self._opt_is_running:
            self._opt_is_running = False
            self._opt_results_text.setPlainText("Optimization stopped by user.")
            if self._parent:
                self._parent._update_status("Optimization stopped.")
            self._opt_apply_btn.setEnabled(False)

    def _on_run_optimization(self):
        """Run system optimization"""
        if not self._parent:
            return

        try:
            from src.global_optimizer import GlobalOptimizer
        except ImportError:
            from src.optimizer import LensOptimizer as GlobalOptimizer

        active_target = self._parent._current_assembly if self._parent._current_assembly else self._parent._current_lens
        if not active_target:
            self._opt_results_text.setPlainText("No system selected.")
            return
        
        if self._opt_is_running:
            self._opt_results_text.setPlainText("Optimization already running.")
            return
        
        self._opt_is_running = True
        self._opt_original_target = active_target
        self._opt_pending_target = None
        self._opt_apply_btn.setEnabled(False)
        
        # Collect variables from dynamic checkboxes
        variables = []
        from src.optical_system import OpticalSystem
        
        if isinstance(active_target, OpticalSystem):
            for i, element in enumerate(active_target.elements):
                if self._opt_check_vars.get(f"r1_{i}").isChecked():
                    variables.append(OptimizationVariable(f"R1_L{i+1}", i, "radius_of_curvature_1", element.lens.radius_of_curvature_1, -10000, 10000))
                if self._opt_check_vars.get(f"r2_{i}").isChecked():
                    variables.append(OptimizationVariable(f"R2_L{i+1}", i, "radius_of_curvature_2", element.lens.radius_of_curvature_2, -10000, 10000))
                if self._opt_check_vars.get(f"th_{i}").isChecked():
                    variables.append(OptimizationVariable(f"Th_L{i+1}", i, "thickness", element.lens.thickness, self._opt_min_thickness.value(), self._opt_max_thickness.value()))
                if self._opt_check_vars.get(f"n_{i}").isChecked():
                    variables.append(OptimizationVariable(f"N_L{i+1}", i, "refractive_index", element.lens.refractive_index, 1.3, 2.4))
                if self._opt_check_vars.get(f"gap_{i}") and self._opt_check_vars.get(f"gap_{i}").isChecked():
                    variables.append(OptimizationVariable(f"Gap_{i+1}_{i+2}", i, "air_gap", active_target.air_gaps[i].thickness, self._opt_min_gap.value(), 500))
        else:
            if self._opt_check_vars.get("r1_0").isChecked():
                variables.append(OptimizationVariable("Radius 1", 0, "radius_of_curvature_1", active_target.radius_of_curvature_1, -10000, 10000))
            if self._opt_check_vars.get("r2_0").isChecked():
                variables.append(OptimizationVariable("Radius 2", 0, "radius_of_curvature_2", active_target.radius_of_curvature_2, -10000, 10000))
            if self._opt_check_vars.get("th_0").isChecked():
                variables.append(OptimizationVariable("Thickness", 0, "thickness", active_target.thickness, self._opt_min_thickness.value(), self._opt_max_thickness.value()))
            if self._opt_check_vars.get("n_0").isChecked():
                variables.append(OptimizationVariable("Index", 0, "refractive_index", active_target.refractive_index, 1.3, 2.4))
            if self._opt_check_vars.get("d_0") and self._opt_check_vars.get("d_0").isChecked():
                variables.append(OptimizationVariable("Diameter", 0, "diameter", active_target.diameter, 1, 500))
        
        if not variables:
            self._opt_results_text.setPlainText("Select at least one variable.")
            self._opt_is_running = False
            return
        
        # Collect targets
        targets = []
        if self._opt_target_fl_enabled.isChecked():
            targets.append(OptimizationTarget('focal_length', self._opt_target_fl.value(), weight=1.0, target_type="target"))
        if self._opt_target_spot.isChecked():
            targets.append(OptimizationTarget('spot_size', 0, weight=1.0, target_type="minimize"))
        if self._opt_target_spherical.isChecked():
            targets.append(OptimizationTarget('spherical', 0, weight=1.0, target_type="minimize"))
        if self._opt_target_coma.isChecked():
            targets.append(OptimizationTarget('coma', 0, weight=1.0, target_type="minimize"))
        if self._opt_target_astig.isChecked():
            targets.append(OptimizationTarget('astigmatism', 0, weight=1.0, target_type="minimize"))
        
        if not targets:
            self._opt_results_text.setPlainText("Select at least one target.")
            self._opt_is_running = False
            return
        
        # Build constraints
        constraints = {}
        constraints['min_center_thickness'] = self._opt_min_thickness.value()
        constraints['max_center_thickness'] = self._opt_max_thickness.value()
        constraints['min_edge_thickness'] = self._opt_min_edge.value()
        constraints['min_air_gap'] = self._opt_min_gap.value()
        
        self._opt_results_text.setPlainText("Optimizing...")
        
        def run_optimization_thread():
            try:
                from src.optical_system import OpticalSystem
                
                # Setup system
                if isinstance(active_target, OpticalSystem):
                    system = copy.deepcopy(active_target)
                else:
                    system = OpticalSystem(name="Optimization")
                    system.add_lens(copy.deepcopy(active_target))
                
                optimizer = GlobalOptimizer(system, variables, targets, constraints=constraints)
                
                # Run optimization based on algorithm selection
                algorithm = self._opt_algorithm.currentText()
                if "Simplex" in algorithm:
                    result = optimizer.optimize(max_iterations=100)
                elif "Simulated" in algorithm:
                    result = optimizer.optimize_simulated_annealing(max_iterations=500)
                elif "Genetic" in algorithm:
                    result = optimizer.optimize_genetic(population_size=30, generations=30)
                else:
                    result = optimizer.optimize(max_iterations=100)
                
                # Emit signals through parent
                self._parent.opt_finished.emit(result, variables)
                                       
            except Exception as e:
                import traceback
                error_details = traceback.format_exc()
                logger.error(f"Optimization error:\n{error_details}")
                self._parent.opt_failed.emit(str(e))

        thread = threading.Thread(target=run_optimization_thread, daemon=True)
        thread.start()

    @Slot(object, list)
    def _on_optimization_finished(self, result, variables):
        """Callback for finished optimization"""
        self._opt_is_running = False
        from src.optical_system import OpticalSystem
        
        if result.success:
            text = f"Optimization Successful!\n\n"
            text += f"Final Merit Function: {result.final_merit:.4f}\n"
            text += f"Iterations: {result.iterations}\n\n"
            text += "Optimized Values (Preview):\n"
            
            # Show parameter changes
            if result.optimized_system:
                self._opt_pending_target = result.optimized_system
                self._opt_apply_btn.setEnabled(True)
                
                if isinstance(result.optimized_system, OpticalSystem):
                    self._opt_asm_viz.update_system(result.optimized_system)
                    for var in variables:
                        if var.parameter == "air_gap":
                            val = result.optimized_system.air_gaps[var.element_index].thickness
                        else:
                            val = getattr(result.optimized_system.elements[var.element_index].lens, var.parameter)
                        text += f"  {var.name}: {val:.4f}\n"
                else:
                    lens = result.optimized_system.elements[0].lens if hasattr(result.optimized_system, 'elements') else result.optimized_system
                    self._opt_lens_viz.update_lens(lens)
                    for var in variables:
                        val = getattr(lens, var.parameter)
                        text += f"  {var.name}: {val:.4f}\n"
            
            self._opt_results_text.setPlainText(text)
            self._opt_results_text.append("\nClick 'Apply & Keep' to save these changes.")
        else:
            self._opt_results_text.setPlainText(f"Optimization failed: {result.message}")

    @Slot(str)
    def _on_optimization_failed(self, message):
        """Callback for failed optimization"""
        self._opt_is_running = False
        self._opt_results_text.setPlainText(f"Optimization Error: {message}")
        if self._parent:
            self._parent._update_status(f"Optimization failed: {message}")

    def _on_apply_optimization(self):
        """Apply the optimization results to the current system"""
        if not self._parent or not self._opt_pending_target:
            return

        from src.optical_system import OpticalSystem
        if isinstance(self._opt_pending_target, OpticalSystem):
            self._parent._current_assembly = self._opt_pending_target
            self._parent._optical_system = self._opt_pending_target
            self._parent._assembly_tab_widget._assembly_viz.update_system(self._opt_pending_target)
        else:
            self._parent._current_lens = self._opt_pending_target
            self._parent._lens_editor.load_lens(self._opt_pending_target)
        
        self._parent._update_all_tabs()
        self._opt_apply_btn.setEnabled(False)
        self._opt_pending_target = None
        self._opt_results_text.append("\nChanges applied to system.")
        self._parent._save_to_database()

    def _on_reset_optimization(self):
        """Reset optimization to original values"""
        if not self._parent or not self._opt_original_target:
            self._opt_results_text.setPlainText("No original state to reset to.")
            return

        from src.optical_system import OpticalSystem
        if isinstance(self._opt_original_target, OpticalSystem):
            self._parent._current_assembly = self._opt_original_target
            self._parent._optical_system = self._opt_original_target
            self._opt_asm_viz.update_system(self._parent._current_assembly)
        else:
            self._parent._current_lens = self._opt_original_target
            self._opt_lens_viz.update_lens(self._parent._current_lens)
        
        self._parent._update_all_tabs()
        self._opt_results_text.setPlainText("Reset to original values.")
        self._opt_apply_btn.setEnabled(False)
        self._opt_pending_target = None
