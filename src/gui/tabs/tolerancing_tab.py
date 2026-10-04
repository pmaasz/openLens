"""
OpenLens PySide6 Tolerancing Tab
Tab for tolerancing and yield analysis
"""

import logging
import copy
from typing import List

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QFormLayout,
    QDoubleSpinBox,
    QSpinBox,
    QComboBox,
    QCheckBox,
    QTextEdit,
    QPushButton,
    QScrollArea,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QProgressBar,
    QMessageBox,
    QDialog,
)
from PySide6.QtCore import Signal, Slot, Qt, QThread

from .base_tab import BaseTab
from ...tolerancing import (
    MonteCarloAnalyzer,
    InverseSensitivityAnalyzer,
    ToleranceOperand,
    ToleranceType,
)

logger = logging.getLogger(__name__)


def _as_system(target):
    """Wrap a bare Lens in a throwaway system; pass a system through.

    Both workers need an OpticalSystem to trace. A single lens gets a
    one-element wrapper; an assembly is already one and must be used as-is,
    otherwise its elements, gaps and alignment would be discarded and the
    element indices in the tolerance operands would refer to nothing.
    """
    from ...optical_system import OpticalSystem

    if isinstance(target, OpticalSystem):
        return target
    system = OpticalSystem(name="Tolerancing")
    system.add_lens(copy.deepcopy(target))
    return system


class MonteCarloWorker(QThread):
    """Background thread that runs the Monte Carlo tolerance analysis."""

    finished = Signal(str, dict)
    failed = Signal(str)

    def __init__(
        self,
        current_lens,
        tol_operands: List[ToleranceOperand],
        num_trials: int,
        criterion: float,
        refocus: bool = False,
        focus_range: float = 5.0,
    ) -> None:
        """Initialize the worker inputs.

        Args:
            current_lens: Lens under analysis (deep-copied before sampling).
            tol_operands: Tolerance operands defining the perturbations.
            num_trials: Number of Monte Carlo trials to run.
            criterion: RMS spot radius limit used as the pass/fail criterion.
            refocus: Re-optimize focus every trial (focus compensator).
            focus_range: Focus adjustment range (±mm) when refocusing.
        """
        super().__init__()
        self.current_lens = current_lens
        self.tol_operands = tol_operands
        self.num_trials = num_trials
        self.criterion = criterion
        self.refocus = refocus
        self.focus_range = focus_range

    def run(self) -> None:
        """Run the Monte Carlo analysis in this thread and emit ``finished``
        with a report and raw results, or ``failed`` on error."""
        from ...optical_system import OpticalSystem
        from ...tolerancing import ToleranceOperand as _Operand
        from ...tolerancing import ToleranceType as _Type

        try:
            system = _as_system(self.current_lens)

            compensators = []
            if self.refocus:
                compensators.append(_Operand(0, _Type.FOCUS, -self.focus_range, self.focus_range))
            analyzer = MonteCarloAnalyzer(system, self.tol_operands, compensators=compensators)

            results = analyzer.run(
                num_trials=self.num_trials,
                criterion="rms_spot_radius",
                criterion_limit=self.criterion,
            )

            text = f"=== MONTE CARLO RESULTS ===\n\n"
            text += f"Total Trials: {results['trials']}\n"
            text += f"Passed (Yield): {results['yield']:.1f}%\n"
            text += f"Nominal RMS: {results['nominal']:.4f} mm\n"
            text += f"Mean Performance: {results['mean']:.4f} mm\n"
            text += f"Std Dev: {results['std_dev']:.4f} mm\n"
            text += f"90th Percentile: {results['90th_percentile']:.4f} mm\n"
            text += f"Worst Case (Max): {results['max']:.4f} mm\n"

            self.finished.emit(text, results)

        except Exception as e:
            import traceback

            error_details = traceback.format_exc()
            self.failed.emit(f"Monte Carlo Error: {e}\n{error_details}")


