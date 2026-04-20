#!/usr/bin/env python3
"""
OpenLens - Optical Lens Design Application
PySide6-based modern GUI
"""

import sys
import os
import math
import logging

logger = logging.getLogger(__name__)

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                               QLabel, QListWidget, QListWidgetItem, QPushButton, 
                               QDoubleSpinBox, QSpinBox, QLineEdit, QGroupBox, QFormLayout, 
                               QFrame, QTabWidget, QComboBox, QCheckBox, QDialog, QStatusBar,
                               QTextEdit, QFileDialog, QMessageBox, QScrollArea)
from PySide6.QtCore import Qt, QTimer, Slot, Signal, QMetaObject, Q_ARG
from PySide6.QtGui import QKeySequence

# Matplotlib imports for Analysis
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar

from src.lens import Lens

# Try to import from new module structure, fall back to inline
try:
    from src.gui.widgets import LensEditorWidget, LensVisualizationWidget
    from src.gui.dialogs import StartupDialog
except ImportError:
    LensEditorWidget = None
    LensVisualizationWidget = None
    StartupDialog = None
from src.services import LensService


class AnalysisPlotDialog(QDialog):
    """Reusable dialog for displaying Matplotlib plots."""
    
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(800, 600)
        
        layout = QVBoxLayout(self)
        
        # Create figure and canvas
        self.figure = Figure(figsize=(8, 6), dpi=100)
        if hasattr(parent, '_theme') and parent._theme == 'dark':
            self.figure.patch.set_facecolor('#1e1e1e')
            
        self.canvas = FigureCanvas(self.figure)
        layout.addWidget(self.canvas)
        
        # Add navigation toolbar
        self.toolbar = NavigationToolbar(self.canvas, self)
        layout.addWidget(self.toolbar)
        
        # Add close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

    def get_axes(self, *args, **kwargs):
        """Get axes for the figure, setting dark theme if needed."""
        ax = self.figure.add_subplot(*args, **kwargs)
        if hasattr(self.parent(), '_theme') and self.parent()._theme == 'dark':
            ax.set_facecolor('#1e1e1e')
            ax.tick_params(colors='#e0e0e0')
            ax.xaxis.label.set_color('#e0e0e0')
            ax.yaxis.label.set_color('#e0e0e0')
            ax.title.set_color('#e0e0e0')
            for spine in ax.spines.values():
                spine.set_edgecolor('#3f3f3f')
        return ax


