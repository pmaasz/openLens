"""
OpenLens GUI Main Window Module

This module provides the main LensEditorWindow class for the OpenLens
application.
"""

import logging
import tkinter as tk
from tkinter import ttk
import os
from typing import Optional, List, Any, TYPE_CHECKING, cast, Union

if TYPE_CHECKING:
    from ..lens import Lens
    from ..optical_system import OpticalSystem
    from ..gui_controllers import (
        LensSelectionController,
        LensEditorController,
        SimulationController,
        PerformanceController,
        ExportController
    )
    from ..lens_visualizer import LensVisualizer

# Configure module logger
logger = logging.getLogger(__name__)

# Import constants
try:
    from ..constants import (
        # GUI Colors
        COLOR_BG_DARK, COLOR_FG,
        # Font settings
        FONT_FAMILY, FONT_SIZE_NORMAL, FONT_SIZE_LARGE, FONT_SIZE_TITLE,
        # Padding
        PADDING_SMALL, PADDING_XLARGE,
    )
except ImportError:
    # Fallback if constants module not found
    COLOR_BG_DARK = '#252526'
    COLOR_FG = '#e0e0e0'
    FONT_FAMILY = 'Arial'
    FONT_SIZE_NORMAL = 10
    FONT_SIZE_LARGE = 12
    FONT_SIZE_TITLE = 14
    PADDING_SMALL = 5
    PADDING_XLARGE = 20

# Import theme and storage
from .theme import ThemeManager, COLORS, setup_dark_mode
from .storage import LensStorage
from .taskbar import TaskbarMenu

# Try to import visualization (optional dependency)
try:
    from ..lens_visualizer import LensVisualizer
    VISUALIZATION_AVAILABLE = True
except ImportError:
    try:
        from lens_visualizer import LensVisualizer
        VISUALIZATION_AVAILABLE = True
    except ImportError:
        VISUALIZATION_AVAILABLE = False
        logger.info("matplotlib not available. 3D visualization disabled.")

# Try to import aberrations calculator
try:
    from ..aberrations import AberrationsCalculator
    ABERRATIONS_AVAILABLE = True
except ImportError:
    try:
        from aberrations import AberrationsCalculator
        ABERRATIONS_AVAILABLE = True
    except ImportError:
        ABERRATIONS_AVAILABLE = False
        logger.info("Aberrations calculator not available.")

# Initialize controller classes to None to avoid LSP warnings
LensSelectionController = None
LensEditorController = None
SimulationController = None
PerformanceController = None
ExportController = None
OptimizationController = None

# Try to import GUI controllers
try:
    from ..gui_controllers import (
        LensSelectionController,
        LensEditorController,
        SimulationController,
        PerformanceController,
        ExportController
    )
        # Import OptimizationController from its dedicated module (sibling)
    from .optimization_controller import OptimizationController
    from .tolerancing_controller import TolerancingController
    CONTROLLERS_AVAILABLE = True

except ImportError:
    try:
        from gui_controllers import (
            LensSelectionController,
            LensEditorController,
            SimulationController,
            PerformanceController,
            ExportController
        )
        # Try importing from local gui/optimization_controller.py
        try:
            from gui.optimization_controller import OptimizationController
            from gui.tolerancing_controller import TolerancingController
        except ImportError:
             # If running from src/ directly or finding module locally
            from optimization_controller import OptimizationController
            from tolerancing_controller import TolerancingController

        CONTROLLERS_AVAILABLE = True
    except ImportError:
        CONTROLLERS_AVAILABLE = False
        logger.info("GUI controllers not available.")

# Import Lens model
try:
    from ..lens import Lens
    from ..optical_system import OpticalSystem
except ImportError:
    try:
        from lens import Lens
        from optical_system import OpticalSystem
    except ImportError:
        logger.error("Could not import Lens model")
        # Runtime fallback
        if not TYPE_CHECKING:
            class Lens: pass
            class OpticalSystem: pass

