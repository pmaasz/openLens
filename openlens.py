#!/usr/bin/env python3
"""
OpenLens - Optical Lens Design Application
PySide6-based modern GUI
"""

import sys
import os
import json
import logging
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                               QLabel, QTabWidget, QStatusBar, QFileDialog, QMessageBox)
from PySide6.QtCore import QTimer
from PySide6.QtGui import QKeySequence

from src.lens import Lens
from src.optical_system import OpticalSystem
from src.database import LensInUseError
from src.gui.storage import LensStorage
from src.gui.widgets import LensEditorWidget
from src.gui.tabs import (SimulationTab, PerformanceTab,
                          AssemblyTab, OptimizationTab, TolerancingTab)
from src.gui.dialogs import StartupDialog, AnalysisPlotDialog
from src.gui.theme import (
    DARK, LIGHT, get_app_stylesheet, get_menubar_qss,
    get_status_bar_qss, get_tab_widget_qss,
)
from src.stl_export import STLExporter
from src.io.step_export import StepExporter
from src.io.export import ISO10110Generator
from src.analysis.ghost import GhostAnalyzer
from src.analysis.psf_mtf import ImageQualityAnalyzer
from src.analysis.diffraction_psf import WavefrontSensor
from src.analysis.plots import (
    apply_dark_axis_theme, plot_ghost_analysis,
    plot_mtf, plot_psf, plot_wavefront,
)


