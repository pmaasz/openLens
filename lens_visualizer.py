#!/usr/bin/env python3
"""
openlens - 3D Lens Visualization Module
Renders 3D cross-section of optical lenses
"""

import math
import numpy as np
import matplotlib
matplotlib.use('TkAgg')  # Use TkAgg backend for embedding in tkinter
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from mpl_toolkits.mplot3d import Axes3D


class LensVisualizer:
    """Creates 3D visualization of lens geometry with dark mode support"""
    
    # Dark mode colors for visualization
    COLORS_3D = {
        'bg': '#1e1e1e',
        'surface_front': '#4fc3f7',   # Light blue
        'surface_back': '#81c784',    # Light green
        'edge': '#757575',            # Gray
        'axis': '#ef5350',            # Red
        'text': '#e0e0e0',            # Light gray text
        'grid': '#3f3f3f',            # Dark gray grid
        'pane': '#252525'             # Darker background for panes
    }
    
    def __init__(self, parent_frame, width=6, height=5):
        """Initialize the 3D visualization canvas with dark mode"""
        # Optimize figure settings
        self.figure = Figure(figsize=(width, height), dpi=100, facecolor=self.COLORS_3D['bg'])
        self.figure.subplots_adjust(left=0.05, right=0.95, top=0.95, bottom=0.05)
        
        self.ax = self.figure.add_subplot(111, projection='3d', 
                                          facecolor=self.COLORS_3D['bg'],
                                          computed_zorder=False)
        self.canvas = FigureCanvasTkAgg(self.figure, parent_frame)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.pack(fill='both', expand=True)
        
        # Enable blitting for faster updates
        self.canvas.draw()
        self.background = self.canvas.copy_from_bbox(self.ax.bbox)
    
    def reparent_canvas(self, new_parent_frame):
        """Move the canvas to a new parent frame"""
        # Unpack from current parent
        self.canvas_widget.pack_forget()
        
        # Destroy old canvas widget
        self.canvas_widget.destroy()
        
        # Create new canvas widget with new parent
        self.canvas = FigureCanvasTkAgg(self.figure, new_parent_frame)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.pack(fill='both', expand=True)
        
        # Redraw
        self.canvas.draw()
    
    def configure_dark_mode(self):
        """Configure dark mode styling for the 3D plot"""
        # Check if this is a 3D axis before configuring panes
        if not hasattr(self.ax, 'zaxis'):
            return  # 2D axis, skip 3D-specific configuration
        
        # Set pane colors with transparency for better depth perception
        self.ax.xaxis.pane.set_facecolor(self.COLORS_3D['pane'])
        self.ax.yaxis.pane.set_facecolor(self.COLORS_3D['pane'])
        self.ax.zaxis.pane.set_facecolor(self.COLORS_3D['pane'])
        self.ax.xaxis.pane.set_alpha(0.9)
        self.ax.yaxis.pane.set_alpha(0.9)
        self.ax.zaxis.pane.set_alpha(0.9)
        
        # Set pane edges
        self.ax.xaxis.pane.set_edgecolor(self.COLORS_3D['grid'])
        self.ax.yaxis.pane.set_edgecolor(self.COLORS_3D['grid'])
        self.ax.zaxis.pane.set_edgecolor(self.COLORS_3D['grid'])
        
        # Set grid color with reduced opacity
        self.ax.xaxis._axinfo['grid']['color'] = self.COLORS_3D['grid']
        self.ax.yaxis._axinfo['grid']['color'] = self.COLORS_3D['grid']
        self.ax.zaxis._axinfo['grid']['color'] = self.COLORS_3D['grid']
        self.ax.xaxis._axinfo['grid']['linewidth'] = 0.5
        self.ax.yaxis._axinfo['grid']['linewidth'] = 0.5
        self.ax.zaxis._axinfo['grid']['linewidth'] = 0.5
        
        # Set tick colors and size
        self.ax.tick_params(axis='x', colors=self.COLORS_3D['text'], labelsize=8)
        self.ax.tick_params(axis='y', colors=self.COLORS_3D['text'], labelsize=8)
        self.ax.tick_params(axis='z', colors=self.COLORS_3D['text'], labelsize=8)
        
        # Set spine colors
        self.ax.xaxis.line.set_color(self.COLORS_3D['text'])
        self.ax.yaxis.line.set_color(self.COLORS_3D['text'])
        self.ax.zaxis.line.set_color(self.COLORS_3D['text'])
        
    def calculate_surface_points(self, radius, diameter, is_front=True):
        """Calculate points for a spherical surface with optimized resolution"""
        if abs(radius) > 10000:  # Treat as flat surface
            return None
        
        # Calculate the sagitta (height) of the spherical cap
        r = abs(radius)
        h = diameter / 2  # half-diameter
        
        if h >= r:
            h = r * 0.95  # Prevent invalid geometry
        
        # Sagitta formula: sag = r - sqrt(r^2 - h^2)
        sag = r - math.sqrt(r**2 - h**2)
        
        # Optimized resolution: fewer points for faster rendering
        # Higher resolution for smaller lenses, lower for larger
        u_res = max(20, min(40, int(60 - diameter / 5)))
        v_res = max(10, min(20, int(30 - diameter / 10)))
        
        # Create surface points
        u = np.linspace(0, 2 * np.pi, u_res)
        v = np.linspace(0, sag/r, v_res)
        
        if radius > 0:  # Convex (curving outward)
            x = r * np.outer(np.sin(np.arccos(1 - v)), np.cos(u))
            y = r * np.outer(np.sin(np.arccos(1 - v)), np.sin(u))
            z = r * (1 - np.outer(np.cos(np.arccos(1 - v)), np.ones(np.size(u))))
            if is_front:
                z = -z  # Front surface curves toward negative Z
        else:  # Concave (curving inward)
            x = r * np.outer(np.sin(np.arccos(1 - v)), np.cos(u))
            y = r * np.outer(np.sin(np.arccos(1 - v)), np.sin(u))
            z = -r * (1 - np.outer(np.cos(np.arccos(1 - v)), np.ones(np.size(u))))
            if is_front:
                z = -z
        
        # Limit to lens diameter
        mask = x**2 + y**2 <= (diameter/2)**2
        
        return x, y, z, mask
    
    def draw_lens(self, r1, r2, thickness, diameter):
        """Draw the complete lens in 3D with optimized rendering"""
        # Validate inputs
        if diameter <= 0:
            from tkinter import messagebox
            messagebox.showwarning(
                "Invalid Lens Parameters",
                "Cannot render 3D view: Lens diameter must be greater than 0.\n\n"
                f"Current diameter: {diameter} mm"
            )
            return
        
        if thickness <= 0:
            from tkinter import messagebox
            messagebox.showwarning(
                "Invalid Lens Parameters",
                "Cannot render 3D view: Lens thickness must be greater than 0.\n\n"
                f"Current thickness: {thickness} mm"
            )
            return
        
        # Recreate 3D axis if needed (in case we switched from 2D)
        if not hasattr(self.ax, 'zaxis'):
            self.figure.clear()
            self.ax = self.figure.add_subplot(111, projection='3d', 
                                              facecolor=self.COLORS_3D['bg'],
                                              computed_zorder=False)
        
        self.ax.clear()
        self.configure_dark_mode()  # Reapply dark mode after clear
        
        # Adaptive resolution for edge based on diameter
        edge_res = max(20, min(30, int(40 - diameter / 10)))
        
        # Draw front surface (R1) with improved rendering
        if abs(r1) < 10000:
            points = self.calculate_surface_points(r1, diameter, is_front=True)
            if points:
                x1, y1, z1, mask1 = points
                # Apply mask
                x1_masked = np.where(mask1, x1, np.nan)
                y1_masked = np.where(mask1, y1, np.nan)
                z1_masked = np.where(mask1, z1, np.nan)
                
                self.ax.plot_surface(x1_masked, y1_masked, z1_masked, 
                                    alpha=0.8, color=self.COLORS_3D['surface_front'], 
                                    edgecolor=self.COLORS_3D['text'], linewidth=0.15,
                                    antialiased=True, shade=True, 
                                    lightsource=self._get_light_source())
        else:
            # Draw flat surface with optimized resolution
            u = np.linspace(0, 2 * np.pi, edge_res)
            v = np.linspace(0, diameter/2, 8)
            x1 = np.outer(v, np.cos(u))
            y1 = np.outer(v, np.sin(u))
            z1 = np.zeros_like(x1)
            self.ax.plot_surface(x1, y1, z1, alpha=0.8, color=self.COLORS_3D['surface_front'],
                               edgecolor=self.COLORS_3D['text'], linewidth=0.15,
                               antialiased=True, shade=True)
        
        # Draw back surface (R2) with improved rendering
        if abs(r2) < 10000:
            points = self.calculate_surface_points(r2, diameter, is_front=False)
            if points:
                x2, y2, z2, mask2 = points
                z2 = z2 + thickness  # Offset by lens thickness
                
                # Apply mask
                x2_masked = np.where(mask2, x2, np.nan)
                y2_masked = np.where(mask2, y2, np.nan)
                z2_masked = np.where(mask2, z2, np.nan)
                
                self.ax.plot_surface(x2_masked, y2_masked, z2_masked, 
                                    alpha=0.8, color=self.COLORS_3D['surface_back'],
                                    edgecolor=self.COLORS_3D['text'], linewidth=0.15,
                                    antialiased=True, shade=True,
                                    lightsource=self._get_light_source())
        else:
            # Draw flat surface with optimized resolution
            u = np.linspace(0, 2 * np.pi, edge_res)
            v = np.linspace(0, diameter/2, 8)
            x2 = np.outer(v, np.cos(u))
            y2 = np.outer(v, np.sin(u))
            z2 = np.ones_like(x2) * thickness
            self.ax.plot_surface(x2, y2, z2, alpha=0.8, color=self.COLORS_3D['surface_back'],
                               edgecolor=self.COLORS_3D['text'], linewidth=0.15,
                               antialiased=True, shade=True)
        
        # Draw lens edge (cylindrical surface) with optimized resolution
        theta = np.linspace(0, 2 * np.pi, edge_res)
        z_edge = np.linspace(0, thickness, 8)
        theta_grid, z_grid = np.meshgrid(theta, z_edge)
        x_edge = (diameter / 2) * np.cos(theta_grid)
        y_edge = (diameter / 2) * np.sin(theta_grid)
        
        self.ax.plot_surface(x_edge, y_edge, z_grid, 
                           alpha=0.4, color=self.COLORS_3D['edge'],
                           edgecolor=self.COLORS_3D['grid'], linewidth=0.1,
                           antialiased=True)
        
        # Draw optical axis with improved visibility
        axis_length = max(diameter, thickness) * 1.2
        self.ax.plot([0, 0], [0, 0], [-axis_length/3, thickness + axis_length/3],
                    color=self.COLORS_3D['axis'], linestyle='--', 
                    linewidth=2.5, alpha=0.9, label='Optical Axis')
        
        # Set equal aspect ratio and optimized limits
        max_dim = max(diameter, thickness) * 0.7
        self.ax.set_xlim([-max_dim, max_dim])
        self.ax.set_ylim([-max_dim, max_dim])
        self.ax.set_zlim([-max_dim/2, thickness + max_dim/2])
        
        # Reduce number of tick marks for cleaner look
        self.ax.locator_params(nbins=5)
        
        # Labels with dark mode colors and optimized font
        self.ax.set_xlabel('X (mm)', color=self.COLORS_3D['text'], fontsize=9)
        self.ax.set_ylabel('Y (mm)', color=self.COLORS_3D['text'], fontsize=9)
        self.ax.set_zlabel('Z (mm)', color=self.COLORS_3D['text'], fontsize=9)
        self.ax.set_title('Lens 3D Cross-Section', color=self.COLORS_3D['text'],
                         fontsize=11, pad=10)
        
        # Add legend with dark mode and compact style
        legend = self.ax.legend(['Optical Axis'], loc='upper right', 
                               fontsize=8, framealpha=0.9)
        legend.get_frame().set_facecolor(self.COLORS_3D['pane'])
        legend.get_frame().set_edgecolor(self.COLORS_3D['grid'])
        for text in legend.get_texts():
            text.set_color(self.COLORS_3D['text'])
        
        # Refresh canvas with optimization
        self.canvas.draw_idle()  # Use idle draw for better performance
    
    def _get_light_source(self):
        """Create optimized light source for better 3D rendering"""
        from matplotlib.colors import LightSource
        return LightSource(azdeg=315, altdeg=45)
    
    def draw_lens_2d(self, r1, r2, thickness, diameter):
        """Draw the lens in 2D side view (cross-section)"""
        # Validate inputs
        if diameter <= 0:
            from tkinter import messagebox
            messagebox.showwarning(
                "Invalid Lens Parameters",
                "Cannot render 2D view: Lens diameter must be greater than 0.\n\n"
                f"Current diameter: {diameter} mm"
            )
            return
        
        if thickness <= 0:
            from tkinter import messagebox
            messagebox.showwarning(
                "Invalid Lens Parameters",
                "Cannot render 2D view: Lens thickness must be greater than 0.\n\n"
                f"Current thickness: {thickness} mm"
            )
            return
        
        # Clear and reconfigure for 2D
        self.figure.clear()
        self.ax = self.figure.add_subplot(111, facecolor=self.COLORS_3D['bg'])
        
        # Configure dark mode for 2D
        self.ax.set_facecolor(self.COLORS_3D['bg'])
        self.ax.spines['bottom'].set_color(self.COLORS_3D['text'])
        self.ax.spines['top'].set_color(self.COLORS_3D['text'])
        self.ax.spines['left'].set_color(self.COLORS_3D['text'])
        self.ax.spines['right'].set_color(self.COLORS_3D['text'])
        self.ax.tick_params(axis='x', colors=self.COLORS_3D['text'], labelsize=8)
        self.ax.tick_params(axis='y', colors=self.COLORS_3D['text'], labelsize=8)
        self.ax.xaxis.label.set_color(self.COLORS_3D['text'])
        self.ax.yaxis.label.set_color(self.COLORS_3D['text'])
        self.ax.title.set_color(self.COLORS_3D['text'])
        self.ax.grid(True, color=self.COLORS_3D['grid'], linestyle='--', linewidth=0.5, alpha=0.3)
        
        # Calculate lens profile
        y_max = diameter / 2
        y = np.linspace(-y_max, y_max, 200)
        
        # Front surface (R1)
        if abs(r1) < 10000:
            # Calculate sag for front surface
            r1_abs = abs(r1)
            valid_mask = y**2 <= r1_abs**2
            y_valid = y[valid_mask]
            
            if r1 > 0:  # Convex
                x1 = -r1_abs + np.sqrt(r1_abs**2 - y_valid**2)
            else:  # Concave
                x1 = r1_abs - np.sqrt(r1_abs**2 - y_valid**2)
        else:
            # Flat surface
            y_valid = y
            x1 = np.zeros_like(y_valid)
        
        # Back surface (R2)
        if abs(r2) < 10000:
            r2_abs = abs(r2)
            valid_mask2 = y**2 <= r2_abs**2
            y_valid2 = y[valid_mask2]
            
            if r2 > 0:  # Convex
                x2 = thickness + r2_abs - np.sqrt(r2_abs**2 - y_valid2**2)
            else:  # Concave
                x2 = thickness - r2_abs + np.sqrt(r2_abs**2 - y_valid2**2)
        else:
            # Flat surface
            y_valid2 = y
            x2 = np.full_like(y_valid2, thickness)
        
        # Draw lens surfaces
        self.ax.plot(x1, y_valid, color=self.COLORS_3D['surface_front'], linewidth=2.5, label='Front Surface')
        self.ax.plot(x2, y_valid2, color=self.COLORS_3D['surface_back'], linewidth=2.5, label='Back Surface')
        
        # Draw edges
        if len(x1) > 0 and len(x2) > 0:
            # Top edge
            self.ax.plot([x1[0], x2[0]], [y_valid[0], y_valid2[0]], 
                        color=self.COLORS_3D['edge'], linewidth=1.5)
            # Bottom edge
            self.ax.plot([x1[-1], x2[-1]], [y_valid[-1], y_valid2[-1]], 
                        color=self.COLORS_3D['edge'], linewidth=1.5)
        
        # Draw optical axis
        x_min = min(x1.min() if len(x1) > 0 else 0, x2.min() if len(x2) > 0 else thickness)
        x_max = max(x1.max() if len(x1) > 0 else 0, x2.max() if len(x2) > 0 else thickness)
        margin = (x_max - x_min) * 0.2
        self.ax.axhline(0, color=self.COLORS_3D['axis'], linestyle='--', linewidth=1.5, 
                       alpha=0.7, label='Optical Axis')
        
        # Labels and styling
        self.ax.set_xlabel('Z (mm)', color=self.COLORS_3D['text'], fontsize=10)
        self.ax.set_ylabel('Y (mm)', color=self.COLORS_3D['text'], fontsize=10)
        self.ax.set_title('Lens 2D Cross-Section', color=self.COLORS_3D['text'], 
                         fontsize=11, pad=10)
        self.ax.set_aspect('equal')
        
        # Set limits with margin
        self.ax.set_xlim(x_min - margin, x_max + margin)
        
        # Ensure ylim values are not identical (prevents matplotlib warning)
        if y_max > 0:
            self.ax.set_ylim(-y_max * 1.2, y_max * 1.2)
        else:
            # Fallback to small default range if y_max is 0
            self.ax.set_ylim(-1, 1)
        
        # Legend
        legend = self.ax.legend(loc='upper right', fontsize=8, framealpha=0.9)
        legend.get_frame().set_facecolor(self.COLORS_3D['pane'])
        legend.get_frame().set_edgecolor(self.COLORS_3D['grid'])
        for text in legend.get_texts():
            text.set_color(self.COLORS_3D['text'])
        
        self.canvas.draw_idle()
    
    def clear(self):
        """Clear the visualization with optimizations"""
        self.ax.clear()
        self.configure_dark_mode()
        self.ax.view_init(elev=20, azim=45)
        self.ax.set_xlabel('X (mm)', color=self.COLORS_3D['text'], fontsize=9)
        self.ax.set_ylabel('Y (mm)', color=self.COLORS_3D['text'], fontsize=9)
        self.ax.set_zlabel('Z (mm)', color=self.COLORS_3D['text'], fontsize=9)
        self.ax.set_title('Lens 3D Cross-Section', color=self.COLORS_3D['text'],
                         fontsize=11, pad=10)
        self.canvas.draw_idle()
