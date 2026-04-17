"""
Modern Performance Tab for OpenLens using PySide6.
Provides aberration metrics, MTF/PSF analysis, and image simulation for optical systems.
"""

import logging
import math
from typing import Optional, List, Dict, Any, TYPE_CHECKING, Union

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                               QGroupBox, QFormLayout, QDoubleSpinBox, 
                               QSpinBox, QComboBox, QPushButton, QTextEdit, 
                               QScrollArea, QFrame, QSplitter)
from PySide6.QtCore import Qt, Signal, Slot

# Optional: Matplotlib for embedded plots if needed in the future
try:
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

try:
    from ..aberrations import AberrationsCalculator
    from ..optical_system import OpticalSystem
    from ..lens import Lens
    from ..analysis.psf_mtf import ImageQualityAnalyzer
    from ..analysis.spot_diagram import SpotDiagram
    from ..analysis.geometric import GeometricTraceAnalysis
    from ..analysis.ghost import GhostAnalyzer
except ImportError:
    from src.aberrations import AberrationsCalculator
    from src.optical_system import OpticalSystem
    from src.lens import Lens
    from src.analysis.psf_mtf import ImageQualityAnalyzer
    from src.analysis.spot_diagram import SpotDiagram
    from src.analysis.geometric import GeometricTraceAnalysis
    from src.analysis.ghost import GhostAnalyzer

logger = logging.getLogger(__name__)

