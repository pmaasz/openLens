#!/usr/bin/env python3
"""
OpenLense - GUI Editor Window
Interactive graphical interface for optical lens creation and modification
"""

import tkinter as tk
from tkinter import ttk
import json
import os
from datetime import datetime

# Try to import visualization (optional dependency)
try:
    from lens_visualizer import LensVisualizer
    VISUALIZATION_AVAILABLE = True
except ImportError:
    VISUALIZATION_AVAILABLE = False
    print("Note: matplotlib not available. 3D visualization disabled.")
    print("Install with: pip install matplotlib numpy")


class ToolTip:
    """Simple tooltip for tkinter widgets"""
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip = None
        self.widget.bind("<Enter>", self.show_tooltip)
        self.widget.bind("<Leave>", self.hide_tooltip)
    
    def show_tooltip(self, event=None):
        x, y, _, _ = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 25
        
        self.tooltip = tk.Toplevel(self.widget)
        self.tooltip.wm_overrideredirect(True)
        self.tooltip.wm_geometry(f"+{x}+{y}")
        
        label = tk.Label(self.tooltip, text=self.text, 
                        background="#252525", foreground="#e0e0e0",
                        relief=tk.SOLID, borderwidth=1, 
                        font=("Arial", 9), padx=5, pady=3)
        label.pack()
    
    def hide_tooltip(self, event=None):
        if self.tooltip:
            self.tooltip.destroy()
            self.tooltip = None


class Lens:
    def __init__(self, name="Untitled", radius_of_curvature_1=100.0, radius_of_curvature_2=-100.0,
                 thickness=5.0, diameter=50.0, refractive_index=1.5168, 
                 lens_type="Biconvex", material="BK7"):
        self.id = datetime.now().strftime("%Y%m%d%H%M%S%f")
        self.name = name
        self.radius_of_curvature_1 = radius_of_curvature_1  # R1 (front surface, mm)
        self.radius_of_curvature_2 = radius_of_curvature_2  # R2 (back surface, mm)
        self.thickness = thickness  # Center thickness (mm)
        self.diameter = diameter  # Lens diameter (mm)
        self.refractive_index = refractive_index  # Index of refraction (n)
        self.lens_type = lens_type  # Convex, Concave, Plano-Convex, etc.
        self.material = material  # Glass type
        self.created_at = datetime.now().isoformat()
        self.modified_at = datetime.now().isoformat()
    
    def to_dict(self):
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
            "created_at": self.created_at,
            "modified_at": self.modified_at
        }
    
    @classmethod
    def from_dict(cls, data):
        lens = cls(
            name=data.get("name", "Untitled"),
            radius_of_curvature_1=data.get("radius_of_curvature_1", 100.0),
            radius_of_curvature_2=data.get("radius_of_curvature_2", -100.0),
            thickness=data.get("thickness", 5.0),
            diameter=data.get("diameter", 50.0),
            refractive_index=data.get("refractive_index", 1.5168),
            lens_type=data.get("type", "Biconvex"),
            material=data.get("material", "BK7")
        )
        lens.id = data.get("id", lens.id)
        lens.created_at = data.get("created_at", lens.created_at)
        lens.modified_at = data.get("modified_at", lens.modified_at)
        return lens
    
    def calculate_focal_length(self):
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


