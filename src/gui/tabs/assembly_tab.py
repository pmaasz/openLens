"""
OpenLens PySide6 Assembly Tab
Multi-element optical system builder
"""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QFormLayout,
    QComboBox,
    QDoubleSpinBox,
    QPushButton,
    QListWidget,
    QListWidgetItem,
)
from .base_tab import BaseTab
from ..widgets.assembly_viz import AssemblyVisualizationWidget
from ...optical_system import OpticalSystem, AirGap


class AssemblyTab(BaseTab):
    """Multi-element optical system builder"""

    def _setup_ui(self) -> None:
        """Build the builder panels and create the initial optical system."""
        layout = QHBoxLayout(self)

        # Left: Available lenses + System builder
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)

        # Lens selection
        lens_sel_group = QGroupBox("Lens Selection")
        lens_sel_layout = QVBoxLayout(lens_sel_group)
        self._assembly_lens_list = QListWidget()
        lens_sel_layout.addWidget(self._assembly_lens_list)

        add_btn = QPushButton("Add to System")
        add_btn.clicked.connect(self._on_add_lens_to_system)
        lens_sel_layout.addWidget(add_btn)

        left_layout.addWidget(lens_sel_group)

        # System builder
        sys_group = QGroupBox("System Builder")
        sys_layout = QVBoxLayout(sys_group)
        self._system_list = QListWidget()
        self._system_list.currentRowChanged.connect(self._on_system_item_selected)
        sys_layout.addWidget(self._system_list)

        # Air Gap Editor (contextual)
        self._air_gap_group = QGroupBox("Air Gap (Before Selected Element)")
        self._air_gap_group.setEnabled(False)
        ag_layout = QFormLayout(self._air_gap_group)

        input_row = QHBoxLayout()
        self._air_gap_input = QDoubleSpinBox()
        self._air_gap_input.setRange(0, 1000)
        self._air_gap_input.setDecimals(3)
        self._air_gap_input.setSingleStep(0.1)
        self._air_gap_input.setSuffix(" mm")
        # Removed the direct valueChanged connection to prevent jumping during typing

        self._apply_gap_btn = QPushButton("Set")
        self._apply_gap_btn.setFixedWidth(60)
        self._apply_gap_btn.clicked.connect(self._on_apply_gap_clicked)

        input_row.addWidget(self._air_gap_input)
        input_row.addWidget(self._apply_gap_btn)

        ag_layout.addRow("Thickness:", input_row)
        sys_layout.addWidget(self._air_gap_group)

        btn_row = QHBoxLayout()
        up_btn = QPushButton("Up")
        up_btn.clicked.connect(self._on_move_lens_up)
        down_btn = QPushButton("Down")
        down_btn.clicked.connect(self._on_move_lens_down)
        remove_btn = QPushButton("Remove")
        remove_btn.clicked.connect(self._on_remove_lens_from_system)
        btn_row.addWidget(up_btn)
        btn_row.addWidget(down_btn)
        btn_row.addWidget(remove_btn)
        sys_layout.addLayout(btn_row)

        left_layout.addWidget(sys_group)

        # Aperture stop: which air gap holds the stop, and its diameter.
        # 0 diameter = unspecified (position only).
        stop_group = QGroupBox("Aperture Stop")
        stop_layout = QFormLayout(stop_group)
        self._stop_gap_combo = QComboBox()
        stop_layout.addRow("Gap:", self._stop_gap_combo)
        self._stop_dia_input = QDoubleSpinBox()
        self._stop_dia_input.setRange(0, 500)
        self._stop_dia_input.setDecimals(3)
        self._stop_dia_input.setSingleStep(0.1)
        self._stop_dia_input.setSuffix(" mm")
        stop_layout.addRow("Diameter (0 = n/a):", self._stop_dia_input)
        stop_btn_row = QHBoxLayout()
        stop_set_btn = QPushButton("Set")
        stop_set_btn.clicked.connect(self._on_stop_set_clicked)
        stop_clear_btn = QPushButton("Clear")
        stop_clear_btn.clicked.connect(self._on_stop_clear_clicked)
        stop_btn_row.addWidget(stop_set_btn)
        stop_btn_row.addWidget(stop_clear_btn)
        stop_layout.addRow(stop_btn_row)
        left_layout.addWidget(stop_group)

        # Element alignment: decenter/tilt of the selected element.
        self._align_group = QGroupBox("Element Alignment")
        self._align_group.setEnabled(False)
        align_layout = QFormLayout(self._align_group)
        self._decenter_y_input = QDoubleSpinBox()
        self._decenter_y_input.setRange(-10, 10)
        self._decenter_y_input.setDecimals(3)
        self._decenter_y_input.setSuffix(" mm")
        align_layout.addRow("Decenter Y:", self._decenter_y_input)
        self._decenter_z_input = QDoubleSpinBox()
        self._decenter_z_input.setRange(-10, 10)
        self._decenter_z_input.setDecimals(3)
        self._decenter_z_input.setSuffix(" mm")
        align_layout.addRow("Decenter Z:", self._decenter_z_input)
        self._tilt_inputs = []
        for axis in ("X", "Y", "Z"):
            spin = QDoubleSpinBox()
            spin.setRange(-5, 5)
            spin.setDecimals(3)
            spin.setSuffix(" deg")
            align_layout.addRow(f"Tilt {axis}:", spin)
            self._tilt_inputs.append(spin)
        align_apply_btn = QPushButton("Apply to selected element")
        align_apply_btn.clicked.connect(self._on_align_apply_clicked)
        align_layout.addRow(align_apply_btn)
        left_layout.addWidget(self._align_group)

        layout.addWidget(left_panel, 1)

        # Right: 2D visualization
        self._assembly_viz = AssemblyVisualizationWidget()
        layout.addWidget(self._assembly_viz, 2)

        # Create optical system
        self._optical_system = OpticalSystem(name="New Assembly")
        self.refresh_lens_list()

    def refresh_lens_list(self) -> None:
        """Populate the lens selection list from the main window's lens collection.

        Schedules a retry via a short timer while the list is still empty,
        e.g. when the database load has not finished yet.
        """
        self._assembly_lens_list.clear()
        if hasattr(self._parent, "_lenses"):
            for lens in self._parent._lenses:
                self._assembly_lens_list.addItem(lens.name)

        # If the list is still empty, try to refresh it again in 100ms
        # This handles cases where the database load is still in progress
        if self._assembly_lens_list.count() == 0:
            from PySide6.QtCore import QTimer

            QTimer.singleShot(100, self.refresh_lens_list)

    def _update_system_list(self) -> None:
        """Update the system list widget from the optical system model."""
        self._system_list.clear()
        stop = self._optical_system.get_aperture_stop()
        stop_gap = stop["gap_index"] if stop is not None else None
        for i, element in enumerate(self._optical_system.elements):
            # Air gap before element i is at index i-1
            gap_str = ""
            if i > 0 and i - 1 < len(self._optical_system.air_gaps):
                gap = self._optical_system.air_gaps[i - 1]
                gap_value = gap.thickness if isinstance(gap, AirGap) else gap
                gap_str = f" (Gap: {gap_value:.3f}mm)"
                if stop_gap is not None and i - 1 == stop_gap:
                    dia = stop.get("diameter")
                    gap_str += f" STOP{f' Ø{dia:.2f}mm' if dia else ''}"
            align_str = ""
            if any(
                abs(getattr(element, attr, 0.0) or 0.0) > 1e-12
                for attr in ("decenter_y", "decenter_z", "tilt_x", "tilt_y", "tilt_z")
            ):
                align_str = " [aligned≠0]"

            item = QListWidgetItem(f"{i+1}: {element.lens.name}{gap_str}{align_str}")
            self._system_list.addItem(item)
        self._refresh_stop_ui()

    def _refresh_stop_ui(self) -> None:
        """Rebuild the stop gap combo and reflect the current stop."""
        combo = self._stop_gap_combo
        combo.blockSignals(True)
        combo.clear()
        gaps = self._optical_system.air_gaps
        if not gaps:
            combo.addItem("(no air gaps)", -1)
            combo.setEnabled(False)
        else:
            combo.setEnabled(True)
            for g in range(len(gaps)):
                combo.addItem(f"Gap {g} (before element {g + 2})", g)
        stop = self._optical_system.get_aperture_stop()
        if stop is not None:
            idx = combo.findData(stop["gap_index"])
            combo.setCurrentIndex(idx if idx >= 0 else 0)
            dia = stop.get("diameter")
            self._stop_dia_input.setValue(dia if dia else 0.0)
        else:
            combo.setCurrentIndex(0)
            self._stop_dia_input.setValue(0.0)
        combo.blockSignals(False)

    def _on_stop_set_clicked(self) -> None:
        """Place the aperture stop in the selected gap."""
        gap_index = self._stop_gap_combo.currentData()
        if gap_index is None or gap_index < 0:
            return
        diameter = self._stop_dia_input.value()
        try:
            self._optical_system.set_aperture_stop(
                int(gap_index), diameter if diameter > 0 else None
            )
        except ValueError:
            return
        self._update_system_list()
        self._assembly_viz.update_system(self._optical_system)
        self._on_assembly_changed()

    def _on_stop_clear_clicked(self) -> None:
        """Remove the aperture stop definition."""
        self._optical_system.clear_aperture_stop()
        self._update_system_list()
        self._assembly_viz.update_system(self._optical_system)
        self._on_assembly_changed()

    def _on_align_apply_clicked(self) -> None:
        """Apply decenter/tilt values to the selected element."""
        current = self._system_list.currentRow()
        if current < 0 or current >= len(self._optical_system.elements):
            return
        tilts = [spin.value() for spin in self._tilt_inputs]
        if self._optical_system.set_element_alignment(
            current,
            decenter_y=self._decenter_y_input.value(),
            decenter_z=self._decenter_z_input.value(),
            tilt_x=tilts[0],
            tilt_y=tilts[1],
            tilt_z=tilts[2],
        ):
            self._update_system_list()
            self._assembly_viz.update_system(self._optical_system)
            self._on_assembly_changed()

    def _on_add_lens_to_system(self) -> None:
        """Add selected lens to optical system."""
        current = self._assembly_lens_list.currentRow()
        if current >= 0 and current < len(self._parent._lenses):
            lens = self._parent._lenses[current]
            # Default gap 5.0mm if not the first element
            gap = 5.0 if self._optical_system.elements else 0.0
            self._optical_system.add_lens(lens, air_gap_before=gap)
            self._update_system_list()
            self._assembly_viz.update_system(self._optical_system)
            self._on_assembly_changed()

    def _on_remove_lens_from_system(self) -> None:
        """Remove selected lens from system."""
        current = self._system_list.currentRow()
        if current >= 0 and current < len(self._optical_system.elements):
            self._optical_system.remove_lens(current)
            self._update_system_list()
            self._assembly_viz.update_system(self._optical_system)
            self._on_assembly_changed()

    def _on_move_lens_up(self) -> None:
        """Move lens up in system."""
        current = self._system_list.currentRow()
        if current > 0:
            (
                self._optical_system.elements[current],
                self._optical_system.elements[current - 1],
            ) = (
                self._optical_system.elements[current - 1],
                self._optical_system.elements[current],
            )
            self._update_system_list()
            self._assembly_viz.update_system(self._optical_system)
            self._on_assembly_changed()

    def _on_move_lens_down(self) -> None:
        """Move lens down in system."""
        current = self._system_list.currentRow()
        if current >= 0 and current < len(self._optical_system.elements) - 1:
            (
                self._optical_system.elements[current],
                self._optical_system.elements[current + 1],
            ) = (
                self._optical_system.elements[current + 1],
                self._optical_system.elements[current],
            )
            self._update_system_list()
            self._assembly_viz.update_system(self._optical_system)
            self._on_assembly_changed()

    def _on_system_item_selected(self, index: int) -> None:
        """Handle system item selection.

        Args:
            index: Row index of the element selected in the system list;
                enables the air gap editor for rows after the first element.
        """
        if index > 0:
            self._air_gap_group.setEnabled(True)
            # The gap before the element at 'index' is at index-1 in the air_gaps list
            gap_index = index - 1
            if gap_index < len(self._optical_system.air_gaps):
                gap_obj = self._optical_system.air_gaps[gap_index]
                gap_value = gap_obj.thickness if isinstance(gap_obj, AirGap) else gap_obj
                self._air_gap_input.blockSignals(True)
                self._air_gap_input.setValue(gap_value)
                self._air_gap_input.blockSignals(False)
            else:
                self._air_gap_group.setEnabled(False)
        else:
            self._air_gap_group.setEnabled(False)

        # Alignment editor follows the selected element (any row, incl. 0).
        elements = self._optical_system.elements
        if 0 <= index < len(elements):
            self._align_group.setEnabled(True)
            element = elements[index]
            self._decenter_y_input.blockSignals(True)
            self._decenter_z_input.blockSignals(True)
            self._decenter_y_input.setValue(element.decenter_y or 0.0)
            self._decenter_z_input.setValue(element.decenter_z or 0.0)
            self._decenter_y_input.blockSignals(False)
            self._decenter_z_input.blockSignals(False)
            for spin, attr in zip(self._tilt_inputs, ("tilt_x", "tilt_y", "tilt_z")):
                spin.blockSignals(True)
                spin.setValue(getattr(element, attr, 0.0) or 0.0)
                spin.blockSignals(False)
        else:
            self._align_group.setEnabled(False)

    def _on_apply_gap_clicked(self) -> None:
        """Apply the current air gap value to the system."""
        self._on_air_gap_changed(self._air_gap_input.value())

    def _on_air_gap_changed(self, value: float) -> None:
        """Update air gap for selected element.

        Args:
            value: New air gap thickness in mm, applied to the gap before the
                element currently selected in the system list.
        """
        current = self._system_list.currentRow()
        if current >= 0:
            # The gap before the i-th element is at index i-1 in self.air_gaps
            gap_index = current - 1
            if gap_index >= 0 and gap_index < len(self._optical_system.air_gaps):
                gap_obj = self._optical_system.air_gaps[gap_index]
                if isinstance(gap_obj, AirGap):
                    gap_obj.thickness = value
                else:
                    self._optical_system.air_gaps[gap_index] = value

                # Update positions in the optical system
                self._optical_system._update_positions()

                self._update_system_list()
                self._assembly_viz.update_system(self._optical_system)
                self._on_assembly_changed()

    def _on_assembly_changed(self) -> None:
        """Notify parent window of assembly changes."""
        self._parent._current_assembly = self._optical_system
        self._parent._update_status(f"Assembly updated: {self._optical_system.name}")
        self.data_updated.emit()

    def refresh(self) -> None:
        """Refresh assembly tab state from parent's current assembly.

        Reloads the lens list and syncs the builder with the parent window's
        current lens/system state.
        """
        self.refresh_lens_list()

        # Sync with parent's current assembly if it exists
        if hasattr(self._parent, "_current_assembly") and self._parent._current_assembly:
            self._optical_system = self._parent._current_assembly
            self._update_system_list()

        self._assembly_viz.update_system(self._optical_system)
