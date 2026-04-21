"""
OpenLens PySide6 Tolerancing Tab
Tab for tolerancing and yield analysis
"""

import logging
import threading
import copy
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, 
                               QFormLayout, QCheckBox, QDoubleSpinBox, QSpinBox,
                               QComboBox, QTextEdit, QPushButton, QScrollArea, 
                               QLabel, QTableWidget, QTableWidgetItem, QHeaderView,
                               QProgressBar, QMessageBox, QDialog)
from PySide6.QtCore import Slot, Signal, Qt, QMetaObject, Q_ARG

try:
    from .base_tab import BaseTab
except ImportError:
    from src.gui.tabs.base_tab import BaseTab

try:
    from ..dialogs.analysis_plots import AnalysisPlotDialog
except ImportError:
    from src.gui.dialogs.analysis_plots import AnalysisPlotDialog

from src.tolerancing import MonteCarloAnalyzer, InverseSensitivityAnalyzer, ToleranceOperand, ToleranceType

logger = logging.getLogger(__name__)

class TolerancingTab(BaseTab):
    """Tab for tolerancing and yield analysis"""
    
    def _setup_ui(self):
        # Create scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none;")
        
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(10, 10, 10, 10)
        
        title = QLabel("Tolerancing Analysis")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)
        
        # Main split: Left (Operands) and Right (Analysis)
        split_layout = QHBoxLayout()
        
        # Left Panel: Tolerance Operands
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        left_layout.addWidget(QLabel("Tolerance Operands"))
        
        # Toolbar
        toolbar = QWidget()
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        
        add_btn = QPushButton("Add Tolerance")
        add_btn.clicked.connect(self._on_add_tolerance)
        remove_btn = QPushButton("Remove")
        remove_btn.clicked.connect(self._on_remove_tolerance)
        clear_btn = QPushButton("Clear All")
        clear_btn.clicked.connect(self._on_clear_tolerances)
        default_btn = QPushButton("Default Set")
        default_btn.clicked.connect(self._on_add_default_tolerances)
        
        toolbar_layout.addWidget(add_btn)
        toolbar_layout.addWidget(remove_btn)
        toolbar_layout.addWidget(clear_btn)
        toolbar_layout.addWidget(default_btn)
        left_layout.addWidget(toolbar)
        
        # Operands table
        self._tol_table = QTableWidget()
        self._tol_table.setColumnCount(5)
        self._tol_table.setHorizontalHeaderLabels(["Element #", "Type", "Min", "Max", "Distribution"])
        self._tol_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._tol_table.setEditTriggers(QTableWidget.DoubleClicked)
        self._tol_table.itemChanged.connect(self._on_tol_item_changed)
        self._tol_table.setStyleSheet("background-color: #2b2b2b; color: #e0e0e0; font-family: Courier; font-size: 10px;")
        left_layout.addWidget(QLabel("Operands (Double-click to edit Min/Max):"))
        left_layout.addWidget(self._tol_table)
        
        # Right Panel: Analysis
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        right_layout.addWidget(QLabel("Analysis & Yield"))
        
        # Monte Carlo Settings
        mc_group = QGroupBox("Monte Carlo Settings")
        mc_layout = QFormLayout(mc_group)
        
        self._tol_num_trials = QSpinBox()
        self._tol_num_trials.setRange(10, 10000)
        self._tol_num_trials.setValue(100)
        mc_layout.addRow("Number of Trials:", self._tol_num_trials)
        
        self._tol_criterion = QDoubleSpinBox()
        self._tol_criterion.setRange(0.001, 1)
        self._tol_criterion.setValue(0.05)
        self._tol_criterion.setSuffix(" mm")
        mc_layout.addRow("Criterion Limit (RMS):", self._tol_criterion)
        
        right_layout.addWidget(mc_group)
        
        # Action Buttons
        btn_layout = QHBoxLayout()
        run_mc_btn = QPushButton("Run Monte Carlo")
        run_mc_btn.clicked.connect(self._on_run_monte_carlo)
        run_inv_btn = QPushButton("Inverse Sensitivity")
        run_inv_btn.clicked.connect(self._on_run_inverse_sensitivity)
        
        btn_layout.addWidget(run_mc_btn)
        btn_layout.addWidget(run_inv_btn)
        right_layout.addLayout(btn_layout)
        
        # Progress Bar
        self._tol_progress = QProgressBar()
        self._tol_progress.setRange(0, 100)
        self._tol_progress.setValue(0)
        self._tol_progress.setVisible(False)
        right_layout.addWidget(self._tol_progress)
        
        # Results
        results_group = QGroupBox("Results")
        results_layout = QVBoxLayout(results_group)
        
        self._tol_results_text = QTextEdit()
        self._tol_results_text.setReadOnly(True)
        self._tol_results_text.setMinimumHeight(200)
        self._tol_results_text.setStyleSheet("background-color: #2b2b2b; color: #e0e0e0; font-family: Courier; font-size: 10px;")
        self._tol_results_text.setPlainText("Configure tolerances and click 'Run Monte Carlo' or 'Inverse Sensitivity' to analyze.")
        results_layout.addWidget(self._tol_results_text)
        
        right_layout.addWidget(results_group)
        
        # Add panels to split
        split_layout.addWidget(left_panel, 1)
        split_layout.addWidget(right_panel, 1)
        
        layout.addLayout(split_layout)
        
        layout.addStretch()
        
        scroll.setWidget(content)
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(scroll)

    def refresh(self):
        """Update display when parent changes"""
        if self._parent and hasattr(self._parent, '_tol_operands'):
            self._update_tolerance_operands_display()

    def _on_add_tolerance(self):
        """Add a new tolerance operand"""
        if not self._parent or not self._parent._current_lens:
            return
            
        dialog = QDialog(self)
        dialog.setWindowTitle("Add Tolerance Operand")
        layout = QVBoxLayout(dialog)
        form = QFormLayout()
        
        # Element selection
        num_elements = 1
        if hasattr(self._parent._current_lens, 'elements'):
            num_elements = len(self._parent._current_lens.elements)
        
        elem_combo = QComboBox()
        elem_combo.addItems([str(i) for i in range(num_elements)])
        form.addRow("Element Index:", elem_combo)
        
        type_combo = QComboBox()
        type_combo.addItems([t.value for t in ToleranceType])
        form.addRow("Parameter Type:", type_combo)
        
        min_spin = QDoubleSpinBox()
        min_spin.setRange(-10, 10)
        min_spin.setDecimals(4)
        min_spin.setValue(-0.1)
        form.addRow("Min Deviation:", min_spin)
        
        max_spin = QDoubleSpinBox()
        max_spin.setRange(-10, 10)
        max_spin.setDecimals(4)
        max_spin.setValue(0.1)
        form.addRow("Max Deviation:", max_spin)
        
        dist_combo = QComboBox()
        dist_combo.addItems(["uniform", "gaussian"])
        form.addRow("Distribution:", dist_combo)
        
        layout.addLayout(form)
        
        add_btn = QPushButton("Add")
        add_btn.clicked.connect(dialog.accept)
        layout.addWidget(add_btn)
        
        if dialog.exec():
            p_type = next((t for t in ToleranceType if t.value == type_combo.currentText()), ToleranceType.RADIUS_1)
            
            operand = ToleranceOperand(
                element_index=int(elem_combo.currentText()),
                param_type=p_type,
                min_val=min_spin.value(),
                max_val=max_spin.value(),
                distribution=dist_combo.currentText()
            )
            self._parent._tol_operands.append(operand)
            self._update_tolerance_operands_display()

    def _on_add_default_tolerances(self):
        """Add standard tolerances"""
        if not self._parent or not self._parent._current_lens:
            return
            
        num_elements = 1
        if hasattr(self._parent._current_lens, 'elements'):
            num_elements = len(self._parent._current_lens.elements)
            
        new_operands = []
        for i in range(num_elements):
            new_operands.extend([
                ToleranceOperand(i, ToleranceType.RADIUS_1, -0.1, 0.1),
                ToleranceOperand(i, ToleranceType.RADIUS_2, -0.1, 0.1),
                ToleranceOperand(i, ToleranceType.THICKNESS, -0.05, 0.05),
                ToleranceOperand(i, ToleranceType.DECENTER_Y, -0.05, 0.05),
                ToleranceOperand(i, ToleranceType.TILT_X, -0.1, 0.1),
            ])
        
        self._parent._tol_operands.extend(new_operands)
        self._update_tolerance_operands_display()

    def _on_remove_tolerance(self):
        """Remove selected tolerance operands"""
        if not self._parent:
            return
        selected_rows = sorted(set(index.row() for index in self._tol_table.selectedIndexes()), reverse=True)
        if not selected_rows and self._parent._tol_operands:
            self._parent._tol_operands.pop()
        else:
            for row in selected_rows:
                if row < len(self._parent._tol_operands):
                    self._parent._tol_operands.pop(row)
        
        self._update_tolerance_operands_display()

    def _on_clear_tolerances(self):
        """Clear all tolerances"""
        if not self._parent or not self._parent._tol_operands:
            return
            
        if QMessageBox.question(self, "Clear All", "Are you sure you want to clear all tolerance operands?",
                               QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self._parent._tol_operands = []
            self._update_tolerance_operands_display()

    def _on_tol_item_changed(self, item):
        """Handle manual edits"""
        if not self._parent:
            return
        row = item.row()
        col = item.column()
        if row < len(self._parent._tol_operands) and col in (2, 3):
            try:
                val = float(item.text())
                if col == 2:
                    self._parent._tol_operands[row].min_val = val
                else:
                    self._parent._tol_operands[row].max_val = val
            except ValueError:
                self._update_tolerance_operands_display()

    def _update_tolerance_operands_display(self):
        """Update the table display"""
        if not self._parent:
            return
        self._tol_table.blockSignals(True)
        self._tol_table.setRowCount(len(self._parent._tol_operands))
        
        for i, op in enumerate(self._parent._tol_operands):
            item0 = QTableWidgetItem(str(op.element_index))
            item0.setFlags(item0.flags() & ~Qt.ItemIsEditable)
            self._tol_table.setItem(i, 0, item0)
            
            item1 = QTableWidgetItem(op.param_type.value)
            item1.setFlags(item1.flags() & ~Qt.ItemIsEditable)
            self._tol_table.setItem(i, 1, item1)
            
            self._tol_table.setItem(i, 2, QTableWidgetItem(f"{op.min_val:+.4f}"))
            self._tol_table.setItem(i, 3, QTableWidgetItem(f"{op.max_val:+.4f}"))
            
            dist = getattr(op, 'distribution', 'uniform')
            item4 = QTableWidgetItem(dist)
            item4.setFlags(item4.flags() & ~Qt.ItemIsEditable)
            self._tol_table.setItem(i, 4, item4)
            
        self._tol_table.blockSignals(False)

    def _on_run_monte_carlo(self):
        """Run Monte Carlo analysis"""
        if not self._parent or not self._parent._current_lens:
            self._tol_results_text.setPlainText("No lens selected.")
            return
        
        if not self._parent._tol_operands:
            self._tol_results_text.setPlainText("No tolerance operands defined.")
            return
        
        self._tol_results_text.setPlainText(f"Starting Monte Carlo analysis ({self._tol_num_trials.value()} trials)...")
        self._tol_progress.setVisible(True)
        self._tol_progress.setValue(0)
        
        thread = threading.Thread(target=self._run_mc_worker, daemon=True)
        thread.start()

    def _run_mc_worker(self):
        """Worker thread for Monte Carlo analysis"""
        from src.optical_system import OpticalSystem
        try:
            system = OpticalSystem(name="Tolerancing")
            system.add_lens(copy.deepcopy(self._parent._current_lens))
            
            analyzer = MonteCarloAnalyzer(system, self._parent._tol_operands)
            num_trials = self._tol_num_trials.value()
            criterion = self._tol_criterion.value()
            
            results = analyzer.run_monte_carlo(num_trials=num_trials, criterion=criterion)
            
            text = f"=== MONTE CARLO RESULTS ===\n\n"
            text += f"Total Trials: {results['total_trials']}\n"
            text += f"Passed (Yield): {results['passed_trials']} ({results['yield_percent']:.1f}%)\n"
            text += f"Failed: {results['failed_trials']}\n"
            text += f"RMS Spot Size - Mean: {results['mean_rms']:.4f} mm\n"
            text += f"RMS Spot Size - Std Dev: {results['std_rms']:.4f} mm\n"
            text += f"RMS Spot Size - Max: {results['max_rms']:.4f} mm\n"
            text += f"RMS Spot Size - Min: {results['min_rms']:.4f} mm\n"
            
            QMetaObject.invokeMethod(self, "_on_analysis_finished", 
                                   Qt.QueuedConnection,
                                   Q_ARG(str, text),
                                   Q_ARG(dict, results))
            
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            QMetaObject.invokeMethod(self, "_on_analysis_failed",
                                   Qt.QueuedConnection,
                                   Q_ARG(str, f"Monte Carlo Error: {e}\n{error_details}"))

    @Slot(str, dict)
    def _on_analysis_finished(self, text, results):
        """Callback for finished analysis"""
        self._tol_results_text.setPlainText(text)
        self._tol_progress.setValue(100)
        self._tol_progress.setVisible(False)
        
        if not results: return

        # Show histogram
        num_trials = results.get('total_trials', 100)
        criterion = self._tol_criterion.value()
        
        dialog = AnalysisPlotDialog(f"Monte Carlo Distribution - {self._parent._current_lens.name}", self)
        ax = dialog.get_axes()
        
        all_rms = results.get('all_rms', [])
        if all_rms:
            import numpy as np
            ax.hist(all_rms, bins=max(10, num_trials // 10), color='skyblue', edgecolor='black', alpha=0.7)
            ax.axvline(criterion, color='red', linestyle='--', label=f'Criterion ({criterion})')
            ax.axvline(results['mean_rms'], color='green', linestyle='-', label=f'Mean ({results["mean_rms"]:.4f})')
            ax.set_xlabel("RMS Spot Size (mm)")
            ax.set_ylabel("Frequency")
            ax.set_title("Monte Carlo Yield Distribution")
            ax.legend()
            ax.grid(True, linestyle='--', alpha=0.3)
            dialog.exec()

    @Slot(str)
    def _on_analysis_failed(self, error_msg):
        self._tol_results_text.setPlainText(error_msg)
        self._tol_progress.setVisible(False)

    def _on_run_inverse_sensitivity(self):
        """Run Inverse Sensitivity analysis"""
        if not self._parent or not self._parent._current_lens:
            self._tol_results_text.setPlainText("No lens selected.")
            return
        
        if not self._parent._tol_operands:
            self._tol_results_text.setPlainText("No tolerance operands defined.")
            return
        
        self._tol_results_text.setPlainText("Starting Inverse Sensitivity analysis...")
        self._tol_progress.setVisible(True)
        self._tol_progress.setMinimum(0)
        self._tol_progress.setMaximum(0)
        
        thread = threading.Thread(target=self._run_inv_worker, daemon=True)
        thread.start()

    def _run_inv_worker(self):
        """Worker thread for Inverse Sensitivity"""
        from src.optical_system import OpticalSystem
        try:
            system = OpticalSystem(name="Tolerancing")
            system.add_lens(copy.deepcopy(self._parent._current_lens))
            
            analyzer = InverseSensitivityAnalyzer(system, self._parent._tol_operands)
            criterion = self._tol_criterion.value()
            
            results = analyzer.optimize_limits(target_yield_criterion=criterion, method='rss')
            
            text = f"=== INVERSE SENSITIVITY RESULTS ===\n\n"
            text += f"Target Yield Criterion: {criterion} mm RMS\n\n"
            text += "Suggested Limits (RSS budget):\n"
            text += "-" * 55 + "\n"
            text += f"{'Elem':<5} | {'Type':<20} | {'Limit (+/-)':<10}\n"
            text += "-" * 55 + "\n"
            for op in results:
                text += f"{op.element_index:<5} | {op.param_type.value:<20} | {op.max_val:10.4f}\n"
            
            QMetaObject.invokeMethod(self, "_on_analysis_finished", 
                                   Qt.QueuedConnection,
                                   Q_ARG(str, text),
                                   Q_ARG(dict, {}))
                                   
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            QMetaObject.invokeMethod(self, "_on_analysis_failed",
                                   Qt.QueuedConnection,
                                   Q_ARG(str, f"Inverse Sensitivity Error: {e}\n{error_details}"))
