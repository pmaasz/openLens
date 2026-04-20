"""
OpenLens PySide6 Main Window
Main window for lens editing application
"""

from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, 
                           QLabel, QStatusBar, QMenuBar, QMenu, QScrollArea)
from PySide6.QtCore import Qt, Slot, Signal
from PySide6.QtGui import QKeySequence

from .widgets import LensEditorWidget
from .dialogs import StartupDialog


class OpenLensWindow(QMainWindow):
    """Main application window"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("OpenLens")
        self.setMinimumSize(1200, 800)
        
        # Central widget and layout
        self._central = QWidget()
        self.setCentralWidget(self._central)
        self._main_layout = QVBoxLayout(self._central)
        
        # Status bar
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        
        # Current lens data
        self._current_lens = None
        self._current_assembly = None
        self._lens_list = []
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup main UI"""
        # Menu bar
        self._menu_bar = self.menuBar()
        self._create_menus()
        
        # Tab widget for different functions
        self._tabs = QTabWidget()
        self._tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #3f3f3f;
                background-color: #1e1e1e;
            }
            QTabBar::tab {
                background-color: #2d2d2d;
                color: #aaa;
                padding: 8px 16px;
                border: 1px solid #3f3f3f;
            }
            QTabBar::tab:selected {
                background-color: #1e1e1e;
                color: #fff;
            }
        """)
        
        self._main_layout.addWidget(self._tabs)
        
        # Try to use extracted widget, fallback to placeholder
        try:
            self._editor_tab = LensEditorWidget(self)
        except Exception as e:
            print(f"Using placeholder editor: {e}")
            self._editor_tab = self._create_editor_placeholder()
        
        self._tabs.addTab(self._editor_tab, "Lens Editor")
        
        # Assembly tab
        self._assembly_tab = QWidget()
        self._tabs.addTab(self._assembly_tab, "Assembly Editor")
        
        # Sim tab placeholder  
        self._sim_tab = QWidget()
        self._tabs.addTab(self._sim_tab, "Simulation")
        
        self._perf_tab = QWidget()
        self._tabs.addTab(self._perf_tab, "Performance")
        
        self._opt_tab = QWidget()
        self._tabs.addTab(self._opt_tab, "Optimization")
        
        self._tol_tab = QWidget()
        self._tabs.addTab(self._tol_tab, "Tolerancing")
        
        # Export tab
        self._export_tab = QWidget()
        self._tabs.addTab(self._export_tab, "Export")
    
    def _create_editor_placeholder(self):
        """Fallback editor widget if import fails"""
        from PySide6.QtWidgets import QLabel
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        
        label = QLabel("Lens Editor\n\nUse openlens.py for full editor functionality")
        label.setStyleSheet("color: #888; padding: 50px; font-size: 16px;")
        scroll.setWidget(label)
        return scroll
    
    def _create_menus(self):
        """Create menu bar"""
        # File menu
        file_menu = self._menu_bar.addMenu("File")
        
        new_action = file_menu.addAction("New Lens")
        new_action.setShortcut(QKeySequence("Ctrl+N"))
        
        open_action = file_menu.addAction("Open...")
        open_action.setShortcut(QKeySequence("Ctrl+O"))
        
        save_action = file_menu.addAction("Save")
        save_action.setShortcut(QKeySequence("Ctrl+S"))
        
        file_menu.addSeparator()
        
        exit_action = file_menu.addAction("Exit")
        exit_action.setShortcut(QKeySequence("Ctrl+Q"))
        
        # View menu
        view_menu = self._menu_bar.addMenu("View")
        
        # Help menu
        help_menu = self._menu_bar.addMenu("Help")
    
    @Slot(str)
    def _update_status(self, message):
        """Update status bar"""
        self._status_bar.showMessage(message)
    
    def show_startup(self):
        """Show startup dialog"""
        dialog = StartupDialog()
        if dialog.exec():
            action = dialog._selected_action
            data = dialog._selected_data
            # Handle the action
            if action == "new_lens":
                self._create_new_lens()
            elif action == "new_assembly":
                self._create_new_assembly()
            elif data:
                self._load_lens_data(data)
    
    def _create_new_lens(self):
        """Create a new lens"""
        from src.lens import Lens
        self._current_lens = Lens(name="New Lens")
        self._update_status("Created new lens")
    
    def _create_new_assembly(self):
        """Create a new assembly"""
        self._update_status("Created new assembly")
    
    def _load_lens_data(self, data):
        """Load lens from data"""
        self._update_status(f"Loaded: {data.get('name')}")
    
    def load_lens(self, lens):
        """Load a lens into the editor"""
        self._current_lens = lens
        self._update_status(f"Loaded: {lens.name}")