class OpenLensWindow(QMainWindow):
    """Main application window"""
    
    # Define custom signals for thread-safe UI updates
    opt_finished = Signal(object, list)
    opt_failed = Signal(str)
    
    def __init__(self, action=None, data=None):
        super().__init__()
        
        self._action = action
        self._data = data
        self._theme = 'dark'
        
        self.setWindowTitle("OpenLens - Optical Lens Design")
        self.setMinimumSize(1000, 700)
        
        # Initialize database
        self._db_path = "openlens.db"
        self._load_from_database()
        
        self._setup_ui()
        self._create_menu()
        
        # Connect signals
        self.opt_finished.connect(self._on_optimization_finished)
        self.opt_failed.connect(self._on_optimization_failed)
        
        self._handle_startup(action, data)
    
    def _load_from_database(self):
        """Load lenses and assemblies from SQLite database"""
        from src.gui.storage import LensStorage
        from src.database import DatabaseManager
        
        try:
            storage = LensStorage(self._db_path, lambda x: None)
            all_items = storage.load_lenses()
            
            self._lenses = []
            self._assemblies = []
            self._current_lens = None
            self._current_assembly = None
            
            for item in all_items:
                if hasattr(item, 'elements') and hasattr(item, 'air_gaps'):
                    self._assemblies.append(item)
                else:
                    self._lenses.append(item)
            
            logger.info(f"Loaded {len(self._lenses)} lenses and {len(self._assemblies)} assemblies from database")
            
        except Exception as e:
            logger.error(f"Failed to load from database: {e}")
            self._lenses = []
            self._assemblies = []
            self._current_lens = None
            self._current_assembly = None
    
    def _save_to_database(self):
        """Save all lenses and assemblies to SQLite database"""
        from src.gui.storage import LensStorage
        
        try:
            # Sync tolerances to current target metadata before saving
            target = self._current_assembly if self._current_assembly else self._current_lens
            if target:
                if not hasattr(target, 'metadata'):
                    target.metadata = {}
                target.metadata['tolerances'] = [
                    {
                        'element_index': op.element_index,
                        'type': op.param_type.value,
                        'min_val': op.min_val,
                        'max_val': op.max_val,
                        'distribution': getattr(op, 'distribution', 'uniform')
                    } for op in self._tol_operands
                ]

            storage = LensStorage(self._db_path, lambda x: None)
            all_items = self._lenses + self._assemblies
            storage.save_lenses(all_items)
            logger.info(f"Saved {len(all_items)} items to database")
        except Exception as e:
            logger.error(f"Failed to save to database: {e}")
    
    def _handle_startup(self, action, data):
        """Handle startup action"""
        if action == "create_lens":
            self._on_new_lens()
            self._update_status("New lens created")
        elif action == "create_assembly":
            self._on_new_lens()
            self._update_status("New assembly created")
        elif action == "open_lens" and data:
            self._load_lens_from_data(data)
            self._update_status(f"Loaded: {getattr(data, 'name', 'Unknown')}")
        elif action == "open_assembly" and data:
            self._load_lens_from_data(data)
            self._update_status(f"Loaded: {getattr(data, 'name', 'Unknown')}")
        else:
            self._load_default_lens()
            self._update_status("Loaded default lens")
    
    def _update_status(self, message):
        """Update status bar message"""
        if hasattr(self, '_status_label'):
            self._status_label.setText(message)
        if hasattr(self, '_status_bar'):
            self._status_bar.showMessage(message)
    
    def _load_lens_from_data(self, data):
        """Load lens or assembly from saved data"""
        from src.optical_system import OpticalSystem
        if isinstance(data, OpticalSystem):
            self._assemblies.append(data)
            self._current_assembly = data
            self._current_lens = None
            self._show_assembly_editor(True)
            self._show_lens_editor(False)
            self._assembly_viz.update_system(data)
            self._optical_system = data
            self._update_system_list()
        elif isinstance(data, Lens):
            self._lenses.append(data)
            self._current_lens = data
            self._current_assembly = None
            self._show_assembly_editor(False)
            self._show_lens_editor(True)
        elif isinstance(data, dict):
            # Fallback for dict data
            if data.get('type') == 'OpticalSystem':
                system = OpticalSystem.from_dict(data)
                self._assemblies.append(system)
                self._current_assembly = system
                self._current_lens = None
            else:
                lens = Lens.from_dict(data)
                self._lenses.append(lens)
                self._current_lens = lens
                self._current_assembly = None
        else:
            self._load_default_lens()
        
        self._update_lens_list()
        if self._current_lens:
            self._lens_editor.load_lens(self._current_lens)
        
        # Load tolerances if they exist in metadata
        target = self._current_assembly if self._current_assembly else self._current_lens
        if target and hasattr(target, 'metadata') and 'tolerances' in target.metadata:
            try:
                from src.tolerancing import ToleranceOperand, ToleranceType
                self._tol_operands = []
                for t_data in target.metadata['tolerances']:
                    p_type = next((t for t in ToleranceType if t.value == t_data['type']), ToleranceType.RADIUS_1)
                    op = ToleranceOperand(
                        element_index=t_data['element_index'],
                        param_type=p_type,
                        min_val=t_data['min_val'],
                        max_val=t_data['max_val'],
                        distribution=t_data.get('distribution', 'uniform')
                    )
                    self._tol_operands.append(op)
                self._update_tolerance_operands_display()
            except Exception as e:
                logger.warning(f"Failed to load tolerances: {e}")
        else:
            self._tol_operands = []
            self._update_tolerance_operands_display()

        self._update_all_tabs()
    
    def _setup_ui(self):
        """Setup the main UI"""
        central = QWidget()
        self.setCentralWidget(central)
        
        # Main layout
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Top: Main content area
        content = QWidget()
        content_layout = QHBoxLayout(content)
        content_layout.setContentsMargins(5, 5, 5, 5)
        
        # Right: Editor with visualization
        self._editor_widget = None  # Will be LensEditorWidget
        
        content_layout.addWidget(self._create_editor_area())
        
        main_layout.addWidget(content, 1)
        
        # Status bar
        self._status_bar = QStatusBar()
        self._status_bar.setStyleSheet("""
            QStatusBar {
                background-color: #2d2d2d;
                color: #e0e0e0;
                border-top: 1px solid #3f3f3f;
            }
        """)
        self._status_label = QLabel("Ready")
        self._status_bar.addWidget(self._status_label)
        self.setStatusBar(self._status_bar)
        
        self._update_status("Welcome to OpenLens")
    
    def _create_editor_area(self):
        """Create the main editor area with tabs"""
        from PySide6.QtWidgets import QTabWidget, QFrame
        
        self._editor_tabs = QTabWidget()
        self._editor_tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #3f3f3f;
                background-color: #1e1e1e;
            }
            QTabBar::tab {
                background-color: #2d2d2d;
                color: #e0e0e0;
                padding: 8px 16px;
                border: 1px solid #3f3f3f;
            }
            QTabBar::tab:selected {
                background-color: #0078d4;
            }
        """)
        
        # Lens Editor tab (always visible)
        self._lens_editor = LensEditorWidget(self)
        self._editor_tabs.addTab(self._lens_editor, "Lens Editor")
        
        # Assembly Editor tab (initially hidden - only shown when editing assembly)
        self._assembly_tab = self._create_assembly_editor()
        self._assembly_tab_index = self._editor_tabs.addTab(self._assembly_tab, "Assembly Editor")
        self._editor_tabs.setTabVisible(self._assembly_tab_index, False)
        
        # Other tabs
        sim_tab = self._create_simulation_tab()
        self._editor_tabs.addTab(sim_tab, "Simulation")
        
        perf_tab = self._create_performance_tab()
        self._editor_tabs.addTab(perf_tab, "Performance")
        
        opt_tab = self._create_optimization_tab()
        self._editor_tabs.addTab(opt_tab, "Optimization")
        
        tol_tab = self._create_tolerancing_tab()
        self._editor_tabs.addTab(tol_tab, "Tolerancing")
        
        return self._editor_tabs
    
    def _show_assembly_editor(self, show=True):
        """Show/hide assembly editor tab"""
        if hasattr(self, '_assembly_tab_index'):
            self._editor_tabs.setTabVisible(self._assembly_tab_index, show)
    
    def _show_lens_editor(self, show=True):
        """Show lens editor tab"""
        self._editor_tabs.setTabVisible(0, show)
    
    def _create_menu(self):
        """Create menu bar"""
        from PySide6.QtWidgets import QMenuBar, QMenu
        
        menubar = self.menuBar()
        menubar.setStyleSheet("""
            QMenuBar {
                background-color: #2d2d2d;
                color: #e0e0e0;
            }
            QMenuBar::item:selected {
                background-color: #0078d4;
            }
            QMenu {
                background-color: #2d2d2d;
                color: #e0e0e0;
                border: 1px solid #3f3f3f;
            }
            QMenu::item:selected {
                background-color: #0078d4;
            }
        """)
        
        # File menu
        file_menu = menubar.addMenu("File")
        file_menu.addAction("New Lens", self._on_new_lens, QKeySequence.New)
        file_menu.addAction("Open...", self._on_open, QKeySequence.Open)
        file_menu.addAction("Save", self._on_save, QKeySequence.Save)
        file_menu.addAction("Save As...", self._on_save_as, QKeySequence("Ctrl+Shift+S"))
        file_menu.addSeparator()
        
        # Export submenu
        export_menu = file_menu.addMenu("Export")
        export_menu.addAction("Export to STL...", self._on_export_stl)
        export_menu.addAction("Export to STEP...", self._on_export_step)
        export_menu.addAction("Export to ISO 10110...", self._on_export_iso10110)
        export_menu.addAction("Export Report...", self._on_export_report)
        
        file_menu.addSeparator()
        file_menu.addAction("Exit", self.close, QKeySequence.Quit)
        
        # Edit menu
        edit_menu = menubar.addMenu("Edit")
        edit_menu.addAction("Undo", self._on_undo, QKeySequence("Ctrl+Z"))
        edit_menu.addAction("Redo", self._on_redo, QKeySequence("Ctrl+Y"))
        edit_menu.addSeparator()
        edit_menu.addAction("Delete Lens", self._on_delete_lens, QKeySequence("Delete"))
        edit_menu.addSeparator()
        edit_menu.addAction("Duplicate Lens", self._on_duplicate_lens, QKeySequence("Ctrl+D"))
        
        # Preferences menu
        prefs_menu = menubar.addMenu("Preferences")
        prefs_menu.addAction("Toggle Dark/Light Theme", self._on_toggle_theme, QKeySequence("Ctrl+T"))
        
        # Lens menu (quick switch)
        lens_menu = menubar.addMenu("Lens")
        
        # Lenses section header
        lens_menu.addAction("--- Lenses ---")
        for i, lens in enumerate(self._lenses):
            act = lens_menu.addAction(lens.name, lambda idx=i: self._switch_to_lens(idx))
        
        # Separator
        lens_menu.addSeparator()
        
        if self._assemblies:
            # Assemblies section header
            asm_action = lens_menu.addAction("--- Assemblies ---")
            asm_action.setEnabled(False)
            for i, asm in enumerate(self._assemblies):
                idx = len(self._lenses) + i
                act = lens_menu.addAction(f"[{asm.name}]", lambda idx=idx: self._switch_to_lens(idx))
        
        lens_menu.addSeparator()
        lens_menu.addAction("Refresh", self._refresh_lens_menu)
        
# View menu
        view_menu = menubar.addMenu("View")
        view_menu_2d = view_menu.addMenu("2D View")
        view_menu_2d.addAction("Top", lambda: self._set_viz_mode("2D"))
        view_menu_2d.addAction("Side", lambda: self._set_viz_mode("side"))
        
        view_menu_3d = view_menu.addMenu("3D View (External)")
        view_menu_3d.addAction("Open 3D Viewer...", self._open_3d_viewer)
        
        view_menu.addSeparator()
        view_menu.addAction("Reset Window", self._on_reset_window, QKeySequence("Ctrl+0"))
        
        # Help menu
        help_menu = menubar.addMenu("Help")
        help_menu.addAction("About", self._on_about)
        help_menu.addAction("Keyboard Shortcuts", self._on_show_shortcuts)
    
    def _create_simulation_tab(self):
        """Create the simulation tab"""
        from PySide6.QtWidgets import QSlider
        from PySide6.QtCore import Signal
        
        sim = QWidget()
        layout = QHBoxLayout(sim)
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
        
        # Ghost analysis checkbox (moved above buttons)
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
        
        # Reset View button in bottom right
        reset_view_btn = QPushButton("Reset View")
        reset_view_btn.clicked.connect(self._reset_simulation_view)
        controls_layout.addWidget(reset_view_btn)
        
        controls_layout.addStretch()
        
        layout.addWidget(controls, 1)
        
        # Right: Visualization
        self._sim_viz = SimulationVisualizationWidget()
        layout.addWidget(self._sim_viz, 3)
        
        return sim
    
    def _on_run_simulation(self):
        """Run ray tracing simulation"""
        active_system = self._current_assembly if self._current_assembly else self._current_lens
        if active_system:
            num_rays = int(self._sim_num_rays.value())
            angle = self._sim_angle.value()
            source_height = self._sim_source_height.value()
            show_ghosts = self._ghost_analysis.isChecked() if hasattr(self, '_ghost_analysis') else False
            
            # Get wavelength
            wavelength_idx = self._sim_wavelength.currentIndex()
            if wavelength_idx == 5:  # Custom
                wavelength = self._sim_custom_wavelength.value()
            else:
                wavelengths = [400, 450, 550, 650, 700]
                wavelength = wavelengths[wavelength_idx]
            
            self._sim_viz.run_simulation(active_system, num_rays, angle, source_height, show_ghosts, wavelength)
    
    def _on_wavelength_changed(self, index):
        """Show/hide custom wavelength input based on selection"""
        is_custom = (index == 5)
        self._sim_custom_label.setVisible(is_custom)
        self._sim_custom_wavelength.setVisible(is_custom)
        if is_custom:
            self._sim_custom_wavelength.setEnabled(True)
        else:
            self._sim_custom_wavelength.setEnabled(False)
    
    def _on_clear_simulation(self):
        """Clear simulation visualization"""
        self._sim_viz.clear_simulation()
    
    def _reset_simulation_view(self):
        """Reset the simulation view (zoom and pan)"""
        self._sim_viz.reset_view()
    
    def _create_performance_tab(self):
        """Create the Performance tab"""
        from src.aberrations import AberrationsCalculator
        
        perf = QWidget()
        
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
        metrics_layout = QVBoxLayout(metrics_group)
        
        self._perf_metrics_text = QTextEdit()
        self._perf_metrics_text.setReadOnly(True)
        self._perf_metrics_text.setMaximumHeight(200)
        self._perf_metrics_text.setStyleSheet("background-color: #2b2b2b; color: #e0e0e0; font-family: Courier; font-size: 10px;")
        self._perf_metrics_text.setPlainText("Select a lens and click 'Calculate Metrics' to view performance data.")
        metrics_layout.addWidget(self._perf_metrics_text)
        
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
        
        # Buttons - Row 2: Image Quality & Export
        btn_layout2 = QHBoxLayout()
        psf_btn = QPushButton("PSF Analysis")
        psf_btn.clicked.connect(self._on_show_psf)
        mtf_btn = QPushButton("MTF Analysis")
        mtf_btn.clicked.connect(self._on_show_mtf)
        wavefront_btn = QPushButton("Wavefront Map")
        wavefront_btn.clicked.connect(self._on_show_wavefront_map)
        export_btn = QPushButton("Export Report")
        export_btn.clicked.connect(self._on_export_performance_report)
        image_sim_btn = QPushButton("Image Simulation")
        image_sim_btn.clicked.connect(self._on_show_image_simulation)
        
        btn_layout2.addWidget(psf_btn)
        btn_layout2.addWidget(mtf_btn)
        btn_layout2.addWidget(wavefront_btn)
        btn_layout2.addWidget(export_btn)
        btn_layout2.addWidget(image_sim_btn)
        layout.addLayout(btn_layout2)
        
        layout.addStretch()
        
        # Set the content widget in the scroll area
        scroll.setWidget(content)
        
        # Add scroll area to main layout
        main_layout = QVBoxLayout(perf)
        main_layout.addWidget(scroll)
        
        return perf
    
    def _on_calculate_performance_metrics(self):
        """Calculate and display performance metrics for the active lens or assembly"""
        active_system = self._current_assembly if self._current_assembly else self._current_lens
        if not active_system:
            self._perf_metrics_text.setPlainText("No system selected.")
            return
        
        try:
            from src.aberrations import AberrationsCalculator
            from src.optical_system import OpticalSystem
            
            # 1. Prepare parameters
            wavelengths = [400, 450, 550, 650, 700]
            wavelength = wavelengths[self._perf_wavelength.currentIndex()]
            entrance_pupil = self._perf_entrance_pupil.value()
            object_distance = self._perf_object_distance.value()
            sensor_size = self._perf_sensor_size.value()
            
            # For multi-field metrics, we'll use a default max field angle based on sensor size or 20 deg
            # Or better, derive it from sensor size and focal length if possible
            
            # Wrap in OpticalSystem if it's just a lens
            if not isinstance(active_system, OpticalSystem):
                system = OpticalSystem(name=active_system.name)
                system.add_lens(active_system)
            else:
                system = active_system

            calculator = AberrationsCalculator(system)
            
            # Get optical properties
            # Note: For assemblies, we should use system-level focal length
            if hasattr(system, 'get_system_focal_length'):
                fl = system.get_system_focal_length()
            else:
                fl = active_system.calculate_focal_length()
                
            power = system.calculate_optical_power() if hasattr(system, 'calculate_optical_power') else active_system.calculate_optical_power()
            bfl = system.calculate_back_focal_length() if hasattr(system, 'calculate_back_focal_length') else active_system.calculate_back_focal_length()
            
            # Calculate aberrations (this now handles systems)
            # Use field angle derived from sensor size: theta = atan(sensor/2 / fl)
            field_angle = 0.0
            if fl and fl > 0:
                field_angle = math.degrees(math.atan((sensor_size / 2.0) / fl))
            
            results = calculator.calculate_all_aberrations(field_angle=field_angle)
            
            # Calculate chromatic focal shift if it's an assembly
            chromatic_text = ""
            if isinstance(active_system, OpticalSystem):
                chromatic = active_system.calculate_chromatic_aberration()
                if chromatic.get('longitudinal') is not None:
                    chromatic_text = f"Chromatic Focal Shift (C-F): {chromatic['longitudinal']:.4f} mm\n"
                    if 'bfl_d' in chromatic:
                        chromatic_text += f"  BFL (F=486nm): {chromatic['bfl_F']:.3f} mm\n"
                        chromatic_text += f"  BFL (d=587nm): {chromatic['bfl_d']:.3f} mm\n"
                        chromatic_text += f"  BFL (C=656nm): {chromatic['bfl_C']:.3f} mm\n"

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
            
            # Update status
            self._update_status(f"Calculated metrics for {system.name}")
                
        except Exception as e:
            import traceback
            logger.error(f"Performance calculation error: {e}\n{traceback.format_exc()}")
            self._perf_metrics_text.setPlainText(f"Error calculating metrics: {e}")

    
    def _on_show_spot_diagram(self):
        """Show spot diagram using SpotDiagram analyzer for active system"""
        active_system = self._current_assembly if self._current_assembly else self._current_lens
        if not active_system:
            QMessageBox.warning(self, "No Selection", "Please select a lens or assembly first")
            return
        
        try:
            from src.optical_system import OpticalSystem
            from src.analysis.spot_diagram import SpotDiagram
            
            # 1. Prepare parameters
            wavelengths_vals = [400, 450, 550, 650, 700]
            wavelength = wavelengths_vals[self._perf_wavelength.currentIndex()]
            entrance_pupil = self._perf_entrance_pupil.value()
            sensor_size = self._perf_sensor_size.value()
            
            # 2. Setup optical system
            if not isinstance(active_system, OpticalSystem):
                system = OpticalSystem(name=active_system.name)
                system.add_lens(active_system)
            else:
                system = active_system
            
            # 3. Create analyzer
            try:
                analyzer = SpotDiagram(system)
            except Exception as e:
                raise RuntimeError(f"Failed to initialize spot analyzer: {e}")
            
            # 4. Perform analysis (multi-field if possible)
            # For now, on-axis and max-field (derived from sensor)
            fl = system.get_system_focal_length() if hasattr(system, 'get_system_focal_length') else system.calculate_focal_length()
            max_field = 0.0
            if fl and fl > 0:
                max_field = math.degrees(math.atan((sensor_size / 2.0) / fl))

            # Sample wavelengths if we want chromatic spot diagram
            wavelengths = [wavelength]
            colors = ['#0078d4'] # Default blue
            
            # If d line (587) selected, maybe show F and C too?
            if wavelength == 550 or wavelength == 587 or wavelength == 450:
                # Show RGB-ish lines
                wavelengths = [656.3, 587.6, 486.1]
                colors = ['#ff0000', '#00ff00', '#0000ff'] # Red, Green, Blue

            def trace_multi_wl(field):
                all_pts = []
                stats = []
                for wl in wavelengths:
                    try:
                        res = analyzer.trace_spot(field_angle_y=field, wavelength=wl, num_rings=6)
                        if res['valid_rays'] > 0:
                            all_pts.append(res['points'])
                            stats.append(res)
                    except Exception as e:
                        logger.warning(f"Spot trace failed for {wl}nm at {field} deg: {e}")
                return all_pts, stats

            # Trace on-axis
            pts_on, stats_on = trace_multi_wl(0.0)
            if not pts_on:
                raise RuntimeError("No on-axis rays reached the image plane. Check for total internal reflection or blocked aperture.")
            
            # Trace off-axis
            pts_off, stats_off = trace_multi_wl(max_field) if max_field > 0 else ([], [])
            
            # 5. Show in dialog
            dialog = AnalysisPlotDialog(f"Spot Diagram - {system.name}", self)
            
            if pts_off:
                ax1 = dialog.get_axes(1, 2, 1)
                ax2 = dialog.get_axes(1, 2, 2)
                
                # On-axis
                for i, pts in enumerate(pts_on):
                    ax1.scatter([p[1]*1000 for p in pts], [p[0]*1000 for p in pts], 
                               s=8, alpha=0.5, color=colors[i % len(colors)], label=f"{wavelengths[i]}nm")
                ax1.set_aspect('equal')
                rms_val = stats_on[0]['rms_radius']*1000 if stats_on else 0
                ax1.set_title(f"On-axis (RMS={rms_val:.2f}µm)")
                ax1.grid(True, linestyle='--', alpha=0.3)
                
                # Off-axis
                for i, pts in enumerate(pts_off):
                    centroid = stats_off[i]['centroid']
                    ax2.scatter([(p[1]-centroid[1])*1000 for p in pts], [(p[0]-centroid[0])*1000 for p in pts], 
                               s=8, alpha=0.5, color=colors[i % len(colors)])
                ax2.set_aspect('equal')
                rms_val_off = stats_off[0]['rms_radius']*1000 if stats_off else 0
                ax2.set_title(f"Field {max_field:.1f}° (RMS={rms_val_off:.2f}µm)")
                ax2.grid(True, linestyle='--', alpha=0.3)
                ax1.legend(fontsize='x-small')
            else:
                ax = dialog.get_axes()
                for i, pts in enumerate(pts_on):
                    ax.scatter([p[1]*1000 for p in pts], [p[0]*1000 for p in pts], 
                               s=8, alpha=0.5, color=colors[i % len(colors)], label=f"{wavelengths[i]}nm")
                ax.set_aspect('equal')
                rms_val = stats_on[0]['rms_radius']*1000 if stats_on else 0
                ax.set_title(f"Spot Diagram (RMS={rms_val:.2f}µm)")
                ax.grid(True, linestyle='--', alpha=0.3)
                ax.legend(fontsize='x-small')
            
            dialog.exec()
            
        except Exception as e:
            logger.error(f"Spot diagram error: {e}")
            QMessageBox.critical(self, "Analysis Error", f"Failed to generate spot diagram: {e}")
    
    def _on_show_ray_fan(self):
        """Show ray fan plot using GeometricTraceAnalysis for active system"""
        active_system = self._current_assembly if self._current_assembly else self._current_lens
        if not active_system:
            QMessageBox.warning(self, "No Selection", "Please select a lens or assembly first")
            return
            
        try:
            from src.optical_system import OpticalSystem
            from src.analysis.geometric import GeometricTraceAnalysis
            
            # 1. Prepare parameters
            wavelengths_vals = [400, 450, 550, 650, 700]
            selected_wl = wavelengths_vals[self._perf_wavelength.currentIndex()]
            
            # 2. Setup optical system
            if not isinstance(active_system, OpticalSystem):
                system = OpticalSystem(name=active_system.name)
                system.add_lens(active_system)
            else:
                system = active_system
            
            # 3. Create analyzer
            analyzer = GeometricTraceAnalysis(system)
            
            # 4. Perform analysis
            dialog = AnalysisPlotDialog(f"Ray Fan - {system.name}", self)
            ax1 = dialog.get_axes(1, 2, 1) # Tangential
            ax2 = dialog.get_axes(1, 2, 2) # Sagittal
            
            # Use chromatic lines if appropriate
            wls = [selected_wl]
            colors = ['#0078d4']
            if selected_wl in [550, 587, 450]:
                wls = [486.1, 587.6, 656.3] # F, d, C
                colors = ['#0000ff', '#00ff00', '#ff0000']

            fan_success = False
            for i, wl in enumerate(wls):
                try:
                    # Tangential Fan (Pupil Y)
                    res_t = analyzer.calculate_ray_fan(field_angle=0.0, wavelength=wl, pupil_axis='y')
                    if res_t['ray_errors']:
                        ax1.plot(res_t['pupil_coords'], [e*1000 for e in res_t['ray_errors']], 
                                color=colors[i], label=f"{wl}nm" if i==0 else "")
                        fan_success = True
                    
                    # Sagittal Fan (Pupil Z)
                    res_s = analyzer.calculate_ray_fan(field_angle=0.0, wavelength=wl, pupil_axis='z')
                    if res_s['ray_errors']:
                        ax2.plot(res_s['pupil_coords'], [e*1000 for e in res_s['ray_errors']], 
                                color=colors[i])
                except Exception as e:
                    logger.warning(f"Ray fan trace failed for {wl}nm: {e}")

            if not fan_success:
                raise RuntimeError("No rays reached the image plane for the ray fan analysis. Verify system geometry and apertures.")

            ax1.axhline(0, color='gray', linestyle='-', linewidth=0.5)
            ax1.axvline(0, color='gray', linestyle='-', linewidth=0.5)
            ax1.set_xlabel("Normalized Pupil (Py)")
            ax1.set_ylabel("Transverse Error (µm)")
            ax1.set_title("Tangential Fan")
            ax1.grid(True, linestyle='--', alpha=0.3)
            
            ax2.axhline(0, color='gray', linestyle='-', linewidth=0.5)
            ax2.axvline(0, color='gray', linestyle='-', linewidth=0.5)
            ax2.set_xlabel("Normalized Pupil (Px)")
            ax2.set_ylabel("Transverse Error (µm)")
            ax2.set_title("Sagittal Fan")
            ax2.grid(True, linestyle='--', alpha=0.3)
            
            if len(wls) > 1:
                ax1.legend(fontsize='x-small')
                
            dialog.exec()
            
        except Exception as e:
            logger.error(f"Ray fan error: {e}")
            QMessageBox.critical(self, "Analysis Error", f"Failed to generate ray fan: {e}")


    def _on_show_field_curves(self):
        """Show field curves using GeometricTraceAnalysis for active system"""
        active_system = self._current_assembly if self._current_assembly else self._current_lens
        if not active_system:
            QMessageBox.warning(self, "No Selection", "Please select a lens or assembly first")
            return
            
        try:
            from src.optical_system import OpticalSystem
            from src.analysis.geometric import GeometricTraceAnalysis
            
            # 1. Prepare parameters
            wavelengths_vals = [400, 450, 550, 650, 700]
            wavelength = wavelengths_vals[self._perf_wavelength.currentIndex()]
            sensor_size = self._perf_sensor_size.value()
            
            # 2. Setup optical system
            if not isinstance(active_system, OpticalSystem):
                system = OpticalSystem(name=active_system.name)
                system.add_lens(active_system)
            else:
                system = active_system
            
            # 3. Create analyzer
            analyzer = GeometricTraceAnalysis(system)
            
            # 4. Perform analysis
            # Derive max field angle from sensor size
            fl = system.get_system_focal_length() if hasattr(system, 'get_system_focal_length') else system.calculate_focal_length()
            max_field = 20.0 # Default fallback
            if fl and fl > 0:
                max_field = math.degrees(math.atan((sensor_size / 2.0) / fl))

            res = analyzer.calculate_field_curvature_distortion(
                max_field_angle=max_field, num_points=11, wavelength=wavelength
            )
            
            # 5. Show in dialog
            dialog = AnalysisPlotDialog(f"Field Curvature & Distortion - {system.name}", self)
            
            # Subplot 1: Field Curvature
            ax1 = dialog.get_axes(1, 2, 1)
            ax1.plot(res['tan_focus_shift'], res['field_angles'], 'b-', label='Tangential')
            ax1.plot(res['sag_focus_shift'], res['field_angles'], 'r--', label='Sagittal')
            ax1.axvline(0, color='gray', linestyle='-', linewidth=0.5)
            ax1.set_xlabel("Focus Shift (mm)")
            ax1.set_ylabel("Field Angle (deg)")
            ax1.set_title("Field Curvature")
            ax1.legend()
            ax1.grid(True, linestyle='--', alpha=0.3)
            
            # Subplot 2: Distortion
            ax2 = dialog.get_axes(1, 2, 2)
            ax2.plot(res['distortion_pct'], res['field_angles'], 'g-')
            ax2.axvline(0, color='gray', linestyle='-', linewidth=0.5)
            ax2.set_xlabel("Distortion (%)")
            ax2.set_ylabel("Field Angle (deg)")
            ax2.set_title("Distortion")
            ax2.grid(True, linestyle='--', alpha=0.3)
            
            dialog.exec()
            
        except Exception as e:
            logger.error(f"Field curves error: {e}")
            QMessageBox.critical(self, "Analysis Error", f"Failed to generate field curves: {e}")
    
    def _draw_system_2d_on_axes(self, ax, system):
        """Helper to draw a multi-element system on Matplotlib axes (using same logic as 2D viz)"""
        import numpy as np
        for element in system.elements:
            lens = element.lens
            z_offset = element.position
            r1 = lens.radius_of_curvature_1
            r2 = lens.radius_of_curvature_2
            t = lens.thickness
            d = lens.diameter
            h = d / 2.0
            
            y_pts = np.linspace(-h, h, 100)
            
            # Helper to get sag at y (same as _2DVisualizationWidget)
            def get_sag(r, y):
                if abs(r) < 1e-6: return 0
                r_a = abs(r)
                y_safe = min(abs(y), r_a)
                sag = r_a - math.sqrt(max(0, r_a**2 - y_safe**2))
                return sag if r > 0 else -sag
            
            # Front surface
            x_front = z_offset + np.array([get_sag(r1, y) for y in y_pts])
            ax.plot(x_front, y_pts, 'w-', linewidth=1.5, alpha=0.8)
            
            # Back surface
            x_back = z_offset + t + np.array([get_sag(r2, y) for y in y_pts])
            ax.plot(x_back, y_pts, 'w-', linewidth=1.5, alpha=0.8)
            
            # Edge lines
            ax.plot([x_front[0], x_back[0]], [y_pts[0], y_pts[0]], 'w-', linewidth=1.5, alpha=0.8)
            ax.plot([x_front[-1], x_back[-1]], [y_pts[-1], y_pts[-1]], 'w-', linewidth=1.5, alpha=0.8)

    def _on_show_ghost_analysis(self):
        """Show ghost analysis using GhostAnalyzer for active system"""
        active_system = self._current_assembly if self._current_assembly else self._current_lens
        if not active_system:
            QMessageBox.warning(self, "No Selection", "Please select a lens or assembly first")
            return
            
        try:
            from src.optical_system import OpticalSystem
            from src.analysis.ghost import GhostAnalyzer
            
            # 1. Setup optical system
            if not isinstance(active_system, OpticalSystem):
                system = OpticalSystem(name=active_system.name)
                system.add_lens(active_system)
            else:
                system = active_system
            
            # 2. Create analyzer
            analyzer = GhostAnalyzer(system)
            
            # 3. Perform analysis
            ghost_paths = analyzer.trace_ghosts(num_rays=11)
            
            # 4. Show in dialog
            dialog = AnalysisPlotDialog(f"Ghost Analysis - {system.name}", self)
            ax = dialog.get_axes()
            
            # Draw system geometry
            self._draw_system_2d_on_axes(ax, system)

            # Trace and plot each ghost path
            colors = ['#ff0000', '#ff8000', '#ffff00', '#00ff00', '#00ffff', '#0000ff', '#ff00ff']
            for i, path in enumerate(ghost_paths[:7]): # Limit to first 7 paths for clarity
                color = colors[i % len(colors)]
                label = f"Ghost {path.reflection_1_index}->{path.reflection_2_index} (I={path.intensity:.4f})"
                
                for ray in path.rays:
                    x_vals = [p.x for p in ray.path]
                    y_vals = [p.y for p in ray.path]
                    ax.plot(x_vals, y_vals, '-', color=color, alpha=0.3, linewidth=0.5)
                
                # Plot one representative ray for the legend
                if path.rays:
                    ax.plot([], [], '-', color=color, label=label)
            
            ax.set_aspect('equal')
            ax.set_xlabel("X (mm)")
            ax.set_ylabel("Y (mm)")
            ax.set_title(f"Ghost Reflection Paths (2nd Order)")
            ax.legend(fontsize='x-small', loc='upper right')
            ax.grid(True, linestyle='--', alpha=0.3)
            
            dialog.exec()
            
        except Exception as e:
            logger.error(f"Ghost analysis error: {e}")
            QMessageBox.critical(self, "Analysis Error", f"Failed to generate ghost analysis: {e}")
    
    def _on_show_psf(self):
        """Show PSF analysis using ImageQualityAnalyzer for active system"""
        active_system = self._current_assembly if self._current_assembly else self._current_lens
        if not active_system:
            QMessageBox.warning(self, "No Selection", "Please select a lens or assembly first")
            return
            
        try:
            from src.optical_system import OpticalSystem
            from src.analysis.psf_mtf import ImageQualityAnalyzer
            
            # 1. Prepare parameters
            wavelengths_vals = [400, 450, 550, 650, 700]
            wavelength = wavelengths_vals[self._perf_wavelength.currentIndex()]
            
            # 2. Setup optical system
            if not isinstance(active_system, OpticalSystem):
                system = OpticalSystem(name=active_system.name)
                system.add_lens(active_system)
            else:
                system = active_system
            
            # 3. Create analyzer
            analyzer = ImageQualityAnalyzer(system)
            
            # 4. Perform analysis
            # We sample a small area around the chief ray intersection
            psf_data = analyzer.calculate_psf(field_angle=0.0, wavelength=wavelength, pixels=64)
            
            # 5. Show in dialog
            dialog = AnalysisPlotDialog(f"Point Spread Function - {system.name}", self)
            ax = dialog.get_axes(projection='3d')
            
            # Create grid for plotting
            import numpy as np
            # Use correct keys from calculate_psf() return dict
            z_axis = psf_data.get('z_axis', np.linspace(-0.05, 0.05, 64))
            y_axis = psf_data.get('y_axis', np.linspace(-0.05, 0.05, 64))
            X, Y = np.meshgrid(z_axis, y_axis)
            Z = psf_data.get('image', np.zeros((64, 64)))
            
            # Normalize Z
            if Z.max() > 0:
                Z = Z / Z.max()
            
            surf = ax.plot_surface(X, Y, Z, cmap='viridis', edgecolor='none', alpha=0.8)
            ax.set_xlabel("X (µm)")
            ax.set_ylabel("Y (µm)")
            ax.set_zlabel("Relative Intensity")
            ax.set_title(f"PSF (λ={wavelength}nm)")
            
            dialog.exec()
            
        except Exception as e:
            logger.error(f"PSF error: {e}")
            QMessageBox.critical(self, "Analysis Error", f"Failed to generate PSF: {e}")

    def _on_show_mtf(self):
        """Show MTF analysis using ImageQualityAnalyzer for active system"""
        active_system = self._current_assembly if self._current_assembly else self._current_lens
        if not active_system:
            QMessageBox.warning(self, "No Selection", "Please select a lens or assembly first")
            return
            
        try:
            from src.optical_system import OpticalSystem
            from src.analysis.psf_mtf import ImageQualityAnalyzer
            
            # 1. Prepare parameters
            wavelengths_vals = [400, 450, 550, 650, 700]
            wavelength = wavelengths_vals[self._perf_wavelength.currentIndex()]
            sensor_size = self._perf_sensor_size.value()
            
            # 2. Setup optical system
            if not isinstance(active_system, OpticalSystem):
                system = OpticalSystem(name=active_system.name)
                system.add_lens(active_system)
            else:
                system = active_system
            
            # 3. Create analyzer
            analyzer = ImageQualityAnalyzer(system)
            
            # 4. Perform analysis
            # Derive max field angle
            fl = system.get_system_focal_length() if hasattr(system, 'get_system_focal_length') else system.calculate_focal_length()
            max_field = 0.0
            if fl and fl > 0:
                max_field = math.degrees(math.atan((sensor_size / 2.0) / fl))

            # Calculate MTF for 0, 0.7, and 1.0 field
            fields = [0.0, max_field * 0.7, max_field] if max_field > 0 else [0.0]
            
            dialog = AnalysisPlotDialog(f"Modulation Transfer Function - {system.name}", self)
            ax = dialog.get_axes()
            
            styles = ['-', '--', ':']
            colors = ['#0078d4', '#ff7800', '#2b88d8']
            
            for i, field in enumerate(fields):
                res = analyzer.calculate_mtf(field_angle=field, wavelength=wavelength)
                freqs = res['freq']
                mtf_tan = res['mtf_tan']
                mtf_sag = res['mtf_sag']
                
                label_base = f"Field {field:.1f}°"
                ax.plot(freqs, mtf_tan, color=colors[i % len(colors)], linestyle='-', label=f"{label_base} (T)")
                ax.plot(freqs, mtf_sag, color=colors[i % len(colors)], linestyle='--', label=f"{label_base} (S)")

            # Add diffraction limit (theoretical)
            # Axial resolution limit at this wavelength
            diffraction_cutoff = 1.0 / (wavelength * 1e-6) if wavelength else 100
            ax.axvline(x=diffraction_cutoff, color='gray', linestyle=':', alpha=0.3, label="Diffraction Limit")

            ax.set_xlabel("Spatial Frequency (lp/mm)")
            ax.set_ylabel("Modulation")
            ax.set_title(f"MTF (λ={wavelength}nm)")
            ax.set_ylim(0, 1.05)
            ax.legend(fontsize='x-small')
            ax.grid(True, linestyle='--', alpha=0.3)
            
            dialog.exec()
            
        except Exception as e:
            logger.error(f"MTF error: {e}")
            QMessageBox.critical(self, "Analysis Error", f"Failed to generate MTF: {e}")

    
    def _on_show_wavefront_map(self):
        """Show wavefront map using WavefrontSensor for active system"""
        active_system = self._current_assembly if self._current_assembly else self._current_lens
        if not active_system:
            QMessageBox.warning(self, "No Selection", "Please select a lens or assembly first")
            return
            
        try:
            from src.optical_system import OpticalSystem
            from src.analysis.diffraction_psf import WavefrontSensor
            
            # 1. Prepare parameters
            wavelengths_vals = [400, 450, 550, 650, 700]
            wavelength = wavelengths_vals[self._perf_wavelength.currentIndex()]
            
            # 2. Setup optical system
            if not isinstance(active_system, OpticalSystem):
                system = OpticalSystem(name=active_system.name)
                system.add_lens(active_system)
            else:
                system = active_system
            
            # 3. Create sensor
            sensor = WavefrontSensor(system)
            
            # 4. Perform analysis
            # grid_size 64 is enough for visualization
            wf = sensor.get_pupil_wavefront(
                field_angle=0.0, 
                wavelength=wavelength * 1e-6, 
                grid_size=64
            )
            
            # 5. Show in dialog
            dialog = AnalysisPlotDialog(f"Wavefront Error - {system.name}", self)
            ax = dialog.get_axes()
            
            # Heatmap of W (nan handled by imshow)
            import numpy as np
            im = ax.imshow(wf.W, extent=[
                wf.Z.min(), wf.Z.max(), wf.Y.min(), wf.Y.max()
            ], cmap='RdBu_r', origin='lower')
            
            ax.set_xlabel("Pupil X (mm)")
            ax.set_ylabel("Pupil Y (mm)")
            ax.set_title(f"Wavefront Error (λ={wavelength}nm)")
            
            # Add contour lines
            if not np.all(np.isnan(wf.W)):
                ax.contour(wf.W, levels=10, colors='k', alpha=0.3, extent=[
                    wf.Z.min(), wf.Z.max(), wf.Y.min(), wf.Y.max()
                ], origin='lower')
            
            # Add colorbar
            dialog.figure.colorbar(im, ax=ax, label='OPD (Waves)')
            
            dialog.exec()
            
        except Exception as e:
            logger.error(f"Performance analysis error: {e}")
            QMessageBox.critical(self, "Analysis Error", f"Operation failed: {e}")

    def _on_export_performance_report(self):
        """Export performance report"""
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        if not self._current_lens:
            QMessageBox.warning(self, "No Lens", "Please select a lens first")
            return
        
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Export Performance Report", f"{self._current_lens.name}_performance.txt",
            "Text Files (*.txt)"
        )
        
        if not filepath:
            return
        
        try:
            with open(filepath, 'w') as f:
                f.write(self._perf_metrics_text.toPlainText())
            QMessageBox.information(self, "Export Complete", f"Exported to {filepath}")
        except Exception as e:
            logger.error(f"Export error: {e}")
            QMessageBox.critical(self, "Export Error", f"Failed to export report: {e}")

    def _on_show_image_simulation(self):
        """Show image simulation by loading a custom image and applying lens blur for active system"""
        active_system = self._current_assembly if self._current_assembly else self._current_lens
        if not active_system:
            QMessageBox.warning(self, "No Selection", "Please select a lens or assembly first")
            return
            
        try:
            from PySide6.QtWidgets import QFileDialog, QInputDialog
            from src.analysis.psf_mtf import ImageQualityAnalyzer
            from src.optical_system import OpticalSystem
            import numpy as np
            from PIL import Image
            import os
            
            # Prepare System
            if isinstance(active_system, OpticalSystem):
                system = active_system
            else:
                system = OpticalSystem(name=active_system.name)
                system.add_lens(active_system)

            # 1. Select source (Pattern or File)
            source_type, ok = QInputDialog.getItem(self, "Image Simulation", 
                                                "Select Image Source:", ["Geometric Patterns", "Load Image File..."], 0, False)
            if not ok:
                return
                
            input_image = None
            title_suffix = ""
            
            if source_type == "Load Image File...":
                filepath, _ = QFileDialog.getOpenFileName(self, "Select Image", "", "Images (*.png *.jpg *.jpeg *.bmp *.tif)")
                if not filepath:
                    return
                # Load and convert to RGB
                img = Image.open(filepath).convert('RGB')
                # Resize if too large for performance
                if max(img.size) > 512:
                    img.thumbnail((512, 512))
                input_image = np.array(img).astype(float) / 255.0
                title_suffix = f"File: {os.path.basename(filepath)}"
            else:
                # Select pattern
                patterns = ["Star", "Grid", "USAF 1951"]
                pattern, ok = QInputDialog.getItem(self, "Image Simulation", "Select Pattern:", patterns, 0, False)
                if not ok:
                    return
                
                size = 512
                input_image = np.zeros((size, size, 3))
                cx, cy = size // 2, size // 2
                title_suffix = f"Pattern: {pattern}"
                
                if pattern == "Star":
                    import math
                    for i in range(36):
                        angle = i * 10 * math.pi / 180
                        x2 = int(cx + 200 * math.cos(angle))
                        y2 = int(cy + 200 * math.sin(angle))
                        # Simple line drawing
                        for t in np.linspace(0, 1, 400):
                            px = int(cx + t * (x2 - cx))
                            py = int(cy + t * (y2 - cy))
                            if 0 <= px < size and 0 <= py < size:
                                input_image[py, px, :] = 1.0
                elif pattern == "Grid":
                    for i in range(0, size, 40):
                        input_image[i, :, :] = 1.0
                        input_image[:, i, :] = 1.0
                elif pattern == "USAF 1951":
                    # Simplified USAF-like pattern
                    for i in range(4):
                        s = 40 // (i + 1)
                        input_image[cy-100:cy-100+s, cx-100:cx-100+3*s:2*s, :] = 1.0
                        input_image[cy-100:cy-100+3*s:2*s, cx-100:cx-100+s, :] = 1.0

            # 2. Run simulation using ImageQualityAnalyzer
            analyzer = ImageQualityAnalyzer(system)
            
            # Parameters
            wavelengths = (656.3, 587.6, 486.1) # R, G, B
            field = 0.0
            defocus = 0.0
            pixel_size = 0.005 # 5 microns
            
            self._update_status("Running simulation... this may take a moment.")
            QApplication.setOverrideCursor(Qt.WaitCursor)
            
            try:
                simulated = analyzer.simulate_image(
                    input_image,
                    pixel_size=pixel_size,
                    wavelengths=wavelengths,
                    field_angle=field,
                    focus_shift=defocus
                )
            finally:
                QApplication.restoreOverrideCursor()

            # 3. Show in dialog
            dialog = AnalysisPlotDialog(f"Image Simulation - {system.name}", self)
            ax = dialog.get_axes()
            
            # Show original and blurred side-by-side
            fig = dialog.figure
            fig.clear()
            ax1 = fig.add_subplot(121)
            ax2 = fig.add_subplot(122)
            
            ax1.imshow(input_image)
            ax1.set_title("Original")
            ax1.axis('off')
            
            ax2.imshow(simulated)
            ax2.set_title("Simulated Performance")
            ax2.axis('off')
            
            fig.suptitle(f"Optical Simulation: {title_suffix}\nSystem: {system.name}")
            fig.tight_layout()
            
            dialog.exec()
            
        except Exception as e:
            logger.error(f"Image simulation error: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Analysis Error", f"Failed to generate image simulation: {e}")

    def _update_performance_metrics(self):
        """Update performance metrics for current lens or assembly"""
        if not self._current_lens and not self._current_assembly:
            return
        
        try:
            from src.optical_system import OpticalSystem
            from src.aberrations import AberrationsCalculator

            if self._current_assembly:
                system = self._current_assembly
                name = system.name
            else:
                system = OpticalSystem(name="Temporary")
                system.add_lens(self._current_lens)
                name = self._current_lens.name

            # Use system-level properties where possible
            fl = system.get_system_focal_length() if hasattr(system, 'get_system_focal_length') else system.calculate_focal_length()
            fl_text = f"{fl:.2f} mm" if fl else "Infinite"
            
            power = system.calculate_optical_power() if hasattr(system, 'calculate_optical_power') else system.elements[0].lens.calculate_optical_power()
            power_text = f"{power:.4f} D" if power else "-"
            
            bfl = system.calculate_back_focal_length() if hasattr(system, 'calculate_back_focal_length') else system.elements[0].lens.calculate_back_focal_length()
            bfl_text = f"{bfl:.2f} mm" if bfl else "-"
            
            calculator = AberrationsCalculator(system)
            results = calculator.calculate_all_aberrations()
            
            # Update individual labels if they exist (for backward compatibility)
            if hasattr(self, '_perf_long_focal'):
                self._perf_long_focal.setText(fl_text)
            if hasattr(self, '_perf_power'):
                self._perf_power.setText(power_text)
            if hasattr(self, '_perf_back_focal'):
                self._perf_back_focal.setText(bfl_text)
            if hasattr(self, '_perf_spherical'):
                self._perf_spherical.setText(f"{results.get('spherical', 0):.4f} mm")
            if hasattr(self, '_perf_coma'):
                self._perf_coma.setText(f"{results.get('coma', 0):.4f} mm")
            if hasattr(self, '_perf_astig'):
                self._perf_astig.setText(f"{results.get('astigmatism', 0):.4f} mm")
            if hasattr(self, '_perf_distortion'):
                self._perf_distortion.setText(f"{results.get('distortion', 0):.2f} %")
            if hasattr(self, '_perf_mtfc'):
                self._perf_mtfc.setText(f"{results.get('mtf_cutoff', 0):.1f} lp/mm")
            
            # Update text display if it exists
            if hasattr(self, '_perf_metrics_text'):
                text = f"""=== OPTICAL PERFORMANCE METRICS ===
{ 'Assembly' if self._current_assembly else 'Lens' }: {name}

