from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QPoint, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QPainterPath, QBrush
import math

class _2DVisualizationWidget(QWidget):
    """2D lens visualization"""
    
    # Signals for interactive manipulation
    property_changed = Signal(str, float)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._lens = None
        self._view_mode = "2D"
        
        self.setMinimumSize(400, 300)
        self.setStyleSheet("background-color: #1e1e1e;")
        
        self._bg_color = QColor("#1e1e1e")
        self._r1_color = QColor(0, 150, 255, 180)    # Blue for radius 1
        self._r2_color = QColor(0, 200, 100, 180)  # Green for radius 2
        self._fill_color = QColor(150, 200, 230, 80)   # Light blue fill
        self._edge_color = QColor(150, 150, 150, 200)   # Grey for lens edge
        self._text_color = QColor("#e0e0e0")
        self._axis_color = QColor("#666666")
        self._handle_color = QColor(255, 255, 255, 200) # White for interactive handles
        
        # Interaction state
        self._active_handle = None # 'r1', 'r2', 'thickness', 'diameter'
        self._last_mouse_pos = None
        self._handles = {} # name -> (x, y)
        self._scale = 1.0
        self._cx = 0
        self._cy = 0
        
        self.setMouseTracking(True)

    def mousePressEvent(self, event):
        if not self._lens: return
        
        pos = event.position().toPoint()
        for name, h_pos in self._handles.items():
            dx = pos.x() - h_pos.x()
            dy = pos.y() - h_pos.y()
            if (dx*dx + dy*dy) < 100: # 10px radius hit area
                self._active_handle = name
                self._last_mouse_pos = pos
                self.setCursor(Qt.ClosedHandCursor)
                break

    def mouseReleaseEvent(self, event):
        self._active_handle = None
        self.setCursor(Qt.ArrowCursor)

    def mouseMoveEvent(self, event):
        if not self._lens: return
        
        pos = event.position().toPoint()
        if self._active_handle:
            dx = (pos.x() - self._last_mouse_pos.x()) / self._scale
            dy = (pos.y() - self._last_mouse_pos.y()) / self._scale
            
            if self._active_handle == 'r1':
                # Dragging R1 vertex horizontally
                new_r1 = self._lens.radius_of_curvature_1 + dx
                # Snap to flat if close to zero
                if abs(new_r1) < 1.0: new_r1 = 0.0
                self.property_changed.emit('r1', new_r1)
            elif self._active_handle == 'r2':
                # Dragging R2 vertex horizontally
                new_r2 = self._lens.radius_of_curvature_2 + dx
                # Snap to flat if close to zero
                if abs(new_r2) < 1.0: new_r2 = 0.0
                self.property_changed.emit('r2', new_r2)
            elif self._active_handle == 'thickness':
                # Dragging right edge
                new_t = self._lens.thickness + dx
                if new_t < 0.1: new_t = 0.1
                self.property_changed.emit('thickness', new_t)
            elif self._active_handle == 'diameter':
                # Dragging top/bottom edge
                new_d = self._lens.diameter - 2 * dy # Screen Y is inverted
                if new_d < 1.0: new_d = 1.0
                self.property_changed.emit('diameter', new_d)
                
            self._last_mouse_pos = pos
        else:
            # Update cursor if hovering over a handle
            hovering = False
            for h_pos in self._handles.values():
                dx = pos.x() - h_pos.x()
                dy = pos.y() - h_pos.y()
                if (dx*dx + dy*dy) < 100:
                    hovering = True
                    break
            if hovering:
                self.setCursor(Qt.PointingHandCursor)
            else:
                self.setCursor(Qt.ArrowCursor)

    def set_view_mode(self, mode):
        self._view_mode = mode
        self.update()
    
    def update_lens(self, lens):
        self._lens = lens
        self.update()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        w, h = self.width(), self.height()
        painter.fillRect(0, 0, w, h, self._bg_color)
        
        if not self._lens:
            return
        
        r1 = self._lens.radius_of_curvature_1
        r2 = self._lens.radius_of_curvature_2
        thickness = self._lens.thickness
        diameter = self._lens.diameter
        
        # Larger scale for bigger lens
        max_dim = max(thickness * 2, diameter, 100)
        self._scale = min(w, h) / max_dim * 0.85
        scale = self._scale
        cx, cy = w/2, h/2
        self._cx, self._cy = cx, cy
        
        # Draw grid
        grid_color = QColor("#333333")
        painter.setPen(QPen(grid_color, 1))
        grid_spacing = 10 * scale  # 10mm grid
        
        # Draw grid lines relative to center
        start_x = cx % grid_spacing
        while start_x < w:
            painter.drawLine(start_x, 0, start_x, h)
            start_x += grid_spacing
        start_y = cy % grid_spacing
        while start_y < h:
            painter.drawLine(0, start_y, w, start_y)
            start_y += grid_spacing
        
        # Draw axis
        painter.setPen(QPen(self._axis_color, 1))
        painter.drawLine(0, cy, w, cy)
        painter.drawLine(cx, 0, cx, h)
        
        # Geometric calculations
        r1_abs = abs(r1)
        r2_abs = abs(r2)
        half_d = diameter / 2
        
        # Helper to get sag at y
        def get_sag(r, y):
            if abs(r) < 1e-6: return 0
            r_a = abs(r)
            y_safe = min(abs(y), r_a)
            sag = r_a - math.sqrt(max(0, r_a**2 - y_safe**2))
            return sag if r > 0 else -sag

        # X positions
        x1_vertex = cx
        sag1_edge = get_sag(r1, half_d)
        x1_edge = x1_vertex + sag1_edge * scale
        
        x2_edge = x1_edge + thickness * scale
        sag2_edge = get_sag(r2, half_d)
        x2_vertex = x2_edge - sag2_edge * scale

        # Safety check: if x2_vertex or x1_vertex is NaN, use defaults to prevent crash
        if math.isnan(x1_vertex): x1_vertex = cx
        if math.isnan(x2_vertex): x2_vertex = cx + thickness * scale
        if math.isnan(x1_edge): x1_edge = x1_vertex
        if math.isnan(x2_edge): x2_edge = x1_edge + thickness * scale

        # Clear handles
        self._handles = {}

        # Construct single coherent lens path for filling
        path_lens = QPainterPath()
        
        # 1. Front Surface (top to bottom)
        pts = 50
        for i in range(pts + 1):
            y = -half_d + (diameter * i / pts)
            x = x1_vertex + get_sag(r1, abs(y)) * scale
            if i == 0: path_lens.moveTo(x, cy + y * scale)
            else: path_lens.lineTo(x, cy + y * scale)
            
        # 2. Bottom Edge
        path_lens.lineTo(x2_edge, cy + half_d * scale)
        
        # 3. Back Surface (bottom to top)
        for i in range(pts + 1):
            y = half_d - (diameter * i / pts)
            x = x2_vertex + get_sag(r2, abs(y)) * scale
            path_lens.lineTo(x, cy + y * scale)
            
        # 4. Top Edge
        path_lens.closeSubpath()
        
        # Fill and stroke lens
        painter.setPen(QPen(self._edge_color, 1))
        painter.setBrush(QBrush(self._fill_color))
        painter.drawPath(path_lens)
        
        # Highlight surfaces with colors
        # R1
        path_r1 = QPainterPath()
        for i in range(pts + 1):
            y = -half_d + (diameter * i / pts)
            x = x1_vertex + get_sag(r1, abs(y)) * scale
            if i == 0: path_r1.moveTo(x, cy + y * scale)
            else: path_r1.lineTo(x, cy + y * scale)
        painter.setPen(QPen(self._r1_color, 2))
        painter.drawPath(path_r1)
        
        # R2
        path_r2 = QPainterPath()
        for i in range(pts + 1):
            y = -half_d + (diameter * i / pts)
            x = x2_vertex + get_sag(r2, abs(y)) * scale
            if i == 0: path_r2.moveTo(x, cy + y * scale)
            else: path_r2.lineTo(x, cy + y * scale)
        painter.setPen(QPen(self._r2_color, 2))
        painter.drawPath(path_r2)

        # Draw handles (spaced out to avoid crowding)
        def draw_handle(p, name, pos, label=""):
            self._handles[name] = pos
            if self._active_handle == name:
                p.setPen(QPen(QColor(0, 255, 0), 2))
                p.setBrush(QBrush(QColor(0, 255, 0, 150)))
            else:
                p.setPen(QPen(Qt.white, 1))
                p.setBrush(QBrush(QColor(255, 255, 255, 50)))
            p.drawEllipse(pos, 6, 6)
            
        # R1 handle at vertex
        draw_handle(painter, 'r1', QPoint(int(x1_vertex), int(cy)))
        # R2 handle at vertex
        draw_handle(painter, 'r2', QPoint(int(x2_vertex), int(cy)))
        # Thickness handle at bottom center
        draw_handle(painter, 'thickness', QPoint(int((x1_edge + x2_edge)/2), int(cy + half_d * scale + 15)))
        # Diameter handle at top center
        draw_handle(painter, 'diameter', QPoint(int((x1_edge + x2_edge)/2), int(cy - half_d * scale - 15)))
