#!/usr/bin/env python3
"""
openlens - GUI Editor Window
Interactive graphical interface for optical lens creation and modification
"""

import logging
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

# Configure module logger
logger = logging.getLogger(__name__)

# Import constants
try:
    from .constants import (
        # GUI Colors
        COLOR_BG_DARK, COLOR_BG_MEDIUM, COLOR_BG_LIGHT, COLOR_FG, COLOR_FG_DIM,
        COLOR_ACCENT, COLOR_SUCCESS, COLOR_WARNING, COLOR_ERROR, COLOR_HIGHLIGHT,
        # Font settings
        FONT_FAMILY, FONT_SIZE_NORMAL, FONT_SIZE_LARGE, FONT_SIZE_TITLE,
        # Padding
        PADDING_SMALL, PADDING_MEDIUM, PADDING_LARGE, PADDING_XLARGE,
        # Widget sizing
        ENTRY_WIDTH, BUTTON_WIDTH, LISTBOX_WIDTH, LISTBOX_HEIGHT,
        # Tooltip
        TOOLTIP_OFFSET_X, TOOLTIP_OFFSET_Y,
        # Defaults
        DEFAULT_RADIUS_1, DEFAULT_RADIUS_2, DEFAULT_THICKNESS, DEFAULT_DIAMETER,
        DEFAULT_NUM_RAYS, DEFAULT_TEMPERATURE,
        # Validation
        MIN_RADIUS_OF_CURVATURE, MAX_RADIUS_OF_CURVATURE,
        MIN_THICKNESS, MAX_THICKNESS, MIN_DIAMETER, MAX_DIAMETER,
        MIN_REFRACTIVE_INDEX, MAX_REFRACTIVE_INDEX,
        # Optical
        REFRACTIVE_INDEX_BK7, WAVELENGTH_D_LINE, WAVELENGTH_GREEN,
        # Lens types
        ALL_LENS_TYPES,
        # Mesh resolution
        MESH_RESOLUTION_LOW, MESH_RESOLUTION_MEDIUM, MESH_RESOLUTION_HIGH,
        # Numerical
        EPSILON,
    )
    LENS_TYPES = ALL_LENS_TYPES
except ImportError:
    from constants import (
        # GUI Colors
        COLOR_BG_DARK, COLOR_BG_MEDIUM, COLOR_BG_LIGHT, COLOR_FG, COLOR_FG_DIM,
        COLOR_ACCENT, COLOR_SUCCESS, COLOR_WARNING, COLOR_ERROR, COLOR_HIGHLIGHT,
        # Font settings
        FONT_FAMILY, FONT_SIZE_NORMAL, FONT_SIZE_LARGE, FONT_SIZE_TITLE,
        # Padding
        PADDING_SMALL, PADDING_MEDIUM, PADDING_LARGE, PADDING_XLARGE,
        # Widget sizing
        ENTRY_WIDTH, BUTTON_WIDTH, LISTBOX_WIDTH, LISTBOX_HEIGHT,
        # Tooltip
        TOOLTIP_OFFSET_X, TOOLTIP_OFFSET_Y,
        # Defaults
        DEFAULT_RADIUS_1, DEFAULT_RADIUS_2, DEFAULT_THICKNESS, DEFAULT_DIAMETER,
        DEFAULT_NUM_RAYS, DEFAULT_TEMPERATURE,
        # Validation
        MIN_RADIUS_OF_CURVATURE, MAX_RADIUS_OF_CURVATURE,
        MIN_THICKNESS, MAX_THICKNESS, MIN_DIAMETER, MAX_DIAMETER,
        MIN_REFRACTIVE_INDEX, MAX_REFRACTIVE_INDEX,
        # Optical
        REFRACTIVE_INDEX_BK7, WAVELENGTH_D_LINE, WAVELENGTH_GREEN,
        # Lens types
        ALL_LENS_TYPES,
        # Mesh resolution
        MESH_RESOLUTION_LOW, MESH_RESOLUTION_MEDIUM, MESH_RESOLUTION_HIGH,
        # Numerical
        EPSILON,
    )
    LENS_TYPES = ALL_LENS_TYPES

