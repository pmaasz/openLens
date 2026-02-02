#!/usr/bin/env python3
"""
OpenLense - GUI Editor Window
Interactive graphical interface for optical lens creation and modification
"""

import tkinter as tk
from tkinter import ttk, messagebox
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
        
        # Configure dark mode
        self.setup_dark_mode()
        
        self.setup_ui()
        self.refresh_lens_list()
        
        # Keyboard shortcuts
        self.root.bind('<Control-h>', lambda e: self.toggle_left_panel())
        self.root.bind('<F1>', lambda e: self.toggle_left_panel())
    
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
    
    def load_lenses(self):
        if os.path.exists(self.storage_file):
            try:
                with open(self.storage_file, 'r') as f:
                    data = json.load(f)
                    return [Lens.from_dict(lens_data) for lens_data in data]
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load lenses: {e}")
                return []
        return []
    
    def save_lenses(self):
        try:
            with open(self.storage_file, 'w') as f:
                json.dump([lens.to_dict() for lens in self.lenses], f, indent=2)
            return True
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save lenses: {e}")
            return False
    
    def setup_ui(self):
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.columnconfigure(2, weight=1)  # Add third column for visualization
        main_frame.rowconfigure(0, weight=1)
        
        # Track visibility state
        self.left_panel_visible = True
        
        # Left panel - Lens list (collapsible)
        self.left_frame = ttk.Frame(main_frame, padding="5")
        self.left_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Header with title and toggle button
        header_frame = ttk.Frame(self.left_frame)
        header_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(header_frame, text="Optical Lenses", 
                 font=('Arial', 12, 'bold')).pack(side=tk.LEFT)
        
        # Toggle button (using Unicode arrow)
        self.toggle_btn = ttk.Button(header_frame, text="◀", width=3,
                                     command=self.toggle_left_panel)
        self.toggle_btn.pack(side=tk.RIGHT)
        
        # Add tooltip to toggle button
        ToolTip(self.toggle_btn, "Hide/Show lens list (Ctrl+H or F1)")
        
        # Container for collapsible content
        self.left_content = ttk.Frame(self.left_frame)
        self.left_content.pack(fill=tk.BOTH, expand=True)
        
        # Lens listbox with scrollbar
        list_frame = ttk.Frame(self.left_content)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.lens_listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set, 
                                        width=35, font=('Arial', 10),
                                        bg=self.COLORS['entry_bg'],
                                        fg=self.COLORS['fg'],
                                        selectbackground=self.COLORS['accent'],
                                        selectforeground=self.COLORS['fg'],
                                        highlightthickness=1,
                                        highlightcolor=self.COLORS['border'],
                                        highlightbackground=self.COLORS['border'],
                                        borderwidth=0)
        self.lens_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.lens_listbox.yview)
        
        self.lens_listbox.bind('<<ListboxSelect>>', self.on_lens_select)
        
        # Buttons for list operations
        btn_frame = ttk.Frame(self.left_content)
        btn_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(btn_frame, text="New", command=self.new_lens).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Delete", command=self.delete_lens).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Duplicate", command=self.duplicate_lens).pack(side=tk.LEFT, padx=2)
        
        # Right panel - Editor
        right_frame = ttk.Frame(main_frame, padding="5")
        right_frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S))
        right_frame.columnconfigure(1, weight=1)
        
        ttk.Label(right_frame, text="Optical Lens Properties", font=('Arial', 12, 'bold')).grid(
            row=0, column=0, columnspan=2, pady=5, sticky=tk.W)
        
        # Form fields
        row = 1
        
        ttk.Label(right_frame, text="ID:").grid(row=row, column=0, sticky=tk.W, pady=5, padx=5)
        self.id_var = tk.StringVar()
        self.id_entry = ttk.Entry(right_frame, textvariable=self.id_var, width=40,
                                  state='readonly')
        self.id_entry.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=5, padx=5)
        row += 1
        
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
        
        # Separator
        ttk.Separator(right_frame, orient='horizontal').grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)
        row += 1
        
        ttk.Label(right_frame, text="Created At:").grid(row=row, column=0, sticky=tk.W, pady=5, padx=5)
        self.created_var = tk.StringVar()
        self.created_entry = ttk.Entry(right_frame, textvariable=self.created_var, width=40, 
                                       state='readonly')
        self.created_entry.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=5, padx=5)
        row += 1
        
        ttk.Label(right_frame, text="Modified At:").grid(row=row, column=0, sticky=tk.W, pady=5, padx=5)
        self.modified_var = tk.StringVar()
        self.modified_entry = ttk.Entry(right_frame, textvariable=self.modified_var, width=40,
                                        state='readonly')
        self.modified_entry.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=5, padx=5)
        row += 1
        
        # Action buttons
        action_frame = ttk.Frame(right_frame)
        action_frame.grid(row=row, column=0, columnspan=2, pady=20)
        
        self.save_btn = ttk.Button(action_frame, text="Save", command=self.save_current_lens)
        self.save_btn.pack(side=tk.LEFT, padx=5)
        
        
        ttk.Button(action_frame, text="Calculate Focal Length", 
                   command=self.calculate_and_display_focal_length).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(action_frame, text="Auto-Update Modified", 
                   command=self.auto_update_modified).pack(side=tk.LEFT, padx=5)
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
        viz_frame = ttk.LabelFrame(main_frame, text="3D Lens Visualization", padding="5")
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
        
        # Status bar
        status_frame = ttk.Frame(main_frame)
        status_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)
        
        self.status_var = tk.StringVar(value="Ready")
        status_label = ttk.Label(status_frame, textvariable=self.status_var, 
                                 relief=tk.SUNKEN, anchor=tk.W)
        status_label.pack(fill=tk.X)
        
        self.update_status("Ready")
    
    def toggle_left_panel(self):
        """Toggle visibility of the left panel (lens list)"""
        if self.left_panel_visible:
            # Hide the panel - collapse to just the toggle button
            self.left_content.pack_forget()
            self.toggle_btn.configure(text="▶")
            # Don't set width, let it collapse naturally
            self.left_panel_visible = False
            self.update_status("Lens list hidden (Ctrl+H or F1 to show)")
        else:
            # Show the panel
            self.left_content.pack(fill=tk.BOTH, expand=True, before=self.toggle_btn.master)
            self.toggle_btn.configure(text="◀")
            self.left_panel_visible = True
            self.update_status("Lens list shown (Ctrl+H or F1 to hide)")
    
    def refresh_lens_list(self):
        self.lens_listbox.delete(0, tk.END)
        for lens in self.lenses:
            display_text = f"{lens.name} - {lens.material} ({lens.lens_type})"
            self.lens_listbox.insert(tk.END, display_text)
        
        self.update_status(f"{len(self.lenses)} lens(es) loaded")
    
    def on_lens_select(self, event):
        selection = self.lens_listbox.curselection()
        if selection:
            idx = selection[0]
            self.current_lens = self.lenses[idx]
            self.load_lens_to_form(self.current_lens)
    
    def load_lens_to_form(self, lens):
        self.id_var.set(lens.id)
        self.name_var.set(lens.name)
        self.r1_var.set(str(lens.radius_of_curvature_1))
        self.r2_var.set(str(lens.radius_of_curvature_2))
        self.thickness_var.set(str(lens.thickness))
        self.diameter_var.set(str(lens.diameter))
        self.refr_index_var.set(str(lens.refractive_index))
        self.type_var.set(lens.lens_type)
        self.material_var.set(lens.material)
        self.created_var.set(lens.created_at)
        self.modified_var.set(lens.modified_at)
        
        self.calculate_and_display_focal_length()
        self.update_3d_view()  # Update 3D visualization
        self.update_status(f"Editing: {lens.name}")
    
    def clear_form(self):
        self.id_var.set("")
        self.name_var.set("")
        self.r1_var.set("100.0")
        self.r2_var.set("-100.0")
        self.thickness_var.set("5.0")
        self.diameter_var.set("50.0")
        self.refr_index_var.set("1.5168")
        self.type_var.set("Biconvex")
        self.material_var.set("BK7")
        self.created_var.set("")
        self.modified_var.set("")
        self.current_lens = None
        
        self.focal_length_label.config(text="Focal Length: Not calculated")
        self.optical_power_label.config(text="Optical Power: Not calculated")
        
        self.lens_listbox.selection_clear(0, tk.END)
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
    
    def auto_update_modified(self):
        self.modified_var.set(datetime.now().isoformat())
        self.update_status("Modified timestamp updated")
    
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
        selection = self.lens_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a lens to duplicate.")
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
        self.refresh_lens_list()
        
        # Select the new lens
        self.lens_listbox.selection_clear(0, tk.END)
        self.lens_listbox.selection_set(len(self.lenses) - 1)
        self.lens_listbox.see(len(self.lenses) - 1)
        self.current_lens = new_lens
        self.load_lens_to_form(new_lens)
        
        messagebox.showinfo("Success", "Lens duplicated successfully!")
        self.update_status("Lens duplicated")
    
    def save_current_lens(self):
        try:
            lens_id = self.id_var.get().strip()
            name = self.name_var.get().strip() or "Untitled"
            r1 = float(self.r1_var.get())
            r2 = float(self.r2_var.get())
            thickness = float(self.thickness_var.get())
            diameter = float(self.diameter_var.get())
            refractive_index = float(self.refr_index_var.get())
            lens_type = self.type_var.get()
            material = self.material_var.get().strip() or "BK7"
            created_at = self.created_var.get().strip()
            modified_at = self.modified_var.get().strip()
            
            if self.current_lens:
                # Update existing lens
                self.current_lens.id = lens_id if lens_id else self.current_lens.id
                self.current_lens.name = name
                self.current_lens.radius_of_curvature_1 = r1
                self.current_lens.radius_of_curvature_2 = r2
                self.current_lens.thickness = thickness
                self.current_lens.diameter = diameter
                self.current_lens.refractive_index = refractive_index
                self.current_lens.lens_type = lens_type
                self.current_lens.material = material
                self.current_lens.created_at = created_at if created_at else self.current_lens.created_at
                self.current_lens.modified_at = modified_at if modified_at else datetime.now().isoformat()
                message = "Lens updated successfully!"
            else:
                # Create new lens
                lens = Lens(name, r1, r2, thickness, diameter, refractive_index, lens_type, material)
                if lens_id:
                    lens.id = lens_id
                if created_at:
                    lens.created_at = created_at
                if modified_at:
                    lens.modified_at = modified_at
                self.lenses.append(lens)
                self.current_lens = lens
                message = "Lens created successfully!"
            
            if self.save_lenses():
                self.refresh_lens_list()
                
                # Select the current lens in the list
                for idx, lens in enumerate(self.lenses):
                    if lens.id == self.current_lens.id:
                        self.lens_listbox.selection_clear(0, tk.END)
                        self.lens_listbox.selection_set(idx)
                        self.lens_listbox.see(idx)
                        break
                
                self.load_lens_to_form(self.current_lens)
                messagebox.showinfo("Success", message)
                self.update_status(message)
        
        except ValueError as e:
            messagebox.showerror("Error", "Invalid numeric value. Please check all numeric fields.")
            self.update_status("Error: Invalid input")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save lens: {e}")
            self.update_status(f"Error: {e}")
    
    def delete_lens(self):
        selection = self.lens_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a lens to delete.")
            return
        
        idx = selection[0]
        lens = self.lenses[idx]
        
        if messagebox.askyesno("Confirm Delete", f"Delete lens '{lens.name}'?"):
            self.lenses.pop(idx)
            self.save_lenses()
            self.clear_form()
            self.refresh_lens_list()
            messagebox.showinfo("Success", "Lens deleted successfully!")
            self.update_status("Lens deleted")
    
    def update_status(self, message):
        self.status_var.set(message)
        self.root.update_idletasks()


def main():
    root = tk.Tk()
    app = LensEditorWindow(root)
    root.mainloop()


if __name__ == "__main__":
    main()
