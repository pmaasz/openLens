"""
OpenLens PySide6 Simulation Tab
Simulation controls and visualization
"""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QFormLayout,
    QSpinBox,
    QDoubleSpinBox,
    QComboBox,
    QCheckBox,
    QPushButton,
    QLabel,
)
from .base_tab import BaseTab
from ..widgets.simulation_viz import SimulationVisualizationWidget
from ...constants import WAVELENGTH_GREEN, WAVELENGTH_PRESETS

#: The wavelengths offered in the picker, as ``(nm, label)``. Both the numbers
#: and their order come from ``constants.WAVELENGTH_PRESETS``, so the
#: simulation and performance pickers cannot drift apart. The trace reads its
#: wavelength from this same table, so the combo's strings and the traced value
#: are one list.
SIMULATION_WAVELENGTHS = tuple(
    (nanometres, f"{nanometres:g} nm ({name})") for nanometres, name in WAVELENGTH_PRESETS
)

#: Index of the "Custom" entry, which follows the preset wavelengths.
CUSTOM_WAVELENGTH_INDEX = len(SIMULATION_WAVELENGTHS)

#: Preset wavelength selected by default: the photopic peak, which is also the
#: application's default for ray-tracing visualization.
DEFAULT_WAVELENGTH_INDEX = next(
    index
    for index, (nanometres, _label) in enumerate(SIMULATION_WAVELENGTHS)
    if nanometres == WAVELENGTH_GREEN
)


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
        self._sim_wavelength.addItems([label for _nm, label in SIMULATION_WAVELENGTHS] + ["Custom"])
        self._sim_wavelength.setCurrentIndex(DEFAULT_WAVELENGTH_INDEX)
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
        active_system = (
            self._parent._current_assembly
            if self._parent._current_assembly
            else self._parent._current_lens
        )
        if active_system:
            num_rays = int(self._sim_num_rays.value())
            angle = self._sim_angle.value()
            source_height = self._sim_source_height.value()
            show_ghosts = self._ghost_analysis.isChecked()

            # Get wavelength
            wavelength = self._selected_wavelength()

            self._sim_viz.run_simulation(
                active_system, num_rays, angle, source_height, show_ghosts, wavelength
            )

    def _selected_wavelength(self) -> float:
        """Wavelength in nm for the current picker selection.

        Reads the preset value out of :data:`SIMULATION_WAVELENGTHS` rather than
        from a parallel list of numbers, so the value traced is the one the
        entry is labelled with.

        Returns:
            The selected wavelength in nanometers.
        """
        index = self._sim_wavelength.currentIndex()
        if index == CUSTOM_WAVELENGTH_INDEX:
            return float(self._sim_custom_wavelength.value())
        if 0 <= index < len(SIMULATION_WAVELENGTHS):
            return SIMULATION_WAVELENGTHS[index][0]
        return WAVELENGTH_GREEN

    def _on_wavelength_changed(self, index: int) -> None:
        """Show/hide custom wavelength input based on selection.

        Args:
            index: Index of the selected wavelength entry; index 5 selects
                the custom wavelength input.
        """
        is_custom = index == CUSTOM_WAVELENGTH_INDEX
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
        """Re-run the simulation against the parent's current lens/system.

        This was ``pass``. The visualization widget holds a live reference to
        the lens, so after an edit the view drew the *new* lens with rays that
        belonged to the *old* one - and because the rays were never recomputed,
        the two silently disagreed.

        Args:
            None

        Returns:
            None
        """
        self._sim_viz.refresh()
