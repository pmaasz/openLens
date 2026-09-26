from PySide6.QtWidgets import QWidget, QVBoxLayout
from typing import Optional, TYPE_CHECKING

try:
    import numpy as np
except ImportError:
    np = None

if TYPE_CHECKING:
    from ...lens import Lens


class _3DVisualizationWidget(QWidget):
    """3D lens visualization using matplotlib"""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialize the widget and its embedded matplotlib canvas.

        Falls back to a placeholder label when matplotlib is unavailable.

        Args:
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self._lens = None
        self._canvas = None
        self._figure = None
        self._ax = None
        self._ax_lens = None
        self._ax_coords = None
        self._surface_profiles = {}

        self.setMinimumSize(400, 300)
        self.setStyleSheet("background-color: #1e1e1e;")

        try:
            import matplotlib

            matplotlib.use("Qt5Agg")
            from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
            from matplotlib.figure import Figure

            self._figure = Figure(figsize=(6, 5), facecolor="#1e1e1e")
            self._canvas = FigureCanvasQTAgg(self._figure)
            self._canvas.setStyleSheet("background-color: #1e1e1e;")

            layout = QVBoxLayout(self)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(self._canvas)

            self._figure.subplots_adjust(left=0.05, right=0.95, top=0.95, bottom=0.05)

            # Fixed coordinate system (background)
            self._ax_coords = self._figure.add_subplot(
                111, projection="3d", facecolor="#1e1e1e", computed_zorder=False
            )
            self._ax_coords.view_init(elev=20, azim=45)
            self._ax_coords.mouse_init()

            # Rotatable lens geometry (foreground)
            self._ax_lens = self._figure.add_subplot(
                111, projection="3d", facecolor="none", computed_zorder=False
            )
            self._ax_lens.set_position(self._ax_coords.get_position())
            self._ax_lens.patch.set_alpha(0)
            self._ax_lens.view_init(elev=20, azim=45)
            self._ax_lens.set_axis_off()
            self._ax_lens.mouse_init()

            # Use lens axis for main reference
            self._ax = self._ax_lens

            # Configure coordinate appearance
            self._ax_coords.set_xlabel("X (mm)", color="#666")
            self._ax_coords.set_ylabel("Y (mm)", color="#666")
            self._ax_coords.set_zlabel("Z (mm)", color="#666")
            self._ax_coords.tick_params(colors="#555", labelsize=8)
            self._ax_coords.xaxis.pane.set_facecolor("#1e1e1e")
            self._ax_coords.yaxis.pane.set_facecolor("#1e1e1e")
            self._ax_coords.zaxis.pane.set_facecolor("#1e1e1e")
            self._ax_coords.xaxis.pane.set_alpha(0.9)
            self._ax_coords.yaxis.pane.set_alpha(0.9)
            self._ax_coords.zaxis.pane.set_alpha(0.9)

        except ImportError:
            from PySide6.QtWidgets import QLabel

            layout = QVBoxLayout(self)
            lbl = QLabel("Install matplotlib\nfor 3D view")
            lbl.setStyleSheet("color: #888; padding: 50px;")
            layout.addWidget(lbl)

    def update_lens(self, lens: "Lens") -> None:
        """Redraw the 3D lens geometry for the given lens.

        The radial mesh is built from the same Fresnel-aware profile as the
        2D outline, including the vertical step at every groove boundary.

        Args:
            lens: The lens model to render.
        """
        if not lens or not self._ax or not self._figure or np is None:
            return

        self._lens = lens
        self._ax_lens.clear()
        self._ax_lens.set_axis_off()

        from ...constants import COLOR_LENS_BAD, COLOR_LENS_R1, COLOR_LENS_R2, COLOR_LENS_RIM
        from ...geometry import LensGeometry

        thickness = lens.thickness
        diameter = lens.diameter
        max_r = abs(diameter) / 2.0
        facet_count = max(
            len(LensGeometry.fresnel_facets(lens, 1)),
            len(LensGeometry.fresnel_facets(lens, 2)),
        )
        display_limit = 512 if facet_count <= 256 else 128
        front_profile = LensGeometry.surface_profile(
            lens, 1, num_points=14, max_points=display_limit
        )
        back_profile = LensGeometry.surface_profile(
            lens, 2, num_points=14, max_points=display_limit
        )
        self._surface_profiles = {1: front_profile, 2: back_profile}

        x1_vertex = 0.0
        x2_vertex = thickness
        x1_edge = x1_vertex + front_profile[-1][0]
        x2_edge = x2_vertex + back_profile[-1][0]
        outline = LensGeometry.lens_outline(lens, num_points=50, max_points=display_limit)
        edge_thickness = outline.get("minimum_thickness", outline.get("edge_thickness"))
        _bad = edge_thickness is None or edge_thickness <= 0
        _c1 = COLOR_LENS_BAD if _bad else COLOR_LENS_R1
        _c2 = COLOR_LENS_BAD if _bad else COLOR_LENS_R2

        theta = np.linspace(0, 2 * np.pi, 36)
        x_front = max_r * np.cos(theta)
        y_front = max_r * np.sin(theta)
        z_front = np.full_like(theta, x1_edge)
        self._ax.plot(x_front, y_front, z_front, color=_c1, linewidth=2)

        x_back = max_r * np.cos(theta)
        y_back = max_r * np.sin(theta)
        z_back = np.full_like(theta, x2_edge)
        self._ax.plot(x_back, y_back, z_back, color=_c2, linewidth=2)

        for index in range(0, len(theta), 2):
            self._ax.plot(
                [x_front[index], x_back[index]],
                [y_front[index], y_back[index]],
                [z_front[index], z_back[index]],
                color=COLOR_LENS_RIM,
                linewidth=0.5,
            )

        theta_vals = np.linspace(0, 2 * np.pi, 25)
        for profile, offset, color in (
            (front_profile, x1_vertex, _c1),
            (back_profile, x2_vertex, _c2),
        ):
            radial = np.asarray([point[1] for point in profile], dtype=float)
            axial = np.asarray([point[0] for point in profile], dtype=float)
            R, THETA = np.meshgrid(radial, theta_vals)
            Z = offset + axial[None, :] * np.ones((len(theta_vals), 1))
            X = R * np.cos(THETA)
            Y = R * np.sin(THETA)
            rstride = 1 if getattr(lens, "is_fresnel", False) else 2
            self._ax.plot_surface(X, Y, Z, alpha=0.5, color=color, rstride=rstride, cstride=2)

        for surface, offset, color in (
            (1, x1_vertex, _c1),
            (2, x2_vertex, _c2),
        ):
            for radius, before, after in LensGeometry.groove_steps(
                lens, surface, max_steps=display_limit
            ):
                if abs(after - before) <= 1e-12:
                    continue
                for axial in (offset + before, offset + after):
                    self._ax.plot(
                        radius * np.cos(theta),
                        radius * np.sin(theta),
                        np.full_like(theta, axial),
                        color=color,
                        linewidth=0.7,
                    )

        z_values = [0.0, thickness]
        z_values.extend(point[0] for point in front_profile)
        z_values.extend(thickness + point[0] for point in back_profile)
        z_min = min(z_values)
        z_max = max(z_values)
        padding = max(diameter, thickness) * 0.3
        limit = max(diameter, thickness) / 2 + padding
        self._ax.set_xlim([-limit, limit])
        self._ax.set_ylim([-limit, limit])
        self._ax.set_zlim([z_min - padding, z_max + padding])
        if hasattr(self, "_ax_coords"):
            self._ax_coords.set_xlim([-limit, limit])
            self._ax_coords.set_ylim([-limit, limit])
            self._ax_coords.set_zlim([z_min - padding, z_max + padding])

        self._ax.view_init(elev=20, azim=45)

        dim_text = f"D={diameter:.0f}mm  t={thickness:.1f}mm"
        if getattr(lens, "is_fresnel", False):
            pitch = float(getattr(lens, "groove_pitch", 0.0))
            grooves = int(max_r / pitch) if pitch > 0 else 0
            dim_text += f"  Fresnel ({grooves} grooves)"
        if _bad:
            dim_text += "  (infeasible)"
        self._ax.text2D(
            0.02,
            0.98,
            dim_text,
            transform=self._ax.transAxes,
            color=COLOR_LENS_BAD if _bad else "white",
            fontsize=10,
            fontweight="bold",
        )

        self._canvas.draw()