# Try to import visualization (optional dependency)
try:
    from .lens_visualizer import LensVisualizer
    VISUALIZATION_AVAILABLE = True
except ImportError:
    try:
        from lens_visualizer import LensVisualizer
        VISUALIZATION_AVAILABLE = True
    except ImportError:
        VISUALIZATION_AVAILABLE = False
        logger.info("matplotlib not available. 3D visualization disabled.")

# Try to import STL export (optional dependency)
try:
    from .stl_export import export_lens_stl
    STL_EXPORT_AVAILABLE = True
except ImportError:
    try:
        from stl_export import export_lens_stl
        STL_EXPORT_AVAILABLE = True
    except ImportError:
        STL_EXPORT_AVAILABLE = False
        logger.info("STL export not available. NumPy required.")

# Try to import aberrations calculator
try:
    from .aberrations import AberrationsCalculator, analyze_lens_quality
    ABERRATIONS_AVAILABLE = True
except ImportError:
    try:
        from aberrations import AberrationsCalculator, analyze_lens_quality
        ABERRATIONS_AVAILABLE = True
    except ImportError:
        ABERRATIONS_AVAILABLE = False
        logger.info("Aberrations calculator not available.")

# Try to import ray tracer
try:
    from .ray_tracer import LensRayTracer, Ray
    RAY_TRACING_AVAILABLE = True
except ImportError:
    try:
        from ray_tracer import LensRayTracer, Ray
        RAY_TRACING_AVAILABLE = True
    except ImportError:
        RAY_TRACING_AVAILABLE = False
        logger.info("Ray tracer not available.")

# Try to import validation utilities
try:
    from .validation import (
        validate_json_file_path,
        validate_file_path,
        ValidationError
    )
except ImportError:
    try:
        from validation import (
            validate_json_file_path,
            validate_file_path,
            ValidationError
        )
    except ImportError:
        # Fallback if validation module not available
        ValidationError = ValueError
        def validate_json_file_path(path: Any, **kwargs: Any) -> Path:
            return Path(path)
        def validate_file_path(path: Any, **kwargs: Any) -> Path:
            return Path(path)

# Try to import GUI controllers
try:
    from .gui_controllers import (
        LensSelectionController,
        LensEditorController,
        SimulationController,
        PerformanceController,
        ComparisonController,
        ExportController
    )
    CONTROLLERS_AVAILABLE = True
except ImportError:
    try:
        from gui_controllers import (
            LensSelectionController,
            LensEditorController,
            SimulationController,
            PerformanceController,
            ComparisonController,
            ExportController
        )
        CONTROLLERS_AVAILABLE = True
    except ImportError:
        CONTROLLERS_AVAILABLE = False
        logger.info("GUI controllers not available.")

# Import Lens model
try:
    from .lens import Lens
except ImportError:
    try:
        from lens import Lens
    except ImportError:
        # Fallback if lens module not available (shouldn't happen in proper install)
        logger.error("Could not import Lens model")
        class Lens: pass

# Import CopyableMessageBox for copyable error dialogs
try:
    from .dialogs import CopyableMessageBox
except ImportError:
    try:
        from dialogs import CopyableMessageBox
    except ImportError:
        # Fallback to standard messagebox
        CopyableMessageBox = None

class ToolTip:
    """Simple tooltip for tkinter widgets"""
    def __init__(self, widget: tk.Widget, text: str) -> None:
        self.widget = widget
        self.text = text
        self.tooltip: Optional[tk.Toplevel] = None
        self.widget.bind("<Enter>", self.show_tooltip)
        self.widget.bind("<Leave>", self.hide_tooltip)
    
    def show_tooltip(self, event: Optional[tk.Event] = None) -> None:
        x, y, _, _ = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + TOOLTIP_OFFSET_X
        y += self.widget.winfo_rooty() + TOOLTIP_OFFSET_Y
        
        self.tooltip = tk.Toplevel(self.widget)
        self.tooltip.wm_overrideredirect(True)
        self.tooltip.wm_geometry(f"+{x}+{y}")
        
        label = tk.Label(self.tooltip, text=self.text, 
                        background=COLOR_BG_DARK, foreground=COLOR_FG,
                        relief=tk.SOLID, borderwidth=1, 
                        font=("Arial", 9), padx=PADDING_SMALL, pady=3)
        label.pack()
    
    def hide_tooltip(self, event: Optional[tk.Event] = None) -> None:
        if self.tooltip:
            self.tooltip.destroy()
            self.tooltip = None


