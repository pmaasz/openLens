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
    
    def __init__(self, parent_frame, width=6, height=5):
        """Initialize the 3D visualization canvas with dark mode"""
        self._radius_change_callback = None
        self._current_lens_params = {}
        
        # Optimize figure settings
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
        
        # Create TWO overlaid 3D axes:
        # 1. ax_coords: Fixed coordinate system (background)
        # 2. ax_lens: Rotatable lens geometry (foreground)
        
        # Fixed coordinate system (background)
        self.ax_coords = self.figure.add_subplot(111, projection='3d', 
                                                  facecolor=self.COLORS_3D['bg'],
                                                  computed_zorder=False)
        self.ax_coords.view_init(elev=20, azim=45)
        self.ax_coords.mouse_init()
        
        # Rotatable lens geometry (foreground)
        self.ax_lens = self.figure.add_subplot(111, projection='3d',
                                                facecolor='none',  # Transparent background
                                                computed_zorder=False)
        self.ax_lens.set_position(self.ax_coords.get_position())  # Same position
        self.ax_lens.patch.set_alpha(0)  # Transparent patch
        self.ax_lens.view_init(elev=20, azim=45)  # Start with same view
        
        # Show axes for zoom/pan interaction
        self.ax_lens.set_axis_on()
        self.ax_lens.mouse_init()
        
        # Keep reference to main axis for compatibility (use lens axis)
        self.ax = self.ax_lens
        
        self.canvas = FigureCanvasTkAgg(self.figure, parent_frame)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.pack(fill='both', expand=True)
        
        # Enable blitting for faster updates
        self.canvas.draw()
        self.background = self.canvas.copy_from_bbox(self.ax.bbox)
        
        # Mouse drag interaction
        self._drag_active = False
        self._drag_surface = None
        self._drag_start_y = None
        self._drag_start_radius = None
        self._highlight_line = None
        self.canvas.mpl_connect('button_press_event', self._on_click)
        self.canvas.mpl_connect('button_release_event', self._on_release)
        self.canvas.mpl_connect('motion_notify_event', self._on_motion)
        self.canvas.mpl_connect('motion_notify_event', self._on_hover)
    
    def set_radius_change_callback(self, callback):
        """Set callback for radius changes (callback(radius1, radius2))"""
        self._radius_change_callback = callback
    
    def _on_click(self, event):
        """Handle mouse click on canvas"""
        if event.inaxes != self.ax:
            return
        if not hasattr(self, '_current_lens_params'):
            return
        
        r1 = self._current_lens_params.get('r1', 0)
        r2 = self._current_lens_params.get('r2', 0)
        thickness = self._current_lens_params.get('thickness', 5)
        diameter = self._current_lens_params.get('diameter', 50)
        
        x_lim = self.ax.get_xlim()
        y_lim = self.ax.get_ylim()
        x_click = event.xdata
        y_click = event.ydata
        
        x_front = 0
        x_back = thickness
        
        tol = diameter / 4
        
        if abs(x_click - x_front) < tol and abs(y_click) < diameter / 2:
            self._drag_active = True
            self._drag_surface = 'r1'
            self._drag_start_y = y_click
            self._drag_start_radius = r1
        elif abs(x_click - x_back) < tol and abs(y_click) < diameter / 2:
            self._drag_active = True
            self._drag_surface = 'r2'
            self._drag_start_y = y_click
            self._drag_start_radius = r2
        else:
            self._drag_active = False
        self._update_highlight(None)
    
    def _on_hover(self, event):
        """Show cursor feedback when hovering over draggable surfaces"""
        if event.inaxes != self.ax or not hasattr(self, '_current_lens_params'):
            self._update_highlight(None)
            return
        
        thickness = self._current_lens_params.get('thickness', 5)
        diameter = self._current_lens_params.get('diameter', 50)
        x_click = event.xdata
        y_click = event.ydata
        
        x_front = 0
        x_back = thickness
        tol = diameter / 3
        
        if abs(x_click - x_front) < tol and abs(y_click) < diameter / 2:
            self._update_highlight('r1')
            self.canvas.widget.set_cursor(1)  # pointer
        elif abs(x_click - x_back) < tol and abs(y_click) < diameter / 2:
            self._update_highlight('r2')
            self.canvas.widget.set_cursor(1)
        else:
            self._update_highlight(None)
            self.canvas.widget.set_cursor(0)  # default
    
    def _update_highlight(self, surface):
        """Update visual highlight of draggable surface"""
        if hasattr(self, '_highlight_line'):
            try:
                self._highlight_line.remove()
            except:
                pass
        
        if not surface or not hasattr(self, '_current_lens_params'):
            self._highlight_line = None
            return
        
        thickness = self._current_lens_params.get('thickness', 5)
        diameter = self._current_lens_params.get('diameter', 50)
        
        x = 0 if surface == 'r1' else thickness
        self._highlight_line = self.ax.axvline(x, color='yellow', linewidth=3, alpha=0.7, zorder=10)
    
    def _on_motion(self, event):
        """Handle mouse drag"""
        if not self._drag_active or event.inaxes != self.ax:
            return
        
        r1 = self._current_lens_params.get('r1', 100)
        r2 = self._current_lens_params.get('r2', -100)
        diameter = self._current_lens_params.get('diameter', 50)
        
        dy = event.ydata - self._drag_start_y
        
        # Scale factor - full diameter drag = 200mm radius change
        scale = diameter * 4
        
        if self._drag_surface == 'r1':
            new_r = r1 + dy * scale
            if abs(new_r) < 1:
                new_r = 1 if new_r > 0 else -1
            new_r = max(-500, min(500, new_r))
            self._current_lens_params['r1'] = new_r
        else:
            new_r = r2 - dy * scale
            if abs(new_r) < 1:
                new_r = 1 if new_r > 0 else -1
            new_r = max(-500, min(500, new_r))
            self._current_lens_params['r2'] = new_r
        
        if self._radius_change_callback:
            self._radius_change_callback(
                self._current_lens_params.get('r1', 100),
                self._current_lens_params.get('r2', -100)
            )
    
    def _on_release(self, event):
        """Handle mouse release"""
        if self._drag_active and self._radius_change_callback:
            self._radius_change_callback(
                self._current_lens_params.get('r1', 100),
                self._current_lens_params.get('r2', -100)
            )
        self._drag_active = False
    
    def _fix_axis_labels(self, event):
        """No longer needed - coordinate axes are separate and fixed"""
        pass
    
    def reparent_canvas(self, new_parent_frame):
        """Move the canvas to a new parent frame"""
        try:
            self.canvas_widget.pack_forget()
        except:
            pass
        
        try:
            self.canvas_widget.destroy()
        except:
            pass
        
        self.canvas = FigureCanvasTkAgg(self.figure, new_parent_frame)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.pack(fill='both', expand=True)
        
        self.canvas.draw_idle()
    
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
    
    def _configure_coordinate_system(self, diameter, thickness):
        """Configure the fixed coordinate system (ax_coords)"""
        # Apply dark mode to coordinate axis
        self.ax_coords.xaxis.pane.set_facecolor(self.COLORS_3D['pane'])
        self.ax_coords.yaxis.pane.set_facecolor(self.COLORS_3D['pane'])
        self.ax_coords.zaxis.pane.set_facecolor(self.COLORS_3D['pane'])
        self.ax_coords.xaxis.pane.set_alpha(0.9)
        self.ax_coords.yaxis.pane.set_alpha(0.9)
        self.ax_coords.zaxis.pane.set_alpha(0.9)
        
        self.ax_coords.xaxis.pane.set_edgecolor(self.COLORS_3D['grid'])
        self.ax_coords.yaxis.pane.set_edgecolor(self.COLORS_3D['grid'])
        self.ax_coords.zaxis.pane.set_edgecolor(self.COLORS_3D['grid'])
        
        # Grid styling
        self.ax_coords.xaxis._axinfo['grid']['color'] = self.COLORS_3D['grid']
        self.ax_coords.yaxis._axinfo['grid']['color'] = self.COLORS_3D['grid']
        self.ax_coords.zaxis._axinfo['grid']['color'] = self.COLORS_3D['grid']
        self.ax_coords.xaxis._axinfo['grid']['linewidth'] = 0.5
        self.ax_coords.yaxis._axinfo['grid']['linewidth'] = 0.5
        self.ax_coords.zaxis._axinfo['grid']['linewidth'] = 0.5
        
        # Tick styling
        self.ax_coords.tick_params(axis='x', colors=self.COLORS_3D['text'], labelsize=8)
        self.ax_coords.tick_params(axis='y', colors=self.COLORS_3D['text'], labelsize=8)
        self.ax_coords.tick_params(axis='z', colors=self.COLORS_3D['text'], labelsize=8)
        
        # Spine colors
        self.ax_coords.xaxis.line.set_color(self.COLORS_3D['text'])
        self.ax_coords.yaxis.line.set_color(self.COLORS_3D['text'])
        self.ax_coords.zaxis.line.set_color(self.COLORS_3D['text'])
        
        # Set limits (same as lens will have)
        max_dim = max(diameter, thickness) * 0.7
        self.ax_coords.set_xlim([-max_dim, max_dim])
        self.ax_coords.set_ylim([-max_dim, max_dim])
        self.ax_coords.set_zlim([-max_dim/2, thickness + max_dim/2])
        
        # Reduce number of tick marks
        self.ax_coords.locator_params(nbins=5)
        
        # Labels
        self.ax_coords.set_xlabel('X (mm)', color=self.COLORS_3D['text'], fontsize=9)
        self.ax_coords.set_ylabel('Y (mm)', color=self.COLORS_3D['text'], fontsize=9)
        self.ax_coords.set_zlabel('Z (mm)', color=self.COLORS_3D['text'], fontsize=9)
        
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
    
    def draw_system(self, system):
        """Draw a multi-element optical system in 3D"""
        if not system or not system.elements:
            self.clear()
            return

        # Check if axes exist, recreate if needed (similar to draw_lens)
        needs_recreate = (not hasattr(self, 'ax_lens') or not hasattr(self, 'ax_coords') or
                          not hasattr(self.ax_lens, 'zaxis') or not hasattr(self.ax_coords, 'zaxis') or
                          self.ax_lens not in self.figure.axes or self.ax_coords not in self.figure.axes)
        
        if needs_recreate:
            self.figure.clear()
            self.ax_coords = self.figure.add_subplot(111, projection='3d',
                                                      facecolor=self.COLORS_3D['bg'],
                                                      computed_zorder=False)
            self.ax_coords.view_init(elev=20, azim=45)
            self.ax_coords.mouse_init()
            
            self.ax_lens = self.figure.add_subplot(111, projection='3d',
                                                    facecolor='none',
                                                    computed_zorder=False)
            self.ax_lens.set_position(self.ax_coords.get_position())
            self.ax_lens.patch.set_alpha(0)
            self.ax_lens.view_init(elev=20, azim=45)
            self.ax_lens.set_axis_off()
            self.ax = self.ax_lens
        else:
            self.ax_coords.clear()
            self.ax_lens.clear()
        
        # Calculate system bounds for coordinate system
        max_diameter = 0
        total_length = system.get_total_length()
        
        for element in system.elements:
            max_diameter = max(max_diameter, element.lens.diameter)
            
        self._configure_coordinate_system(max_diameter, total_length)
        self.ax_lens.set_axis_off()
        
        # Draw each element
        for element in system.elements:
            lens = element.lens
            self._draw_lens_mesh(lens.radius_of_curvature_1, 
                                 lens.radius_of_curvature_2, 
                                 lens.thickness, 
                                 lens.diameter,
                                 z_offset=element.position)

        # Draw optical axis
        axis_length = max(max_diameter, total_length) * 1.2
        # Center the axis display relative to the system
        z_mid = total_length / 2
        z_start = -axis_length * 0.2
        z_end = total_length + axis_length * 0.2
        
        self.ax.plot([0, 0], [0, 0], [z_start, z_end],
                    color=self.COLORS_3D['axis'], linestyle='--', 
                    linewidth=2.5, alpha=0.9, label='Optical Axis')

        # Set limits
        max_dim = max(max_diameter, total_length) * 0.7
        self.ax.set_xlim([-max_dim, max_dim])
        self.ax.set_ylim([-max_dim, max_dim])
        self.ax.set_zlim([z_start, z_end])
        
        self.canvas.draw_idle()

    def _draw_lens_mesh(self, r1, r2, thickness, diameter, z_offset=0.0):
        """Helper to draw a single lens mesh at a specific Z offset"""
        
        # Adaptive resolution
        edge_res = max(20, min(30, int(40 - diameter / 10)))
        
        # Draw front surface (R1) - treat R=0 as flat
        r1_is_flat = r1 == 0 or abs(r1) > 10000
        if not r1_is_flat:
            points = self.calculate_surface_points(r1, diameter, is_front=True)
            if points:
                x1, y1, z1, mask1 = points
                z1 = z1 + z_offset # Apply offset
                
                x1_masked = np.where(mask1, x1, np.nan)
                y1_masked = np.where(mask1, y1, np.nan)
                z1_masked = np.where(mask1, z1, np.nan)
                
                self.ax.plot_surface(x1_masked, y1_masked, z1_masked, 
                                    alpha=0.8, color=self.COLORS_3D['surface_front'], 
                                    edgecolor=self.COLORS_3D['text'], linewidth=0.15,
                                    antialiased=True, shade=True, 
                                    lightsource=self._get_light_source())
        else:
            # Flat surface
            u = np.linspace(0, 2 * np.pi, edge_res)
            v = np.linspace(0, diameter/2, 8)
            x1 = np.outer(v, np.cos(u))
            y1 = np.outer(v, np.sin(u))
            z1 = np.zeros_like(x1) + z_offset
            self.ax.plot_surface(x1, y1, z1, alpha=0.8, color=self.COLORS_3D['surface_front'],
                               edgecolor=self.COLORS_3D['text'], linewidth=0.15,
                               antialiased=True, shade=True)
        
        # Draw back surface (R2) - treat R=0 as flat
        r2_is_flat = r2 == 0 or abs(r2) > 10000
        if not r2_is_flat:
            points = self.calculate_surface_points(r2, diameter, is_front=False)
            if points:
                x2, y2, z2, mask2 = points
                z2 = z2 + thickness + z_offset
                
                x2_masked = np.where(mask2, x2, np.nan)
                y2_masked = np.where(mask2, y2, np.nan)
                z2_masked = np.where(mask2, z2, np.nan)
                
                self.ax.plot_surface(x2_masked, y2_masked, z2_masked, 
                                    alpha=0.8, color=self.COLORS_3D['surface_back'],
                                    edgecolor=self.COLORS_3D['text'], linewidth=0.15,
                                    antialiased=True, shade=True,
                                    lightsource=self._get_light_source())
        else:
            # Flat surface
            u = np.linspace(0, 2 * np.pi, edge_res)
            v = np.linspace(0, diameter/2, 8)
            x2 = np.outer(v, np.cos(u))
            y2 = np.outer(v, np.sin(u))
            z2 = np.ones_like(x2) * (thickness + z_offset)
            self.ax.plot_surface(x2, y2, z2, alpha=0.8, color=self.COLORS_3D['surface_back'],
                               edgecolor=self.COLORS_3D['text'], linewidth=0.15,
                               antialiased=True, shade=True)
        
        # Calculate edge z-coordinates
        # Note: Recalculating edge points here to account for Z-offset
        # (This duplicates some logic from draw_lens but avoids passing complex z_edge arrays)
        
        # Front edge Z - treat R=0 as flat
        r1_is_flat = r1 == 0 or abs(r1) > 10000
        if not r1_is_flat:
            r1_abs = abs(r1)
            h_edge = diameter / 2
            if h_edge < r1_abs:
                sag_front = r1_abs - math.sqrt(r1_abs**2 - h_edge**2)
                z_front_edge = -sag_front if r1 > 0 else sag_front
            else:
                z_front_edge = 0
        else:
            z_front_edge = 0
        z_front_edge += z_offset
            
        # Back edge Z - treat R=0 as flat
        r2_is_flat = r2 == 0 or abs(r2) > 10000
        if not r2_is_flat:
            r2_abs = abs(r2)
            h_edge = diameter / 2
            if h_edge < r2_abs:
                sag_back = r2_abs - math.sqrt(r2_abs**2 - h_edge**2)
                z_back_edge = thickness + sag_back if r2 > 0 else thickness - sag_back
            else:
                z_back_edge = thickness
        else:
            z_back_edge = thickness
        z_back_edge += z_offset

        # Draw edge
        theta = np.linspace(0, 2 * np.pi, edge_res)
        z_edge = np.linspace(z_front_edge, z_back_edge, 8)
        theta_grid, z_grid = np.meshgrid(theta, z_edge)
        x_edge = (diameter / 2) * np.cos(theta_grid)
        y_edge = (diameter / 2) * np.sin(theta_grid)
        
        self.ax.plot_surface(x_edge, y_edge, z_grid, 
                           alpha=0.4, color=self.COLORS_3D['edge'],
                           edgecolor=self.COLORS_3D['grid'], linewidth=0.1,
                           antialiased=True)

    def draw_lens(self, r1, r2, thickness, diameter):
        """Draw the complete lens in 3D with optimized rendering"""
        # Validate inputs (keep validation)
        if diameter <= 0 or thickness <= 0:
             # ... error handling ...
             return

        # Recreate axes check ...
        needs_recreate = (not hasattr(self, 'ax_lens') or not hasattr(self, 'ax_coords') or
                          not hasattr(self.ax_lens, 'zaxis') or not hasattr(self.ax_coords, 'zaxis') or
                          self.ax_lens not in self.figure.axes or self.ax_coords not in self.figure.axes)
        
        if needs_recreate:
             # ... recreation code ...
             self.figure.clear()
             self.ax_coords = self.figure.add_subplot(111, projection='3d', facecolor=self.COLORS_3D['bg'], computed_zorder=False)
             self.ax_coords.view_init(elev=20, azim=45)
             self.ax_coords.mouse_init()
             self.ax_lens = self.figure.add_subplot(111, projection='3d', facecolor='none', computed_zorder=False)
             self.ax_lens.set_position(self.ax_coords.get_position())
             self.ax_lens.patch.set_alpha(0)
             self.ax_lens.view_init(elev=20, azim=45)
             self.ax_lens.set_axis_off()
             self.ax = self.ax_lens
        else:
            self.ax_coords.clear()
            self.ax_lens.clear()
            
        self._configure_coordinate_system(diameter, thickness)
        self.ax_lens.set_axis_off()
        
        # Use the helper
        self._draw_lens_mesh(r1, r2, thickness, diameter, z_offset=0.0)
        
        # Draw optical axis
        axis_length = max(diameter, thickness) * 1.2
        self.ax.plot([0, 0], [0, 0], [-axis_length/3, thickness + axis_length/3],
                    color=self.COLORS_3D['axis'], linestyle='--', 
                    linewidth=2.5, alpha=0.9, label='Optical Axis')
                    
        # Set limits
        max_dim = max(diameter, thickness) * 0.7
        self.ax.set_xlim([-max_dim, max_dim])
        self.ax.set_ylim([-max_dim, max_dim])
        self.ax.set_zlim([-max_dim/2, thickness + max_dim/2])
        
        self.canvas.draw_idle()

    
    def _get_light_source(self):
        """Create optimized light source for better 3D rendering"""
        from matplotlib.colors import LightSource
        return LightSource(azdeg=315, altdeg=45)
    
    def draw_lens_2d(self, r1, r2, thickness, diameter):
        """Draw the lens in 2D side view (cross-section)"""
        # Store current params for drag interaction
        self._current_lens_params = {'r1': r1, 'r2': r2, 'thickness': thickness, 'diameter': diameter}
        
        # Validate inputs
        if diameter <= 0:
            try:
                from dialogs import CopyableMessageBox
                CopyableMessageBox.showwarning(
                    None,
                    "Invalid Lens Parameters",
                    "Cannot render 2D view: Lens diameter must be greater than 0.\n\n"
                    f"Current diameter: {diameter} mm"
                )
            except ImportError:
                from tkinter import messagebox
                messagebox.showwarning(
                    "Invalid Lens Parameters",
                    "Cannot render 2D view: Lens diameter must be greater than 0.\n\n"
                    f"Current diameter: {diameter} mm"
                )
            return
        
        if thickness <= 0:
            try:
                from dialogs import CopyableMessageBox
                CopyableMessageBox.showwarning(
                    None,
                    "Invalid Lens Parameters",
                    "Cannot render 2D view: Lens thickness must be greater than 0.\n\n"
                    f"Current thickness: {thickness} mm"
                )
            except ImportError:
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
        self.ax.grid(True, color=self.COLORS_3D['grid'], linestyle='-', linewidth=1, alpha=0.5)
        
        # Calculate lens profile
        y_max = diameter / 2
        y = np.linspace(-y_max, y_max, 200)
        
        # Front surface (R1) - treat R=0 as flat
        r1_is_flat = r1 == 0 or abs(r1) > 10000
        
        # Back surface (R2) - treat R=0 as flat
        r2_is_flat = r2 == 0 or abs(r2) > 10000
        
        # Conventional lens logic: Thickness is usually vertex-to-vertex.
        # However, the request is to apply it at the edge.
        h_edge = diameter / 2
        
        # Calculate sag1 (facing left)
        if not r1_is_flat:
            r1_abs = abs(r1)
            h_edge_clipped1 = min(h_edge, r1_abs)
            sag1_edge = r1_abs - math.sqrt(r1_abs**2 - h_edge_clipped1**2)
            # Center of R1 vertex is at x=0
            # For positive R1 (convex left): edge is at x = sag1_edge
            # For negative R1 (concave left): edge is at x = -sag1_edge
            x1_edge = sag1_edge if r1 > 0 else -sag1_edge
            
            y_limit1 = min(y_max, r1_abs * 0.999)
            y_valid = np.linspace(-y_limit1, y_limit1, 200)
            if r1 > 0:  # Convex
                x1 = (r1_abs - np.sqrt(r1_abs**2 - y_valid**2))
            else:  # Concave
                x1 = -(r1_abs - np.sqrt(r1_abs**2 - y_valid**2))
        else:
            x1_edge = 0
            y_valid = y
            x1 = np.zeros_like(y_valid)
            
        # Calculate x2_edge = x1_edge + thickness
        x2_edge = x1_edge + thickness
        
        # Calculate back surface (R2) which faces right
        if not r2_is_flat:
            r2_abs = abs(r2)
            h_edge_clipped2 = min(h_edge, r2_abs)
            sag2_edge = r2_abs - math.sqrt(r2_abs**2 - h_edge_clipped2**2)
            
            # For R2 (facing right):
            # If R2 > 0 (convex right): edge is at x = vertex - sag2_edge => vertex = edge + sag2_edge
            # If R2 < 0 (concave right): edge is at x = vertex + sag2_edge => vertex = edge - sag2_edge
            x2_vertex = x2_edge + sag2_edge if r2 > 0 else x2_edge - sag2_edge
            
            y_limit2 = min(y_max, r2_abs * 0.999)
            y_valid2 = np.linspace(-y_limit2, y_limit2, 200)
            if r2 > 0:  # Convex
                x2 = x2_vertex - (r2_abs - np.sqrt(r2_abs**2 - y_valid2**2))
            else:  # Concave
                x2 = x2_vertex + (r2_abs - np.sqrt(r2_abs**2 - y_valid2**2))
        else:
            y_valid2 = y
            x2 = np.full_like(y_valid2, x2_edge)
        
        # Draw lens surfaces
        self.ax.plot(x1, y_valid, color=self.COLORS_3D['surface_front'], linewidth=2.5, label='Front Surface')
        self.ax.plot(x2, y_valid2, color=self.COLORS_3D['surface_back'], linewidth=2.5, label='Back Surface')


        # Fill lens body (physical lens material)
        # Ensure we interpolate to same y coordinates for filling
        y_fill = np.linspace(-y_max, y_max, 200)

        # Interpolate x1 and x2 to y_fill, keeping x values constant if y is outside surface range
        x1_fill = np.interp(y_fill, y_valid, x1)
        x2_fill = np.interp(y_fill, y_valid2, x2)

        self.ax.fill_betweenx(y_fill, x1_fill, x2_fill, color=self.COLORS_3D['surface_front'], alpha=0.2)

        # Draw edges
        # Top edge
        self.ax.plot([x1_fill[0], x2_fill[0]], [y_fill[0], y_fill[0]], 
                    color=self.COLORS_3D['edge'], linewidth=1.5)
        # Bottom edge
        self.ax.plot([x1_fill[-1], x2_fill[-1]], [y_fill[-1], y_fill[-1]], 
                    color=self.COLORS_3D['edge'], linewidth=1.5)
        
        # Draw optical axis
        x_min = min(x1.min() if len(x1) > 0 else 0, x2.min() if len(x2) > 0 else thickness)
        x_max = max(x1.max() if len(x1) > 0 else 0, x2.max() if len(x2) > 0 else thickness)
        margin = x_max  # Equal to lens thickness for empty space
        self.ax.axhline(0, color=self.COLORS_3D['axis'], linestyle='--', linewidth=1.5, 
                       alpha=0.7, label='Optical Axis')
        
        # Labels and styling
        self.ax.set_xlabel('Thickness (mm)', color=self.COLORS_3D['text'], fontsize=10)
        self.ax.set_ylabel('Diameter (mm)', color=self.COLORS_3D['text'], fontsize=10)
        
        # Add surface labels
        x_start = x1[0] if len(x1) > 0 else 0
        x_end = x2[-1] if len(x2) > 0 else thickness
        self.ax.annotate('Radius 1', xy=(x_start, y_max*0.8), fontsize=9, color=self.COLORS_3D['surface_front'])
        self.ax.annotate('Radius 2', xy=(x_end, y_max*0.8), fontsize=9, color=self.COLORS_3D['surface_back'])
        
        # Set axis limits to show more empty space
        max_dim = max(thickness, y_max) * 2
        self.ax.set_xlim(-max_dim, max_dim)
        self.ax.set_ylim(-max_dim, max_dim)
        
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
        self.canvas.draw_idle()
