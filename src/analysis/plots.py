"""
Matplotlib plotting helpers for the analysis dialogs.

These functions draw on a caller-supplied Axes so the GUI layer stays
thin: openlens.py builds the dialog and calls one of these with the
analyzer output. Everything lives next to the analyzer classes in
src/analysis/ instead of inline in window code.
"""

from typing import List

import numpy as np

from ..constants import (
    COLOR_LENS_BAD,
    COLOR_LENS_FILL,
    COLOR_LENS_R1,
    COLOR_LENS_R2,
    COLOR_LENS_RIM,
)
from ..geometry import LensGeometry
from ..optical_system import OpticalSystem


def draw_system_outline(ax, system: OpticalSystem) -> None:
    """Draw the lens element outlines of ``system`` onto ``ax`` (Z vs Y).

    Canonical convention: ``lens.thickness`` is the CENTER (vertex to
    vertex) thickness, matching the ray tracers, the ABCD matrix, the
    lensmaker equation, and ``LensGeometry``. The rim (edge) thickness is
    derived as ``thickness - sag1 + sag2`` at the clear aperture.
    """
    current_z = 0.0
    for i, element in enumerate(system.elements):
        lens = element.lens
        half_d = lens.diameter / 2
        thickness = lens.thickness

        # Shared outline (same helper as every 2D view), shifted so the
        # front vertex sits at current_z.
        outline = LensGeometry.lens_outline(lens, num_points=50)
        bad = not outline["feasible"]
        z1 = [current_z + x for x, _ in outline["front"]]
        y_front = [y for _, y in outline["front"]]
        z2 = [current_z + x for x, _ in outline["back"]]
        y_back = [y for _, y in outline["back"]]
        x1_edge = current_z + outline["x1_edge"]
        x2_edge = current_z + outline["x2_edge"]

        # Filled lens (matches editor's translucent fill) + colored outlines
        # Build closed polygon: front (top->bottom) -> bottom edge -> back (bottom->top) -> top edge
        try:
            from matplotlib.patches import Polygon

            poly_z = z1 + [x2_edge] + z2 + [x1_edge]
            poly_y = y_front + [half_d] + y_back + [-half_d]
            poly = Polygon(
                list(zip(poly_z, poly_y)),
                closed=True,
                facecolor=COLOR_LENS_BAD if bad else COLOR_LENS_FILL,
                edgecolor="none",
                alpha=0.3,
            )
            ax.add_patch(poly)
        except Exception:
            pass

        front_color = COLOR_LENS_BAD if bad else COLOR_LENS_R1
        back_color = COLOR_LENS_BAD if bad else COLOR_LENS_R2
        ax.plot(z1, y_front, color=front_color, alpha=0.9, linewidth=2)
        ax.plot(z2, y_back, color=back_color, alpha=0.9, linewidth=2)
        # Flat rims
        ax.plot(
            [x1_edge, x2_edge],
            [half_d, half_d],
            color=COLOR_LENS_RIM,
            alpha=0.7,
            linewidth=1,
        )
        ax.plot(
            [x1_edge, x2_edge],
            [-half_d, -half_d],
            color=COLOR_LENS_RIM,
            alpha=0.7,
            linewidth=1,
        )

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
