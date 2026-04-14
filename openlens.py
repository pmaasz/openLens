#!/usr/bin/env python3
"""
OpenLens - Optical Lens Design Application
PySide6-based modern GUI
"""

import sys
import os
import logging

logger = logging.getLogger(__name__)

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                               QLabel, QListWidget, QListWidgetItem, QPushButton, 
                               QDoubleSpinBox, QSpinBox, QLineEdit, QGroupBox, QFormLayout, 
                               QFrame, QTabWidget, QComboBox, QCheckBox, QDialog, QStatusBar)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QKeySequence

from src.lens import Lens
from src.services import LensService


class OpenLensWindow(QMainWindow):
    """Main application window"""
    
    def __init__(self, action=None, data=None):
        super().__init__()
        
        self._action = action
        self._data = data
        self._theme = 'dark'
        
        self.setWindowTitle("OpenLens - Optical Lens Design")
        self.setMinimumSize(1400, 900)
        
        # Initialize database
        self._db_path = "openlens.db"
        self._load_from_database()
        
        self._setup_ui()
        self._create_menu()
        
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
        """Load lens from saved data"""
        if isinstance(data, dict):
            self._lenses.append(data)
            self._current_lens = data if isinstance(data, Lens) else None
        else:
            self._load_default_lens()
        
        self._update_lens_list()
        if self._current_lens:
            self._lens_editor.load_lens(self._current_lens)
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
        
        # Left: Lens list (sidebar)
        self._lens_list = []  # Will be QListWidget
        
        # Right: Editor with visualization
        self._editor_widget = None  # Will be LensEditorWidget
        
        content_layout.addWidget(self._create_sidebar(), 1)
        content_layout.addWidget(self._create_editor_area(), 3)
        
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
    
    def _create_sidebar(self):
        """Create lens list sidebar"""
        from PySide6.QtWidgets import QListWidget, QListWidgetItem, QPushButton, QVBoxLayout, QWidget, QLabel, QFrame
        
        sidebar = QFrame()
        sidebar.setFrameShape(QFrame.StyledPanel)
        layout = QVBoxLayout(sidebar)
        
        title = QLabel("Lenses")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #e0e0e0;")
        layout.addWidget(title)
        
        self._lens_list_widget = QListWidget()
        self._lens_list_widget.setStyleSheet("""
            QListWidget {
                background-color: #2d2d2d;
                color: #e0e0e0;
                border: 1px solid #3f3f3f;
            }
            QListWidget::item:selected {
                background-color: #0078d4;
            }
        """)
        self._lens_list_widget.currentRowChanged.connect(self._on_lens_selected)
        layout.addWidget(self._lens_list_widget)
        
        # Mode toggle (Lens/Assembly)
        btn_layout = QHBoxLayout()
        new_lens_btn = QPushButton("New Lens")
        new_lens_btn.clicked.connect(self._on_new_lens)
        new_lens_btn.setStyleSheet("QPushButton { padding: 3px; }")
        
        new_asm_btn = QPushButton("New Assembly")
        new_asm_btn.clicked.connect(self._on_new_assembly)
        new_asm_btn.setStyleSheet("QPushButton { padding: 3px; }")
        
        delete_btn = QPushButton("Delete")
        delete_btn.clicked.connect(self._on_delete_lens)
        
        btn_layout.addWidget(new_lens_btn)
        btn_layout.addWidget(new_asm_btn)
        btn_layout.addWidget(delete_btn)
        layout.addLayout(btn_layout)
        
        return sidebar
    
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
        
        controls_layout.addWidget(source_group)
        
        # Simulation buttons
        btn_layout = QHBoxLayout()
        run_btn = QPushButton("Run Simulation")
        run_btn.clicked.connect(self._on_run_simulation)
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self._on_clear_simulation)
        btn_layout.addWidget(run_btn)
        btn_layout.addWidget(clear_btn)
        controls_layout.addLayout(btn_layout)
        
        # Ghost analysis checkbox
        self._ghost_analysis = QCheckBox("Show Ghost Analysis")
        controls_layout.addWidget(self._ghost_analysis)
        
        ghost_note = QLabel("Analyze 2nd order reflections")
        ghost_note.setStyleSheet("color: #888; font-size: 10px;")
        controls_layout.addWidget(ghost_note)
        
        # Image simulation checkbox
        img_sim_group = QGroupBox("Image Simulation")
        img_sim_layout = QVBoxLayout(img_sim_group)
        
        self._img_sim_check = QCheckBox("Enable")
        img_sim_layout.addWidget(self._img_sim_check)
        
        self._img_pattern = QComboBox()
        self._img_pattern.addItems(["Star", "Grid", "USAF 1951", "Slant Edge"])
        img_sim_layout.addWidget(QLabel("Pattern:"))
        img_sim_layout.addWidget(self._img_pattern)
        
        controls_layout.addWidget(img_sim_group)
        
        controls_layout.addStretch()
        
        layout.addWidget(controls, 1)
        
        # Right: Visualization
        self._sim_viz = SimulationVisualizationWidget()
        layout.addWidget(self._sim_viz, 3)
        
        return sim
    
    def _on_run_simulation(self):
        """Run ray tracing simulation"""
        if self._current_lens:
            num_rays = int(self._sim_num_rays.value())
            angle = self._sim_angle.value()
            source_height = self._sim_source_height.value()
            show_ghosts = self._ghost_analysis.isChecked() if hasattr(self, '_ghost_analysis') else False
            self._sim_viz.run_simulation(self._current_lens, num_rays, angle, source_height, show_ghosts)
    
    def _on_clear_simulation(self):
        """Clear simulation visualization"""
        self._sim_viz.clear_simulation()
    
    def _create_performance_tab(self):
        """Create the Performance tab"""
        from src.aberrations import AberrationsCalculator
        
        perf = QWidget()
        layout = QHBoxLayout(perf)
        layout.setContentsMargins(10, 10, 10, 10)
        
        left = QWidget()
        left_layout = QVBoxLayout(left)
        
        title = QLabel("Performance Metrics")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        left_layout.addWidget(title)
        
        metrics_group = QGroupBox("Optical Performance")
        metrics_layout = QFormLayout(metrics_group)
        
        self._perf_long_focal = QLabel("-")
        self._perf_long_focal.setStyleSheet("color: #00a0ff; font-weight: bold;")
        metrics_layout.addRow("Focal Length:", self._perf_long_focal)
        
        self._perf_power = QLabel("-")
        self._perf_power.setStyleSheet("color: #00a0ff; font-weight: bold;")
        metrics_layout.addRow("Optical Power:", self._perf_power)
        
        self._perf_back_focal = QLabel("-")
        self._perf_back_focal.setStyleSheet("color: #00a0ff; font-weight: bold;")
        metrics_layout.addRow("Back Focal Length:", self._perf_back_focal)
        
        left_layout.addWidget(metrics_group)
        
        aber_group = QGroupBox("Aberrations")
        aber_layout = QFormLayout(aber_group)
        
        self._perf_spherical = QLabel("-")
        self._perf_spherical.setStyleSheet("color: #ffaa00;")
        aber_layout.addRow("Spherical:", self._perf_spherical)
        
        self._perf_coma = QLabel("-")
        self._perf_coma.setStyleSheet("color: #ffaa00;")
        aber_layout.addRow("Coma:", self._perf_coma)
        
        self._perf_astig = QLabel("-")
        self._perf_astig.setStyleSheet("color: #ffaa00;")
        aber_layout.addRow("Astigmatism:", self._perf_astig)
        
        self._perf_distortion = QLabel("-")
        self._perf_distortion.setStyleSheet("color: #ffaa00;")
        aber_layout.addRow("Distortion:", self._perf_distortion)
        
        self._perf_mtfc = QLabel("-")
        self._perf_mtfc.setStyleSheet("color: #00ff88;")
        aber_layout.addRow("MTF Cutoff:", self._perf_mtfc)
        
        left_layout.addWidget(aber_group)
        
        left_layout.addStretch()
        
        layout.addWidget(left, 1)
        
        self._perf_viz = PerformanceVisualizationWidget()
        layout.addWidget(self._perf_viz, 2)
        
        self._perf_viz.update_lens(None)
        
        return perf
    
    def _update_performance_metrics(self):
        """Update performance metrics for current lens"""
        if not self._current_lens:
            return
        
        try:
            fl = self._current_lens.calculate_focal_length()
            if fl:
                self._perf_long_focal.setText(f"{fl:.2f} mm")
            else:
                self._perf_long_focal.setText("Infinite")
            
            power = self._current_lens.calculate_optical_power()
            if power:
                self._perf_power.setText(f"{power:.4f} D")
            else:
                self._perf_power.setText("-")
            
            bfl = self._current_lens.calculate_back_focal_length()
            if bfl:
                self._perf_back_focal.setText(f"{bfl:.2f} mm")
            else:
                self._perf_back_focal.setText("-")
            
            from src.aberrations import AberrationsCalculator
            calculator = AberrationsCalculator(self._current_lens)
            results = calculator.calculate_all()
            
            self._perf_spherical.setText(f"{results.get('spherical', 0):.4f} mm")
            self._perf_coma.setText(f"{results.get('coma', 0):.4f} mm")
            self._perf_astig.setText(f"{results.get('astigmatism', 0):.4f} mm")
            self._perf_distortion.setText(f"{results.get('distortion', 0):.4f} %")
            self._perf_mtfc.setText(f"{results.get('mtf_cutoff', 0):.1f} lp/mm")
            
            self._perf_viz.update_lens(self._current_lens)
            self._perf_viz.update_metrics(results)
            
        except Exception as e:
            print(f"Performance update error: {e}")
    
    def _create_optimization_tab(self):
        """Create the Optimization tab"""
        from src.optimizer import LensOptimizer
        
        opt = QWidget()
        layout = QHBoxLayout(opt)
        layout.setContentsMargins(10, 10, 10, 10)
        
        left = QWidget()
        left_layout = QVBoxLayout(left)
        
        title = QLabel("Lens Optimization")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        left_layout.addWidget(title)
        
        targets_group = QGroupBox("Optimization Targets")
        targets_layout = QFormLayout(targets_group)
        
        self._opt_target_fl = QDoubleSpinBox()
        self._opt_target_fl.setRange(1, 1000)
        self._opt_target_fl.setValue(50)
        self._opt_target_fl.setSuffix(" mm")
        targets_layout.addRow("Target Focal Length:", self._opt_target_fl)
        
        self._opt_target_fno = QDoubleSpinBox()
        self._opt_target_fno.setRange(1, 20)
        self._opt_target_fno.setValue(2)
        targets_layout.addRow("Target F/#:", self._opt_target_fno)
        
        self._opt_target_bfl = QDoubleSpinBox()
        self._opt_target_bfl.setRange(1, 500)
        self._opt_target_bfl.setValue(45)
        self._opt_target_bfl.setSuffix(" mm")
        targets_layout.addRow("Target BFL:", self._opt_target_bfl)
        
        left_layout.addWidget(targets_group)
        
        variables_group = QGroupBox("Variables to Optimize")
        variables_layout = QVBoxLayout(variables_group)
        
        self._opt_var_r1 = QCheckBox("Radius 1")
        self._opt_var_r1.setChecked(True)
        variables_layout.addWidget(self._opt_var_r1)
        
        self._opt_var_r2 = QCheckBox("Radius 2")
        self._opt_var_r2.setChecked(True)
        variables_layout.addWidget(self._opt_var_r2)
        
        self._opt_var_thickness = QCheckBox("Thickness")
        self._opt_var_thickness.setChecked(True)
        variables_layout.addWidget(self._opt_var_thickness)
        
        self._opt_var_material = QCheckBox("Material (n)")
        variables_layout.addWidget(self._opt_var_material)
        
        left_layout.addWidget(variables_group)
        
        btn_layout = QHBoxLayout()
        run_opt_btn = QPushButton("Run Optimization")
        run_opt_btn.clicked.connect(self._on_run_optimization)
        reset_btn = QPushButton("Reset")
        reset_btn.clicked.connect(self._on_reset_optimization)
        btn_layout.addWidget(run_opt_btn)
        btn_layout.addWidget(reset_btn)
        left_layout.addLayout(btn_layout)
        
        self._opt_result = QLabel("Ready")
        self._opt_result.setStyleSheet("padding: 10px; background: #2d2d2d; border-radius: 5px;")
        left_layout.addWidget(self._opt_result)
        
        left_layout.addStretch()
        
        layout.addWidget(left, 1)
        
        self._opt_viz = LensVisualizationWidget()
        layout.addWidget(self._opt_viz, 2)
        
        return opt
    
    def _on_run_optimization(self):
        """Run lens optimization"""
        if not self._current_lens:
            return
        
        target_fl = self._opt_target_fl.value()
        target_fno = self._opt_target_fno.value()
        
        variables = []
        if self._opt_var_r1.isChecked():
            variables.append('radius_1')
        if self._opt_var_r2.isChecked():
            variables.append('radius_2')
        if self._opt_var_thickness.isChecked():
            variables.append('thickness')
        
        if not variables:
            self._opt_result.setText("Select at least one variable")
            return
        
        self._opt_result.setText("Optimizing...")
        
        try:
            lens = self._current_lens
            original_fl = lens.calculate_focal_length()
            
            if original_fl and abs(original_fl - target_fl) < 0.1:
                self._opt_result.setText(f"Already at target!\nFL: {original_fl:.2f} mm")
            else:
                step = 0.5 if original_fl and original_fl > target_fl else -0.5
                for i in range(50):
                    if 'radius_1' in variables:
                        lens.radius_of_curvature_1 += step
                    if 'radius_2' in variables:
                        lens.radius_of_curvature_2 -= step
                    
                    new_fl = lens.calculate_focal_length()
                    if new_fl and abs(new_fl - target_fl) < 0.1:
                        break
                
                new_fl = lens.calculate_focal_length()
                self._opt_result.setText(f"Optimized!\nTarget: {target_fl:.1f} mm\nResult: {new_fl:.2f} mm" if new_fl else "Error")
                self._lens_editor.load_lens(lens)
                self._update_all_tabs()
                
        except Exception as e:
            self._opt_result.setText(f"Error: {str(e)[:30]}")
    
    def _on_reset_optimization(self):
        """Reset optimization to defaults"""
        if self._current_lens:
            self._lens_editor.load_lens(self._current_lens)
            self._opt_result.setText("Reset complete")
    
    def _create_tolerancing_tab(self):
        """Create the Tolerancing tab"""
        tol = QWidget()
        layout = QHBoxLayout(tol)
        layout.setContentsMargins(10, 10, 10, 10)
        
        left = QWidget()
        left_layout = QVBoxLayout(left)
        
        title = QLabel("Tolerancing Analysis")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        left_layout.addWidget(title)
        
        tol_group = QGroupBox("Tolerance Sensitivities")
        tol_layout = QFormLayout(tol_group)
        
        self._tol_surface_sig = QDoubleSpinBox()
        self._tol_surface_sig.setRange(0.001, 1)
        self._tol_surface_sig.setValue(0.05)
        self._tol_surface_sig.setSuffix(" mm")
        tol_layout.addRow("Surface Sign:", self._tol_surface_sig)
        
        self._tol_thickness_sig = QDoubleSpinBox()
        self._tol_thickness_sig.setRange(0.001, 1)
        self._tol_thickness_sig.setValue(0.02)
        self._tol_thickness_sig.setSuffix(" mm")
        tol_layout.addRow("Thickness:", self._tol_thickness_sig)
        
        self._tol_index_sig = QDoubleSpinBox()
        self._tol_index_sig.setRange(0.0001, 0.1)
        self._tol_index_sig.setValue(0.001)
        tol_layout.addRow("Index (n):", self._tol_index_sig)
        
        left_layout.addWidget(tol_group)
        
        results_group = QGroupBox("Sensitivity Results")
        results_layout = QFormLayout(results_group)
        
        self._tol_fl_sens = QLabel("-")
        results_layout.addRow("FL Sensitivity:", self._tol_fl_sens)
        
        self._tol_power_sens = QLabel("-")
        results_layout.addRow("Power Sensitivity:", self._tol_power_sens)
        
        self._tol_bfl_sens = QLabel("-")
        results_layout.addRow("BFL Sensitivity:", self._tol_bfl_sens)
        
        left_layout.addWidget(results_group)
        
        btn_layout = QHBoxLayout()
        calc_btn = QPushButton("Calculate")
        calc_btn.clicked.connect(self._on_calculate_tolerances)
        btn_layout.addWidget(calc_btn)
        left_layout.addLayout(btn_layout)
        
        left_layout.addStretch()
        
        layout.addWidget(left, 1)
        
        self._tol_viz = LensVisualizationWidget()
        layout.addWidget(self._tol_viz, 2)
        
        return tol
    
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
        sys_layout.addWidget(self._system_list)
        
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
    
    def _on_remove_lens_from_system(self):
        """Remove selected lens from system"""
        current = self._system_list.currentRow()
        if current >= 0 and current < len(self._optical_system.elements):
            self._optical_system.remove_lens(current)
            self._update_system_list()
            self._assembly_viz.update_system(self._optical_system)
    
    def _on_move_lens_up(self):
        """Move lens up in system"""
        current = self._system_list.currentRow()
        if current > 0:
            self._optical_system.elements[current], self._optical_system.elements[current-1] = \
                self._optical_system.elements[current-1], self._optical_system.elements[current]
            self._update_system_list()
            self._assembly_viz.update_system(self._optical_system)
    
    def _on_move_lens_down(self):
        """Move lens down in system"""
        current = self._system_list.currentRow()
        if current >= 0 and current < len(self._optical_system.elements) - 1:
            self._optical_system.elements[current], self._optical_system.elements[current+1] = \
                self._optical_system.elements[current+1], self._optical_system.elements[current]
            self._update_system_list()
            self._assembly_viz.update_system(self._optical_system)
    
    def _update_system_list(self):
        """Update the system list"""
        self._system_list.clear()
        for element in self._optical_system.elements:
            lens = element.lens
            self._system_list.addItem(f"{lens.name} (n={lens.refractive_index:.3f})")
    
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
        """Update the lens list widget with lenses and assemblies"""
        self._lens_list_widget.clear()
        for lens in self._lenses:
            self._lens_list_widget.addItem(lens.name)
        for assembly in self._assemblies:
            self._lens_list_widget.addItem(f"[{assembly.name}]")
    
    def _on_lens_selected(self, row):
        """Handle lens/assembly selection from list"""
        if row >= 0:
            # Check if row is in lenses or assemblies list
            if row < len(self._lenses):
                self._current_lens = self._lenses[row]
                self._current_assembly = None
                self._show_assembly_editor(False)
                self._lens_editor.load_lens(self._current_lens)
                self._update_all_tabs()
                self._update_status(f"Selected lens: {self._current_lens.name}")
            elif row - len(self._lenses) < len(self._assemblies):
                idx = row - len(self._lenses)
                self._current_assembly = self._assemblies[idx]
                self._current_lens = None
                self._show_assembly_editor(True)
                self._editor_tabs.setCurrentIndex(1)
                self._load_assembly(self._current_assembly)
                self._update_status(f"Selected assembly: {self._current_assembly.name} ({len(self._current_assembly.elements)} elements)")
    
    def _load_assembly(self, assembly):
        """Load assembly into assembly editor"""
        if hasattr(self, '_optical_system'):
            self._optical_system = assembly
        if hasattr(self, '_assembly_viz'):
            self._assembly_viz.update_system(assembly)
        if hasattr(self, '_system_list'):
            self._update_system_list()
    
    def _update_all_tabs(self):
        """Update all tab displays for current lens"""
        if not self._current_lens:
            return
        
        if hasattr(self, '_sim_viz'):
            self._sim_viz.run_simulation(self._current_lens, 
                                  int(self._sim_num_rays.value()) if hasattr(self, '_sim_num_rays') else 11,
                                  self._sim_angle.value() if hasattr(self, '_sim_angle') else 0,
                                  self._sim_source_height.value() if hasattr(self, '_sim_source_height') else 0)
        
        if hasattr(self, '_opt_viz'):
            self._opt_viz.update_lens(self._current_lens)
        
        if hasattr(self, '_tol_viz'):
            self._tol_viz.update_lens(self._current_lens)
        
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
        """Delete selected lens or assembly"""
        current = self._lens_list_widget.currentRow()
        if current < 0:
            return
        
        if current < len(self._lenses):
            # It's a lens
            if len(self._lenses) > 1:
                self._lenses.pop(current)
                self._current_lens = self._lenses[0]
                self._current_assembly = None
                self._lens_editor.load_lens(self._current_lens)
                self._update_status(f"Deleted. Selected: {self._current_lens.name}")
        else:
            # It's an assembly
            asm_idx = current - len(self._lenses)
            if asm_idx < len(self._assemblies):
                self._assemblies.pop(asm_idx)
                if self._assemblies:
                    self._current_assembly = self._assemblies[0]
                else:
                    self._current_assembly = None
                self._update_status("Deleted assembly")
        
        self._update_lens_list()
        self._update_all_tabs()
    
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
        """)
    
    def _on_reset_window(self):
        """Reset window to default size and position"""
        self.resize(1400, 900)
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
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Left: Properties panel
        props_panel = self._create_properties_panel()
        layout.addWidget(props_panel, 1)
        
        # Right: Visualization
        self._viz_widget = LensVisualizationWidget()
        layout.addWidget(self._viz_widget, 2)
    
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
        layout.addWidget(name_group)
        
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
        self._n_input.valueChanged.connect(self._on_property_changed)
        mat_layout.addRow("Refractive Index:", self._n_input)
        
        layout.addWidget(mat_group)
        
        # Fresnel properties
        self._fresnel_group = QGroupBox("Fresnel Properties")
        fresnel_layout = QFormLayout(self._fresnel_group)
        
        self._fresnel_check = QCheckBox()
        self._fresnel_check.setText("Enable Fresnel Lens")
        self._fresnel_check.stateChanged.connect(self._on_fresnel_changed)
        fresnel_layout.addRow("Fresnel:", self._fresnel_check)
        
        self._groove_pitch_input = QDoubleSpinBox()
        self._groove_pitch_input.setRange(0.01, 10)
        self._groove_pitch_input.setValue(0.5)
        self._groove_pitch_input.setSuffix(" mm")
        self._groove_pitch_input.setEnabled(False)
        fresnel_layout.addRow("Groove Pitch:", self._groove_pitch_input)
        
        self._num_grooves_label = QLabel("0")
        fresnel_layout.addRow("Number of Grooves:", self._num_grooves_label)
        
        layout.addWidget(self._fresnel_group)
        
        # Calculated
        calc_group = QGroupBox("Calculated Properties")
        calc_layout = QFormLayout(calc_group)
        
        self._focal_label = QLabel("--")
        calc_layout.addRow("Focal Length:", self._focal_label)
        
        self._power_label = QLabel("--")
        calc_layout.addRow("Power:", self._power_label)
        
        layout.addWidget(calc_group)
        
        layout.addStretch()
        
        return frame
    
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
    
    def _on_fresnel_changed(self, state):
        """Handle Fresnel checkbox change"""
        enabled = state == 2  # Qt.Checked
        self._groove_pitch_input.setEnabled(enabled)
        if enabled and self._lens:
            self._lens.is_fresnel = True
            self._update_groove_count()
        elif self._lens:
            self._lens.is_fresnel = False
            self._num_grooves_label.setText("0")
    
    def _update_groove_count(self):
        """Calculate number of grooves"""
        if not self._lens or not hasattr(self._lens, 'is_fresnel') or not self._lens.is_fresnel:
            return
        pitch = self._groove_pitch_input.value()
        diameter = self._lens.diameter
        if pitch > 0:
            grooves = int(diameter / (2 * pitch))
            self._num_grooves_label.setText(str(grooves))
    
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
        else:
            self._focal_label.setText("∞")
            self._power_label.setText("0 D")
    
    def load_lens(self, lens):
        """Load a lens into the editor"""
        self._lens = lens
        self._name_input.setText(lens.name)
        self._r1_input.setValue(lens.radius_of_curvature_1)
        self._r2_input.setValue(lens.radius_of_curvature_2)
        self._thickness_input.setValue(lens.thickness)
        self._diameter_input.setValue(lens.diameter)
        self._n_input.setValue(lens.refractive_index)
        self._update_calculated()
        self._viz_widget.update_lens(lens)


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
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._lens = None
        self._view_mode = "2D"
        
        self.setMinimumSize(400, 300)
        self.setStyleSheet("background-color: #1e1e1e;")
        
        from PySide6.QtGui import QColor
        self._bg_color = QColor("#1e1e1e")
        self._lens_color = QColor(0, 120, 212, 150)
        self._text_color = QColor("#e0e0e0")
        self._axis_color = QColor("#666666")
    
    def set_view_mode(self, mode):
        self._view_mode = mode
        self.update()
    
    def update_lens(self, lens):
        self._lens = lens
        self.update()
    
    def paintEvent(self, event):
        from PySide6.QtGui import QPainter, QPen, QColor, QPainterPath, QBrush
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
        
        max_dim = max(thickness * 3, diameter, 200) * 1.5
        scale = min(w, h) / max_dim / 2
        cx, cy = w/2 - thickness*scale/2, h/2
        
        painter.setPen(QPen(self._axis_color, 1))
        painter.drawLine(0, cy, w, cy)
        
        path = QPainterPath()
        r1_abs = abs(r1) * scale
        for i in range(51):
            y = -diameter/2*scale + diameter*scale*i/50
            if abs(y) <= r1_abs and r1_abs > 0:
                x = cx + (r1_abs - (r1_abs**2 - y**2)**0.5) if r1 > 0 else cx - (r1_abs - (r1_abs**2 - y**2)**0.5)
                path.moveTo(x, cy+y) if i == 0 else path.lineTo(x, cy+y)
        
        r2_abs = abs(r2) * scale
        for i in range(51):
            y = diameter/2*scale - diameter*scale*i/50
            if abs(y) <= r2_abs and r2_abs > 0:
                x = cx + thickness*scale + (r2_abs - (r2_abs**2 - y**2)**0.5) if r2 > 0 else cx + thickness*scale - (r2_abs - (r2_abs**2 - y**2)**0.5)
                path.lineTo(x, cy+y)
        
        path.closeSubpath()
        painter.setPen(QPen(self._lens_color, 2))
        painter.setBrush(QBrush(self._lens_color))
        painter.drawPath(path)


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
            
            self._ax = self._figure.add_subplot(111, projection='3d', facecolor='#1e1e1e')
            self._ax.set_facecolor('#1e1e1e')
            
        except ImportError:
            from PySide6.QtWidgets import QLabel
            layout = QVBoxLayout(self)
            lbl = QLabel("Install matplotlib\nfor 3D view")
            lbl.setStyleSheet("color: #888; padding: 50px;")
            layout.addWidget(lbl)
    
    def update_lens(self, lens):
        if not lens or not self._ax or not self._figure:
            return
        
        self._ax.clear()
        self._ax.set_facecolor('#1e1e1e')
        
        r1, r2 = lens.radius_of_curvature_1, lens.radius_of_curvature_2
        thickness, diameter = lens.thickness, lens.diameter
        
        import numpy as np
        u = np.linspace(0, 2*np.pi, 30)
        v = np.linspace(0, diameter/2, 20)
        U, V = np.meshgrid(u, v)
        
        X = V * np.cos(U)
        Y = V * np.sin(U)
        
        if abs(r1) > 0.1:
            val = r1**2 - X**2 - Y**2
            Z = np.sqrt(np.maximum(0, val))
            self._ax.plot_surface(X, Y, Z, alpha=0.6, color='cyan')
        
        if abs(r2) > 0.1:
            val2 = r2**2 - X**2 - Y**2
            Z2 = thickness - np.sqrt(np.maximum(0, val2))
            self._ax.plot_surface(X, Y, Z2, alpha=0.6, color='magenta')
        
        self._ax.set_xlabel('X', color='#aaa')
        self._ax.set_ylabel('Y', color='#aaa')
        self._ax.set_zlabel('Z', color='#aaa')
        self._ax.tick_params(colors='#aaa')
        
        self._canvas.draw()
        
        return  # End of _3DVisualizationWidget
    
    def paintEvent(self, event):
        # Fallback 2D drawing if matplotlib not available
        from PySide6.QtGui import QPainter
        painter = QPainter(self)
        w, h = self.width(), self.height()
        from PySide6.QtGui import QColor
        painter.fillRect(0, 0, w, h, QColor("#1e1e1e"))
        
        # Draw lens
        path = QPainterPath()
        
        # Front surface
        r1_abs = abs(r1) * scale
        for i in range(51):
            y = -diameter/2 * scale + diameter * scale * i / 50
            if abs(y) <= r1_abs:
                x = cx + (r1_abs - (r1_abs**2 - y**2)**0.5) if r1 > 0 else cx - (r1_abs - (r1_abs**2 - y**2)**0.5)
                if i == 0:
                    path.moveTo(x, cy + y)
                else:
                    path.lineTo(x, cy + y)
        
        # Back surface
        r2_abs = abs(r2) * scale
        for i in range(51):
            y = diameter/2 * scale - diameter * scale * i / 50
            if abs(y) <= r2_abs:
                x = cx + thickness * scale + (r2_abs - (r2_abs**2 - y**2)**0.5) if r2 > 0 else cx + thickness * scale - (r2_abs - (r2_abs**2 - y**2)**0.5)
                path.lineTo(x, cy + y)
        
        path.closeSubpath()
        
        painter.setPen(QPen(self._lens_color, 2))
        painter.setBrush(QBrush(self._lens_color))
        painter.drawPath(path)
        
        # Labels
        painter.setPen(QPen(self._text_color, 1))
        painter.drawText(cx, cy - diameter * scale / 2 - 5, "R1")
        painter.drawText(cx + thickness * scale, cy - diameter * scale / 2 - 5, "R2")


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
        
        path = QPainterPath()
        
        # Front surface
        r1_abs = abs(r1) * scale
        for i in range(51):
            y = -diameter/2 * scale + diameter * scale * i / 50
            if abs(y) <= r1_abs:
                x = cx + (r1_abs - (r1_abs**2 - y**2)**0.5) if r1 > 0 else cx - (r1_abs - (r1_abs**2 - y**2)**0.5)
                if i == 0:
                    path.moveTo(x, cy + y)
                else:
                    path.lineTo(x, cy + y)
        
        # Back surface
        r2_abs = abs(r2) * scale
        for i in range(51):
            y = diameter/2 * scale - diameter * scale * i / 50
            if abs(y) <= r2_abs:
                x = cx + thickness * scale + (r2_abs - (r2_abs**2 - y**2)**0.5) if r2 > 0 else cx + thickness * scale - (r2_abs - (r2_abs**2 - y**2)**0.5)
                path.lineTo(x, cy + y)
        
        path.closeSubpath()
        
        painter.setPen(QPen(color, 2))
        painter.setBrush(QBrush(color))
        painter.drawPath(path)


class SimulationVisualizationWidget(QWidget):
    """2D ray tracing simulation visualization widget"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._lens = None
        self._rays = []
        
        self.setMinimumSize(400, 300)
        self.setStyleSheet("background-color: #1e1e1e; border: 1px solid #3f3f3f;")
        
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
    
    def run_simulation(self, lens, num_rays=11, angle=0, source_height=0, show_ghosts=False):
        """Run ray tracing simulation"""
        self._lens = lens
        self._rays = []
        self._ghost_rays = []
        self._show_ghosts = show_ghosts
        
        try:
            from src.ray_tracer import LensRayTracer
            from src.ray_tracer import Ray
            
            tracer = LensRayTracer(lens)
            
            angle_rad = angle * 3.14159 / 180.0
            diameter = lens.diameter
            
            for i in range(num_rays):
                if num_rays == 1:
                    h = 0
                else:
                    h = -diameter/2 + diameter * i / (num_rays - 1)
                
                ray = Ray(-100, h + source_height, angle=angle_rad)
                tracer.trace_ray(ray)
                self._rays.append(ray)
            
            if show_ghosts and lens:
                self._run_ghost_analysis(lens, tracer)
        
        except Exception as e:
            print(f"Simulation error: {e}")
        
        self.update()
    
    def _run_ghost_analysis(self, lens, tracer):
        """Run ghost analysis for 2nd order reflections"""
        try:
            from src.optical_system import OpticalSystem
            from src.analysis.ghost import GhostAnalyzer
            
            system = OpticalSystem(name="Ghost Analysis")
            system.add_lens(lens, air_gap_before=5.0)
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
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        w = self.width()
        h = self.height()
        
        painter.fillRect(0, 0, w, h, self._bg_color)
        
        if not self._lens:
            painter.setPen(QPen(self._text_color, 1))
            painter.drawText(w//2 - 80, h//2, "Run simulation to see rays")
            return
        
        # Draw axis
        painter.setPen(QPen(self._axis_color, 1, Qt.DashLine))
        painter.drawLine(0, h//2, w, h//2)
        
        # Lens geometry
        r1 = self._lens.radius_of_curvature_1
        r2 = self._lens.radius_of_curvature_2
        thickness = self._lens.thickness
        diameter = self._lens.diameter
        
        max_dim = max(thickness * 3, diameter, 200) * 1.5
        scale = min(w, h) / max_dim / 2
        
        cx = w / 2 - thickness * scale / 2
        cy = h / 2
        
        # Draw lens
        path = QPainterPath()
        r1_abs = abs(r1) * scale
        for i in range(51):
            y = -diameter/2 * scale + diameter * scale * i / 50
            if abs(y) <= r1_abs and r1_abs > 0:
                x = cx + (r1_abs - (r1_abs**2 - y**2)**0.5) if r1 > 0 else cx - (r1_abs - (r1_abs**2 - y**2)**0.5)
                if i == 0:
                    path.moveTo(x, cy + y)
                else:
                    path.lineTo(x, cy + y)
        
        r2_abs = abs(r2) * scale
        for i in range(51):
            y = diameter/2 * scale - diameter * scale * i / 50
            if abs(y) <= r2_abs and r2_abs > 0:
                x = cx + thickness * scale + (r2_abs - (r2_abs**2 - y**2)**0.5) if r2 > 0 else cx + thickness * scale - (r2_abs - (r2_abs**2 - y**2)**0.5)
                path.lineTo(x, cy + y)
        
        path.closeSubpath()
        
        painter.setPen(QPen(self._lens_color, 2))
        painter.setBrush(QBrush(self._lens_color))
        painter.drawPath(path)
        
        # Draw rays
        painter.setPen(QPen(self._ray_color, 1.5))
        
        for ray in self._rays:
            if len(ray.path) < 2:
                continue
            
            # Convert path points to widget coordinates
            for j in range(len(ray.path) - 1):
                x1, y1 = ray.path[j]
                x2, y2 = ray.path[j + 1]
                
                wx1 = cx + x1 * scale
                wy1 = cy - y1 * scale
                wx2 = cx + x2 * scale
                wy2 = cy - y2 * scale
                
                painter.drawLine(int(wx1), int(wy1), int(wx2), int(wy2))
        
        if self._show_ghosts and self._ghost_rays:
            painter.setPen(QPen(self._ghost_color, 1))
            for ghost_path in self._ghost_rays:
                for ray in ghost_path:
                    if len(ray.path) < 2:
                        continue
                    for j in range(len(ray.path) - 1):
                        x1, y1 = ray.path[j]
                        x2, y2 = ray.path[j + 1]
                        wx1 = cx + x1 * scale
                        wy1 = cy - y1 * scale
                        wx2 = cx + x2 * scale
                        wy2 = cy - y2 * scale
                        painter.drawLine(int(wx1), int(wy1), int(wx2), int(wy2))
        
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
        self.setFixedSize(650, 650)
        
        self._selected_action = None
        self._selected_data = None
        self._centered = False
        
        self._setup_ui()
    
    def showEvent(self, event):
        """Center on screen when dialog is shown"""
        super().showEvent(event)
        # Use a timer to ensure the window is mapped and window manager 
        # has finished its initial placement before we override it.
        from PySide6.QtCore import QTimer
        # 100ms is a safe delay for most Linux/X11 window managers
        QTimer.singleShot(100, self._recenter)

    def _recenter(self):
        """Truly center the window on the active screen."""
        from PySide6.QtGui import QGuiApplication, QCursor
        
        # 1. Detect screen based on current mouse position
        screen = QGuiApplication.screenAt(QCursor.pos())
        if not screen:
            screen = QGuiApplication.primaryScreen()
        
        if screen:
            # 2. Use the full screen geometry (ignoring taskbars for true center)
            # This matches how the successful Tkinter version calculates its offset
            screen_geom = screen.geometry()
            
            # 3. Calculate top-left x,y using exactly the same logic as Tkinter
            # x = monitor_offset + (monitor_width - window_width) // 2
            x = screen_geom.x() + (screen_geom.width() - 650) // 2
            # y = monitor_offset + (monitor_height - window_height) // 2
            y = screen_geom.y() + (screen_geom.height() - 650) // 2
            
            # 4. Set geometry and move, ensuring fixed size is respected
            # setGeometry(x, y, w, h) is the most authoritative way to place a window in Qt
            self.setGeometry(x, y, 650, 650)
            self.setFixedSize(650, 650)
            # Re-confirm move in case setGeometry was partially ignored
            self.move(x, y)
    
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
                # For layouts, we need a recursive or more careful cleanup
                pass
        
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
        
        # Recenter window as size might have changed
        self._recenter()

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