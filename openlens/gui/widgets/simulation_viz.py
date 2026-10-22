from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
import logging
import math
from typing import Any, Callable, Optional, Sequence, TYPE_CHECKING, Union

from ...constants import COLOR_LENS_FILL, NM_TO_MM, WAVELENGTH_GREEN
from ..theme import DARK, get_palette

if TYPE_CHECKING:
    from PySide6.QtGui import QKeyEvent, QMouseEvent, QPaintEvent, QWheelEvent

    from ...lens import Lens
    from ...optical_system import OpticalSystem
    from ...ray_tracer import SystemRayTracer

logger = logging.getLogger(__name__)


class SimulationVisualizationWidget(QWidget):
    """2D ray tracing simulation visualization widget"""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialize the widget with default view and display state.

        Args:
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self._lens = None
        self._system = None
        # Applied to the model at trace time (a conditioned copy, for
        # instance). The widget keeps the live model, so an edit is picked up
        # by the next trace.
        self._conditioner = None
        self._rays = []
        self._ray_groups = []
        self._wavelength = WAVELENGTH_GREEN  # Primary wavelength in nm
        self._wavelengths = [WAVELENGTH_GREEN]

        self.setMinimumSize(400, 300)
        self._theme = DARK
        self.set_theme(DARK)
        # Shared glass fill so simulation matches the editor view.
        self._lens_color = QColor(COLOR_LENS_FILL)
        self._lens_color.setAlpha(80)
        self._ray_color = QColor(255, 200, 0, 200)
        self._ghost_color = QColor(255, 100, 100, 180)
        self._show_ghosts = False
        self._show_image_sim = False
        self._image_pattern = "Star"
        # Parameters of the last run, kept so refresh() can re-trace with the
        # same settings. Without them a refresh would have to invent them, and
        # "re-trace" would silently mean "re-trace differently".
        self._last_num_rays = 11
        self._last_angle = 0.0
        self._last_source_height = 0.0

        # Zoom and pan state
        self._zoom = 1.0
        self._pan_x = 0
        self._pan_y = 0
        self._is_panning = False
        self._last_mouse_x = 0
        self._last_mouse_y = 0

        # Install event filters
        self.setFocusPolicy(Qt.StrongFocus)

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
            f"background-color: {palette['plot_bg']}; "
            f"border: 2px solid {palette['canvas_border']};"
        )
        self.update()

    @staticmethod
    def wavelength_to_color(wavelength: float) -> QColor:
        """Convert wavelength (nm) to RGB color

        Args:
            wavelength: Wavelength in nanometers (clamped to 380-780 nm).

        Returns:
            A QColor approximating the spectral color at that wavelength.
        """
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

    def wheelEvent(self, event: "QWheelEvent") -> None:
        """Handle mouse wheel for zooming"""
        if event.angleDelta().y() > 0:
            self._zoom *= 1.1
        else:
            self._zoom /= 1.1
        self._zoom = max(0.1, min(self._zoom, 50.0))
        self.update()

    def mousePressEvent(self, event: "QMouseEvent") -> None:
        """Start panning on mouse press"""
        if event.button() == Qt.LeftButton:
            self._is_panning = True
            self._last_mouse_x = event.position().x()
            self._last_mouse_y = event.position().y()

    def mouseMoveEvent(self, event: "QMouseEvent") -> None:
        """Pan the view when dragging"""
        if self._is_panning:
            dx = event.position().x() - self._last_mouse_x
            dy = event.position().y() - self._last_mouse_y
            self._pan_x += dx
            self._pan_y -= dy  # Invert because screen Y is down
            self._last_mouse_x = event.position().x()
            self._last_mouse_y = event.position().y()
            self.update()

    def mouseReleaseEvent(self, event: "QMouseEvent") -> None:
        """Stop panning on mouse release"""
        if event.button() == Qt.LeftButton:
            self._is_panning = False

    def keyPressEvent(self, event: "QKeyEvent") -> None:
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

    def reset_view(self) -> None:
        """Reset zoom and pan"""
        self._zoom = 1.0
        self._pan_x = 0
        self._pan_y = 0
        self.update()

    def run_simulation(
        self,
        lens_or_system: Union["Lens", "OpticalSystem"],
        num_rays: int = 11,
        angle: float = 0,
        source_height: float = 0,
        show_ghosts: bool = False,
        wavelength: float = WAVELENGTH_GREEN,
        wavelengths: Optional[Sequence[float]] = None,
        conditioner: Optional[Callable[[Any], Any]] = None,
    ) -> None:
        """Run ray tracing simulation

        Args:
            lens_or_system: The lens model or optical system to trace.
            num_rays: Number of rays to trace across the aperture.
            angle: Field angle of the ray fan in degrees.
            source_height: Vertical offset of the ray fan origin (mm).
            show_ghosts: Whether to trace ghost rays from internal
                reflections.
            wavelength: Single wavelength in nanometers, kept for callers
                that trace one colour. Used to select the tracer's dispersive
                index and the ray colour.
            wavelengths: Multiple wavelengths in nanometers. Each gets its
                own trace group and spectral colour; duplicates are ignored.
                When given, ``wavelength`` is ignored.
            conditioner: Applied to the model at trace time, returning the
                model to trace (a conditioned copy, for instance). The widget
                keeps a live reference to the model, so an edit is picked up
                by the next trace; the environment is applied here rather
                than once, so a trace never works on a stale snapshot.
        """
        from ...optical_system import OpticalSystem

        if isinstance(lens_or_system, OpticalSystem):
            self._system = lens_or_system
            self._lens = None
        else:
            self._lens = lens_or_system
            self._system = None
        self._conditioner = conditioner

        selected = wavelengths if wavelengths is not None else [wavelength]
        unique = [float(nm) for nm in dict.fromkeys(selected)]
        self._wavelengths = unique or [WAVELENGTH_GREEN]

        self._rays = []
        self._ray_groups = []
        self._ghost_rays = []
        self._show_ghosts = show_ghosts
        self._wavelength = self._wavelengths[0]
        self._last_num_rays = num_rays
        self._last_angle = angle
        self._last_source_height = source_height
        self._ray_color = self.wavelength_to_color(self._wavelength)

        try:
            from ...ray_tracer import LensRayTracer, Ray, SystemRayTracer

            # The model to trace: the live one, conditioned for the
            # environment. The live model is what the widget holds, so an
            # edit is picked up by the next trace.
            traced = self._traced_target()
            system = traced if isinstance(traced, OpticalSystem) else None
            lens = None if system is not None else traced

            # Use appropriate tracer. Each wavelength gets its own tracer so
            # the dispersion curve is evaluated once per element, not per ray.
            if system is not None:
                diameter = system.elements[0].lens.diameter if system.elements else 25.0
            else:
                diameter = lens.diameter if lens is not None else 25.0

            angle_rad = angle * math.pi / 180.0

            for trace_wavelength in self._wavelengths:
                group = []
                color = self.wavelength_to_color(trace_wavelength)
                try:
                    if system is not None:
                        tracer = SystemRayTracer(system, wavelength_nm=trace_wavelength)
                    else:
                        tracer = LensRayTracer(lens, wavelength_nm=trace_wavelength)

                    for i in range(num_rays):
                        if num_rays == 1:
                            h = 0
                        else:
                            h = -diameter / 2 + diameter * i / (num_rays - 1)

                        # wavelength_mm has to be set explicitly; the Ray
                        # default is green independent of the tracer index.
                        ray = Ray(
                            -100,
                            h + source_height,
                            angle_rad=angle_rad,
                            wavelength_mm=trace_wavelength * NM_TO_MM,
                        )
                        tracer.trace_ray(ray)
                        group.append(ray)
                        self._rays.append(ray)
                except Exception as e:
                    logger.error("Simulation failed at %.1f nm: %s", trace_wavelength, e)
                self._ray_groups.append((color, group))

            if show_ghosts:
                if system is not None:
                    self._run_ghost_analysis(system, SystemRayTracer(system))
                elif lens is not None:
                    # Wrap lens in temporary system for GhostAnalyzer
                    temp_system = OpticalSystem(name="Ghost Analysis")
                    temp_system.add_lens(lens)
                    self._run_ghost_analysis(temp_system, LensRayTracer(lens))

        except Exception as e:
            logger.error("Simulation failed: %s", e)

        self.update()

    def _traced_target(self) -> Any:
        """The model to trace: the live one, conditioned for the environment.

        The widget holds a live reference to the model, so an edit is picked
        up by the next trace. The environment (a temperature, a pressure) is
        applied here, at trace time: applying it once and storing the result
        left the widget with a snapshot, and every later edit was silently
        discarded.
        """
        target = self._system if self._system is not None else self._lens
        if target is None:
            return None
        if self._conditioner is not None:
            return self._conditioner(target)
        return target

    def _run_ghost_analysis(self, system: "OpticalSystem", tracer: "SystemRayTracer") -> None:
        """Run ghost analysis for 2nd order reflections"""
        try:
            from ...analysis.ghost import GhostAnalyzer

            analyzer = GhostAnalyzer(system)
            ghosts = analyzer.trace_ghosts(num_rays=3)

            for ghost in ghosts:
                if ghost.rays:
                    self._ghost_rays.append(ghost.rays)
        except Exception as e:
            logger.error("Ghost analysis failed: %s", e)

    def run_image_simulation(self, lens: "Lens", pattern: str = "Star") -> None:
        """Run image simulation pattern through lens

        Args:
            lens: The lens model to simulate the image for.
            pattern: Image pattern name ('Star', 'Grid' or 'USAF 1951').
        """
        self._lens = lens
        self._show_image_sim = True
        self._image_pattern = pattern
        self.update()

    def clear_simulation(self) -> None:
        """Clear simulation results"""
        self._rays = []
        self._ray_groups = []
        self._ghost_rays = []
        self._lens = None
        self._show_image_sim = False
        self.update()

    def refresh(self) -> None:
        """Re-trace the current lens or system with the last run's settings.

        The widget holds a *live reference* to the lens, so after an edit the
        drawn lens is the new one while the drawn rays still belong to the old
        one - the two disagree, and nothing about the display says so. This
        re-runs the trace so the rays match what is being drawn.

        A refresh is not a re-configure: the wavelength, ray count, angle,
        source height and ghost setting are the ones the user last chose, not
        defaults. Anything else would make "refresh" a second, invisible way of
        changing the simulation.
        """
        if self._show_image_sim:
            # An image simulation draws from the lens directly and has no rays
            # to re-trace; repainting picks up the edit on its own.
            self.update()
            return

        # The live model, not the last traced one: the environment is applied
        # by run_simulation, so the trace works on the current design.
        live = self._system if self._system is not None else self._lens
        if live is None:
            self.update()
            return

        self.run_simulation(
            live,
            num_rays=self._last_num_rays,
            angle=self._last_angle,
            source_height=self._last_source_height,
            show_ghosts=self._show_ghosts,
            wavelengths=self._wavelengths,
            conditioner=self._conditioner,
        )
        self.update()

    def paintEvent(self, event: "QPaintEvent") -> None:
        """Paint the simulation"""
        from PySide6.QtGui import QPainter, QPen, QColor, QPainterPath, QBrush

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()

        painter.fillRect(0, 0, w, h, self._bg_color)

        if not self._lens and not self._system:
            painter.setPen(QPen(self._text_color, 1))
            painter.drawText(w // 2 - 80, h // 2, "Run simulation to see rays")
            return

        # Draw axis
        painter.setPen(QPen(self._axis_color, 1, Qt.DashLine))
        painter.drawLine(0, h // 2, w, h // 2)

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

        def draw_single_lens(
            pnt: QPainter,
            lens: "Lens",
            start_x: float,
            center_y: float,
            sc: float,
            color: QColor,
        ) -> None:
            """Draw the filled cross-section of a single lens.

            Shape comes from the shared LensGeometry outline (same as every
            2D view); ``color`` only tints the glass body.
            """
            from ...constants import COLOR_LENS_R1, COLOR_LENS_R2, COLOR_LENS_RIM, COLOR_LENS_BAD
            from ...geometry import LensGeometry

            half_d = lens.diameter / 2
            outline = LensGeometry.lens_outline(lens, num_points=50, max_points=2000)
            bad = not outline["feasible"]
            bad_color = QColor(COLOR_LENS_BAD)

            def _to_screen(pt) -> tuple:
                """Map a vertex-frame (x, y) outline point to widget pixels."""
                return (start_x + pt[0] * sc, center_y + pt[1] * sc)

            x2_edge = start_x + outline["x2_edge"] * sc

            path = QPainterPath()

            # 1. Front Surface (top to bottom)
            for i, pt in enumerate(outline["front"]):
                x, y = _to_screen(pt)
                if i == 0:
                    path.moveTo(x, y)
                else:
                    path.lineTo(x, y)

            # 2. Bottom Edge
            path.lineTo(x2_edge, center_y + half_d * sc)

            # 3. Back Surface (bottom to top)
            for pt in outline["back"]:
                path.lineTo(*_to_screen(pt))

            # 4. Top Edge
            path.closeSubpath()

            body = (
                QColor(bad_color.red(), bad_color.green(), bad_color.blue(), 90) if bad else color
            )
            pnt.setPen(QPen(QColor(COLOR_LENS_RIM), 1))
            pnt.setBrush(QBrush(body))
            pnt.drawPath(path)

            # Surface highlights use the shared R1/R2 palette (red if bad).
            surfaces = ((outline["front"], COLOR_LENS_R1), (outline["back"], COLOR_LENS_R2))
            for pts, hex_color in surfaces:
                surf = QPainterPath()
                for i, pt in enumerate(pts):
                    x, y = _to_screen(pt)
                    if i == 0:
                        surf.moveTo(x, y)
                    else:
                        surf.lineTo(x, y)
                stroke = bad_color if bad else QColor(hex_color)
                pnt.setPen(QPen(stroke, 2))
                pnt.drawPath(surf)

        # Draw lenses
        if self._system:
            for element in self._system.elements:
                draw_single_lens(
                    painter,
                    element.lens,
                    cx + element.position * scale,
                    cy,
                    scale,
                    self._lens_color,
                )
        else:
            draw_single_lens(painter, self._lens, cx, cy, scale, self._lens_color)

        # Draw rays, one spectral colour per wavelength group. Additive
        # blending makes overlapping spectral lines read as white light
        # instead of letting whichever wavelength is drawn last repaint them.
        ray_groups = self._ray_groups or [(self._ray_color, self._rays)]
        if len(ray_groups) > 1:
            painter.setCompositionMode(QPainter.CompositionMode_Plus)
        for color, rays in ray_groups:
            painter.setPen(QPen(color, 1.5))
            for ray in rays:
                if len(ray.path) < 2:
                    continue
                for j in range(len(ray.path) - 1):
                    p1, p2 = ray.path[j], ray.path[j + 1]
                    if hasattr(p1, "x"):
                        x1, y1, x2, y2 = p1.x, p1.y, p2.x, p2.y
                    else:
                        x1, y1, x2, y2 = p1[0], p1[1], p2[0], p2[1]
                    painter.drawLine(
                        int(cx + x1 * scale),
                        int(cy - y1 * scale),
                        int(cx + x2 * scale),
                        int(cy - y2 * scale),
                    )
        painter.setCompositionMode(QPainter.CompositionMode_SourceOver)

        # Ghost rays
        if self._show_ghosts and self._ghost_rays:
            painter.setPen(QPen(self._ghost_color, 1))
            for ghost_path in self._ghost_rays:
                for ray in ghost_path:
                    if len(ray.path) < 2:
                        continue
                    for j in range(len(ray.path) - 1):
                        p1, p2 = ray.path[j], ray.path[j + 1]
                        if hasattr(p1, "x"):
                            x1, y1, x2, y2 = p1.x, p1.y, p2.x, p2.y
                        else:
                            x1, y1, x2, y2 = p1[0], p1[1], p2[0], p2[1]
                        painter.drawLine(
                            int(cx + x1 * scale),
                            int(cy - y1 * scale),
                            int(cx + x2 * scale),
                            int(cy - y2 * scale),
                        )

        if self._show_image_sim and self._lens:
            painter.setPen(QPen(QColor(0, 255, 136), 2))
            cx_img = w // 2
            cy_img = h // 2
            pattern = self._image_pattern

            if pattern == "Star":
                for i in range(8):
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
                        size = 5 * (1.122**i)
                        x = cx_img - 50 + j * 20
                        y = cy_img - 50 + i * 15
                        painter.drawRect(int(x), int(y), int(size), int(size))
