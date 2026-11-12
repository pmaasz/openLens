"""
OpenLens PySide6 Assembly Visualization Widget
2D visualization of optical system (multiple lenses)
"""

from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QPen, QPainterPath, QBrush, QColor
from PySide6.QtCore import Qt, QRectF
from typing import Optional, TYPE_CHECKING

from ..theme import DARK, get_palette

if TYPE_CHECKING:
    from PySide6.QtGui import QPaintEvent

    from ...lens import Lens
    from ...optical_system import OpticalSystem
    from ...casing import Casing


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
        self._theme = DARK
        self.set_theme(DARK)

        self._lens_colors = [
            QColor(0, 120, 212, 150),
            QColor(0, 180, 100, 150),
            QColor(200, 100, 0, 150),
            QColor(150, 50, 200, 150),
        ]

    def set_theme(self, theme: str = DARK) -> None:
        """Repaint with *theme*'s canvas colours.

        Args:
            theme: "dark" or "light".
        """
        palette = get_palette(theme)
        self._theme = theme
        self._bg_color = QColor(palette["plot_bg"])
        self._axis_color = QColor(palette["plot_axis"])
        self._text_color = QColor(palette["plot_text"])
        self.setStyleSheet(
            f"background-color: {palette['plot_bg']}; " f"border: 1px solid {palette['border']};"
        )
        self.update()

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
        casing = getattr(self._system, "casing", None)
        if casing is not None:
            max_diameter = max(max_diameter, casing.outer_diameter)
        total_thickness = max(
            total_thickness,
            casing.end_x if casing is not None else total_thickness,
        )

        # Floor the divisor like the other 2D views: Lens accepts a zero
        # thickness and diameter, so a degenerate model would otherwise
        # divide by zero inside the paint event on every repaint.
        max_dim = max(total_thickness * 1.5, max_diameter * 1.3, 1.0)
        scale = min(w, h) / max_dim / 2

        cx = 30
        cy = h / 2

        painter.setPen(QPen(self._axis_color, 1, Qt.DashLine))
        painter.drawLine(0, cy, w, cy)

        if casing is not None:
            self._draw_casing(
                painter, casing, cx - self._system.elements[0].position * scale, cy, scale
            )

        for i, element in enumerate(self._system.elements):
            lens = element.lens
            color = self._lens_colors[i % len(self._lens_colors)]

            self._draw_lens(painter, lens, cx, cy, scale, color)

            if i < len(self._system.air_gaps):
                cx += lens.thickness * scale + self._system.air_gaps[i].thickness * scale
            else:
                cx += lens.thickness * scale

    def _draw_casing(
        self,
        painter: QPainter,
        casing: "Casing",
        origin_x: float,
        cy: float,
        scale: float,
    ) -> None:
        """Draw the casing's two open-ended walls to scale.

        Args:
            painter: Painter used for drawing.
            casing: Casing model in assembly-axis coordinates (mm).
            origin_x: Screen x of model x = 0.
            cy: Screen y of the optical axis.
            scale: Pixels per millimeter.
        """
        from ...constants import COLOR_CASING

        color = QColor(COLOR_CASING)
        fill = QColor(color.red(), color.green(), color.blue(), 90)
        left = origin_x + casing.start_x * scale
        width = casing.length * scale
        inner = casing.inner_radius * scale
        wall = casing.wall_thickness * scale

        painter.save()
        painter.setPen(QPen(color, 1))
        painter.setBrush(QBrush(fill))
        painter.drawRect(QRectF(left, cy - inner - wall, width, wall))
        painter.drawRect(QRectF(left, cy + inner, width, wall))
        painter.restore()

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

        outline = LensGeometry.lens_outline(lens, num_points=50, max_points=2000)
        bad = not outline["feasible"]
        bad_color = QColor(COLOR_LENS_BAD)

        def _to_screen(pt) -> tuple:
            """Map a vertex-frame (x, y) outline point to widget pixels."""
            return (cx + pt[0] * scale, cy + pt[1] * scale)

        path = QPainterPath()

        for i, pt in enumerate(outline["front"]):
            x, y = _to_screen(pt)
            if i == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)

        # Rim chain, top side (front rim -> back rim), then the mirrored
        # chain after the back surface.
        for pt in outline["edge"][1:]:
            path.lineTo(*_to_screen(pt))

        for pt in outline["back"]:
            path.lineTo(*_to_screen(pt))

        for x, radius in reversed(outline["edge"][1:-1]):
            path.lineTo(*_to_screen((x, -radius)))

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
