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
    QListWidget,
    QListWidgetItem,
)
from PySide6.QtCore import Qt

from .base_tab import BaseTab
from ..widgets.simulation_viz import SimulationVisualizationWidget
from ...analysis.environmental import EnvironmentalAnalyzer
from ...constants import (
    ABSOLUTE_ZERO_C,
    DEFAULT_TEMPERATURE,
    WAVELENGTH_GREEN,
    WAVELENGTH_PRESETS,
)

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

#: Seven samples across the visible range, used by the white-light option.
#: A continuous spectrum would be prettier but would turn each ray fan into
#: hundreds of nearly coincident lines; seven spectral colours already blend
#: into white and show the chromatic spread.
WHITE_LIGHT_WAVELENGTHS = tuple(float(nm) for nm in range(400, 701, 50))

#: Preset wavelength selected by default: the photopic peak, which is also the
#: application's default for ray-tracing visualization.
DEFAULT_WAVELENGTH_INDEX = next(
    index
    for index, (nanometres, _label) in enumerate(SIMULATION_WAVELENGTHS)
    if nanometres == WAVELENGTH_GREEN
)


def _wavelength_label(nanometres: float) -> str:
    """Return the picker/list label for a wavelength."""
    for value, label in SIMULATION_WAVELENGTHS:
        if abs(value - nanometres) < 1e-9:
            return label
    return f"{nanometres:g} nm (Custom)"


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

        # Environment: applied to a temporary copy for each run, so the stored
        # lens/assembly keeps its nominal 20 °C geometry and index.
        environment_group = QGroupBox("Environment")
        environment_layout = QFormLayout(environment_group)
        self._sim_temperature = QDoubleSpinBox()
        self._sim_temperature.setRange(ABSOLUTE_ZERO_C, 200.0)
        self._sim_temperature.setDecimals(2)
        self._sim_temperature.setSingleStep(5.0)
        self._sim_temperature.setValue(DEFAULT_TEMPERATURE)
        self._sim_temperature.setSuffix(" °C")
        self._sim_temperature.setToolTip(
            f"Operating temperature in Celsius. The lower limit is 0 K "
            f"({ABSOLUTE_ZERO_C:g} °C)."
        )
        environment_layout.addRow("Temperature:", self._sim_temperature)
        controls_layout.addWidget(environment_group)

        # Selected wavelengths: the picker above chooses one, Add appends it
        # here, and the simulation traces every entry.
        wavelength_group = QGroupBox("Wavelengths")
        wavelength_layout = QVBoxLayout(wavelength_group)

        self._sim_wavelengths = QListWidget()
        self._sim_wavelengths.setMaximumHeight(110)
        self._sim_wavelengths.setToolTip("Wavelengths traced on the next run")
        wavelength_layout.addWidget(self._sim_wavelengths)

        wavelength_buttons = QHBoxLayout()
        self._sim_add_wavelength = QPushButton("Add")
        self._sim_add_wavelength.setToolTip("Add the wavelength selected above")
        self._sim_add_wavelength.clicked.connect(self._add_wavelength)
        self._sim_remove_wavelength = QPushButton("Remove")
        self._sim_remove_wavelength.setToolTip("Remove the selected wavelength")
        self._sim_remove_wavelength.clicked.connect(self._remove_wavelength)
        wavelength_buttons.addWidget(self._sim_add_wavelength)
        wavelength_buttons.addWidget(self._sim_remove_wavelength)
        wavelength_layout.addLayout(wavelength_buttons)

        self._sim_white_light = QCheckBox("White light (400-700 nm)")
        self._sim_white_light.setToolTip("Trace a seven-point visible spectrum instead of the list")
        self._sim_white_light.toggled.connect(self._on_white_light_toggled)
        wavelength_layout.addWidget(self._sim_white_light)

        self._add_wavelength_item(WAVELENGTH_GREEN)

        controls_layout.addWidget(wavelength_group)

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
        active_system = self._active_target()
        if active_system:
            num_rays = int(self._sim_num_rays.value())
            angle = self._sim_angle.value()
            source_height = self._sim_source_height.value()
            show_ghosts = self._ghost_analysis.isChecked()

            # The live model goes to the widget, and the environment is
            # applied at trace time. Handing over a conditioned copy instead
            # left the widget with a snapshot: every later edit of the lens
            # was silently discarded, because the refresh re-traced that
            # snapshot.
            def _conditioned(target):
                return EnvironmentalAnalyzer.condition_at_temperature(
                    target, self._sim_temperature.value()
                )

            self._sim_viz.run_simulation(
                active_system,
                num_rays,
                angle,
                source_height,
                show_ghosts,
                wavelengths=self._selected_wavelengths(),
                conditioner=_conditioned,
            )

    def _add_wavelength_item(self, nanometres: float) -> QListWidgetItem:
        """Append one wavelength entry to the list.

        Args:
            nanometres: Wavelength in nanometers.

        Returns:
            The inserted list item.
        """
        item = QListWidgetItem(_wavelength_label(nanometres))
        item.setData(Qt.ItemDataRole.UserRole, float(nanometres))
        self._sim_wavelengths.addItem(item)
        return item

    def _listed_wavelengths(self) -> list[float]:
        """Return the wavelengths currently listed, in display order."""
        return [
            float(self._sim_wavelengths.item(row).data(Qt.ItemDataRole.UserRole))
            for row in range(self._sim_wavelengths.count())
        ]

    def _add_wavelength(self) -> None:
        """Add the wavelength picked above to the traced list."""
        value = self._selected_wavelength()
        if any(abs(existing - value) < 1e-6 for existing in self._listed_wavelengths()):
            return
        item = self._add_wavelength_item(value)
        self._sim_wavelengths.setCurrentItem(item)

    def _remove_wavelength(self) -> None:
        """Remove the selected wavelength from the traced list."""
        row = self._sim_wavelengths.currentRow()
        if row >= 0:
            self._sim_wavelengths.takeItem(row)

    def _selected_wavelengths(self) -> list[float]:
        """Wavelengths to trace for the current controls.

        White light replaces the list with a fixed visible spectrum. An empty
        list falls back to the picker so Run Simulation always has a target.

        Returns:
            Sorted, unique wavelengths in nanometers.
        """
        if self._sim_white_light.isChecked():
            return list(WHITE_LIGHT_WAVELENGTHS)
        values = sorted(set(self._listed_wavelengths()))
        return values or [self._selected_wavelength()]

    def _on_white_light_toggled(self, checked: bool) -> None:
        """Swap between the wavelength list and the white-light spectrum."""
        for widget in (
            self._sim_wavelength,
            self._sim_wavelengths,
            self._sim_add_wavelength,
            self._sim_remove_wavelength,
        ):
            widget.setEnabled(not checked)
        self._sim_custom_wavelength.setEnabled(not checked)
        if checked:
            self._sim_custom_label.setVisible(False)
            self._sim_custom_wavelength.setVisible(False)
        else:
            self._on_wavelength_changed(self._sim_wavelength.currentIndex())

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
