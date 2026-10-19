"""
OpenLens PySide6 Performance Tab
Optical performance metrics and analysis plots
"""

import math
import logging
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QFormLayout,
    QDoubleSpinBox,
    QComboBox,
    QPushButton,
    QLabel,
    QTextEdit,
    QScrollArea,
    QMessageBox,
)
from .base_tab import BaseTab
from ..workers import AnalysisWorker

logger = logging.getLogger(__name__)


#: Keys excluded from a metrics fingerprint, because they identify the *record*
#: or the moment it was written rather than the design it now holds:
#: `modified_at`/`created_at` change on every touch (including a rename or a
#: mere re-selection) and `id` is a fresh uuid per object, so including them
#: would make two identical designs fingerprint differently and throw the cache
#: away constantly.
_VOLATILE_MODEL_KEYS = frozenset({"modified_at", "created_at", "id"})


def metrics_fingerprint(model) -> str:
    """A stable fingerprint of a model's optical state.

    The metrics cache was keyed on object identity, and the editor edits the
    lens in place, so the identity never changed: after a radius edit the tab
    went on repainting the focal length and aberrations of the lens as it was
    *before* the edit, with nothing to say they were out of date. Keying on what
    the model actually contains fixes that, and also catches edits made
    anywhere rather than only through the editor.

    Every serialized key counts, not a hand-picked list of optical ones, so a
    newly added field cannot be quietly left out of the cache key. That can
    cause a needless recompute - never a stale one - which is the right way
    round to be wrong.

    Args:
        model: A Lens or OpticalSystem.

    Returns:
        A string that changes whenever any non-volatile serialized value does.
    """
    try:
        data = model.to_dict()
    except Exception:  # pragma: no cover - defensive; to_dict is a plain read
        logger.debug("Could not fingerprint %r for the metrics cache", model, exc_info=True)
        return ""

    payload = {key: value for key, value in sorted(data.items()) if key not in _VOLATILE_MODEL_KEYS}
    try:
        return repr(payload)
    except Exception:  # pragma: no cover - repr of exotic metadata
        logger.debug("Could not represent %r for the metrics cache", model, exc_info=True)
        return ""


def _fmt(value, spec: str = ".4f", scale: float = 1.0) -> str:
    """Format a possibly-missing metric for the report.

    Aberration helpers return None when a value could not be measured. These
    used to be published as 0.0 - indistinguishable from a perfect design - so
    the report never had to cope with a gap. It now does, and says so rather
    than showing a fictional number.
    """
    if value is None:
        return "N/A"
    try:
        return format(value * scale, spec)
    except (TypeError, ValueError):
        return "N/A"


