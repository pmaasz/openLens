"""
OpenLens PySide6 Assembly Visualization Widget
2D visualization of optical system (multiple lenses)
"""

from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QPen, QPainterPath, QBrush, QColor
from PySide6.QtCore import Qt
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from PySide6.QtGui import QPaintEvent

    from ...lens import Lens
    from ...optical_system import OpticalSystem


class AssemblyVisualizationWidget(QWidget):
    """2D visualization of optical system (multiple lenses)"""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialize the widget with its color palette.

        Args:
            parent: Optional parent widget.
        """
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

    def update_system(self, system: "OpticalSystem") -> None:
        """Update visualization with optical system

        Args:
            system: The optical system whose elements should be drawn.
        """
        self._system = system
        self.update()

    def paintEvent(self, event: "QPaintEvent") -> None:
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

    def _draw_lens(
        self,
        painter: QPainter,
        lens: "Lens",
        cx: float,
        cy: float,
        scale: float,
        color: QColor,
    ) -> None:
        """Draw a single lens

        Args:
            painter: Painter used for drawing.
            lens: The lens model to draw.
            cx: Horizontal center of the lens in widget coordinates.
            cy: Vertical center of the lens in widget coordinates.
            scale: Pixels per millimeter.
            color: Fill and outline color for the lens.
        """

        # Shared outline (same helper as every 2D view); ``color``
        # distinguishes elements in the assembly, surface/rim strokes use
        # the shared R1/R2 palette.
        from ...constants import COLOR_LENS_R1, COLOR_LENS_R2, COLOR_LENS_RIM, COLOR_LENS_BAD
        from ...geometry import LensGeometry

        half_d = lens.diameter / 2
        outline = LensGeometry.lens_outline(lens, num_points=50)
        bad = not outline["feasible"]
        bad_color = QColor(COLOR_LENS_BAD)

        def _to_screen(pt) -> tuple:
            """Map a vertex-frame (x, y) outline point to widget pixels."""
            return (cx + pt[0] * scale, cy + pt[1] * scale)

        x2_edge = cx + outline["x2_edge"] * scale

        path = QPainterPath()

        for i, pt in enumerate(outline["front"]):
            x, y = _to_screen(pt)
            if i == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)

        path.lineTo(x2_edge, cy + half_d * scale)

        for pt in outline["back"]:
            path.lineTo(*_to_screen(pt))

        path.closeSubpath()

        body = QColor(bad_color.red(), bad_color.green(), bad_color.blue(), 90) if bad else color
        painter.setPen(QPen(QColor(COLOR_LENS_RIM), 1))
        painter.setBrush(QBrush(body))
        painter.drawPath(path)

        surfaces = ((outline["front"], COLOR_LENS_R1), (outline["back"], COLOR_LENS_R2))
        for pts, hex_color in surfaces:
            surf = QPainterPath()
            for i, pt in enumerate(pts):
                x, y = _to_screen(pt)
                if i == 0:
                    surf.moveTo(x, y)
                else:
                    surf.lineTo(x, y)
            painter.setPen(QPen(bad_color if bad else QColor(hex_color), 2))
            painter.drawPath(surf)
