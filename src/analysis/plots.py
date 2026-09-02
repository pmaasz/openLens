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
    if y > r_a:
        return r_a
    sag = r_a - (r_a**2 - y**2) ** 0.5
    return sag if radius > 0 else -sag


def draw_system_outline(ax, system: OpticalSystem) -> None:
    """Draw the lens element outlines of ``system`` onto ``ax`` (Z vs Y)."""
    current_z = 0.0
    for i, element in enumerate(system.elements):
        lens = element.lens
        half_d = lens.diameter / 2
        y = [v / 10.0 for v in range(int(-half_d * 10), int(half_d * 10) + 1)]
        z1 = [current_z + _sag(lens.radius_of_curvature_1, yv) for yv in y]
        z2 = [
            current_z + lens.thickness + _sag(lens.radius_of_curvature_2, yv)
            for yv in y
        ]

        ax.plot(z1, y, "b-", alpha=0.5)
        ax.plot(z2, y, "b-", alpha=0.5)
        # Edges
        ax.plot([z1[0], z2[0]], [y[0], y[0]], "b-", alpha=0.5)
        ax.plot([z1[-1], z2[-1]], [y[-1], y[-1]], "b-", alpha=0.5)

        if i < len(system.air_gaps):
            current_z += lens.thickness + system.air_gaps[i].thickness
        else:
            current_z += lens.thickness


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