class InverseSensitivityWorker(QThread):
    """Background thread that computes inverse sensitivity tolerance limits."""

    finished = Signal(str, dict)
    failed = Signal(str)

    def __init__(
        self,
        current_lens,
        tol_operands: List[ToleranceOperand],
        criterion: float,
    ) -> None:
        """Initialize the worker inputs.

        Args:
            current_lens: Lens under analysis (deep-copied before optimizing).
            tol_operands: Tolerance operands to budget.
            criterion: Target RMS yield criterion for the limit optimization.
        """
        super().__init__()
        self.current_lens = current_lens
        self.tol_operands = tol_operands
        self.criterion = criterion

    def run(self) -> None:
        """Run the inverse sensitivity analysis in this thread and emit
        ``finished`` with a report, or ``failed`` on error."""
        from ...optical_system import OpticalSystem

        try:
            system = _as_system(self.current_lens)

            analyzer = InverseSensitivityAnalyzer(system, self.tol_operands)

            results = analyzer.optimize_limits(target_yield_criterion=self.criterion, method="rss")

            text = f"=== INVERSE SENSITIVITY RESULTS ===\n\n"
            text += f"Target Yield Criterion: {self.criterion} mm RMS\n\n"
            text += "Suggested Limits (RSS budget):\n"
            text += "-" * 55 + "\n"
            text += f"{'Elem':<5} | {'Type':<20} | {'Limit (+/-)':<10}\n"
            text += "-" * 55 + "\n"
            for op in results:
                text += f"{op.element_index:<5} | {op.param_type.value:<20} | {op.max_val:10.4f}\n"

            self.finished.emit(text, {})

        except Exception as e:
            import traceback

            error_details = traceback.format_exc()
            self.failed.emit(f"Inverse Sensitivity Error: {e}\n{error_details}")


