"""
OpenLens PySide6 Simulation Tab
Simulation controls and visualization
"""

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
                               QFormLayout, QSpinBox, QDoubleSpinBox, QComboBox,
                               QCheckBox, QPushButton, QLabel)
from .base_tab import BaseTab
from ..widgets.simulation_viz import SimulationVisualizationWidget


class SimulationTab(BaseTab):
    """Simulation controls and visualization"""
    
    def _setup_ui(self) -> None:
        """Build the ray source controls panel and the visualization widget."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Left: Controls
        controls = QWidget()
        controls_layout = QVBoxLayout(controls)
        
        # Source configuration
        source_group = QGroupBox("Ray Source")
        source_layout = QFormLayout(source_group)
        
        self._sim_num_rays = QSpinBox()
        self._sim_num_rays.setRange(1, 51)
        self._sim_num_rays.setValue(11)
        source_layout.addRow("Number of Rays:", self._sim_num_rays)
        
        self._sim_angle = QDoubleSpinBox()
        self._sim_angle.setRange(-45, 45)
        self._sim_angle.setValue(0)
        source_layout.addRow("Angle (deg):", self._sim_angle)
        
        self._sim_source_height = QDoubleSpinBox()
        self._sim_source_height.setRange(-50, 50)
        self._sim_source_height.setValue(0)
        source_layout.addRow("Source Height:", self._sim_source_height)
        
        self._sim_wavelength = QComboBox()
        self._sim_wavelength.addItems(["400 nm (Violet)", "450 nm (Blue)", "550 nm (Green)", "650 nm (Red)", "700 nm (IR)", "Custom"])
        self._sim_wavelength.setCurrentIndex(2)  # Default to 550nm (Green)
        source_layout.addRow("Wavelength:", self._sim_wavelength)
        
        self._sim_custom_label = QLabel("Custom:")
        self._sim_custom_wavelength = QDoubleSpinBox()
        self._sim_custom_wavelength.setRange(380, 780)
        self._sim_custom_wavelength.setValue(550)
        self._sim_custom_wavelength.setSuffix(" nm")
        self._sim_custom_label.setVisible(False)
        self._sim_custom_wavelength.setVisible(False)
        source_layout.addRow(self._sim_custom_label, self._sim_custom_wavelength)
        
        # Connect wavelength combo to enable/disable custom
        self._sim_wavelength.currentIndexChanged.connect(self._on_wavelength_changed)
        
        controls_layout.addWidget(source_group)
        
        # Ghost analysis checkbox
        self._ghost_analysis = QCheckBox("Show Ghost Analysis")
        controls_layout.addWidget(self._ghost_analysis)
        
        ghost_note = QLabel("Analyze 2nd order reflections")
        ghost_note.setStyleSheet("color: #888; font-size: 10px;")
        controls_layout.addWidget(ghost_note)
        
        # Simulation buttons
        btn_layout = QHBoxLayout()
        run_btn = QPushButton("Run Simulation")
        run_btn.clicked.connect(self._on_run_simulation)
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self._on_clear_simulation)
        btn_layout.addWidget(run_btn)
        btn_layout.addWidget(clear_btn)
        controls_layout.addLayout(btn_layout)
        
        # Reset View button
        reset_view_btn = QPushButton("Reset View")
        reset_view_btn.clicked.connect(self._reset_simulation_view)
        controls_layout.addWidget(reset_view_btn)
        
        controls_layout.addStretch()
        layout.addWidget(controls, 1)
        
        # Right: Visualization
        self._sim_viz = SimulationVisualizationWidget()
        layout.addWidget(self._sim_viz, 3)

    def _on_run_simulation(self) -> None:
        """Run ray tracing simulation.

        Reads the source settings from the controls and forwards them, along
        with the active lens/assembly from the parent window, to the
        visualization widget.
        """
        active_system = self._parent._current_assembly if self._parent._current_assembly else self._parent._current_lens
        if active_system:
            num_rays = int(self._sim_num_rays.value())
            angle = self._sim_angle.value()
            source_height = self._sim_source_height.value()
            show_ghosts = self._ghost_analysis.isChecked()
            
            # Get wavelength
            wavelength_idx = self._sim_wavelength.currentIndex()
            if wavelength_idx == 5:  # Custom
                wavelength = self._sim_custom_wavelength.value()
            else:
                wavelengths = [400, 450, 550, 650, 700]
                wavelength = wavelengths[wavelength_idx]
            
            self._sim_viz.run_simulation(active_system, num_rays, angle, source_height, show_ghosts, wavelength)
    
    def _on_wavelength_changed(self, index: int) -> None:
        """Show/hide custom wavelength input based on selection.

        Args:
            index: Index of the selected wavelength entry; index 5 selects
                the custom wavelength input.
        """
        is_custom = (index == 5)
        self._sim_custom_label.setVisible(is_custom)
        self._sim_custom_wavelength.setVisible(is_custom)
        self._sim_custom_wavelength.setEnabled(is_custom)
    
    def _on_clear_simulation(self) -> None:
        """Clear simulation visualization."""
        self._sim_viz.clear_simulation()
    
    def _reset_simulation_view(self) -> None:
        """Reset the simulation view (zoom and pan)."""
        self._sim_viz.reset_view()

    def refresh(self) -> None:
        """Refresh simulation state if needed.

        Reloads from the parent window's current lens/system state; currently
        no extra work is required.
        """
        pass