class LensEditorWindow:
    # Dark mode color scheme
    COLORS = {
        'bg': '#1e1e1e',           # Main background
        'fg': '#e0e0e0',           # Main text
        'bg_dark': '#252525',      # Darker sections
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
    
    def __init__(self, root):
        self.root = root
        self.root.title("OpenLense - Optical Lens Editor")
        self.root.geometry("1400x800")  # Increased width for 3D view
        self.storage_file = "lenses.json"
        self.lenses = self.load_lenses()
        self.current_lens = None
        self.visualizer = None  # Will be initialized in setup_ui
        self.selected_lens_id = None
        
        # Initialize status_var early
        self.status_var = tk.StringVar(value="Welcome to OpenLense")
        
        # Configure dark mode
        self.setup_dark_mode()
        
        self.setup_ui()
        self.refresh_lens_list()
        
        # Keyboard shortcuts
        self.root.bind('<Return>', lambda e: self.save_current_lens())
        self.root.bind('<KP_Enter>', lambda e: self.save_current_lens())  # Numpad Enter
    
    def setup_dark_mode(self):
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
    
    def load_lenses(self):
        if os.path.exists(self.storage_file):
            try:
                with open(self.storage_file, 'r') as f:
                    data = json.load(f)
                    return [Lens.from_dict(lens_data) for lens_data in data]
            except Exception as e:
                print(f"Error: Failed to load lenses: {e}")
                return []
        return []
    
    def save_lenses(self):
        try:
            with open(self.storage_file, 'w') as f:
                json.dump([lens.to_dict() for lens in self.lenses], f, indent=2)
            return True
        except Exception as e:
            self.update_status(f"Error: Failed to save lenses: {e}")
            return False
    
    def setup_ui(self):
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
        
        # Create Lens Selection tab (always enabled)
        self.selection_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.selection_tab, text="Lens Selection")
        
        # Create Editor tab (disabled until lens selected)
        self.editor_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.editor_tab, text="Editor", state='disabled')
        
        # Create Simulation tab (disabled until lens selected)
        self.simulation_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.simulation_tab, text="Simulation", state='disabled')
        
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
        
        # Status bar (below tabs)
        status_frame = ttk.Frame(main_frame)
        status_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=5, padx=5)
        
        self.status_var = tk.StringVar(value="Select or create a lens to begin")
        status_label = ttk.Label(status_frame, textvariable=self.status_var, 
                                 relief=tk.SUNKEN, anchor=tk.W,
                                 font=('Arial', 9, 'bold'),
                                 padding=(5, 3))
        status_label.pack(fill=tk.X)
        
        self.update_status("Select or create a lens to begin")
    
    def setup_selection_tab(self):
        """Setup the Lens Selection tab"""
        
        # Main content frame
        content_frame = ttk.Frame(self.selection_tab, padding="20")
        content_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        content_frame.columnconfigure(0, weight=1)
        content_frame.rowconfigure(1, weight=1)
        
        # Title
        title_label = ttk.Label(content_frame, text="Lens Library", 
                               font=('Arial', 16, 'bold'))
        title_label.grid(row=0, column=0, pady=(0, 20))
        
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
                                           font=('Arial', 11),
                                           height=15,
                                           borderwidth=1,
                                           relief=tk.SOLID)
        self.selection_listbox.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 5))
        scrollbar.config(command=self.selection_listbox.yview)
        
        # Bind double-click to select lens
        self.selection_listbox.bind('<Double-Button-1>', lambda e: self.select_lens_from_list())
        
        # Lens info panel
        info_frame = ttk.LabelFrame(content_frame, text="Lens Information", padding="10")
        info_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=20)
        
        self.selection_info_text = tk.Text(info_frame, 
                                          height=9, 
                                          bg=self.COLORS['entry_bg'],
                                          fg=self.COLORS['fg'],
                                          font=('Arial', 10),
                                          wrap=tk.WORD,
                                          borderwidth=1,
                                          relief=tk.SOLID,
                                          state='disabled')
        self.selection_info_text.pack(fill=tk.BOTH, expand=True)
        
        # Bind selection change to update info
        self.selection_listbox.bind('<<ListboxSelect>>', self.update_selection_info)
        
        # Button frame
        button_frame = ttk.Frame(content_frame)
        button_frame.grid(row=3, column=0, pady=20)
        
        ttk.Button(button_frame, text="Create New Lens", 
                  command=self.create_new_lens_from_selection,
                  width=20).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(button_frame, text="Select & Edit", 
                  command=self.select_lens_from_list,
                  width=20).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(button_frame, text="Delete Lens", 
                  command=self.delete_lens_from_selection,
                  width=20).pack(side=tk.LEFT, padx=5)
        
        # Populate the list
        self.refresh_selection_list()
    
    def refresh_selection_list(self):
        """Refresh the lens selection list"""
        self.selection_listbox.delete(0, tk.END)
        for lens in self.lenses:
            display_name = f"{lens.name} ({lens.lens_type})"
            self.selection_listbox.insert(tk.END, display_name)
        
        if self.lenses:
            self.update_status(f"{len(self.lenses)} lens(es) available - Select one to edit or create new")
        else:
            self.update_status("No lenses available - Create a new lens to begin")
    
    def update_selection_info(self, event=None):
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
    
    def create_new_lens_from_selection(self):
        """Create a new lens from the selection tab"""
        # Clear the form and current lens to start fresh
        self.current_lens = None
        self.clear_form()
        
        # Enable editor and simulation tabs
        self.notebook.tab(1, state='normal')  # Editor tab
        self.notebook.tab(2, state='normal')  # Simulation tab
        
        # Switch to editor tab
        self.notebook.select(1)
        self.update_status("Ready to create new lens")
    
    def select_lens_from_list(self):
        """Select a lens from the selection list and switch to editor"""
        selection = self.selection_listbox.curselection()
        if not selection:
            self.update_status("Please select a lens first")
            return
        
        index = selection[0]
        self.current_lens = self.lenses[index]
        
        # Enable editor and simulation tabs
        self.notebook.tab(1, state='normal')  # Editor tab
        self.notebook.tab(2, state='normal')  # Simulation tab
        
        # Switch to editor tab
        self.notebook.select(1)
        
        # Update editor display
        self.refresh_lens_list()
        self.load_lens_to_form(self.current_lens)
        
        self.update_status(f"Lens selected: '{self.current_lens.name}' - Ready to edit")
    
    def delete_lens_from_selection(self):
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
        
        self.update_status(f"Lens '{lens.name}' deleted")
    
    def setup_editor_tab(self):
        """Setup the Editor tab with lens properties"""
        
        # Single panel - Editor (no lens list)
        right_frame = ttk.Frame(self.editor_tab, padding="5")
        right_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        right_frame.columnconfigure(1, weight=1)
        
        ttk.Label(right_frame, text="Optical Lens Properties", font=('Arial', 12, 'bold')).grid(
            row=0, column=0, columnspan=2, pady=5, sticky=tk.W)
        
        # Form fields
        row = 1
        
        ttk.Label(right_frame, text="Name:").grid(row=row, column=0, sticky=tk.W, pady=5, padx=5)
        self.name_var = tk.StringVar()
        self.name_entry = ttk.Entry(right_frame, textvariable=self.name_var, width=40)
        self.name_entry.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=5, padx=5)
        row += 1
        
        # Separator
        ttk.Separator(right_frame, orient='horizontal').grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)
        row += 1
        
        ttk.Label(right_frame, text="Radius of Curvature 1 (mm):").grid(row=row, column=0, sticky=tk.W, pady=5, padx=5)
        self.r1_var = tk.StringVar(value="100.0")
        self.r1_entry = ttk.Entry(right_frame, textvariable=self.r1_var, width=40)
        self.r1_entry.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=5, padx=5)
        row += 1
        
        ttk.Label(right_frame, text="Radius of Curvature 2 (mm):").grid(row=row, column=0, sticky=tk.W, pady=5, padx=5)
        self.r2_var = tk.StringVar(value="-100.0")
        self.r2_entry = ttk.Entry(right_frame, textvariable=self.r2_var, width=40)
        self.r2_entry.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=5, padx=5)
        row += 1
        
        ttk.Label(right_frame, text="Center Thickness (mm):").grid(row=row, column=0, sticky=tk.W, pady=5, padx=5)
        self.thickness_var = tk.StringVar(value="5.0")
        self.thickness_entry = ttk.Entry(right_frame, textvariable=self.thickness_var, width=40)
        self.thickness_entry.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=5, padx=5)
        row += 1
        
        ttk.Label(right_frame, text="Diameter (mm):").grid(row=row, column=0, sticky=tk.W, pady=5, padx=5)
        self.diameter_var = tk.StringVar(value="50.0")
        self.diameter_entry = ttk.Entry(right_frame, textvariable=self.diameter_var, width=40)
        self.diameter_entry.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=5, padx=5)
        row += 1
        
        ttk.Label(right_frame, text="Refractive Index (n):").grid(row=row, column=0, sticky=tk.W, pady=5, padx=5)
        self.refr_index_var = tk.StringVar(value="1.5168")
        self.refr_index_entry = ttk.Entry(right_frame, textvariable=self.refr_index_var, width=40)
        self.refr_index_entry.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=5, padx=5)
        row += 1
        
        ttk.Label(right_frame, text="Lens Type:").grid(row=row, column=0, sticky=tk.W, pady=5, padx=5)
        self.type_var = tk.StringVar(value="Biconvex")
        type_combo = ttk.Combobox(right_frame, textvariable=self.type_var, 
                                   values=["Biconvex", "Biconcave", "Plano-Convex", "Plano-Concave", 
                                          "Meniscus Convex", "Meniscus Concave"], 
                                   width=37, state="readonly")
        type_combo.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=5, padx=5)
        row += 1
        
        ttk.Label(right_frame, text="Material:").grid(row=row, column=0, sticky=tk.W, pady=5, padx=5)
        self.material_var = tk.StringVar(value="BK7")
        material_combo = ttk.Combobox(right_frame, textvariable=self.material_var,
                                          values=["BK7", "Fused Silica", "SF11", "N-BK7", 
                                                  "Crown Glass", "Flint Glass", "Sapphire", "Custom"],
                                          width=37)
        material_combo.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=5, padx=5)
        row += 1
        
        # Action buttons
        action_frame = ttk.Frame(right_frame)
        action_frame.grid(row=row, column=0, columnspan=2, pady=20)
        
        self.save_btn = ttk.Button(action_frame, text="Save", command=self.save_current_lens)
        self.save_btn.pack(side=tk.LEFT, padx=5)
        
        # Add tooltip to save button
        ToolTip(self.save_btn, "Save lens (Enter)")
        row += 1
        
        # Calculated properties display
        calc_frame = ttk.LabelFrame(right_frame, text="Calculated Properties", padding="10")
        calc_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)
        
        self.focal_length_label = ttk.Label(calc_frame, text="Focal Length: Not calculated", 
                                            font=('Arial', 10))
        self.focal_length_label.pack(anchor=tk.W, pady=2)
        
        self.optical_power_label = ttk.Label(calc_frame, text="Optical Power: Not calculated", 
                                             font=('Arial', 10))
        self.optical_power_label.pack(anchor=tk.W, pady=2)
        row += 1
        
        # Info panel with tips
        info_frame = ttk.LabelFrame(right_frame, text="Tips", padding="10")
        info_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)
        
        tips_text = """• Positive radius = convex (curving outward), Negative = concave (curving inward)
• R1 is front surface, R2 is back surface
• Use 'inf' or large value for flat (plano) surfaces
• Refractive index: Air=1.0, Glass~1.5-1.9, Water=1.33"""
        ttk.Label(info_frame, text=tips_text, justify=tk.LEFT, font=('Arial', 9)).pack(anchor=tk.W)
        
        # Right panel - 3D Visualization
        viz_frame = ttk.LabelFrame(self.editor_tab, text="3D Lens Visualization", padding="5")
        viz_frame.grid(row=0, column=2, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        if VISUALIZATION_AVAILABLE:
            try:
                self.visualizer = LensVisualizer(viz_frame, width=6, height=6)
            except Exception as e:
                ttk.Label(viz_frame, text=f"Visualization error: {e}", 
                         wraplength=300).pack(pady=20)
                self.visualizer = None
        else:
            msg = "3D visualization not available.\n\nInstall dependencies:\n  pip install matplotlib numpy"
            ttk.Label(viz_frame, text=msg, justify=tk.CENTER, 
                     font=('Arial', 10)).pack(pady=50)
            self.visualizer = None
        
        # Visualization controls
        if self.visualizer:
            viz_controls = ttk.Frame(viz_frame)
            viz_controls.pack(fill=tk.X, pady=5)
            
            ttk.Button(viz_controls, text="Update 3D View", 
                      command=self.update_3d_view).pack(side=tk.LEFT, padx=5)
    
    def setup_simulation_tab(self):
        """Setup the Simulation tab for ray tracing and optical analysis"""
        # Configure simulation tab grid
        self.simulation_tab.columnconfigure(0, weight=1)
        self.simulation_tab.rowconfigure(0, weight=1)
        
        # Main content frame
        content_frame = ttk.Frame(self.simulation_tab, padding="10")
        content_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        content_frame.columnconfigure(0, weight=1)
        content_frame.rowconfigure(1, weight=1)
        
        # Title
        ttk.Label(content_frame, text="Optical Simulation", 
                 font=('Arial', 14, 'bold')).grid(row=0, column=0, pady=10)
        
        # Simulation canvas area
        sim_frame = ttk.LabelFrame(content_frame, text="Ray Tracing Simulation", padding="10")
        sim_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)
        sim_frame.columnconfigure(0, weight=1)
        sim_frame.rowconfigure(0, weight=1)
        
        # Placeholder for simulation visualization
        if VISUALIZATION_AVAILABLE:
            try:
                # Create simulation visualizer
                self.sim_visualizer = LensVisualizer(sim_frame, width=10, height=8)
                
                # Simulation info
                info_text = """Ray Tracing Simulation
                
This tab will display:
• Light ray paths through the lens
• Focal point visualization
• Aberration analysis
• Optical path differences
• Image formation

Select a lens from the Editor tab to simulate."""
                
                info_label = ttk.Label(sim_frame, text=info_text, 
                                      justify=tk.CENTER, font=('Arial', 10))
                info_label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
                
            except Exception as e:
                ttk.Label(sim_frame, text=f"Simulation error: {e}", 
                         wraplength=400).pack(pady=20)
                self.sim_visualizer = None
        else:
            msg = "Simulation not available.\n\nInstall dependencies:\n  pip install matplotlib numpy"
            ttk.Label(sim_frame, text=msg, justify=tk.CENTER, 
                     font=('Arial', 10)).pack(pady=50)
            self.sim_visualizer = None
        
        # Simulation controls
        controls_frame = ttk.LabelFrame(content_frame, text="Simulation Controls", padding="10")
        controls_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=10)
        
        # Ray parameters
        ttk.Label(controls_frame, text="Number of Rays:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.num_rays_var = tk.StringVar(value="10")
        ttk.Entry(controls_frame, textvariable=self.num_rays_var, width=10).grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        
        ttk.Label(controls_frame, text="Ray Angle (degrees):").grid(row=0, column=2, sticky=tk.W, padx=5, pady=5)
        self.ray_angle_var = tk.StringVar(value="0")
        ttk.Entry(controls_frame, textvariable=self.ray_angle_var, width=10).grid(row=0, column=3, sticky=tk.W, padx=5, pady=5)
        
        # Simulation buttons
        btn_frame = ttk.Frame(controls_frame)
        btn_frame.grid(row=1, column=0, columnspan=4, pady=10)
        
        ttk.Button(btn_frame, text="Run Simulation", 
                  command=self.run_simulation).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Clear Simulation", 
                  command=self.clear_simulation).pack(side=tk.LEFT, padx=5)
    
    def run_simulation(self):
        """Run optical simulation for the current lens"""
        if not self.current_lens:
            self.update_status("Please select or create a lens first")
            return
        
        self.update_status(f"Running simulation for '{self.current_lens.name}'...")
        # Placeholder for actual simulation logic
        # This would implement ray tracing through the lens
        
    def clear_simulation(self):
        """Clear the simulation display"""
        if hasattr(self, 'sim_visualizer') and self.sim_visualizer:
            self.sim_visualizer.clear()
        self.update_status("Simulation cleared")
    
    def refresh_lens_list(self):
        """Refresh the selection list only"""
        # Also refresh selection tab list
        if hasattr(self, 'selection_listbox'):
            self.refresh_selection_list()
        
        self.update_status(f"{len(self.lenses)} lens(es) loaded")
    
    def load_lens_to_form(self, lens):
        self.name_var.set(lens.name)
        self.r1_var.set(str(lens.radius_of_curvature_1))
        self.r2_var.set(str(lens.radius_of_curvature_2))
        self.thickness_var.set(str(lens.thickness))
        self.diameter_var.set(str(lens.diameter))
        self.refr_index_var.set(str(lens.refractive_index))
        self.type_var.set(lens.lens_type)
        self.material_var.set(lens.material)
        
        self.calculate_and_display_focal_length()
        self.update_3d_view()  # Update 3D visualization
        self.update_status(f"Editing: {lens.name}")
    
    def clear_form(self):
        self.name_var.set("")
        self.r1_var.set("100.0")
        self.r2_var.set("-100.0")
        self.thickness_var.set("5.0")
        self.diameter_var.set("50.0")
        self.refr_index_var.set("1.5168")
        self.type_var.set("Biconvex")
        self.material_var.set("BK7")
        self.current_lens = None
        
        self.focal_length_label.config(text="Focal Length: Not calculated")
        self.optical_power_label.config(text="Optical Power: Not calculated")
        
        self.update_status("Form cleared")
    
    def new_lens(self):
        self.clear_form()
        self.name_entry.focus()
        self.update_status("Create new lens")
    
    def calculate_and_display_focal_length(self):
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
            
            if abs(power) < 1e-10:
                self.focal_length_label.config(text="Focal Length: Infinite (No optical power)")
                self.optical_power_label.config(text="Optical Power: 0.00 D")
            else:
                focal_length = 1 / power
                self.focal_length_label.config(text=f"Focal Length: {focal_length:.2f} mm")
                self.optical_power_label.config(text=f"Optical Power: {power:.4f} mm⁻¹ ({power*1000:.2f} D)")
        
        except ValueError:
            self.focal_length_label.config(text="Focal Length: Invalid input")
            self.optical_power_label.config(text="Optical Power: Invalid input")
    
    
    def update_3d_view(self):
        """Update the 3D visualization with current lens parameters"""
        if not self.visualizer:
            return
        
        try:
            r1 = float(self.r1_var.get())
            r2 = float(self.r2_var.get())
            thickness = float(self.thickness_var.get())
            diameter = float(self.diameter_var.get())
            
            self.visualizer.draw_lens(r1, r2, thickness, diameter)
            self.update_status("3D view updated")
        except ValueError:
            self.update_status("Invalid lens parameters for 3D view")
        except Exception as e:
            self.update_status(f"3D visualization error: {e}")
    
    def duplicate_lens(self):
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
    
    def save_current_lens(self):
        try:
            name = self.name_var.get().strip() or "Untitled"
            r1 = float(self.r1_var.get())
            r2 = float(self.r2_var.get())
            thickness = float(self.thickness_var.get())
            diameter = float(self.diameter_var.get())
            refractive_index = float(self.refr_index_var.get())
            lens_type = self.type_var.get()
            material = self.material_var.get().strip() or "BK7"
            
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
                self.current_lens.modified_at = modified_at
                message = "Lens updated successfully!"
            else:
                # Create new lens
                lens = Lens(name, r1, r2, thickness, diameter, refractive_index, lens_type, material)
                lens.modified_at = modified_at
                self.lenses.append(lens)
                self.current_lens = lens
                message = "Lens created successfully!"
            
            # Auto-calculate focal length before saving
            if self.current_lens:
                self.current_lens.focal_length = self.current_lens.calculate_focal_length()
            
            if self.save_lenses():
                self.refresh_selection_list()
                self.load_lens_to_form(self.current_lens)
                self.update_3d_view()
                self.update_status(message)
        
        except ValueError as e:
            self.update_status("Error: Invalid numeric value. Please check all numeric fields.")
        except Exception as e:
            self.update_status(f"Error: Failed to save lens: {e}")
    
    def delete_lens(self):
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
    
    def update_status(self, message):
        self.status_var.set(message)
        self.root.update_idletasks()


def main():
    root = tk.Tk()
    app = LensEditorWindow(root)
    root.mainloop()


if __name__ == "__main__":
    main()
