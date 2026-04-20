"""
OpenLens PySide6 3D Lens Visualization Widget
3D matplotlib-based visualization for lens geometry
"""

import math
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt


class _3DVisualizationWidget(QWidget):
    """3D lens visualization using matplotlib"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._lens = None
        self._canvas = None
        self._figure = None
        
        self.setMinimumSize(400, 300)
        self.setStyleSheet("background-color: #1e1e1e;")
        
        try:
            import matplotlib
            matplotlib.use('Qt5Agg')
            from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
            from matplotlib.figure import Figure
            
            self._figure = Figure(figsize=(6, 5), facecolor='#1e1e1e')
            self._canvas = FigureCanvasQTAgg(self._figure)
            self._canvas.setStyleSheet("background-color: #1e1e1e;")
            
            layout = QVBoxLayout(self)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(self._canvas)
            
            self._figure.subplots_adjust(left=0.05, right=0.95, top=0.95, bottom=0.05)
            
            # Fixed coordinate system (background)
            self._ax_coords = self._figure.add_subplot(111, projection='3d', facecolor='#1e1e1e', computed_zorder=False)
            self._ax_coords.view_init(elev=20, azim=45)
            self._ax_coords.mouse_init()
            
            # Rotatable lens geometry (foreground)
            self._ax_lens = self._figure.add_subplot(111, projection='3d', facecolor='none', computed_zorder=False)
            self._ax_lens.set_position(self._ax_coords.get_position())
            self._ax_lens.patch.set_alpha(0)
            self._ax_lens.view_init(elev=20, azim=45)
            self._ax_lens.set_axis_off()
            self._ax_lens.mouse_init()
            
            # Use lens axis for main reference
            self._ax = self._ax_lens
            
            # Configure coordinate appearance
            self._ax_coords.set_xlabel('X (mm)', color='#666')
            self._ax_coords.set_ylabel('Y (mm)', color='#666')
            self._ax_coords.set_zlabel('Z (mm)', color='#666')
            self._ax_coords.tick_params(colors='#555', labelsize=8)
            self._ax_coords.xaxis.pane.set_facecolor('#1e1e1e')
            self._ax_coords.yaxis.pane.set_facecolor('#1e1e1e')
            self._ax_coords.zaxis.pane.set_facecolor('#1e1e1e')
            self._ax_coords.xaxis.pane.set_alpha(0.9)
            self._ax_coords.yaxis.pane.set_alpha(0.9)
            self._ax_coords.zaxis.pane.set_alpha(0.9)
            
        except ImportError:
            layout = QVBoxLayout(self)
            lbl = QLabel("Install matplotlib\nfor 3D view")
            lbl.setStyleSheet("color: #888; padding: 50px;")
            layout.addWidget(lbl)
    
    def update_lens(self, lens):
        if not lens or not self._ax or not self._figure:
            return
        
        # Clear only lens axis
        if hasattr(self, '_ax_lens'):
            self._ax_lens.clear()
            self._ax_lens.set_axis_off()
            
            # Keep coordinate system fixed (don't clear/recreate it)
            # Just set limits from current lens
            thickness, diameter = lens.thickness, lens.diameter
            max_dim = max(diameter, thickness) * 0.7
            if hasattr(self, '_ax_coords'):
                self._ax_coords.set_xlim([-max_dim, max_dim])
                self._ax_coords.set_ylim([-max_dim, max_dim])
                self._ax_coords.set_zlim([-max_dim/2, thickness + max_dim/2])
        
        r1, r2 = lens.radius_of_curvature_1, lens.radius_of_curvature_2
        thickness, diameter = lens.thickness, lens.diameter
        max_r = diameter / 2.0
        
        import numpy as np
        
        # Create circles at top and bottom edges
        theta = np.linspace(0, 2*np.pi, 36)
        
        # Front face Z position (vertex)
        z1_vertex = 0
        
        # Calculate sag at the edge to find actual edge Z position
        r1_abs = abs(r1)
        sag1_edge = 0
        if r1_abs > 0.1:
            max_r_clamped = min(max_r, r1_abs * 0.999)
            sag1_edge = r1_abs - np.sqrt(r1_abs**2 - max_r_clamped**2)
            
        r2_abs = abs(r2)
        sag2_edge = 0
        if r2_abs > 0.1:
            max_r_clamped = min(max_r, r2_abs * 0.999)
            sag2_edge = r2_abs - np.sqrt(r2_abs**2 - max_r_clamped**2)

        x1_vertex = 0
        x1_edge = x1_vertex + (sag1_edge if r1 > 0 else 0)
        x2_edge = x1_edge + thickness
        x2_vertex = x2_edge - (sag2_edge if r2 < 0 else 0)

        # Circle at front edge
        x_front = max_r * np.cos(theta)
        y_front = max_r * np.sin(theta)
        z_front = np.full_like(theta, x1_edge)
        self._ax.plot(x_front, y_front, z_front, color='blue', linewidth=2)
        
        # Circle at back edge  
        x_back = max_r * np.cos(theta)
        y_back = max_r * np.sin(theta)
        z_back = np.full_like(theta, x2_edge)
        self._ax.plot(x_back, y_back, z_back, color='green', linewidth=2)
        
        # Connect edges with vertical lines (cylinder wall)
        for i in range(0, len(theta), 2):
            ex = [x_front[i], x_back[i]]
            ey = [y_front[i], y_back[i]]
            ez = [z_front[i], z_back[i]]
            self._ax.plot(ex, ey, ez, color='gray', linewidth=0.5)
        
        # Fill surfaces
        r_vals = np.linspace(0, max_r, 15)
        theta_vals = np.linspace(0, 2*np.pi, 25)
        R, THETA = np.meshgrid(r_vals, theta_vals)

        # Front surface (blue)
        if r1_abs > 0.1:
            rho = R
            rho_safe = np.minimum(rho, r1_abs * 0.999)
            sag1 = r1_abs - np.sqrt(r1_abs**2 - rho_safe**2)
            Z_front = x1_vertex + (sag1 if r1 > 0 else -sag1)

            X = R * np.cos(THETA)
            Y = R * np.sin(THETA)
            self._ax.plot_surface(X, Y, Z_front, alpha=0.5, color='blue', rstride=2, cstride=2)

        # Back surface (green)
        if r2_abs > 0.1:
            rho = R
            rho_safe = np.minimum(rho, r2_abs * 0.999)
            sag2 = r2_abs - np.sqrt(r2_abs**2 - rho_safe**2)
            Z_back = x2_vertex + (sag2 if r2 > 0 else -sag2)
            
            X = R * np.cos(THETA)
            Y = R * np.sin(THETA)
            self._ax.plot_surface(X, Y, Z_back, alpha=0.5, color='green', rstride=2, cstride=2)
        
        # Set axis limits on lens axis only
        z_min = min(x1_vertex + (-sag1_edge if r1 < 0 else 0), x2_vertex + (-sag2_edge if r2 < 0 else 0))
        z_max = max(x1_vertex + (sag1_edge if r1 > 0 else 0), x2_vertex + (sag2_edge if r2 > 0 else 0))
        padding = max(diameter, thickness) * 0.3
        limit = max(diameter, thickness) / 2 + padding
        self._ax.set_xlim([-limit, limit])
        self._ax.set_ylim([-limit, limit])
        self._ax.set_zlim([z_min - padding, z_max + padding])

        
        self._ax.view_init(elev=20, azim=45)
        
        # Add dimension text
        dim_text = f"D={diameter:.0f}mm  t={thickness:.1f}mm"
        self._ax.text2D(0.02, 0.98, dim_text, transform=self._ax.transAxes,
                       color='white', fontsize=10, fontweight='bold')
        
        self._canvas.draw()