--- Basic Optical Properties ---
Focal Length: {fl_text}
Optical Power: {power_text}
Back Focal Length: {bfl_text}
"""
                if not self._current_assembly:
                    text += f"Diameter: {system.elements[0].lens.diameter:.2f} mm\n"
                    text += f"Thickness: {system.elements[0].lens.thickness:.2f} mm\n"
                
                text += f"""
--- Primary Aberrations ---
Spherical Aberration: {results.get('spherical', 0):.4f} mm
Coma: {results.get('coma', 0):.4f} mm
Astigmatism: {results.get('astigmatism', 0):.4f} mm
Distortion: {results.get('distortion', 0):.2f} %
Chromatic Aberration: {results.get('chromatic', 0):.4f} mm

--- Image Quality Metrics ---
MTF Cutoff: {results.get('mtf_cutoff', 0):.1f} lp/mm
Strehl Ratio: {results.get('strehl', 0):.3f}
Spot Size (RMS): {results.get('spot_rms', 0):.3f} µm
"""
                self._perf_metrics_text.setPlainText(text)
            
        except Exception as e:
            logger.error(f"Performance update error: {e}")


    def _create_optimization_tab(self):
        """Create the Optimization tab with support for both single lenses and assemblies"""
        from src.optimizer import LensOptimizer, OptimizationVariable, OptimizationTarget
        
        opt = QWidget()
        
        # Create scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none;")
        
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Variables Section - Now dynamic for Assemblies
        self._opt_vars_group = QGroupBox("Optimization Variables")
        self._opt_vars_container = QVBoxLayout(self._opt_vars_group)
        self._opt_vars_scroll = QScrollArea()
        self._opt_vars_scroll.setWidgetResizable(True)
        self._opt_vars_scroll.setMinimumHeight(150)
        self._opt_vars_widget = QWidget()
        self._opt_vars_layout = QVBoxLayout(self._opt_vars_widget)
        self._opt_vars_scroll.setWidget(self._opt_vars_widget)
        self._opt_vars_container.addWidget(self._opt_vars_scroll)
        
        # Targets Section
        targets_group = QGroupBox("Optimization Targets")
        targets_layout = QFormLayout(targets_group)
        
        self._opt_target_fl_enabled = QCheckBox("Target Focal Length (mm):")
        self._opt_target_fl_enabled.setChecked(True)
        self._opt_target_fl = QDoubleSpinBox()
        self._opt_target_fl.setRange(1, 10000)
        self._opt_target_fl.setValue(50)
        
        self._opt_target_fl_enabled.toggled.connect(self._opt_target_fl.setEnabled)
        targets_layout.addRow(self._opt_target_fl_enabled, self._opt_target_fl)
        
        self._opt_target_spot = QCheckBox("Minimize RMS Spot Size")
        self._opt_target_spot.setChecked(True)
        targets_layout.addRow("Spot Size:", self._opt_target_spot)
        
        self._opt_target_spherical = QCheckBox("Minimize Spherical Aberration")
        targets_layout.addRow("Spherical:", self._opt_target_spherical)
        
        self._opt_target_coma = QCheckBox("Minimize Coma")
        targets_layout.addRow("Coma:", self._opt_target_coma)
        
        self._opt_target_astig = QCheckBox("Minimize Astigmatism")
        targets_layout.addRow("Astigmatism:", self._opt_target_astig)
        
        # Layout organization
        top_row_layout = QHBoxLayout()
        top_row_layout.addWidget(self._opt_vars_group, 1)
        top_row_layout.addWidget(targets_group, 1)
        layout.addLayout(top_row_layout)
        
        # Constraints and Results side-by-side
        middle_row_layout = QHBoxLayout()
        
        # Constraints Section
        constraints_group = QGroupBox("Constraints & Options")
        constraints_layout = QFormLayout(constraints_group)
        
        self._opt_min_thickness = QDoubleSpinBox()
        self._opt_min_thickness.setRange(0.1, 50)
        self._opt_min_thickness.setValue(1.0)
        self._opt_min_thickness.setSuffix(" mm")
        constraints_layout.addRow("Min Thickness:", self._opt_min_thickness)
        
        self._opt_max_thickness = QDoubleSpinBox()
        self._opt_max_thickness.setRange(1, 500)
        self._opt_max_thickness.setValue(50)
        self._opt_max_thickness.setSuffix(" mm")
        constraints_layout.addRow("Max Thickness:", self._opt_max_thickness)
        
        self._opt_min_edge = QDoubleSpinBox()
        self._opt_min_edge.setRange(0.1, 20)
        self._opt_min_edge.setValue(0.5)
        self._opt_min_edge.setSuffix(" mm")
        constraints_layout.addRow("Min Edge Thickness:", self._opt_min_edge)
        
        self._opt_min_gap = QDoubleSpinBox()
        self._opt_min_gap.setRange(0, 100)
        self._opt_min_gap.setValue(0.1)
        self._opt_min_gap.setSuffix(" mm")
        constraints_layout.addRow("Min Air Gap:", self._opt_min_gap)
        
        self._opt_algorithm = QComboBox()
        self._opt_algorithm.addItems(["Local (Simplex)", "Global (Simulated Annealing)", "Global (Genetic Algorithm)"])
        self._opt_algorithm.setCurrentIndex(0)
        constraints_layout.addRow("Algorithm:", self._opt_algorithm)
        
        self._opt_robust = QCheckBox("Robust Mode (Yield Optimization)")
        constraints_layout.addRow("", self._opt_robust)
        
        # Results display
        results_group = QGroupBox("Optimization Results")
        results_layout = QVBoxLayout(results_group)
        
        self._opt_results_text = QTextEdit()
        self._opt_results_text.setReadOnly(True)
        self._opt_results_text.setMinimumHeight(150)
        self._opt_results_text.setStyleSheet("background-color: #2b2b2b; color: #e0e0e0; font-family: Courier; font-size: 10px;")
        results_layout.addWidget(self._opt_results_text)
        
        middle_row_layout.addWidget(constraints_group, 1)
        middle_row_layout.addWidget(results_group, 1)
        layout.addLayout(middle_row_layout)
        
        # Buttons
        btn_layout = QHBoxLayout()
        run_opt_btn = QPushButton("Run Optimization")
        run_opt_btn.clicked.connect(self._on_run_optimization)
        stop_btn = QPushButton("Stop")
        stop_btn.clicked.connect(self._on_stop_optimization)
        self._opt_apply_btn = QPushButton("Apply&Keep")
        self._opt_apply_btn.setEnabled(False)
        self._opt_apply_btn.clicked.connect(self._on_apply_optimization)
        reset_btn = QPushButton("Reset to Original")
        reset_btn.clicked.connect(self._on_reset_optimization)
        btn_layout.addWidget(run_opt_btn)
        btn_layout.addWidget(stop_btn)
        btn_layout.addWidget(self._opt_apply_btn)
        btn_layout.addWidget(reset_btn)
        layout.addLayout(btn_layout)
        
        # Visualization (Dual Support)
        self._opt_lens_viz = _2DVisualizationWidget()
        self._opt_asm_viz = AssemblyVisualizationWidget()
        self._opt_asm_viz.setVisible(False)
        layout.addWidget(self._opt_lens_viz)
        layout.addWidget(self._opt_asm_viz)
        
        layout.addStretch()
        
        scroll.setWidget(content)
        main_layout = QVBoxLayout(opt)
        main_layout.addWidget(scroll)
        
        self._opt_is_running = False
        self._opt_original_target = None
        self._opt_pending_target = None
        
        # Variables map for dynamic checkboxes
        self._opt_check_vars = {} # key -> QCheckBox
        
        return opt

    def _refresh_optimization_variables(self):
        """Update the variables list based on current selection (Lens or Assembly)"""
        # Clear existing
        while self._opt_vars_layout.count():
            child = self._opt_vars_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self._opt_check_vars.clear()
        
        active_target = self._current_assembly if self._current_assembly else self._current_lens
        if not active_target:
            self._opt_vars_layout.addWidget(QLabel("No system selected"))
            return

        from src.optical_system import OpticalSystem
        
        if isinstance(active_target, OpticalSystem):
            self._opt_lens_viz.setVisible(False)
            self._opt_asm_viz.setVisible(True)
            self._opt_asm_viz.update_system(active_target)
            
            for i, element in enumerate(active_target.elements):
                lens_name = element.lens.name or f"Lens {i+1}"
                group = QGroupBox(f"{i+1}. {lens_name}")
                vbox = QVBoxLayout(group)
                
                for label, param, key in [
                    ("Radius 1", "radius_of_curvature_1", f"r1_{i}"),
                    ("Radius 2", "radius_of_curvature_2", f"r2_{i}"),
                    ("Thickness", "thickness", f"th_{i}"),
                    ("Refractive Index", "refractive_index", f"n_{i}")
                ]:
                    val = getattr(element.lens, param)
                    cb = QCheckBox(f"{label} ({val:.2f})")
                    cb.setChecked(label in ["Radius 1", "Radius 2"])
                    self._opt_check_vars[key] = cb
                    vbox.addWidget(cb)
                
                # Air Gap
                if i < len(active_target.air_gaps):
                    gap_val = active_target.air_gaps[i].thickness
                    cb = QCheckBox(f"Air Gap to Next ({gap_val:.2f})")
                    self._opt_check_vars[f"gap_{i}"] = cb
                    vbox.addWidget(cb)
                    
                self._opt_vars_layout.addWidget(group)
        else:
            self._opt_lens_viz.setVisible(True)
            self._opt_asm_viz.setVisible(False)
            self._opt_lens_viz.update_lens(active_target)
            
            group = QGroupBox("Lens Properties")
            vbox = QVBoxLayout(group)
            for label, param, key in [
                ("Radius 1", "radius_of_curvature_1", "r1_0"),
                ("Radius 2", "radius_of_curvature_2", "r2_0"),
                ("Thickness", "thickness", "th_0"),
                ("Refractive Index", "refractive_index", "n_0"),
                ("Diameter", "diameter", "d_0")
            ]:
                val = getattr(active_target, param)
                cb = QCheckBox(f"{label} ({val:.2f})")
                cb.setChecked(label in ["Radius 1", "Radius 2", "Thickness"])
                self._opt_check_vars[key] = cb
                vbox.addWidget(cb)
            self._opt_vars_layout.addWidget(group)
            
        self._opt_vars_layout.addStretch()
    
    def _on_stop_optimization(self):
        """Stop the currently running optimization"""
        if self._opt_is_running:
            # We don't have a direct kill mechanism for the optimizer thread yet,
            # but we can set the flag so the UI knows we are 'done'
            self._opt_is_running = False
            self._opt_results_text.setPlainText("Optimization stopped by user.")
            self._update_status("Optimization stopped.")
            self._opt_apply_btn.setEnabled(False)

    def _on_run_optimization(self):
        """Run system optimization using LensOptimizer or GlobalOptimizer"""
        from src.optimizer import OptimizationVariable, OptimizationTarget
        try:
            from src.global_optimizer import GlobalOptimizer
            HAS_GLOBAL = True
        except ImportError:
            from src.optimizer import LensOptimizer as GlobalOptimizer
            HAS_GLOBAL = False

        active_target = self._current_assembly if self._current_assembly else self._current_lens
        if not active_target:
            self._opt_results_text.setPlainText("No system selected.")
            return
        
        if self._opt_is_running:
            self._opt_results_text.setPlainText("Optimization already running.")
            return
        
        self._opt_is_running = True
        self._opt_original_target = active_target
        self._opt_pending_target = None
        self._opt_apply_btn.setEnabled(False)
        
        # Collect variables from dynamic checkboxes
        variables = []
        from src.optical_system import OpticalSystem
        
        if isinstance(active_target, OpticalSystem):
            for i, element in enumerate(active_target.elements):
                if self._opt_check_vars.get(f"r1_{i}").isChecked():
                    variables.append(OptimizationVariable(f"R1_L{i+1}", i, "radius_of_curvature_1", element.lens.radius_of_curvature_1, -10000, 10000))
                if self._opt_check_vars.get(f"r2_{i}").isChecked():
                    variables.append(OptimizationVariable(f"R2_L{i+1}", i, "radius_of_curvature_2", element.lens.radius_of_curvature_2, -10000, 10000))
                if self._opt_check_vars.get(f"th_{i}").isChecked():
                    variables.append(OptimizationVariable(f"Th_L{i+1}", i, "thickness", element.lens.thickness, self._opt_min_thickness.value(), self._opt_max_thickness.value()))
                if self._opt_check_vars.get(f"n_{i}").isChecked():
                    variables.append(OptimizationVariable(f"N_L{i+1}", i, "refractive_index", element.lens.refractive_index, 1.3, 2.4))
                if self._opt_check_vars.get(f"gap_{i}") and self._opt_check_vars.get(f"gap_{i}").isChecked():
                    variables.append(OptimizationVariable(f"Gap_{i+1}_{i+2}", i, "air_gap", active_target.air_gaps[i].thickness, self._opt_min_gap.value(), 500))
        else:
            if self._opt_check_vars.get("r1_0").isChecked():
                variables.append(OptimizationVariable("Radius 1", 0, "radius_of_curvature_1", active_target.radius_of_curvature_1, -10000, 10000))
            if self._opt_check_vars.get("r2_0").isChecked():
                variables.append(OptimizationVariable("Radius 2", 0, "radius_of_curvature_2", active_target.radius_of_curvature_2, -10000, 10000))
            if self._opt_check_vars.get("th_0").isChecked():
                variables.append(OptimizationVariable("Thickness", 0, "thickness", active_target.thickness, self._opt_min_thickness.value(), self._opt_max_thickness.value()))
            if self._opt_check_vars.get("n_0").isChecked():
                variables.append(OptimizationVariable("Index", 0, "refractive_index", active_target.refractive_index, 1.3, 2.4))
            if self._opt_check_vars.get("d_0") and self._opt_check_vars.get("d_0").isChecked():
                variables.append(OptimizationVariable("Diameter", 0, "diameter", active_target.diameter, 1, 500))
        
        if not variables:
            self._opt_results_text.setPlainText("Select at least one variable.")
            self._opt_is_running = False
            return
        
        # Collect targets
        targets = []
        if self._opt_target_fl_enabled.isChecked():
            targets.append(OptimizationTarget('focal_length', self._opt_target_fl.value(), weight=1.0, target_type="target"))
        if self._opt_target_spot.isChecked():
            targets.append(OptimizationTarget('spot_size', 0, weight=1.0, target_type="minimize"))
        if self._opt_target_spherical.isChecked():
            targets.append(OptimizationTarget('spherical', 0, weight=1.0, target_type="minimize"))
        if self._opt_target_coma.isChecked():
            targets.append(OptimizationTarget('coma', 0, weight=1.0, target_type="minimize"))
        if self._opt_target_astig.isChecked():
            targets.append(OptimizationTarget('astigmatism', 0, weight=1.0, target_type="minimize"))
        
        if not targets:
            self._opt_results_text.setPlainText("Select at least one target.")
            self._opt_is_running = False
            return
        
        # Build constraints
        constraints = {}
        constraints['min_center_thickness'] = self._opt_min_thickness.value()
        constraints['max_center_thickness'] = self._opt_max_thickness.value()
        constraints['min_edge_thickness'] = self._opt_min_edge.value()
        constraints['min_air_gap'] = self._opt_min_gap.value()
        
        self._opt_results_text.setPlainText("Optimizing...")
        
        def run_optimization_thread():
            try:
                from src.optical_system import OpticalSystem
                import copy
                
                # Setup system
                if isinstance(active_target, OpticalSystem):
                    system = copy.deepcopy(active_target)
                else:
                    system = OpticalSystem(name="Optimization")
                    system.add_lens(copy.deepcopy(active_target))
                
                optimizer = GlobalOptimizer(system, variables, targets, constraints=constraints)
                
                # Run optimization based on algorithm selection
                algorithm = self._opt_algorithm.currentText()
                if "Simplex" in algorithm:
                    result = optimizer.optimize(max_iterations=100)
                elif "Simulated" in algorithm:
                    result = optimizer.optimize_simulated_annealing(max_iterations=500)
                elif "Genetic" in algorithm:
                    result = optimizer.optimize_genetic(population_size=30, generations=30)
                else:
                    result = optimizer.optimize(max_iterations=100)
                
                # Emit signals
                self.opt_finished.emit(result, variables)
                                       
            except Exception as e:
                import traceback
                error_details = traceback.format_exc()
                logger.error(f"Optimization error:\n{error_details}")
                self.opt_failed.emit(str(e))

        import threading
        thread = threading.Thread(target=run_optimization_thread, daemon=True)
        thread.start()

    @Slot(object, list)
    def _on_optimization_finished(self, result, variables):
        """Callback for finished optimization"""
        self._opt_is_running = False
        from src.optical_system import OpticalSystem
        
        if result.success:
            text = f"Optimization Successful!\n\n"
            text += f"Final Merit Function: {result.final_merit:.4f}\n"
            text += f"Iterations: {result.iterations}\n\n"
            text += "Optimized Values (Preview):\n"
            
            # Show parameter changes
            if result.optimized_system:
                self._opt_pending_target = result.optimized_system
                self._opt_apply_btn.setEnabled(True)
                
                if isinstance(result.optimized_system, OpticalSystem):
                    self._opt_asm_viz.update_system(result.optimized_system)
                    for var in variables:
                        if var.parameter == "air_gap":
                            val = result.optimized_system.air_gaps[var.element_index].thickness
                        else:
                            val = getattr(result.optimized_system.elements[var.element_index].lens, var.parameter)
                        text += f"  {var.name}: {val:.4f}\n"
                else:
                    # Case where it returns just a lens? (Unlikely with SystemOptimizer but handle it)
                    lens = result.optimized_system.elements[0].lens if hasattr(result.optimized_system, 'elements') else result.optimized_system
                    self._opt_lens_viz.update_lens(lens)
                    for var in variables:
                        val = getattr(lens, var.parameter)
                        text += f"  {var.name}: {val:.4f}\n"
            
            self._opt_results_text.setPlainText(text)
            self._opt_results_text.append("\nClick 'Apply & Keep' to save these changes.")
        else:
            self._opt_results_text.setPlainText(f"Optimization failed: {result.message}")

    @Slot(str)
    def _on_optimization_failed(self, message):
        """Callback for failed optimization"""
        self._opt_is_running = False
        self._opt_results_text.setPlainText(f"Optimization Error: {message}")
        self._update_status(f"Optimization failed: {message}")

    def _on_apply_optimization(self):
        """Apply the optimization results to the current system"""
        if self._opt_pending_target:
            from src.optical_system import OpticalSystem
            if isinstance(self._opt_pending_target, OpticalSystem):
                self._current_assembly = self._opt_pending_target
                self._optical_system = self._opt_pending_target
                self._assembly_viz.update_system(self._current_assembly)
            else:
                self._current_lens = self._opt_pending_target
                self._lens_editor.load_lens(self._current_lens)
            
            self._update_all_tabs()
            self._opt_apply_btn.setEnabled(False)
            self._opt_pending_target = None
            self._opt_results_text.append("\nChanges applied to system.")
            self._save_to_database()

    def _on_reset_optimization(self):
        """Reset optimization to original values"""
        if self._opt_original_target:
            from src.optical_system import OpticalSystem
            if isinstance(self._opt_original_target, OpticalSystem):
                self._current_assembly = self._opt_original_target
                self._optical_system = self._opt_original_target
                self._opt_asm_viz.update_system(self._current_assembly)
            else:
                self._current_lens = self._opt_original_target
                self._opt_lens_viz.update_lens(self._current_lens)
            
            self._update_all_tabs()
            self._opt_results_text.setPlainText("Reset to original values.")
            self._opt_apply_btn.setEnabled(False)
            self._opt_pending_target = None
        else:
            self._opt_results_text.setPlainText("No original state to reset to.")
    
    def _create_tolerancing_tab(self):
        """Create the Tolerancing tab"""
        from src.tolerancing import MonteCarloAnalyzer, InverseSensitivityAnalyzer, ToleranceOperand, ToleranceType
        
        tol = QWidget()
        
        # Create scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none;")
        
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(10, 10, 10, 10)
        
        title = QLabel("Tolerancing Analysis")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)
        
        # Main split: Left (Operands) and Right (Analysis)
        split_layout = QHBoxLayout()
        
        # Left Panel: Tolerance Operands
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        left_layout.addWidget(QLabel("Tolerance Operands"))
        
        # Toolbar
        toolbar = QWidget()
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        
        add_btn = QPushButton("Add Tolerance")
        add_btn.clicked.connect(self._on_add_tolerance)
        remove_btn = QPushButton("Remove")
        remove_btn.clicked.connect(self._on_remove_tolerance)
        clear_btn = QPushButton("Clear All")
        clear_btn.clicked.connect(self._on_clear_tolerances)
        default_btn = QPushButton("Default Set")
        default_btn.clicked.connect(self._on_add_default_tolerances)
        
        toolbar_layout.addWidget(add_btn)
        toolbar_layout.addWidget(remove_btn)
        toolbar_layout.addWidget(clear_btn)
        toolbar_layout.addWidget(default_btn)
        left_layout.addWidget(toolbar)
        
        # Operands table
        from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView
        self._tol_table = QTableWidget()
        self._tol_table.setColumnCount(5)
        self._tol_table.setHorizontalHeaderLabels(["Element #", "Type", "Min", "Max", "Distribution"])
        self._tol_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._tol_table.setEditTriggers(QTableWidget.DoubleClicked)
        self._tol_table.itemChanged.connect(self._on_tol_item_changed)
        self._tol_table.setStyleSheet("background-color: #2b2b2b; color: #e0e0e0; font-family: Courier; font-size: 10px;")
        left_layout.addWidget(QLabel("Operands (Double-click to edit Min/Max):"))
        left_layout.addWidget(self._tol_table)
        
        # Right Panel: Analysis
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        right_layout.addWidget(QLabel("Analysis & Yield"))
        
        # Monte Carlo Settings
        mc_group = QGroupBox("Monte Carlo Settings")
        mc_layout = QFormLayout(mc_group)
        
        self._tol_num_trials = QSpinBox()
        self._tol_num_trials.setRange(10, 10000)
        self._tol_num_trials.setValue(100)
        mc_layout.addRow("Number of Trials:", self._tol_num_trials)
        
        self._tol_criterion = QDoubleSpinBox()
        self._tol_criterion.setRange(0.001, 1)
        self._tol_criterion.setValue(0.05)
        self._tol_criterion.setSuffix(" mm")
        mc_layout.addRow("Criterion Limit (RMS):", self._tol_criterion)
        
        right_layout.addWidget(mc_group)
        
        # Action Buttons
        btn_layout = QHBoxLayout()
        run_mc_btn = QPushButton("Run Monte Carlo")
        run_mc_btn.clicked.connect(self._on_run_monte_carlo)
        run_inv_btn = QPushButton("Inverse Sensitivity")
        run_inv_btn.clicked.connect(self._on_run_inverse_sensitivity)
        
        btn_layout.addWidget(run_mc_btn)
        btn_layout.addWidget(run_inv_btn)
        right_layout.addLayout(btn_layout)
        
        # Progress Bar
        from PySide6.QtWidgets import QProgressBar
        self._tol_progress = QProgressBar()
        self._tol_progress.setRange(0, 100)
        self._tol_progress.setValue(0)
        self._tol_progress.setVisible(False)
        right_layout.addWidget(self._tol_progress)
        
        # Results
        results_group = QGroupBox("Results")
        results_layout = QVBoxLayout(results_group)
        
        self._tol_results_text = QTextEdit()
        self._tol_results_text.setReadOnly(True)
        self._tol_results_text.setMinimumHeight(200)
        self._tol_results_text.setStyleSheet("background-color: #2b2b2b; color: #e0e0e0; font-family: Courier; font-size: 10px;")
        self._tol_results_text.setPlainText("Configure tolerances and click 'Run Monte Carlo' or 'Inverse Sensitivity' to analyze.")
        results_layout.addWidget(self._tol_results_text)
        
        right_layout.addWidget(results_group)
        
        # Add panels to split
        split_layout.addWidget(left_panel, 1)
        split_layout.addWidget(right_panel, 1)
        
        layout.addLayout(split_layout)
        
        # Store tolerancing data
        self._tol_operands = []
        
        layout.addStretch()
        
        # Set the content widget in the scroll area
        scroll.setWidget(content)
        
        # Add scroll area to main layout
        main_layout = QVBoxLayout(tol)
        main_layout.addWidget(scroll)
        
        return tol
    
    def _on_add_tolerance(self):
        """Add a new tolerance operand with element selection"""
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QFormLayout, QComboBox, QDoubleSpinBox, QPushButton
        
        if not self._current_lens:
            return
            
        dialog = QDialog(self)
        dialog.setWindowTitle("Add Tolerance Operand")
        layout = QVBoxLayout(dialog)
        form = QFormLayout()
        
        # Element selection
        num_elements = 1
        if hasattr(self._current_lens, 'elements'):
            num_elements = len(self._current_lens.elements)
        
        elem_combo = QComboBox()
        elem_combo.addItems([str(i) for i in range(num_elements)])
        form.addRow("Element Index:", elem_combo)
        
        # Type selection
        from src.tolerancing import ToleranceType, ToleranceOperand
        type_combo = QComboBox()
        type_combo.addItems([t.value for t in ToleranceType])
        form.addRow("Parameter Type:", type_combo)
        
        # Min/Max
        min_spin = QDoubleSpinBox()
        min_spin.setRange(-10, 10)
        min_spin.setDecimals(4)
        min_spin.setValue(-0.1)
        form.addRow("Min Deviation:", min_spin)
        
        max_spin = QDoubleSpinBox()
        max_spin.setRange(-10, 10)
        max_spin.setDecimals(4)
        max_spin.setValue(0.1)
        form.addRow("Max Deviation:", max_spin)
        
        # Distribution
        dist_combo = QComboBox()
        dist_combo.addItems(["uniform", "gaussian"])
        form.addRow("Distribution:", dist_combo)
        
        layout.addLayout(form)
        
        add_btn = QPushButton("Add")
        add_btn.clicked.connect(dialog.accept)
        layout.addWidget(add_btn)
        
        if dialog.exec():
            p_type = None
            for member in ToleranceType:
                if member.value == type_combo.currentText():
                    p_type = member
                    break
            
            operand = ToleranceOperand(
                element_index=int(elem_combo.currentText()),
                param_type=p_type,
                min_val=min_spin.value(),
                max_val=max_spin.value(),
                distribution=dist_combo.currentText()
            )
            self._tol_operands.append(operand)
            self._update_tolerance_operands_display()

    def _on_add_default_tolerances(self):
        """Add standard tolerances for all elements in the system"""
        from src.tolerancing import ToleranceType, ToleranceOperand
        
        if not self._current_lens:
            return
            
        num_elements = 1
        if hasattr(self._current_lens, 'elements'):
            num_elements = len(self._current_lens.elements)
            
        new_operands = []
        for i in range(num_elements):
            new_operands.extend([
                ToleranceOperand(i, ToleranceType.RADIUS_1, -0.1, 0.1),
                ToleranceOperand(i, ToleranceType.RADIUS_2, -0.1, 0.1),
                ToleranceOperand(i, ToleranceType.THICKNESS, -0.05, 0.05),
                ToleranceOperand(i, ToleranceType.DECENTER_Y, -0.05, 0.05),
                ToleranceOperand(i, ToleranceType.TILT_X, -0.1, 0.1),
            ])
        
            self._tol_operands.extend(new_operands)
        self._update_tolerance_operands_display()

    def _on_remove_tolerance(self):
        """Remove selected tolerance operands from the table"""
        selected_rows = sorted(set(index.row() for index in self._tol_table.selectedIndexes()), reverse=True)
        if not selected_rows and self._tol_operands:
            # Fallback to removing last row if nothing selected
            self._tol_operands.pop()
        else:
            for row in selected_rows:
                if row < len(self._tol_operands):
                    self._tol_operands.pop(row)
        
        self._update_tolerance_operands_display()

    def _on_clear_tolerances(self):
        """Clear all tolerance operands"""
        from PySide6.QtWidgets import QMessageBox
        if not self._tol_operands:
            return
            
        if QMessageBox.question(self, "Clear All", "Are you sure you want to clear all tolerance operands?",
                               QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self._tol_operands = []
            self._update_tolerance_operands_display()

    def _on_tol_item_changed(self, item):
        """Handle manual edits in the tolerance table"""
        row = item.row()
        col = item.column()
        if row < len(self._tol_operands) and col in (2, 3):
            try:
                val = float(item.text())
                if col == 2:
                    self._tol_operands[row].min_val = val
                else:
                    self._tol_operands[row].max_val = val
            except ValueError:
                # Revert if invalid
                self._update_tolerance_operands_display()

    def _update_tolerance_operands_display(self):
        """Update the operands table display"""
        from PySide6.QtWidgets import QTableWidgetItem
        from PySide6.QtCore import Qt
        
        self._tol_table.blockSignals(True)
        self._tol_table.setRowCount(len(self._tol_operands))
        
        for i, op in enumerate(self._tol_operands):
            # Element #
            item = QTableWidgetItem(str(op.element_index))
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            self._tol_table.setItem(i, 0, item)
            
            # Type
            item = QTableWidgetItem(op.param_type.value)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            self._tol_table.setItem(i, 1, item)
            
            # Min
            self._tol_table.setItem(i, 2, QTableWidgetItem(f"{op.min_val:+.4f}"))
            
            # Max
            self._tol_table.setItem(i, 3, QTableWidgetItem(f"{op.max_val:+.4f}"))
            
            # Distribution
            dist = getattr(op, 'distribution', 'uniform')
            item = QTableWidgetItem(dist)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            self._tol_table.setItem(i, 4, item)
            
        self._tol_table.blockSignals(False)

    def _on_run_monte_carlo(self):
        """Run Monte Carlo analysis in a thread to keep UI responsive"""
        if not self._current_lens:
            self._tol_results_text.setPlainText("No lens selected.")
            return
        
        if not self._tol_operands:
            self._tol_results_text.setPlainText("No tolerance operands defined.")
            return
        
        self._tol_results_text.setPlainText(f"Starting Monte Carlo analysis ({self._tol_num_trials.value()} trials)...")
        self._tol_progress.setVisible(True)
        self._tol_progress.setValue(0)
        
        import threading
        thread = threading.Thread(target=self._run_mc_worker, daemon=True)
        thread.start()

    def _run_mc_worker(self):
        """Worker thread for Monte Carlo analysis"""
        from src.tolerancing import MonteCarloAnalyzer
        from src.optical_system import OpticalSystem
        from PySide6.QtCore import QMetaObject, Qt, Q_ARG
        import copy
        
        try:
            # Copy system for thread safety
            system = OpticalSystem(name="Tolerancing")
            system.add_lens(copy.deepcopy(self._current_lens))
            
            analyzer = MonteCarloAnalyzer(system, self._tol_operands)
            num_trials = self._tol_num_trials.value()
            criterion = self._tol_criterion.value()
            
            # Run analysis
            results = analyzer.run_monte_carlo(num_trials=num_trials, criterion=criterion)
            
            # Format report
            text = f"=== MONTE CARLO RESULTS ===\n\n"
            text += f"Total Trials: {results['total_trials']}\n"
            text += f"Passed (Yield): {results['passed_trials']} ({results['yield_percent']:.1f}%)\n"
            text += f"Failed: {results['failed_trials']}\n"
            text += f"RMS Spot Size - Mean: {results['mean_rms']:.4f} mm\n"
            text += f"RMS Spot Size - Std Dev: {results['std_rms']:.4f} mm\n"
            text += f"RMS Spot Size - Max: {results['max_rms']:.4f} mm\n"
            text += f"RMS Spot Size - Min: {results['min_rms']:.4f} mm\n"
            
            # Update UI from thread
            QMetaObject.invokeMethod(self, "_on_analysis_finished", 
                                   Qt.QueuedConnection,
                                   Q_ARG(str, text),
                                   Q_ARG(dict, results))
            
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            QMetaObject.invokeMethod(self, "_on_analysis_failed",
                                   Qt.QueuedConnection,
                                   Q_ARG(str, f"Monte Carlo Error: {e}\n{error_details}"))

    @Slot(str, dict)
    def _on_analysis_finished(self, text, results):
        """Callback for finished analysis"""
        self._tol_results_text.setPlainText(text)
        self._tol_progress.setValue(100)
        self._tol_progress.setVisible(False)
        
        # Show histogram
        num_trials = results.get('total_trials', 100)
        criterion = self._tol_criterion.value()
        
        dialog = AnalysisPlotDialog(f"Monte Carlo Distribution - {self._current_lens.name}", self)
        ax = dialog.get_axes()
        
        all_rms = results.get('all_rms', [])
        if all_rms:
            import numpy as np
            ax.hist(all_rms, bins=max(10, num_trials // 10), color='skyblue', edgecolor='black', alpha=0.7)
            ax.axvline(criterion, color='red', linestyle='--', label=f'Criterion ({criterion})')
            ax.axvline(results['mean_rms'], color='green', linestyle='-', label=f'Mean ({results["mean_rms"]:.4f})')
            ax.set_xlabel("RMS Spot Size (mm)")
            ax.set_ylabel("Frequency")
            ax.set_title("Monte Carlo Yield Distribution")
            ax.legend()
            ax.grid(True, linestyle='--', alpha=0.3)
            dialog.exec()

    @Slot(str)
    def _on_analysis_failed(self, error_msg):
        """Callback for failed analysis"""
        self._tol_results_text.setPlainText(error_msg)
        self._tol_progress.setVisible(False)

    def _on_run_inverse_sensitivity(self):
        """Run Inverse Sensitivity analysis in a thread"""
        if not self._current_lens:
            self._tol_results_text.setPlainText("No lens selected.")
            return
        
        if not self._tol_operands:
            self._tol_results_text.setPlainText("No tolerance operands defined.")
            return
        
        self._tol_results_text.setPlainText("Starting Inverse Sensitivity analysis...")
        self._tol_progress.setVisible(True)
        self._tol_progress.setMinimum(0)
        self._tol_progress.setMaximum(0) # Busy indicator
        
        import threading
        thread = threading.Thread(target=self._run_inv_worker, daemon=True)
        thread.start()

    def _run_inv_worker(self):
        """Worker thread for Inverse Sensitivity"""
        from src.tolerancing import InverseSensitivityAnalyzer
        from src.optical_system import OpticalSystem
        from PySide6.QtCore import QMetaObject, Qt, Q_ARG
        import copy
        
        try:
            system = OpticalSystem(name="Tolerancing")
            system.add_lens(copy.deepcopy(self._current_lens))
            
            analyzer = InverseSensitivityAnalyzer(system, self._tol_operands)
            criterion = self._tol_criterion.value()
            
            # Use RSS method as in Tkinter version
            results = analyzer.optimize_limits(target_yield_criterion=criterion, method='rss')
            
            text = f"=== INVERSE SENSITIVITY RESULTS ===\n\n"
            text += f"Target Yield Criterion: {criterion} mm RMS\n\n"
            text += "Suggested Limits (RSS budget):\n"
            text += "-" * 55 + "\n"
            text += f"{'Elem':<5} | {'Type':<20} | {'Limit (+/-)':<10}\n"
            text += "-" * 55 + "\n"
            for op in results:
                text += f"{op.element_index:<5} | {op.param_type.value:<20} | {op.max_val:10.4f}\n"
            
            QMetaObject.invokeMethod(self, "_on_analysis_finished", 
                                   Qt.QueuedConnection,
                                   Q_ARG(str, text),
                                   Q_ARG(dict, {}))
                                   
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            QMetaObject.invokeMethod(self, "_on_analysis_failed",
                                   Qt.QueuedConnection,
                                   Q_ARG(str, f"Inverse Sensitivity Error: {e}\n{error_details}"))
    
    def _on_calculate_tolerances(self):
        """Calculate tolerance sensitivities"""
        if not self._current_lens:
            return
        
        delta_r = self._tol_surface_sig.value()
        delta_t = self._tol_thickness_sig.value()
        delta_n = self._tol_index_sig.value()
        
        try:
            r1_orig = self._current_lens.radius_of_curvature_1
            
            self._current_lens.radius_of_curvature_1 = r1_orig + delta_r
            fl_plus = self._current_lens.calculate_focal_length()
            
            self._current_lens.radius_of_curvature_1 = r1_orig - delta_r
            fl_minus = self._current_lens.calculate_focal_length()
            
            self._current_lens.radius_of_curvature_1 = r1_orig
            
            if fl_plus and fl_minus:
                fl_sens = abs(fl_plus - fl_minus) / (2 * delta_r)
                self._tol_fl_sens.setText(f"{fl_sens:.4f} mm/mm")
            
            pow_plus = self._current_lens.calculate_optical_power()
            if pow_plus:
                self._tol_power_sens.setText(f"{pow_plus:.6f} D/%")
            
            t_orig = self._current_lens.thickness
            self._current_lens.thickness = t_orig + delta_t
            bfl = self._current_lens.calculate_back_focal_length()
            self._current_lens.thickness = t_orig
            
            if bfl:
                self._tol_bfl_sens.setText(f"{bfl:.4f} mm")
                
        except Exception as e:
            print(f"Tolerance calculation error: {e}")
    
    def _create_assembly_editor(self):
        """Create the assembly editor tab"""
        from src.optical_system import OpticalSystem
        
        assembly = QWidget()
        layout = QHBoxLayout(assembly)
        
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
        
        # Populate lens list
        for lens in self._lenses:
            self._assembly_lens_list.addItem(lens.name)
        
        return assembly
    
    def _on_add_lens_to_system(self):
        """Add selected lens to optical system"""
        current = self._assembly_lens_list.currentRow()
        if current >= 0:
            lens = self._lenses[current]
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

    def _on_assembly_changed(self):
        """Handle assembly change, update other tabs if in assembly mode"""
        if self._current_assembly:
             # If we are currently editing an assembly, other tabs should reflect it
             self._update_all_tabs()

    
    def _update_system_list(self):
        """Update the system list"""
        self._system_list.blockSignals(True)
        self._system_list.clear()
        for i, element in enumerate(self._optical_system.elements):
            lens = element.lens
            self._system_list.addItem(f"{i}: {lens.name} (n={lens.refractive_index:.3f})")
        self._system_list.blockSignals(False)

    def _on_system_item_selected(self, index):
        """Handle selection in the system list to show air gap editor"""
        if index >= 0 and index < len(self._optical_system.elements):
            # Element 0 has no 'air_gap_before' in the current model logic usually,
            # but let's check the OpticalSystem structure.
            # In OpticalSystem.add_lens(air_gap_before=...) it seems to store it in self.air_gaps.
            
            # Show/Enable air gap editor for any element > 0
            if index > 0:
                self._air_gap_group.setEnabled(True)
                # Air gap index is usually index - 1 (gap between element index-1 and index)
                gap_idx = index - 1
                if gap_idx < len(self._optical_system.air_gaps):
                    gap = self._optical_system.air_gaps[gap_idx]
                    self._air_gap_input.blockSignals(True)
                    self._air_gap_input.setValue(gap.thickness)
                    self._air_gap_input.blockSignals(False)
            else:
                self._air_gap_group.setEnabled(False)
        else:
            self._air_gap_group.setEnabled(False)

    def _on_air_gap_changed(self, value):
        """Handle air gap thickness change"""
        index = self._system_list.currentRow()
        if index > 0:
            gap_idx = index - 1
            if gap_idx < len(self._optical_system.air_gaps):
                self._optical_system.air_gaps[gap_idx].thickness = value
                self._assembly_viz.update_system(self._optical_system)
                self._on_assembly_changed()
                
                # Auto-save to database
                if hasattr(self, '_save_to_database'):
                    self._save_to_database()
    
    def _load_default_lens(self):
        """Load default lens on startup"""
        if self._lenses:
            self._current_lens = self._lenses[0]
            self._current_assembly = None
        else:
            lens = Lens(name="Default Lens")
            self._lenses.append(lens)
            self._current_lens = lens
        
        self._show_assembly_editor(False)
        self._update_lens_list()
        self._lens_editor.load_lens(self._current_lens)
    
    def _on_toggle_mode(self):
        """Toggle between Lens and Assembly mode"""
        is_lens_mode = self._mode_toggle.isChecked() if hasattr(self, '_mode_toggle') else True
        
        if is_lens_mode:
            self._mode_toggle.setText("Lens")
            self._show_assembly_editor(False)
            self._update_status("Mode: Single Lens")
        else:
            self._mode_toggle.setText("Assembly")
            self._show_assembly_editor(True)
            self._update_status("Mode: Multi-lens Assembly")
    
    def _set_current_item(self, item, is_assembly=False):
        """Set current item (lens or assembly)"""
        if is_assembly:
            self._current_assembly = item
            self._current_lens = None
            self._show_assembly_editor(True)
            self._editor_tabs.setCurrentIndex(1)
            self._load_assembly(item)
            self._update_status(f"Selected: {item.name} ({len(item.elements)} elements)")
        else:
            self._current_lens = item
            self._current_assembly = None
            self._show_assembly_editor(False)
            self._editor_tabs.setCurrentIndex(0)  # Switch to Lens Editor
            self._lens_editor.load_lens(item)
            self._update_all_tabs()
            self._update_status(f"Selected: {item.name}")
    
    def _update_lens_list(self):
        """Update internal lens list (list widget removed)"""
        pass
    
    def _on_lens_selected(self, row):
        """Handle lens/assembly selection (deprecated - list removed)"""
        pass
    
    def _load_assembly(self, assembly):
        """Load assembly into assembly editor"""
        if hasattr(self, '_optical_system'):
            self._optical_system = assembly
        if hasattr(self, '_assembly_viz'):
            self._assembly_viz.update_system(assembly)
        if hasattr(self, '_system_list'):
            self._update_system_list()
    
    def _update_all_tabs(self):
        """Update all tab displays for current lens or assembly"""
        if not self._current_lens and not self._current_assembly:
            return
        
        active_system = self._current_assembly if self._current_assembly else self._current_lens

        if hasattr(self, '_sim_viz'):
            self._on_run_simulation()
        
        if hasattr(self, '_opt_vars_layout'):
            self._refresh_optimization_variables()
        
        if hasattr(self, '_tol_viz') and hasattr(self._tol_viz, 'update_lens'):
            target = self._current_lens if self._current_lens else self._current_assembly.elements[0].lens
            self._tol_viz.update_lens(target)
        
        self._update_performance_metrics()

    
    def _on_new_lens(self):
        """Create new lens"""
        lens = Lens(name=f"Lens {len(self._lenses) + 1}")
        self._lenses.append(lens)
        self._current_lens = lens
        self._current_assembly = None
        self._update_lens_list()
        self._editor_tabs.setCurrentIndex(0)  # Go to Lens Editor
        self._lens_editor.load_lens(lens)
        self._update_all_tabs()
        self._update_status(f"Created: {lens.name}")
    
    def _on_new_assembly(self):
        """Create new assembly"""
        from src.optical_system import OpticalSystem
        asm = OpticalSystem(name=f"Assembly {len(self._assemblies) + 1}")
        self._assemblies.append(asm)
        self._current_assembly = asm
        self._current_lens = None
        self._optical_system = asm
        self._update_lens_list()
        self._show_assembly_editor(True)
        self._editor_tabs.setCurrentIndex(1)
        self._update_system_list()
        self._assembly_viz.update_system(asm)
        self._update_status(f"Created: {asm.name}")
    
    def _on_delete_lens(self):
        """Delete current lens or assembly"""
        if self._current_lens:
            if len(self._lenses) > 1:
                idx = self._lenses.index(self._current_lens)
                self._lenses.pop(idx)
                self._current_lens = self._lenses[0]
                self._current_assembly = None
                self._lens_editor.load_lens(self._current_lens)
                self._update_all_tabs()
                self._update_status(f"Deleted. Now editing: {self._current_lens.name}")
            else:
                self._update_status("Cannot delete the last lens")
        elif self._current_assembly:
            idx = self._assemblies.index(self._current_assembly)
            self._assemblies.pop(idx)
            if self._assemblies:
                self._current_assembly = self._assemblies[0]
            else:
                self._current_assembly = None
            self._update_status("Deleted assembly")
    
    def _on_open(self):
        """Open from database - just reload"""
        self._load_from_database()
        self._update_lens_list()
        if self._current_lens:
            self._lens_editor.load_lens(self._current_lens)
        self._update_status("Reloaded from database")
    
    def _on_save(self):
        """Save to database"""
        self._save_to_database()
        self._update_status("Saved to database")
    
    def _on_save_as(self):
        """Save lens with new filename"""
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        
        if not self._current_lens:
            return
        
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Save Lens As", f"{self._current_lens.name}.json", 
            "JSON Files (*.json);;All Files (*)"
        )
        
        if not filepath:
            return
        
        try:
            import json
            data = self._current_lens.to_dict()
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save file: {e}")
    
    def _on_export_stl(self):
        """Export lens to STL file"""
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        
        if not self._current_lens:
            QMessageBox.warning(self, "No Selection", "Please select a lens first")
            return
        
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Export to STL", f"{self._current_lens.name}.stl",
            "STL Files (*.stl)"
        )
        
        if not filepath:
            return
        
        try:
            import numpy as np
            self._export_lens_stl(filepath)
            QMessageBox.information(self, "Export Complete", f"Exported to {filepath}")
        except ImportError:
            QMessageBox.warning(self, "Missing Dependency", "STL export requires numpy. Install with: pip install numpy")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export: {e}")
    
    def _export_lens_stl(self, filepath):
        """Export lens to STL mesh"""
        import numpy as np
        
        lens = self._current_lens
        r1 = lens.radius_of_curvature_1
        r2 = lens.radius_of_curvature_2
        thickness = lens.thickness
        diameter = lens.diameter
        
        vertices = []
        triangles = []
        
        num_segments = 24
        num_rings = 12
        
        for ring in range(num_rings + 1):
            v = ring / num_rings
            y = -diameter/2 + diameter * v
            
            if abs(r1) > 1e6:
                x1 = 0
            else:
                r1_abs = abs(r1)
                if r1 > 0:
                    x1 = r1 - (r1_abs**2 - y**2)**0.5
                else:
                    x1 = -(r1_abs - (r1_abs**2 - y**2)**0.5)
            
            if abs(r2) > 1e6:
                x2 = thickness
            else:
                r2_abs = abs(r2)
                if r2 > 0:
                    x2 = thickness + r2 - (r2_abs**2 - y**2)**0.5
                else:
                    x2 = thickness - (r2_abs - (r2_abs**2 - y**2)**0.5)
            
            for seg in range(num_segments):
                u = seg / num_segments
                theta = 2 * 3.14159 * u
                
                x = x1 + (x2 - x1) * v
                vx = x + y * 0
                vy = y * np.cos(theta)
                vz = y * np.sin(theta)
                vertices.append((vx, vy, vz))
        
        for ring in range(num_rings):
            for seg in range(num_segments):
                i = ring * num_segments + seg
                j = ring * num_segments + (seg + 1) % num_segments
                k = (ring + 1) * num_segments + (seg + 1) % num_segments
                l = (ring + 1) * num_segments + seg
                
                triangles.append((i, j, k))
                triangles.append((i, k, l))
        
        if triangles:
            data = np.zeros(len(triangles), dtype=[('v1', 'i4', 3), ('v2', 'i4', 3), ('v3', 'i4', 3)])
            for i, (a, b, c) in enumerate(triangles):
                data['v1'][i] = vertices[a]
                data['v2'][i] = vertices[b]
                data['v3'][i] = vertices[c]
            
            from numpy import GenBinaryBinaryWriter
            writer = GenBinaryBinaryWriter(filepath)
            writer.write(data)
            writer.close()
        else:
            with open(filepath, 'w') as f:
                f.write("solid model\n")
                f.write("endsolid model\n")
    
    def _on_export_step(self):
        """Export lens to STEP file"""
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        
        if not self._current_lens:
            QMessageBox.warning(self, "No Selection", "Please select a lens first")
            return
        
        QMessageBox.information(self, "Export STEP", "STEP export coming soon")
    
    def _on_export_iso10110(self):
        """Export lens to ISO 10110 format"""
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        
        if not self._current_lens:
            QMessageBox.warning(self, "No Selection", "Please select a lens first")
            return
        
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Export to ISO 10110", f"{self._current_lens.name}.txt",
            "Text Files (*.txt);;All Files (*)"
        )
        
        if not filepath:
            return
        
        try:
            with open(filepath, 'w') as f:
                f.write(f"Lens: {self._current_lens.name}\n")
                f.write(f"Material: {self._current_lens.material}\n")
                f.write(f"Index: {self._current_lens.refractive_index}\n")
                f.write(f"Diameter: {self._current_lens.diameter} mm\n")
                f.write(f"Thickness: {self._current_lens.thickness} mm\n")
                f.write(f"Radius 1: {self._current_lens.radius_of_curvature_1} mm\n")
                f.write(f"Radius 2: {self._current_lens.radius_of_curvature_2} mm\n")
            QMessageBox.information(self, "Export Complete", f"Exported to {filepath}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to export: {e}")
    
    def _on_export_report(self):
        """Export lens report"""
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        
        if not self._current_lens:
            QMessageBox.warning(self, "No Selection", "Please select a lens first")
            return
        
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Export Report", f"{self._current_lens.name}_report.txt",
            "Text Files (*.txt)"
        )
        
        if not filepath:
            return
        
        try:
            with open(filepath, 'w') as f:
                f.write("=" * 50 + "\n")
                f.write(f"Lens Report: {self._current_lens.name}\n")
                f.write("=" * 50 + "\n\n")
                
                f.write("Physical Properties:\n")
                f.write(f"  Diameter: {self._current_lens.diameter:.2f} mm\n")
                f.write(f"  Thickness: {self._current_lens.thickness:.2f} mm\n")
                f.write(f"  Radius 1: {self._current_lens.radius_of_curvature_1:.2f} mm\n")
                f.write(f"  Radius 2: {self._current_lens.radius_of_curvature_2:.2f} mm\n")
                f.write(f"  Material: {self._current_lens.material}\n")
                f.write(f"  Refractive Index: {self._current_lens.refractive_index:.4f}\n\n")
                
                fl = self._current_lens.calculate_focal_length()
                if fl:
                    f.write("Optical Properties:\n")
                    f.write(f"  Focal Length: {fl:.2f} mm\n")
                
                power = self._current_lens.calculate_optical_power()
                if power:
                    f.write(f"  Optical Power: {power:.4f} D\n")
            
            QMessageBox.information(self, "Export Complete", f"Exported to {filepath}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to export: {e}")
    
    def _on_about(self):
        """Show about dialog"""
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.about(self, "About OpenLens", 
            "OpenLens - Optical Lens Design\n\n"
            "Version 2.0 (PySide6)\n\n"
            "A modern optical lens design and simulation tool.\n\n"
            "Features:\n"
            "- Lens editor with live visualization\n"
            "- Ray tracing simulation\n"
            "- Performance metrics\n"
            "- Optimization\n"
            "- Tolerancing\n\n"
            "Migrated from Tkinter to PySide6")
    
    def _on_show_shortcuts(self):
        """Show keyboard shortcuts"""
        from PySide6.QtWidgets import QMessageBox
        shortcuts = """