class OpenLensWindow(QMainWindow):
    """Main application window.

    Owns the lens/assembly library (``_lenses`` / ``_assemblies``), the
    tabbed editor area, and SQLite persistence. Tabs are refreshed via
    :meth:`_update_all_tabs` whenever the active model changes.
    """
    
    def __init__(
            self,
            action: Optional[str] = None,
            data: Optional[Any] = None) -> None:
        """Create the main window and load its state.

        Args:
            action: Startup action selected in the startup dialog. One of
                "create_lens", "create_assembly", "open_lens",
                "open_assembly", or None for the default lens.
            data: Model instance associated with an "open_*" action
                (a Lens or OpticalSystem); ignored for "create_*" actions.
        """
        super().__init__()
        
        self._action = action
        self._data = data
        self._theme = 'dark'
        
        self.setWindowTitle("OpenLens - Optical Lens Design")
        self.setMinimumSize(1000, 700)
        
        # Initialize database
        self._db_path = "openlens.db"
        self._storage = LensStorage(self._db_path)
        self._lenses = []
        self._assemblies = []
        self._current_lens = None
        self._current_assembly = None
        
        self._setup_ui()
        self._create_menu()
        
        # Defer database loading to keep startup responsive
        QTimer.singleShot(0, self._load_from_database)
        
        self._handle_startup(action, data)
    
    def _load_from_database(self) -> None:
        """Load lenses and assemblies from SQLite database"""
        
        self._update_status("Loading library...")
        try:
            all_items = self._storage.load_lenses()
            
            self._lenses = []
            self._assemblies = []
            
            for item in all_items:
                if hasattr(item, 'elements') and hasattr(item, 'air_gaps'):
                    self._assemblies.append(item)
                else:
                    self._lenses.append(item)
            
            logger.info("Loaded %d lenses and %d assemblies from database",
                        len(self._lenses), len(self._assemblies))
            self._update_status(f"Loaded library: {len(self._lenses)} lenses, {len(self._assemblies)} assemblies")
            
            # Update tabs that depend on the loaded library
            self._update_all_tabs()
            
        except Exception as e:
            logger.error("Failed to load from database: %s", e)
            self._lenses = []
            self._assemblies = []
            self._current_lens = None
            self._current_assembly = None
    
    def _save_to_database(self) -> None:
        """Save all lenses and assemblies to SQLite database"""
        
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

            all_items = self._lenses + self._assemblies
            
            # Make sure we have the latest state of all items
            all_items = []
            
            self._storage.save_lenses(list(unique_items.values()),
                                   reconcile=True)
            logger.info("Saved %d unique items to database", len(unique_items))
        except Exception as e:
            logger.error("Failed to save to database: %s", e)
    
    def _handle_startup(self, action: Optional[str], data: Optional[Any]) -> None:
        """Handle startup action"""
        if action == "create_lens":
            self._on_new_lens()
            self._update_status("New lens created")
        elif action == "create_assembly":
            self._on_new_assembly()
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
    
    def _update_status(self, message: str) -> None:
        """Update status bar message"""
        if hasattr(self, '_status_label'):
            self._status_label.setText(message)
        if hasattr(self, '_status_bar'):
            self._status_bar.showMessage(message)
    
    def _load_lens_from_data(self, data: Any) -> None:
        """Load lens or assembly from saved data"""
        from src.optical_system import OpticalSystem

        # Check if the item already exists in the library by ID
        existing = None
        if hasattr(data, 'id'):
            for item in self._lenses + self._assemblies:
                if getattr(item, 'id', None) == data.id:
                    existing = item
                    break

        if isinstance(data, OpticalSystem):
            if not existing:
                self._assemblies.append(data)
                target = data
            else:
                target = existing
            self._current_assembly = target
            self._current_lens = None
            self._show_assembly_editor(True)
            self._show_lens_editor(False)
            self._optical_system = target
        elif isinstance(data, Lens):
            if not existing:
                self._lenses.append(data)
                target = data
            else:
                target = existing
            self._current_lens = target
            self._current_assembly = None
            self._show_assembly_editor(False)
            self._show_lens_editor(True)
        elif isinstance(data, dict):
            # Fallback for dict data
            data_id = data.get('id')
            for item in self._lenses + self._assemblies:
                if getattr(item, 'id', None) == data_id:
                    existing = item
                    break
            
            if data.get('type') == 'OpticalSystem':
                if not existing:
                    system = OpticalSystem.from_dict(data)
                    self._assemblies.append(system)
                    target = system
                else:
                    target = existing
                self._current_assembly = target
                self._current_lens = None
            else:
                if not existing:
                    lens = Lens.from_dict(data)
                    self._lenses.append(lens)
                    target = lens
                else:
                    target = existing
                self._current_lens = target
                self._current_assembly = None
        else:
            self._load_default_lens()
            return
        
        if self._current_lens:
            self._lens_editor.load_lens(self._current_lens)
        
        self._update_all_tabs()
    
    def _setup_ui(self) -> None:
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
        self._status_bar.setStyleSheet(get_status_bar_qss(self._theme))
        self._status_label = QLabel("Ready")
        self._status_bar.addWidget(self._status_label)
        self.setStatusBar(self._status_bar)
        
        # Initialize tolerance operands list
        self._tol_operands = []
        
        self._update_status("Welcome to OpenLens")

    
    def _create_editor_area(self) -> QTabWidget:
        """Create the main editor area with tabs"""
        self._editor_tabs = QTabWidget()
        self._editor_tabs.setStyleSheet(get_tab_widget_qss(self._theme))
        
        # Lens Editor tab (always visible)
        self._lens_editor = LensEditorWidget(self)
        self._lens_editor.lens_modified.connect(self._on_lens_modified)
        self._editor_tabs.addTab(self._lens_editor, "Lens Editor")
        
        # Assembly Editor tab (initially hidden - only shown when editing assembly)
        self._assembly_tab_widget = AssemblyTab(self)
        self._assembly_tab_widget.data_updated.connect(self._on_assembly_modified)
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
    
    def _on_lens_modified(self, lens: Lens) -> None:
        """Handle lens modification from editor widget"""
        self._save_to_database()
        self._update_all_tabs()
        self._update_status(f"Updated: {lens.name}")

    def _on_assembly_modified(self) -> None:
        """Handle assembly modification from assembly tab"""
        # Ensure we are saving the actual modified system
        modified_system = self._assembly_tab_widget._optical_system
        self._current_assembly = modified_system
        
        # Update the reference in self._assemblies to the new state
        for i, asm in enumerate(self._assemblies):
            if asm.id == modified_system.id:
                self._assemblies[i] = modified_system
                break
                
        self._save_to_database()
        self._update_all_tabs()
        self._update_status(f"Assembly updated: {self._current_assembly.name if self._current_assembly else 'Unknown'}")

    def _show_assembly_editor(self, show: bool = True) -> None:
        """Show/hide assembly editor tab"""
        if hasattr(self, '_assembly_tab_index'):
            self._editor_tabs.setTabVisible(self._assembly_tab_index, show)
    
    def _show_lens_editor(self, show: bool = True) -> None:
        """Show lens editor tab"""
        self._editor_tabs.setTabVisible(0, show)
    
    def _create_menu(self) -> None:
        """Create menu bar"""
        menubar = self.menuBar()
        menubar.setStyleSheet(get_menubar_qss(self._theme))
        
        # File menu
        file_menu = menubar.addMenu("File")
        file_menu.addAction("New Lens", self._on_new_lens, QKeySequence.New)
        file_menu.addAction("Open...", self._on_open, QKeySequence.Open)
        file_menu.addAction("Save", self._on_save, QKeySequence("Ctrl+S"))
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
        edit_menu.addAction("Delete Lens", self._on_delete_lens, QKeySequence("Delete"))
        edit_menu.addSeparator()
        edit_menu.addAction("Duplicate Lens", self._on_duplicate_lens, QKeySequence("Ctrl+D"))
        
        # Preferences menu
        prefs_menu = menubar.addMenu("Preferences")
        prefs_menu.addAction("Toggle Dark/Light Theme", self._on_toggle_theme, QKeySequence("Ctrl+T"))
        
        # Lens menu (quick switch). Rebuilt every time it opens so it
        # reflects the deferred database load and any library changes.
        self._lens_menu = menubar.addMenu("Lens")
        self._lens_menu.aboutToShow.connect(self._rebuild_lens_menu)

