"""
Matplotlib plotting helpers for the analysis dialogs.

These functions draw on a caller-supplied Axes so the GUI layer stays
thin: openlens.py builds the dialog and calls one of these with the
analyzer output. Everything lives next to the analyzer classes in
src/analysis/ instead of inline in window code.
"""

from typing import List

import numpy as np

from ..optical_system import OpticalSystem


def _sag(radius: float, y: float) -> float:
    """Sagitta of a spherical surface at aperture height ``y``."""
    if abs(radius) < 1e-6:
        return 0
    r_a = abs(radius)
    y_safe = min(abs(y), r_a)
    sag = r_a - (r_a**2 - y_safe**2) ** 0.5
    return sag if radius > 0 else -sag


def draw_system_outline(ax, system: OpticalSystem) -> None:
    """Draw the lens element outlines of ``system`` onto ``ax`` (Z vs Y).

    Uses the same edge-thickness convention as the 2D editor widgets
    (lens_viz_2d, simulation_viz, assembly_viz) so the ghost dialog
    matches the Editor tab: the rim-to-rim distance is ``lens.thickness``
    and the vertex separation is ``thickness + sag1 - sag2``. The
    previous center-thickness placement (``current_z + thickness + sag2``)
    produced a pointy/spindle outline for large apertures that did not
    match the editor.
    """
    current_z = 0.0
    for i, element in enumerate(system.elements):
        lens = element.lens
        half_d = lens.diameter / 2
        r1 = lens.radius_of_curvature_1
        r2 = lens.radius_of_curvature_2
        thickness = lens.thickness

        # Editor convention: front vertex at current_z, rim distance = thickness
        # Matches src/gui/widgets/lens_viz_2d.py:147 / simulation_viz:295
        sag1_edge = _sag(r1, half_d)
        x1_vertex = current_z
        x1_edge = x1_vertex + sag1_edge
        x2_edge = x1_edge + thickness
        sag2_edge = _sag(r2, half_d)
        x2_vertex = x2_edge - sag2_edge

        # Use same 50-point sampling as the editor widgets for pixel-perfect match
        pts = 50
        y_front = [-half_d + (2 * half_d * j / pts) for j in range(pts + 1)]
        z1 = [x1_vertex + _sag(r1, abs(yv)) for yv in y_front]
        y_back = [half_d - (2 * half_d * j / pts) for j in range(pts + 1)]
        z2 = [x2_vertex + _sag(r2, abs(yv)) for yv in y_back]

        # Filled lens (matches editor's translucent fill) + colored outlines
        # Build closed polygon: front (top->bottom) -> bottom edge -> back (bottom->top) -> top edge
        try:
            from matplotlib.patches import Polygon

            poly_z = z1 + [x2_edge] + z2 + [x1_edge]
            poly_y = y_front + [half_d] + y_back + [-half_d]
            poly = Polygon(
                list(zip(poly_z, poly_y)),
                closed=True,
                facecolor="#96c8e6",
                edgecolor="none",
                alpha=0.25,
            )
            ax.add_patch(poly)
        except Exception:
            pass

        ax.plot(z1, y_front, color="#0096ff", alpha=0.9, linewidth=1.5)
        ax.plot(z2, y_back, color="#00c864", alpha=0.9, linewidth=1.5)
        # Flat rims
        ax.plot([x1_edge, x2_edge], [half_d, half_d], color="#969696", alpha=0.7, linewidth=1)
        ax.plot([x1_edge, x2_edge], [-half_d, -half_d], color="#969696", alpha=0.7, linewidth=1)

        if i < len(system.air_gaps):
            current_z += thickness + system.air_gaps[i].thickness
        else:
            current_z += thickness


def plot_ghost_analysis(ax, system: OpticalSystem, ghosts) -> int:
    """Draw system outline plus ghost ray paths; returns path count."""
    draw_system_outline(ax, system)

    for ghost in ghosts:
        for ray in ghost.rays:
            # GhostPath.rays are Ray3D objects; .path holds Vector3 points
            if hasattr(ray, "path") and ray.path:
                zs = [p.x for p in ray.path]
                ys = [p.y for p in ray.path]
                ax.plot(zs, ys, "r--", alpha=0.3)

    ax.set_title(f"Ghost Reflection Analysis: {len(ghosts)} paths found")
    ax.set_xlabel("Z (mm)")
    ax.set_ylabel("Y (mm)")
    ax.grid(True, alpha=0.2)
    return len(ghosts)


def apply_dark_axis_theme(ax) -> None:
    """Style an Axes for the dark theme."""
    ax.set_facecolor("#1e1e1e")
    ax.tick_params(colors="#e0e0e0")
    ax.xaxis.label.set_color("#e0e0e0")
    ax.yaxis.label.set_color("#e0e0e0")
    ax.title.set_color("#e0e0e0")
    for spine in ax.spines.values():
        spine.set_edgecolor("#3f3f3f")


def plot_psf(ax, psf_data: dict) -> None:
    """Render a PSF intensity map (expects calculate_psf() output)."""
    img = psf_data["image"]
    if np.iscomplexobj(img):
        img = np.real(img)
    extent = [
        psf_data["z_axis"][0],
        psf_data["z_axis"][-1],
        psf_data["y_axis"][0],
        psf_data["y_axis"][-1],
    ]
    im = ax.imshow(img, extent=extent, cmap="viridis", origin="lower")
    ax.figure.colorbar(im, ax=ax, label="Relative Intensity")
    ax.set_title("Point Spread Function (Geometric)")
    ax.set_xlabel("Sagittal (mm)")
    ax.set_ylabel("Tangential (mm)")


def plot_mtf(ax, mtf_data: dict) -> None:
    """Plot tangential/sagittal MTF curves (expects calculate_mtf() output)."""
    freq = np.real(mtf_data["freq"])
    tan = np.real(mtf_data["mtf_tan"])
    sag = np.real(mtf_data["mtf_sag"])

    ax.plot(freq, tan, "r-", label="Tangential")
    ax.plot(freq, sag, "b--", label="Sagittal")

    ax.set_ylim(0, 1.05)
    ax.set_title("Modulation Transfer Function")
    ax.set_xlabel("Spatial Frequency (lp/mm)")
    ax.set_ylabel("Modulation")
    ax.legend()
    ax.grid(True, alpha=0.3)


def plot_wavefront(ax, wf_data) -> None:
    """Render exit-pupil wavefront error map (waves)."""
    data = np.real(wf_data) if np.iscomplexobj(wf_data) else wf_data
    im = ax.imshow(data, cmap="RdBu", origin="lower")
    ax.figure.colorbar(im, ax=ax, label="Wavefront Error (λ)")
    ax.set_title("Exit Pupil Wavefront Error")
    ax.set_xlabel("X Pupil")
    ax.set_ylabel("Y Pupil")