Keyboard Shortcuts
================

Ctrl+N         New Lens
Ctrl+O         Open
Ctrl+S         Save
Ctrl+Shift+S   Save As
Ctrl+D         Duplicate Lens
Ctrl+T         Toggle Theme
Ctrl+0         Reset Window
Delete        Delete Lens

Tab Switching:
Ctrl+1         Lens Editor
Ctrl+2         Assembly Editor  
Ctrl+3         Simulation
Ctrl+4         Performance
Ctrl+5         Optimization
Ctrl+6         Tolerancing
"""
        QMessageBox.information(self, "Keyboard Shortcuts", shortcuts)
    
    def _on_duplicate_lens(self):
        """Duplicate current lens"""
        if not self._current_lens:
            return
        
        data = self._current_lens.to_dict()
        data['name'] = f"{self._current_lens.name} (copy)"
        new_lens = Lens.from_dict(data)
        
        new_lens.id = f"{new_lens.id}_copy"
        
        self._lenses.append(new_lens)
        self._current_lens = new_lens
        self._update_lens_list()
        self._lens_editor.load_lens(new_lens)
        self._update_all_tabs()
        self._save_to_database()
        self._update_status(f"Duplicated: {new_lens.name}")
    
    def _on_undo(self):
        """Undo last action (placeholder)"""
        self._update_status("Undo not implemented in this version")
    
    def _on_redo(self):
        """Redo last action (placeholder)"""
        self._update_status("Redo not implemented in this version")
    
    def _on_toggle_theme(self):
        """Toggle between dark and light theme"""
        from PySide6.QtWidgets import QApplication
        
        app = QApplication.instance()
        current = getattr(self, '_theme', 'dark')
        
        if current == 'dark':
            self._theme = 'light'
            app.setStyleSheet("""
                QMainWindow {
                    background-color: #f5f5f5;
                }
                QWidget {
                    background-color: #f5f5f5;
                    color: #1e1e1e;
                }
                QGroupBox {
                    color: #1e1e1e;
                    border: 1px solid #ccc;
                    border-radius: 5px;
                    margin-top: 10px;
                    font-weight: bold;
                    padding-top: 10px;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                }
                QDoubleSpinBox, QSpinBox {
                    background-color: #fff;
                    color: #1e1e1e;
                    border: 1px solid #ccc;
                    padding: 3px;
                }
                QPushButton {
                    background-color: #e0e0e0;
                    color: #1e1e1e;
                    border: 1px solid #ccc;
                    padding: 5px 15px;
                }
                QPushButton:hover {
                    background-color: #d0d0d0;
                }
                QPushButton:pressed {
                    background-color: #0078d4;
                    color: #fff;
                }
                QListWidget {
                    background-color: #fff;
                    color: #1e1e1e;
                    border: 1px solid #ccc;
                }
                QListWidget::item:selected {
                    background-color: #0078d4;
                    color: #fff;
                }
                QLabel {
                    color: #1e1e1e;
                }
                QTabWidget::pane {
                    border: 1px solid #ccc;
                }
                QTabBar::tab {
                    background-color: #e0e0e0;
                    color: #1e1e1e;
                    padding: 5px 10px;
                }
                QTabBar::tab:selected {
                    background-color: #0078d4;
                    color: #fff;
                }
                QStatusBar {
                    background-color: #e0e0e0;
                    color: #1e1e1e;
                }
            """)
            self._update_status("Light theme")
        else:
            self._theme = 'dark'
            self.dark_theme(app)
            self._update_status("Dark theme")
    
    def dark_theme(self, app):
        """Apply dark theme"""
        app.setStyleSheet("""
            QMainWindow {
                background-color: #1e1e1e;
            }
            QWidget {
                background-color: #1e1e1e;
                color: #e0e0e0;
            }
            QGroupBox {
                color: #e0e0e0;
                border: 1px solid #3f3f3f;
                border-radius: 5px;
                margin-top: 10px;
                font-weight: bold;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
            }
            QDoubleSpinBox, QSpinBox, QLineEdit, QTextEdit, QTableWidget {
                background-color: #2d2d2d;
                color: #e0e0e0;
                border: 1px solid #3f3f3f;
                padding: 3px;
            }
            QHeaderView::section {
                background-color: #2d2d2d;
                color: #e0e0e0;
                padding: 4px;
                border: 1px solid #3f3f3f;
            }
            QTableCornerButton::section {
                background-color: #2d2d2d;
                border: 1px solid #3f3f3f;
            }
            QPushButton {
                background-color: #2d2d2d;
                color: #e0e0e0;
                border: 1px solid #3f3f3f;
                padding: 5px 15px;
            }
            QPushButton:hover {
                background-color: #3d3d3d;
            }
            QPushButton:pressed {
                background-color: #0078d4;
            }
            QListWidget {
                background-color: #2d2d2d;
                color: #e0e0e0;
                border: 1px solid #3f3f3f;
            }
            QListWidget::item:selected {
                background-color: #0078d4;
            }
            QLabel {
                color: #e0e0e0;
            }
            QTabWidget::pane {
                border: 1px solid #3f3f3f;
            }
            QTabBar::tab {
                background-color: #2d2d2d;
                color: #e0e0e0;
                padding: 5px 10px;
            }
            QTabBar::tab:selected {
                background-color: #0078d4;
            }
            QStatusBar {
                background-color: #2d2d2d;
                color: #e0e0e0;
                border-top: 1px solid #3f3f3f;
            }
            QProgressBar {
                border: 1px solid #3f3f3f;
                border-radius: 2px;
                text-align: center;
                background-color: #2d2d2d;
            }
            QProgressBar::chunk {
                background-color: #0078d4;
            }
        """)

    
    def _on_reset_window(self):
        """Reset window to default size and position"""
        self.resize(1000, 700)
        self.move(50, 50)
        self._update_status("Window reset")
    
    def _set_viz_mode(self, mode):
        """Set visualization view mode"""
        if hasattr(self, '_lens_editor') and self._lens_editor:
            viz = getattr(self._lens_editor, '_viz_widget', None)
            if viz and hasattr(viz, 'set_view_mode'):
                viz.set_view_mode(mode)
        self._update_status(f"View: {mode}")
    
    def _open_3d_viewer(self):
        """Open 3D visualization embedded in the main window"""
        if not self._current_lens:
            self._update_status("No lens selected")
            return
        
        try:
            import matplotlib
            matplotlib.use('Qt5Agg')
            from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
            from matplotlib.figure import Figure
            from mpl_toolkits.mplot3d import Axes3D
            
            lens = self._current_lens
            fig = Figure(figsize=(8, 6), facecolor='#1e1e1e')
            ax = fig.add_subplot(111, projection='3d', facecolor='#1e1e1e')
            
            r1 = lens.radius_of_curvature_1
            r2 = lens.radius_of_curvature_2
            thickness = lens.thickness
            diameter = lens.diameter
            
            theta = 0
            r = diameter / 2
            num_segments = 50
            
            pts = []
            for i in range(num_segments + 1):
                angle = 2 * 3.14159 * i / num_segments
                pts.append((r * np.cos(angle), r * np.sin(angle)))
            
            for surf in ['front', 'back']:
                if surf == 'front':
                    z_vals = np.linspace(0, thickness, 20)
                    r_surf = r1
                else:
                    z_vals = np.linspace(thickness, 0, 20)
                    r_surf = r2
                
                X, Y = np.meshgrid([p[0] for p in pts], z_vals)
                Z = np.zeros_like(X)
                
                for j, pt in enumerate(pts):
                    x, y = pt
                    if abs(r_surf) > 0:
                        z_vals_surf = np.sqrt(max(0, r_surf**2 - x**2 - y**2))
                        if (surf == 'front' and r1 < 0) or (surf == 'back' and r2 > 0):
                            Z[:, j] = thickness - z_vals_surf
                        else:
                            Z[:, j] = z_vals_surf
                
                ax.plot_surface(X, Y, Z, alpha=0.6, color='cyan', edgecolor='gray')
            
            ax.set_xlabel('X (mm)', color='#e0e0e0')
            ax.set_ylabel('Y (mm)', color='#e0e0e0')
            ax.set_zlabel('Z (mm)', color='#e0e0e0')
            ax.tick_params(colors='#e0e0e0')
            ax.xaxis.label.set_color('#e0e0e0')
            ax.yaxis.label.set_color('#e0e0e0')
            ax.zaxis.label.set_color('#e0e0e0')
            
            ax.view_init(elev=30, azim=45)
            
            canvas = FigureCanvasQTAgg(fig)
            canvas.setStyleSheet("background-color: #1e1e1e;")
            canvas.setMinimumSize(400, 300)
            
            self._update_status("3D view ready")
            
        except ImportError:
            self._update_status("Matplotlib not installed")
        except Exception as e:
            self._update_status(f"Error: {str(e)[:20]}")
    
    def _refresh_lens_menu(self):
        """Refresh the lens quick-switch menu"""
        lens_menu = self.menuBar().findChild(type(self.menuBar().addMenu("")))
        if hasattr(self, '_lens_action_group') and len(self._lenses) > len(self._lens_action_group):
            for i, lens in enumerate(self._lenses):
                if i >= len(self._lens_action_group):
                    pass
    
    def _switch_to_lens(self, index):
        """Switch to lens by index"""
        if 0 <= index < len(self._lenses):
            self._current_lens = self._lenses[index]
            self._lens_list_widget.setCurrentRow(index)
            self._lens_editor.load_lens(self._current_lens)
            self._update_all_tabs()
            self._update_status(f"Switched to: {self._current_lens.name}")


class LensEditorWidget(QWidget):
    """Lens editor with properties and visualization"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._lens = None
        self._parent = parent
        self._setup_ui()
    
    def _setup_ui(self):
        from PySide6.QtWidgets import QScrollArea
        
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # Left: Properties panel (scrollable)
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
        from PySide6.QtWidgets import QGroupBox, QFormLayout, QLabel, QDoubleSpinBox, QLineEdit, QVBoxLayout, QFrame
        
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
        
        # Material dropdown
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
            
            # Notify parent to update UI lists
            if self._parent and hasattr(self._parent, '_update_lens_list'):
                self._parent._update_lens_list()
            
            # Auto-save to database
            if self._parent and hasattr(self._parent, '_save_to_database'):
                self._parent._save_to_database()

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
            
            # Update classification display
            self._class_type_label.setText(self._lens.classify_lens_type())
            
            # Auto-save to database
            if self._parent and hasattr(self._parent, '_save_to_database'):
                self._parent._save_to_database()
            
            # Notify parent to update all tab displays
            if self._parent and hasattr(self._parent, '_update_all_tabs'):
                self._parent._update_all_tabs()
            if self._parent and hasattr(self._parent, '_update_status'):
                self._parent._update_status(f"Updated: {self._lens.name}")
    
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
        enabled = state == 2  # Qt.Checked
        
        # Hide/show the input fields and their labels
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
        
        # Calculate optical properties using lensmaker's equation
        n = self._lens.refractive_index
        r1 = self._lens.radius_of_curvature_1
        r2 = self._lens.radius_of_curvature_2
        t = self._lens.thickness
        
        # Avoid division by zero
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
            
            # Back focal length: BFL = f * (1 - d * power2 / n)
            bfl = f * (1 - t * power2 / n) if n != 0 else f
            self._bfl_label.setText(f"{bfl:.2f} mm")
            
            # Front focal length: FFL = f * (1 - d * power1 / n)
            ffl = f * (1 - t * power1 / n) if n != 0 else f
            self._ffl_label.setText(f"{ffl:.2f} mm")
        else:
            self._focal_label.setText("∞")
            self._power_label.setText("0 D")
            self._bfl_label.setText("∞")
            self._ffl_label.setText("∞")
    
    def load_lens(self, lens):
        """Load a lens into the editor"""
        self._lens = lens
        # Block signals to prevent _on_name_changed from firing during load
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


