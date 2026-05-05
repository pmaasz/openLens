from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen, QBrush
import math

class SimulationVisualizationWidget(QWidget):
    """2D ray tracing simulation visualization widget"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._lens = None
        self._system = None
        self._rays = []
        self._wavelength = 550  # Default wavelength in nm
        
        self.setMinimumSize(400, 300)
        self.setStyleSheet("background-color: #1e1e1e; border: 2px solid #888888;")
        
        self._bg_color = QColor("#1e1e1e")
        self._axis_color = QColor("#666666")
        self._lens_color = QColor(0, 120, 212, 150)
        self._ray_color = QColor(255, 200, 0, 200)
        self._text_color = QColor("#e0e0e0")
        self._ghost_color = QColor(255, 100, 100, 180)
        self._show_ghosts = False
        self._show_image_sim = False
        self._image_pattern = "Star"
        
        # Zoom and pan state
        self._zoom = 1.0
        self._pan_x = 0
        self._pan_y = 0
        self._is_panning = False
        self._last_mouse_x = 0
        self._last_mouse_y = 0
        
        # Install event filters
        self.setFocusPolicy(Qt.StrongFocus)
    
    @staticmethod
    def wavelength_to_color(wavelength):
        """Convert wavelength (nm) to RGB color"""
        if wavelength < 380:
            wavelength = 380
        elif wavelength > 780:
            wavelength = 780
        
        # Simplified spectral color approximation
        if wavelength < 440:
            r = int((440 - wavelength) / (440 - 380) * 255)
            g = 0
            b = 255
        elif wavelength < 490:
            r = 0
            g = int((wavelength - 440) / (490 - 440) * 255)
            b = 255
        elif wavelength < 510:
            r = 0
            g = 255
            b = int((510 - wavelength) / (510 - 490) * 255)
        elif wavelength < 580:
            r = int((wavelength - 510) / (580 - 510) * 255)
            g = 255
            b = 0
        elif wavelength < 645:
            r = 255
            g = int((645 - wavelength) / (645 - 580) * 255)
            b = 0
        else:
            r = 255
            g = 0
            b = 0
        
        return QColor(r, g, b, 200)
    
    def wheelEvent(self, event):
        """Handle mouse wheel for zooming"""
        if event.angleDelta().y() > 0:
            self._zoom *= 1.1
        else:
            self._zoom /= 1.1
        self._zoom = max(0.1, min(self._zoom, 50.0))
        self.update()
    
    def mousePressEvent(self, event):
        """Start panning on mouse press"""
        if event.button() == Qt.LeftButton:
            self._is_panning = True
            self._last_mouse_x = event.position().x()
            self._last_mouse_y = event.position().y()
    
    def mouseMoveEvent(self, event):
        """Pan the view when dragging"""
        if self._is_panning:
            dx = event.position().x() - self._last_mouse_x
            dy = event.position().y() - self._last_mouse_y
            self._pan_x += dx
            self._pan_y -= dy  # Invert because screen Y is down
            self._last_mouse_x = event.position().x()
            self._last_mouse_y = event.position().y()
            self.update()
    
    def mouseReleaseEvent(self, event):
        """Stop panning on mouse release"""
        if event.button() == Qt.LeftButton:
            self._is_panning = False
    
    def keyPressEvent(self, event):
        """Handle keyboard for zoom/pan reset"""
        if event.key() == Qt.Key_R:
            self._zoom = 1.0
            self._pan_x = 0
            self._pan_y = 0
            self.update()
        elif event.key() == Qt.Key_Plus or event.key() == Qt.Key_Equal:
            self._zoom *= 1.2
            self.update()
        elif event.key() == Qt.Key_Minus:
            self._zoom /= 1.2
            self._zoom = max(0.1, self._zoom)
            self.update()
    
    def reset_view(self):
        """Reset zoom and pan"""
        self._zoom = 1.0
        self._pan_x = 0
        self._pan_y = 0
        self.update()
    
    def run_simulation(self, lens_or_system, num_rays=11, angle=0, source_height=0, show_ghosts=False, wavelength=550):
        """Run ray tracing simulation"""
        from src.optical_system import OpticalSystem
        if isinstance(lens_or_system, OpticalSystem):
            self._system = lens_or_system
            self._lens = None
        else:
            self._lens = lens_or_system
            self._system = None
            
        self._rays = []
        self._ghost_rays = []
        self._show_ghosts = show_ghosts
        self._wavelength = wavelength
        self._ray_color = self.wavelength_to_color(wavelength)
        
        try:
            from src.ray_tracer import LensRayTracer, Ray
            
            # Use appropriate tracer
            if self._system:
                # OpticalSystem has multiple elements
                from src.ray_tracer import SystemRayTracer
                tracer = SystemRayTracer(self._system)
                diameter = self._system.elements[0].lens.diameter if self._system.elements else 25.0
            else:
                tracer = LensRayTracer(self._lens)
                diameter = self._lens.diameter
            
            angle_rad = angle * math.pi / 180.0
            
            for i in range(num_rays):
                if num_rays == 1:
                    h = 0
                else:
                    h = -diameter/2 + diameter * i / (num_rays - 1)
                
                ray = Ray(-100, h + source_height, angle_rad=angle_rad)
                tracer.trace_ray(ray)
                self._rays.append(ray)
            
            if show_ghosts:
                if self._system:
                    self._run_ghost_analysis(self._system, tracer)
                elif self._lens:
                    # Wrap lens in temporary system for GhostAnalyzer
                    temp_system = OpticalSystem(name="Ghost Analysis")
                    temp_system.add_lens(self._lens)
                    self._run_ghost_analysis(temp_system, tracer)
        
        except Exception as e:
            print(f"Simulation error: {e}")
        
        self.update()
    
    def _run_ghost_analysis(self, system, tracer):
        """Run ghost analysis for 2nd order reflections"""
        try:
            from src.analysis.ghost import GhostAnalyzer
            analyzer = GhostAnalyzer(system)
            ghosts = analyzer.trace_ghosts(num_rays=3)
            
            for ghost in ghosts:
                if ghost.rays:
                    self._ghost_rays.append(ghost.rays)
        except Exception as e:
            print(f"Ghost analysis error: {e}")
    
    def run_image_simulation(self, lens, pattern="Star"):
        """Run image simulation pattern through lens"""
        self._lens = lens
        self._show_image_sim = True
        self._image_pattern = pattern
        self.update()
    
    def clear_simulation(self):
        """Clear simulation results"""
        self._rays = []
        self._ghost_rays = []
        self._lens = None
        self._show_image_sim = False
        self.update()
    
    def paintEvent(self, event):
        """Paint the simulation"""
        from PySide6.QtGui import QPainter, QPen, QColor, QPainterPath, QBrush
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        w = self.width()
        h = self.height()
        
        painter.fillRect(0, 0, w, h, self._bg_color)
        
        if not self._lens and not self._system:
            painter.setPen(QPen(self._text_color, 1))
            painter.drawText(w//2 - 80, h//2, "Run simulation to see rays")
            return
        
        # Draw axis
        painter.setPen(QPen(self._axis_color, 1, Qt.DashLine))
        painter.drawLine(0, h//2, w, h//2)
        
        # Determine total bounds for scaling
        if self._system:
            total_thickness = self._system.get_total_length()
            max_diameter = max((e.lens.diameter for e in self._system.elements), default=25.0)
        else:
            total_thickness = self._lens.thickness
            max_diameter = self._lens.diameter
            
        max_dim = max(total_thickness * 2, max_diameter, 30) * 1.2
        scale = min(w, h) / max_dim * self._zoom
        
        cx = w / 4 + self._pan_x
        cy = h / 2 + self._pan_y

        def draw_single_lens(pnt, lens, start_x, center_y, sc, color):
            # Helper to get sag at y
            def get_sag(r, y):
                if abs(r) < 1e-6: return 0
                r_a = abs(r)
                if y > r_a: return r_a
                sag = r_a - (r_a**2 - y**2)**0.5
                return sag if r > 0 else -sag

            r1 = lens.radius_of_curvature_1
            r2 = lens.radius_of_curvature_2
            t = lens.thickness
            d = lens.diameter
            half_d = d / 2

            x1_vertex = start_x
            sag1_edge = get_sag(r1, half_d)
            x1_edge = x1_vertex + sag1_edge * sc
            
            x2_edge = x1_edge + t * sc
            sag2_edge = get_sag(r2, half_d)
            x2_vertex = x2_edge - sag2_edge * sc

            path = QPainterPath()
            pts = 50
            
            # 1. Front Surface (top to bottom)
            for i in range(pts + 1):
                y = -half_d + (d * i / pts)
                x = x1_vertex + get_sag(r1, abs(y)) * sc
                if i == 0: path.moveTo(x, center_y + y * sc)
                else: path.lineTo(x, center_y + y * sc)
                
            # 2. Bottom Edge
            path.lineTo(x2_edge, center_y + half_d * sc)
            
            # 3. Back Surface (bottom to top)
            for i in range(pts + 1):
                y = half_d - (d * i / pts)
                x = x2_vertex + get_sag(r2, abs(y)) * sc
                path.lineTo(x, center_y + y * sc)
                
            # 4. Top Edge
            path.closeSubpath()
            
            pnt.setPen(QPen(color, 2))
            pnt.setBrush(QBrush(color))
            pnt.drawPath(path)

        # Draw lenses
        if self._system:
            for element in self._system.elements:
                draw_single_lens(painter, element.lens, cx + element.position * scale, cy, scale, self._lens_color)
        else:
            draw_single_lens(painter, self._lens, cx, cy, scale, self._lens_color)
        
        # Draw rays
        painter.setPen(QPen(self._ray_color, 1.5))
        for ray in self._rays:
            if len(ray.path) < 2: continue
            for j in range(len(ray.path) - 1):
                p1, p2 = ray.path[j], ray.path[j + 1]
                if hasattr(p1, 'x'): x1, y1, x2, y2 = p1.x, p1.y, p2.x, p2.y
                else: x1, y1, x2, y2 = p1[0], p1[1], p2[0], p2[1]
                painter.drawLine(int(cx + x1 * scale), int(cy - y1 * scale), int(cx + x2 * scale), int(cy - y2 * scale))
        
        # Ghost rays
        if self._show_ghosts and self._ghost_rays:
            painter.setPen(QPen(self._ghost_color, 1))
            for ghost_path in self._ghost_rays:
                for ray in ghost_path:
                    if len(ray.path) < 2: continue
                    for j in range(len(ray.path) - 1):
                        p1, p2 = ray.path[j], ray.path[j + 1]
                        if hasattr(p1, 'x'): x1, y1, x2, y2 = p1.x, p1.y, p2.x, p2.y
                        else: x1, y1, x2, y2 = p1[0], p1[1], p2[0], p2[1]
                        painter.drawLine(int(cx + x1 * scale), int(cy - y1 * scale), int(cx + x2 * scale), int(cy - y2 * scale))
        
        if self._show_image_sim and self._lens:
            painter.setPen(QPen(QColor(0, 255, 136), 2))
            cx_img = w // 2
            cy_img = h // 2
            pattern = self._image_pattern
            
            if pattern == "Star":
                for i in range(8):
                    angle = i * math.pi / 4
                    x2 = cx_img + 80 * (1 if i % 2 else 0.5) * (1 if i < 4 else -1)
                    y2 = cy_img + 80 * (1 if i % 2 else 0.5) * (1 if (i % 8) < 4 else -1)
                    painter.drawLine(cx_img, cy_img, int(x2), int(y2))
            elif pattern == "Grid":
                for i in range(-3, 4):
                    painter.drawLine(cx_img + i * 25, cy_img - 75, cx_img + i * 25, cy_img + 75)
                    painter.drawLine(cx_img - 75, cy_img + i * 25, cx_img + 75, cy_img + i * 25)
            elif pattern == "USAF 1951":
                for i in range(6):
                    for j in range(6):
                        size = 5 * (1.122 ** i)
                        x = cx_img - 50 + j * 20
                        y = cy_img - 50 + i * 15
                        painter.drawRect(int(x), int(y), int(size), int(size))
