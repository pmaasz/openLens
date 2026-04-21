"""
OpenLens PySide6 Performance Tab
Optical performance metrics and analysis plots
"""

import math
import logging
import os
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, 
                               QFormLayout, QDoubleSpinBox, QComboBox, 
                               QPushButton, QLabel, QTextEdit, QScrollArea, QMessageBox, QFileDialog)
from PySide6.QtCore import Qt
from src.gui.tabs.base_tab import BaseTab

logger = logging.getLogger(__name__)

class PerformanceTab(BaseTab):
    """Optical performance metrics and analysis plots"""
    
    def _setup_ui(self):
        # Create scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none;")
        
        # Create content widget
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(10, 10, 10, 10)
        
        title = QLabel("Performance Metrics Dashboard")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)
        
        # Metrics display area
        metrics_group = QGroupBox("Optical Performance Metrics")
        metrics_layout = QHBoxLayout(metrics_group)
        
        self._perf_metrics_text = QTextEdit()
        self._perf_metrics_text.setReadOnly(True)
        self._perf_metrics_text.setMinimumWidth(300)
        self._perf_metrics_text.setStyleSheet("background-color: #2b2b2b; color: #e0e0e0; font-family: Courier; font-size: 10px;")
        self._perf_metrics_text.setPlainText("Select a lens and click 'Calculate Metrics' to view performance data.")
        metrics_layout.addWidget(self._perf_metrics_text, 1)
        
        # Add the visualization widget
        from src.gui.widgets import PerformanceVisualizationWidget
        self._perf_viz = PerformanceVisualizationWidget()
        metrics_layout.addWidget(self._perf_viz, 2)
        
        layout.addWidget(metrics_group)
        
        # Calculation parameters
        params_group = QGroupBox("Calculation Parameters")
        params_layout = QFormLayout(params_group)
        
        self._perf_entrance_pupil = QDoubleSpinBox()
        self._perf_entrance_pupil.setRange(1, 100)
        self._perf_entrance_pupil.setValue(10.0)
        self._perf_entrance_pupil.setSuffix(" mm")
        self._perf_entrance_pupil.setFixedWidth(100)
        params_layout.addRow("Entrance Pupil:", self._perf_entrance_pupil)
        
        self._perf_wavelength = QComboBox()
        self._perf_wavelength.addItems(["400 nm (Violet)", "450 nm (Blue)", "550 nm (Green)", "650 nm (Red)", "700 nm (IR)"])
        self._perf_wavelength.setCurrentIndex(2)  # Default to 550nm
        self._perf_wavelength.setFixedWidth(140)
        params_layout.addRow("Wavelength:", self._perf_wavelength)
        
        self._perf_object_distance = QDoubleSpinBox()
        self._perf_object_distance.setRange(1, 10000)
        self._perf_object_distance.setValue(1000)
        self._perf_object_distance.setSuffix(" mm")
        self._perf_object_distance.setFixedWidth(100)
        params_layout.addRow("Object Distance:", self._perf_object_distance)
        
        self._perf_sensor_size = QDoubleSpinBox()
        self._perf_sensor_size.setRange(1, 100)
        self._perf_sensor_size.setValue(36)
        self._perf_sensor_size.setSuffix(" mm")
        self._perf_sensor_size.setFixedWidth(100)
        params_layout.addRow("Sensor Size:", self._perf_sensor_size)
        
        layout.addWidget(params_group)
        
        # Buttons - Row 1: Geometric Analysis
        btn_layout1 = QHBoxLayout()
        calc_btn = QPushButton("Calculate Metrics")
        calc_btn.clicked.connect(self._on_calculate_performance_metrics)
        spot_btn = QPushButton("Spot Diagram")
        spot_btn.clicked.connect(self._on_show_spot_diagram)
        ray_fan_btn = QPushButton("Ray Fan")
        ray_fan_btn.clicked.connect(self._on_show_ray_fan)
        field_btn = QPushButton("Field Curves")
        field_btn.clicked.connect(self._on_show_field_curves)
        ghost_btn = QPushButton("Ghost Analysis")
        ghost_btn.clicked.connect(self._on_show_ghost_analysis)
        
        btn_layout1.addWidget(calc_btn)
        btn_layout1.addWidget(spot_btn)
        btn_layout1.addWidget(ray_fan_btn)
        btn_layout1.addWidget(field_btn)
        btn_layout1.addWidget(ghost_btn)
        layout.addLayout(btn_layout1)
        
        # Buttons - Row 2: Wavefront & Image Quality
        btn_layout2 = QHBoxLayout()
        psf_btn = QPushButton("PSF Analysis")
        psf_btn.clicked.connect(self._on_show_psf)
        mtf_btn = QPushButton("MTF Curve")
        mtf_btn.clicked.connect(self._on_show_mtf)
        wavefront_btn = QPushButton("Wavefront Map")
        wavefront_btn.clicked.connect(self._on_show_wavefront)
        image_sim_btn = QPushButton("Image Simulation")
        image_sim_btn.clicked.connect(self._on_show_image_simulation)
        
        btn_layout2.addWidget(psf_btn)
        btn_layout2.addWidget(mtf_btn)
        btn_layout2.addWidget(wavefront_btn)
        btn_layout2.addWidget(image_sim_btn)
        btn_layout2.addStretch()
        layout.addLayout(btn_layout2)
        
        layout.addStretch()
        
        scroll.setWidget(content)
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(scroll)

    def _on_show_image_simulation(self):
        """Show Image Simulation Dialog with side-by-side view"""
        active_system = self._parent._current_assembly if self._parent._current_assembly else self._parent._current_lens
        if not active_system:
            QMessageBox.warning(self, "No Selection", "Please select a lens or assembly first")
            return
            
        try:
            from src.optical_system import OpticalSystem
            from src.gui.dialogs.image_sim import ImageSimulationDialog
            
            if not isinstance(active_system, OpticalSystem):
                system = OpticalSystem(name=active_system.name)
                system.add_lens(active_system)
            else:
                system = active_system
            
            dialog = ImageSimulationDialog(system, self._parent)
            dialog.exec()
            
        except ImportError as e:
            if 'PIL' in str(e) or 'Pillow' in str(e):
                QMessageBox.warning(self, "Dependency Missing", "Image simulation requires 'Pillow' (PIL).")
            else:
                logger.error(f"Import error in image simulation: {e}")
        except Exception as e:
            logger.error(f"Image simulation error: {e}")
            QMessageBox.critical(self, "Analysis Error", f"Failed to start image simulation: {e}")


    def _on_calculate_performance_metrics(self):
        """Calculate and display performance metrics for the active lens or assembly"""
        active_system = self._parent._current_assembly if self._parent._current_assembly else self._parent._current_lens
        if not active_system:
            self._perf_metrics_text.setPlainText("No system selected.")
            return
        
        try:
            from src.aberrations import AberrationsCalculator
            from src.optical_system import OpticalSystem
            
            # Prepare parameters
            wavelengths = [400, 450, 550, 650, 700]
            wavelength = wavelengths[self._perf_wavelength.currentIndex()]
            entrance_pupil = self._perf_entrance_pupil.value()
            object_distance = self._perf_object_distance.value()
            sensor_size = self._perf_sensor_size.value()
            
            # Wrap in OpticalSystem if it's just a lens
            if not isinstance(active_system, OpticalSystem):
                system = OpticalSystem(name=active_system.name)
                system.add_lens(active_system)
            else:
                system = active_system

            calculator = AberrationsCalculator(system)
            
            # Get optical properties
            if hasattr(system, 'get_system_focal_length'):
                fl = system.get_system_focal_length()
            else:
                fl = active_system.calculate_focal_length()
                
            power = system.calculate_optical_power() if hasattr(system, 'calculate_optical_power') else active_system.calculate_optical_power()
            bfl = system.calculate_back_focal_length() if hasattr(system, 'calculate_back_focal_length') else active_system.calculate_back_focal_length()
            
            # Calculate field angle derived from sensor size
            field_angle = 0.0
            if fl and fl > 0:
                field_angle = math.degrees(math.atan((sensor_size / 2.0) / fl))
            
            results = calculator.calculate_all_aberrations(field_angle=field_angle)
            
            # Calculate chromatic focal shift if it's an assembly
            chromatic_text = ""
            if isinstance(active_system, OpticalSystem):
                chromatic = active_system.calculate_chromatic_aberration()
                if chromatic and chromatic.get('longitudinal') is not None:
                    chromatic_text = f"Chromatic Focal Shift (C-F): {chromatic['longitudinal']:.4f} mm\n"
                    if chromatic.get('bfl_d') is not None:
                        bfl_F = chromatic.get('bfl_F')
                        chromatic_text += f"  BFL (F=486nm): {f'{bfl_F:.3f}' if bfl_F is not None else 'N/A'} mm\n"
                        bfl_d = chromatic.get('bfl_d')
                        chromatic_text += f"  BFL (d=587nm): {f'{bfl_d:.3f}' if bfl_d is not None else 'N/A'} mm\n"
                        bfl_C = chromatic.get('bfl_C')
                        chromatic_text += f"  BFL (C=656nm): {f'{bfl_C:.3f}' if bfl_C is not None else 'N/A'} mm\n"

            # Build metrics text
            text = f"""=== OPTICAL PERFORMANCE METRICS ===
System: {system.name}
Type: {"Assembly" if isinstance(active_system, OpticalSystem) else "Single Lens"}

--- Basic Optical Properties ---
Focal Length: {f"{fl:.2f} mm" if fl else "Infinite"}
Optical Power: {f"{power:.4f} D" if power else "N/A"}
Back Focal Length: {f"{bfl:.2f} mm" if bfl else "N/A"}
Entrance Pupil: {entrance_pupil:.2f} mm
f-number (f/#): {results.get('f_number', 0):.2f}
{chromatic_text}
--- Calculation Parameters ---
Wavelength: {wavelength} nm
Object Distance: {object_distance} mm
Max Field Angle: {field_angle:.2f} deg (derived from {sensor_size}mm sensor)

--- Primary Aberrations ---
Spherical Aberration: {results.get('spherical', 0):.4f} mm (longitudinal)
Coma: {results.get('coma', 0):.4f} mm (transverse)
Astigmatism: {results.get('astigmatism', 0):.4f} mm
Distortion: {results.get('distortion', 0):.2f} %
Chromatic Aberration: {results.get('chromatic', 0):.4f} mm

--- Image Quality Metrics ---
MTF Cutoff: {results.get('mtf_cutoff', 0):.1f} lp/mm
Strehl Ratio: {results.get('strehl', 0):.3f}
Spot Size (RMS): {results.get('spot_rms', 0):.3f} µm
Airy Disk (Dia): {results.get('airy_disk_diameter', 0)*1000:.2f} µm
"""
            self._perf_metrics_text.setPlainText(text)
            
            # Update visualization widget
            if hasattr(self, '_perf_viz'):
                self._perf_viz.update_lens(active_system)
                self._perf_viz.update_metrics(results)
                
            self._parent._update_status(f"Calculated metrics for {system.name}")
                
        except Exception as e:
            logger.error(f"Performance calculation error: {e}")
            self._perf_metrics_text.setPlainText(f"Error calculating metrics: {e}")

    def _on_show_spot_diagram(self):
        """Show spot diagram using ImageQualityAnalyzer for active system"""
        active_system = self._parent._current_assembly if self._parent._current_assembly else self._parent._current_lens
        if not active_system:
            QMessageBox.warning(self, "No Selection", "Please select a lens or assembly first")
            return
            
        try:
            from src.analysis.psf_mtf import ImageQualityAnalyzer
            from src.optical_system import OpticalSystem
            from src.gui.dialogs.analysis_plots import AnalysisPlotDialog
            
            # Wrap in system if needed
            if not isinstance(active_system, OpticalSystem):
                system = OpticalSystem(name=active_system.name)
                system.add_lens(active_system)
            else:
                system = active_system
                
            analyzer = ImageQualityAnalyzer(system)
            
            # Use current parameters from UI
            wavelengths = [400, 450, 550, 650, 700]
            wavelength = wavelengths[self._perf_wavelength.currentIndex()]
            
            # Calculate field angle
            fl = system.get_system_focal_length()
            sensor_size = self._perf_sensor_size.value()
            max_field = 0.0
            if fl and fl > 0:
                max_field = math.degrees(math.atan((sensor_size / 2.0) / fl))
                
            # Perform multi-field spot analysis
            fields = [0, max_field * 0.7, max_field]
            colors = ['#ffffff', '#00ff00', '#ff0000']
            
            dialog = AnalysisPlotDialog(f"Spot Diagram - {system.name}", self._parent)
            ax = dialog.get_axes()
            
            for i, field in enumerate(fields):
                # Request 6 rings for a clear spot without overcrowding (~37 rays)
                spot_data = analyzer.calculate_spot_diagram(field_angle=field, wavelength=wavelength, num_rings=6)
                # Spot points are (y, z) - usually we plot Y vs Z or vice versa
                z_pts = [p[1] * 1000 for p in spot_data] # Sagittal (Z)
                y_pts = [p[0] * 1000 for p in spot_data] # Tangential (Y)
                ax.plot(z_pts, y_pts, '.', color=colors[i], label=f"Field {field:.1f}°", markersize=3, alpha=0.6)
            
            ax.set_aspect('equal')
            ax.set_xlabel("Sagittal (µm)")
            ax.set_ylabel("Tangential (µm)")
            ax.set_title(f"Spot Diagram ({wavelength}nm)")
            ax.legend(fontsize='small')
            ax.grid(True, linestyle='--', alpha=0.3)
            
            dialog.exec()
            
        except Exception as e:
            logger.error(f"Spot diagram error: {e}")
            QMessageBox.critical(self, "Analysis Error", f"Failed to generate spot diagram: {e}")

    def _on_show_ray_fan(self):
        """Show ray fan plot for active system"""
        active_system = self._parent._current_assembly if self._parent._current_assembly else self._parent._current_lens
        if not active_system:
            QMessageBox.warning(self, "No Selection", "Please select a lens or assembly first")
            return
            
        try:
            from src.aberrations import AberrationsCalculator
            from src.optical_system import OpticalSystem
            from src.gui.dialogs.analysis_plots import AnalysisPlotDialog
            
            if not isinstance(active_system, OpticalSystem):
                system = OpticalSystem(name=active_system.name)
                system.add_lens(active_system)
            else:
                system = active_system
                
            calculator = AberrationsCalculator(system)
            
            wavelengths = [400, 450, 550, 650, 700]
            wavelength = wavelengths[self._perf_wavelength.currentIndex()]
            
            dialog = AnalysisPlotDialog(f"Ray Fan - {system.name}", self._parent)
            ax = dialog.get_axes()
            
            # Calculate ray fan (transverse ray aberration vs pupil coordinate)
            # Use 3 fields: 0, 0.7, 1.0
            fl = system.get_system_focal_length()
            sensor_size = self._perf_sensor_size.value()
            max_field = 0.0
            if fl and fl > 0:
                max_field = math.degrees(math.atan((sensor_size / 2.0) / fl))
            
            fields = [0, max_field * 0.7, max_field]
            styles = ['-', '--', ':']
            
            for i, field in enumerate(fields):
                fan_data = calculator.calculate_ray_fan(field_angle=field, wavelength=wavelength)
                pupil_coords = fan_data['pupil_coords']
                aberrations = fan_data['ray_errors']
                ax.plot(pupil_coords, aberrations, styles[i], color='#0078d4', label=f"Field {field:.1f}°")
            
            ax.set_xlabel("Normalized Pupil Coordinate")
            ax.set_ylabel("Transverse Aberration (mm)")
            ax.set_title(f"Ray Fan Plot ({wavelength}nm)")
            ax.legend(fontsize='small')
            ax.grid(True, linestyle='--', alpha=0.3)
            ax.axhline(0, color='white', linewidth=0.5, alpha=0.5)
            ax.axvline(0, color='white', linewidth=0.5, alpha=0.5)
            
            dialog.exec()
            
        except Exception as e:
            logger.error(f"Ray fan error: {e}")
            QMessageBox.critical(self, "Analysis Error", f"Failed to generate ray fan: {e}")

    def _on_show_field_curves(self):
        """Show field curvature and distortion plots"""
        active_system = self._parent._current_assembly if self._parent._current_assembly else self._parent._current_lens
        if not active_system:
            QMessageBox.warning(self, "No Selection", "Please select a lens or assembly first")
            return
            
        try:
            from src.aberrations import AberrationsCalculator
            from src.optical_system import OpticalSystem
            from src.gui.dialogs.analysis_plots import AnalysisPlotDialog
            
            if not isinstance(active_system, OpticalSystem):
                system = OpticalSystem(name=active_system.name)
                system.add_lens(active_system)
            else:
                system = active_system
                
            calculator = AberrationsCalculator(system)
            
            fl = system.get_system_focal_length()
            sensor_size = self._perf_sensor_size.value()
            max_field = 20.0
            if fl and fl > 0:
                max_field = math.degrees(math.atan((sensor_size / 2.0) / fl))
            
            dialog = AnalysisPlotDialog(f"Field Curves & Distortion - {system.name}", self._parent)
            
            # Subplot 1: Field Curvature (Sagittal and Tangential)
            ax1 = dialog.figure.add_subplot(121)
            if self._parent._theme == 'dark':
                ax1.set_facecolor('#1e1e1e')
                ax1.tick_params(colors='#e0e0e0')
                ax1.xaxis.label.set_color('#e0e0e0')
                ax1.yaxis.label.set_color('#e0e0e0')
                ax1.title.set_color('#e0e0e0')
                for spine in ax1.spines.values():
                    spine.set_edgecolor('#3f3f3f')
            
            angles, sag, tan = calculator.calculate_field_curvature(max_field_angle=max_field)
            ax1.plot(sag, angles, 'b-', label='Sagittal')
            ax1.plot(tan, angles, 'r--', label='Tangential')
            ax1.set_ylabel("Field Angle (deg)")
            ax1.set_xlabel("Focus Shift (mm)")
            ax1.set_title("Field Curvature")
            ax1.legend(fontsize='x-small')
            ax1.grid(True, linestyle='--', alpha=0.3)
            
            # Subplot 2: Distortion
            ax2 = dialog.figure.add_subplot(122)
            if self._parent._theme == 'dark':
                ax2.set_facecolor('#1e1e1e')
                ax2.tick_params(colors='#e0e0e0')
                ax2.xaxis.label.set_color('#e0e0e0')
                ax2.yaxis.label.set_color('#e0e0e0')
                ax2.title.set_color('#e0e0e0')
                for spine in ax2.spines.values():
                    spine.set_edgecolor('#3f3f3f')
                    
            angles, dist = calculator.calculate_distortion_curve(max_field_angle=max_field)
            ax2.plot(dist, angles, 'g-')
            ax2.set_ylabel("Field Angle (deg)")
            ax2.set_xlabel("Distortion (%)")
            ax2.set_title("f-theta Distortion")
            ax2.grid(True, linestyle='--', alpha=0.3)
            ax2.axvline(0, color='white', linewidth=0.5, alpha=0.5)
            
            dialog.figure.tight_layout()
            dialog.exec()
            
        except Exception as e:
            logger.error(f"Field curves error: {e}")
            QMessageBox.critical(self, "Analysis Error", f"Failed to generate field curves: {e}")

    def _on_show_psf(self):
        """Show PSF Analysis through parent"""
        self._parent._on_show_psf()

    def _on_show_mtf(self):
        """Show MTF Analysis through parent"""
        self._parent._on_show_mtf()

    def _on_show_wavefront(self):
        """Show Wavefront Analysis through parent"""
        self._parent._on_show_wavefront()

    def _on_show_ghost_analysis(self):
        """Show Ghost Analysis through parent"""
        self._parent._on_show_ghost_analysis()

    def refresh(self):
        """Refresh performance tab state"""
        # Re-calculate metrics if there's an active lens/assembly
        active_system = self._parent._current_assembly if self._parent._current_assembly else self._parent._current_lens
        if active_system:
            self._on_calculate_performance_metrics()
        else:
            self._perf_metrics_text.setPlainText("Select a lens or assembly and click 'Calculate Metrics' to view performance data.")
            if hasattr(self, '_perf_viz'):
                self._perf_viz.update_lens(None)