class LensVisualizationWidget(QWidget):
    """Lens visualization widget with 2D and 3D views"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._lens = None
        self._view_mode = "2D"
        self._rotation = 0
        
        self.setMinimumSize(400, 300)
        self.setStyleSheet("background-color: #1e1e1e;")
        
        from PySide6.QtWidgets import QTabWidget, QVBoxLayout
        from PySide6.QtGui import QColor
        
        self._bg_color = QColor("#1e1e1e")
        self._axis_color = QColor("#666666")
        self._lens_color = QColor(0, 120, 212, 150)
        self._text_color = QColor("#e0e0e0")
        
        # Create 2D/3D tab structure
        self._viz_tabs = QTabWidget()
        self._viz_tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #3f3f3f; }
            QTabBar::tab { background: #2d2d2d; color: #e0e0e0; padding: 5px 10px; }
            QTabBar::tab:selected { background: #0078d4; }
        """)
        
        # 2D view (custom canvas)
        self._2d_widget = _2DVisualizationWidget()
        self._viz_tabs.addTab(self._2d_widget, "2D")
        
        # 3D view (matplotlib embedded)
        self._3d_widget = _3DVisualizationWidget()
        self._viz_tabs.addTab(self._3d_widget, "3D")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._viz_tabs)
    
    def set_view_mode(self, mode):
        """Set view mode (2D, 3D, Side)"""
        self._view_mode = mode
        if mode.startswith("3D"):
            self._viz_tabs.setCurrentIndex(1)
        else:
            self._viz_tabs.setCurrentIndex(0)
            self._2d_widget.set_view_mode(mode)
    
    def update_lens(self, lens):
        """Update visualization with new lens data"""
        self._lens = lens
        self._2d_widget.update_lens(lens)
        self._3d_widget.update_lens(lens)


