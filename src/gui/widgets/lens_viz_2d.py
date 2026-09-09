from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QPoint, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QPainterPath, QBrush
from typing import Optional, TYPE_CHECKING

from ...constants import (
    COLOR_LENS_BAD,
    COLOR_LENS_FILL,
    COLOR_LENS_R1,
    COLOR_LENS_R2,
    COLOR_LENS_RIM,
)
from ...geometry import LensGeometry

if TYPE_CHECKING:
    from PySide6.QtGui import QMouseEvent, QPaintEvent

    from ...lens import Lens


class LensViz2DWidget(QWidget):
    """2D lens visualization"""

    # Signals for interactive manipulation
    property_changed = Signal(str, float)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialize the widget with default colors and interaction state.

        Args:
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self._lens = None
        self._view_mode = "2D"

        self.setMinimumSize(400, 300)
        self.setStyleSheet("background-color: #1e1e1e;")

        self._bg_color = QColor("#1e1e1e")
        # Shared lens palette (constants.py) so every 2D view matches.
        self._r1_color = QColor(COLOR_LENS_R1)
        self._r2_color = QColor(COLOR_LENS_R2)
        self._fill_color = QColor(COLOR_LENS_FILL)
        self._fill_color.setAlpha(80)
        self._edge_color = QColor(COLOR_LENS_RIM)
        self._bad_color = QColor(COLOR_LENS_BAD)
        self._text_color = QColor("#e0e0e0")
        self._axis_color = QColor("#666666")
        self._handle_color = QColor(255, 255, 255, 200)  # White for interactive handles

        # Interaction state
        self._active_handle = None  # 'r1', 'r2', 'thickness', 'diameter'
        self._last_mouse_pos = None
        self._handles = {}  # name -> (x, y)
        self._scale = 1.0
        self._cx = 0
        self._cy = 0

        self.setMouseTracking(True)

    def mousePressEvent(self, event: "QMouseEvent") -> None:
        """Select the handle under the mouse cursor, if any."""
        if not self._lens:
            return

        pos = event.position().toPoint()
        for name, h_pos in self._handles.items():
            dx = pos.x() - h_pos.x()
            dy = pos.y() - h_pos.y()
            if (dx * dx + dy * dy) < 100:  # 10px radius hit area
                self._active_handle = name
                self._last_mouse_pos = pos
                self.setCursor(Qt.ClosedHandCursor)
                break

    def mouseReleaseEvent(self, event: "QMouseEvent") -> None:
        """Deselect the active handle and restore the cursor."""
        self._active_handle = None
        self.setCursor(Qt.ArrowCursor)

    def mouseMoveEvent(self, event: "QMouseEvent") -> None:
        """Drag the active handle or update the cursor on hover."""
        if not self._lens:
            return

        pos = event.position().toPoint()
        if self._active_handle:
            dx = (pos.x() - self._last_mouse_pos.x()) / self._scale
            dy = (pos.y() - self._last_mouse_pos.y()) / self._scale

            if self._active_handle == "r1":
                # Dragging R1 vertex horizontally
                new_r1 = self._lens.radius_of_curvature_1 + dx
                # Snap to flat if close to zero
                if abs(new_r1) < 1.0:
                    new_r1 = 0.0
                self.property_changed.emit("r1", new_r1)
            elif self._active_handle == "r2":
                # Dragging R2 vertex horizontally
                new_r2 = self._lens.radius_of_curvature_2 + dx
                # Snap to flat if close to zero
                if abs(new_r2) < 1.0:
                    new_r2 = 0.0
                self.property_changed.emit("r2", new_r2)
            elif self._active_handle == "thickness":
                # Dragging right edge
                new_t = self._lens.thickness + dx
                if new_t < 0.1:
                    new_t = 0.1
                self.property_changed.emit("thickness", new_t)
            elif self._active_handle == "diameter":
                # Dragging top/bottom edge
                new_d = self._lens.diameter - 2 * dy  # Screen Y is inverted
                if new_d < 1.0:
                    new_d = 1.0
                self.property_changed.emit("diameter", new_d)

            self._last_mouse_pos = pos
        else:
            # Update cursor if hovering over a handle
            hovering = False
            for h_pos in self._handles.values():
                dx = pos.x() - h_pos.x()
                dy = pos.y() - h_pos.y()
                if (dx * dx + dy * dy) < 100:
                    hovering = True
                    break
            if hovering:
                self.setCursor(Qt.PointingHandCursor)
            else:
                self.setCursor(Qt.ArrowCursor)

    def set_view_mode(self, mode: str) -> None:
        """Set the view mode and schedule a repaint.

        Args:
            mode: View mode name (e.g. '2D').
        """
        self._view_mode = mode
        self.update()

    def update_lens(self, lens: "Lens") -> None:
        """Set the lens model to visualize and schedule a repaint.

        Args:
            lens: The lens model to draw.
        """
        self._lens = lens
        self.update()

    def paintEvent(self, event: "QPaintEvent") -> None:
        """Paint the grid, axis, lens cross-section and interactive handles."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w, h = self.width(), self.height()
        painter.fillRect(0, 0, w, h, self._bg_color)

        if not self._lens:
            return

        thickness = self._lens.thickness
        diameter = self._lens.diameter
        half_d = diameter / 2

        # Larger scale for bigger lens
        max_dim = max(thickness * 2, diameter, 100)
        self._scale = min(w, h) / max_dim * 0.85
        scale = self._scale
        cx, cy = w / 2, h / 2
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

        # Shared outline: front (top->bottom) and back (bottom->top) in the
        # vertex frame (front vertex at 0). Same helper as every 2D view.
        outline = LensGeometry.lens_outline(self._lens, num_points=50)
        x1_vertex = cx + outline["x1_vertex"] * scale
        x2_vertex = cx + outline["x2_vertex"] * scale
        x1_edge = cx + outline["x1_edge"] * scale
        x2_edge = cx + outline["x2_edge"] * scale

        def _to_screen(pt) -> tuple:
            """Map a vertex-frame (x, y) outline point to widget pixels."""
            return (cx + pt[0] * scale, cy + pt[1] * scale)

        # Clear handles
        self._handles = {}

        # Construct single coherent lens path for filling
        path_lens = QPainterPath()

        # 1. Front Surface (top to bottom)
        for i, pt in enumerate(outline["front"]):
            x, y = _to_screen(pt)
            if i == 0:
                path_lens.moveTo(x, y)
            else:
                path_lens.lineTo(x, y)

        # 2. Bottom Edge
        path_lens.lineTo(x2_edge, cy + half_d * scale)

        # 3. Back Surface (bottom to top)
        for pt in outline["back"]:
            path_lens.lineTo(*_to_screen(pt))

        # 4. Top Edge
        path_lens.closeSubpath()

        # Flag unrealizable geometry (edge <= 0: bowtie outline). Tint red.
        _infeasible = not outline["feasible"]
        _bad = self._bad_color
        _fill = (
            QColor(_bad.red(), _bad.green(), _bad.blue(), 90) if _infeasible else self._fill_color
        )
        _edge_c = (
            QColor(_bad.red(), _bad.green(), _bad.blue(), 220) if _infeasible else self._edge_color
        )

        # Fill and stroke lens
        painter.setPen(QPen(_edge_c, 1))
        painter.setBrush(QBrush(_fill))
        painter.drawPath(path_lens)

        if _infeasible:
            painter.setPen(QPen(QColor(_bad.red(), _bad.green(), _bad.blue(), 230), 1))
            painter.drawText(10, 20, "Unrealizable: surfaces intersect within aperture")

        # Highlight surfaces with colors
        # R1
        path_r1 = QPainterPath()
        for i, pt in enumerate(outline["front"]):
            x, y = _to_screen(pt)
            if i == 0:
                path_r1.moveTo(x, y)
            else:
                path_r1.lineTo(x, y)
        painter.setPen(QPen(self._r1_color if not _infeasible else _bad, 2))
        painter.drawPath(path_r1)

        # R2
        path_r2 = QPainterPath()
        for i, pt in enumerate(outline["back"]):
            x, y = _to_screen(pt)
            if i == 0:
                path_r2.moveTo(x, y)
            else:
                path_r2.lineTo(x, y)
        painter.setPen(QPen(self._r2_color if not _infeasible else _bad, 2))
        painter.drawPath(path_r2)

        # Draw handles (spaced out to avoid crowding)
        def draw_handle(p: QPainter, name: str, pos: QPoint, label: str = "") -> None:
            """Draw an interactive handle and register it for hit testing."""
            self._handles[name] = pos
            if self._active_handle == name:
                p.setPen(QPen(QColor(0, 255, 0), 2))
                p.setBrush(QBrush(QColor(0, 255, 0, 150)))
            else:
                p.setPen(QPen(Qt.white, 1))
                p.setBrush(QBrush(QColor(255, 255, 255, 50)))
            p.drawEllipse(pos, 6, 6)

        # R1 handle at vertex
        draw_handle(painter, "r1", QPoint(int(x1_vertex), int(cy)))
        # R2 handle at vertex
        draw_handle(painter, "r2", QPoint(int(x2_vertex), int(cy)))
        # Thickness handle at bottom center
        draw_handle(
            painter,
            "thickness",
            QPoint(int((x1_edge + x2_edge) / 2), int(cy + half_d * scale + 15)),
        )
        # Diameter handle at top center
        draw_handle(
            painter,
            "diameter",
            QPoint(int((x1_edge + x2_edge) / 2), int(cy - half_d * scale - 15)),
        )