# View menu
        view_menu = menubar.addMenu("View")
        view_menu_2d = view_menu.addMenu("2D View")
        view_menu_2d.addAction("Top", lambda: self._set_viz_mode("2D"))
        view_menu_2d.addAction("Side", lambda: self._set_viz_mode("side"))
        
        view_menu.addSeparator()
        view_menu.addAction("Reset Window", self._on_reset_window, QKeySequence("Ctrl+0"))
        
        # Help menu
        help_menu = menubar.addMenu("Help")
        help_menu.addAction("About", self._on_about)
        help_menu.addAction("Keyboard Shortcuts", self._on_show_shortcuts)
    
    def _set_current_item(self, item: Any, is_assembly: bool = False) -> None:
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
    
    def _load_assembly(self, assembly: OpticalSystem) -> None:
        """Load assembly into assembly editor"""
        if hasattr(self, '_optical_system'):
            self._optical_system = assembly
        if hasattr(self, '_assembly_viz'):
            self._assembly_viz.update_system(assembly)
        if hasattr(self, '_system_list'):
            self._update_system_list()
    
    def _update_all_tabs(self) -> None:
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

    
    def _on_new_lens(self) -> None:
        """Create new lens"""
        lens = Lens(name=f"Lens {len(self._lenses) + 1}")
        self._lenses.append(lens)
        self._current_lens = lens
        self._current_assembly = None
        self._editor_tabs.setCurrentIndex(0)  # Go to Lens Editor
        self._lens_editor.load_lens(lens)
        self._update_all_tabs()
        self._update_status(f"Created: {lens.name}")
    
    def _on_new_assembly(self) -> None:
        """Create new assembly"""
        asm = OpticalSystem(name=f"Assembly {len(self._assemblies) + 1}")
        self._assemblies.append(asm)
        self._current_assembly = asm
        self._current_lens = None
        self._optical_system = asm
        self._show_assembly_editor(True)
        self._editor_tabs.setCurrentIndex(1)
        self._update_all_tabs()
        self._update_status(f"Created: {asm.name}")
    
    def _notify_delete_blocked(self, error: LensInUseError) -> None:
        """Tell the user a lens cannot be deleted while assemblies use it."""
        logger.error("Deletion refused: %s", error)
        QMessageBox.warning(
            self, "Lens is in use",
            "This lens is still used by the following assemblies:\n\n"
            + "\n".join(f"  • {name}" for _, name in error.assemblies)
            + "\n\nRemove it from those assemblies first.")

    def _on_delete_lens(self) -> None:
        """Delete the current lens or assembly (memory and database).

        Raises nothing to the user on refusal: LensInUseError surfaces as
        a warning dialog and leaves both memory and database untouched.
        """
        item = self._current_lens if self._current_lens else self._current_assembly
        if not item:
            return

        # Refusals that must not touch memory or database:
        if self._current_lens and len(self._lenses) <= 1:
            self._update_status("Cannot delete the last lens")
            return

        # Persist the removal first; abort on refusal without touching memory.
        try:
            self._storage.delete_item(item.id)
        except LensInUseError as e:
            self._notify_delete_blocked(e)
            return
        except Exception as e:
            logger.error("Database delete failed for %s: %s", item.id, e)
            QMessageBox.critical(self, "Delete failed",
                                 f"Could not delete '{item.name}': {e}")
            return

        if self._current_lens:
            idx = self._lenses.index(self._current_lens)
            self._lenses.pop(idx)
            self._current_lens = self._lenses[0]
            self._current_assembly = None
            self._lens_editor.load_lens(self._current_lens)
            self._update_all_tabs()
            self._update_status(f"Deleted. Now editing: {self._current_lens.name}")
        else:
            idx = self._assemblies.index(self._current_assembly)
            self._assemblies.pop(idx)
            self._current_assembly = self._assemblies[0] if self._assemblies else None
            self._update_status("Deleted assembly")
    
    def _on_open(self) -> None:
        """Open from database - just reload"""
        self._load_from_database()
        if self._current_lens:
            self._lens_editor.load_lens(self._current_lens)
        self._update_status("Reloaded from database")
    
    def _on_save(self) -> None:
        """Save to database"""
        if self._editor_tabs.currentIndex() == 0:  # Lens Editor Tab
            # Sync data from Lens Editor widget back to the lens object
            self._lens_editor._on_property_changed()
            # If we are editing an existing lens, ensure it's in the list
            if self._current_lens and self._current_lens not in self._lenses:
                # Check for existing lens by ID
                found = False
                for i, lens in enumerate(self._lenses):
                    if lens.id == self._current_lens.id:
                        self._lenses[i] = self._current_lens
                        found = True
                        break
                if not found:
                    self._lenses.append(self._current_lens)
        elif self._editor_tabs.currentIndex() == self._assembly_tab_index:
             # Force sync from assembly tab state before saving
             self._current_assembly = self._assembly_tab_widget._optical_system
             # Ensure it's in the list
             if self._current_assembly and self._current_assembly not in self._assemblies:
                found = False
                for i, asm in enumerate(self._assemblies):
                    if asm.id == self._current_assembly.id:
                        self._assemblies[i] = self._current_assembly
                        found = True
                        break
                if not found:
                    self._assemblies.append(self._current_assembly)
                    
        self._save_to_database()
        self._update_status("Saved to database")
    
    def _on_save_as(self) -> None:
        """Save lens with new filename"""
        if not self._current_lens:
            return
        
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Save Lens As", f"{self._current_lens.name}.json", 
            "JSON Files (*.json);;All Files (*)"
        )
        
        if not filepath:
            return
        
        try:
            data = self._current_lens.to_dict()
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            logger.error("Failed to save file: %s", e)
            QMessageBox.critical(self, "Error", f"Failed to save file: {e}")
    
    def _on_about(self) -> None:
        """Show about dialog"""
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
    
    def _on_show_shortcuts(self) -> None:
        """Show keyboard shortcuts"""
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
    
    def _on_duplicate_lens(self) -> None:
        """Duplicate current lens"""
        if not self._current_lens:
            return

        data = self._current_lens.to_dict()
        # Pop identity so the constructor mints a fresh uuid4 id, matching
        # LensService.duplicate_lens; keeping the id would collide with the
        # original on INSERT OR REPLACE.
        data.pop('id', None)
        data['name'] = f"{self._current_lens.name} (copy)"
        new_lens = Lens.from_dict(data)

        self._lenses.append(new_lens)
        self._current_lens = new_lens
        self._lens_editor.load_lens(new_lens)
        self._update_all_tabs()
        self._save_to_database()
        self._update_status(f"Duplicated: {new_lens.name}")
    
    def _on_toggle_theme(self) -> None:
        """Toggle between dark and light theme"""
        app = QApplication.instance()
        current = getattr(self, '_theme', 'dark')
        
        if current == 'dark':
            self._theme = 'light'
            app.setStyleSheet(get_app_stylesheet(LIGHT))
            self._update_status("Light theme")
        else:
            self._theme = 'dark'
            self.dark_theme(app)
            self._update_status("Dark theme")
    
    def dark_theme(self, app: QApplication) -> None:
        """Apply the dark application stylesheet."""
        app.setStyleSheet(get_app_stylesheet(DARK))

    
    def _on_reset_window(self) -> None:
        """Reset window to default size and position"""
        self.resize(1000, 700)
        self.move(50, 50)
        self._update_status("Window reset")
    
    def _set_viz_mode(self, mode: str) -> None:
        """Set visualization view mode"""
        if hasattr(self, '_lens_editor') and self._lens_editor:
            viz = getattr(self._lens_editor, '_viz_widget', None)
            if viz and hasattr(viz, 'set_view_mode'):
                viz.set_view_mode(mode)
        self._update_status(f"View: {mode}")
    
    def _on_export_stl(self) -> None:
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
            
            if isinstance(target, Lens):
                system = OpticalSystem(name=target.name)
                system.add_lens(target)
            else:
                system = target
                
            exporter = STLExporter(system)
            exporter.export(filepath)
            self._update_status(f"Exported to STL: {os.path.basename(filepath)}")
        except Exception as e:
            logger.error("STL export failed: %s", e)
            QMessageBox.critical(self, "Export Error", f"Failed to export STL: {e}")

    def _on_export_step(self) -> None:
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
            
            if isinstance(target, Lens):
                system = OpticalSystem(name=target.name)
                system.add_lens(target)
            else:
                system = target
                
            exporter = STEPExporter(system)
            exporter.export(filepath)
            self._update_status(f"Exported to STEP: {os.path.basename(filepath)}")
        except ImportError:
            logger.error("STEP export failed with ImportError: %s", e)
            QMessageBox.warning(self, "Export Error", "STEP export requires additional dependencies (e.g. pythonocc-core).")
        except Exception as e:
            logger.error("STEP export failed: %s", e)
            QMessageBox.critical(self, "Export Error", f"Failed to export STEP: {e}")

    def _on_export_iso10110(self) -> None:
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
            
            if isinstance(target, Lens):
                system = OpticalSystem(name=target.name)
                system.add_lens(target)
            else:
                system = target
                
            generator = ISO10110Generator(system)
            generator.generate_svg(filepath)
            self._update_status(f"Exported drawing to: {os.path.basename(filepath)}")
        except Exception as e:
            logger.error("ISO 10110 export failed: %s", e)
            QMessageBox.critical(self, "Export Error", f"Failed to export drawing: {e}")

    def _on_export_report(self) -> None:
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
            logger.error("Report export failed: %s", e)
            QMessageBox.critical(self, "Export Error", f"Failed to export report: {e}")

    def _on_show_ghost_analysis(self) -> None:
        """Show Ghost Reflection Analysis"""
        target = self._current_assembly if self._current_assembly else self._current_lens
        if not target:
            return

        try:
            if isinstance(target, Lens):
                system = OpticalSystem(name=target.name)
                system.add_lens(target)
            else:
                system = target

            analyzer = GhostAnalyzer(system)
            ghosts = analyzer.trace_ghosts(num_rays=5)

            dialog = AnalysisPlotDialog("Ghost Analysis", self)
            ax = dialog.get_axes()
            plot_ghost_analysis(ax, system, ghosts)
            dialog.exec()
            
        except Exception as e:
            logger.error("Ghost analysis failed: %s", e)
            QMessageBox.critical(self, "Analysis Error", f"Failed to perform ghost analysis: {e}")

    def _on_show_psf(self) -> None:
        """Show Point Spread Function analysis"""
        target = self._current_assembly if self._current_assembly else self._current_lens
        if not target:
            return

        try:
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
                apply_dark_axis_theme(ax)

            plot_psf(ax, psf_data)
            dialog.exec()
        except Exception as e:
            logger.error("PSF calculation failed: %s", e)
            QMessageBox.critical(self, "Analysis Error", f"Failed to calculate PSF: {e}")

    def _on_show_mtf(self) -> None:
        """Show Modulation Transfer Function analysis"""
        target = self._current_assembly if self._current_assembly else self._current_lens
        if not target:
            return

        try:
            if isinstance(target, Lens):
                system = OpticalSystem(name=target.name)
                system.add_lens(target)
            else:
                system = target

            analyzer = ImageQualityAnalyzer(system)
            mtf_data = analyzer.calculate_mtf(max_freq=100)

            dialog = AnalysisPlotDialog("MTF Analysis", self)
            ax = dialog.get_axes()
            plot_mtf(ax, mtf_data)
            dialog.exec()
        except Exception as e:
            logger.error("MTF calculation failed: %s", e)
            QMessageBox.critical(self, "Analysis Error", f"Failed to calculate MTF: {e}")

    def _on_show_wavefront(self) -> None:
        """Show Wavefront Error analysis"""
        target = self._current_assembly if self._current_assembly else self._current_lens
        if not target:
            return

        try:
            if isinstance(target, Lens):
                system = OpticalSystem(name=target.name)
                system.add_lens(target)
            else:
                system = target

            sensor = WavefrontSensor(system)
            wf = sensor.get_pupil_wavefront(grid_size=64)

            dialog = AnalysisPlotDialog("Wavefront Analysis", self)
            ax = dialog.get_axes()
            plot_wavefront(ax, wf.W)
            dialog.exec()
        except Exception as e:
            logger.error("Wavefront analysis failed: %s", e)
            QMessageBox.critical(self, "Analysis Error", f"Failed to analyze wavefront: {e}")

    def _load_default_lens(self) -> None:
        """Create a fresh default lens and make it the active editor target."""
        lens = Lens(name="Default Lens")
        self._lenses.append(lens)
        self._current_lens = lens
        self._current_assembly = None
        if hasattr(self, '_lens_editor'):
            self._lens_editor.load_lens(lens)
        self._update_all_tabs()

    def _switch_to_lens(self, index: int) -> None:
        """Select the lens or assembly at the given combined menu index.

        Args:
            index: Index into lenses followed by assemblies.
        """
        if 0 <= index < len(self._lenses):
            self._set_current_item(self._lenses[index], is_assembly=False)
        elif len(self._lenses) <= index < len(self._lenses) + len(self._assemblies):
            self._set_current_item(self._assemblies[index - len(self._lenses)], is_assembly=True)

    def _rebuild_lens_menu(self) -> None:
        """Repopulate the Lens quick-switch menu from current state.

        Connected to the menu's aboutToShow signal so entries always
        reflect the library, including items loaded by the deferred
        database load and everything created or deleted afterwards.
        """
        menu = self._lens_menu
        menu.clear()

        if not self._lenses and not self._assemblies:
            empty = menu.addAction("(library is empty)")
            empty.setEnabled(False)
            return

        lenses_header = menu.addAction("--- Lenses ---")
        lenses_header.setEnabled(False)
        for lens in self._lenses:
            action = menu.addAction(lens.name)
            action.setCheckable(True)
            action.setChecked(lens is self._current_lens)
            action.triggered.connect(
                lambda checked=False, item=lens: self._set_current_item(item))

        if self._assemblies:
            menu.addSeparator()
            asm_header = menu.addAction("--- Assemblies ---")
            asm_header.setEnabled(False)
            for asm in self._assemblies:
                action = menu.addAction(f"[{asm.name}]")
                action.setCheckable(True)
                action.setChecked(asm is self._current_assembly)
                action.triggered.connect(
                    lambda checked=False, item=asm: self._set_current_item(
                        item, is_assembly=True))


def main() -> None:
    """Run the OpenLens application: startup dialog, then the main window."""
    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    # Set dark theme
    app.setStyleSheet(get_app_stylesheet(DARK))
    
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

