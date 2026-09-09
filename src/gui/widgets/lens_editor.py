"""
OpenLens PySide6 Lens Editor Widget
Main editor widget for lens properties with visualization
"""

from typing import Optional, TYPE_CHECKING

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QFormLayout,
    QLabel,
    QDoubleSpinBox,
    QLineEdit,
    QFrame,
    QComboBox,
    QCheckBox,
)
from PySide6.QtCore import Signal

from .lens_viz_container import LensVisualizationWidget
from ...validation import check_physical_feasibility

if TYPE_CHECKING:
    from ...lens import Lens


class LensEditorWidget(QWidget):
    """Lens editor with properties and visualization"""

    # Signal emitted when lens properties change
    lens_updated = Signal()
    # Signal emitted when lens model is modified and needs saving/refreshing
    lens_modified = Signal(object)  # Using object for Lens class to avoid circularity if any

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialize the editor widget and build its UI.

        Args:
            parent: Optional parent widget (usually the main window).
        """
        super().__init__(parent)
        self._lens = None
        self._parent = parent
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the editor layout with the properties panel and visualization."""
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # Left: Properties panel (scrollable)
        from PySide6.QtWidgets import QScrollArea

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")

        props_panel = self._create_properties_panel()
        scroll.setWidget(props_panel)

        main_layout.addWidget(scroll, 1)

        # Right: Visualization
        self._viz_widget = LensVisualizationWidget()
        # Connect interactive signals from the 2D visualization widget
        self._viz_widget._2d_widget.property_changed.connect(self._on_interactive_property_changed)

        main_layout.addWidget(self._viz_widget, 2)

    def _on_interactive_property_changed(self, prop: str, value: float) -> None:
        """Update UI and lens when dragging in 2D view

        Args:
            prop: Name of the changed property ('r1', 'r2', 'thickness' or
                'diameter').
            value: New numeric value for the property.
        """
        if prop == "r1":
            self._r1_input.setValue(value)
        elif prop == "r2":
            self._r2_input.setValue(value)
        elif prop == "thickness":
            self._thickness_input.setValue(value)
        elif prop == "diameter":
            self._diameter_input.setValue(value)

    def _create_properties_panel(self) -> QFrame:
        """Create the properties panel

        Returns:
            The frame containing all editor input groups.
        """
        frame = QFrame()
        frame.setFrameShape(QFrame.StyledPanel)
        layout = QVBoxLayout(frame)

        # Name
        name_group = QGroupBox("Name")
        name_layout = QFormLayout(name_group)
        self._name_input = QLineEdit()
        self._name_input.setStyleSheet("""
            QLineEdit {
                background-color: #2d2d2d;
                color: #e0e0e0;
                border: 1px solid #3f3f3f;
                padding: 5px;
            }
        """)
        name_layout.addRow("Name:", self._name_input)
        self._name_input.textChanged.connect(self._on_name_changed)
        layout.addWidget(name_group)

        # Classification (read-only display)
        class_group = QGroupBox("Classification")
        class_layout = QFormLayout(class_group)
        self._class_type_label = QLabel("Biconvex")
        self._class_type_label.setStyleSheet("color: #4fc3f7; font-weight: bold;")
        class_layout.addRow("Type:", self._class_type_label)
        layout.addWidget(class_group)

        # Dimensions
        dim_group = QGroupBox("Dimensions")
        dim_layout = QFormLayout(dim_group)

        self._r1_input = QDoubleSpinBox()
        self._r1_input.setRange(-10000, 10000)
        self._r1_input.setValue(100)
        self._r1_input.setSuffix(" mm")
        self._r1_input.valueChanged.connect(self._on_property_changed)
        dim_layout.addRow("Radius 1:", self._r1_input)

        self._r2_input = QDoubleSpinBox()
        self._r2_input.setRange(-10000, 10000)
        self._r2_input.setValue(-100)
        self._r2_input.setSuffix(" mm")
        self._r2_input.valueChanged.connect(self._on_property_changed)
        dim_layout.addRow("Radius 2:", self._r2_input)

        self._thickness_input = QDoubleSpinBox()
        self._thickness_input.setRange(0.1, 1000)
        self._thickness_input.setValue(5)
        self._thickness_input.setSuffix(" mm")
        self._thickness_input.valueChanged.connect(self._on_property_changed)
        dim_layout.addRow("Thickness:", self._thickness_input)

        self._diameter_input = QDoubleSpinBox()
        self._diameter_input.setRange(1, 500)
        self._diameter_input.setValue(40)
        self._diameter_input.setSuffix(" mm")
        self._diameter_input.valueChanged.connect(self._on_property_changed)
        dim_layout.addRow("Diameter:", self._diameter_input)

        # Edge lock: keep the rim-wall thickness fixed when radii/diameter
        # change by compensating the center thickness (which is what the
        # "Thickness" spinbox stores). Unchecked = classic behavior where
        # the center stays fixed and the rim wall absorbs the change.
        self._lock_edge_check = QCheckBox("Lock edge thickness")
        self._lock_edge_check.setChecked(True)
        self._lock_edge_check.setToolTip(
            "When locked, editing radii or diameter adjusts center thickness "
            "so the rim (edge) thickness stays constant."
        )
        dim_layout.addRow(self._lock_edge_check)

        layout.addWidget(dim_group)

        # Parabolic surfaces – sag at clear aperture (vertex to rim)
        para_group = QGroupBox("Parabolic Surfaces (sag at D/2)")
        para_layout = QFormLayout(para_group)

        self._para1_check = QCheckBox("Parabolic Surface 1")
        self._para1_check.stateChanged.connect(self._on_parabolic_changed)
        para_layout.addRow(self._para1_check)

        self._para1_sag_input = QDoubleSpinBox()
        self._para1_sag_input.setRange(-100, 100)
        self._para1_sag_input.setValue(3.0)
        self._para1_sag_input.setSuffix(" mm")
        self._para1_sag_input.setDecimals(3)
        self._para1_sag_input.setSingleStep(0.1)
        self._para1_sag_input.valueChanged.connect(self._on_parabolic_changed)
        self._para1_sag_input.setEnabled(False)
        para_layout.addRow("Sag 1 (peak→rim):", self._para1_sag_input)

        self._para2_check = QCheckBox("Parabolic Surface 2")
        self._para2_check.stateChanged.connect(self._on_parabolic_changed)
        para_layout.addRow(self._para2_check)

        self._para2_sag_input = QDoubleSpinBox()
        self._para2_sag_input.setRange(-100, 100)
        self._para2_sag_input.setValue(-3.0)
        self._para2_sag_input.setSuffix(" mm")
        self._para2_sag_input.setDecimals(3)
        self._para2_sag_input.setSingleStep(0.1)
        self._para2_sag_input.valueChanged.connect(self._on_parabolic_changed)
        self._para2_sag_input.setEnabled(False)
        para_layout.addRow("Sag 2 (peak→rim):", self._para2_sag_input)

        layout.addWidget(para_group)

        # Material
        mat_group = QGroupBox("Material")
        mat_layout = QFormLayout(mat_group)

        materials = ["BK7", "SF11", "F2", "N-BK7", "Fused Silica", "Custom"]
        self._material_combo = QComboBox()
        self._material_combo.addItems(materials)
        self._material_combo.setCurrentText("BK7")
        self._material_combo.currentTextChanged.connect(self._on_material_changed)
        mat_layout.addRow("Material:", self._material_combo)

        self._n_input = QDoubleSpinBox()
        self._n_input.setRange(1.0, 3.0)
        self._n_input.setValue(1.5168)
        self._n_input.setDecimals(4)
        self._n_input.setReadOnly(True)
        self._n_input.setStyleSheet("QSpinBox: { background: #2d2d2d; color: #888; }")
        mat_layout.addRow("Refractive Index:", self._n_input)

        layout.addWidget(mat_group)

        # Fresnel lens
        fresnel_box = QGroupBox("Fresnel Lens")
        fresnel_layout = QFormLayout(fresnel_box)

        self._fresnel_check = QCheckBox()
        self._fresnel_check.setText("Enable")
        self._fresnel_check.stateChanged.connect(self._on_fresnel_changed)
        fresnel_layout.addRow("Fresnel:", self._fresnel_check)

        self._groove_pitch_label = QLabel("Groove Pitch:")
        self._groove_pitch_label.setStyleSheet("color: #aaa;")
        self._groove_pitch_input = QDoubleSpinBox()
        self._groove_pitch_input.setRange(0.01, 10)
        self._groove_pitch_input.setValue(0.5)
        self._groove_pitch_input.setSuffix(" mm")
        self._groove_pitch_input.valueChanged.connect(self._on_groove_pitch_changed)
        self._groove_pitch_input.hide()
        self._groove_pitch_label.hide()
        fresnel_layout.addRow(self._groove_pitch_label, self._groove_pitch_input)

        self._num_grooves_label = QLabel("Number of Grooves:")
        self._num_grooves_label.setStyleSheet("color: #aaa;")
        self._num_grooves_value = QLabel("0")
        self._num_grooves_value.hide()
        self._num_grooves_label.hide()
        fresnel_layout.addRow(self._num_grooves_label, self._num_grooves_value)

        self._fresnel_group = fresnel_box
        layout.addWidget(fresnel_box)

        # Calculated
        calc_group = QGroupBox("Calculated Properties")
        calc_layout = QFormLayout(calc_group)

        self._focal_label = QLabel("--")
        calc_layout.addRow("Focal Length:", self._focal_label)

        self._power_label = QLabel("--")
        calc_layout.addRow("Power:", self._power_label)

        self._bfl_label = QLabel("--")
        calc_layout.addRow("Back Focal Length:", self._bfl_label)

        self._ffl_label = QLabel("--")
        calc_layout.addRow("Front Focal Length:", self._ffl_label)

        self._edge_label = QLabel("--")
        calc_layout.addRow("Edge Thickness:", self._edge_label)

        self._feas_warning_label = QLabel("")
        self._feas_warning_label.setWordWrap(True)
        self._feas_warning_label.setStyleSheet("color: #ff6b6b; font-weight: bold;")
        self._feas_warning_label.hide()
        calc_layout.addRow("Feasibility:", self._feas_warning_label)

        layout.addWidget(calc_group)

        layout.addStretch()

        return frame

    def _on_name_changed(self, name: str) -> None:
        """Handle name change"""
        if self._lens:
            self._lens.name = name
            self.lens_modified.emit(self._lens)

    def _on_parabolic_changed(self) -> None:
        """Handle parabolic checkbox / sag changes."""
        is_p1 = self._para1_check.isChecked()
        is_p2 = self._para2_check.isChecked()
        self._para1_sag_input.setEnabled(is_p1)
        self._para2_sag_input.setEnabled(is_p2)
        # Disable radius when parabolic (spherical not used)
        self._r1_input.setEnabled(not is_p1)
        self._r2_input.setEnabled(not is_p2)
        if self._lens:
            self._lens.is_parabolic_1 = is_p1
            self._lens.parabolic_sag_1 = self._para1_sag_input.value()
            self._lens.is_parabolic_2 = is_p2
            self._lens.parabolic_sag_2 = self._para2_sag_input.value()
            self._update_calculated()
            self._viz_widget.update_lens(self._lens)
            self.lens_modified.emit(self._lens)
            self.lens_updated.emit()

    def _on_property_changed(self) -> None:
        """Handle property changes with auto-save"""
        if self._lens:
            if self._lock_edge_check.isChecked() and self.sender() in (
                self._r1_input,
                self._r2_input,
                self._diameter_input,
            ):
                self._apply_geometry_preserving_edge(
                    self._r1_input.value(),
                    self._r2_input.value(),
                    self._diameter_input.value(),
                )
            else:
                self._lens.radius_of_curvature_1 = self._r1_input.value()
                self._lens.radius_of_curvature_2 = self._r2_input.value()
                self._lens.thickness = self._thickness_input.value()
                self._lens.diameter = self._diameter_input.value()
            self._lens.refractive_index = self._n_input.value()
            # Sync parabolic sag diameters if needed (sag stays as absolute distance)
            self._update_calculated()
            self._viz_widget.update_lens(self._lens)

            self._class_type_label.setText(self._lens.classify_lens_type())

            self.lens_modified.emit(self._lens)
            self.lens_updated.emit()

    def _apply_geometry_preserving_edge(
        self, radius_1: float, radius_2: float, diameter: float
    ) -> None:
        """Apply radii/diameter while preserving the current edge thickness.

        Thickness stores the CENTER thickness, so steepening a surface would
        otherwise thin the rim wall. With the edge lock on, the center
        thickness compensates instead (edge(t) = t - sag1 + sag2, hence
        t_new = edge_old + t_old - edge_new_at_old_t). Already-infeasible
        or undefined geometry is applied as-is so the warning can show.
        """
        lens = self._lens
        try:
            old_edge = lens.calculate_edge_thickness()
        except Exception:
            old_edge = None
        lens.radius_of_curvature_1 = radius_1
        lens.radius_of_curvature_2 = radius_2
        lens.diameter = diameter
        if old_edge is None or old_edge <= 0:
            return
        try:
            new_edge_at_old_t = lens.calculate_edge_thickness()
        except Exception:
            new_edge_at_old_t = None
        if new_edge_at_old_t is None:
            return
        t_new = lens.thickness + (old_edge - new_edge_at_old_t)
        t_new = max(0.1, min(1000.0, t_new))
        lens.thickness = t_new
        self._thickness_input.blockSignals(True)
        self._thickness_input.setValue(t_new)
        self._thickness_input.blockSignals(False)

    def _on_material_changed(self, material: str) -> None:
        """Handle material change"""
        material_indices = {
            "BK7": 1.5168,
            "SF11": 1.7847,
            "F2": 1.6200,
            "N-BK7": 1.5168,
            "Fused Silica": 1.4580,
            "Custom": 1.5,
        }
        self._n_input.setValue(material_indices.get(material, 1.5))
        if self._lens:
            self._lens.refractive_index = self._n_input.value()
            self._lens.material = material
            self._update_calculated()
            if self._viz_widget:
                self._viz_widget.update_lens(self._lens)
            self.lens_modified.emit(self._lens)
            self.lens_updated.emit()

    def _on_fresnel_changed(self, state: int) -> None:
        """Handle Fresnel checkbox change"""
        enabled = state == 2

        if enabled:
            self._groove_pitch_input.show()
            self._groove_pitch_label.show()
            self._num_grooves_value.show()
            self._num_grooves_label.show()
        else:
            self._groove_pitch_input.hide()
            self._groove_pitch_label.hide()
            self._num_grooves_value.hide()
            self._num_grooves_label.hide()

        if enabled and self._lens:
            self._lens.is_fresnel = True
            self._lens.groove_pitch = self._groove_pitch_input.value()
            self._update_groove_count()
            self.lens_modified.emit(self._lens)
            self.lens_updated.emit()
        elif self._lens:
            self._lens.is_fresnel = False
            self._num_grooves_value.setText("0")
            self.lens_modified.emit(self._lens)
            self.lens_updated.emit()

    def _on_groove_pitch_changed(self, value):
        """Handle groove pitch change"""
        if self._lens and getattr(self._lens, "is_fresnel", False):
            self._lens.groove_pitch = value
            self._update_groove_count()
            self.lens_modified.emit(self._lens)
            self.lens_updated.emit()

    def _update_groove_count(self):
        """Calculate number of grooves"""
        if not self._lens or not hasattr(self._lens, "is_fresnel") or not self._lens.is_fresnel:
            return
        pitch = self._groove_pitch_input.value()
        diameter = self._lens.diameter
        if pitch > 0:
            grooves = int(diameter / (2 * pitch))
            self._num_grooves_value.setText(str(grooves))

    def _update_calculated(self) -> None:
        """Update calculated properties"""
        if not self._lens:
            return

        n = self._lens.refractive_index
        # Use effective radius for parabolic surfaces
        if hasattr(self._lens, "get_effective_radius_1"):
            r1 = self._lens.get_effective_radius_1()
            r2 = self._lens.get_effective_radius_2()
        else:
            r1 = self._lens.radius_of_curvature_1
            r2 = self._lens.radius_of_curvature_2
        t = self._lens.thickness

        if r1 == 0:
            r1 = float("inf")
        if r2 == 0:
            r2 = float("inf")

        power1 = (n - 1) / r1 if r1 != float("inf") else 0
        power2 = -(n - 1) / r2 if r2 != float("inf") else 0

        if r1 != float("inf") and r2 != float("inf") and r1 * r2 != 0:
            power_spacing = (n - 1) ** 2 * t / (n * r1 * r2)
        else:
            power_spacing = 0

        total_power = power1 + power2 + power_spacing

        if abs(total_power) > 1e-10:
            f = 1.0 / total_power
            self._focal_label.setText(f"{f:.2f} mm")
            self._power_label.setText(f"{1000/f:.2f} D")

            # BFL and FFL – use effective radii
            try:
                bfl = self._lens.calculate_back_focal_length()
                ffl = self._lens.calculate_front_focal_length()
                self._bfl_label.setText(f"{bfl:.2f} mm" if abs(bfl) != float("inf") else "--")
                self._ffl_label.setText(f"{ffl:.2f} mm" if abs(ffl) != float("inf") else "--")
            except Exception:
                self._bfl_label.setText("--")
                self._ffl_label.setText("--")
        else:
            self._focal_label.setText("--")
            self._power_label.setText("--")
            self._bfl_label.setText("--")
            self._ffl_label.setText("--")

        self._update_feasibility()

    def _update_feasibility(self) -> None:
        """Show edge thickness and warn about unrealizable geometry.

        Thickness is the CENTER (vertex to vertex) thickness; the derived
        rim thickness must stay positive or the surfaces intersect within
        the clear aperture (as drawn in the 2D view).
        """
        if not self._lens:
            return

        try:
            edge = self._lens.calculate_edge_thickness()
        except Exception:
            edge = None

        if edge is None:
            self._edge_label.setText("--")
        else:
            self._edge_label.setText(f"{edge:.2f} mm")

        message = None
        if edge is None or edge <= 0:
            if edge is None:
                message = (
                    "Geometry undefined at the rim: aperture overhangs a surface. "
                    "Reduce diameter or flatten radii."
                )
            else:
                message = (
                    f"Surfaces intersect within the clear aperture (edge {edge:.2f} mm). "
                    "Increase thickness, reduce diameter, or flatten radii."
                )
        elif not bool(
            getattr(self._lens, "is_parabolic_1", False)
            or getattr(self._lens, "is_parabolic_2", False)
        ):
            feasible, soft_msg = check_physical_feasibility(
                self._lens.radius_of_curvature_1,
                self._lens.radius_of_curvature_2,
                self._lens.thickness,
                self._lens.diameter,
            )
            if not feasible:
                message = soft_msg

        if message:
            self._feas_warning_label.setText("\u26a0 " + message)
            self._feas_warning_label.show()
        else:
            self._feas_warning_label.hide()

    def load_lens(self, lens: "Lens") -> None:
        """Load a lens into the editor

        Args:
            lens: The lens model to display and edit.
        """
        self._lens = lens
        self._name_input.blockSignals(True)
        self._name_input.setText(lens.name)
        self._name_input.blockSignals(False)
        # Block dimension-spinbox signals while loading: each valueChanged
        # slot rewrites the whole model from the spinboxes, so letting them
        # fire here would clobber not-yet-loaded fields with stale values.
        dim_inputs = (
            self._r1_input,
            self._r2_input,
            self._thickness_input,
            self._diameter_input,
        )
        for spin in dim_inputs:
            spin.blockSignals(True)
        self._r1_input.setValue(lens.radius_of_curvature_1)
        self._r2_input.setValue(lens.radius_of_curvature_2)
        self._thickness_input.setValue(lens.thickness)
        self._diameter_input.setValue(lens.diameter)
        for spin in dim_inputs:
            spin.blockSignals(False)
        self._n_input.setValue(lens.refractive_index)
        # Parabolic
        is_p1 = bool(getattr(lens, "is_parabolic_1", False))
        is_p2 = bool(getattr(lens, "is_parabolic_2", False))
        self._para1_check.blockSignals(True)
        self._para1_check.setChecked(is_p1)
        self._para1_check.blockSignals(False)
        self._para1_sag_input.blockSignals(True)
        self._para1_sag_input.setValue(float(getattr(lens, "parabolic_sag_1", 0.0)))
        self._para1_sag_input.blockSignals(False)
        self._para2_check.blockSignals(True)
        self._para2_check.setChecked(is_p2)
        self._para2_check.blockSignals(False)
        self._para2_sag_input.blockSignals(True)
        self._para2_sag_input.setValue(float(getattr(lens, "parabolic_sag_2", 0.0)))
        self._para2_sag_input.blockSignals(False)
        self._para1_sag_input.setEnabled(is_p1)
        self._para2_sag_input.setEnabled(is_p2)
        self._r1_input.setEnabled(not is_p1)
        self._r2_input.setEnabled(not is_p2)
        self._update_calculated()
        self._viz_widget.update_lens(lens)
        self._class_type_label.setText(lens.classify_lens_type())
