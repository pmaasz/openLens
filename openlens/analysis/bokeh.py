"""Out-of-focus rendering (bokeh) from the aperture stop shape.

A defocused point source images the aperture stop: a plain circle gives a
disc, iris blades give a polygon, an annular stop gives a ring, and spider
vanes notch the outline. Rays are traced through the real stop opening to a
plane offset from focus and collected into an image, so the rendering follows
the geometry the tracers already use. Diffraction is left to ``psf_mtf``; the
geometric blur dominates as soon as the defocus is visible.
"""

import math
from typing import Any, Dict, Optional

from ..constants import EPSILON, NM_TO_MM, WAVELENGTH_GREEN
from ..fields import launch_field_ray
from ..ray_tracer import SystemRayTracer3D
from .paraxial import resolve_image_plane_x

try:
    import numpy as np

    HAS_NUMPY = True
except ImportError:
    np = None  # type: ignore[assignment]
    HAS_NUMPY = False


class BokehRenderer:
    """Render the defocused image of the aperture stop."""

    def __init__(self, system: Any) -> None:
        """Bind the renderer to *system*."""
        self.system = system

    def render(
        self,
        defocus_mm: float = 1.0,
        wavelength_nm: float = WAVELENGTH_GREEN,
        pixels: int = 96,
        field_angle_deg: float = 0.0,
        sensor_size_mm: Optional[float] = None,
        rays: int = 3000,
    ) -> Dict[str, Any]:
        """Return the geometric defocused image of the stop opening.

        Args:
            defocus_mm: Image-plane offset from focus, in mm.
            wavelength_nm: Wavelength in nm.
            pixels: Output grid size per axis.
            field_angle_deg: Field angle in degrees.
            sensor_size_mm: Output window size. None sizes the window from
                the traced blur.
            rays: Number of rays sampled over the stop opening.

        Returns:
            A ``calculate_psf``-shaped payload: ``image``, ``y_axis``,
            ``z_axis``, plus ``defocus_mm`` and ``blur_diameter_mm``.

        Raises:
            ImportError: If numpy is unavailable.
            ValueError: If the defocus is not finite or the system is empty.
        """
        if not HAS_NUMPY:
            raise ImportError("bokeh rendering requires numpy")
        if not math.isfinite(float(defocus_mm)):
            raise ValueError("defocus must be finite")
        if not self.system.elements:
            raise ValueError("cannot render bokeh for an empty system")

        plane = resolve_image_plane_x(self.system, wavelength_nm)
        if plane is None:
            raise ValueError("cannot render bokeh without an image plane")
        target_x = plane + float(defocus_mm)
        wavelength_mm = wavelength_nm * NM_TO_MM

        saved = [
            (element.lens, element.lens.wavelength, element.lens.refractive_index)
            for element in self.system.elements
        ]
        tracer = SystemRayTracer3D(self.system)
        points = []
        try:
            for lens, _, _ in saved:
                lens.update_refractive_index(wavelength_nm=wavelength_nm)

            radius = self._sample_radius()
            for y, z in self._stop_samples(radius, max(int(rays), 1)):
                ray = launch_field_ray(
                    self.system,
                    angle_y_deg=field_angle_deg,
                    pupil_y=y,
                    pupil_z=z,
                    wavelength_mm=wavelength_mm,
                )
                tracer.trace_ray(ray)
                if ray.terminated or abs(ray.direction.x) < EPSILON:
                    continue
                t = (target_x - ray.origin.x) / ray.direction.x
                if t < 0.0:
                    continue
                hit = ray.origin + ray.direction * t
                points.append((hit.y, hit.z))
        finally:
            for lens, wavelength, index in saved:
                lens.wavelength = wavelength
                lens.refractive_index = index

        if not points:
            raise ValueError("no ray reached the defocused plane; check the stop")

        array = np.asarray(points, dtype=float)
        center_y = float(array[:, 0].mean())
        center_z = float(array[:, 1].mean())
        radii = np.hypot(array[:, 0] - center_y, array[:, 1] - center_z)
        blur = 2.0 * float(radii.max())
        half = sensor_size_mm / 2.0 if sensor_size_mm else max(1.1 * blur / 2.0, 0.01)

        y_axis = np.linspace(center_y - half, center_y + half, pixels)
        z_axis = np.linspace(center_z - half, center_z + half, pixels)
        image, _, _ = np.histogram2d(
            array[:, 0],
            array[:, 1],
            bins=pixels,
            range=[
                [float(y_axis[0]), float(y_axis[-1])],
                [float(z_axis[0]), float(z_axis[-1])],
            ],
        )
        peak = float(image.max())
        if peak > 0.0:
            image = image / peak

        return {
            "image": image,
            "y_axis": y_axis,
            "z_axis": z_axis,
            "defocus_mm": float(defocus_mm),
            "blur_diameter_mm": blur,
            "ray_count": int(array.shape[0]),
        }

    def _sample_radius(self) -> float:
        """Entrance-pupil radius that maps onto the stop opening."""
        entrance = float(self.system.elements[0].lens.diameter) / 2.0
        stop = self.system.get_aperture_stop()
        if stop is None or not stop.get("diameter"):
            return entrance
        stop_semi = float(stop["diameter"]) / 2.0
        return min(entrance, stop_semi) if entrance > 0.0 else stop_semi

    @staticmethod
    def _stop_samples(radius: float, count: int):
        """Area-uniform points over a disc (Vogel spiral)."""
        golden = math.pi * (3.0 - math.sqrt(5.0))
        for index in range(count):
            r = radius * math.sqrt((index + 0.5) / count)
            theta = index * golden
            yield r * math.cos(theta), r * math.sin(theta)