class LensEditorWindow:
    # Dark mode color scheme
    COLORS = {
        'bg': '#1e1e1e',           # Main background
        'fg': '#e0e0e0',           # Main text
        'bg_dark': COLOR_BG_DARK,      # Darker sections
        'bg_light': '#2d2d2d',     # Lighter sections
        'accent': '#0078d4',       # Accent color (blue)
        'accent_hover': '#1e88e5', # Accent hover
        'border': '#3f3f3f',       # Border color
        'success': '#4caf50',      # Success green
        'warning': '#ff9800',      # Warning orange
        'error': '#f44336',        # Error red
        'text_dim': '#b0b0b0',     # Dimmed text
        'selected': '#37373d',     # Selected item
        'entry_bg': '#2b2b2b',     # Entry field background
        'button_bg': '#3c3c3c',    # Button background
    }
    
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("openlens - Optical Lens Editor")
        self.root.geometry("1400x800")  # Increased width for 3D view
        self.storage_file = "lenses.json"
        self.lenses: List[Lens] = self.load_lenses()
        self.current_lens: Optional[Lens] = None
        self.visualizer: Optional[Any] = None  # Will be initialized in setup_ui
        self.selected_lens_id: Optional[str] = None
        self._loading_lens: bool = False  # Flag to prevent autosave during load
        self._autosave_timer: Optional[str] = None  # Timer for debounced autosave
        
        # Initialize status_var early
        self.status_var = tk.StringVar(value="Welcome to openlens")
        
        # Initialize controllers (None until UI setup)
        self.selection_controller: Optional[Any] = None
        self.editor_controller: Optional[Any] = None
        self.simulation_controller: Optional[Any] = None
        
        # Configure dark mode
        self.setup_dark_mode()
        
        self.setup_ui()
        # self.refresh_lens_list()  # Removed as handled by controller
        
        # Remove keyboard shortcuts for save (autosave now)
        # self.root.bind('<Return>', lambda e: self.save_current_lens())
        # self.root.bind('<KP_Enter>', lambda e: self.save_current_lens())  # Numpad Enter
    
    def setup_dark_mode(self) -> None:
        """Configure dark mode theme for the application"""
        # Configure root window
        self.root.configure(bg=self.COLORS['bg'])
        
        # Create custom ttk style
        style = ttk.Style()
        style.theme_use('clam')  # Use clam theme as base
        
        # Configure general ttk styles
        style.configure('.',
                       background=self.COLORS['bg'],
                       foreground=self.COLORS['fg'],
                       bordercolor=self.COLORS['border'],
                       darkcolor=self.COLORS['bg_dark'],
                       lightcolor=self.COLORS['bg_light'],
                       troughcolor=self.COLORS['bg_dark'],
                       focuscolor=self.COLORS['accent'],
                       selectbackground=self.COLORS['accent'],
                       selectforeground=self.COLORS['fg'])
        
        # Frame styles
        style.configure('TFrame',
                       background=self.COLORS['bg'])
        
        style.configure('TLabelframe',
                       background=self.COLORS['bg'],
                       foreground=self.COLORS['fg'],
                       bordercolor=self.COLORS['border'])
        
        style.configure('TLabelframe.Label',
                       background=self.COLORS['bg'],
                       foreground=self.COLORS['fg'])
        
        # Label styles
        style.configure('TLabel',
                       background=self.COLORS['bg'],
                       foreground=self.COLORS['fg'])
        
        # Button styles
        style.configure('TButton',
                       background=self.COLORS['button_bg'],
                       foreground=self.COLORS['fg'],
                       bordercolor=self.COLORS['border'],
                       focuscolor=self.COLORS['accent'],
                       lightcolor=self.COLORS['bg_light'],
                       darkcolor=self.COLORS['bg_dark'])
        
        style.map('TButton',
                 background=[('active', self.COLORS['accent']),
                           ('pressed', self.COLORS['bg_dark'])],
                 foreground=[('active', self.COLORS['fg'])])
        
        # Entry styles
        style.configure('TEntry',
                       fieldbackground=self.COLORS['entry_bg'],
                       background=self.COLORS['entry_bg'],
                       foreground=self.COLORS['fg'],
                       bordercolor=self.COLORS['border'],
                       insertcolor=self.COLORS['fg'])
        
        # Readonly entry style (darker background to indicate readonly)
        style.map('TEntry',
                 fieldbackground=[('readonly', self.COLORS['bg_dark'])],
                 foreground=[('readonly', self.COLORS['text_dim'])])
        
        # Combobox styles
        style.configure('TCombobox',
                       fieldbackground=self.COLORS['entry_bg'],
                       background=self.COLORS['entry_bg'],
                       foreground=self.COLORS['fg'],
                       bordercolor=self.COLORS['border'],
                       arrowcolor=self.COLORS['fg'],
                       selectbackground=self.COLORS['accent'],
                       selectforeground=self.COLORS['fg'])
        
        style.map('TCombobox',
                 fieldbackground=[('readonly', self.COLORS['entry_bg'])],
                 selectbackground=[('readonly', self.COLORS['accent'])],
                 selectforeground=[('readonly', self.COLORS['fg'])])
        
        # Separator style
        style.configure('TSeparator',
                       background=self.COLORS['border'])
        
        # Notebook (tab) styles
        style.configure('TNotebook',
                       background=self.COLORS['bg'],
                       bordercolor=self.COLORS['border'],
                       tabmargins=[2, 5, 2, 0])
        
        style.configure('TNotebook.Tab',
                       background=self.COLORS['bg_dark'],
                       foreground=self.COLORS['fg'],
                       padding=[20, 10],
                       bordercolor=self.COLORS['border'])
        
        style.map('TNotebook.Tab',
                 background=[('selected', self.COLORS['accent']),
                            ('active', self.COLORS['bg_light'])],
                 foreground=[('selected', self.COLORS['fg']),
                            ('active', self.COLORS['fg'])],
                 expand=[('selected', [1, 1, 1, 0])])
    
    def load_lenses(self) -> List[Lens]:
        """Load lenses from JSON storage file with path validation"""
        try:
            # Validate file path
            file_path = validate_file_path(
                self.storage_file,
                must_exist=True,
                create_parent=False
            )
            
            # Read and parse JSON
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Validate JSON structure
            if not isinstance(data, list):
                logger.warning("Storage file contains invalid data structure")
                return []
            
            # Load lenses
            lenses = []
            for i, lens_data in enumerate(data):
                try:
                    lenses.append(Lens.from_dict(lens_data))
                except Exception as e:
                    logger.warning("Failed to load lens %d: %s", i, e)
            
            return lenses
            
        except ValidationError:
            # File doesn't exist - return empty list
            return []
        except json.JSONDecodeError as e:
            logger.error("Invalid JSON in storage file: %s", e)
            return []
        except Exception as e:
            logger.error("Failed to load lenses: %s", e)
            return []
    
    def save_lenses(self) -> bool:
        """Save all lenses to JSON storage file with path validation"""
        try:
            # Validate and prepare file path
            file_path = validate_json_file_path(
                self.storage_file,
                must_exist=False
            )
            
            # Ensure parent directory exists and is writable
            parent_dir = file_path.parent
            if not parent_dir.exists():
                parent_dir.mkdir(parents=True, exist_ok=True)
            
            if not os.access(parent_dir, os.W_OK):
                self.update_status(f"Error: Directory is not writable: {parent_dir}")
                return False
            
            # Serialize lenses to JSON
            data = [lens.to_dict() for lens in self.lenses]
            
            # Write to file with atomic operation (write to temp, then rename)
            temp_path = file_path.with_suffix('.tmp')
            try:
                with open(temp_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                
                # Atomic rename
                temp_path.replace(file_path)
                
                self.update_status(f"✓ Saved {len(self.lenses)} lens(es)")
                return True
                
            finally:
                # Clean up temp file if it still exists
                if temp_path.exists():
                    temp_path.unlink()
            
        except ValidationError as e:
            self.update_status(f"Error: Invalid file path: {e}")
            return False
        except PermissionError as e:
            self.update_status(f"Error: Permission denied: {e}")
            return False
        except OSError as e:
            self.update_status(f"Error: OS error when saving: {e}")
            return False
        except Exception as e:
            self.update_status(f"Error: Failed to save lenses: {e}")
            return False
    
    def setup_ui(self) -> None:
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(0, weight=1)
        
        # Create tabbed interface
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.notebook.bind('<<NotebookTabChanged>>', self.on_tab_changed)
        
        # Create Lens Selection tab (always enabled)
        self.selection_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.selection_tab, text="Lens Selection")
        
        # Create Editor tab (disabled until lens selected)
        self.editor_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.editor_tab, text="Editor", state='disabled')
        
        # Create Simulation tab (disabled until lens selected)
        self.simulation_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.simulation_tab, text="Simulation", state='disabled')
        
        # Create Performance tab (disabled until lens selected)
        self.performance_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.performance_tab, text="Performance", state='disabled')
        
        # Create Comparison tab (always enabled for multi-lens comparison)
        self.comparison_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.comparison_tab, text="Comparison")
        
        # Create Export tab (disabled until lens selected)
        self.export_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.export_tab, text="Export", state='disabled')
        
        # Configure tabs grid
        self.selection_tab.columnconfigure(0, weight=1)
        self.selection_tab.rowconfigure(0, weight=1)
        
        self.editor_tab.columnconfigure(1, weight=1)
        self.editor_tab.columnconfigure(2, weight=1)
        self.editor_tab.rowconfigure(0, weight=1)
        
        # Setup tab content
        self.setup_selection_tab()
        self.setup_editor_tab()
        self.setup_simulation_tab()
        self.setup_performance_tab()
        self.setup_comparison_tab()
        self.setup_export_tab()
        
        # Status bar (below tabs)
        status_frame = ttk.Frame(main_frame)
        status_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=PADDING_SMALL, padx=PADDING_SMALL)
        
        self.status_var = tk.StringVar(value="Select or create a lens to begin")
        status_label = ttk.Label(status_frame, textvariable=self.status_var, 
                                 relief=tk.SUNKEN, anchor=tk.W,
                                 font=('Arial', 9, 'bold'),
                                 padding=(5, 3))
        status_label.pack(fill=tk.X)
        
        self.update_status("Select or create a lens to begin")
    
    def setup_selection_tab(self) -> None:
        """Setup the Lens Selection tab using controller"""
        if not CONTROLLERS_AVAILABLE:
            ttk.Label(self.selection_tab, text="Error: GUI Controllers not available").pack(padx=20, pady=20)
            return

        try:
            self.selection_controller = LensSelectionController(
                parent_window=self,
                lens_list=self.lenses,
                colors=self.COLORS,
                on_lens_selected=self.on_lens_selected_callback,
                on_create_new=self.on_create_new_lens,
                on_delete=self.on_delete_lens,
                on_lens_updated=self.on_lens_updated_callback,
                on_export=None
            )
            self.selection_controller.setup_ui(self.selection_tab)
        except Exception as e:
            logger.error("Failed to initialize selection controller: %s", e)
            ttk.Label(self.selection_tab, text=f"Error loading selection tab: {e}").pack(padx=20, pady=20)
    
    # Controller callback methods
    def on_lens_selected_callback(self, lens: 'Lens') -> None:
        """Callback when a lens is selected from the controller"""
        self.current_lens = lens
        
        # Enable tabs
        self.notebook.tab(1, state='normal')  # Editor
        self.notebook.tab(2, state='normal')  # Simulation
        self.notebook.tab(3, state='normal')  # Performance
        self.notebook.tab(5, state='normal')  # Export
        
        # Switch to editor and load lens
        self.notebook.select(1)
        
        # Load lens into controllers
        if hasattr(self, 'editor_controller') and self.editor_controller:
            self.editor_controller.load_lens(lens)
            
        if hasattr(self, 'simulation_controller') and self.simulation_controller:
            self.simulation_controller.load_lens(lens)
        
        if hasattr(self, 'performance_controller') and self.performance_controller:
            self.performance_controller.load_lens(lens)
        
        if hasattr(self, 'export_controller') and self.export_controller:
            self.export_controller.load_lens(lens)
        
        # Update visualization
        self.on_viz_tab_changed(None)
        
        self.update_status(f"Lens selected: '{lens.name}' - Ready to edit")
    
    def on_create_new_lens(self) -> None:
        """Callback when creating a new lens"""
        self.current_lens = None
        
        # Enable tabs
        self.notebook.tab(1, state='normal')
        self.notebook.tab(2, state='normal')
        self.notebook.tab(3, state='normal')
        self.notebook.tab(5, state='normal')
        
        # Switch to editor
        self.notebook.select(1)
        
        # Clear/Prepare editor
        if hasattr(self, 'editor_controller') and self.editor_controller:
            self.editor_controller.load_lens(None)  # Clears form
            
        self.update_status("Ready to create new lens")
    
    def on_delete_lens(self, lens: 'Lens') -> None:
        """Callback when a lens is deleted"""
        if lens in self.lenses:
            self.lenses.remove(lens)
            self.save_lenses()
        
        # If current lens was deleted, clear it and disable tabs
        if self.current_lens == lens:
            self.current_lens = None
            self.notebook.tab(1, state='disabled')
            self.notebook.tab(2, state='disabled')
            self.notebook.tab(3, state='disabled')
            self.notebook.tab(5, state='disabled')
        
        self.update_status(f"Lens '{lens.name}' deleted")
        
        # Refresh comparison controller if available
        if hasattr(self, 'comparison_controller') and self.comparison_controller:
            self.comparison_controller.refresh_lens_list()
    
    def on_lens_updated_callback(self, lens: Optional['Lens'] = None) -> None:
        """Callback when lens data is updated"""
        # If a lens was passed and it's not in our list (newly created), add it
        if lens and lens not in self.lenses:
            self.lenses.append(lens)
            self.current_lens = lens
            self.update_status(f"New lens '{lens.name}' created")
            
        self.save_lenses()
        if self.selection_controller:
            self.selection_controller.refresh_lens_list()
        
        # Refresh comparison controller if available
        if hasattr(self, 'comparison_controller') and self.comparison_controller:
            self.comparison_controller.refresh_lens_list()
    
    def _setup_selection_tab_legacy(self) -> None:
        """Legacy selection tab setup (fallback if controllers unavailable)"""
        pass  # Legacy implementation removed

    
    def setup_editor_tab(self) -> None:
        """Setup the Editor tab with lens properties using controller"""
        if not CONTROLLERS_AVAILABLE:
            ttk.Label(self.editor_tab, text="Error: GUI Controllers not available").pack(padx=20, pady=20)
            return

        # Configure tab grid
        self.editor_tab.columnconfigure(0, weight=1)
        self.editor_tab.columnconfigure(1, weight=1)
        self.editor_tab.rowconfigure(0, weight=1)

        # Left panel: Editor properties
        left_container = ttk.Frame(self.editor_tab)
        left_container.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        left_container.columnconfigure(0, weight=1)
        left_container.rowconfigure(1, weight=1)
        
        # Fixed header
        header_frame = ttk.Frame(left_container, padding="5")
        header_frame.grid(row=0, column=0, sticky=(tk.W, tk.E))
        ttk.Label(header_frame, text="Optical Lens Properties", font=(FONT_FAMILY, FONT_SIZE_TITLE, 'bold')).pack(anchor=tk.W)
        
        # Editor content area
        editor_frame = ttk.Frame(left_container)
        editor_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        try:
            self.editor_controller = LensEditorController(
                colors=self.COLORS,
                on_lens_updated=self.on_lens_updated_callback
            )
            self.editor_controller.parent_window = self  # Give access to parent window
            self.editor_controller.setup_ui(editor_frame)
        except Exception as e:
            logger.error("Failed to initialize editor controller: %s", e)
            ttk.Label(editor_frame, text=f"Error loading editor: {e}").pack(padx=20, pady=20)

        # Right panel: Visualization
        viz_outer_frame = ttk.Frame(self.editor_tab)
        viz_outer_frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S))
        viz_outer_frame.columnconfigure(0, weight=1)
        viz_outer_frame.rowconfigure(1, weight=1)
        
        # Header with title
        viz_header = ttk.Frame(viz_outer_frame)
        viz_header.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=PADDING_SMALL, pady=PADDING_SMALL)
        ttk.Label(viz_header, text="Lens Visualization", font=(FONT_FAMILY, FONT_SIZE_LARGE, 'bold')).pack(side=tk.LEFT)
        
        # Visualization mode toggle using tabs
        self.viz_mode_var = tk.StringVar(value="3D")
        
        # Create notebook for 2D/3D tabs
        self.viz_notebook = ttk.Notebook(viz_outer_frame)
        self.viz_notebook.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=PADDING_SMALL, pady=(0, 5))
        
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
                self.visualizer = LensVisualizer(self.viz_3d_frame, width=6, height=6)
            except Exception as e:
                ttk.Label(self.viz_3d_frame, text=f"Visualization error: {e}", 
                         wraplength=300).pack(pady=PADDING_XLARGE)
                self.visualizer = None
        else:
            msg = "Visualization not available.\n\nInstall dependencies:\n  pip install matplotlib numpy"
            ttk.Label(self.viz_3d_frame, text=msg, justify=tk.CENTER, 
                     font=(FONT_FAMILY, FONT_SIZE_NORMAL)).pack(pady=PADDING_SMALL)
            self.visualizer = None
    
    def _setup_editor_tab_legacy(self) -> None:
        """Legacy implementation of editor tab"""
        pass # Removed as part of consolidation
    
    def on_viz_tab_changed(self, event: tk.Event) -> None:
        """Handle visualization tab change between 2D and 3D"""
        if not self.visualizer:
            return
        
        # Get selected tab index
        selected_tab = self.viz_notebook.index(self.viz_notebook.select())
        
        # Reparent the canvas to the selected tab's frame
        if selected_tab == 0:  # 2D tab
            self.viz_mode_var.set("2D")
            self.visualizer.reparent_canvas(self.viz_2d_frame)
        else:  # 3D tab
            self.viz_mode_var.set("3D")
            self.visualizer.reparent_canvas(self.viz_3d_frame)
        
        # Update the visualization using current lens from controller
        if hasattr(self, 'editor_controller') and self.editor_controller and self.editor_controller.current_lens:
            lens = self.editor_controller.current_lens
            mode = self.viz_mode_var.get()
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
            self.simulation_controller = SimulationController(
                colors=self.COLORS,
                visualization_available=VISUALIZATION_AVAILABLE
            )
            self.simulation_controller.parent_window = self  # Give access to parent window
            self.simulation_controller.setup_ui(self.simulation_tab)
            
            logger.debug("SimulationController integrated successfully")
            
        except ImportError as e:
            logger.error("SimulationController failed to load: %s", e)
            ttk.Label(self.simulation_tab, text=f"Error loading simulation: {e}").pack(padx=20, pady=20)
    
    def _setup_simulation_tab_legacy(self) -> None:
        """Legacy simulation tab setup (fallback)"""
        pass # Removed as part of consolidation

    
    def run_simulation(self) -> None:
        """Run ray tracing simulation for the current lens"""
        # Delegate to controller if available
        if hasattr(self, 'simulation_controller') and self.simulation_controller:
            self.simulation_controller.run_simulation()
            return
        
        logger.warning("Simulation controller not available")

    

    
    
    

    
    
    
    def on_tab_changed(self, event: tk.Event) -> None:
        """Handle tab change events"""
        # Get the currently selected tab index
        selected_tab = self.notebook.index(self.notebook.select())
        
        # If switching to simulation tab (index 2) and we have a current lens
        if selected_tab == 2 and self.current_lens:
            if hasattr(self, 'simulation_controller') and self.simulation_controller:
                self.simulation_controller.load_lens(self.current_lens)
                self.simulation_controller.run_simulation()
        
        # If switching to comparison tab (index 4), refresh the list
        if selected_tab == 4:
            if hasattr(self, 'comparison_controller') and self.comparison_controller:
                self.comparison_controller.refresh_lens_list()
    
    def setup_performance_tab(self) -> None:
        """Setup the Performance Metrics Dashboard tab"""
        # Try to use controller if available
        try:
            from gui_controllers import PerformanceController
            
            colors = {
                'bg': COLOR_BG_DARK,
                'fg': COLOR_FG,
                'entry_bg': self.COLORS['entry_bg']
            }
            
            self.performance_controller = PerformanceController(
                colors=colors,
                aberrations_available=ABERRATIONS_AVAILABLE
            )
            self.performance_controller.setup_ui(self.performance_tab)
            
            logger.debug("PerformanceController integrated successfully")
            
        except ImportError as e:
            logger.error("PerformanceController failed to load: %s", e)
            ttk.Label(self.performance_tab, text=f"Error loading performance tab: {e}").pack(padx=20, pady=20)
    
    def _setup_performance_tab_legacy(self) -> None:
        """Legacy performance tab setup (fallback)"""
        pass # Removed as part of consolidation
    
    def setup_comparison_tab(self) -> None:
        """Setup the Comparison Mode tab"""
        # Try to use controller if available
        if CONTROLLERS_AVAILABLE:
            try:
                from gui_controllers import ComparisonController
                self.comparison_controller = ComparisonController(self, lambda: self.lenses, self.COLORS)
                self.comparison_controller.setup_ui(self.comparison_tab)
                return
            except Exception as e:
                logger.warning("Failed to initialize ComparisonController: %s", e)
                ttk.Label(self.comparison_tab, text=f"Error loading comparison: {e}").pack(padx=20, pady=20)
        
    def _setup_comparison_tab_legacy(self) -> None:
        """Legacy comparison tab setup"""
        pass # Removed as part of consolidation
    
    def setup_export_tab(self) -> None:
        """Setup the Export Enhancements tab"""
        # Try to use controller if available
        if CONTROLLERS_AVAILABLE:
            try:
                from gui_controllers import ExportController
                self.export_controller = ExportController(self, self.COLORS)
                self.export_controller.setup_ui(self.export_tab)
                return
            except Exception as e:
                logger.warning("Failed to initialize ExportController: %s", e)
                self.export_controller = None
        
        # Fallback removed
    
    def _setup_export_tab_legacy(self) -> None:
        """Legacy export tab setup"""
        pass # Removed as part of consolidation

    def export_to_zemax(self) -> None:
        """Legacy export removed"""
        pass

    def export_to_opticstudio(self) -> None:
        """Legacy export removed"""
        pass

    def export_to_pdf(self) -> None:
        """Legacy export removed"""
        pass

    def export_to_svg(self) -> None:
        """Legacy export removed"""
        pass

    def export_prescription(self) -> None:
        """Legacy export removed"""
        pass

    def _log_export_status(self, message: str) -> None:
        """Legacy logging removed"""
        pass
    
    def update_status(self, message: str) -> None:
        self.status_var.set(message)
        self.root.update_idletasks()


def main() -> None:
    root = tk.Tk()
    app = LensEditorWindow(root)
    root.mainloop()


if __name__ == "__main__":
    main()