class TolerancingTab(BaseTab):
    """Tab for tolerancing and yield analysis"""

    def _setup_ui(self) -> None:
        """Build the operands table, analysis controls, and results panel."""
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
        self._grade_combo = QComboBox()
        self._grade_combo.addItems(["Commercial", "Precision", "High Precision"])
        self._grade_combo.setCurrentText("Precision")
        grade_btn = QPushButton("Load Grade")
        grade_btn.clicked.connect(self._on_load_grade)

        toolbar_layout.addWidget(add_btn)
        toolbar_layout.addWidget(remove_btn)
        toolbar_layout.addWidget(clear_btn)
        toolbar_layout.addWidget(default_btn)
        toolbar_layout.addWidget(self._grade_combo)
        toolbar_layout.addWidget(grade_btn)
        left_layout.addWidget(toolbar)

        # Operands table
        self._tol_table = QTableWidget()
        self._tol_table.setColumnCount(5)
        self._tol_table.setHorizontalHeaderLabels(
            ["Element #", "Type", "Min", "Max", "Distribution"]
        )
        self._tol_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._tol_table.setEditTriggers(QTableWidget.DoubleClicked)
        self._tol_table.itemChanged.connect(self._on_tol_item_changed)
        self._tol_table.setStyleSheet(
            "background-color: #2b2b2b; color: #e0e0e0; font-family: Courier; font-size: 10px;"
        )
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

        self._tol_refocus_check = QCheckBox("Refocus each trial")
        self._tol_refocus_check.setChecked(True)
        mc_layout.addRow("Focus Compensator:", self._tol_refocus_check)

        self._tol_focus_range = QDoubleSpinBox()
        self._tol_focus_range.setRange(0.1, 50.0)
        self._tol_focus_range.setValue(5.0)
        self._tol_focus_range.setSuffix(" mm")
        mc_layout.addRow("Focus Range (±):", self._tol_focus_range)

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
        self._tol_results_text.setStyleSheet(
            "background-color: #2b2b2b; color: #e0e0e0; font-family: Courier; font-size: 10px;"
        )
        self._mc_running = False
        self._inv_running = False
        self._tol_last_results = {}

        self._tol_results_text.setPlainText(
            "Configure tolerances and click 'Run Monte Carlo' or 'Inverse Sensitivity' to analyze."
        )
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

        # One guard per worker: each button starts its own thread, and a
        # second click while one is in flight would otherwise leave the
        # previous thread's result racing the new one's.
        self._mc_running = False
        self._inv_running = False

    def refresh(self) -> None:
        """Update display when parent changes.

        Reloads the operand table from the parent window's current lens/system
        state.
        """
        if self._parent and hasattr(self._parent, "_tol_operands"):
            self._update_tolerance_operands_display()

    def _resolve_target(self):
        """The lens or assembly being toleranced, whichever is current.

        The tab used to gate on ``_current_lens`` alone, which is explicitly
        None whenever an assembly is current - so the entire multi-element
        workflow, the tab's reason to exist, was unreachable, and "Add
        Tolerance", "Default Set" and "Load Grade" were silent no-ops.
        """
        if not self._parent:
            return None
        # getattr rather than attribute access: the tab is also driven by
        # tests and embedders that supply only part of the parent surface,
        # and this file already guards parent attributes with hasattr.
        return getattr(self._parent, "_current_assembly", None) or getattr(
            self._parent, "_current_lens", None
        )

    def _require_target(self) -> bool:
        """Report and return False when nothing is selected."""
        if self._resolve_target() is None:
            self._tol_results_text.setPlainText("No lens or assembly selected.")
            return False
        return True

    def _on_add_tolerance(self) -> None:
        """Add a new tolerance operand.

        Shows a dialog to configure the operand, then appends it to the parent
        window's tolerance list.
        """
        if not self._require_target():
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Add Tolerance Operand")
        layout = QVBoxLayout(dialog)
        form = QFormLayout()

        # Element selection: one entry for a bare lens, one per element for
        # an assembly.
        target = self._resolve_target()
        num_elements = len(getattr(target, "elements", None) or [target])

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
            p_type = next(
                (t for t in ToleranceType if t.value == type_combo.currentText()),
                ToleranceType.RADIUS_1,
            )

            operand = ToleranceOperand(
                element_index=int(elem_combo.currentText()),
                param_type=p_type,
                min_val=min_spin.value(),
                max_val=max_spin.value(),
                distribution=dist_combo.currentText(),
            )
            self._parent._tol_operands.append(operand)
            self._update_tolerance_operands_display()

    def _on_add_default_tolerances(self) -> None:
        """Add standard tolerances."""
        if not self._require_target():
            return

        num_elements = 1
        target = self._resolve_target()
        num_elements = len(getattr(target, "elements", []) or [target])

        new_operands = []
        for i in range(num_elements):
            new_operands.extend(
                [
                    ToleranceOperand(i, ToleranceType.RADIUS_1, -0.1, 0.1),
                    ToleranceOperand(i, ToleranceType.RADIUS_2, -0.1, 0.1),
                    ToleranceOperand(i, ToleranceType.THICKNESS, -0.05, 0.05),
                    ToleranceOperand(i, ToleranceType.DECENTER_Y, -0.05, 0.05),
                    ToleranceOperand(i, ToleranceType.TILT_X, -0.1, 0.1),
                ]
            )

        self._parent._tol_operands.extend(new_operands)
        self._update_tolerance_operands_display()

    def _on_load_grade(self) -> None:
        """Build a full shop-grade tolerance set for the current target."""
        from ...tolerancing import tolerances_for_system
        from ...optical_system import OpticalSystem

        if not self._require_target():
            return
        target = self._resolve_target()
        if hasattr(target, "elements"):
            system = target
        else:
            system = OpticalSystem(name="Tolerancing")
            system.add_lens(copy.deepcopy(target))
        try:
            new_operands = tolerances_for_system(system, self._grade_combo.currentText())
        except ValueError:
            return
        self._parent._tol_operands.extend(new_operands)
        self._update_tolerance_operands_display()

    def _on_remove_tolerance(self) -> None:
        """Remove selected tolerance operands."""
        if not self._parent:
            return
        selected_rows = sorted(
            set(index.row() for index in self._tol_table.selectedIndexes()),
            reverse=True,
        )
        if not selected_rows and self._parent._tol_operands:
            self._parent._tol_operands.pop()
        else:
            for row in selected_rows:
                if row < len(self._parent._tol_operands):
                    self._parent._tol_operands.pop(row)

        self._update_tolerance_operands_display()

    def _on_clear_tolerances(self) -> None:
        """Clear all tolerances."""
        if not self._parent or not self._parent._tol_operands:
            return

        if (
            QMessageBox.question(
                self,
                "Clear All",
                "Are you sure you want to clear all tolerance operands?",
                QMessageBox.Yes | QMessageBox.No,
            )
            == QMessageBox.Yes
        ):
            self._parent._tol_operands = []
            self._update_tolerance_operands_display()

    def _on_tol_item_changed(self, item: QTableWidgetItem) -> None:
        """Handle manual edits.

        Args:
            item: Table item whose edited Min/Max cell updates the matching
                tolerance operand.
        """
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

    def _update_tolerance_operands_display(self) -> None:
        """Update the table display."""
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

            dist = getattr(op, "distribution", "uniform")
            item4 = QTableWidgetItem(dist)
            item4.setFlags(item4.flags() & ~Qt.ItemIsEditable)
            self._tol_table.setItem(i, 4, item4)

        self._tol_table.blockSignals(False)

    def _on_run_monte_carlo(self) -> None:
        """Run Monte Carlo analysis.

        Starts a :class:`MonteCarloWorker` thread using the current operands
        and trial settings from the UI.
        """
        if not self._require_target():
            return

        if not self._parent._tol_operands:
            self._tol_results_text.setPlainText("No tolerance operands defined.")
            return

        if self._mc_running:
            self._tol_results_text.setPlainText("Monte Carlo analysis already running.")
            return

        self._mc_running = True
        self._tol_results_text.setPlainText(
            f"Starting Monte Carlo analysis ({self._tol_num_trials.value()} trials)..."
        )
        self._tol_progress.setVisible(True)
        self._tol_progress.setValue(0)
        self._tol_progress.setMinimum(0)
        self._tol_progress.setMaximum(0)

        self._mc_worker = MonteCarloWorker(
            self._resolve_target(),
            self._parent._tol_operands,
            self._tol_num_trials.value(),
            self._tol_criterion.value(),
            refocus=self._tol_refocus_check.isChecked(),
            focus_range=self._tol_focus_range.value(),
        )
        self._mc_worker.finished.connect(self._on_analysis_finished)
        self._mc_worker.failed.connect(self._on_analysis_failed)
        self._mc_worker.start()

    def _on_run_inverse_sensitivity(self) -> None:
        """Run Inverse Sensitivity analysis.

        Starts an :class:`InverseSensitivityWorker` thread to compute RSS
        budgeted tolerance limits for the current operands.
        """
        if not self._require_target():
            return

        if not self._parent._tol_operands:
            self._tol_results_text.setPlainText("No tolerance operands defined.")
            return

        if self._inv_running:
            self._tol_results_text.setPlainText("Inverse Sensitivity analysis already running.")
            return

        self._inv_running = True
        self._tol_results_text.setPlainText("Starting Inverse Sensitivity analysis...")
        self._tol_progress.setVisible(True)
        self._tol_progress.setMinimum(0)
        self._tol_progress.setMaximum(0)

        self._inv_worker = InverseSensitivityWorker(
            self._resolve_target(),
            self._parent._tol_operands,
            self._tol_criterion.value(),
        )
        self._inv_worker.finished.connect(self._on_analysis_finished)
        self._inv_worker.failed.connect(self._on_analysis_failed)
        self._inv_worker.start()

    # ------------------------------------------------------------------
    # Worker completion slots
    #
    # Both run handlers put the progress bar into busy mode (range 0..0, an
    # indeterminate spinner) before starting their thread, so these two slots
    # are the only place that takes it back out. They are the sole reset path
    # for every worker this tab starts.
    # ------------------------------------------------------------------

    @Slot(str, dict)
    def _on_analysis_finished(self, text: str, results: dict) -> None:
        """Display a finished analysis report and clear the busy indicator.

        Args:
            text: Preformatted report emitted by the worker.
            results: Raw analyzer payload carried by the signal. Kept for
                callers that want the numbers; this tab renders only the
                formatted report.
        """
        self._mc_running = False
        self._inv_running = False
        self._tol_last_results = results
        self._tol_progress.setMaximum(100)
        self._tol_progress.setValue(100)
        self._tol_results_text.setPlainText(text)

    @Slot(str)
    def _on_analysis_failed(self, message: str) -> None:
        """Report a failed analysis and clear the busy indicator.

        Args:
            message: Error description emitted by the worker.
        """
        self._mc_running = False
        self._inv_running = False
        self._tol_progress.setMaximum(100)
        self._tol_progress.setValue(0)
        self._tol_results_text.setPlainText(message)
