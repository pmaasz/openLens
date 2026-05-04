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
from src.gui.widgets import (LensEditorWidget, LensVisualizationWidget, 
                             SimulationVisualizationWidget, AssemblyVisualizationWidget,
                             PerformanceVisualizationWidget, _2DVisualizationWidget)
from src.gui.tabs import (EditorTab, SimulationTab, PerformanceTab, 
                          AssemblyTab, OptimizationTab, TolerancingTab)
from src.gui.dialogs import StartupDialog, AnalysisPlotDialog
from src.services import LensService


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
            self._optical_system = data
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
        
        # Initialize tolerance operands list
        self._tol_operands = []
        
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
        self._lens_editor.lens_modified.connect(self._on_lens_modified)
        self._editor_tabs.addTab(self._lens_editor, "Lens Editor")
        
        # Assembly Editor tab (initially hidden - only shown when editing assembly)
        self._assembly_tab_widget = AssemblyTab(self)
        self._assembly_tab_index = self._editor_tabs.addTab(self._assembly_tab_widget, "Assembly Editor")
        self._editor_tabs.setTabVisible(self._assembly_tab_index, False)
        
        # Other tabs
        self._sim_tab = SimulationTab(self)
        self._editor_tabs.addTab(self._sim_tab, "Simulation")
        
        self._perf_tab = PerformanceTab(self)
        self._editor_tabs.addTab(self._perf_tab, "Performance")
        
        self._opt_tab = OptimizationTab(self)
        self._editor_tabs.addTab(self._opt_tab, "Optimization")
        
        self._tol_tab = TolerancingTab(self)
        self._editor_tabs.addTab(self._tol_tab, "Tolerancing")
        
        return self._editor_tabs
    
    def _on_lens_modified(self, lens):
        """Handle lens modification from editor widget"""
        self._update_lens_list()
        self._save_to_database()
        self._update_all_tabs()
        self._update_status(f"Updated: {lens.name}")

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
        
        if hasattr(self, '_sim_tab'):
            self._sim_tab.refresh()
        
        if hasattr(self, '_opt_tab'):
            self._opt_tab.refresh()
            
        if hasattr(self, '_tol_tab'):
            self._tol_tab.refresh()
            
        if hasattr(self, '_perf_tab'):
            self._perf_tab.refresh()
            
        if hasattr(self, '_assembly_tab_widget'):
            self._assembly_tab_widget.refresh()

    
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
        self._update_all_tabs()
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
        

    def _on_export_stl(self):
        """Export current lens or assembly to STL"""
        target = self._current_assembly if self._current_assembly else self._current_lens
        if not target:
            return
            
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Export to STL", f"{target.name}.stl", 
            "STL Files (*.stl);;All Files (*)"
        )
        
        if not filepath:
            return
            
        try:
            from src.stl_export import STLExporter
            from src.optical_system import OpticalSystem
            
            if isinstance(target, Lens):
                system = OpticalSystem(name=target.name)
                system.add_lens(target)
            else:
                system = target
                
            exporter = STLExporter(system)
            exporter.export(filepath)
            self._update_status(f"Exported to STL: {os.path.basename(filepath)}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export STL: {e}")

    def _on_export_step(self):
        """Export current lens or assembly to STEP"""
        target = self._current_assembly if self._current_assembly else self._current_lens
        if not target:
            return
            
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Export to STEP", f"{target.name}.step", 
            "STEP Files (*.step);;All Files (*)"
        )
        
        if not filepath:
            return
            
        try:
            from src.io.step_export import STEPExporter
            from src.optical_system import OpticalSystem
            
            if isinstance(target, Lens):
                system = OpticalSystem(name=target.name)
                system.add_lens(target)
            else:
                system = target
                
            exporter = STEPExporter(system)
            exporter.export(filepath)
            self._update_status(f"Exported to STEP: {os.path.basename(filepath)}")
        except ImportError:
            QMessageBox.warning(self, "Export Error", "STEP export requires additional dependencies (e.g. pythonocc-core).")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export STEP: {e}")

    def _on_export_iso10110(self):
        """Export ISO 10110 drawing as SVG"""
        target = self._current_assembly if self._current_assembly else self._current_lens
        if not target:
            return
            
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Export ISO 10110 Drawing", f"{target.name}_drawing.svg", 
            "SVG Files (*.svg);;All Files (*)"
        )
        
        if not filepath:
            return
            
        try:
            from src.io.export import ISO10110Generator
            from src.optical_system import OpticalSystem
            
            if isinstance(target, Lens):
                system = OpticalSystem(name=target.name)
                system.add_lens(target)
            else:
                system = target
                
            generator = ISO10110Generator(system)
            generator.generate_svg(filepath)
            self._update_status(f"Exported drawing to: {os.path.basename(filepath)}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export drawing: {e}")

    def _on_export_report(self):
        """Export comprehensive design report"""
        target = self._current_assembly if self._current_assembly else self._current_lens
        if not target:
            return
            
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Export Report", f"{target.name}_report.txt", 
            "Text Files (*.txt);;All Files (*)"
        )
        
        if not filepath:
            return
            
        try:
            with open(filepath, 'w') as f:
                f.write(f"OpenLens Design Report\n")
                f.write(f"======================\n\n")
                f.write(f"Name: {target.name}\n")
                f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                
                if isinstance(target, Lens):
                    f.write("Type: Single Lens Element\n")
                    f.write(f"Radius 1: {target.radius_of_curvature_1} mm\n")
                    f.write(f"Radius 2: {target.radius_of_curvature_2} mm\n")
                    f.write(f"Thickness: {target.thickness} mm\n")
                    f.write(f"Diameter: {target.diameter} mm\n")
                    f.write(f"Material: {target.material} (n={target.refractive_index})\n")
                else:
                    f.write(f"Type: Optical Assembly ({len(target.elements)} elements)\n")
                    for i, elem in enumerate(target.elements):
                        f.write(f"\nElement {i+1}: {elem.lens.name}\n")
                        f.write(f"  Position: {elem.position} mm\n")
                        f.write(f"  Thickness: {elem.lens.thickness} mm\n")
                        f.write(f"  Material: {elem.lens.material}\n")
            
            self._update_status(f"Report exported to: {os.path.basename(filepath)}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export report: {e}")

    def _on_show_ghost_analysis(self):
        """Show Ghost Reflection Analysis"""
        target = self._current_assembly if self._current_assembly else self._current_lens
        if not target:
            return
            
        try:
            from src.analysis.ghost import GhostAnalyzer
            from src.optical_system import OpticalSystem
            from src.gui.dialogs import AnalysisPlotDialog
            
            if isinstance(target, Lens):
                system = OpticalSystem(name=target.name)
                system.add_lens(target)
            else:
                system = target
                
            analyzer = GhostAnalyzer(system)
            ghosts = analyzer.trace_ghosts(num_rays=5)
            
            dialog = AnalysisPlotDialog("Ghost Analysis", self)
            ax = dialog.get_axes()
            
            # Plot main system
            # Use the existing visualization logic by providing the axis
            target_system = system
            
            # Draw lenses
            import math
            def get_sag(r, y):
                if abs(r) < 1e-6: return 0
                r_a = abs(r)
                if y > r_a: return r_a
                sag = r_a - (r_a**2 - y**2)**0.5
                return sag if r > 0 else -sag

            current_z = 0
            for i, element in enumerate(target_system.elements):
                lens = element.lens
                r1 = lens.radius_of_curvature_1
                r2 = lens.radius_of_curvature_2
                t = lens.thickness
                d = lens.diameter
                half_d = d / 2

                # Surface 1
                y = [y_val / 10.0 for y_val in range(int(-half_d*10), int(half_d*10)+1)]
                z1 = [current_z + get_sag(r1, y_val) for y_val in y]
                
                # Surface 2
                z2 = [current_z + t + get_sag(r2, y_val) for y_val in y]
                
                # Plot surfaces
                ax.plot(z1, y, 'b-', alpha=0.5)
                ax.plot(z2, y, 'b-', alpha=0.5)
                # Plot edges
                ax.plot([z1[0], z2[0]], [y[0], y[0]], 'b-', alpha=0.5)
                ax.plot([z1[-1], z2[-1]], [y[-1], y[-1]], 'b-', alpha=0.5)
                
                if i < len(target_system.air_gaps):
                    current_z += t + target_system.air_gaps[i].thickness
                else:
                    current_z += t

            ax.set_title(f"Ghost Reflection Analysis: {len(ghosts)} paths found")
            
            for ghost in ghosts:
                for ray in ghost.rays:
                    # ray.path is a list of Vector3? 
                    # Assuming we can access points
                    if hasattr(ray, 'path') and ray.path:
                        zs = [p.x for p in ray.path]
                        ys = [p.y for p in ray.path]
                        ax.plot(zs, ys, 'r--', alpha=0.3)
            
            ax.set_xlabel("Z (mm)")
            ax.set_ylabel("Y (mm)")
            ax.grid(True, alpha=0.2)
            dialog.exec()
            
        except Exception as e:
            QMessageBox.critical(self, "Analysis Error", f"Failed to perform ghost analysis: {e}")

    def _on_show_psf(self):
        """Show Point Spread Function analysis"""
        target = self._current_assembly if self._current_assembly else self._current_lens
        if not target:
            return
            
        try:
            from src.analysis.psf_mtf import ImageQualityAnalyzer
            from src.optical_system import OpticalSystem
            from src.gui.dialogs import AnalysisPlotDialog
            import numpy as np
            
            if isinstance(target, Lens):
                system = OpticalSystem(name=target.name)
                system.add_lens(target)
            else:
                system = target
                
            analyzer = ImageQualityAnalyzer(system)
            psf_data = analyzer.calculate_psf(pixels=64)
            
            dialog = AnalysisPlotDialog("PSF Analysis", self)
            ax = dialog.get_axes()
            
            # Apply dark theme to axes if needed
            if getattr(self, '_theme', 'dark') == 'dark':
                ax.set_facecolor('#1e1e1e')
                ax.tick_params(colors='#e0e0e0')
                ax.xaxis.label.set_color('#e0e0e0')
                ax.yaxis.label.set_color('#e0e0e0')
                ax.title.set_color('#e0e0e0')
                for spine in ax.spines.values():
                    spine.set_edgecolor('#3f3f3f')

            img = psf_data['image']
            extent = [
                psf_data['z_axis'][0], psf_data['z_axis'][-1],
                psf_data['y_axis'][0], psf_data['y_axis'][-1]
            ]
            
            im = ax.imshow(img, extent=extent, cmap='viridis', origin='lower')
            dialog.figure.colorbar(im, ax=ax, label="Relative Intensity")
            
            ax.set_title(f"Point Spread Function (Geometric)")
            ax.set_xlabel("Sagittal (mm)")
            ax.set_ylabel("Tangential (mm)")
            
            dialog.exec()
        except Exception as e:
            QMessageBox.critical(self, "Analysis Error", f"Failed to calculate PSF: {e}")

    def _on_show_mtf(self):
        """Show Modulation Transfer Function analysis"""
        target = self._current_assembly if self._current_assembly else self._current_lens
        if not target:
            return
            
        try:
            from src.analysis.psf_mtf import ImageQualityAnalyzer
            from src.optical_system import OpticalSystem
            from src.gui.dialogs import AnalysisPlotDialog
            
            if isinstance(target, Lens):
                system = OpticalSystem(name=target.name)
                system.add_lens(target)
            else:
                system = target
                
            analyzer = ImageQualityAnalyzer(system)
            mtf_data = analyzer.calculate_mtf(max_freq=100)
            
            dialog = AnalysisPlotDialog("MTF Analysis", self)
            ax = dialog.get_axes()
            
            ax.plot(mtf_data['freq'], mtf_data['mtf_tan'], 'r-', label="Tangential")
            ax.plot(mtf_data['freq'], mtf_data['mtf_sag'], 'b--', label="Sagittal")
            
            ax.set_ylim(0, 1.05)
            ax.set_title("Modulation Transfer Function")
            ax.set_xlabel("Spatial Frequency (lp/mm)")
            ax.set_ylabel("Modulation")
            ax.legend()
            ax.grid(True, alpha=0.3)
            
            dialog.exec()
        except Exception as e:
            QMessageBox.critical(self, "Analysis Error", f"Failed to calculate MTF: {e}")

    def _on_show_wavefront(self):
        """Show Wavefront Error analysis"""
        target = self._current_assembly if self._current_assembly else self._current_lens
        if not target:
            return
            
        try:
            from src.analysis.diffraction_psf import WavefrontSensor
            from src.optical_system import OpticalSystem
            from src.gui.dialogs import AnalysisPlotDialog
            import numpy as np
            
            if isinstance(target, Lens):
                system = OpticalSystem(name=target.name)
                system.add_lens(target)
            else:
                system = target
                
            sensor = WavefrontSensor(system)
            wf = sensor.get_pupil_wavefront(grid_size=64)
            
            dialog = AnalysisPlotDialog("Wavefront Analysis", self)
            ax = dialog.get_axes()
            
            # wf.W is 2D array of wavefront error in waves
            im = ax.imshow(wf.W, cmap='RdBu', origin='lower')
            dialog.figure.colorbar(im, ax=ax, label="Wavefront Error (λ)")
            
            ax.set_title("Exit Pupil Wavefront Error")
            ax.set_xlabel("X Pupil")
            ax.set_ylabel("Y Pupil")
            
            dialog.exec()
        except Exception as e:
            QMessageBox.critical(self, "Analysis Error", f"Failed to analyze wavefront: {e}")

    def _refresh_lens_menu(self):
        pass

    def _on_optimization_finished(self, result, logs):
        pass

    def _on_optimization_failed(self, error):
        pass

    def _load_default_lens(self):
        from src.lens import Lens
        lens = Lens(name="Default Lens")
        self._lenses.append(lens)
        self._current_lens = lens
        self._current_assembly = None
        if hasattr(self, '_lens_editor'):
            self._lens_editor.load_lens(lens)
        self._update_all_tabs()

    def _switch_to_lens(self, index):
        if 0 <= index < len(self._lenses):
            self._set_current_item(self._lenses[index], is_assembly=False)
        elif len(self._lenses) <= index < len(self._lenses) + len(self._assemblies):
            self._set_current_item(self._assemblies[index - len(self._lenses)], is_assembly=True)


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