class PerformanceTab(QWidget):
    """
    Performance tab providing analysis tools for the current optical system.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.current_system: Optional[OpticalSystem] = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Splitter for Metrics (Top) and Controls (Bottom)
        self.splitter = QSplitter(Qt.Vertical)
        
        # 1. Metrics Display Area (Scrollable)
        self.metrics_container = QGroupBox("Optical Performance Metrics")
        metrics_layout = QVBoxLayout(self.metrics_container)
        
        self.metrics_text = QTextEdit()
        self.metrics_text.setReadOnly(True)
        self.metrics_text.setPlaceholderText("Select a system and click 'Calculate Metrics'...")
        self.metrics_text.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #e0e0e0;
                font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
                font-size: 11px;
                border: 1px solid #3f3f3f;
            }
        """)
        metrics_layout.addWidget(self.metrics_text)
        
        self.splitter.addWidget(self.metrics_container)
        
        # 2. Controls Area
        controls_widget = QWidget()
        controls_layout = QVBoxLayout(controls_widget)
        
        params_group = QGroupBox("Analysis Parameters")
        params_form = QFormLayout(params_group)
        
        self.entrance_pupil = QDoubleSpinBox()
        self.entrance_pupil.setRange(0.1, 1000.0)
        self.entrance_pupil.setValue(10.0)
        self.entrance_pupil.setSuffix(" mm")
        params_form.addRow("Entrance Pupil:", self.entrance_pupil)
        
        self.wavelength = QComboBox()
        self.wavelength.addItems([
            "550 nm (Green - Photopic Peak)",
            "587.6 nm (He d-line)",
            "656.3 nm (H-alpha C-line)",
            "486.1 nm (H-beta F-line)",
            "435.8 nm (Hg g-line)"
        ])
        params_form.addRow("Primary Wavelength:", self.wavelength)
        
        self.field_angle = QDoubleSpinBox()
        self.field_angle.setRange(0.0, 90.0)
        self.field_angle.setValue(0.0)
        self.field_angle.setSuffix(" deg")
        params_form.addRow("Field Angle:", self.field_angle)
        
        # Connect parameters to auto-recalculate metrics
        self.entrance_pupil.valueChanged.connect(self.calculate_metrics)
        self.wavelength.currentIndexChanged.connect(self.calculate_metrics)
        self.field_angle.valueChanged.connect(self.calculate_metrics)
        
        controls_layout.addWidget(params_group)
        
        # Analysis Buttons
        buttons_grid = QWidget()
        grid_layout = QVBoxLayout(buttons_grid)
        
        row1 = QHBoxLayout()
        self.btn_calc = QPushButton("Calculate Metrics")
        self.btn_calc.clicked.connect(self.calculate_metrics)
        self.btn_spot = QPushButton("Spot Diagram")
        self.btn_spot.clicked.connect(self.show_spot_diagram)
        self.btn_rayfan = QPushButton("Ray Fan")
        self.btn_rayfan.clicked.connect(self.show_ray_fan)
        row1.addWidget(self.btn_calc)
        row1.addWidget(self.btn_spot)
        row1.addWidget(self.btn_rayfan)
        grid_layout.addLayout(row1)
        
        row2 = QHBoxLayout()
        self.btn_mtf = QPushButton("MTF Analysis")
        self.btn_mtf.clicked.connect(self.show_mtf)
        self.btn_psf = QPushButton("PSF Analysis")
        self.btn_psf.clicked.connect(self.show_psf)
        self.btn_field = QPushButton("Field Curves")
        self.btn_field.clicked.connect(self.show_field_curves)
        row2.addWidget(self.btn_mtf)
        row2.addWidget(self.btn_psf)
        row2.addWidget(self.btn_field)
        grid_layout.addLayout(row2)
        
        row3 = QHBoxLayout()
        self.btn_ghost = QPushButton("Ghost Analysis")
        self.btn_ghost.clicked.connect(self.show_ghost_analysis)
        self.btn_wavefront = QPushButton("Wavefront Map")
        self.btn_wavefront.clicked.connect(self.show_wavefront_map)
        self.btn_sim = QPushButton("Image Simulation")
        self.btn_sim.clicked.connect(self.show_image_simulation)
        row3.addWidget(self.btn_ghost)
        row3.addWidget(self.btn_wavefront)
        row3.addWidget(self.btn_sim)
        grid_layout.addLayout(row3)
        
        row4 = QHBoxLayout()
        self.btn_export = QPushButton("Export Report")
        self.btn_export.clicked.connect(self.export_report)
        row4.addWidget(self.btn_export)
        grid_layout.addLayout(row4)

        
        controls_layout.addWidget(buttons_grid)
        controls_layout.addStretch()
        
        self.splitter.addWidget(controls_widget)
        self.splitter.setStretchFactor(0, 3)
        self.splitter.setStretchFactor(1, 1)
        
        layout.addWidget(self.splitter)

    def set_system(self, system: Union[OpticalSystem, Lens]):
        """Update the current system for analysis."""
        if isinstance(system, Lens):
            # Wrap single lens in an OpticalSystem for analysis parity
            self.current_system = OpticalSystem(name=system.name)
            self.current_system.add_lens(system)
        else:
            self.current_system = system
        
        # Auto-calculate metrics if system changed
        self.calculate_metrics()

    @Slot()
    def calculate_metrics(self):
        if not self.current_system:
            self.metrics_text.setPlainText("No optical system selected.")
            return
            
        try:
            calculator = AberrationsCalculator(self.current_system)
            field = self.field_angle.value()
            
            # Wavelength mapping
            wl_map = [550.0, 587.6, 656.3, 486.1, 435.8]
            wl = wl_map[self.wavelength.currentIndex()]
            
            results = calculator.calculate_all_aberrations(field_angle=field, wavelength=wl)
            
            fl = self.current_system.get_system_focal_length()
            f_num = self.current_system.get_system_f_number()
            
            report = f"""=== OPTICAL PERFORMANCE REPORT ===
System: {self.current_system.name}
Field Angle: {field:.2f}° | Wavelength: {wl:.1f} nm

--- First-Order Properties ---
Effective Focal Length: {f'{fl:.3f} mm' if fl else 'Afocal'}
System F-Number: {f'f/{f_num:.2f}' if f_num else 'N/A'}
Optical Power: {self.current_system.calculate_optical_power():.4f} D

--- Seidel Aberrations (Primary) ---
Spherical Aberration (W040): {results.get('spherical', 0.0):.6f} λ
Coma (W131): {results.get('coma', 0.0):.6f} λ
Astigmatism (W222): {results.get('astigmatism', 0.0):.6f} λ
Field Curvature (W220): {results.get('field_curvature', 0.0):.6f} λ
Distortion (W311): {results.get('distortion', 0.0):.4f} %

--- Chromatic Aberrations ---
Longitudinal Chromatic: {results.get('chromatic_long', 0.0):.6f} mm
Lateral Chromatic: {results.get('chromatic_lat', 0.0):.6f} mm

--- Image Quality ---
RMS Spot Radius: {results.get('spot_rms', 0.0)*1000:.2f} µm
Geometric Spot Radius: {results.get('spot_geo', 0.0)*1000:.2f} µm
Strehl Ratio (est): {results.get('strehl', 0.0):.4f}
"""
            self.metrics_text.setPlainText(report)
            
        except Exception as e:
            logger.error(f"Failed to calculate metrics: {e}", exc_info=True)
            self.metrics_text.setPlainText(f"Error calculating metrics: {e}")

    @Slot()
    def show_spot_diagram(self):
        if not self.current_system:
            return
            
        try:
            # 1. Prepare parameters
            wl_map = [550.0, 587.6, 656.3, 486.1, 435.8]
            selected_wl = wl_map[self.wavelength.currentIndex()]
            field = self.field_angle.value()
            
            # 2. Setup analyzer
            analyzer = SpotDiagram(self.current_system)
            
            # 3. Trace
            # For multi-wavelength display if green/yellow selected
            wavelengths = [selected_wl]
            colors = ['#00ff00']
            if selected_wl in [550.0, 587.6]:
                wavelengths = [656.3, 587.6, 486.1] # C, d, F
                colors = ['#ff0000', '#00ff00', '#0000ff']
            
            all_results = []
            for wl in wavelengths:
                res = analyzer.trace_spot(field_angle_y=field, wavelength=wl, num_rings=6)
                all_results.append(res)
                
            # 4. Show dialog
            from openlens import AnalysisPlotDialog
            dialog = AnalysisPlotDialog(f"Spot Diagram - {self.current_system.name}", self.parent_window)
            ax = dialog.get_axes()
            
            for i, res in enumerate(all_results):
                pts = res['points']
                cent = res['centroid']
                # Plot relative to centroid for off-axis
                ax.scatter([(p[1]-cent[1])*1000 for p in pts], 
                           [(p[0]-cent[0])*1000 for p in pts], 
                           s=8, alpha=0.6, color=colors[i % len(colors)], 
                           label=f"{wavelengths[i]} nm")
            
            ax.set_aspect('equal')
            ax.set_xlabel("X (µm)")
            ax.set_ylabel("Y (µm)")
            rms = all_results[0]['rms_radius'] * 1000
            ax.set_title(f"Spot Diagram (Field {field:.1f}°, RMS={rms:.2f}µm)")
            ax.grid(True, linestyle='--', alpha=0.3)
            ax.legend(fontsize='x-small')
            
            dialog.exec()
            
        except Exception as e:
            logger.error(f"Spot diagram error: {e}", exc_info=True)
            if self.parent_window:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.critical(self.parent_window, "Analysis Error", f"Failed to generate spot diagram: {e}")

    @Slot()
    def show_ray_fan(self):
        if not self.current_system:
            return
            
        try:
            # 1. Prepare parameters
            wl_map = [550.0, 587.6, 656.3, 486.1, 435.8]
            selected_wl = wl_map[self.wavelength.currentIndex()]
            field = self.field_angle.value()
            
            # 2. Setup analyzer
            analyzer = GeometricTraceAnalysis(self.current_system)
            
            # 3. Setup Dialog
            from openlens import AnalysisPlotDialog
            dialog = AnalysisPlotDialog(f"Ray Fan - {self.current_system.name}", self.parent_window)
            ax1 = dialog.get_axes(1, 2, 1) # Tangential
            ax2 = dialog.get_axes(1, 2, 2) # Sagittal
            
            # Use chromatic lines if appropriate
            wls = [selected_wl]
            colors = ['#00ff00']
            if selected_wl in [550.0, 587.6]:
                wls = [656.3, 587.6, 486.1] # C, d, F
                colors = ['#ff0000', '#00ff00', '#0000ff']

            for i, wl in enumerate(wls):
                # Tangential Fan (Pupil Y)
                res_t = analyzer.calculate_ray_fan(field_angle=field, wavelength=wl, pupil_axis='y')
                ax1.plot(res_t['pupil_coords'], [e*1000 for e in res_t['ray_errors']], 
                        color=colors[i], label=f"{wl} nm")
                
                # Sagittal Fan (Pupil Z)
                res_s = analyzer.calculate_ray_fan(field_angle=field, wavelength=wl, pupil_axis='z')
                ax2.plot(res_s['pupil_coords'], [e*1000 for e in res_s['ray_errors']], 
                        color=colors[i])

            ax1.axhline(0, color='gray', linestyle='-', linewidth=0.5)
            ax1.axvline(0, color='gray', linestyle='-', linewidth=0.5)
            ax1.set_xlabel("Normalized Pupil (Py)")
            ax1.set_ylabel("Transverse Error (µm)")
            ax1.set_title("Tangential Fan")
            ax1.grid(True, linestyle='--', alpha=0.3)
            ax1.legend(fontsize='x-small')
            
            ax2.axhline(0, color='gray', linestyle='-', linewidth=0.5)
            ax2.axvline(0, color='gray', linestyle='-', linewidth=0.5)
            ax2.set_xlabel("Normalized Pupil (Px)")
            ax2.set_ylabel("Transverse Error (µm)")
            ax2.set_title("Sagittal Fan")
            ax2.grid(True, linestyle='--', alpha=0.3)
            
            dialog.exec()
            
        except Exception as e:
            logger.error(f"Ray fan error: {e}", exc_info=True)

    @Slot()
    def show_mtf(self):
        if not self.current_system:
            return
            
        try:
            # 1. Prepare parameters
            wl_map = [550.0, 587.6, 656.3, 486.1, 435.8]
            wl = wl_map[self.wavelength.currentIndex()]
            field = self.field_angle.value()
            
            # 2. Setup analyzer
            analyzer = ImageQualityAnalyzer(self.current_system)
            
            # 3. Calculate MTF
            res = analyzer.calculate_mtf(field_angle=field, wavelength=wl)
            
            # 4. Show dialog
            from openlens import AnalysisPlotDialog
            dialog = AnalysisPlotDialog(f"MTF - {self.current_system.name}", self.parent_window)
            ax = dialog.get_axes()
            
            freqs = res['frequencies']
            ax.plot(freqs, res['mtf_tangential'], 'b-', label=f"Field {field:.1f}° (T)")
            ax.plot(freqs, res['mtf_sagittal'], 'b--', label=f"Field {field:.1f}° (S)")
            
            # Add diffraction limit
            dl_res = analyzer.calculate_diffraction_limited_mtf(wavelength=wl)
            ax.plot(dl_res['frequencies'], dl_res['mtf'], 'k-', alpha=0.3, label="Diffraction Limit")

            ax.set_xlabel("Spatial Frequency (lp/mm)")
            ax.set_ylabel("Modulation")
            ax.set_title(f"MTF (λ={wl} nm)")
            ax.set_ylim(0, 1.05)
            ax.legend(fontsize='x-small')
            ax.grid(True, linestyle='--', alpha=0.3)
            
            dialog.exec()
            
        except Exception as e:
            logger.error(f"MTF error: {e}", exc_info=True)

    @Slot()
    def show_psf(self):
        if not self.current_system:
            return
            
        try:
            # 1. Prepare parameters
            wl_map = [550.0, 587.6, 656.3, 486.1, 435.8]
            wl = wl_map[self.wavelength.currentIndex()]
            field = self.field_angle.value()
            
            # 2. Setup analyzer
            analyzer = ImageQualityAnalyzer(self.current_system)
            
            # 3. Calculate PSF
            psf_data = analyzer.calculate_psf(field_angle=field, wavelength=wl, pixels=64)
            
            # 4. Show dialog
            from openlens import AnalysisPlotDialog
            dialog = AnalysisPlotDialog(f"PSF - {self.current_system.name}", self.parent_window)
            ax = dialog.get_axes(projection='3d')
            
            import numpy as np
            size = psf_data['size_um']
            grid = psf_data['grid_size']
            x = np.linspace(-size/2, size/2, grid)
            y = np.linspace(-size/2, size/2, grid)
            X, Y = np.meshgrid(x, y)
            Z = psf_data['intensity']
            
            if Z.max() > 0:
                Z = Z / Z.max()
            
            ax.plot_surface(X, Y, Z, cmap='viridis', edgecolor='none')
            ax.set_xlabel("X (µm)")
            ax.set_ylabel("Y (µm)")
            ax.set_zlabel("Intensity")
            ax.set_title(f"PSF (Field {field:.1f}°, λ={wl} nm)")
            
            dialog.exec()
            
        except Exception as e:
            logger.error(f"PSF error: {e}", exc_info=True)

    @Slot()
    def show_field_curves(self):
        if not self.current_system:
            return
            
        try:
            wl_map = [550.0, 587.6, 656.3, 486.1, 435.8]
            wl = wl_map[self.wavelength.currentIndex()]
            
            analyzer = GeometricTraceAnalysis(self.current_system)
            
            # Use 20 deg or current field if larger as max
            max_f = max(20.0, self.field_angle.value())
            res = analyzer.calculate_field_curvature_distortion(max_field_angle=max_f, wavelength=wl)
            
            from openlens import AnalysisPlotDialog
            dialog = AnalysisPlotDialog(f"Field Curves - {self.current_system.name}", self.parent_window)
            ax1 = dialog.get_axes(1, 2, 1)
            ax2 = dialog.get_axes(1, 2, 2)
            
            ax1.plot(res['tan_focus_shift'], res['field_angles'], 'b-', label='Tangential')
            ax1.plot(res['sag_focus_shift'], res['field_angles'], 'r--', label='Sagittal')
            ax1.set_xlabel("Focus Shift (mm)")
            ax1.set_ylabel("Field Angle (deg)")
            ax1.set_title("Field Curvature")
            ax1.legend()
            ax1.grid(True, alpha=0.3)
            
            ax2.plot(res['distortion_pct'], res['field_angles'], 'g-')
            ax2.set_xlabel("Distortion (%)")
            ax2.set_ylabel("Field Angle (deg)")
            ax2.set_title("Distortion")
            ax2.grid(True, alpha=0.3)
            
            dialog.exec()
        except Exception as e:
            logger.error(f"Field curves error: {e}", exc_info=True)

    @Slot()
    def show_ghost_analysis(self):
        if not self.current_system:
            return
            
        try:
            analyzer = GhostAnalyzer(self.current_system)
            ghost_paths = analyzer.trace_ghosts(num_rays=11)
            
            from openlens import AnalysisPlotDialog
            dialog = AnalysisPlotDialog(f"Ghost Analysis - {self.current_system.name}", self.parent_window)
            ax = dialog.get_axes()
            
            # Helper for simple geometry preview
            for element in self.current_system.elements:
                x = element.position
                t = element.lens.thickness
                d = element.lens.diameter
                ax.plot([x, x], [-d/2, d/2], 'w-', alpha=0.3)
                ax.plot([x+t, x+t], [-d/2, d/2], 'w-', alpha=0.3)

            colors = ['#ff0000', '#00ff00', '#ffff00', '#00ffff', '#ff00ff']
            for i, path in enumerate(ghost_paths[:5]):
                color = colors[i % len(colors)]
                for ray in path.rays:
                    x_vals = [p.x for p in ray.path]
                    y_vals = [p.y for p in ray.path]
                    ax.plot(x_vals, y_vals, '-', color=color, alpha=0.3)
            
            ax.set_aspect('equal')
            ax.set_title("Ghost Reflections (2nd Order)")
            dialog.exec()
        except Exception as e:
            logger.error(f"Ghost analysis error: {e}", exc_info=True)

    @Slot()
    def show_wavefront_map(self):
        if not self.current_system:
            return
            
        try:
            wl_map = [550.0, 587.6, 656.3, 486.1, 435.8]
            wl = wl_map[self.wavelength.currentIndex()]
            field = self.field_angle.value()
            
            try:
                from ..analysis.diffraction_psf import WavefrontSensor
            except ImportError:
                from src.analysis.diffraction_psf import WavefrontSensor
                
            sensor = WavefrontSensor(self.current_system)
            wf = sensor.get_pupil_wavefront(field_angle=field, wavelength=wl*1e-6)
            
            from openlens import AnalysisPlotDialog
            dialog = AnalysisPlotDialog(f"Wavefront - {self.current_system.name}", self.parent_window)
            ax = dialog.get_axes()
            
            import numpy as np
            im = ax.imshow(wf.W, extent=[wf.Z.min(), wf.Z.max(), wf.Y.min(), wf.Y.max()], 
                          cmap='RdBu_r', origin='lower')
            dialog.figure.colorbar(im, ax=ax, label='Waves')
            ax.set_title(f"Wavefront Error (Field {field:.1f}°, λ={wl} nm)")
            
            dialog.exec()
        except Exception as e:
            logger.error(f"Wavefront error: {e}", exc_info=True)

    @Slot()
    def export_report(self):
        """Export the current performance report to a text file."""
        if not self.metrics_text.toPlainText().strip() or "Select a system" in self.metrics_text.toPlainText():
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "No Data", "Please calculate metrics before exporting.")
            return
            
        try:
            from PySide6.QtWidgets import QFileDialog
            file_path, _ = QFileDialog.getSaveFileName(
                self, "Export Performance Report", "", "Text Files (*.txt);;All Files (*)"
            )
            
            if file_path:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(self.metrics_text.toPlainText())
                logger.info(f"Report exported to {file_path}")
        except Exception as e:
            logger.error(f"Failed to export report: {e}")
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Export Error", f"Failed to export report: {e}")

    @Slot()
    def show_image_simulation(self):
        """
        Perform an image simulation by convolving a test pattern with the 
        system's PSF (Point Spread Function).
        """
        if not self.current_system:
            return
            
        try:
            import numpy as np
            from PySide6.QtWidgets import QInputDialog, QFileDialog
            from PIL import Image
            
            # 1. Select Pattern or Custom Image
            items = ["Star Pattern", "Grid Pattern", "Checkerboard", "USAF 1951 Chart", "Load Image..."]
            item, ok = QInputDialog.getItem(self, "Image Simulation", "Select input pattern:", items, 0, False)
            if not ok:
                return
                
            input_img = None
            if item == "Load Image...":
                file_path, _ = QFileDialog.getOpenFileName(self, "Open Image", "", "Image Files (*.png *.jpg *.bmp)")
                if file_path:
                    img = Image.open(file_path).convert('RGB')
                    # Limit size for performance
                    img.thumbnail((512, 512))
                    input_img = np.array(img).astype(float) / 255.0
                else:
                    return
            else:
                # Generate procedural pattern
                size = 512
                input_img = np.zeros((size, size, 3))
                if item == "Star Pattern":
                    center = size // 2
                    for angle in range(0, 360, 10):
                        rad = math.radians(angle)
                        for r in range(size // 2):
                            px = int(center + r * math.cos(rad))
                            py = int(center + r * math.sin(rad))
                            if 0 <= px < size and 0 <= py < size:
                                input_img[py, px, :] = 1.0
                elif item == "Grid Pattern":
                    for i in range(0, size, 32):
                        input_img[i:i+2, :, :] = 1.0
                        input_img[:, i:i+2, :] = 1.0
                elif item == "Checkerboard":
                    for i in range(0, size, 64):
                        for j in range(0, size, 64):
                            if (i // 64 + j // 64) % 2 == 0:
                                input_img[i:i+64, j:j+64, :] = 1.0
                else: # USAF 1951 placeholder
                    input_img[size//4:3*size//4, size//4:3*size//4, 1] = 0.5 # Green square
            
            # 2. Run Simulation
            analyzer = ImageQualityAnalyzer(self.current_system)
            field = self.field_angle.value()
            wl_map = [550.0, 587.6, 656.3, 486.1, 435.8]
            primary_wl = wl_map[self.wavelength.currentIndex()]
            
            # Simulation usually needs RGB wavelengths
            rgb_wavelengths = (656.3, 587.6, 486.1) # C, d, F lines
            
            # Show "Processing" status
            self.metrics_text.append("\nStarting Image Simulation... please wait.")
            
            output_img = analyzer.simulate_image(
                image_array=input_img,
                pixel_size=0.005, # 5 micron pixels
                wavelengths=rgb_wavelengths,
                field_angle=field
            )
            
            # 3. Display Result
            from openlens import AnalysisPlotDialog
            dialog = AnalysisPlotDialog(f"Simulation - {self.current_system.name}", self.parent_window)
            ax1 = dialog.get_axes(1, 2, 1)
            ax2 = dialog.get_axes(1, 2, 2)
            
            ax1.imshow(input_img)
            ax1.set_title("Ideal (Input)")
            ax1.axis('off')
            
            ax2.imshow(output_img)
            ax2.set_title(f"Simulated (Field {field:.1f}°)")
            ax2.axis('off')
            
            self.metrics_text.append("Simulation complete.")
            dialog.exec()
            
        except Exception as e:
            logger.error(f"Image simulation error: {e}", exc_info=True)
            self.metrics_text.append(f"\nSimulation Failed: {str(e)}")

