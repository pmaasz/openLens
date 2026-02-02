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
    """Creates 3D visualization of lens geometry"""
    
    def __init__(self, parent_frame, width=6, height=5):
        """Initialize the 3D visualization canvas"""
        self.figure = Figure(figsize=(width, height), dpi=80)
        self.ax = self.figure.add_subplot(111, projection='3d')
        self.canvas = FigureCanvasTkAgg(self.figure, parent_frame)
        self.canvas.get_tk_widget().pack(fill='both', expand=True)
        
        # Set up the plot
        self.ax.set_xlabel('X (mm)')
        self.ax.set_ylabel('Y (mm)')
        self.ax.set_zlabel('Z (mm)')
        self.ax.set_title('Lens 3D Cross-Section')
        
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
        """Draw the complete lens in 3D"""
        self.ax.clear()
        
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
                                    alpha=0.6, color='lightblue', 
                                    edgecolor='blue', linewidth=0.2)
        else:
            # Draw flat surface
            u = np.linspace(0, 2 * np.pi, 30)
            v = np.linspace(0, diameter/2, 10)
            x1 = np.outer(v, np.cos(u))
            y1 = np.outer(v, np.sin(u))
            z1 = np.zeros_like(x1)
            self.ax.plot_surface(x1, y1, z1, alpha=0.6, color='lightblue',
                               edgecolor='blue', linewidth=0.2)
        
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
                                    alpha=0.6, color='lightgreen',
                                    edgecolor='green', linewidth=0.2)
        else:
            # Draw flat surface
            u = np.linspace(0, 2 * np.pi, 30)
            v = np.linspace(0, diameter/2, 10)
            x2 = np.outer(v, np.cos(u))
            y2 = np.outer(v, np.sin(u))
            z2 = np.ones_like(x2) * thickness
            self.ax.plot_surface(x2, y2, z2, alpha=0.6, color='lightgreen',
                               edgecolor='green', linewidth=0.2)
        
        # Draw lens edge (cylindrical surface)
        theta = np.linspace(0, 2 * np.pi, 30)
        z_edge = np.linspace(0, thickness, 10)
        theta_grid, z_grid = np.meshgrid(theta, z_edge)
        x_edge = (diameter / 2) * np.cos(theta_grid)
        y_edge = (diameter / 2) * np.sin(theta_grid)
        
        self.ax.plot_surface(x_edge, y_edge, z_grid, 
                           alpha=0.3, color='gray',
                           edgecolor='darkgray', linewidth=0.1)
        
        # Draw optical axis
        axis_length = max(diameter, thickness) * 1.2
        self.ax.plot([0, 0], [0, 0], [-axis_length/3, thickness + axis_length/3],
                    'r--', linewidth=1, label='Optical Axis')
        
        # Set equal aspect ratio and limits
        max_dim = max(diameter, thickness) * 0.7
        self.ax.set_xlim([-max_dim, max_dim])
        self.ax.set_ylim([-max_dim, max_dim])
        self.ax.set_zlim([-max_dim/2, thickness + max_dim/2])
        
        # Labels
        self.ax.set_xlabel('X (mm)')
        self.ax.set_ylabel('Y (mm)')
        self.ax.set_zlabel('Z (mm)')
        self.ax.set_title('Lens 3D Cross-Section')
        
        # Add legend
        self.ax.legend(['Optical Axis'])
        
        # Refresh canvas
        self.canvas.draw()
    
    def clear(self):
        """Clear the visualization"""
        self.ax.clear()
        self.ax.set_xlabel('X (mm)')
        self.ax.set_ylabel('Y (mm)')
        self.ax.set_zlabel('Z (mm)')
        self.ax.set_title('Lens 3D Cross-Section')
        self.canvas.draw()