class LensEditorWindow:
    
    def __init__(self, root: tk.Tk, initial_action: str = None, initial_item: Any = None) -> None:
        self.root = root
        self.root.title("openlens - Optical Lens Editor")
        self.root.geometry("1400x800")
        self.initial_action = initial_action
        self.initial_item = initial_item
        
        # Initialize storage
        self.storage_file = "openlens.db"
        self.storage = LensStorage(self.storage_file, self.update_status)
        self.lenses: List[Any] = self.storage.load_lenses()
        
        self.current_lens: Optional[Any] = None
        self.visualizer: Optional['LensVisualizer'] = None
        self.selected_lens_id: Optional[str] = None
        self._loading_lens: bool = False
        self._autosave_timer: Optional[str] = None
        
        # Initialize status_var early
        self.status_var = tk.StringVar(value="Welcome to openlens")
        self._status_clear_timer: Optional[Any] = None
        
        # Initialize controllers (None until UI setup)
        self.selection_controller: Optional['LensSelectionController'] = None
        self.editor_controller: Optional['LensEditorController'] = None
        self.simulation_controller: Optional['SimulationController'] = None
        self.performance_controller: Optional['PerformanceController'] = None
        self.optimization_controller: Optional['OptimizationController'] = None
        self.export_controller: Optional['ExportController'] = None
        self.tolerancing_controller: Optional['TolerancingController'] = None
        
        # Configure dark mode
        self.colors = COLORS
        self.theme_manager = setup_dark_mode(self.root, self.colors)
        
        self.setup_ui()
        
        # Bind keyboard shortcuts
        self.root.bind_all('<Control-s>', self.on_ctrl_s)
        self.root.bind_all('<Control-S>', self.on_ctrl_s)
        self.root.bind_all('<Control-l>', self._on_ctrl_l)
        self.root.bind_all('<Control-L>', self._on_ctrl_l)
        
        # Re-enable status callback for save operations after initialization
        if self.storage:
            self.storage.status_callback = self.update_status
        
    def save_lenses(self, show_status: bool = False) -> bool:
        """Save all lenses to SQLite database"""
        return self.storage.save_lenses(self.lenses, show_status=show_status)
    
    def setup_ui(self) -> None:
        # Create menu bar first
        self._create_menu_bar()
        
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=1, column=0, sticky="nsew")
        
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(0, weight=1)
        
        # Create tabbed interface
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.grid(row=0, column=0, sticky="nsew")
        self.notebook.bind('<<NotebookTabChanged>>', self.on_tab_changed)
        
        # Create Editor tab (disabled until lens selected)
        self.editor_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.editor_tab, text="Editor", state='disabled')
        
        # Create Simulation tab (disabled until lens selected)
        self.simulation_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.simulation_tab, text="Simulation", state='disabled')
        
        # Create Performance tab (disabled until lens selected)
        self.performance_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.performance_tab, text="Performance", state='disabled')

        # Create Optimization tab (disabled until lens selected)
        self.optimization_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.optimization_tab, text="Optimization", state='disabled')

        # Create Tolerancing tab (disabled until lens selected)
        self.tolerancing_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.tolerancing_tab, text="Tolerancing", state='disabled')
        
        # Create Export tab (disabled until lens selected)
        self.export_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.export_tab, text="Export", state='disabled')
        
        self.editor_tab.columnconfigure(1, weight=1)
        self.editor_tab.columnconfigure(2, weight=1)
        self.editor_tab.rowconfigure(0, weight=1)
        
        # Setup tab content
        self.setup_editor_tab()
        self.setup_simulation_tab()
        self.setup_performance_tab()
        self.setup_optimization_tab()
        self.setup_tolerancing_tab()
        self.setup_export_tab()

        # Setup taskbar-style menu for quick lens switching
        self._setup_taskbar_menu()
        
        # Handle initial action from startup window
        if self.initial_action:
            self._handle_initial_action(self.initial_action, self.initial_item)
        
        # Status bar (below tabs)
        status_frame = ttk.Frame(main_frame)
        status_frame.grid(row=1, column=0, sticky="ew", pady=PADDING_SMALL, padx=PADDING_SMALL)
        
        self.status_var = tk.StringVar(value="Select or create a lens to begin")
        status_label = ttk.Label(status_frame, textvariable=self.status_var, 
                                 relief=tk.SUNKEN, anchor=tk.W,
                                 font=('Arial', 9, 'bold'),
                                 padding=(5, 3))
        status_label.pack(fill=tk.X)
        
        # Note: Don't call update_status here - it will trigger auto-clear
        # The status_var is already set above
    
    def _handle_initial_action(self, action: str, item: Any = None) -> None:
        """Handle the initial action from startup window"""
        if action == "create_lens":
            self.on_create_new_lens()
        elif action == "create_assembly":
            self.on_create_new_system()
        elif action == "open_lens":
            self._open_lens_by_name(item)
        elif action == "open_assembly":
            self._open_assembly_by_name(item)
    
    def _open_lens_by_name(self, name: str) -> None:
        """Open a lens by name"""
        for lens in self.lenses:
            if lens.name == name:
                self.on_lens_selected_callback(lens)
                break
    
    def _open_assembly_by_name(self, name: str) -> None:
        """Open an assembly by name"""
        for lens in self.lenses:
            if hasattr(lens, 'elements') and lens.name == name:
                self.on_lens_selected_callback(lens)
                break

    def _create_menu_bar(self) -> None:
        """Create the application menu bar with File, Edit, View, Lens menus."""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0, bg=self.colors.get('bg', '#252526'),
                           fg=self.colors.get('fg', '#e0e0e0'))
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="New Lens", command=self.on_create_new_lens)
        file_menu.add_command(label="New Assembly", command=self.on_create_new_system)
        file_menu.add_separator()
        file_menu.add_command(label="Save", accelerator="Ctrl+S", command=self._menu_save)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        
        # Edit menu
        edit_menu = tk.Menu(menubar, tearoff=0, bg=self.colors.get('bg', '#252526'),
                           fg=self.colors.get('fg', '#e0e0e0'))
        menubar.add_cascade(label="Edit", menu=edit_menu)
        edit_menu.add_command(label="Undo", accelerator="Ctrl+Z")
        edit_menu.add_command(label="Redo", accelerator="Ctrl+Y")
        
        # View menu
        view_menu = tk.Menu(menubar, tearoff=0, bg=self.colors.get('bg', '#252526'),
                           fg=self.colors.get('fg', '#e0e0e0'))
        menubar.add_cascade(label="View", menu=view_menu)
        view_menu.add_command(label="Editor Tab", command=lambda: self.notebook.select(0))
        view_menu.add_command(label="Simulation Tab", command=lambda: self.notebook.select(1))
        view_menu.add_command(label="Performance Tab", command=lambda: self.notebook.select(2))
        
        # Lens menu - shows all available lenses and assemblies
        self._lens_menu = tk.Menu(menubar, tearoff=0, bg=self.colors.get('bg', '#252526'),
                                  fg=self.colors.get('fg', '#e0e0e0'))
        menubar.add_cascade(label="Lens", menu=self._lens_menu)
        self._update_lens_menu()
        
        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0, bg=self.colors.get('bg', '#252526'),
                           fg=self.colors.get('fg', '#e0e0e0'))
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About")

    def _menu_save(self) -> None:
        """Handle menu save action."""
        self.save_lenses(show_status=True)
        self.update_status("Saved")

    def _update_lens_menu(self) -> None:
        """Update the Lens menu with current lenses and assemblies."""
        if not hasattr(self, '_lens_menu'):
            return
            
        self._lens_menu.delete(0, tk.END)
        
        lenses = [l for l in self.lenses 
                  if not (hasattr(l, 'elements') and hasattr(l, 'air_gaps'))]
        assemblies = [l for l in self.lenses 
                     if hasattr(l, 'elements') and hasattr(l, 'air_gaps')]
        
        if lenses:
            self._lens_menu.add_command(label="--- Lenses ---", state='disabled')
            for lens in lenses:
                self._lens_menu.add_command(
                    label=f"  {lens.name}",
                    command=lambda n=lens.name: self._open_lens_by_name(n)
                )
        
        if assemblies:
            if lenses:
                self._lens_menu.add_separator()
            self._lens_menu.add_command(label="--- Assemblies ---", state='disabled')
            for assembly in assemblies:
                self._lens_menu.add_command(
                    label=f"  {assembly.name}",
                    command=lambda n=assembly.name: self._open_assembly_by_name(n)
                )
        
        if not lenses and not assemblies:
            self._lens_menu.add_command(label="(No lenses)", state='disabled')
        
        self._lens_menu.add_separator()
        self._lens_menu.add_command(label="Refresh", command=self._update_lens_menu)
    
    def _setup_taskbar_menu(self) -> None:
        """Setup taskbar-style menu for quick lens switching."""
        self.taskbar_menu = TaskbarMenu(self.root, self.colors)
        self.taskbar_menu.create_menu(self.root)
        
        # Update menu with current lenses
        self._refresh_taskbar_menu()

    def _refresh_taskbar_menu(self) -> None:
        """Refresh the taskbar menu with current lenses and assemblies."""
        # Separate lenses and assemblies
        lenses = [l for l in self.lenses 
                  if not (hasattr(l, 'elements') and hasattr(l, 'air_gaps'))]
        assemblies = [l for l in self.lenses 
                     if hasattr(l, 'elements') and hasattr(l, 'air_gaps')]
        
        self.taskbar_menu.update_items(
            lenses, assemblies,
            on_select_lens=self._on_taskbar_select_lens,
            on_select_assembly=self._on_taskbar_select_assembly
        )

    def _on_taskbar_select_lens(self, name: str) -> None:
        """Handle lens selection from taskbar menu."""
        for lens in self.lenses:
            if lens.name == name:
                self.on_lens_selected_callback(lens)
                break

    def _on_taskbar_select_assembly(self, name: str) -> None:
        """Handle assembly selection from taskbar menu."""
        for lens in self.lenses:
            if hasattr(lens, 'elements') and hasattr(lens, 'air_gaps') and lens.name == name:
                self.on_lens_selected_callback(lens)
                break
    
    # Controller callback methods
    def on_lens_selected_callback(self, lens: Any) -> None:
        """Callback when a lens is selected from the controller"""
        self.current_lens = lens
        
        # Check if it's an OpticalSystem (multi-lens)
        is_system = hasattr(lens, 'elements') and hasattr(lens, 'air_gaps')
        
        if is_system:
            # Multi-lens system selected
            self.notebook.tab(0, state='normal')   # Editor (Enabled for assemblies now)
            self.notebook.tab(1, state='normal')   # Simulation
            self.notebook.tab(2, state='normal')  # Performance (now enabled for assemblies)
            self.notebook.tab(3, state='normal')  # Optimization
            self.notebook.tab(4, state='normal')  # Tolerancing
            self.notebook.tab(5, state='normal')  # Export (Enabled for assemblies)
            
            # Switch to Editor tab automatically for assembly configuration
            self.notebook.select(0)
            
            # Load system into controllers
            if self.editor_controller:
                self.editor_controller.load_lens(lens)

            if self.simulation_controller:
                self.simulation_controller.load_lens(lens)
                
            if self.performance_controller:
                self.performance_controller.load_lens(lens)
                
            if self.optimization_controller:
                self.optimization_controller.load_lens(lens)

            if self.tolerancing_controller:
                self.tolerancing_controller.load_lens(lens)
                
            if self.export_controller:
                self.export_controller.load_lens(lens)
                
            self.update_status(f"Optical System selected ({len(lens.elements)} elements) - Use Editor to build system")
            
        else:
            # Single lens selected
            self.notebook.tab(0, state='normal')
            self.notebook.tab(1, state='normal')
            self.notebook.tab(2, state='normal')
            self.notebook.tab(3, state='normal')
            self.notebook.tab(4, state='normal')
            self.notebook.tab(5, state='normal')
            
            # Re-enable 3D tab for single lenses
            self.viz_notebook.tab(1, state='normal')
            
            # Switch to editor and load lens
            self.notebook.select(0)
            
            # Load lens into controllers
            if self.editor_controller:
                self.editor_controller.load_lens(lens)
                
            if self.simulation_controller:
                self.simulation_controller.load_lens(lens)
            
            if self.performance_controller:
                self.performance_controller.load_lens(lens)
            
            if self.optimization_controller:
                self.optimization_controller.load_lens(lens)
            
            if self.tolerancing_controller:
                self.tolerancing_controller.load_lens(lens)
            
            if self.export_controller:
                self.export_controller.load_lens(lens)
            
            # Update visualization
            self.on_viz_tab_changed(None)
            
            self.update_status(f"Lens selected: '{lens.name}' - Ready to edit")
    
    def on_create_new_lens(self) -> None:
        """Callback when creating a new lens"""
        self.current_lens = None
        
        # Enable tabs
        self.notebook.tab(0, state='normal')
        self.notebook.tab(1, state='normal')
        self.notebook.tab(2, state='normal')
        self.notebook.tab(3, state='normal')
        self.notebook.tab(4, state='normal')
        self.notebook.tab(5, state='normal')
        
        # Re-enable 3D tab for single lenses
        self.viz_notebook.tab(1, state='normal')
        
        # Switch to editor
        self.notebook.select(0)
        
        # Clear/Prepare editor
        if self.editor_controller:
            self.editor_controller.load_lens(None)  # Clears form
            
        self.update_status("Ready to create new lens")
    
    def on_create_new_system(self) -> None:
        """Callback when creating a new optical system"""
        # Create new OpticalSystem
        try:
            from ..optical_system import OpticalSystem
            system = OpticalSystem(name="New Assembly")
        except ImportError:
             # Try local import
            try:
                from optical_system import OpticalSystem
                system = OpticalSystem(name="New Assembly")
            except ImportError:
                # Fallback if class not available
                logger.error("OpticalSystem class not available")
                return

        # Add to list
        self.lenses.append(system)
        
        # Enable tabs
        self.notebook.tab(0, state='normal')
        self.notebook.tab(1, state='normal')
        self.notebook.tab(2, state='normal')
        self.notebook.tab(3, state='normal')
        self.notebook.tab(4, state='normal')
        self.notebook.tab(5, state='normal')
        
        # Switch to editor tab
        self.notebook.select(0)
        
        # Load system into editor to show available lenses
        if self.editor_controller:
            self.editor_controller.load_lens(system)
        
        # Also load into simulation, optimization tabs
        if self.simulation_controller:
            self.simulation_controller.load_lens(system)
        if self.optimization_controller:
            self.optimization_controller.load_lens(system)
        if self.tolerancing_controller:
            self.tolerancing_controller.load_lens(system)
        
        # Update visualization to show the system (force 2D view for assemblies)
        self.viz_notebook.select(0)  # Switch to 2D tab
        self.viz_notebook.tab(1, state='disabled')  # Disable 3D tab for assemblies
        self.on_viz_tab_changed(None)
        
        # Save and refresh
        self.save_lenses()
        
        if self.selection_controller:
            self.selection_controller.refresh_lens_list()
        
        self.update_status(f"New system '{system.name}' created - Select lenses from the list to add to assembly")
    
    def on_delete_lens(self, lens: 'Lens') -> None:
        """Callback when a lens is deleted"""
        if lens in self.lenses:
            self.lenses.remove(lens)
            self.save_lenses()
        
        # If current lens was deleted, clear it and disable tabs
        if self.current_lens == lens:
            self.current_lens = None
            self.notebook.tab(0, state='disabled')
            self.notebook.tab(1, state='disabled')
            self.notebook.tab(2, state='disabled')
            self.notebook.tab(3, state='disabled')
            self.notebook.tab(4, state='disabled')
            self.notebook.tab(5, state='disabled')
        
        self.update_status(f"Lens '{lens.name}' deleted")
    
    def on_lens_updated_callback(self, lens: Optional['Lens'] = None) -> None:
        """Callback when lens data is updated"""
        if not lens:
            self.save_lenses()
            if self.selection_controller:
                self.selection_controller.refresh_lens_list()
            return

        # Check if lens is already in the list (by ID or identity)
        found = False
        for i, existing in enumerate(self.lenses):
            # Check identity first
            if existing is lens:
                found = True
                break
            # Check ID if available
            if hasattr(existing, 'id') and hasattr(lens, 'id') and existing.id == lens.id:
                # Replace the existing object with the new one (e.g. from optimizer)
                self.lenses[i] = lens
                found = True
                
                # If we replaced the current lens, update the reference
                if self.current_lens is existing:
                    self.current_lens = lens
                break
        
        if not found:
            self.lenses.append(lens)
            self.current_lens = lens
            if not getattr(self, '_loading_lens', False):
                self.update_status(f"New lens '{lens.name}' created")
        
        # If a single lens was updated, refresh all assemblies that might use it
        if not (hasattr(lens, 'elements') and hasattr(lens, 'air_gaps')):
            lens_lookup = {l.id: l for l in self.lenses if not (hasattr(l, 'elements') and hasattr(l, 'air_gaps'))}
            for item in self.lenses:
                if hasattr(item, 'elements') and hasattr(item, 'refresh_references'):
                    item.refresh_references(lens_lookup)
            
            # If current lens is an assembly using this lens, reload it in simulation
            if self.current_lens and hasattr(self.current_lens, 'elements'):
                if any(getattr(elem, 'lens_id', None) == getattr(lens, 'id', None) for elem in self.current_lens.elements):
                    if self.simulation_controller:
                        self.simulation_controller.load_lens(self.current_lens)
                        # Only auto-run if in simulation tab
                        if self.notebook.index(self.notebook.select()) == 2:
                            self.simulation_controller.run_simulation()

        self.save_lenses()
        if self.selection_controller:
            self.selection_controller.refresh_lens_list()
        
        # Refresh taskbar menu to reflect new/changed lenses
        if hasattr(self, 'taskbar_menu'):
            self._refresh_taskbar_menu()
        
        # Also refresh the menu bar's Lens menu
        if hasattr(self, '_lens_menu'):
            self._update_lens_menu()
        
        # Load lens into simulation tab
        if self.simulation_controller:
            self.simulation_controller.load_lens(lens)
        
        # Load lens into optimization tab
        if self.optimization_controller:
            self.optimization_controller.load_lens(lens)

        # Load lens into tolerancing tab
        if self.tolerancing_controller:
            self.tolerancing_controller.load_lens(lens)
    
    def setup_editor_tab(self) -> None:

        """Setup the Editor tab with lens properties using controller"""
        if not CONTROLLERS_AVAILABLE:
            ttk.Label(self.editor_tab, text="Error: GUI Controllers not available").pack(padx=20, pady=20)
            return

        # Use PanedWindow for resizable split view
        self.editor_paned = ttk.PanedWindow(self.editor_tab, orient=tk.HORIZONTAL)
        self.editor_paned.pack(fill=tk.BOTH, expand=True)

        # Left panel: Editor properties
        left_container = ttk.Frame(self.editor_paned)
        self.editor_paned.add(left_container, weight=1)
        
        left_container.columnconfigure(0, weight=1)
        left_container.rowconfigure(1, weight=1)
        
        # Fixed header
        header_frame = ttk.Frame(left_container, padding="5")
        header_frame.grid(row=0, column=0, sticky="ew")
        ttk.Label(header_frame, text="Optical Lens Properties", font=(FONT_FAMILY, FONT_SIZE_TITLE, 'bold')).pack(anchor=tk.W)
        
        # Editor content area
        editor_frame = ttk.Frame(left_container)
        editor_frame.grid(row=1, column=0, sticky="nsew")
        
        try:
            if TYPE_CHECKING:
                 assert LensEditorController is not None

            self.editor_controller = LensEditorController(
                colors=self.colors,
                on_lens_updated=self.on_lens_updated_callback
            )
            self.editor_controller.parent_window = self  # Give access to parent window
            self.editor_controller.setup_ui(editor_frame)
        except Exception as e:
            logger.error("Failed to initialize editor controller: %s", e)
            ttk.Label(editor_frame, text=f"Error loading editor: {e}").pack(padx=20, pady=20)

        # Right panel: Visualization
        self.viz_outer_frame = ttk.Frame(self.editor_paned)
        self.editor_paned.add(self.viz_outer_frame, weight=3)
        
        self.viz_outer_frame.columnconfigure(0, weight=1)
        self.viz_outer_frame.rowconfigure(1, weight=1)
        
        # Header with title
        viz_header = ttk.Frame(self.viz_outer_frame)
        viz_header.grid(row=0, column=0, sticky="ew", padx=PADDING_SMALL, pady=PADDING_SMALL)
        ttk.Label(viz_header, text="Lens Visualization", font=(FONT_FAMILY, FONT_SIZE_LARGE, 'bold')).pack(side=tk.LEFT)
        
        # Visualization mode toggle using tabs
        self.viz_mode_var = tk.StringVar(value="3D")
        
        # Create notebook for 2D/3D tabs
        self.viz_notebook = ttk.Notebook(self.viz_outer_frame)
        self.viz_notebook.grid(row=1, column=0, sticky="nsew", padx=PADDING_SMALL, pady=(0, 5))
        
        # Create frames for 2D and 3D tabs
        self.viz_2d_frame = ttk.Frame(self.viz_notebook)
        self.viz_3d_frame = ttk.Frame(self.viz_notebook)
        
        self.viz_notebook.add(self.viz_2d_frame, text="2D")
        self.viz_notebook.add(self.viz_3d_frame, text="3D")
        
        # Bind tab change event
        self.viz_notebook.bind('<<NotebookTabChanged>>', self.on_viz_tab_changed)
        
        # Select 3D tab by default
        self.viz_notebook.select(1)
        
        if VISUALIZATION_AVAILABLE:
            try:
                # Create visualizer in the 3D frame initially
                if TYPE_CHECKING:
                    assert LensVisualizer is not None
                
                self.visualizer = LensVisualizer(self.viz_3d_frame, width=6, height=6)
            except Exception as e:
                ttk.Label(self.viz_3d_frame, text=f"Visualization error: {e}", 
                         wraplength=300).pack(pady=PADDING_XLARGE)
                self.visualizer = None
        else:
            msg = "Visualization not available.\\n\\nInstall dependencies:\\n  pip install matplotlib numpy"
            ttk.Label(self.viz_3d_frame, text=msg, justify=tk.CENTER, 
                      font=(FONT_FAMILY, FONT_SIZE_NORMAL)).pack(pady=PADDING_SMALL)
            self.visualizer = None
    
    def on_viz_tab_changed(self, event: Optional[tk.Event]) -> None:
        """Handle visualization tab change between 2D and 3D"""
        if not self.visualizer:
            return
        
        # Get selected tab index
        try:
            selected_tab = self.viz_notebook.index(self.viz_notebook.select())
        except tk.TclError:
            return
        
        # Reparent the canvas to the selected tab's frame
        if selected_tab == 0:  # 2D tab
            self.viz_mode_var.set("2D")
            self.visualizer.reparent_canvas(self.viz_2d_frame)
        else:  # 3D tab
            self.viz_mode_var.set("3D")
            self.visualizer.reparent_canvas(self.viz_3d_frame)
        
        # Update the visualization using current lens from controller
        if self.editor_controller and self.editor_controller.current_lens:
            lens = self.editor_controller.current_lens
            mode = self.viz_mode_var.get()
            
            # Check if it's an OpticalSystem (assembly)
            if hasattr(lens, 'elements') and hasattr(lens, 'air_gaps'):
                # Hide visualization for assemblies in Editor Tab as per requirements
                try:
                    self.editor_paned.forget(self.editor_paned.panes()[1])
                except (tk.TclError, IndexError):
                    pass
                return
            else:
                # Show visualization for single lenses
                try:
                    panes = self.editor_paned.panes()
                    # If only one pane (index 0) is visible, add the second one back
                    if len(panes) < 2:
                        self.editor_paned.add(self.viz_outer_frame, weight=3)
                except (tk.TclError, AttributeError):
                    pass
            
            # Single lens - use existing logic
            try:
                if mode == "2D":
                    self.visualizer.draw_lens_2d(
                        lens.radius_of_curvature_1, 
                        lens.radius_of_curvature_2, 
                        lens.thickness, 
                        lens.diameter
                    )
                else:
                    self.visualizer.draw_lens(
                        lens.radius_of_curvature_1, 
                        lens.radius_of_curvature_2, 
                        lens.thickness, 
                        lens.diameter
                    )
            except Exception as e:
                logger.warning(f"Failed to update visualization: {e}")

    def setup_simulation_tab(self) -> None:
        """Setup the Simulation tab for ray tracing and optical analysis"""
        if not CONTROLLERS_AVAILABLE:
            ttk.Label(self.simulation_tab, text="Error: GUI Controllers not available").pack(padx=20, pady=20)
            return

        # Try to use controller if available
        try:
            if TYPE_CHECKING:
                assert SimulationController is not None

            self.simulation_controller = SimulationController(
                colors=self.colors,
                visualization_available=VISUALIZATION_AVAILABLE
            )
            self.simulation_controller.parent_window = self  # Give access to parent window
            self.simulation_controller.setup_ui(self.simulation_tab)
            
            logger.debug("SimulationController integrated successfully")
            
        except Exception as e:
            logger.error("SimulationController failed to load: %s", e)
            ttk.Label(self.simulation_tab, text=f"Error loading simulation: {e}").pack(padx=20, pady=20)

    def on_tab_changed(self, event: tk.Event) -> None:
        """Handle tab change events"""
        # Get the currently selected tab index
        try:
            selected_tab = self.notebook.index(self.notebook.select())
        except tk.TclError:
            return
        
        # If switching to simulation tab (index 2) and we have a current lens
        if selected_tab == 2 and self.current_lens:
            if self.simulation_controller:
                self.simulation_controller.load_lens(self.current_lens)
                self.simulation_controller.run_simulation()

    def setup_performance_tab(self) -> None:
        """Setup the Performance Metrics Dashboard tab"""
        try:
            if CONTROLLERS_AVAILABLE:
                if TYPE_CHECKING:
                    assert PerformanceController is not None

                self.performance_controller = PerformanceController(
                    colors=self.colors,
                    aberrations_available=ABERRATIONS_AVAILABLE,
                    parent_window=self
                )
                self.performance_controller.setup_ui(self.performance_tab)
                
                logger.debug("PerformanceController integrated successfully")
            else:
                 ttk.Label(self.performance_tab, text="Performance Controller not available").pack(padx=20, pady=20)
            
        except Exception as e:
            logger.error("PerformanceController failed to load: %s", e)
            ttk.Label(self.performance_tab, text=f"Error loading performance tab: {e}").pack(padx=20, pady=20)

    def setup_optimization_tab(self) -> None:
        """Setup the Optimization tab"""
        try:
            if CONTROLLERS_AVAILABLE:
                if TYPE_CHECKING:
                     assert OptimizationController is not None
                
                self.optimization_controller = OptimizationController(
                    colors=self.colors,
                    on_lens_updated=self.on_lens_updated_callback
                )
                self.optimization_controller.parent_window = self
                self.optimization_controller.setup_ui(self.optimization_tab)
                
                logger.debug("OptimizationController integrated successfully")
            else:
                 ttk.Label(self.optimization_tab, text="Optimization Controller not available").pack(padx=20, pady=20)
            
        except Exception as e:
            logger.error("OptimizationController failed to load: %s", e)
            ttk.Label(self.optimization_tab, text=f"Error loading optimization tab: {e}").pack(padx=20, pady=20)

    def setup_tolerancing_tab(self) -> None:
        """Setup the Tolerancing tab"""
        try:
            if CONTROLLERS_AVAILABLE:
                self.tolerancing_controller = TolerancingController(
                    colors=self.colors
                )
                self.tolerancing_controller.parent_window = self
                self.tolerancing_controller.setup_ui(self.tolerancing_tab)
                
                logger.debug("TolerancingController integrated successfully")
            else:
                 ttk.Label(self.tolerancing_tab, text="Tolerancing Controller not available").pack(padx=20, pady=20)
            
        except Exception as e:
            logger.error("TolerancingController failed to load: %s", e)
            ttk.Label(self.tolerancing_tab, text=f"Error loading tolerancing tab: {e}").pack(padx=20, pady=20)

    def setup_export_tab(self) -> None:
        """Setup the Export Enhancements tab"""
        if CONTROLLERS_AVAILABLE:
            try:
                if TYPE_CHECKING:
                    assert ExportController is not None

                self.export_controller = ExportController(self, self.colors)
                self.export_controller.setup_ui(self.export_tab)
                return
            except Exception as e:
                logger.warning("Failed to initialize ExportController: %s", e)
                self.export_controller = None

    def update_status(self, message: str, auto_clear: bool = True) -> None:
        self.status_var.set(message)
        self.root.update_idletasks()
        
        if auto_clear:
            if hasattr(self, '_status_clear_timer') and self._status_clear_timer is not None:
                self.root.after_cancel(self._status_clear_timer)
            self._status_clear_timer = self.root.after(10000, lambda: self.status_var.set("Ready"))

    def on_ctrl_s(self, event: Optional[tk.Event] = None) -> str:
        """Handle Ctrl+S keyboard shortcut"""
        if self.editor_controller and self.notebook.tab(self.notebook.select(), "text") == "Editor":
            self.editor_controller.save_changes(silent=False)
        return "break"

    def _on_ctrl_l(self, event: Optional[tk.Event] = None) -> str:
        """Handle Ctrl+L keyboard shortcut - show lens quick-switch menu"""
        if hasattr(self, 'taskbar_menu') and self.taskbar_menu.menu:
            self._refresh_taskbar_menu()
            try:
                self.taskbar_menu.menu.tk_popup(
                    self.root.winfo_x() + self.root.winfo_width() // 2,
                    self.root.winfo_y() + 100
                )
            finally:
                self.taskbar_menu.menu.grab_release()
        return "break"
