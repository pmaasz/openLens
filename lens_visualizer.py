#!/usr/bin/env python3
"""
OpenLense - 3D Lens Visualization Module
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
        self.figure = Figure(figsize=(width, height), dpi=80, facecolor=self.COLORS_3D['bg'])
        self.ax = self.figure.add_subplot(111, projection='3d', facecolor=self.COLORS_3D['bg'])
        self.canvas = FigureCanvasTkAgg(self.figure, parent_frame)
        self.canvas.get_tk_widget().pack(fill='both', expand=True)
        
        # Configure dark mode for 3D plot
        self.configure_dark_mode()
        
        # Set up the plot
        self.ax.set_xlabel('X (mm)', color=self.COLORS_3D['text'])
        self.ax.set_ylabel('Y (mm)', color=self.COLORS_3D['text'])
        self.ax.set_zlabel('Z (mm)', color=self.COLORS_3D['text'])
        self.ax.set_title('Lens 3D Cross-Section', color=self.COLORS_3D['text'])
    
    def configure_dark_mode(self):
        """Configure dark mode styling for the 3D plot"""
        # Set pane colors
        self.ax.xaxis.pane.set_facecolor(self.COLORS_3D['pane'])
        self.ax.yaxis.pane.set_facecolor(self.COLORS_3D['pane'])
        self.ax.zaxis.pane.set_facecolor(self.COLORS_3D['pane'])
        
        # Set pane edges
        self.ax.xaxis.pane.set_edgecolor(self.COLORS_3D['grid'])
        self.ax.yaxis.pane.set_edgecolor(self.COLORS_3D['grid'])
        self.ax.zaxis.pane.set_edgecolor(self.COLORS_3D['grid'])
        
        # Set grid color
        self.ax.xaxis._axinfo['grid']['color'] = self.COLORS_3D['grid']
        self.ax.yaxis._axinfo['grid']['color'] = self.COLORS_3D['grid']
        self.ax.zaxis._axinfo['grid']['color'] = self.COLORS_3D['grid']
        
        # Set tick colors
        self.ax.tick_params(axis='x', colors=self.COLORS_3D['text'])
        self.ax.tick_params(axis='y', colors=self.COLORS_3D['text'])
        self.ax.tick_params(axis='z', colors=self.COLORS_3D['text'])
        
        # Set spine colors
        self.ax.xaxis.line.set_color(self.COLORS_3D['text'])
        self.ax.yaxis.line.set_color(self.COLORS_3D['text'])
        self.ax.zaxis.line.set_color(self.COLORS_3D['text'])
        
    def calculate_surface_points(self, radius, diameter, is_front=True):
        """Calculate points for a spherical surface"""
        if abs(radius) > 10000:  # Treat as flat surface
            return None
        
        # Calculate the sagitta (height) of the spherical cap
        r = abs(radius)
        h = diameter / 2  # half-diameter
        
        if h >= r:
            h = r * 0.95  # Prevent invalid geometry
        
        # Sagitta formula: sag = r - sqrt(r^2 - h^2)
        sag = r - math.sqrt(r**2 - h**2)
        
        # Create surface points
        u = np.linspace(0, 2 * np.pi, 30)
        v = np.linspace(0, sag/r, 15)
        
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
        """Draw the complete lens in 3D with dark mode colors"""
        self.ax.clear()
        self.configure_dark_mode()  # Reapply dark mode after clear
        
        # Draw front surface (R1)
        if abs(r1) < 10000:
            points = self.calculate_surface_points(r1, diameter, is_front=True)
            if points:
                x1, y1, z1, mask1 = points
                # Apply mask
                x1_masked = np.where(mask1, x1, np.nan)
                y1_masked = np.where(mask1, y1, np.nan)
                z1_masked = np.where(mask1, z1, np.nan)
                
                self.ax.plot_surface(x1_masked, y1_masked, z1_masked, 
                                    alpha=0.7, color=self.COLORS_3D['surface_front'], 
                                    edgecolor=self.COLORS_3D['text'], linewidth=0.2)
        else:
            # Draw flat surface
            u = np.linspace(0, 2 * np.pi, 30)
            v = np.linspace(0, diameter/2, 10)
            x1 = np.outer(v, np.cos(u))
            y1 = np.outer(v, np.sin(u))
            z1 = np.zeros_like(x1)
            self.ax.plot_surface(x1, y1, z1, alpha=0.7, color=self.COLORS_3D['surface_front'],
                               edgecolor=self.COLORS_3D['text'], linewidth=0.2)
        
        # Draw back surface (R2)
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
                                    alpha=0.7, color=self.COLORS_3D['surface_back'],
                                    edgecolor=self.COLORS_3D['text'], linewidth=0.2)
        else:
            # Draw flat surface
            u = np.linspace(0, 2 * np.pi, 30)
            v = np.linspace(0, diameter/2, 10)
            x2 = np.outer(v, np.cos(u))
            y2 = np.outer(v, np.sin(u))
            z2 = np.ones_like(x2) * thickness
            self.ax.plot_surface(x2, y2, z2, alpha=0.7, color=self.COLORS_3D['surface_back'],
                               edgecolor=self.COLORS_3D['text'], linewidth=0.2)
        
        # Draw lens edge (cylindrical surface)
        theta = np.linspace(0, 2 * np.pi, 30)
        z_edge = np.linspace(0, thickness, 10)
        theta_grid, z_grid = np.meshgrid(theta, z_edge)
        x_edge = (diameter / 2) * np.cos(theta_grid)
        y_edge = (diameter / 2) * np.sin(theta_grid)
        
        self.ax.plot_surface(x_edge, y_edge, z_grid, 
                           alpha=0.3, color=self.COLORS_3D['edge'],
                           edgecolor=self.COLORS_3D['grid'], linewidth=0.1)
        
        # Draw optical axis
        axis_length = max(diameter, thickness) * 1.2
        self.ax.plot([0, 0], [0, 0], [-axis_length/3, thickness + axis_length/3],
                    color=self.COLORS_3D['axis'], linestyle='--', 
                    linewidth=2, label='Optical Axis')
        
        # Set equal aspect ratio and limits
        max_dim = max(diameter, thickness) * 0.7
        self.ax.set_xlim([-max_dim, max_dim])
        self.ax.set_ylim([-max_dim, max_dim])
        self.ax.set_zlim([-max_dim/2, thickness + max_dim/2])
        
        # Labels with dark mode colors
        self.ax.set_xlabel('X (mm)', color=self.COLORS_3D['text'])
        self.ax.set_ylabel('Y (mm)', color=self.COLORS_3D['text'])
        self.ax.set_zlabel('Z (mm)', color=self.COLORS_3D['text'])
        self.ax.set_title('Lens 3D Cross-Section', color=self.COLORS_3D['text'])
        
        # Add legend with dark mode
        legend = self.ax.legend(['Optical Axis'], loc='upper right')
        legend.get_frame().set_facecolor(self.COLORS_3D['pane'])
        legend.get_frame().set_edgecolor(self.COLORS_3D['grid'])
        for text in legend.get_texts():
            text.set_color(self.COLORS_3D['text'])
        
        # Refresh canvas
        self.canvas.draw()
    
    def clear(self):
        """Clear the visualization"""
        self.ax.clear()
        self.configure_dark_mode()
        self.ax.set_xlabel('X (mm)', color=self.COLORS_3D['text'])
        self.ax.set_ylabel('Y (mm)', color=self.COLORS_3D['text'])
        self.ax.set_zlabel('Z (mm)', color=self.COLORS_3D['text'])
        self.ax.set_title('Lens 3D Cross-Section', color=self.COLORS_3D['text'])
        self.canvas.draw()
