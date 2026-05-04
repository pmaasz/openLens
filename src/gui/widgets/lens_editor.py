"""
OpenLens PySide6 Lens Editor Widget
Main editor widget for lens properties with visualization
"""

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout, 
                               QLabel, QDoubleSpinBox, QLineEdit, QFrame, QComboBox, QCheckBox)
from PySide6.QtCore import Signal

from .lens_viz_container import LensVisualizationWidget


class LensEditorWidget(QWidget):
    """Lens editor with properties and visualization"""
    
    # Signal emitted when lens properties change
    lens_updated = Signal()
    # Signal emitted when lens model is modified and needs saving/refreshing
    lens_modified = Signal(object) # Using object for Lens class to avoid circularity if any
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._lens = None
        self._parent = parent
        self._setup_ui()
    
    def _setup_ui(self):
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

    def _on_interactive_property_changed(self, prop, value):
        """Update UI and lens when dragging in 2D view"""
        if prop == 'r1':
            self._r1_input.setValue(value)
        elif prop == 'r2':
            self._r2_input.setValue(value)
        elif prop == 'thickness':
            self._thickness_input.setValue(value)
        elif prop == 'diameter':
            self._diameter_input.setValue(value)
    
    def _create_properties_panel(self):
        """Create the properties panel"""
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
        self._diameter_input.setValue(50)
        self._diameter_input.setSuffix(" mm")
        self._diameter_input.valueChanged.connect(self._on_property_changed)
        dim_layout.addRow("Diameter:", self._diameter_input)
        
        layout.addWidget(dim_group)
        
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
        
        layout.addWidget(calc_group)
        
        layout.addStretch()
        
        return frame
    
    def _on_name_changed(self, name):
        """Handle name change"""
        if self._lens:
            self._lens.name = name
            self.lens_modified.emit(self._lens)

    def _on_property_changed(self):
        """Handle property changes with auto-save"""
        if self._lens:
            self._lens.radius_of_curvature_1 = self._r1_input.value()
            self._lens.radius_of_curvature_2 = self._r2_input.value()
            self._lens.thickness = self._thickness_input.value()
            self._lens.diameter = self._diameter_input.value()
            self._lens.refractive_index = self._n_input.value()
            self._update_calculated()
            self._viz_widget.update_lens(self._lens)
            
            self._class_type_label.setText(self._lens.classify_lens_type())
            
            self.lens_modified.emit(self._lens)
            self.lens_updated.emit()
    
    def _on_material_changed(self, material):
        """Handle material change"""
        material_indices = {
            "BK7": 1.5168,
            "SF11": 1.7847,
            "F2": 1.6200,
            "N-BK7": 1.5168,
            "Fused Silica": 1.4580,
            "Custom": 1.5
        }
        self._n_input.setValue(material_indices.get(material, 1.5))
        if self._lens:
            self._lens.refractive_index = self._n_input.value()
            self._update_calculated()
            if self._viz_widget:
                self._viz_widget.update_lens(self._lens)
    
    def _on_fresnel_changed(self, state):
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
            self._update_groove_count()
        elif self._lens:
            self._lens.is_fresnel = False
            self._num_grooves_value.setText("0")
    
    def _update_groove_count(self):
        """Calculate number of grooves"""
        if not self._lens or not hasattr(self._lens, 'is_fresnel') or not self._lens.is_fresnel:
            return
        pitch = self._groove_pitch_input.value()
        diameter = self._lens.diameter
        if pitch > 0:
            grooves = int(diameter / (2 * pitch))
            self._num_grooves_value.setText(str(grooves))
    
    def _update_calculated(self):
        """Update calculated properties"""
        if not self._lens:
            return
        
        n = self._lens.refractive_index
        r1 = self._lens.radius_of_curvature_1
        r2 = self._lens.radius_of_curvature_2
        t = self._lens.thickness
        
        if r1 == 0:
            r1 = float('inf')
        if r2 == 0:
            r2 = float('inf')
        
        power1 = (n - 1) / r1 if r1 != float('inf') else 0
        power2 = -(n - 1) / r2 if r2 != float('inf') else 0
        
        if r1 != float('inf') and r2 != float('inf') and r1 * r2 != 0:
            power_spacing = (n - 1)**2 * t / (n * r1 * r2)
        else:
            power_spacing = 0
        
        total_power = power1 + power2 + power_spacing
        
        if abs(total_power) > 1e-10:
            f = 1.0 / total_power
            self._focal_label.setText(f"{f:.2f} mm")
            self._power_label.setText(f"{1000/f:.2f} D")
            
            # BFL and FFL
            bfl = f - t * (n - 1) / n
            ffl = f - t * (n - 1)
            self._bfl_label.setText(f"{bfl:.2f} mm")
            self._ffl_label.setText(f"{ffl:.2f} mm")
        else:
            self._focal_label.setText("--")
            self._power_label.setText("--")
            self._bfl_label.setText("--")
            self._ffl_label.setText("--")

    def load_lens(self, lens):
        """Load a lens into the editor"""
        self._lens = lens
        self._name_input.blockSignals(True)
        self._name_input.setText(lens.name)
        self._name_input.blockSignals(False)
        self._r1_input.setValue(lens.radius_of_curvature_1)
        self._r2_input.setValue(lens.radius_of_curvature_2)
        self._thickness_input.setValue(lens.thickness)
        self._diameter_input.setValue(lens.diameter)
        self._n_input.setValue(lens.refractive_index)
        self._update_calculated()
        self._viz_widget.update_lens(lens)
        self._class_type_label.setText(lens.classify_lens_type())