#!/usr/bin/env python3
"""
openlens - GUI Editor Window
Interactive graphical interface for optical lens creation and modification
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

# Import constants
try:
    from .constants import *
except ImportError:
    from constants import *

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
        print("Note: matplotlib not available. 3D visualization disabled.")
        print("Install with: pip install matplotlib numpy")

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
        print("Note: STL export not available. NumPy required.")

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
        print("Note: Aberrations calculator not available.")

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
        print("Note: Ray tracer not available.")

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


class Lens:
    def __init__(self, name: str = "Untitled", 
                 radius_of_curvature_1: float = DEFAULT_RADIUS_1, 
                 radius_of_curvature_2: float = DEFAULT_RADIUS_2,
                 thickness: float = DEFAULT_THICKNESS, 
                 diameter: float = DEFAULT_DIAMETER, 
                 refractive_index: float = REFRACTIVE_INDEX_BK7, 
                 lens_type: str = "Biconvex", 
                 material: str = "BK7", 
                 is_fresnel: bool = False, 
                 groove_pitch: float = DEFAULT_THICKNESS, 
                 num_grooves: Optional[int] = None) -> None:
        self.id = datetime.now().strftime("%Y%m%d%H%M%S%f")
        self.name = name
        self.radius_of_curvature_1 = radius_of_curvature_1  # R1 (front surface, mm)
        self.radius_of_curvature_2 = radius_of_curvature_2  # R2 (back surface, mm)
        self.thickness = thickness  # Center thickness (mm)
        self.diameter = diameter  # Lens diameter (mm)
        self.refractive_index = refractive_index  # Index of refraction (n)
        self.lens_type = lens_type  # Convex, Concave, Plano-Convex, etc.
        self.material = material  # Glass type
        self.is_fresnel = is_fresnel  # Is this a Fresnel lens?
        self.groove_pitch = groove_pitch  # Pitch between grooves (mm)
        self.num_grooves = num_grooves  # Number of grooves (calculated if None)
        self.created_at = datetime.now().isoformat()
        self.modified_at = datetime.now().isoformat()
        
        # Auto-calculate number of grooves if not provided
        if self.is_fresnel and self.num_grooves is None:
            self.calculate_num_grooves()
    
    def calculate_num_grooves(self) -> None:
        """Calculate the number of grooves based on diameter and pitch"""
        if self.groove_pitch > 0:
            self.num_grooves = int((self.diameter / 2) / self.groove_pitch)
        else:
            self.num_grooves = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "radius_of_curvature_1": self.radius_of_curvature_1,
            "radius_of_curvature_2": self.radius_of_curvature_2,
            "thickness": self.thickness,
            "diameter": self.diameter,
            "refractive_index": self.refractive_index,
            "type": self.lens_type,
            "material": self.material,
            "is_fresnel": self.is_fresnel,
            "groove_pitch": self.groove_pitch,
            "num_grooves": self.num_grooves,
            "created_at": self.created_at,
            "modified_at": self.modified_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Lens':
        lens = cls(
            name=data.get("name", "Untitled"),
            radius_of_curvature_1=data.get("radius_of_curvature_1", DEFAULT_RADIUS_1),
            radius_of_curvature_2=data.get("radius_of_curvature_2", DEFAULT_RADIUS_2),
            thickness=data.get("thickness", DEFAULT_THICKNESS),
            diameter=data.get("diameter", DEFAULT_DIAMETER),
            refractive_index=data.get("refractive_index", REFRACTIVE_INDEX_BK7),
            lens_type=data.get("type", "Biconvex"),
            material=data.get("material", "BK7"),
            is_fresnel=data.get("is_fresnel", False),
            groove_pitch=data.get("groove_pitch", DEFAULT_THICKNESS),
            num_grooves=data.get("num_grooves", None)
        )
        lens.id = data.get("id", lens.id)
        lens.created_at = data.get("created_at", lens.created_at)
        lens.modified_at = data.get("modified_at", lens.modified_at)
        return lens
    
    def calculate_focal_length(self) -> Optional[float]:
        """Calculate focal length using the lensmaker's equation"""
        n = self.refractive_index
        R1 = self.radius_of_curvature_1
        R2 = self.radius_of_curvature_2
        d = self.thickness
        
        if R1 == 0 or R2 == 0:
            return None
        
        # Lensmaker's equation
        power = (n - 1) * ((1/R1) - (1/R2) + ((n - 1) * d) / (n * R1 * R2))
        
        if power == 0:
            return None
        
        focal_length = 1 / power
        return focal_length
    
    def calculate_fresnel_efficiency(self) -> Optional[float]:
        """Calculate theoretical efficiency of Fresnel lens"""
        if not self.is_fresnel:
            return None
        
        # Simplified efficiency calculation
        # Fresnel lenses typically have 85-95% efficiency
        # depending on groove quality and pitch
        base_efficiency = 0.90
        
        # Efficiency decreases with smaller pitch (harder to manufacture)
        if self.groove_pitch < 0.5:
            efficiency_factor = 0.85
        elif self.groove_pitch < 1.0:
            efficiency_factor = 0.90
        else:
            efficiency_factor = 0.95
        
        return base_efficiency * efficiency_factor
    
    def calculate_fresnel_thickness_reduction(self) -> Optional[Dict[str, float]]:
        """Calculate thickness reduction compared to conventional lens"""
        if not self.is_fresnel or self.num_grooves is None:
            return None
        
        # Fresnel lens can reduce thickness by removing material between grooves
        # Each groove saves approximately the groove pitch height
        # This is a simplified calculation
        conventional_thickness = self.thickness
        fresnel_thickness = max(1.0, self.groove_pitch * 2)  # Minimum 1mm
        
        reduction_percentage = ((conventional_thickness - fresnel_thickness) / conventional_thickness) * 100
        return {
            'conventional_thickness': conventional_thickness,
            'fresnel_thickness': fresnel_thickness,
            'reduction_percentage': reduction_percentage,
            'weight_reduction_percentage': reduction_percentage * 0.9  # Approximate weight reduction
        }


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
        self.refresh_lens_list()
        
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
                print("Warning: Storage file contains invalid data structure")
                return []
            
            # Load lenses
            lenses = []
            for i, lens_data in enumerate(data):
                try:
                    lenses.append(Lens.from_dict(lens_data))
                except Exception as e:
                    print(f"Warning: Failed to load lens {i}: {e}")
            
            return lenses
            
        except ValidationError:
            # File doesn't exist - return empty list
            return []
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in storage file: {e}")
            return []
        except Exception as e:
            print(f"Error: Failed to load lenses: {e}")
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
        """Setup the Lens Selection tab"""
        
        # Main content frame
        content_frame = ttk.Frame(self.selection_tab, padding="20")
        content_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        content_frame.columnconfigure(0, weight=1)
        content_frame.rowconfigure(1, weight=1)
        
        # Title
        title_label = ttk.Label(content_frame, text="Lens Library", 
                               font=(FONT_FAMILY, 16, 'bold'))
        title_label.grid(row=0, column=0, pady=(0, PADDING_XLARGE))
        
        # Create a frame for the lens list and buttons
        list_frame = ttk.LabelFrame(content_frame, text="Available Lenses", padding="10")
        list_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)
        
        # Lens listbox with scrollbar
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        self.selection_listbox = tk.Listbox(list_frame, 
                                           yscrollcommand=scrollbar.set,
                                           bg=self.COLORS['entry_bg'],
                                           fg=self.COLORS['fg'],
                                           selectbackground=self.COLORS['accent'],
                                           selectforeground=self.COLORS['fg'],
                                           font=(FONT_FAMILY, FONT_SIZE_LARGE),
                                           height=15,
                                           borderwidth=1,
                                           relief=tk.SOLID)
        self.selection_listbox.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 5))
        scrollbar.config(command=self.selection_listbox.yview)
        
        # Bind double-click to select lens
        self.selection_listbox.bind('<Double-Button-1>', lambda e: self.select_lens_from_list())
        
        # Lens info panel
        info_frame = ttk.LabelFrame(content_frame, text="Lens Information", padding="10")
        info_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=PADDING_XLARGE)
        
        self.selection_info_text = tk.Text(info_frame, 
                                          height=9, 
                                          bg=self.COLORS['entry_bg'],
                                          fg=self.COLORS['fg'],
                                          font=(FONT_FAMILY, FONT_SIZE_NORMAL),
                                          wrap=tk.WORD,
                                          borderwidth=1,
                                          relief=tk.SOLID,
                                          state='disabled')
        self.selection_info_text.pack(fill=tk.BOTH, expand=True)
        
        # Bind selection change to update info
        self.selection_listbox.bind('<<ListboxSelect>>', self.update_selection_info)
        
        # Button frame
        button_frame = ttk.Frame(content_frame)
        button_frame.grid(row=3, column=0, pady=PADDING_XLARGE)
        
        ttk.Button(button_frame, text="Create New Lens", 
                  command=self.create_new_lens_from_selection,
                  width=20).pack(side=tk.LEFT, padx=PADDING_SMALL)
        
        ttk.Button(button_frame, text="Select & Edit", 
                  command=self.select_lens_from_list,
                  width=20).pack(side=tk.LEFT, padx=PADDING_SMALL)
        
        ttk.Button(button_frame, text="Delete Lens", 
                  command=self.delete_lens_from_selection,
                  width=20).pack(side=tk.LEFT, padx=PADDING_SMALL)
        
        if STL_EXPORT_AVAILABLE:
            ttk.Button(button_frame, text="Export to STL", 
                      command=self.export_lens_to_stl,
                      width=20).pack(side=tk.LEFT, padx=PADDING_SMALL)
        
        # Populate the list
        self.refresh_selection_list()
    
    def refresh_selection_list(self) -> None:
        """Refresh the lens selection list"""
        self.selection_listbox.delete(0, tk.END)
        for lens in self.lenses:
            display_name = f"{lens.name} ({lens.lens_type})"
            self.selection_listbox.insert(tk.END, display_name)
        
        if self.lenses:
            self.update_status(f"{len(self.lenses)} lens(es) available - Select one to edit or create new")
        else:
            self.update_status("No lenses available - Create a new lens to begin")
    
    def update_selection_info(self, event: Optional[tk.Event] = None) -> None:
        """Update the lens information panel when selection changes"""
        selection = self.selection_listbox.curselection()
        if not selection:
            self.selection_info_text.config(state='normal')
            self.selection_info_text.delete(1.0, tk.END)
            self.selection_info_text.insert(1.0, "Select a lens to view details")
            self.selection_info_text.config(state='disabled')
            return
        
        index = selection[0]
        lens = self.lenses[index]
        
        focal_length = lens.calculate_focal_length() or 0
        
        info = f"""ID: {lens.id}
Name: {lens.name}
Type: {lens.lens_type}
Material: {lens.material}
Radius 1: {lens.radius_of_curvature_1:.3f} mm
Radius 2: {lens.radius_of_curvature_2:.3f} mm
Center Thickness: {lens.thickness:.3f} mm
Diameter: {lens.diameter:.3f} mm
Refractive Index: {lens.refractive_index:.3f}
Focal Length: {focal_length:.3f} mm
Created: {lens.created_at}
Modified: {lens.modified_at}"""
        
        self.selection_info_text.config(state='normal')
        self.selection_info_text.delete(1.0, tk.END)
        self.selection_info_text.insert(1.0, info)
        self.selection_info_text.config(state='disabled')
    
    def create_new_lens_from_selection(self) -> None:
        """Create a new lens from the selection tab"""
        # Clear the form and current lens to start fresh
        self.current_lens = None
        self.clear_form()
        
        # Enable editor, simulation, performance and export tabs
        self.notebook.tab(1, state='normal')  # Editor tab
        self.notebook.tab(2, state='normal')  # Simulation tab
        self.notebook.tab(3, state='normal')  # Performance tab
        self.notebook.tab(5, state='normal')  # Export tab
        
        # Switch to editor tab
        self.notebook.select(1)
        self.update_status("Ready to create new lens")
    
    def select_lens_from_list(self) -> None:
        """Select a lens from the selection list and switch to editor"""
        selection = self.selection_listbox.curselection()
        if not selection:
            self.update_status("Please select a lens first")
            return
        
        index = selection[0]
        self.current_lens = self.lenses[index]
        
        # Enable editor, simulation, performance and export tabs
        self.notebook.tab(1, state='normal')  # Editor tab
        self.notebook.tab(2, state='normal')  # Simulation tab
        self.notebook.tab(3, state='normal')  # Performance tab
        self.notebook.tab(5, state='normal')  # Export tab
        
        # Switch to editor tab
        self.notebook.select(1)
        
        # Update editor display
        self.refresh_lens_list()
        self.load_lens_to_form(self.current_lens)
        
        # Update simulation tab with current lens
        self.update_simulation_view()
        
        self.update_status(f"Lens selected: '{self.current_lens.name}' - Ready to edit")
    
    def delete_lens_from_selection(self) -> None:
        """Delete a lens from the selection list"""
        selection = self.selection_listbox.curselection()
        if not selection:
            self.update_status("Please select a lens to delete")
            return
        
        index = selection[0]
        lens = self.lenses[index]
        
        # Remove the lens
        self.lenses.pop(index)
        self.save_lenses()
        self.refresh_selection_list()
        
        # Clear selection info
        self.selection_info_text.config(state='normal')
        self.selection_info_text.delete(1.0, tk.END)
        self.selection_info_text.insert(1.0, "Select a lens to view details")
        self.selection_info_text.config(state='disabled')
        
        # If current lens was deleted, clear it and disable tabs
        if self.current_lens == lens:
            self.current_lens = None
            self.notebook.tab(1, state='disabled')  # Editor tab
            self.notebook.tab(2, state='disabled')  # Simulation tab
            self.notebook.tab(3, state='disabled')  # Performance tab
            self.notebook.tab(5, state='disabled')  # Export tab
        
        self.update_status(f"Lens '{lens.name}' deleted")
    
    def setup_editor_tab(self) -> None:
        """Setup the Editor tab with lens properties"""
        
        # Left panel container
        left_container = ttk.Frame(self.editor_tab)
        left_container.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        left_container.columnconfigure(0, weight=1)
        left_container.rowconfigure(1, weight=1)
        
        # Fixed header at the top
        header_frame = ttk.Frame(left_container, padding="5")
        header_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E))
        ttk.Label(header_frame, text="Optical Lens Properties", font=(FONT_FAMILY, FONT_SIZE_TITLE, 'bold')).pack(anchor=tk.W)
        
        # Scrollable content area
        scroll_container = ttk.Frame(left_container)
        scroll_container.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scroll_container.columnconfigure(0, weight=1)
        scroll_container.rowconfigure(0, weight=1)
        
        # Create canvas for scrolling
        canvas = tk.Canvas(scroll_container, bg=self.COLORS['bg'], 
                          highlightthickness=0, borderwidth=0)
        canvas.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(scroll_container, orient="vertical", command=canvas.yview)
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # Configure canvas
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Create frame inside canvas for content
        right_frame = ttk.Frame(canvas, padding="5")
        canvas_frame = canvas.create_window((0, 0), window=right_frame, anchor="nw")
        
        # Configure right_frame
        right_frame.columnconfigure(1, weight=1)
        
        # Update scroll region when frame size changes
        def configure_scroll_region(event: Optional[tk.Event] = None) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))
            # Also resize the canvas window to match canvas width
            canvas.itemconfig(canvas_frame, width=canvas.winfo_width())
        
        right_frame.bind("<Configure>", configure_scroll_region)
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas_frame, width=e.width))
        
        # Enable mouse wheel scrolling
        def on_mousewheel(event: tk.Event) -> None:
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        canvas.bind_all("<MouseWheel>", on_mousewheel)
        
        # Form fields
        row = 0
        
        ttk.Label(right_frame, text="Name:").grid(row=row, column=0, sticky=tk.W, pady=PADDING_SMALL, padx=PADDING_SMALL)
        self.name_var = tk.StringVar()
        self.name_var.trace_add('write', lambda *args: self.on_field_change())
        self.name_entry = ttk.Entry(right_frame, textvariable=self.name_var, width=40)
        self.name_entry.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=PADDING_SMALL, padx=PADDING_SMALL)
        row += 1
        
        # Separator
        ttk.Separator(right_frame, orient='horizontal').grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=PADDING_MEDIUM)
        row += 1
        
        ttk.Label(right_frame, text="Radius of Curvature 1 (mm):").grid(row=row, column=0, sticky=tk.W, pady=PADDING_SMALL, padx=PADDING_SMALL)
        self.r1_var = tk.StringVar(value="100.0")
        self.r1_var.trace_add('write', lambda *args: self.on_field_change())
        self.r1_entry = ttk.Entry(right_frame, textvariable=self.r1_var, width=40)
        self.r1_entry.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=PADDING_SMALL, padx=PADDING_SMALL)
        row += 1
        
        ttk.Label(right_frame, text="Radius of Curvature 2 (mm):").grid(row=row, column=0, sticky=tk.W, pady=PADDING_SMALL, padx=PADDING_SMALL)
        self.r2_var = tk.StringVar(value="-100.0")
        self.r2_var.trace_add('write', lambda *args: self.on_field_change())
        self.r2_entry = ttk.Entry(right_frame, textvariable=self.r2_var, width=40)
        self.r2_entry.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=PADDING_SMALL, padx=PADDING_SMALL)
        row += 1
        
        ttk.Label(right_frame, text="Center Thickness (mm):").grid(row=row, column=0, sticky=tk.W, pady=PADDING_SMALL, padx=PADDING_SMALL)
        self.thickness_var = tk.StringVar(value="5.0")
        self.thickness_var.trace_add('write', lambda *args: self.on_field_change())
        self.thickness_entry = ttk.Entry(right_frame, textvariable=self.thickness_var, width=40)
        self.thickness_entry.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=PADDING_SMALL, padx=PADDING_SMALL)
        row += 1
        
        ttk.Label(right_frame, text="Diameter (mm):").grid(row=row, column=0, sticky=tk.W, pady=PADDING_SMALL, padx=PADDING_SMALL)
        self.diameter_var = tk.StringVar(value="50.0")
        self.diameter_var.trace_add('write', lambda *args: self.on_field_change())
        self.diameter_entry = ttk.Entry(right_frame, textvariable=self.diameter_var, width=40)
        self.diameter_entry.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=PADDING_SMALL, padx=PADDING_SMALL)
        row += 1
        
        ttk.Label(right_frame, text="Refractive Index (n):").grid(row=row, column=0, sticky=tk.W, pady=PADDING_SMALL, padx=PADDING_SMALL)
        self.refr_index_var = tk.StringVar(value="1.5168")
        self.refr_index_var.trace_add('write', lambda *args: self.on_field_change())
        self.refr_index_entry = ttk.Entry(right_frame, textvariable=self.refr_index_var, width=40)
        self.refr_index_entry.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=PADDING_SMALL, padx=PADDING_SMALL)
        row += 1
        
        ttk.Label(right_frame, text="Lens Type:").grid(row=row, column=0, sticky=tk.W, pady=PADDING_SMALL, padx=PADDING_SMALL)
        self.type_var = tk.StringVar(value="Biconvex")
        self.type_var.trace_add('write', lambda *args: self.on_field_change())
        type_combo = ttk.Combobox(right_frame, textvariable=self.type_var, 
                                   values=["Biconvex", "Biconcave", "Plano-Convex", "Plano-Concave", 
                                          "Meniscus Convex", "Meniscus Concave"], 
                                   width=37, state="readonly")
        type_combo.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=PADDING_SMALL, padx=PADDING_SMALL)
        row += 1
        
        ttk.Label(right_frame, text="Material:").grid(row=row, column=0, sticky=tk.W, pady=PADDING_SMALL, padx=PADDING_SMALL)
        self.material_var = tk.StringVar(value="BK7")
        self.material_var.trace_add('write', lambda *args: self.on_field_change())
        material_combo = ttk.Combobox(right_frame, textvariable=self.material_var,
                                          values=["BK7", "Fused Silica", "SF11", "N-BK7", 
                                                  "Crown Glass", "Flint Glass", "Sapphire", "Custom"],
                                          width=37)
        material_combo.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=PADDING_SMALL, padx=PADDING_SMALL)
        row += 1
        
        # Fresnel lens section
        ttk.Separator(right_frame, orient='horizontal').grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=PADDING_MEDIUM)
        row += 1
        
        ttk.Label(right_frame, text="Fresnel Lens:", font=(FONT_FAMILY, FONT_SIZE_NORMAL, 'bold')).grid(row=row, column=0, sticky=tk.W, pady=PADDING_SMALL, padx=PADDING_SMALL)
        row += 1
        
        # Fresnel checkbox
        self.is_fresnel_var = tk.BooleanVar(value=False)
        self.is_fresnel_var.trace_add('write', lambda *args: self.on_fresnel_toggle())
        fresnel_check = ttk.Checkbutton(right_frame, text="Enable Fresnel Lens", 
                                       variable=self.is_fresnel_var)
        fresnel_check.grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=PADDING_SMALL, padx=PADDING_SMALL)
        row += 1
        
        # Groove pitch
        ttk.Label(right_frame, text="Groove Pitch (mm):").grid(row=row, column=0, sticky=tk.W, pady=PADDING_SMALL, padx=PADDING_SMALL)
        self.groove_pitch_var = tk.StringVar(value=str(DEFAULT_THICKNESS))
        self.groove_pitch_var.trace_add('write', lambda *args: self.on_field_change())
        self.groove_pitch_entry = ttk.Entry(right_frame, textvariable=self.groove_pitch_var, width=40)
        self.groove_pitch_entry.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=PADDING_SMALL, padx=PADDING_SMALL)
        self.groove_pitch_entry.config(state='disabled')  # Disabled by default
        row += 1
        
        # Number of grooves (readonly, calculated)
        ttk.Label(right_frame, text="Number of Grooves:").grid(row=row, column=0, sticky=tk.W, pady=PADDING_SMALL, padx=PADDING_SMALL)
        self.num_grooves_var = tk.StringVar(value="0")
        num_grooves_entry = ttk.Entry(right_frame, textvariable=self.num_grooves_var, width=40, state='readonly')
        num_grooves_entry.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=PADDING_SMALL, padx=PADDING_SMALL)
        row += 1
        
        # Calculated properties display
        calc_frame = ttk.LabelFrame(right_frame, text="Calculated Properties", padding="10")
        calc_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=PADDING_MEDIUM)
        
        self.focal_length_label = ttk.Label(calc_frame, text="Focal Length: Not calculated", 
                                            font=(FONT_FAMILY, FONT_SIZE_NORMAL))
        self.focal_length_label.pack(anchor=tk.W, pady=2)
        
        self.optical_power_label = ttk.Label(calc_frame, text="Optical Power: Not calculated", 
                                             font=(FONT_FAMILY, FONT_SIZE_NORMAL))
        self.optical_power_label.pack(anchor=tk.W, pady=2)
        
        # Fresnel-specific properties
        self.fresnel_efficiency_label = ttk.Label(calc_frame, text="", font=(FONT_FAMILY, FONT_SIZE_NORMAL))
        self.fresnel_efficiency_label.pack(anchor=tk.W, pady=2)
        
        self.fresnel_thickness_label = ttk.Label(calc_frame, text="", font=(FONT_FAMILY, FONT_SIZE_NORMAL))
        self.fresnel_thickness_label.pack(anchor=tk.W, pady=2)
        
        row += 1
        
        # Info panel with tips
        info_frame = ttk.LabelFrame(right_frame, text="Tips", padding="10")
        info_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=PADDING_MEDIUM)
        
        tips_text = """• Positive radius = convex (curving outward), Negative = concave (curving inward)
• R1 is front surface, R2 is back surface
• Use 'inf' or large value for flat (plano) surfaces
• Refractive index: Air=1.0, Glass~1.5-1.9, Water=1.33
• Fresnel lenses reduce thickness and weight while maintaining optical power
• Groove pitch determines the size of concentric rings"""
        ttk.Label(info_frame, text=tips_text, justify=tk.LEFT, font=('Arial', 9)).pack(anchor=tk.W)
        
        # Right panel - Lens Visualization
        viz_outer_frame = ttk.Frame(self.editor_tab)
        viz_outer_frame.grid(row=0, column=2, sticky=(tk.W, tk.E, tk.N, tk.S))
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
                         wraplength=300).pack(pady=PADDING_XLARGE)  # Fixed width for wrapping
                self.visualizer = None
        else:
            msg = "Visualization not available.\n\nInstall dependencies:\n  pip install matplotlib numpy"
            ttk.Label(self.viz_3d_frame, text=msg, justify=tk.CENTER, 
                     font=(FONT_FAMILY, FONT_SIZE_NORMAL)).pack(pady=PADDING_SMALL)
            self.visualizer = None
    
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
        
        # Update the visualization
        self.toggle_visualization_mode()
    
    def setup_simulation_tab(self) -> None:
        """Setup the Simulation tab for ray tracing and optical analysis"""
        print("="*70)
        print("DEBUG: setup_simulation_tab() called")
        print("="*70)
        
        # Configure simulation tab grid
        self.simulation_tab.columnconfigure(0, weight=1)
        self.simulation_tab.rowconfigure(0, weight=1)
        
        # Main content frame
        content_frame = ttk.Frame(self.simulation_tab, padding="10", style='Debug.TFrame')
        content_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        content_frame.columnconfigure(0, weight=1)
        content_frame.rowconfigure(1, weight=1)
        
        # Title
        title_label = ttk.Label(content_frame, text="Optical Simulation", 
                 font=(FONT_FAMILY, 14, 'bold'))
        title_label.grid(row=0, column=0, pady=PADDING_MEDIUM)
        print(f"DEBUG: Created title label: {title_label}")
        
        # Simulation canvas area
        sim_frame = ttk.LabelFrame(content_frame, text="Ray Tracing Simulation", padding="10", height=450)
        sim_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=PADDING_MEDIUM)
        sim_frame.columnconfigure(0, weight=1)
        sim_frame.rowconfigure(0, weight=1)
        sim_frame.grid_propagate(False)  # Prevent frame from shrinking to fit contents
        print(f"DEBUG: Created sim_frame: {sim_frame}")
        
        # Placeholder for simulation visualization
        if VISUALIZATION_AVAILABLE:
            try:
                # Create a 2D matplotlib canvas for ray tracing (not 3D)
                from matplotlib.figure import Figure
                from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
                
                print("DEBUG: Creating matplotlib figure...")
                self.sim_figure = Figure(figsize=(12, 6), dpi=100, facecolor=COLOR_BG_DARK)
                self.sim_figure.subplots_adjust(left=0.08, right=0.95, top=0.93, bottom=0.10)
                self.sim_ax = self.sim_figure.add_subplot(111, facecolor=COLOR_BG_DARK)
                
                # Draw initial empty plot
                self.sim_ax.set_xlim(-100, 150)
                self.sim_ax.set_ylim(-30, 30)
                self.sim_ax.axhline(y=0, color='gray', linestyle='--', linewidth=1, alpha=0.3)
                self.sim_ax.set_xlabel('Position (mm)', fontsize=FONT_SIZE_NORMAL, color=COLOR_FG)
                self.sim_ax.set_ylabel('Height (mm)', fontsize=FONT_SIZE_NORMAL, color=COLOR_FG)
                self.sim_ax.set_title('Ray Tracing Simulation\n(Select a lens and click "Run Simulation")', 
                                     fontsize=FONT_SIZE_TITLE, color=COLOR_FG)
                self.sim_ax.grid(True, alpha=0.2, color=COLOR_BG_LIGHT)
                self.sim_ax.set_aspect('equal')
                
                # Style the 2D plot
                self.sim_ax.tick_params(colors='#e0e0e0', labelsize=9)
                self.sim_ax.spines['bottom'].set_color('#3f3f3f')
                self.sim_ax.spines['top'].set_color('#3f3f3f')
                self.sim_ax.spines['left'].set_color('#3f3f3f')
                self.sim_ax.spines['right'].set_color('#3f3f3f')
                
                # Create canvas and pack it instead of grid
                print("DEBUG: Creating canvas widget...")
                self.sim_canvas = FigureCanvasTkAgg(self.sim_figure, sim_frame)
                self.sim_canvas_widget = self.sim_canvas.get_tk_widget()
                
                # Use pack to fill the entire frame
                self.sim_canvas_widget.pack(fill='both', expand=True)
                
                print(f"DEBUG: Canvas widget configured: {self.sim_canvas_widget}")
                
                # Draw the initial canvas
                print("DEBUG: Drawing canvas...")
                self.sim_canvas.draw()
                print("DEBUG: Canvas drawn successfully!")
                
                self.sim_visualizer = True  # Flag to indicate sim is available
                
            except Exception as e:
                print(f"ERROR creating simulation canvas: {e}")
                ttk.Label(sim_frame, text=f"Simulation error: {e}", 
                         wraplength=400).pack(pady=PADDING_XLARGE)  # Fixed width for wrapping
                self.sim_visualizer = None
                import traceback
                traceback.print_exc()
        else:
            msg = "Simulation not available.\n\nInstall dependencies:\n  pip install matplotlib numpy"
            ttk.Label(sim_frame, text=msg, justify=tk.CENTER, 
                     font=(FONT_FAMILY, FONT_SIZE_NORMAL)).pack(pady=PADDING_SMALL)
            self.sim_visualizer = None
        
        # Simulation controls
        controls_frame = ttk.LabelFrame(content_frame, text="Simulation Controls", padding="10")
        controls_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=PADDING_MEDIUM)
        
        # Ray parameters
        ttk.Label(controls_frame, text="Number of Rays:").grid(row=0, column=0, sticky=tk.W, padx=PADDING_SMALL, pady=PADDING_SMALL)
        self.num_rays_var = tk.StringVar(value=str(DEFAULT_NUM_RAYS))
        ttk.Entry(controls_frame, textvariable=self.num_rays_var, width=10).grid(row=0, column=1, sticky=tk.W, padx=PADDING_SMALL, pady=PADDING_SMALL)
        
        ttk.Label(controls_frame, text="Ray Angle (degrees):").grid(row=0, column=2, sticky=tk.W, padx=PADDING_SMALL, pady=PADDING_SMALL)
        self.ray_angle_var = tk.StringVar(value="0")
        ttk.Entry(controls_frame, textvariable=self.ray_angle_var, width=10).grid(row=0, column=3, sticky=tk.W, padx=PADDING_SMALL, pady=PADDING_SMALL)
        
        # Simulation buttons
        btn_frame = ttk.Frame(controls_frame)
        btn_frame.grid(row=1, column=0, columnspan=4, pady=PADDING_MEDIUM)
        
        ttk.Button(btn_frame, text="Run Simulation", 
                  command=self.run_simulation).pack(side=tk.LEFT, padx=PADDING_SMALL)
        ttk.Button(btn_frame, text="Clear Simulation", 
                  command=self.clear_simulation).pack(side=tk.LEFT, padx=PADDING_SMALL)
        
        # Aberrations Analysis section
        if ABERRATIONS_AVAILABLE:
            aberr_frame = ttk.LabelFrame(content_frame, text="Aberrations Analysis", padding="10")
            aberr_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=PADDING_MEDIUM)  # Removed N, S sticky
            aberr_frame.columnconfigure(0, weight=1)
            aberr_frame.rowconfigure(1, weight=1)
            
            # Field angle control
            angle_frame = ttk.Frame(aberr_frame)
            angle_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=PADDING_SMALL)
            
            ttk.Label(angle_frame, text="Field Angle (degrees):").pack(side=tk.LEFT, padx=PADDING_SMALL)
            self.field_angle_var = tk.StringVar(value="5.0")  # degrees
            ttk.Entry(angle_frame, textvariable=self.field_angle_var, width=10).pack(side=tk.LEFT, padx=PADDING_SMALL)
            ttk.Button(angle_frame, text="Analyze Aberrations", 
                      command=self.analyze_aberrations).pack(side=tk.LEFT, padx=PADDING_MEDIUM)
            
            # Aberrations display (scrollable text)
            aberr_scroll = ttk.Scrollbar(aberr_frame)
            aberr_scroll.grid(row=1, column=1, sticky=(tk.N, tk.S))
            
            self.aberrations_text = tk.Text(aberr_frame, height=10, width=80, 
                                           wrap=tk.NONE,
                                           bg=self.COLORS['entry_bg'],
                                           fg=self.COLORS['fg'],
                                           font=('Courier', 9),
                                           yscrollcommand=aberr_scroll.set)
            self.aberrations_text.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
            aberr_scroll.config(command=self.aberrations_text.yview)
            
            # Initial message
            self.aberrations_text.insert('1.0', "Select a lens and click 'Analyze Aberrations' to calculate optical aberrations.")
            self.aberrations_text.config(state='disabled')
        else:
            msg_frame = ttk.LabelFrame(content_frame, text="Aberrations Analysis", padding="10")
            msg_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=PADDING_MEDIUM)
            ttk.Label(msg_frame, text="Aberrations calculator module not available.", 
                     font=(FONT_FAMILY, FONT_SIZE_NORMAL)).pack(pady=PADDING_SMALL)
    
    def run_simulation(self) -> None:
        """Run ray tracing simulation for the current lens"""
        print(f"DEBUG: run_simulation called")
        print(f"DEBUG: current_lens = {self.current_lens}")
        print(f"DEBUG: RAY_TRACING_AVAILABLE = {RAY_TRACING_AVAILABLE}")
        print(f"DEBUG: VISUALIZATION_AVAILABLE = {VISUALIZATION_AVAILABLE}")
        
        if not self.current_lens:
            self.update_status("Please select or create a lens first")
            return
        
        if not RAY_TRACING_AVAILABLE:
            self.update_status("Ray tracer not available")
            return
        
        if not VISUALIZATION_AVAILABLE:
            self.update_status("Visualization (matplotlib) required for ray tracing display")
            return
        
        print(f"DEBUG: Starting ray tracing...")
        
        try:
            # Get current lens parameters from editor fields (real-time)
            # This ensures we always use the current editor values
            try:
                name = self.name_var.get().strip() or "Untitled"
                r1 = float(self.r1_var.get())
                r2 = float(self.r2_var.get())
                thickness = float(self.thickness_var.get())
                diameter = float(self.diameter_var.get())
                refractive_index = float(self.refr_index_var.get())
                lens_type = self.type_var.get()
                material = self.material_var.get().strip() or "BK7"
                
                # Create a temporary lens with current editor values
                simulation_lens = Lens(
                    name=name,
                    radius_of_curvature_1=r1,
                    radius_of_curvature_2=r2,
                    thickness=thickness,
                    diameter=diameter,
                    refractive_index=refractive_index,
                    lens_type=lens_type,
                    material=material
                )
                print(f"DEBUG: Using lens from editor: {name}, R1={r1}, R2={r2}, thickness={thickness}")
            except ValueError as e:
                self.update_status(f"Invalid lens parameters: {e}")
                return
            
            # Get simulation parameters
            try:
                num_rays = int(self.num_rays_var.get())
                num_rays = max(1, min(50, num_rays))  # Limit to 1-50 rays
            except ValueError:
                num_rays = DEFAULT_NUM_RAYS
                self.num_rays_var.set("10")
            
            try:
                ray_angle = float(self.ray_angle_var.get())
            except ValueError:
                ray_angle = 0
                self.ray_angle_var.set("0")
            
            # Create ray tracer with the lens from editor
            tracer = LensRayTracer(simulation_lens)
            
            # Trace rays based on angle
            if abs(ray_angle) < 0.1:
                # Parallel rays (collimated beam)
                print(f"DEBUG: Tracing {num_rays} parallel rays...")
                rays = tracer.trace_parallel_rays(num_rays=num_rays)
                focal_point = tracer.find_focal_point(rays)
                print(f"DEBUG: Traced {len(rays)} rays, focal_point = {focal_point}")
            else:
                # Point source rays
                print(f"DEBUG: Tracing {num_rays} point source rays at angle {ray_angle}...")
                source_x = -100.0  # 100mm before lens
                source_y = 0
                rays = tracer.trace_point_source_rays(
                    source_x, source_y, 
                    num_rays=num_rays,
                    max_angle=abs(ray_angle)
                )
                focal_point = None
                print(f"DEBUG: Traced {len(rays)} rays")
            
            # Visualize in simulation view
            print(f"DEBUG: Checking sim_visualizer: {hasattr(self, 'sim_visualizer')}")
            if hasattr(self, 'sim_visualizer') and self.sim_visualizer:
                print(f"DEBUG: Starting visualization...")
                print(f"DEBUG: Has sim_ax: {hasattr(self, 'sim_ax')}")
                print(f"DEBUG: Has sim_canvas: {hasattr(self, 'sim_canvas')}")
                # Hide info label
                if hasattr(self, 'sim_info_label'):
                    self.sim_info_label.place_forget()
                
                # Clear previous plot
                print(f"DEBUG: Clearing plot...")
                self.sim_ax.clear()
                self.sim_ax.set_facecolor('#1e1e1e')
                
                # Get lens outline
                lens_outline = tracer.get_lens_outline()
                print(f"DEBUG: Got lens outline with {len(lens_outline) if lens_outline else 0} points")
                
                # Calculate lens position - center it in view
                # Lens spans from x=0 to x=thickness, rays start at x=-50
                # We want to show rays starting well before lens
                lens_start_x = 0
                lens_end_x = self.current_lens.thickness
                
                # Draw lens at its actual position
                if lens_outline:
                    xs = [p[0] for p in lens_outline]
                    ys = [p[1] for p in lens_outline]
                    self.sim_ax.fill(xs, ys, color='lightblue', alpha=0.4, label='Lens', zorder=3)
                    self.sim_ax.plot(xs, ys, color=COLOR_ACCENT, linewidth=2.5, zorder=4)
                
                # Draw optical axis (full range)
                ray_x_coords = [p[0] for ray in rays for p in ray.path]
                x_min = min(ray_x_coords + [-60])
                x_max = max(ray_x_coords + [lens_end_x + 50])
                self.sim_ax.axhline(y=0, color='gray', linestyle='--', linewidth=1, alpha=0.4, zorder=1)
                
                # Draw rays with proper z-order
                for i, ray in enumerate(rays):
                    if len(ray.path) > 1:
                        xs = [p[0] for p in ray.path]
                        ys = [p[1] for p in ray.path]
                        
                        # Color based on ray position
                        if i == 0 or i == len(rays)-1:
                            color = '#ff4444'  # Red for edge rays
                            linewidth = 2.0
                            alpha = 0.8
                            label = 'Edge Rays' if i == 0 else None
                        elif i == len(rays)//2:
                            color = '#44ff44'  # Green for center ray
                            linewidth = 2.0
                            alpha = 0.8
                            label = 'Center Ray'
                        else:
                            color = '#ffaa44'  # Orange for other rays
                            linewidth = 1.5
                            alpha = 0.6
                            label = None
                        
                        self.sim_ax.plot(xs, ys, color=color, linewidth=linewidth, 
                                        alpha=alpha, label=label, zorder=5)
                
                # Draw focal point if found
                if focal_point:
                    fx, fy = focal_point
                    self.sim_ax.plot(fx, fy, 'go', markersize=12, markeredgecolor='white',
                                   markeredgewidth=2, label=f'Focal Point ({fx:.1f} mm)', zorder=6)
                    
                    # Draw vertical line at focal point
                    self.sim_ax.axvline(x=fx, color='green', linestyle=':', 
                                       linewidth=2, alpha=0.6, zorder=2)
                
                # Set proper axis limits to show everything
                self.sim_ax.set_xlim(x_min - 10, x_max + 10)
                y_extent = simulation_lens.diameter / 2 * 1.2
                self.sim_ax.set_ylim(-y_extent, y_extent)
                
                # Set labels and limits
                self.sim_ax.set_xlabel('Position (mm)', fontsize=FONT_SIZE_NORMAL, color=COLOR_FG)
                self.sim_ax.set_ylabel('Height (mm)', fontsize=FONT_SIZE_NORMAL, color=COLOR_FG)
                self.sim_ax.set_title(
                    f'Ray Tracing: {simulation_lens.name}\n'
                    f'{num_rays} rays, angle={ray_angle}°',
                    fontsize=FONT_SIZE_LARGE, color=COLOR_FG
                )
                self.sim_ax.legend(loc='best', fontsize=9, facecolor='#2e2e2e', 
                                  edgecolor=COLOR_BG_LIGHT, labelcolor=COLOR_FG)
                self.sim_ax.grid(True, alpha=0.3, color=COLOR_BG_LIGHT)
                self.sim_ax.set_aspect('equal')
                
                # Update tick colors
                self.sim_ax.tick_params(colors='#e0e0e0', labelsize=9)
                
                # Refresh canvas
                print(f"DEBUG: Drawing canvas...")
                self.sim_canvas.draw()
                self.sim_canvas.flush_events()
                print(f"DEBUG: Canvas drawn!")
                
                # Update status
                focal_str = f" Focal point at {focal_point[0]:.1f} mm" if focal_point else ""
                self.update_status(f"Ray tracing complete: {num_rays} rays traced.{focal_str}")
            else:
                self.update_status("Simulation visualizer not available")
        
        except Exception as e:
            self.update_status(f"Simulation error: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def analyze_aberrations(self) -> None:
        """Analyze and display lens aberrations"""
        if not self.current_lens:
            self.update_status("Please select or create a lens first")
            return
        
        if not ABERRATIONS_AVAILABLE:
            self.update_status("Aberrations calculator not available")
            return
        
        try:
            field_angle = float(self.field_angle_var.get())
        except ValueError:
            field_angle = 5.0  # degrees off-axis
            self.field_angle_var.set("5.0")
        
        try:
            # Create aberrations calculator
            calc = AberrationsCalculator(self.current_lens)
            
            # Get aberration summary
            summary = calc.get_aberration_summary(field_angle=field_angle)
            
            # Get quality analysis
            quality = analyze_lens_quality(self.current_lens, field_angle=field_angle)
            
            # Build output text
            output = summary
            output += f"\n\n{'='*65}\n"
            output += f"QUALITY ASSESSMENT\n"
            output += f"{'='*65}\n"
            output += f"Overall Quality Score: {quality['quality_score']}/100\n"
            output += f"Rating: {quality['rating']}\n"
            output += f"\nIssues Identified:\n"
            for issue in quality['issues']:
                output += f"  • {issue}\n"
            
            # Display in text widget
            self.aberrations_text.config(state='normal')
            self.aberrations_text.delete('1.0', tk.END)
            self.aberrations_text.insert('1.0', output)
            self.aberrations_text.config(state='disabled')
            
            self.update_status(f"Aberrations analyzed for '{self.current_lens.name}' - Quality: {quality['rating']}")
            
        except Exception as e:
            self.aberrations_text.config(state='normal')
            self.aberrations_text.delete('1.0', tk.END)
            self.aberrations_text.insert('1.0', f"Error analyzing aberrations:\n{str(e)}")
            self.aberrations_text.config(state='disabled')
            self.update_status(f"Error: {str(e)}")
        
    def clear_simulation(self) -> None:
        """Clear the simulation display"""
        if hasattr(self, 'sim_visualizer') and self.sim_visualizer:
            if hasattr(self, 'sim_ax'):
                self.sim_ax.clear()
                self.sim_ax.set_facecolor('#1e1e1e')
                
                # Redraw empty plot with styling
                self.sim_ax.set_xlim(-100, 150)
                self.sim_ax.set_ylim(-30, 30)
                self.sim_ax.axhline(y=0, color='gray', linestyle='--', linewidth=1, alpha=0.3)
                self.sim_ax.set_xlabel('Position (mm)', fontsize=FONT_SIZE_NORMAL, color=COLOR_FG)
                self.sim_ax.set_ylabel('Height (mm)', fontsize=FONT_SIZE_NORMAL, color=COLOR_FG)
                self.sim_ax.set_title('Ray Tracing Simulation\n(Select a lens and click "Run Simulation")', 
                                     fontsize=FONT_SIZE_TITLE, color=COLOR_FG)
                self.sim_ax.grid(True, alpha=0.2, color=COLOR_BG_LIGHT)
                self.sim_ax.set_aspect('equal')
                self.sim_ax.tick_params(colors='#e0e0e0', labelsize=9)
                
                self.sim_canvas.draw()
        
        self.update_status("Simulation cleared")
    
    def update_simulation_view(self) -> None:
        """Update the simulation tab with the current lens visualization"""
        # NOTE: This function is deprecated - we now use run_simulation() instead
        # The simulation tab uses 2D matplotlib canvas, not 3D LensVisualizer
        # Just return silently to avoid errors
        return
    
    def refresh_lens_list(self) -> None:
        """Refresh the selection list only"""
        # Also refresh selection tab list
        if hasattr(self, 'selection_listbox'):
            self.refresh_selection_list()
        
        # Also refresh comparison list
        if hasattr(self, 'comparison_listbox'):
            self.refresh_comparison_list()
        
        self.update_status(f"{len(self.lenses)} lens(es) loaded")
    
    def load_lens_to_form(self, lens: Lens) -> None:
        self._loading_lens = True  # Prevent autosave during load
        self.name_var.set(lens.name)
        self.r1_var.set(str(lens.radius_of_curvature_1))
        self.r2_var.set(str(lens.radius_of_curvature_2))
        self.thickness_var.set(str(lens.thickness))
        self.diameter_var.set(str(lens.diameter))
        self.refr_index_var.set(str(lens.refractive_index))
        self.type_var.set(lens.lens_type)
        self.material_var.set(lens.material)
        
        # Load Fresnel properties
        self.is_fresnel_var.set(getattr(lens, 'is_fresnel', False))
        self.groove_pitch_var.set(str(getattr(lens, 'groove_pitch', 1.0)))
        self.num_grooves_var.set(str(getattr(lens, 'num_grooves', 0) or 0))
        
        # Enable/disable groove pitch field based on Fresnel status
        if self.is_fresnel_var.get():
            self.groove_pitch_entry.config(state='normal')
        else:
            self.groove_pitch_entry.config(state='disabled')
        
        self.calculate_and_display_focal_length()
        self.update_3d_view()  # Update 3D visualization
        self._loading_lens = False  # Re-enable autosave
        self.update_status(f"Editing: {lens.name}")
    
    def clear_form(self) -> None:
        self._loading_lens = True  # Prevent autosave during clear
        self.name_var.set("")
        self.r1_var.set(str(DEFAULT_RADIUS_1))
        self.r2_var.set(str(DEFAULT_RADIUS_2))
        self.thickness_var.set(str(DEFAULT_THICKNESS))
        self.diameter_var.set(str(DEFAULT_DIAMETER))
        self.refr_index_var.set(str(REFRACTIVE_INDEX_BK7))
        self.type_var.set("Biconvex")
        self.material_var.set("BK7")
        self.is_fresnel_var.set(False)
        self.groove_pitch_var.set("1.0")
        self.num_grooves_var.set("0")
        self.groove_pitch_entry.config(state='disabled')
        self.current_lens = None
        
        self.focal_length_label.config(text="Focal Length: Not calculated")
        self.optical_power_label.config(text="Optical Power: Not calculated")
        self.fresnel_efficiency_label.config(text="")
        self.fresnel_thickness_label.config(text="")
        
        self._loading_lens = False  # Re-enable autosave
        self.update_status("Form cleared")
    
    def new_lens(self) -> None:
        self.clear_form()
        self.name_entry.focus()
        self.update_status("Create new lens")
    
    def on_fresnel_toggle(self) -> None:
        """Handle Fresnel lens checkbox toggle"""
        if self._loading_lens:
            return
        
        is_fresnel = self.is_fresnel_var.get()
        
        # Enable/disable groove pitch field
        if is_fresnel:
            self.groove_pitch_entry.config(state='normal')
        else:
            self.groove_pitch_entry.config(state='disabled')
            self.fresnel_efficiency_label.config(text="")
            self.fresnel_thickness_label.config(text="")
        
        # Trigger update
        self.on_field_change()
    
    def calculate_and_display_focal_length(self) -> None:
        try:
            r1 = float(self.r1_var.get())
            r2 = float(self.r2_var.get())
            thickness = float(self.thickness_var.get())
            n = float(self.refr_index_var.get())
            
            if r1 == 0 or r2 == 0:
                self.focal_length_label.config(text="Focal Length: Undefined (R cannot be 0)")
                self.optical_power_label.config(text="Optical Power: Undefined")
                return
            
            # Lensmaker's equation
            power = (n - 1) * ((1/r1) - (1/r2) + ((n - 1) * thickness) / (n * r1 * r2))
            
            if abs(power) < EPSILON:
                self.focal_length_label.config(text="Focal Length: Infinite (No optical power)")
                self.optical_power_label.config(text="Optical Power: 0.00 D")
            else:
                focal_length = 1 / power
                self.focal_length_label.config(text=f"Focal Length: {focal_length:.2f} mm")
                self.optical_power_label.config(text=f"Optical Power: {power:.4f} mm⁻¹ ({power*1000:.2f} D)")
            
            # Calculate Fresnel-specific properties if enabled
            if self.is_fresnel_var.get():
                self.calculate_and_display_fresnel_properties()
            else:
                self.fresnel_efficiency_label.config(text="")
                self.fresnel_thickness_label.config(text="")
        
        except ValueError:
            self.focal_length_label.config(text="Focal Length: Invalid input")
            self.optical_power_label.config(text="Optical Power: Invalid input")
    
    def calculate_and_display_fresnel_properties(self) -> None:
        """Calculate and display Fresnel-specific properties"""
        try:
            diameter = float(self.diameter_var.get())
            groove_pitch = float(self.groove_pitch_var.get())
            thickness = float(self.thickness_var.get())
            
            if groove_pitch <= 0:
                self.num_grooves_var.set("0")
                return
            
            # Calculate number of grooves
            num_grooves = int((diameter / 2) / groove_pitch)
            self.num_grooves_var.set(str(num_grooves))
            
            # Calculate efficiency
            base_efficiency = 0.90
            if groove_pitch < 0.5:
                efficiency_factor = 0.85
            elif groove_pitch < 1.0:
                efficiency_factor = 0.90
            else:
                efficiency_factor = 0.95
            
            efficiency = base_efficiency * efficiency_factor * 100
            self.fresnel_efficiency_label.config(
                text=f"Fresnel Efficiency: {efficiency:.1f}%"
            )
            
            # Calculate thickness reduction
            fresnel_thickness = max(1.0, groove_pitch * 2)
            reduction = ((thickness - fresnel_thickness) / thickness) * 100
            self.fresnel_thickness_label.config(
                text=f"Thickness Reduction: {reduction:.1f}% ({thickness:.1f}mm → {fresnel_thickness:.1f}mm)"
            )
            
        except ValueError:
            self.num_grooves_var.set("0")
            self.fresnel_efficiency_label.config(text="Fresnel Efficiency: Invalid input")
            self.fresnel_thickness_label.config(text="")
    
    
    def toggle_visualization_mode(self) -> None:
        """Toggle between 2D and 3D visualization"""
        self.update_3d_view()
    
    def update_3d_view(self) -> None:
        """Update the visualization with current lens parameters (2D or 3D based on mode)"""
        if not self.visualizer:
            return
        
        try:
            r1 = float(self.r1_var.get())
            r2 = float(self.r2_var.get())
            thickness = float(self.thickness_var.get())
            diameter = float(self.diameter_var.get())
            
            # Check which mode is selected
            mode = self.viz_mode_var.get() if hasattr(self, 'viz_mode_var') else "3D"
            
            if mode == "2D":
                self.visualizer.draw_lens_2d(r1, r2, thickness, diameter)
                self.update_status("2D view updated")
            else:
                self.visualizer.draw_lens(r1, r2, thickness, diameter)
                self.update_status("3D view updated")
        except ValueError:
            self.update_status("Invalid lens parameters for visualization")
        except Exception as e:
            self.update_status(f"Visualization error: {e}")
    
    def duplicate_lens(self) -> None:
        selection = self.selection_listbox.curselection()
        if not selection:
            self.update_status("Please select a lens to duplicate")
            return
        
        idx = selection[0]
        original_lens = self.lenses[idx]
        
        # Create a new lens with same properties
        new_lens = Lens(
            name=f"{original_lens.name} (Copy)",
            radius_of_curvature_1=original_lens.radius_of_curvature_1,
            radius_of_curvature_2=original_lens.radius_of_curvature_2,
            thickness=original_lens.thickness,
            diameter=original_lens.diameter,
            refractive_index=original_lens.refractive_index,
            lens_type=original_lens.lens_type,
            material=original_lens.material
        )
        
        self.lenses.append(new_lens)
        self.save_lenses()
        self.refresh_selection_list()
        
        # Select the new lens
        self.selection_listbox.selection_clear(0, tk.END)
        self.selection_listbox.selection_set(len(self.lenses) - 1)
        self.selection_listbox.see(len(self.lenses) - 1)
        self.current_lens = new_lens
        self.load_lens_to_form(new_lens)
        
        self.update_status("Lens duplicated successfully!")
    
    def on_field_change(self) -> None:
        """Called when any field changes - handles autosave and visualization update"""
        if self._loading_lens:
            return  # Don't autosave while loading
        
        # Cancel any existing timer
        if self._autosave_timer:
            self.root.after_cancel(self._autosave_timer)
        
        # Schedule autosave and update after 500ms of no changes (debounce)
        self._autosave_timer = self.root.after(500, self._perform_autosave_and_update)  # 500ms autosave delay
    
    def _perform_autosave_and_update(self) -> None:
        """Perform the actual autosave and visualization update"""
        try:
            # Update calculated properties
            self.calculate_and_display_focal_length()
            
            # Update 3D visualization
            self.update_3d_view()
            
            # Autosave if we have a current lens
            if self.current_lens:
                self.save_current_lens()
        except Exception as e:
            # Silently handle errors during autosave
            pass
    
    def save_current_lens(self) -> None:
        try:
            name = self.name_var.get().strip() or "Untitled"
            r1 = float(self.r1_var.get())
            r2 = float(self.r2_var.get())
            thickness = float(self.thickness_var.get())
            diameter = float(self.diameter_var.get())
            refractive_index = float(self.refr_index_var.get())
            lens_type = self.type_var.get()
            material = self.material_var.get().strip() or "BK7"
            is_fresnel = self.is_fresnel_var.get()
            groove_pitch = float(self.groove_pitch_var.get()) if is_fresnel else 1.0
            
            # Auto-update modified timestamp
            modified_at = datetime.now().isoformat()
            
            if self.current_lens:
                # Update existing lens
                self.current_lens.name = name
                self.current_lens.radius_of_curvature_1 = r1
                self.current_lens.radius_of_curvature_2 = r2
                self.current_lens.thickness = thickness
                self.current_lens.diameter = diameter
                self.current_lens.refractive_index = refractive_index
                self.current_lens.lens_type = lens_type
                self.current_lens.material = material
                self.current_lens.is_fresnel = is_fresnel
                self.current_lens.groove_pitch = groove_pitch
                if is_fresnel:
                    self.current_lens.calculate_num_grooves()
                else:
                    self.current_lens.num_grooves = 0
                self.current_lens.modified_at = modified_at
                message = "Lens autosaved"
            else:
                # Create new lens
                lens = Lens(name, r1, r2, thickness, diameter, refractive_index, 
                           lens_type, material, is_fresnel, groove_pitch)
                lens.modified_at = modified_at
                self.lenses.append(lens)
                self.current_lens = lens
                message = "Lens created and autosaved"
            
            # Auto-calculate focal length before saving
            if self.current_lens:
                self.current_lens.focal_length = self.current_lens.calculate_focal_length()
            
            if self.save_lenses():
                self.refresh_selection_list()
                self.update_simulation_view()
                self.update_status(message)
        
        except ValueError as e:
            # Silent fail for autosave on invalid values
            pass
        except Exception as e:
            # Silent fail for autosave errors
            pass
    
    def delete_lens(self) -> None:
        selection = self.selection_listbox.curselection()
        if not selection:
            self.update_status("Please select a lens to delete")
            return
        
        idx = selection[0]
        lens = self.lenses[idx]
        
        # Delete directly without confirmation popup
        self.lenses.pop(idx)
        self.save_lenses()
        self.clear_form()
        self.refresh_selection_list()
        self.update_status(f"Lens '{lens.name}' deleted successfully")
    
    def export_lens_to_stl(self) -> None:
        """Export the selected lens to STL file"""
        selection = self.selection_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a lens to export")
            return
        
        idx = selection[0]
        lens = self.lenses[idx]
        
        # Ask for filename
        default_filename = f"{lens.name.replace(' ', '_')}.stl"
        filename = filedialog.asksaveasfilename(
            title="Export Lens to STL",
            defaultextension=".stl",
            initialfile=default_filename,
            filetypes=[("STL files", "*.stl"), ("All files", "*.*")]
        )
        
        if not filename:
            return  # User cancelled
        
        try:
            # Export with resolution based on lens size
            resolution = MESH_RESOLUTION_MEDIUM  # Default resolution
            if lens.diameter > 100:
                resolution = MESH_RESOLUTION_HIGH  # Higher resolution for larger lenses
            elif lens.diameter < 25:
                resolution = MESH_RESOLUTION_LOW  # Lower resolution for smaller lenses
            
            num_triangles = export_lens_stl(lens, filename, resolution=resolution)
            
            messagebox.showinfo(
                "Export Successful",
                f"Lens '{lens.name}' exported successfully!\n\n"
                f"File: {os.path.basename(filename)}\n"
                f"Triangles: {num_triangles}\n"
                f"Resolution: {resolution} points"
            )
            self.update_status(f"Exported '{lens.name}' to {os.path.basename(filename)}")
        
        except Exception as e:
            messagebox.showerror(
                "Export Failed",
                f"Failed to export lens:\n{str(e)}"
            )
            self.update_status(f"Export failed: {str(e)}")
    
    def on_tab_changed(self, event: tk.Event) -> None:
        """Handle tab change events"""
        # Get the currently selected tab index
        selected_tab = self.notebook.index(self.notebook.select())
        
        # If switching to simulation tab (index 2) and we have a current lens
        if selected_tab == 2 and self.current_lens:
            self.update_simulation_view()
    
    def setup_performance_tab(self) -> None:
        """Setup the Performance Metrics Dashboard tab"""
        # Configure performance tab grid
        self.performance_tab.columnconfigure(0, weight=1)
        self.performance_tab.rowconfigure(1, weight=1)
        
        # Main content frame
        content_frame = ttk.Frame(self.performance_tab, padding="10")
        content_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        content_frame.columnconfigure(0, weight=1)
        content_frame.rowconfigure(1, weight=1)
        
        # Title
        title_label = ttk.Label(content_frame, text="Performance Metrics Dashboard", 
                                font=(FONT_FAMILY, 14, 'bold'))
        title_label.grid(row=0, column=0, pady=PADDING_MEDIUM)
        
        # Metrics display area
        metrics_frame = ttk.LabelFrame(content_frame, text="Optical Performance Metrics", padding="10")
        metrics_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=PADDING_MEDIUM)
        metrics_frame.columnconfigure(0, weight=1)
        metrics_frame.rowconfigure(0, weight=1)
        
        # Text widget for metrics display
        metrics_scroll = ttk.Scrollbar(metrics_frame)
        metrics_scroll.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        self.metrics_text = tk.Text(metrics_frame, height=20, width=80,
                                   wrap=tk.WORD,
                                   bg=self.COLORS['entry_bg'],
                                   fg=self.COLORS['fg'],
                                   font=('Courier', 10),
                                   yscrollcommand=metrics_scroll.set)
        self.metrics_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        metrics_scroll.config(command=self.metrics_text.yview)
        
        self.metrics_text.insert('1.0', "Select a lens and click 'Calculate Metrics' to view performance data.")
        self.metrics_text.config(state='disabled')
        
        # Controls
        controls_frame = ttk.LabelFrame(content_frame, text="Calculation Parameters", padding="10")
        controls_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=PADDING_MEDIUM)
        
        # Parameter inputs
        ttk.Label(controls_frame, text="Entrance Pupil Diameter (mm):").grid(row=0, column=0, sticky=tk.W, padx=PADDING_SMALL, pady=PADDING_SMALL)
        self.entrance_pupil_var = tk.StringVar(value="10.0")  # mm
        ttk.Entry(controls_frame, textvariable=self.entrance_pupil_var, width=15).grid(row=0, column=1, sticky=tk.W, padx=PADDING_SMALL, pady=PADDING_SMALL)
        
        ttk.Label(controls_frame, text="Wavelength (nm):").grid(row=0, column=2, sticky=tk.W, padx=PADDING_SMALL, pady=PADDING_SMALL)
        self.wavelength_var = tk.StringVar(value=str(int(WAVELENGTH_GREEN)))  # nm
        ttk.Entry(controls_frame, textvariable=self.wavelength_var, width=15).grid(row=0, column=3, sticky=tk.W, padx=PADDING_SMALL, pady=PADDING_SMALL)
        
        ttk.Label(controls_frame, text="Object Distance (mm):").grid(row=1, column=0, sticky=tk.W, padx=PADDING_SMALL, pady=PADDING_SMALL)
        self.object_distance_var = tk.StringVar(value="1000")  # mm
        ttk.Entry(controls_frame, textvariable=self.object_distance_var, width=15).grid(row=1, column=1, sticky=tk.W, padx=PADDING_SMALL, pady=PADDING_SMALL)
        
        ttk.Label(controls_frame, text="Sensor Size (mm):").grid(row=1, column=2, sticky=tk.W, padx=PADDING_SMALL, pady=PADDING_SMALL)
        self.sensor_size_var = tk.StringVar(value="36")  # mm (full frame)
        ttk.Entry(controls_frame, textvariable=self.sensor_size_var, width=15).grid(row=1, column=3, sticky=tk.W, padx=PADDING_SMALL, pady=PADDING_SMALL)
        
        # Calculate button
        btn_frame = ttk.Frame(controls_frame)
        btn_frame.grid(row=2, column=0, columnspan=4, pady=PADDING_MEDIUM)
        ttk.Button(btn_frame, text="Calculate Metrics", 
                  command=self.calculate_performance_metrics).pack(side=tk.LEFT, padx=PADDING_SMALL)
        ttk.Button(btn_frame, text="Export Report", 
                  command=self.export_performance_report).pack(side=tk.LEFT, padx=PADDING_SMALL)
    
    def setup_comparison_tab(self) -> None:
        """Setup the Comparison Mode tab"""
        # Configure comparison tab grid
        self.comparison_tab.columnconfigure(0, weight=1)
        self.comparison_tab.rowconfigure(1, weight=1)
        
        # Main content frame
        content_frame = ttk.Frame(self.comparison_tab, padding="10")
        content_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        content_frame.columnconfigure(0, weight=1)
        content_frame.rowconfigure(1, weight=1)
        
        # Title
        title_label = ttk.Label(content_frame, text="Lens Comparison Tool", 
                                font=(FONT_FAMILY, 14, 'bold'))
        title_label.grid(row=0, column=0, pady=PADDING_MEDIUM)
        
        # Comparison table area
        table_frame = ttk.LabelFrame(content_frame, text="Side-by-Side Comparison", padding="10")
        table_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=PADDING_MEDIUM)
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)
        
        # Text widget for comparison table
        table_scroll = ttk.Scrollbar(table_frame)
        table_scroll.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        self.comparison_text = tk.Text(table_frame, height=20, width=100,
                                      wrap=tk.NONE,
                                      bg=self.COLORS['entry_bg'],
                                      fg=self.COLORS['fg'],
                                      font=('Courier', 9),
                                      yscrollcommand=table_scroll.set)
        self.comparison_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        table_scroll.config(command=self.comparison_text.yview)
        
        self.comparison_text.insert('1.0', "Select lenses below and click 'Compare' to view side-by-side comparison.")
        self.comparison_text.config(state='disabled')
        
        # Lens selection area
        selection_frame = ttk.LabelFrame(content_frame, text="Select Lenses to Compare", padding="10")
        selection_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=PADDING_MEDIUM)
        
        # Listbox for lens selection (multiple selection)
        list_container = ttk.Frame(selection_frame)
        list_container.pack(fill=tk.BOTH, expand=True)
        
        list_scroll = ttk.Scrollbar(list_container)
        list_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.comparison_listbox = tk.Listbox(list_container,
                                            selectmode=tk.MULTIPLE,
                                            yscrollcommand=list_scroll.set,
                                            bg=self.COLORS['entry_bg'],
                                            fg=self.COLORS['fg'],
                                            selectbackground=self.COLORS['accent'],
                                            selectforeground=self.COLORS['fg'],
                                            font=(FONT_FAMILY, FONT_SIZE_NORMAL),
                                            height=6)
        self.comparison_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        list_scroll.config(command=self.comparison_listbox.yview)
        
        # Buttons
        btn_frame = ttk.Frame(selection_frame)
        btn_frame.pack(pady=PADDING_MEDIUM)
        ttk.Button(btn_frame, text="Compare Selected", 
                  command=self.compare_lenses).pack(side=tk.LEFT, padx=PADDING_SMALL)
        ttk.Button(btn_frame, text="Clear Comparison", 
                  command=self.clear_comparison).pack(side=tk.LEFT, padx=PADDING_SMALL)
        ttk.Button(btn_frame, text="Export Comparison", 
                  command=self.export_comparison).pack(side=tk.LEFT, padx=PADDING_SMALL)
        
        # Populate list with lenses
        self.refresh_comparison_list()
    
    def setup_export_tab(self) -> None:
        """Setup the Export Enhancements tab"""
        # Configure export tab grid
        self.export_tab.columnconfigure(0, weight=1)
        self.export_tab.rowconfigure(0, weight=1)
        
        # Main content frame
        content_frame = ttk.Frame(self.export_tab, padding="10")
        content_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        content_frame.columnconfigure(0, weight=1)
        
        # Title
        title_label = ttk.Label(content_frame, text="Professional Export Formats", 
                                font=(FONT_FAMILY, 14, 'bold'))
        title_label.grid(row=0, column=0, pady=PADDING_MEDIUM)
        
        # Export formats
        export_formats = [
            ("Zemax (.zmx)", "Export to Zemax OpticStudio format", self.export_to_zemax),
            ("OpticStudio (.txt)", "Export to CODE V format", self.export_to_opticstudio),
            ("PDF Technical Drawing", "Generate PDF with lens specifications", self.export_to_pdf),
            ("SVG Cross-Section", "Export as scalable vector graphics", self.export_to_svg),
            ("Prescription File (.json)", "Export lens prescription data", self.export_prescription),
            ("STL 3D Model", "Export as 3D printable model", self.export_lens_to_stl)
        ]
        
        row = 1
        for format_name, description, command in export_formats:
            frame = ttk.LabelFrame(content_frame, text=format_name, padding="15")
            frame.grid(row=row, column=0, sticky=(tk.W, tk.E), pady=PADDING_MEDIUM, padx=PADDING_XLARGE)
            
            ttk.Label(frame, text=description, font=(FONT_FAMILY, FONT_SIZE_NORMAL)).pack(side=tk.LEFT, padx=PADDING_MEDIUM)
            ttk.Button(frame, text="Export", command=command, width=15).pack(side=tk.RIGHT, padx=PADDING_MEDIUM)
            
            row += 1
        
        # Status area
        status_frame = ttk.LabelFrame(content_frame, text="Export Status", padding="10")
        status_frame.grid(row=row, column=0, sticky=(tk.W, tk.E), pady=PADDING_MEDIUM, padx=PADDING_XLARGE)
        
        self.export_status_text = tk.Text(status_frame, height=8, width=80,
                                         wrap=tk.WORD,
                                         bg=self.COLORS['entry_bg'],
                                         fg=self.COLORS['fg'],
                                         font=('Arial', 9),
                                         state='disabled')
        self.export_status_text.pack(fill=tk.BOTH, expand=True)
    
    def calculate_performance_metrics(self) -> None:
        """Calculate and display performance metrics for current lens"""
        if not self.current_lens:
            self.update_status("Please select or create a lens first")
            return
        
        try:
            from .performance_metrics import PerformanceMetrics
        except ImportError:
            try:
                from performance_metrics import PerformanceMetrics
            except ImportError:
                self.update_status("Performance metrics module not available")
                return
        
        try:
            # Get parameters
            entrance_pupil = float(self.entrance_pupil_var.get())
            wavelength = float(self.wavelength_var.get())
            object_distance = float(self.object_distance_var.get())
            sensor_size = float(self.sensor_size_var.get())
            
            # Calculate metrics
            calc = PerformanceMetrics(self.current_lens)
            metrics = calc.get_all_metrics(
                entrance_pupil_diameter=entrance_pupil,
                wavelength=wavelength,
                object_distance=object_distance,
                sensor_size=sensor_size
            )
            report = calc.format_metrics_report(metrics)
            
            # Display in text widget
            self.metrics_text.config(state='normal')
            self.metrics_text.delete('1.0', tk.END)
            self.metrics_text.insert('1.0', report)
            self.metrics_text.config(state='disabled')
            
            self.update_status(f"Metrics calculated for '{self.current_lens.name}'")
            
        except ValueError as e:
            self.update_status(f"Invalid parameter value: {e}")
        except Exception as e:
            self.update_status(f"Error calculating metrics: {e}")
    
    def export_performance_report(self) -> None:
        """Export performance metrics to file"""
        if not self.current_lens:
            self.update_status("Please select a lens first")
            return
        
        filename = filedialog.asksaveasfilename(
            title="Export Performance Report",
            defaultextension=".txt",
            initialfile=f"{self.current_lens.name}_performance.txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                content = self.metrics_text.get('1.0', tk.END)
                with open(filename, 'w') as f:
                    f.write(content)
                self.update_status(f"Report exported to {os.path.basename(filename)}")
            except Exception as e:
                self.update_status(f"Export failed: {e}")
    
    def refresh_comparison_list(self) -> None:
        """Refresh the lens list for comparison"""
        if hasattr(self, 'comparison_listbox'):
            self.comparison_listbox.delete(0, tk.END)
            for lens in self.lenses:
                self.comparison_listbox.insert(tk.END, f"{lens.name} ({lens.lens_type})")
    
    def compare_lenses(self) -> None:
        """Compare selected lenses"""
        selection = self.comparison_listbox.curselection()
        if len(selection) < 2:
            self.update_status("Please select at least 2 lenses to compare")
            return
        
        try:
            from .lens_comparator import LensComparator
        except ImportError:
            try:
                from lens_comparator import LensComparator
            except ImportError:
                self.update_status("Lens comparator module not available")
                return
        
        try:
            selected_lenses = [self.lenses[i] for i in selection]
            comparator = LensComparator()
            
            for lens in selected_lenses:
                comparator.add_lens(lens)
            
            comparison_table = comparator.get_comparison_table()
            
            # Display in text widget
            self.comparison_text.config(state='normal')
            self.comparison_text.delete('1.0', tk.END)
            self.comparison_text.insert('1.0', comparison_table)
            self.comparison_text.config(state='disabled')
            
            self.update_status(f"Compared {len(selected_lenses)} lenses")
            
        except Exception as e:
            self.update_status(f"Comparison error: {e}")
    
    def clear_comparison(self) -> None:
        """Clear comparison display"""
        self.comparison_text.config(state='normal')
        self.comparison_text.delete('1.0', tk.END)
        self.comparison_text.insert('1.0', "Select lenses below and click 'Compare' to view side-by-side comparison.")
        self.comparison_text.config(state='disabled')
        self.update_status("Comparison cleared")
    
    def export_comparison(self) -> None:
        """Export comparison table to file"""
        filename = filedialog.asksaveasfilename(
            title="Export Comparison",
            defaultextension=".txt",
            initialfile="lens_comparison.txt",
            filetypes=[("Text files", "*.txt"), ("CSV files", "*.csv"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                content = self.comparison_text.get('1.0', tk.END)
                with open(filename, 'w') as f:
                    f.write(content)
                self.update_status(f"Comparison exported to {os.path.basename(filename)}")
            except Exception as e:
                self.update_status(f"Export failed: {e}")
    
    def export_to_zemax(self) -> None:
        """Export current lens to Zemax format"""
        if not self.current_lens:
            self.update_status("Please select a lens first")
            return
        
        try:
            from .export_formats import ZemaxExporter
        except ImportError:
            try:
                from export_formats import ZemaxExporter
            except ImportError:
                self.update_status("Export module not available")
                return
        
        filename = filedialog.asksaveasfilename(
            title="Export to Zemax",
            defaultextension=".zmx",
            initialfile=f"{self.current_lens.name}.zmx",
            filetypes=[("Zemax files", "*.zmx"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                ZemaxExporter.export_lens(self.current_lens, filename)
                self._log_export_status(f"Successfully exported to Zemax format: {os.path.basename(filename)}")
                self.update_status(f"Exported to {os.path.basename(filename)}")
            except Exception as e:
                self._log_export_status(f"Error: {e}")
                self.update_status(f"Export failed: {e}")
    
    def export_to_opticstudio(self) -> None:
        """Export current lens to OpticStudio format"""
        if not self.current_lens:
            self.update_status("Please select a lens first")
            return
        
        try:
            from .export_formats import OpticStudioExporter
        except ImportError:
            try:
                from export_formats import OpticStudioExporter
            except ImportError:
                self.update_status("Export module not available")
                return
        
        filename = filedialog.asksaveasfilename(
            title="Export to OpticStudio",
            defaultextension=".txt",
            initialfile=f"{self.current_lens.name}_opticstudio.txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                OpticStudioExporter.export_lens(self.current_lens, filename)
                self._log_export_status(f"Successfully exported to OpticStudio format: {os.path.basename(filename)}")
                self.update_status(f"Exported to {os.path.basename(filename)}")
            except Exception as e:
                self._log_export_status(f"Error: {e}")
                self.update_status(f"Export failed: {e}")
    
    def export_to_pdf(self) -> None:
        """Export lens as PDF technical drawing"""
        if not self.current_lens:
            self.update_status("Please select a lens first")
            return
        
        self._log_export_status("PDF export feature coming soon...")
        self.update_status("PDF export not yet implemented")
    
    def export_to_svg(self) -> None:
        """Export lens cross-section as SVG"""
        if not self.current_lens:
            self.update_status("Please select a lens first")
            return
        
        try:
            from .export_formats import SVGExporter
        except ImportError:
            try:
                from export_formats import SVGExporter
            except ImportError:
                self.update_status("Export module not available")
                return
        
        filename = filedialog.asksaveasfilename(
            title="Export to SVG",
            defaultextension=".svg",
            initialfile=f"{self.current_lens.name}.svg",
            filetypes=[("SVG files", "*.svg"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                SVGExporter.export_lens(self.current_lens, filename)
                self._log_export_status(f"Successfully exported to SVG format: {os.path.basename(filename)}")
                self.update_status(f"Exported to {os.path.basename(filename)}")
            except Exception as e:
                self._log_export_status(f"Error: {e}")
                self.update_status(f"Export failed: {e}")
    
    def export_prescription(self) -> None:
        """Export lens prescription file"""
        if not self.current_lens:
            self.update_status("Please select a lens first")
            return
        
        filename = filedialog.asksaveasfilename(
            title="Export Prescription",
            defaultextension=".json",
            initialfile=f"{self.current_lens.name}_prescription.json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                with open(filename, 'w') as f:
                    json.dump(self.current_lens.to_dict(), f, indent=2)
                self._log_export_status(f"Successfully exported prescription: {os.path.basename(filename)}")
                self.update_status(f"Prescription exported to {os.path.basename(filename)}")
            except Exception as e:
                self._log_export_status(f"Error: {e}")
                self.update_status(f"Export failed: {e}")
    
    def _log_export_status(self, message: str) -> None:
        """Log message to export status text widget"""
        if hasattr(self, 'export_status_text'):
            self.export_status_text.config(state='normal')
            self.export_status_text.insert(tk.END, f"{datetime.now().strftime('%H:%M:%S')} - {message}\n")
            self.export_status_text.see(tk.END)
            self.export_status_text.config(state='disabled')
    
    def update_status(self, message: str) -> None:
        self.status_var.set(message)
        self.root.update_idletasks()


def main() -> None:
    root = tk.Tk()
    app = LensEditorWindow(root)
    root.mainloop()


if __name__ == "__main__":
    main()