class _2DVisualizationWidget(QWidget):
    """2D lens visualization"""
    
    # Signals for interactive manipulation
    property_changed = Signal(str, float)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._lens = None
        self._view_mode = "2D"
        
        self.setMinimumSize(400, 300)
        self.setStyleSheet("background-color: #1e1e1e;")
        
        from PySide6.QtGui import QColor
        self._bg_color = QColor("#1e1e1e")
        self._r1_color = QColor(0, 150, 255, 180)    # Blue for radius 1
        self._r2_color = QColor(0, 200, 100, 180)  # Green for radius 2
        self._fill_color = QColor(150, 200, 230, 80)   # Light blue fill
        self._edge_color = QColor(150, 150, 150, 200)   # Grey for lens edge
        self._text_color = QColor("#e0e0e0")
        self._axis_color = QColor("#666666")
        self._handle_color = QColor(255, 255, 255, 200) # White for interactive handles
        
        # Interaction state
        self._active_handle = None # 'r1', 'r2', 'thickness', 'diameter'
        self._last_mouse_pos = None
        self._handles = {} # name -> (x, y)
        self._scale = 1.0
        self._cx = 0
        self._cy = 0
        
        self.setMouseTracking(True)

    def mousePressEvent(self, event):
        if not self._lens: return
        
        pos = event.position().toPoint()
        for name, h_pos in self._handles.items():
            dx = pos.x() - h_pos.x()
            dy = pos.y() - h_pos.y()
            if (dx*dx + dy*dy) < 100: # 10px radius hit area
                self._active_handle = name
                self._last_mouse_pos = pos
                self.setCursor(Qt.ClosedHandCursor)
                break

    def mouseReleaseEvent(self, event):
        self._active_handle = None
        self.setCursor(Qt.ArrowCursor)

    def mouseMoveEvent(self, event):
        if not self._lens: return
        
        pos = event.position().toPoint()
        if self._active_handle:
            dx = (pos.x() - self._last_mouse_pos.x()) / self._scale
            dy = (pos.y() - self._last_mouse_pos.y()) / self._scale
            
            if self._active_handle == 'r1':
                # Dragging R1 vertex horizontally
                new_r1 = self._lens.radius_of_curvature_1 + dx
                # Snap to flat if close to zero
                if abs(new_r1) < 1.0: new_r1 = 0.0
                self.property_changed.emit('r1', new_r1)
            elif self._active_handle == 'r2':
                # Dragging R2 vertex horizontally
                new_r2 = self._lens.radius_of_curvature_2 + dx
                # Snap to flat if close to zero
                if abs(new_r2) < 1.0: new_r2 = 0.0
                self.property_changed.emit('r2', new_r2)
            elif self._active_handle == 'thickness':
                # Dragging right edge
                new_t = self._lens.thickness + dx
                if new_t < 0.1: new_t = 0.1
                self.property_changed.emit('thickness', new_t)
            elif self._active_handle == 'diameter':
                # Dragging top/bottom edge
                new_d = self._lens.diameter - 2 * dy # Screen Y is inverted
                if new_d < 1.0: new_d = 1.0
                self.property_changed.emit('diameter', new_d)
                
            self._last_mouse_pos = pos
        else:
            # Update cursor if hovering over a handle
            hovering = False
            for h_pos in self._handles.values():
                dx = pos.x() - h_pos.x()
                dy = pos.y() - h_pos.y()
                if (dx*dx + dy*dy) < 100:
                    hovering = True
                    break
            if hovering:
                self.setCursor(Qt.PointingHandCursor)
            else:
                self.setCursor(Qt.ArrowCursor)

    def set_view_mode(self, mode):
        self._view_mode = mode
        self.update()
    
    def update_lens(self, lens):
        self._lens = lens
        self.update()
    
    def paintEvent(self, event):
        from PySide6.QtGui import QPainter, QPen, QColor, QPainterPath, QBrush
        from PySide6.QtCore import Qt, QPoint
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        w, h = self.width(), self.height()
        painter.fillRect(0, 0, w, h, self._bg_color)
        
        if not self._lens:
            return
        
        r1 = self._lens.radius_of_curvature_1
        r2 = self._lens.radius_of_curvature_2
        thickness = self._lens.thickness
        diameter = self._lens.diameter
        
        # Larger scale for bigger lens
        max_dim = max(thickness * 2, diameter, 100)
        self._scale = min(w, h) / max_dim * 0.85
        scale = self._scale
        cx, cy = w/2, h/2
        self._cx, self._cy = cx, cy
        
        # Draw grid
        grid_color = QColor("#333333")
        painter.setPen(QPen(grid_color, 1))
        grid_spacing = 10 * scale  # 10mm grid
        
        # Draw grid lines relative to center
        start_x = cx % grid_spacing
        while start_x < w:
            painter.drawLine(start_x, 0, start_x, h)
            start_x += grid_spacing
        start_y = cy % grid_spacing
        while start_y < h:
            painter.drawLine(0, start_y, w, start_y)
            start_y += grid_spacing
        
        # Draw axis
        painter.setPen(QPen(self._axis_color, 1))
        painter.drawLine(0, cy, w, cy)
        painter.drawLine(cx, 0, cx, h)
        
        # Geometric calculations
        r1_abs = abs(r1)
        r2_abs = abs(r2)
        half_d = diameter / 2
        
        # Helper to get sag at y
        def get_sag(r, y):
            if abs(r) < 1e-6: return 0
            r_a = abs(r)
            # Ensure y doesn't exceed radius of curvature to avoid NaN
            # Use a slightly more robust clamping
            y_safe = min(y, r_a)
            sag = r_a - math.sqrt(max(0, r_a**2 - y_safe**2))
            return sag if r > 0 else -sag

        # X positions
        x1_vertex = cx
        sag1_edge = get_sag(r1, half_d)
        x1_edge = x1_vertex + sag1_edge * scale
        
        x2_edge = x1_edge + thickness * scale
        sag2_edge = get_sag(r2, half_d)
        x2_vertex = x2_edge - sag2_edge * scale

        # Safety check: if x2_vertex or x1_vertex is NaN, use defaults to prevent crash
        if math.isnan(x1_vertex): x1_vertex = cx
        if math.isnan(x2_vertex): x2_vertex = cx + thickness * scale
        if math.isnan(x1_edge): x1_edge = x1_vertex
        if math.isnan(x2_edge): x2_edge = x1_edge + thickness * scale

        # Clear handles
        self._handles = {}

        # Construct single coherent lens path for filling
        path_lens = QPainterPath()
        
        # 1. Front Surface (top to bottom)
        pts = 50
        for i in range(pts + 1):
            y = -half_d + (diameter * i / pts)
            x = x1_vertex + get_sag(r1, abs(y)) * scale
            if i == 0: path_lens.moveTo(x, cy + y * scale)
            else: path_lens.lineTo(x, cy + y * scale)
            
        # 2. Bottom Edge
        path_lens.lineTo(x2_edge, cy + half_d * scale)
        
        # 3. Back Surface (bottom to top)
        for i in range(pts + 1):
            y = half_d - (diameter * i / pts)
            x = x2_vertex + get_sag(r2, abs(y)) * scale
            path_lens.lineTo(x, cy + y * scale)
            
        # 4. Top Edge
        path_lens.closeSubpath()
        
        # Fill and stroke lens
        painter.setPen(QPen(self._edge_color, 1))
        painter.setBrush(QBrush(self._fill_color))
        painter.drawPath(path_lens)
        
        # Highlight surfaces with colors
        # R1
        path_r1 = QPainterPath()
        for i in range(pts + 1):
            y = -half_d + (diameter * i / pts)
            x = x1_vertex + get_sag(r1, abs(y)) * scale
            if i == 0: path_r1.moveTo(x, cy + y * scale)
            else: path_r1.lineTo(x, cy + y * scale)
        painter.setPen(QPen(self._r1_color, 2))
        painter.drawPath(path_r1)
        
        # R2
        path_r2 = QPainterPath()
        for i in range(pts + 1):
            y = -half_d + (diameter * i / pts)
            x = x2_vertex + get_sag(r2, abs(y)) * scale
            if i == 0: path_r2.moveTo(x, cy + y * scale)
            else: path_r2.lineTo(x, cy + y * scale)
        painter.setPen(QPen(self._r2_color, 2))
        painter.drawPath(path_r2)

        # Draw handles (spaced out to avoid crowding)
        def draw_handle(p, name, pos, label=""):
            self._handles[name] = pos
            if self._active_handle == name:
                p.setPen(QPen(QColor(0, 255, 0), 2))
                p.setBrush(QBrush(QColor(0, 255, 0, 150)))
            else:
                p.setPen(QPen(Qt.white, 1))
                p.setBrush(QBrush(QColor(255, 255, 255, 50)))
            p.drawEllipse(pos, 6, 6)
            
        # R1 handle at vertex
        draw_handle(painter, 'r1', QPoint(int(x1_vertex), int(cy)))
        # R2 handle at vertex
        draw_handle(painter, 'r2', QPoint(int(x2_vertex), int(cy)))
        # Thickness handle at bottom center
        draw_handle(painter, 'thickness', QPoint(int((x1_edge + x2_edge)/2), int(cy + half_d * scale + 15)))
        # Diameter handle at top center
        draw_handle(painter, 'diameter', QPoint(int((x1_edge + x2_edge)/2), int(cy - half_d * scale - 15)))


