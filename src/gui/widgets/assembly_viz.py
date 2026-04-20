"""
OpenLens PySide6 Assembly Visualization Widget
2D visualization of optical system (multiple lenses)
"""

from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QPen, QPainterPath, QBrush, QColor
from PySide6.QtCore import Qt


class AssemblyVisualizationWidget(QWidget):
    """2D visualization of optical system (multiple lenses)"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._system = None
        
        self.setMinimumSize(400, 300)
        self.setStyleSheet("background-color: #1e1e1e; border: 1px solid #3f3f3f;")
        
        self._bg_color = QColor("#1e1e1e")
        self._axis_color = QColor("#666666")
        self._lens_colors = [
            QColor(0, 120, 212, 150),
            QColor(0, 180, 100, 150),
            QColor(200, 100, 0, 150),
            QColor(150, 50, 200, 150),
        ]
        self._text_color = QColor("#e0e0e0")
    
    def update_system(self, system):
        """Update visualization with optical system"""
        self._system = system
        self.update()
    
    def paintEvent(self, event):
        """Paint the optical system visualization"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        w = self.width()
        h = self.height()
        
        painter.fillRect(0, 0, w, h, self._bg_color)
        
        if not self._system or not self._system.elements:
            return
        
        total_thickness = sum(e.lens.thickness for e in self._system.elements)
        for i in range(len(self._system.elements) - 1):
            if i < len(self._system.air_gaps):
                total_thickness += self._system.air_gaps[i].thickness
        
        max_diameter = max(e.lens.diameter for e in self._system.elements)
        
        max_dim = max(total_thickness * 1.5, max_diameter * 1.3)
        scale = min(w, h) / max_dim / 2
        
        cx = 30
        cy = h / 2
        
        painter.setPen(QPen(self._axis_color, 1, Qt.DashLine))
        painter.drawLine(0, cy, w, cy)
        
        for i, element in enumerate(self._system.elements):
            lens = element.lens
            color = self._lens_colors[i % len(self._lens_colors)]
            
            self._draw_lens(painter, lens, cx, cy, scale, color)
            
            if i < len(self._system.air_gaps):
                cx += lens.thickness * scale + self._system.air_gaps[i].thickness * scale
            else:
                cx += lens.thickness * scale
    
    def _draw_lens(self, painter, lens, cx, cy, scale, color):
        """Draw a single lens"""
        import math
        
        def get_sag(r, y):
            if abs(r) < 1e-6: return 0
            r_a = abs(r)
            if y > r_a: return r_a
            sag = r_a - (r_a**2 - y**2)**0.5
            return sag if r > 0 else -sag

        r1 = lens.radius_of_curvature_1
        r2 = lens.radius_of_curvature_2
        thickness = lens.thickness
        diameter = lens.diameter
        
        half_d = diameter / 2
        x1_vertex = cx
        sag1_edge = get_sag(r1, half_d)
        x1_edge = x1_vertex + sag1_edge * scale
        
        x2_edge = x1_edge + thickness * scale
        sag2_edge = get_sag(r2, half_d)
        x2_vertex = x2_edge - sag2_edge * scale

        path = QPainterPath()
        pts = 50
        
        for i in range(pts + 1):
            y = -half_d + (diameter * i / pts)
            x = x1_vertex + get_sag(r1, abs(y)) * scale
            if i == 0: path.moveTo(x, cy + y * scale)
            else: path.lineTo(x, cy + y * scale)
            
        path.lineTo(x2_edge, cy + half_d * scale)
        
        for i in range(pts + 1):
            y = half_d - (diameter * i / pts)
            x = x2_vertex + get_sag(r2, abs(y)) * scale
            path.lineTo(x, cy + y * scale)
            
        path.closeSubpath()
        
        painter.setPen(QPen(color, 2))
        painter.setBrush(QBrush(color))
        painter.drawPath(path)