class PerformanceTab(BaseTab):
    """Optical performance metrics and analysis plots"""

    def _setup_ui(self) -> None:
        """Build the metrics dashboard, parameter inputs, and analysis buttons."""
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
        self._perf_metrics_text.setStyleSheet(
            "background-color: #2b2b2b; color: #e0e0e0; font-family: Courier; font-size: 10px;"
        )
        self._perf_metrics_text.setPlainText(
            "Select a lens and click 'Calculate Metrics' to view performance data."
        )
        metrics_layout.addWidget(self._perf_metrics_text, 1)

        # Last computed metrics, so refresh() can repaint without recomputing.
        self._cached_metrics_text = None
        self._cached_metrics = None
        self._cached_metrics_for = None
        # What the cached metrics were computed from. Identity alone is not
        # enough: the editor edits a lens in place, so the same object can hold
        # a different design than it did when the metrics were run.
        self._cached_metrics_stamp = None
        # The in-flight metrics computation. Held so a second click cannot
        # stack another trace on top, and so quitting can stop it.
        self._metrics_worker = None

        # Add the visualization widget
        from ..widgets import PerformanceVisualizationWidget

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
        self._perf_wavelength.addItems(
            [
                "400 nm (Violet)",
                "450 nm (Blue)",
                "550 nm (Green)",
                "650 nm (Red)",
                "700 nm (IR)",
            ]
        )
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

    def _current_system(self):
        """The assembly or lens the tab analyses, or None if nothing is selected."""
        return (
            self._parent._current_assembly
            if self._parent._current_assembly
            else self._parent._current_lens
        )

    @staticmethod
    def _wrap_in_system(active_system):
        """Wrap a bare lens in an OpticalSystem for the analysis helpers.

        Args:
            active_system: A Lens or an OpticalSystem.

        Returns:
            An OpticalSystem; the input itself when it already is one.
        """
        from ...optical_system import OpticalSystem

        if isinstance(active_system, OpticalSystem):
            return active_system
        system = OpticalSystem(name=active_system.name)
        system.add_lens(active_system)
        return system

    def _selected_wavelength(self) -> float:
        """Wavelength selected in the calculation parameters, in nanometres."""
        wavelengths = [400, 450, 550, 650, 700]
        return wavelengths[self._perf_wavelength.currentIndex()]

    def _max_field_angle(self, system) -> float:
        """Half-sensor field angle for the configured sensor size.

        Field curves used to be computed over a hardcoded 20 degrees, which
        has nothing to do with the system or the sensor the spot diagram and
        ray fan use. Deriving it here makes all three describe the same field.

        Args:
            system: OpticalSystem whose focal length sets the angle.

        Returns:
            The field angle in degrees, or 0.0 when the focal length is
            unknown (an afocal or invalid system).
        """
        fl = system.get_system_focal_length()
        sensor_size = self._perf_sensor_size.value()
        if fl and fl > 0:
            return math.degrees(math.atan((sensor_size / 2.0) / fl))
        return 0.0

    def _analysis_fields(self, system) -> list:
        """The three field angles shared by the spot diagram and ray fan."""
        max_field = self._max_field_angle(system)
        return [0, max_field * 0.7, max_field]

    def _report_missing_matplotlib(self, error) -> None:
        """Tell the user an analysis needs matplotlib rather than crash."""
        logger.warning("Analysis plot dependency missing: %s", error)
        QMessageBox.warning(
            self,
            "Dependency Missing",
            "This analysis requires 'matplotlib'.\n" "Install it with 'pip install matplotlib'.",
        )

    def _on_show_image_simulation(self) -> None:
        """Show Image Simulation Dialog with side-by-side view."""
        active_system = (
            self._parent._current_assembly
            if self._parent._current_assembly
            else self._parent._current_lens
        )
        if not active_system:
            QMessageBox.warning(self, "No Selection", "Please select a lens or assembly first")
            return

        try:
            from ...optical_system import OpticalSystem
            from ..dialogs.image_sim import ImageSimulationDialog

            if not isinstance(active_system, OpticalSystem):
                system = OpticalSystem(name=active_system.name)
                system.add_lens(active_system)
            else:
                system = active_system

            dialog = ImageSimulationDialog(system, self._parent)
            dialog.exec()

        except ImportError as e:
            if "PIL" in str(e) or "Pillow" in str(e):
                QMessageBox.warning(
                    self,
                    "Dependency Missing",
                    "Image simulation requires 'Pillow' (PIL).",
                )
            else:
                logger.error("Import error in image simulation: %s", e)
                QMessageBox.warning(
                    self,
                    "Dependency Missing",
                    f"Image simulation requires matplotlib.\n\n{e}",
                )
        except Exception as e:
            logger.error("Image simulation error: %s", e)
            QMessageBox.critical(self, "Analysis Error", f"Failed to start image simulation: {e}")

    def _on_calculate_performance_metrics(self) -> None:
        """Calculate the metrics; the ray traces run off the GUI thread.

        The report shows a status line immediately and is painted when the
        worker finishes. A stale result is never published: if the design or
        the selection changes while the trace runs, the tab says so instead of
        showing numbers for a design that is no longer on screen.
        """
        active_system = self._current_system()
        if not active_system:
            self._perf_metrics_text.setPlainText("No system selected.")
            return

        if self._metrics_worker is not None and self._metrics_worker.isRunning():
            self._parent._update_status("Metrics calculation is already running")
            return

        # Read the UI on the GUI thread; the worker must not touch widgets.
        wavelength = self._selected_wavelength()
        entrance_pupil = self._perf_entrance_pupil.value()
        object_distance = self._perf_object_distance.value()
        sensor_size = self._perf_sensor_size.value()
        system = self._wrap_in_system(active_system)

        def _compute():
            from ...aberrations import AberrationsCalculator
            from ...optical_system import OpticalSystem

            # Fingerprint before measuring: it must describe the design the
            # report describes, not whatever the editor holds by the end.
            stamp = metrics_fingerprint(active_system)
            calculator = AberrationsCalculator(system)

            # Get optical properties
            if hasattr(system, "get_system_focal_length"):
                fl = system.get_system_focal_length()
            else:
                fl = active_system.calculate_focal_length()

            power = (
                system.calculate_optical_power()
                if hasattr(system, "calculate_optical_power")
                else active_system.calculate_optical_power()
            )
            bfl = (
                system.calculate_back_focal_length()
                if hasattr(system, "calculate_back_focal_length")
                else active_system.calculate_back_focal_length()
            )

            # Calculate field angle derived from sensor size
            field_angle = 0.0
            if fl and fl > 0:
                field_angle = math.degrees(math.atan((sensor_size / 2.0) / fl))

            results = calculator.calculate_all_aberrations(
                field_angle_deg=field_angle, wavelength_nm=wavelength
            )

            # Calculate chromatic focal shift if it's an assembly
            chromatic_text = ""
            if isinstance(active_system, OpticalSystem):
                chromatic = active_system.calculate_chromatic_aberration()
                if chromatic and chromatic.get("longitudinal") is not None:
                    chromatic_text = (
                        f"Chromatic Focal Shift (C-F): {chromatic['longitudinal']:.4f} mm\n"
                    )
                    if chromatic.get("bfl_d") is not None:
                        bfl_F = chromatic.get("bfl_F")
                        chromatic_text += f"  BFL (F=486nm): {f'{bfl_F:.3f}' if bfl_F is not None else 'N/A'} mm\n"
                        bfl_d = chromatic.get("bfl_d")
                        chromatic_text += f"  BFL (d=587nm): {f'{bfl_d:.3f}' if bfl_d is not None else 'N/A'} mm\n"
                        bfl_C = chromatic.get("bfl_C")
                        chromatic_text += f"  BFL (C=656nm): {f'{bfl_C:.3f}' if bfl_C is not None else 'N/A'} mm\n"

            # Surface the calculator's own validity verdict, so a value that
            # could not be measured is visibly absent rather than silently 0.
            if results.get("error"):
                validity_note = f"\n--- WARNING ---\n{results['error']}\n"
            elif results.get("valid") is False:
                validity_note = (
                    "\n--- WARNING ---\nSome metrics could not be evaluated "
                    "(ray trace failed or the design is vignetted). "
                    "They are reported as N/A, not as zero.\n"
                )
            else:
                validity_note = ""

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
Spherical Aberration: {_fmt(results.get('spherical'))} mm (longitudinal)
Coma: {_fmt(results.get('coma'))} mm (transverse)
Astigmatism: {_fmt(results.get('astigmatism'))} mm
Distortion: {_fmt(results.get('distortion'), '.2f')} %
Chromatic Aberration: {_fmt(results.get('chromatic'))} mm