class _3DVisualizationWidget(QWidget):
    """3D lens visualization using matplotlib"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._lens = None
        self._canvas = None
        self._figure = None
        
        self.setMinimumSize(400, 300)
        self.setStyleSheet("background-color: #1e1e1e;")
        
        try:
            import matplotlib
            matplotlib.use('Qt5Agg')
            from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
            from matplotlib.figure import Figure
            
            self._figure = Figure(figsize=(6, 5), facecolor='#1e1e1e')
            self._canvas = FigureCanvasQTAgg(self._figure)
            self._canvas.setStyleSheet("background-color: #1e1e1e;")
            
            layout = QVBoxLayout(self)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(self._canvas)
            
            self._figure.subplots_adjust(left=0.05, right=0.95, top=0.95, bottom=0.05)
            
            # Fixed coordinate system (background)
            self._ax_coords = self._figure.add_subplot(111, projection='3d', facecolor='#1e1e1e', computed_zorder=False)
            self._ax_coords.view_init(elev=20, azim=45)
            self._ax_coords.mouse_init()
            
            # Rotatable lens geometry (foreground)
            self._ax_lens = self._figure.add_subplot(111, projection='3d', facecolor='none', computed_zorder=False)
            self._ax_lens.set_position(self._ax_coords.get_position())
            self._ax_lens.patch.set_alpha(0)
            self._ax_lens.view_init(elev=20, azim=45)
            self._ax_lens.set_axis_off()
            self._ax_lens.mouse_init()
            
            # Use lens axis for main reference
            self._ax = self._ax_lens
            
            # Configure coordinate appearance
            self._ax_coords.set_xlabel('X (mm)', color='#666')
            self._ax_coords.set_ylabel('Y (mm)', color='#666')
            self._ax_coords.set_zlabel('Z (mm)', color='#666')
            self._ax_coords.tick_params(colors='#555', labelsize=8)
            self._ax_coords.xaxis.pane.set_facecolor('#1e1e1e')
            self._ax_coords.yaxis.pane.set_facecolor('#1e1e1e')
            self._ax_coords.zaxis.pane.set_facecolor('#1e1e1e')
            self._ax_coords.xaxis.pane.set_alpha(0.9)
            self._ax_coords.yaxis.pane.set_alpha(0.9)
            self._ax_coords.zaxis.pane.set_alpha(0.9)
            
        except ImportError:
            from PySide6.QtWidgets import QLabel
            layout = QVBoxLayout(self)
            lbl = QLabel("Install matplotlib\nfor 3D view")
            lbl.setStyleSheet("color: #888; padding: 50px;")
            layout.addWidget(lbl)
    
    def update_lens(self, lens):
        if not lens or not self._ax or not self._figure:
            return
        
        # Clear only lens axis
        if hasattr(self, '_ax_lens'):
            self._ax_lens.clear()
            self._ax_lens.set_axis_off()
            
            # Keep coordinate system fixed (don't clear/recreate it)
            # Just set limits from current lens
            thickness, diameter = lens.thickness, lens.diameter
            max_dim = max(diameter, thickness) * 0.7
            if hasattr(self, '_ax_coords'):
                self._ax_coords.set_xlim([-max_dim, max_dim])
                self._ax_coords.set_ylim([-max_dim, max_dim])
                self._ax_coords.set_zlim([-max_dim/2, thickness + max_dim/2])
        
        r1, r2 = lens.radius_of_curvature_1, lens.radius_of_curvature_2
        thickness, diameter = lens.thickness, lens.diameter
        max_r = diameter / 2.0
        
        import numpy as np
        
        # Create circles at top and bottom edges
        theta = np.linspace(0, 2*np.pi, 36)
        
        # Front face Z position (vertex)
        z1_vertex = 0
        
        # Back face Z position (vertex)
        z2_vertex = thickness
        
        # Circle at front edge
        x_front = max_r * np.cos(theta)
        y_front = max_r * np.sin(theta)
        # Calculate sag at the edge to find actual edge Z position
        z_front_edge = 0
        # Helper for edge sag
        def get_sag_edge(r, y):
            if abs(r) < 1e-6: return 0
            r_a = abs(r)
            y_safe = min(y, r_a)
            sag = r_a - np.sqrt(max(0, r_a**2 - y_safe**2))
            return sag if r > 0 else -sag

        # Front edge circle at z=0 (curves per get_sag)
        if r1_abs > 0.1:
            z_front_edge = get_sag_edge(r1, max_r)
        else:
            z_front_edge = 0
        z_front = np.full_like(theta, z_front_edge)
        self._ax.plot(x_front, y_front, z_front, color='blue', linewidth=2)
        
        # Back edge circle at z=thickness
        x_back = max_r * np.cos(theta)
        y_back = max_r * np.sin(theta)
        if r2_abs > 0.1:
            z_back_edge = thickness + get_sag_edge(r2, max_r)
        else:
            z_back_edge = thickness
            
        z_back = np.full_like(theta, z_back_edge)
        self._ax.plot(x_back, y_back, z_back, color='green', linewidth=2)
        
        # Connect edges with vertical lines (cylinder wall)
        for i in range(0, len(theta), 2):
            ex = [x_front[i], x_back[i]]
            ey = [y_front[i], y_back[i]]
            ez = [z_front[i], z_back[i]]
            self._ax.plot(ex, ey, ez, color='gray', linewidth=0.5)
        
        # Fill surfaces
        r_vals = np.linspace(0, max_r, 15)
        theta_vals = np.linspace(0, 2*np.pi, 25)
        R, THETA = np.meshgrid(r_vals, theta_vals)

        # Helper to get sag at radial distance (same logic as 2D)
        def get_sag_3d(r, rho):
            if abs(r) < 1e-6: return 0
            r_a = abs(r)
            rho_safe = min(rho, r_a)
            sag = r_a - np.sqrt(max(0, r_a**2 - rho_safe**2))
            return sag if r > 0 else -sag

        # Front surface at z=0
        if r1_abs > 0.1:
            Z_front = get_sag_3d(r1, rho)
            X = R * np.cos(THETA)
            Y = R * np.sin(THETA)
            self._ax.plot_surface(X, Y, Z_front, alpha=0.5, color='blue', rstride=2, cstride=2)

        # Back surface at z=thickness
        if r2_abs > 0.1:
            Z_back = thickness + get_sag_3d(r2, rho)
            X = R * np.cos(THETA)
            Y = R * np.sin(THETA)
            self._ax.plot_surface(X, Y, Z_back, alpha=0.5, color='green', rstride=2, cstride=2)
        
        # Set axis limits on lens axis only
        padding = max(diameter, thickness) * 0.3
        limit = max(diameter, thickness) / 2 + padding
        self._ax.set_xlim([-limit, limit])
        self._ax.set_ylim([-limit, limit])
        self._ax.set_zlim([min(z_front_edge, z_back_edge) - padding, max(z_front_edge, z_back_edge) + padding])
        
        self._ax.view_init(elev=20, azim=45)
        
        # Add dimension text
        dim_text = f"D={diameter:.0f}mm  t={thickness:.1f}mm"
        self._ax.text2D(0.02, 0.98, dim_text, transform=self._ax.transAxes,
                       color='white', fontsize=10, fontweight='bold')
        
        self._canvas.draw()


class AssemblyVisualizationWidget(QWidget):
    """2D visualization of optical system (multiple lenses)"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._system = None
        
        self.setMinimumSize(400, 300)
        self.setStyleSheet("background-color: #1e1e1e; border: 1px solid #3f3f3f;")
        
        from PySide6.QtGui import QColor
        self._bg_color = QColor("#1e1e1e")
        self._axis_color = QColor("#666666")
        self._lens_colors = [
            QColor(0, 120, 212, 150),
            QColor(0, 180, 100, 150),
            QColor(200, 100, 0, 150),
            QColor(150, 50, 200, 150),
        ]
        self._text_color = QColor("#e0e0e0")
    
    def update_system(self, system):
        """Update visualization with optical system"""
        self._system = system
        self.update()
    
    def paintEvent(self, event):
        """Paint the optical system visualization"""
        from PySide6.QtGui import QPainter, QPen, QPainterPath, QBrush
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        w = self.width()
        h = self.height()
        
        # Background
        painter.fillRect(0, 0, w, h, self._bg_color)
        
        if not self._system or not self._system.elements:
            return
        
        # Calculate total width
        total_thickness = sum(e.lens.thickness for e in self._system.elements)
        for i in range(len(self._system.elements) - 1):
            if i < len(self._system.air_gaps):
                total_thickness += self._system.air_gaps[i].thickness
        
        max_diameter = max(e.lens.diameter for e in self._system.elements)
        
        # Scale
        max_dim = max(total_thickness * 1.5, max_diameter * 1.3)
        scale = min(w, h) / max_dim / 2
        
        cx = 30
        cy = h / 2
        
        # Draw axis
        painter.setPen(QPen(self._axis_color, 1, Qt.DashLine))
        painter.drawLine(0, cy, w, cy)
        
        # Draw each lens
        for i, element in enumerate(self._system.elements):
            lens = element.lens
            color = self._lens_colors[i % len(self._lens_colors)]
            
            r1 = lens.radius_of_curvature_1
            r2 = lens.radius_of_curvature_2
            thickness = lens.thickness
            diameter = lens.diameter
            
            self._draw_lens(painter, r1, r2, thickness, diameter, cx, cy, scale, color)
            
            # Add gap
            if i < len(self._system.air_gaps):
                cx += thickness * scale + self._system.air_gaps[i].thickness * scale
            else:
                cx += thickness * scale
    
    def _draw_lens(self, painter, r1, r2, thickness, diameter, cx, cy, scale, color):
        """Draw a single lens"""
        from PySide6.QtGui import QPainterPath, QPen, QBrush
        
        # Helper to get sag at y
        def get_sag(r, y):
            if abs(r) < 1e-6: return 0
            r_a = abs(r)
            if y > r_a: return r_a
            sag = r_a - (r_a**2 - y**2)**0.5
            return sag if r > 0 else -sag

        half_d = diameter / 2
        x1_vertex = cx
        sag1_edge = get_sag(r1, half_d)
        x1_edge = x1_vertex + sag1_edge * scale
        
        x2_edge = x1_edge + thickness * scale
        sag2_edge = get_sag(r2, half_d)
        x2_vertex = x2_edge - sag2_edge * scale

        path = QPainterPath()
        pts = 50
        
        # 1. Front Surface (top to bottom)
        for i in range(pts + 1):
            y = -half_d + (diameter * i / pts)
            x = x1_vertex + get_sag(r1, abs(y)) * scale
            if i == 0: path.moveTo(x, cy + y * scale)
            else: path.lineTo(x, cy + y * scale)
            
        # 2. Bottom Edge
        path.lineTo(x2_edge, cy + half_d * scale)
        
        # 3. Back Surface (bottom to top)
        for i in range(pts + 1):
            y = half_d - (diameter * i / pts)
            x = x2_vertex + get_sag(r2, abs(y)) * scale
            path.lineTo(x, cy + y * scale)
            
        # 4. Top Edge
        path.closeSubpath()
        
        painter.setPen(QPen(color, 2))
        painter.setBrush(QBrush(color))
        painter.drawPath(path)


