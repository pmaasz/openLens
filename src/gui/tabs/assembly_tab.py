"""
OpenLens PySide6 Assembly Tab
Multi-element optical system builder
"""

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, 
                               QFormLayout, QDoubleSpinBox, QPushButton, 
                               QListWidget, QListWidgetItem)
from src.gui.tabs.base_tab import BaseTab
from src.gui.widgets.assembly_viz import AssemblyVisualizationWidget
from src.optical_system import OpticalSystem


class AssemblyTab(BaseTab):
    """Multi-element optical system builder"""
    
    def _setup_ui(self):
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
        self._air_gap_input = QDoubleSpinBox()
        self._air_gap_input.setRange(0, 1000)
        self._air_gap_input.setSuffix(" mm")
        self._air_gap_input.valueChanged.connect(self._on_air_gap_changed)
        ag_layout.addRow("Thickness:", self._air_gap_input)
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
        layout.addWidget(left_panel, 1)
        
        # Right: 2D visualization
        self._assembly_viz = AssemblyVisualizationWidget()
        layout.addWidget(self._assembly_viz, 2)
        
        # Create optical system
        self._optical_system = OpticalSystem(name="New Assembly")
        self.refresh_lens_list()

    def refresh_lens_list(self):
        """Populate the lens selection list from the main window's lens collection"""
        self._assembly_lens_list.clear()
        if hasattr(self._parent, '_lenses'):
            for lens in self._parent._lenses:
                self._assembly_lens_list.addItem(lens.name)

    def _update_system_list(self):
        """Update the system list widget from the optical system model"""
        self._system_list.clear()
        for i, element in enumerate(self._optical_system.elements):
            gap = self._optical_system.air_gaps[i] if i < len(self._optical_system.air_gaps) else 0.0
            item = QListWidgetItem(f"{i+1}: {element.lens.name} (Gap: {gap:.1f}mm)")
            self._system_list.addItem(item)

    def _on_add_lens_to_system(self):
        """Add selected lens to optical system"""
        current = self._assembly_lens_list.currentRow()
        if current >= 0 and current < len(self._parent._lenses):
            lens = self._parent._lenses[current]
            self._optical_system.add_lens(lens, air_gap_before=5.0)
            self._update_system_list()
            self._assembly_viz.update_system(self._optical_system)
            self._on_assembly_changed()
    
    def _on_remove_lens_from_system(self):
        """Remove selected lens from system"""
        current = self._system_list.currentRow()
        if current >= 0 and current < len(self._optical_system.elements):
            self._optical_system.remove_lens(current)
            self._update_system_list()
            self._assembly_viz.update_system(self._optical_system)
            self._on_assembly_changed()
    
    def _on_move_lens_up(self):
        """Move lens up in system"""
        current = self._system_list.currentRow()
        if current > 0:
            self._optical_system.elements[current], self._optical_system.elements[current-1] = \
                self._optical_system.elements[current-1], self._optical_system.elements[current]
            self._update_system_list()
            self._assembly_viz.update_system(self._optical_system)
            self._on_assembly_changed()
    
    def _on_move_lens_down(self):
        """Move lens down in system"""
        current = self._system_list.currentRow()
        if current >= 0 and current < len(self._optical_system.elements) - 1:
            self._optical_system.elements[current], self._optical_system.elements[current+1] = \
                self._optical_system.elements[current+1], self._optical_system.elements[current]
            self._update_system_list()
            self._assembly_viz.update_system(self._optical_system)
            self._on_assembly_changed()

    def _on_system_item_selected(self, index):
        """Handle system item selection"""
        if index >= 0:
            self._air_gap_group.setEnabled(True)
            gap = self._optical_system.air_gaps[index] if index < len(self._optical_system.air_gaps) else 0.0
            self._air_gap_input.blockSignals(True)
            self._air_gap_input.setValue(gap)
            self._air_gap_input.blockSignals(False)
        else:
            self._air_gap_group.setEnabled(False)

    def _on_air_gap_changed(self, value):
        """Update air gap for selected element"""
        current = self._system_list.currentRow()
        if current >= 0 and current < len(self._optical_system.air_gaps):
            self._optical_system.air_gaps[current] = value
            self._update_system_list()
            self._assembly_viz.update_system(self._optical_system)
            self._on_assembly_changed()

    def _on_assembly_changed(self):
        """Notify parent window of assembly changes"""
        self._parent._current_assembly = self._optical_system
        self._parent._update_status(f"Assembly updated: {self._optical_system.name}")
        self.data_updated.emit()

    def refresh(self):
        """Refresh assembly tab state from parent's current assembly"""
        self.refresh_lens_list()
        
        # Sync with parent's current assembly if it exists
        if hasattr(self._parent, '_current_assembly') and self._parent._current_assembly:
            self._optical_system = self._parent._current_assembly
            self._update_system_list()
            
        self._assembly_viz.update_system(self._optical_system)