--- Image Quality Metrics ---
MTF Cutoff: {_fmt(results.get('mtf_cutoff'), '.1f')} lp/mm
Strehl Ratio: {_fmt(results.get('strehl'), '.3f')} (from traced RMS wavefront error)
RMS Wavefront Error: {_fmt(results.get('wfe_rms_waves'), '.3f')} waves
Spot Size (RMS): {_fmt(results.get('spot_rms'), '.3f')} µm
Airy Disk (Dia): {_fmt(results.get('airy_disk_diameter'), '.2f', 1000.0)} µm
{validity_note}"""
            return active_system, text, results, stamp

        self._perf_metrics_text.setPlainText(
            "Calculating metrics…\nThe analysis runs in the background."
        )
        worker = AnalysisWorker(_compute, self)
        self._metrics_worker = worker
        worker.done.connect(lambda payload, w=worker: self._on_metrics_ready(w, payload))
        worker.failed.connect(lambda message, w=worker: self._on_metrics_failed(w, message))
        worker.finished.connect(lambda w=worker: self._on_metrics_finished(w))
        worker.start()

    def _on_metrics_ready(self, worker, payload) -> None:
        """Publish a finished report if it still describes the current design."""
        if self._metrics_worker is not worker:
            # A newer run replaced this one; only its result is current.
            return

        measured, text, results, stamp = payload
        active_system = self._current_system()
        if active_system is None:
            self._perf_metrics_text.setPlainText("No system selected.")
            return

        current = metrics_fingerprint(active_system)
        if active_system is not measured or current != stamp:
            # The design changed (or the selection moved) while the trace ran.
            # Publishing the payload would silently show numbers for a design
            # that is no longer on screen.
            self._cached_metrics_text = None
            self._cached_metrics = None
            self._cached_metrics_for = active_system
            self._cached_metrics_stamp = current
            if active_system is measured:
                message = (
                    f"{active_system.name} has changed since these metrics were "
                    "calculated.\nThey no longer describe this design - click "
                    "'Calculate Metrics' to update them."
                )
            else:
                message = (
                    f"Metrics not yet calculated for {active_system.name}.\n"
                    "Click 'Calculate Metrics' to run the analysis."
                )
            self._perf_metrics_text.setPlainText(message)
            if hasattr(self, "_perf_viz"):
                self._perf_viz.update_lens(active_system)
            return

        # Remember the result so refresh() can repaint without recomputing.
        # Keyed on what the model *contains*, not on which object it is: the
        # editor edits lenses in place, so identity alone cannot tell an
        # edited lens from an untouched one.
        self._perf_metrics_text.setPlainText(text)
        self._cached_metrics_text = text
        self._cached_metrics = results
        self._cached_metrics_for = active_system
        self._cached_metrics_stamp = stamp

        # Update visualization widget
        if hasattr(self, "_perf_viz"):
            self._perf_viz.update_lens(active_system)
            self._perf_viz.update_metrics(results)

        self._parent._update_status(f"Calculated metrics for {active_system.name}")

    def _on_metrics_failed(self, worker, message: str) -> None:
        """Report a failed metrics run in the report pane."""
        if self._metrics_worker is not worker:
            return
        logger.error("Performance calculation error: %s", message)
        self._perf_metrics_text.setPlainText(f"Error calculating metrics: {message}")

    def _on_metrics_finished(self, worker) -> None:
        """Drop the finished worker so a later run can start cleanly."""
        if self._metrics_worker is worker:
            self._metrics_worker = None

    def _on_show_spot_diagram(self) -> None:
        """Show the spot diagram; the ray trace runs off the GUI thread."""
        active_system = self._current_system()
        if not active_system:
            QMessageBox.warning(self, "No Selection", "Please select a lens or assembly first")
            return

        try:
            from ...analysis.psf_mtf import ImageQualityAnalyzer

            system = self._wrap_in_system(active_system)
            wavelength = self._selected_wavelength()
            fields = self._analysis_fields(system)
            colors = ["#ffffff", "#00ff00", "#ff0000"]

            def _compute():
                analyzer = ImageQualityAnalyzer(system)
                return [
                    (
                        field,
                        analyzer.calculate_spot_diagram(
                            field_angle_deg=field, wavelength_nm=wavelength, num_rings=6
                        ),
                    )
                    for field in fields
                ]

            def _plot(ax, payload):
                for index, (field, spot_data) in enumerate(payload):
                    # Spot points are (y, z) - usually we plot Y vs Z or vice versa
                    z_pts = [p[1] * 1000 for p in spot_data]  # Sagittal (Z)
                    y_pts = [p[0] * 1000 for p in spot_data]  # Tangential (Y)
                    ax.plot(
                        z_pts,
                        y_pts,
                        ".",
                        color=colors[index],
                        label=f"Field {field:.1f}°",
                        markersize=3,
                        alpha=0.6,
                    )

                ax.set_aspect("equal")
                ax.set_xlabel("Sagittal (µm)")
                ax.set_ylabel("Tangential (µm)")
                ax.set_title(f"Spot Diagram ({wavelength}nm)")
                ax.legend(fontsize="small")
                ax.grid(True, linestyle="--", alpha=0.3)

            self._parent._open_analysis_dialog(f"Spot Diagram - {system.name}", _compute, _plot)

        except ImportError as e:
            self._report_missing_matplotlib(e)
        except Exception as e:
            logger.error("Spot diagram error: %s", e)
            QMessageBox.critical(self, "Analysis Error", f"Failed to generate spot diagram: {e}")

    def _on_show_ray_fan(self) -> None:
        """Show the ray fan; the ray traces run off the GUI thread."""
        active_system = self._current_system()
        if not active_system:
            QMessageBox.warning(self, "No Selection", "Please select a lens or assembly first")
            return

        try:
            from ...aberrations import AberrationsCalculator

            system = self._wrap_in_system(active_system)
            wavelength = self._selected_wavelength()
            fields = self._analysis_fields(system)
            calculator = AberrationsCalculator(system)
            colors = ["#ffffff", "#00ff00", "#ff0000"]
            styles = ["-", "--", ":"]

            def _compute():
                return [
                    (
                        field,
                        calculator.calculate_ray_fan(
                            field_angle_deg=field, wavelength_nm=wavelength
                        ),
                    )
                    for field in fields
                ]

            def _plot(ax, payload):
                for index, (field, fan_data) in enumerate(payload):
                    ax.plot(
                        fan_data["pupil_coords"],
                        fan_data["transverse_aberration"],
                        color=colors[index],
                        linestyle=styles[index],
                        label=f"Field {field:.1f}°",
                    )

                ax.set_xlabel("Pupil Coordinate (Normalized)")
                ax.set_ylabel("Transverse Aberration (mm)")
                ax.set_title(f"Ray Fan - Tangential ({wavelength}nm)")
                ax.axhline(0, color="white", linewidth=0.5, alpha=0.5)
                ax.axvline(0, color="white", linewidth=0.5, alpha=0.5)
                ax.legend(fontsize="small")
                ax.grid(True, linestyle="--", alpha=0.3)

            self._parent._open_analysis_dialog(f"Ray Fan - {system.name}", _compute, _plot)

        except ImportError as e:
            self._report_missing_matplotlib(e)
        except Exception as e:
            logger.error("Ray fan error: %s", e)
            QMessageBox.critical(self, "Analysis Error", f"Failed to generate ray fan: {e}")

    def _on_show_field_curves(self) -> None:
        """Show field curvature and distortion; the traces run in a worker."""
        active_system = self._current_system()
        if not active_system:
            QMessageBox.warning(self, "No Selection", "Please select a lens or assembly first")
            return

        try:
            from ...aberrations import AberrationsCalculator

            system = self._wrap_in_system(active_system)
            wavelength = self._selected_wavelength()
            max_field = self._max_field_angle(system)
            calculator = AberrationsCalculator(system)

            def _compute():
                angles, sag, tan = calculator.calculate_field_curvature(
                    max_field_angle_deg=max_field, wavelength_nm=wavelength
                )
                dist_angles, dist = calculator.calculate_distortion_curve(
                    max_field_angle_deg=max_field, wavelength_nm=wavelength
                )
                return angles, sag, tan, dist_angles, dist

            def _plot(axes, payload):
                ax1, ax2 = axes
                angles, sag, tan, dist_angles, dist = payload

                ax1.plot(sag, angles, "b-", label="Sagittal")
                ax1.plot(tan, angles, "r--", label="Tangential")
                ax1.set_ylabel("Field Angle (deg)")
                ax1.set_xlabel("Focus Shift (mm)")
                ax1.set_title("Field Curvature")
                ax1.legend(fontsize="x-small")
                ax1.grid(True, linestyle="--", alpha=0.3)

                ax2.plot(dist, dist_angles, "g-")
                ax2.set_ylabel("Field Angle (deg)")
                ax2.set_xlabel("Distortion (%)")
                ax2.set_title("f-theta Distortion")
                ax2.grid(True, linestyle="--", alpha=0.3)
                ax2.axvline(0, color="white", linewidth=0.5, alpha=0.5)
                ax2.figure.tight_layout()

            self._parent._open_analysis_dialog(
                f"Field Curves - {system.name}", _compute, _plot, columns=2
            )

        except ImportError as e:
            self._report_missing_matplotlib(e)
        except Exception as e:
            logger.error("Field curves error: %s", e)
            QMessageBox.critical(self, "Analysis Error", f"Failed to generate field curves: {e}")

    def _on_show_psf(self) -> None:
        """Show PSF Analysis through parent."""
        self._parent._on_show_psf()

    def _on_show_mtf(self) -> None:
        """Show MTF Analysis through parent."""
        self._parent._on_show_mtf()

    def _on_show_wavefront(self) -> None:
        """Show Wavefront Analysis through parent."""
        self._parent._on_show_wavefront()

    def _on_show_ghost_analysis(self) -> None:
        """Show Ghost Analysis through parent."""
        self._parent._on_show_ghost_analysis()

    def refresh(self) -> None:
        """Refresh performance tab state.

        Repaints from the last computed metrics; it does **not** recompute.
        ``refresh()`` runs on every edit keystroke via
        ``OpenLensWindow._update_all_tabs``, and computing here meant a full
        ``calculate_all_aberrations()`` plus ``calculate_chromatic_aberration()``
        ray trace ran on the GUI thread per keystroke - ~96 ms each, so typing
        a 20-character name took about two seconds of stuttering. Calculation
        belongs to the explicit "Calculate Metrics" button, which already
        exists.
        """
        active_system = (
            self._parent._current_assembly
            if self._parent._current_assembly
            else self._parent._current_lens
        )
        if not active_system:
            self._cached_metrics_text = None
            self._cached_metrics_for = None
            self._cached_metrics_stamp = None
            self._perf_metrics_text.setPlainText(
                "Select a lens or assembly and click 'Calculate Metrics' to view performance data."
            )
            if hasattr(self, "_perf_viz"):
                self._perf_viz.update_lens(None)
            return

        # Metrics are cached per model, so switching targets shows that
        # target's own last result rather than the previous one's. The key is
        # what the model contains, so an in-place edit - which the editor does
        # on every keystroke - drops the cache too. Keying on identity alone let
        # an edited lens keep showing the pre-edit numbers with no indication
        # they were stale.
        current = metrics_fingerprint(active_system)
        same_model = self._cached_metrics_for is active_system

        # Only a *previous result for this very model* can go stale. A model we
        # have never calculated for is not stale, it is uncalculated - and
        # telling a user their report is out of date when they never asked for
        # one is its own kind of lie.
        went_stale = (
            same_model
            and self._cached_metrics_text is not None
            and self._cached_metrics_stamp is not None
            and self._cached_metrics_stamp != current
        )

        if went_stale or not same_model:
            self._cached_metrics_text = None
            self._cached_metrics = None
            self._cached_metrics_stamp = current
            self._cached_metrics_for = active_system

        if self._cached_metrics_text is None:
            if went_stale:
                # The distinction matters. "Not yet calculated" tells the user
                # to press the button; "these numbers are from before your
                # edit" tells them the report they were reading has just
                # stopped describing the lens in front of them. Only the second
                # is honest, and the first is what made the staleness invisible.
                self._perf_metrics_text.setPlainText(
                    f"{active_system.name} has changed since these metrics were "
                    "calculated.\nThey no longer describe this design - click "
                    "'Calculate Metrics' to update them."
                )
            else:
                self._perf_metrics_text.setPlainText(
                    f"Metrics not yet calculated for {active_system.name}.\n"
                    "Click 'Calculate Metrics' to run the analysis."
                )
            if hasattr(self, "_perf_viz"):
                self._perf_viz.update_lens(active_system)
            return

        self._perf_metrics_text.setPlainText(self._cached_metrics_text)
        if hasattr(self, "_perf_viz"):
            self._perf_viz.update_lens(active_system)
            if self._cached_metrics is not None:
                self._perf_viz.update_metrics(self._cached_metrics)