class SimulationVisualizationWidget(QWidget):
    """2D ray tracing simulation visualization widget"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._lens = None
        self._system = None
        self._rays = []
        self._wavelength = 550  # Default wavelength in nm
        
        self.setMinimumSize(400, 300)
        self.setStyleSheet("background-color: #1e1e1e; border: 2px solid #888888;")
        
        from PySide6.QtGui import QColor
        self._bg_color = QColor("#1e1e1e")
        self._axis_color = QColor("#666666")
        self._lens_color = QColor(0, 120, 212, 150)
        self._ray_color = QColor(255, 200, 0, 200)
        self._text_color = QColor("#e0e0e0")
        self._ghost_color = QColor(255, 100, 100, 180)
        self._show_ghosts = False
        self._show_image_sim = False
        self._image_pattern = "Star"
        
        # Zoom and pan state
        self._zoom = 1.0
        self._pan_x = 0
        self._pan_y = 0
        self._is_panning = False
        self._last_mouse_x = 0
        self._last_mouse_y = 0
        
        # Install event filters
        self.setFocusPolicy(Qt.StrongFocus)
    
    @staticmethod
    def wavelength_to_color(wavelength):
        """Convert wavelength (nm) to RGB color"""
        from PySide6.QtGui import QColor
        if wavelength < 380:
            wavelength = 380
        elif wavelength > 780:
            wavelength = 780
        
        # Simplified spectral color approximation
        if wavelength < 440:
            r = int((440 - wavelength) / (440 - 380) * 255)
            g = 0
            b = 255
        elif wavelength < 490:
            r = 0
            g = int((wavelength - 440) / (490 - 440) * 255)
            b = 255
        elif wavelength < 510:
            r = 0
            g = 255
            b = int((510 - wavelength) / (510 - 490) * 255)
        elif wavelength < 580:
            r = int((wavelength - 510) / (580 - 510) * 255)
            g = 255
            b = 0
        elif wavelength < 645:
            r = 255
            g = int((645 - wavelength) / (645 - 580) * 255)
            b = 0
        else:
            r = 255
            g = 0
            b = 0
        
        return QColor(r, g, b, 200)
    
    def wheelEvent(self, event):
        """Handle mouse wheel for zooming"""
        from PySide6.QtCore import Qt
        if event.angleDelta().y() > 0:
            self._zoom *= 1.1
        else:
            self._zoom /= 1.1
        self._zoom = max(0.1, min(self._zoom, 50.0))
        self.update()
    
    def mousePressEvent(self, event):
        """Start panning on mouse press"""
        from PySide6.QtCore import Qt
        if event.button() == Qt.LeftButton:
            self._is_panning = True
            self._last_mouse_x = event.position().x()
            self._last_mouse_y = event.position().y()
    
    def mouseMoveEvent(self, event):
        """Pan the view when dragging"""
        if self._is_panning:
            dx = event.position().x() - self._last_mouse_x
            dy = event.position().y() - self._last_mouse_y
            self._pan_x += dx
            self._pan_y -= dy  # Invert because screen Y is down
            self._last_mouse_x = event.position().x()
            self._last_mouse_y = event.position().y()
            self.update()
    
    def mouseReleaseEvent(self, event):
        """Stop panning on mouse release"""
        from PySide6.QtCore import Qt
        if event.button() == Qt.LeftButton:
            self._is_panning = False
    
    def keyPressEvent(self, event):
        """Handle keyboard for zoom/pan reset"""
        from PySide6.QtCore import Qt
        if event.key() == Qt.Key_R:
            self._zoom = 1.0
            self._pan_x = 0
            self._pan_y = 0
            self.update()
        elif event.key() == Qt.Key_Plus or event.key() == Qt.Key_Equal:
            self._zoom *= 1.2
            self.update()
        elif event.key() == Qt.Key_Minus:
            self._zoom /= 1.2
            self._zoom = max(0.1, self._zoom)
            self.update()
    
    def reset_view(self):
        """Reset zoom and pan"""
        self._zoom = 1.0
        self._pan_x = 0
        self._pan_y = 0
        self.update()
    
    def run_simulation(self, lens_or_system, num_rays=11, angle=0, source_height=0, show_ghosts=False, wavelength=550):
        """Run ray tracing simulation"""
        from src.optical_system import OpticalSystem
        if isinstance(lens_or_system, OpticalSystem):
            self._system = lens_or_system
            self._lens = None
        else:
            self._lens = lens_or_system
            self._system = None
            
        self._rays = []
        self._ghost_rays = []
        self._show_ghosts = show_ghosts
        self._wavelength = wavelength
        self._ray_color = self.wavelength_to_color(wavelength)
        
        try:
            from src.ray_tracer import LensRayTracer, Ray
            
            # Use appropriate tracer
            if self._system:
                # OpticalSystem has multiple elements
                from src.ray_tracer import SystemRayTracer
                tracer = SystemRayTracer(self._system)
                diameter = self._system.elements[0].lens.diameter if self._system.elements else 25.0
            else:
                tracer = LensRayTracer(self._lens)
                diameter = self._lens.diameter
            
            angle_rad = angle * 3.14159 / 180.0
            
            for i in range(num_rays):
                if num_rays == 1:
                    h = 0
                else:
                    h = -diameter/2 + diameter * i / (num_rays - 1)
                
                ray = Ray(-100, h + source_height, angle=angle_rad)
                tracer.trace_ray(ray)
                self._rays.append(ray)
            
            if show_ghosts:
                if self._system:
                    self._run_ghost_analysis(self._system, tracer)
                elif self._lens:
                    # Wrap lens in temporary system for GhostAnalyzer
                    temp_system = OpticalSystem(name="Ghost Analysis")
                    temp_system.add_lens(self._lens)
                    self._run_ghost_analysis(temp_system, tracer)
        
        except Exception as e:
            print(f"Simulation error: {e}")
            import traceback
            traceback.print_exc()
        
        self.update()
    
    def _run_ghost_analysis(self, system, tracer):
        """Run ghost analysis for 2nd order reflections"""
        try:
            from src.analysis.ghost import GhostAnalyzer
            analyzer = GhostAnalyzer(system)
            ghosts = analyzer.trace_ghosts(num_rays=3)
            
            for ghost in ghosts:
                if ghost.rays:
                    self._ghost_rays.append(ghost.rays)
        except Exception as e:
            print(f"Ghost analysis error: {e}")
    
    def run_image_simulation(self, lens, pattern="Star"):
        """Run image simulation pattern through lens"""
        self._lens = lens
        self._show_image_sim = True
        self._image_pattern = pattern
        self.update()
    
    def clear_simulation(self):
        """Clear simulation results"""
        self._rays = []
        self._ghost_rays = []
        self._lens = None
        self._show_image_sim = False
        self.update()
    
    def paintEvent(self, event):
        """Paint the simulation"""
        from PySide6.QtGui import QPainter, QPen, QColor, QPainterPath, QBrush
        from PySide6.QtCore import Qt
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        w = self.width()
        h = self.height()
        
        painter.fillRect(0, 0, w, h, self._bg_color)
        
        if not self._lens and not self._system:
            painter.setPen(QPen(self._text_color, 1))
            painter.drawText(w//2 - 80, h//2, "Run simulation to see rays")
            return
        
        # Draw axis
        painter.setPen(QPen(self._axis_color, 1, Qt.DashLine))
        painter.drawLine(0, h//2, w, h//2)
        
        # Determine total bounds for scaling
        if self._system:
            total_thickness = self._system.get_total_length()
            max_diameter = max((e.lens.diameter for e in self._system.elements), default=25.0)
        else:
            total_thickness = self._lens.thickness
            max_diameter = self._lens.diameter
            
        max_dim = max(total_thickness * 2, max_diameter, 30) * 1.2
        scale = min(w, h) / max_dim * self._zoom
        
        cx = w / 4 + self._pan_x
        cy = h / 2 + self._pan_y

        def draw_single_lens(pnt, lens, start_x, center_y, sc, color):
            from PySide6.QtGui import QPainterPath, QPen, QBrush
            
            # Helper to get sag at y
            def get_sag(r, y):
                if abs(r) < 1e-6: return 0
                r_a = abs(r)
                if y > r_a: return r_a
                sag = r_a - (r_a**2 - y**2)**0.5
                return sag if r > 0 else -sag

            r1 = lens.radius_of_curvature_1
            r2 = lens.radius_of_curvature_2
            t = lens.thickness
            d = lens.diameter
            half_d = d / 2

            x1_vertex = start_x
            sag1_edge = get_sag(r1, half_d)
            x1_edge = x1_vertex + sag1_edge * sc
            
            x2_edge = x1_edge + t * sc
            sag2_edge = get_sag(r2, half_d)
            x2_vertex = x2_edge - sag2_edge * sc

            path = QPainterPath()
            pts = 50
            
            # 1. Front Surface (top to bottom)
            for i in range(pts + 1):
                y = -half_d + (d * i / pts)
                x = x1_vertex + get_sag(r1, abs(y)) * sc
                if i == 0: path.moveTo(x, center_y + y * sc)
                else: path.lineTo(x, center_y + y * sc)
                
            # 2. Bottom Edge
            path.lineTo(x2_edge, center_y + half_d * sc)
            
            # 3. Back Surface (bottom to top)
            for i in range(pts + 1):
                y = half_d - (d * i / pts)
                x = x2_vertex + get_sag(r2, abs(y)) * sc
                path.lineTo(x, center_y + y * sc)
                
            # 4. Top Edge
            path.closeSubpath()
            
            pnt.setPen(QPen(color, 2))
            pnt.setBrush(QBrush(color))
            pnt.drawPath(path)


        # Draw lenses
        if self._system:
            for element in self._system.elements:
                draw_single_lens(painter, element.lens, cx + element.position * scale, cy, scale, self._lens_color)
        else:
            draw_single_lens(painter, self._lens, cx, cy, scale, self._lens_color)
        
        # Draw rays
        painter.setPen(QPen(self._ray_color, 1.5))
        for ray in self._rays:
            if len(ray.path) < 2: continue
            for j in range(len(ray.path) - 1):
                p1, p2 = ray.path[j], ray.path[j + 1]
                if hasattr(p1, 'x'): x1, y1, x2, y2 = p1.x, p1.y, p2.x, p2.y
                else: x1, y1, x2, y2 = p1[0], p1[1], p2[0], p2[1]
                painter.drawLine(int(cx + x1 * scale), int(cy - y1 * scale), int(cx + x2 * scale), int(cy - y2 * scale))
        
        # Ghost rays
        if self._show_ghosts and self._ghost_rays:
            painter.setPen(QPen(self._ghost_color, 1))
            for ghost_path in self._ghost_rays:
                for ray in ghost_path:
                    if len(ray.path) < 2: continue
                    for j in range(len(ray.path) - 1):
                        p1, p2 = ray.path[j], ray.path[j + 1]
                        if hasattr(p1, 'x'): x1, y1, x2, y2 = p1.x, p1.y, p2.x, p2.y
                        else: x1, y1, x2, y2 = p1[0], p1[1], p2[0], p2[1]
                        painter.drawLine(int(cx + x1 * scale), int(cy - y1 * scale), int(cx + x2 * scale), int(cy - y2 * scale))
        
        if self._show_image_sim and self._lens:
            painter.setPen(QPen(QColor(0, 255, 136), 2))
            cx = w // 2
            cy = h // 2
            pattern = self._image_pattern
            
            if pattern == "Star":
                for i in range(8):
                    angle = i * 3.14159 / 4
                    x2 = cx + 80 * (1 if i % 2 else 0.5) * (1 if i < 4 else -1)
                    y2 = cy + 80 * (1 if i % 2 else 0.5) * (1 if (i % 8) < 4 else -1)
                    painter.drawLine(cx, cy, int(x2), int(y2))
            elif pattern == "Grid":
                for i in range(-3, 4):
                    painter.drawLine(cx + i * 25, cy - 75, cx + i * 25, cy + 75)
                    painter.drawLine(cx - 75, cy + i * 25, cx + 75, cy + i * 25)
            elif pattern == "USAF 1951":
                for i in range(6):
                    for j in range(6):
                        size = 5 * (1.122 ** i)
                        x = cx - 50 + j * 20
                        y = cy - 50 + i * 15
                        painter.drawRect(int(x), int(y), int(size), int(size))


class StartupDialog(QDialog):
    """Startup dialog for creating or opening lenses"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("OpenLens")
        self.setModal(True)
        # Set fixed size immediately so geometry calculations are accurate
        self.setFixedSize(650, 650)
        
        self._selected_action = None
        self._selected_data = None
        self._force_centered_count = 0
        
        self._setup_ui()
    
    def moveEvent(self, event):
        """Catch window manager overrides and force center."""
        super().moveEvent(event)
        # If the window manager moves it somewhere else (like 0,0), 
        # we fight back and move it to the center.
        if self._force_centered_count < 5:
            self._recenter()
            self._force_centered_count += 1

    def showEvent(self, event):
        """Final attempt to center when window is mapped."""
        super().showEvent(event)
        self._recenter()
        # Additional timers as a fallback if the window manager is very stubborn
        from PySide6.QtCore import QTimer
        QTimer.singleShot(100, self._recenter)
        QTimer.singleShot(500, self._recenter)

    def _recenter(self):
        """Truly center the window on the active screen."""
        from PySide6.QtGui import QGuiApplication, QCursor
        
        # 1. Detect screen based on current mouse position
        screen = QGuiApplication.screenAt(QCursor.pos())
        if not screen:
            screen = QGuiApplication.primaryScreen()
        
        if screen:
            # 2. Use the AVAILABLE screen geometry (subtracting docks/taskbars)
            avail_geom = screen.availableGeometry()
            
            # 3. Calculate top-left x,y without dividing the width by 2
            # Aligning top-left to total available width/height minus window half-width (325)
            x = avail_geom.x() + avail_geom.width() - 325
            y = avail_geom.y() + avail_geom.height() - 325
            
            current_pos = self.pos()
            if current_pos.x() != x or current_pos.y() != y:
                self.move(x, y)
                # Force the OS to process the move immediately
                from PySide6.QtWidgets import QApplication
                QApplication.processEvents()
    
    def _setup_ui(self):
        from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QPushButton, QListWidget, QLabel, QGroupBox, QWidget, QSizePolicy
        from PySide6.QtCore import Qt
        
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(30, 30, 30, 30)
        
        title = QLabel("Welcome to OpenLens")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #e0e0e0;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        layout.addWidget(QLabel(""))
        
        button_width = 250
        
        new_lens_btn = QPushButton("Create New Lens")
        new_lens_btn.setFixedWidth(button_width)
        new_lens_btn.clicked.connect(self._create_new_lens)
        layout.addWidget(new_lens_btn, alignment=Qt.AlignCenter)
        
        new_assembly_btn = QPushButton("Create New Assembly")
        new_assembly_btn.setFixedWidth(button_width)
        new_assembly_btn.clicked.connect(self._create_new_assembly)
        layout.addWidget(new_assembly_btn, alignment=Qt.AlignCenter)
        
        open_lens_btn = QPushButton("Open Existing Lens")
        open_lens_btn.setFixedWidth(button_width)
        open_lens_btn.clicked.connect(self._show_lens_list)
        layout.addWidget(open_lens_btn, alignment=Qt.AlignCenter)
        
        open_asm_btn = QPushButton("Open Existing Assembly")
        open_asm_btn.setFixedWidth(button_width)
        open_asm_btn.clicked.connect(self._show_assembly_list)
        layout.addWidget(open_asm_btn, alignment=Qt.AlignCenter)
        
        layout.addWidget(QLabel(""))
        
        # Container for dynamic lists
        self.list_container = QWidget()
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.list_container)
        
        # Load existing items from database
        from src.gui.storage import LensStorage
        try:
            storage = LensStorage("openlens.db", lambda x: None)
            self._all_items = storage.load_lenses()
        except:
            self._all_items = []
            
        layout.addStretch()

    def _show_lens_list(self):
        self._show_list("lens")

    def _show_assembly_list(self):
        self._show_list("assembly")

    def _show_list(self, list_type):
        from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QPushButton, QListWidget, QLabel, QGroupBox, QWidget
        from PySide6.QtCore import Qt
        
        # Clear previous list
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                # Recursive cleanup for layouts
                def clear_layout(layout):
                    while layout.count():
                        child = layout.takeAt(0)
                        if child.widget():
                            child.widget().deleteLater()
                        elif child.layout():
                            clear_layout(child.layout())
                clear_layout(item.layout())
        
        if list_type == "lens":
            title = "Available Lenses"
            action = "open_lens"
        else:
            title = "Available Assemblies"
            action = "open_assembly"
            
        group = QGroupBox(title)
        group_layout = QVBoxLayout(group)
        group_layout.setContentsMargins(10, 20, 10, 10) # Add top margin for title
        
        list_widget = QListWidget()
        list_widget.setFixedHeight(200)
        list_widget.setStyleSheet("border: none; background: transparent;") # Remove inner border
        
        items_to_show = []
        for item in self._all_items:
            is_asm = hasattr(item, 'elements') and hasattr(item, 'air_gaps')
            if (list_type == "lens" and not is_asm) or (list_type == "assembly" and is_asm):
                list_widget.addItem(item.name)
                items_to_show.append(item)
                
        list_widget.itemDoubleClicked.connect(lambda: self._open_selected_from_list(list_widget, items_to_show, action))
        group_layout.addWidget(list_widget)
        
        self.list_layout.addWidget(group)
        
        # Import/Delete buttons outside the group box
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        
        button_style = """
            QPushButton {
                background-color: #3d3d3d;
                color: #ffffff;
                font-weight: bold;
                font-size: 20px;
                border: 2px solid #555555;
                border-radius: 4px;
                padding: 0px;
                min-width: 40px;
                min-height: 40px;
            }
            QPushButton:hover {
                background-color: #4d4d4d;
                border-color: #0078d4;
            }
        """
        
        import_btn = QPushButton("+")
        import_btn.setStyleSheet(button_style)
        import_btn.clicked.connect(lambda: self._import_item(list_type))
        btn_row.addWidget(import_btn)
        
        delete_btn = QPushButton("-")
        delete_btn.setStyleSheet(button_style)
        delete_btn.clicked.connect(lambda: self._delete_item_from_list(list_widget, items_to_show, list_type))
        btn_row.addWidget(delete_btn)
        
        self.list_layout.addLayout(btn_row)
        
        open_btn = QPushButton("Open Selected")
        open_btn.setFixedWidth(150)
        open_btn.clicked.connect(lambda: self._open_selected_from_list(list_widget, items_to_show, action))
        self.list_layout.addWidget(open_btn, alignment=Qt.AlignCenter)
        
        # We do NOT call _recenter here anymore, to avoid "jumping" when expanding.
        # The window stays at its current center.

    def _open_selected_from_list(self, list_widget, items, action):
        row = list_widget.currentRow()
        if row >= 0:
            self._selected_action = action
            self._selected_data = items[row]
            self.accept()

    def _delete_item_from_list(self, list_widget, items, list_type):
        row = list_widget.currentRow()
        if row < 0:
            return
            
        item_to_delete = items[row]
        
        from PySide6.QtWidgets import QMessageBox
        import sqlite3
        
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Delete '{item_to_delete.name}'?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
            
        try:
            conn = sqlite3.connect("openlens.db")
            cursor = conn.cursor()
            
            if list_type == "lens":
                cursor.execute("DELETE FROM lenses WHERE id = ?", (item_to_delete.id,))
            else:
                cursor.execute("DELETE FROM assemblies WHERE id = ?", (item_to_delete.id,))
                cursor.execute("DELETE FROM assembly_elements WHERE assembly_id = ?", (item_to_delete.id,))
                cursor.execute("DELETE FROM assembly_air_gaps WHERE assembly_id = ?", (item_to_delete.id,))
            
            conn.commit()
            conn.close()
            
            # Reload and refresh
            from src.gui.storage import LensStorage
            storage = LensStorage("openlens.db", lambda x: None)
            self._all_items = storage.load_lenses()
            self._show_list(list_type)
            
        except Exception as e:
            QMessageBox.critical(self, "Delete Error", f"Failed to delete: {e}")
    
    def _create_new_lens(self):
        self._selected_action = "create_lens"
        self._selected_data = None
        self.accept()
    
    def _create_new_assembly(self):
        self._selected_action = "create_assembly"
        self._selected_data = None
        self.accept()
    
    def _import_item(self, item_type):
        """Import lens or assembly from file"""
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        import json
        
        if item_type == "lens":
            title = "Import Lens"
            filter_str = "JSON Files (*.json);;All Files (*)"
        else:
            title = "Import Assembly"
            filter_str = "JSON Files (*.json);;All Files (*)"
        
        filepath, _ = QFileDialog.getOpenFileName(self, title, "", filter_str)
        
        if not filepath:
            return
        
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            if item_type == "lens":
                item = Lens.from_dict(data)
            else:
                from src.optical_system import OpticalSystem
                item = OpticalSystem.from_dict(data)
            
            # Add to database
            from src.gui.storage import LensStorage
            storage = LensStorage("openlens.db", lambda x: None)
            storage.save_lenses([item])
            
            # Reload lists
            self._all_items = storage.load_lenses()
            
            # Refresh current list view if any
            self._show_list(item_type)
            
            QMessageBox.information(self, "Import Complete", f"Imported: {item.name}")
            
        except Exception as e:
            QMessageBox.critical(self, "Import Error", f"Failed to import: {e}")
    
    def get_result(self):
        return self._selected_action, self._selected_data



class PerformanceVisualizationWidget(QWidget):
    """Performance metrics visualization widget"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._lens = None
        self._metrics = {}
        
        self.setMinimumSize(400, 300)
        self.setStyleSheet("background-color: #1e1e1e; border: 1px solid #3f3f3f;")
        
        from PySide6.QtGui import QColor
        self._bg_color = QColor("#1e1e1e")
        self._axis_color = QColor("#666666")
        self._lens_color = QColor(0, 120, 212, 150)
        self._text_color = QColor("#e0e0e0")
        self._mtf_color = QColor(0, 255, 136, 200)
    
    def update_lens(self, lens):
        """Update lens data"""
        self._lens = lens
        self.update()
    
    def update_metrics(self, metrics):
        """Update metrics data"""
        self._metrics = metrics
        self.update()
    
    def paintEvent(self, event):
        """Paint performance visualization"""
        from PySide6.QtGui import QPainter, QPen, QColor, QBrush, QFont
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        w = self.width()
        h = self.height()
        
        painter.fillRect(0, 0, w, h, self._bg_color)
        
        if not self._lens:
            painter.setPen(QPen(self._text_color, 1))
            painter.drawText(w//2 - 60, h//2, "No lens selected")
            return
        
        cx = w // 2
        cy = h // 2
        
        title_font = QFont("Arial", 12, QFont.Bold)
        painter.setFont(title_font)
        painter.setPen(QPen(self._text_color, 1))
        painter.drawText(10, 25, "Spherical Aberration")
        
        sa = self._metrics.get('spherical', 0)
        
        painter.setPen(QPen(QColor(255, 170, 0), 2))
        painter.drawLine(30, cy, w - 30, cy)
        
        for i in range(-20, 21, 10):
            y_pos = cy - i * 5
            painter.setPen(QPen(self._axis_color, 1))
            painter.drawLine(30, y_pos, w - 30, y_pos)
            
            painter.setPen(QPen(self._text_color, 1))
            painter.drawText(5, y_pos + 4, str(i))


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    # Set dark theme
    app.setStyleSheet("""
        QMainWindow {
            background-color: #1e1e1e;
        }
        QWidget {
            background-color: #1e1e1e;
            color: #e0e0e0;
        }
        QGroupBox {
            color: #e0e0e0;
            border: 1px solid #3f3f3f;
            border-radius: 5px;
            margin-top: 10px;
            font-weight: bold;
            padding-top: 10px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
        }
        QDoubleSpinBox, QSpinBox {
            background-color: #2d2d2d;
            color: #e0e0e0;
            border: 1px solid #3f3f3f;
            padding: 3px;
        }
        QPushButton {
            background-color: #2d2d2d;
            color: #e0e0e0;
            border: 1px solid #3f3f3f;
            padding: 5px 15px;
        }
        QPushButton:hover {
            background-color: #3d3d3d;
        }
        QPushButton:pressed {
            background-color: #0078d4;
        }
    """)
    
    startup = StartupDialog()
    result = startup.exec()
    
    if result == 0:
        return
    
    action, data = startup.get_result()
    
    window = OpenLensWindow(action=action, data=data)
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()