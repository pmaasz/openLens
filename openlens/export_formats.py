import logging

logger = logging.getLogger(__name__)

"""
Export to professional optical design formats
Zemax, OpticStudio, SVG technical drawings
"""

import math
from typing import Any, Dict, List, Optional
from xml.sax.saxutils import escape

from .lens import Lens
from .optical_system import OpticalSystem
from .atomic import atomic_write_text
from .constants import (
    DEFAULT_MATERIAL_INDICES,
    EPSILON,
    MAX_RADIUS_OF_CURVATURE,
    REFRACTIVE_INDEX_BK7,
    WAVELENGTH_D_LINE,
)
from .material_database import get_material_database
from .validation import (
    ValidationError,
    reject_oversized_file,
    validate_clear_aperture,
    validate_lens_parameters,
    validate_wavelength,
)


def _gap_before(system: OpticalSystem, index: int) -> float:
    """Return the air gap preceding element ``index``, in mm.

    ``LensElement`` has no ``air_gap_before`` field - gaps live on the system
    as ``system.air_gaps``, rebuilt by ``_rebuild_from_tree``. Both the
    OpticStudio and SVG system exporters read ``elem.air_gap_before``, so
    every system export raised::

        AttributeError: 'LensElement' object has no attribute 'air_gap_before'

    ``air_gaps[i]`` is the gap *after* element i, so the gap before element i
    is ``air_gaps[i - 1]``. Returns 0.0 for the first element, which has
    nothing in front of it.
    """
    if index <= 0 or index - 1 >= len(system.air_gaps):
        return 0.0
    return system.air_gaps[index - 1].thickness


class ZemaxExporter:
    """Export to Zemax format (.zmx)"""

    @staticmethod
    def export_lens(lens: Lens, filename: str):
        """Export single lens to Zemax format"""
        with atomic_write_text(filename) as f:
            f.write("! OpenLens Export\n")
            f.write(f"! {lens.name}\n")
            f.write("VERS 140000\n")
            f.write("MODE SEQ\n")
            f.write("\n")

            # Surface 0 (object)
            f.write("SURF 0\n")
            f.write("  TYPE STANDARD\n")
            f.write("  CURV 0.0\n")
            f.write("  DISZ INFINITY\n")
            f.write("\n")

            # Surface 1 (front)
            f.write("SURF 1\n")
            f.write("  TYPE STANDARD\n")
            # A parabolic surface is CONI -1 at its vertex radius, not a
            # standard sphere at the nominal radius.
            f.write(f"  CURV {_zemax_curv(lens.get_effective_radius_1())}\n")
            conic = _zemax_conic(lens.is_parabolic_1, lens.conic_constant_1)
            if conic is not None:
                f.write(f"  CONI {conic:g}\n")
            f.write(f"  DISZ {lens.thickness}\n")
            f.write(f"  DIAM {_zemax_diam(lens.get_clear_aperture_1())}\n")
            f.write(f"  GLAS {_zemax_material(lens.material)}\n")
            f.write(f"  WAVE {lens.wavelength:g}\n")
            coat1 = lens.coating_label(1)
            if coat1 != "Uncoated":
                f.write(f"  COAT {coat1}\n")
            f.write("\n")

            # Surface 2 (back)
            f.write("SURF 2\n")
            f.write("  TYPE STANDARD\n")
            f.write(f"  CURV {_zemax_curv(lens.get_effective_radius_2())}\n")
            conic = _zemax_conic(lens.is_parabolic_2, lens.conic_constant_2)
            if conic is not None:
                f.write(f"  CONI {conic:g}\n")
            f.write(f"  DIAM {_zemax_diam(lens.get_clear_aperture_2())}\n")
            coat2 = lens.coating_label(2)
            if coat2 != "Uncoated":
                f.write(f"  COAT {coat2}\n")
            f.write("  DISZ 100.0\n")
            f.write("\n")

            # Image surface
            f.write("SURF 3\n")
            f.write("  TYPE STANDARD\n")
            f.write("\n")


class OpticStudioExporter:
    """Export to Zemax OpticStudio text format"""

    @staticmethod
    def export_lens(lens: Lens, filename: str):
        """
        Export single lens to OpticStudio text prescription format.
        This is a human-readable format that can be imported into OpticStudio.
        """
        with atomic_write_text(filename) as f:
            # Header
            f.write("# OpenLens Export - OpticStudio Format\n")
            f.write(f"# Lens: {lens.name}\n")
            f.write("#" + "=" * 60 + "\n\n")

            # System info
            f.write("SYSTEM PRESCRIPTION DATA\n")
            f.write("-" * 40 + "\n")
            f.write(f"Title: {lens.name}\n")
            f.write("Units: Millimeters\n")
            f.write("Type: Sequential\n")
            f.write("\n")

            # Lens data
            f.write("LENS DATA SUMMARY\n")
            f.write("-" * 40 + "\n")
            f.write(f"Material: {lens.material}\n")
            f.write(f"Refractive Index (d-line): {lens.refractive_index:.6f}\n")
            f.write(f"Outer Diameter: {lens.diameter:.4f} mm\n")
            f.write(
                f"Clear Aperture 1/2: "
                f"{lens.get_clear_aperture_1():.4f} / {lens.get_clear_aperture_2():.4f} mm\n"
            )
            f.write(f"Bevel 1/2 (45 deg): {lens.bevel_1:.4f} / {lens.bevel_2:.4f} mm\n")
            f.write(f"Coating 1/2: {lens.coating_label(1)} / {lens.coating_label(2)}\n")

            focal_length = lens.calculate_focal_length()
            if focal_length:
                f.write(f"Effective Focal Length: {focal_length:.4f} mm\n")
            f.write("\n")

            # Surface data table
            f.write("SURFACE DATA DETAIL\n")
            f.write("-" * 40 + "\n")
            f.write(
                f"{'Surface':<10} {'Type':<12} {'Radius':<14} {'Thickness':<12} "
                f"{'Glass':<10} {'Diameter':<10}\n"
            )
            f.write("-" * 70 + "\n")

            # Object surface
            f.write(
                f"{'OBJ':<10} {'STANDARD':<12} {'Infinity':<14} {'Infinity':<12} "
                f"{'':<10} {'':<10}\n"
            )

            # Stop surface (entrance pupil at front surface)
            f.write(
                f"{'STO':<10} {'STANDARD':<12} {'Infinity':<14} {'0.0000':<12} {'':<10} "
                f"{lens.diameter:<10.4f}\n"
            )

            # Front surface
            r1_str = (
                f"{lens.radius_of_curvature_1:.4f}"
                if abs(lens.radius_of_curvature_1) < 1e10
                else "Infinity"
            )
            f.write(
                f"{'1':<10} {'STANDARD':<12} {r1_str:<14} {lens.thickness:<12.4f} "
                f"{lens.material:<10} {lens.get_clear_aperture_1():<10.4f}\n"
            )

            # Back surface
            r2_str = (
                f"{lens.radius_of_curvature_2:.4f}"
                if abs(lens.radius_of_curvature_2) < 1e10
                else "Infinity"
            )
            f.write(
                f"{'2':<10} {'STANDARD':<12} {r2_str:<14} {'100.0000':<12} {'':<10} "
                f"{lens.get_clear_aperture_2():<10.4f}\n"
            )

            # Image surface
            f.write(f"{'IMA':<10} {'STANDARD':<12} {'Infinity':<14} {'':<12} {'':<10} {'':<10}\n")

            f.write("\n")
            f.write("# End of OpenLens Export\n")

    @staticmethod
    def export_system(system: OpticalSystem, filename: str):
        """Export optical system to OpticStudio format"""
        with atomic_write_text(filename) as f:
            # Header
            f.write("# OpenLens Export - OpticStudio Format\n")
            f.write(f"# System: {system.name}\n")
            f.write("#" + "=" * 60 + "\n\n")

            f.write("SYSTEM PRESCRIPTION DATA\n")
            f.write("-" * 40 + "\n")
            f.write(f"Title: {system.name}\n")
            f.write("Units: Millimeters\n")
            f.write("Type: Sequential\n")
            f.write(f"Number of Elements: {len(system.elements)}\n")

            total_length = system.get_total_length()
            if total_length:
                f.write(f"Total Length: {total_length:.4f} mm\n")

            system_fl = system.get_system_focal_length()
            if system_fl:
                f.write(f"System Focal Length: {system_fl:.4f} mm\n")
            f.write("\n")

            # Surface data
            f.write("SURFACE DATA DETAIL\n")
            f.write("-" * 40 + "\n")
            f.write(
                f"{'Surface':<10} {'Type':<12} {'Radius':<14} {'Thickness':<12} {'Glass':<10}\n"
            )
            f.write("-" * 60 + "\n")

            # Object
            f.write(f"{'OBJ':<10} {'STANDARD':<12} {'Infinity':<14} {'Infinity':<12} {'':<10}\n")

            surf_num = 1
            for i, elem in enumerate(system.elements):
                lens = elem.lens

                # Air gap before lens
                gap_before = _gap_before(system, i)
                if gap_before > 0:
                    f.write(
                        f"{surf_num:<10} {'STANDARD':<12} {'Infinity':<14} "
                        f"{gap_before:<12.4f} {'':<10}\n"
                    )
                    surf_num += 1

                # Front surface
                r1_str = (
                    f"{lens.radius_of_curvature_1:.4f}"
                    if abs(lens.radius_of_curvature_1) < 1e10
                    else "Infinity"
                )
                f.write(
                    f"{surf_num:<10} {'STANDARD':<12} {r1_str:<14} "
                    f"{lens.thickness:<12.4f} {lens.material:<10}\n"
                )
                surf_num += 1

                # Back surface
                r2_str = (
                    f"{lens.radius_of_curvature_2:.4f}"
                    if abs(lens.radius_of_curvature_2) < 1e10
                    else "Infinity"
                )
                f.write(f"{surf_num:<10} {'STANDARD':<12} {r2_str:<14} {'100.0000':<12} {'':<10}\n")
                surf_num += 1

            # Image
            f.write(f"{'IMA':<10} {'STANDARD':<12} {'Infinity':<14} {'':<12} {'':<10}\n")

            f.write("\n")
            f.write("# End of OpenLens Export\n")


class SVGExporter:
    """Export lens diagrams as SVG (Scalable Vector Graphics)"""

    @staticmethod
    def _generate_arc_path(
        cx: float,
        cy: float,
        radius: float,
        y_start: float,
        y_end: float,
        is_left_surface: bool,
    ) -> str:
        """
        Generate SVG path for a lens surface arc.

        Args:
            cx: Center x of the arc circle
            cy: Center y of the arc circle
            radius: Radius of curvature (absolute value)
            y_start: Starting y coordinate (top)
            y_end: Ending y coordinate (bottom)
            is_left_surface: True for left/front surface, False for right/back

        Returns:
            SVG path d attribute string
        """
        # Calculate arc endpoints
        half_height = abs(y_end - y_start) / 2

        if radius < half_height:
            # Radius too small, use straight line
            return ""

        # Calculate x offset from center for the arc endpoints
        try:
            x_offset = math.sqrt(radius * radius - half_height * half_height)
        except ValueError:
            return ""

        if is_left_surface:
            # Left surface: arc curves to the left (center is to the right of surface)
            x_top = cx - x_offset
            x_bottom = cx - x_offset
        else:
            # Right surface: arc curves to the right (center is to the left of surface)
            x_top = cx + x_offset
            x_bottom = cx + x_offset

        y_top = cy - half_height
        y_bottom = cy + half_height

        # SVG arc parameters
        large_arc = 0  # Always use small arc for lens surfaces
        sweep = 1 if is_left_surface else 0

        return (
            f"M {x_top:.2f} {y_top:.2f} A {radius:.2f} {radius:.2f} "
            f"0 {large_arc} {sweep} {x_bottom:.2f} {y_bottom:.2f}"
        )

    @staticmethod
    def _get_surface_x(radius: float, half_diameter: float, base_x: float, is_front: bool) -> float:
        """Calculate x position of surface edge given radius and y position"""
        if abs(radius) > 1e9:  # Flat surface
            return base_x

        try:
            sag = abs(radius) - math.sqrt(radius * radius - half_diameter * half_diameter)
        except ValueError:
            sag = 0

        if is_front:
            if radius > 0:  # Convex front
                return base_x - sag
            else:  # Concave front
                return base_x + sag
        else:
            if radius > 0:  # Concave back (radius measured from back)
                return base_x + sag
            else:  # Convex back
                return base_x - sag

    @staticmethod
    def export_lens(
        lens: Lens,
        filename: str,
        width: int = 400,
        height: int = 300,
        show_rays: bool = False,
        show_labels: bool = True,
    ):
        """
        Export lens cross-section as SVG.

        Args:
            lens: Lens object to export
            filename: Output SVG filename
            width: SVG width in pixels
            height: SVG height in pixels
            show_rays: Whether to show ray paths (simplified)
            show_labels: Whether to show dimension labels
        """
        # Calculate scaling
        margin = 40
        available_width = width - 2 * margin
        available_height = height - 2 * margin

        # Scale to fit lens
        max_dimension = max(lens.thickness * 2, lens.diameter)
        scale = min(available_width, available_height) / max_dimension * 0.8

        # Center position
        cx = width / 2
        cy = height / 2

        # Scaled lens dimensions
        thickness = lens.thickness * scale
        half_diameter = (lens.diameter / 2) * scale

        # Calculate surface positions
        front_x = cx - thickness / 2
        back_x = cx + thickness / 2

        with atomic_write_text(filename) as f:
            # SVG header
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
            f.write(
                f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
                f'height="{height}" viewBox="0 0 {width} {height}">\n'
            )
            f.write("  <defs>\n")
            f.write("    <style>\n")
            f.write("      .lens-fill { fill: #b3d9ff; fill-opacity: 0.5; }\n")
            f.write("      .lens-stroke { stroke: #0066cc; stroke-width: 2; fill: none; }\n")
            f.write("      .axis { stroke: #999999; stroke-width: 1; stroke-dasharray: 5,5; }\n")
            f.write("      .ray { stroke: #ff6600; stroke-width: 1.5; fill: none; }\n")
            f.write(
                "      .label { font-family: Arial, sans-serif; font-size: 12px; fill: #333333; }\n"
            )
            f.write(
                "      .title { font-family: Arial, sans-serif; font-size: 14px; "
                "font-weight: bold; fill: #333333; }\n"
            )
            f.write("    </style>\n")
            f.write("  </defs>\n")
            f.write("\n")

            # Background
            f.write(f'  <rect width="{width}" height="{height}" fill="white"/>\n')
            f.write("\n")

            # Title
            f.write(
                f'  <text x="{width/2}" y="25" class="title" text-anchor="middle">'
                f"{escape(str(lens.name))}</text>\n"
            )
            f.write("\n")

            # Optical axis
            f.write(
                f'  <line x1="{margin}" y1="{cy}" x2="{width-margin}" y2="{cy}" class="axis"/>\n'
            )
            f.write("\n")

            # Generate lens outline path
            r1 = lens.radius_of_curvature_1
            r2 = lens.radius_of_curvature_2

            # Calculate sag (surface deviation from flat)
            def calc_sag(radius, half_d):
                if abs(radius) > 1e9:
                    return 0
                try:
                    return abs(radius) - math.sqrt(radius * radius - half_d * half_d)
                except ValueError as e:
                    logger.debug("Sag calculation failed: %s", e)
                    return 0

            sag1 = calc_sag(r1, lens.diameter / 2) * scale
            sag2 = calc_sag(r2, lens.diameter / 2) * scale

            # Front surface edge x positions
            if abs(r1) > 1e9:  # Flat
                front_top_x = front_x
                front_bot_x = front_x
            elif r1 > 0:  # Convex front
                front_top_x = front_x + sag1
                front_bot_x = front_x + sag1
            else:  # Concave front
                front_top_x = front_x - sag1
                front_bot_x = front_x - sag1

            # Back surface edge x positions
            if abs(r2) > 1e9:  # Flat
                back_top_x = back_x
                back_bot_x = back_x
            elif r2 < 0:  # Convex back (negative radius)
                back_top_x = back_x - sag2
                back_bot_x = back_x - sag2
            else:  # Concave back
                back_top_x = back_x + sag2
                back_bot_x = back_x + sag2

            # Build path for lens outline
            top_y = cy - half_diameter
            bot_y = cy + half_diameter

            # Start path
            path_parts = []

            # Front surface (top to bottom)
            if abs(r1) > 1e9:  # Flat surface
                path_parts.append(f"M {front_top_x:.2f} {top_y:.2f}")
                path_parts.append(f"L {front_bot_x:.2f} {bot_y:.2f}")
            else:
                # Curved surface using quadratic bezier approximation
                # Control point for quadratic bezier
                if r1 > 0:  # Convex
                    ctrl_x = front_x
                else:  # Concave
                    ctrl_x = front_top_x + sag1 * 2

                path_parts.append(f"M {front_top_x:.2f} {top_y:.2f}")
                path_parts.append(f"Q {ctrl_x:.2f} {cy:.2f} {front_bot_x:.2f} {bot_y:.2f}")

            # Bottom edge
            path_parts.append(f"L {back_bot_x:.2f} {bot_y:.2f}")

            # Back surface (bottom to top)
            if abs(r2) > 1e9:  # Flat surface
                path_parts.append(f"L {back_top_x:.2f} {top_y:.2f}")
            else:
                if r2 < 0:  # Convex back
                    ctrl_x = back_x
                else:  # Concave back
                    ctrl_x = back_bot_x - sag2 * 2

                path_parts.append(f"Q {ctrl_x:.2f} {cy:.2f} {back_top_x:.2f} {top_y:.2f}")

            # Close path
            path_parts.append("Z")

            path_d = " ".join(path_parts)

            # Draw lens
            f.write(f'  <path d="{path_d}" class="lens-fill"/>\n')
            f.write(f'  <path d="{path_d}" class="lens-stroke"/>\n')
            f.write("\n")

            # Optional rays
            if show_rays:
                ray_y_positions = [-half_diameter * 0.7, 0, half_diameter * 0.7]
                for ray_y in ray_y_positions:
                    # Simplified parallel rays
                    f.write(
                        f'  <line x1="{margin}" y1="{cy + ray_y}" x2="{front_top_x}" '
                        f'y2="{cy + ray_y}" class="ray"/>\n'
                    )
                f.write("\n")

            # Labels
            if show_labels:
                # Diameter label
                f.write(
                    f'  <text x="{margin + 10}" y="{cy - half_diameter - 5}" '
                    f'class="label">∅{lens.diameter:.1f}mm</text>\n'
                )

                # Thickness label
                f.write(
                    f'  <text x="{cx}" y="{cy + half_diameter + 20}" class="label" '
                    f'text-anchor="middle">t={lens.thickness:.1f}mm</text>\n'
                )

                # Material label
                f.write(
                    f'  <text x="{cx}" y="{height - 15}" class="label" text-anchor="middle">'
                    f"{escape(str(lens.material))} "
                    f"(n={lens.refractive_index:.4f})</text>\n"
                )

                # Focal length
                fl = lens.calculate_focal_length()
                if fl:
                    f.write(
                        f'  <text x="{width - margin - 10}" y="{cy - 10}" class="label" '
                        f'text-anchor="end">f={fl:.1f}mm</text>\n'
                    )

            f.write("\n")
            f.write("</svg>\n")

    @staticmethod
    def export_system(system: OpticalSystem, filename: str, width: int = 600, height: int = 300):
        """Export optical system as SVG diagram"""
        margin = 40

        with atomic_write_text(filename) as f:
            # SVG header
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
            f.write(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">\n')
            f.write("  <defs>\n")
            f.write("    <style>\n")
            f.write("      .lens-fill { fill: #b3d9ff; fill-opacity: 0.5; }\n")
            f.write("      .lens-stroke { stroke: #0066cc; stroke-width: 2; fill: none; }\n")
            f.write("      .axis { stroke: #999999; stroke-width: 1; stroke-dasharray: 5,5; }\n")
            f.write(
                "      .title { font-family: Arial, sans-serif; font-size: 14px; "
                "font-weight: bold; }\n"
            )
            f.write("    </style>\n")
            f.write("  </defs>\n")

            # Background
            f.write(f'  <rect width="{width}" height="{height}" fill="white"/>\n')

            # Title
            f.write(
                f'  <text x="{width/2}" y="25" class="title" text-anchor="middle">'
                f"{escape(str(system.name))}</text>\n"
            )

            # Optical axis
            cy = height / 2
            f.write(
                f'  <line x1="{margin}" y1="{cy}" x2="{width-margin}" y2="{cy}" class="axis"/>\n'
            )

            # Calculate total system length for scaling
            total_length = system.get_total_length() or 100

            # Get max diameter for vertical scaling
            max_diameter = max((elem.lens.diameter for elem in system.elements), default=50)

            available_width = width - 2 * margin
            available_height = height - 2 * margin

            scale_x = available_width / total_length * 0.8
            scale_y = available_height / max_diameter * 0.8
            scale = min(scale_x, scale_y)

            # Draw each lens element
            x_pos = margin + 20
            for i, elem in enumerate(system.elements):
                lens = elem.lens

                # Add air gap
                x_pos += _gap_before(system, i) * scale

                # Lens dimensions
                t = lens.thickness * scale
                h = lens.diameter / 2 * scale

                # Simple rectangle for each lens (simplified)
                f.write(
                    f'  <rect x="{x_pos}" y="{cy - h}" width="{t}" height="{h * 2}" '
                    f'class="lens-fill"/>\n'
                )
                f.write(
                    f'  <rect x="{x_pos}" y="{cy - h}" width="{t}" height="{h * 2}" '
                    f'class="lens-stroke"/>\n'
                )

                x_pos += t

            f.write("</svg>\n")


class PrescriptionExporter:
    """Export lens prescription format"""

    @staticmethod
    def export_prescription(lens: Lens, filename: str):
        """Export lens prescription (industry standard format)"""
        with atomic_write_text(filename) as f:
            f.write("LENS PRESCRIPTION\n")
            f.write("=" * 60 + "\n\n")
            f.write(f"Lens Name: {lens.name}\n")
            f.write(f"Lens Type: {lens.lens_type}\n\n")

            f.write("OPTICAL PARAMETERS:\n")
            f.write(f"  Radius of Curvature 1: {lens.radius_of_curvature_1:.3f} mm\n")
            f.write(f"  Radius of Curvature 2: {lens.radius_of_curvature_2:.3f} mm\n")
            f.write(f"  Center Thickness: {lens.thickness:.3f} mm\n")
            f.write(f"  Clear Aperture: {lens.diameter:.3f} mm\n")
            f.write(f"  Material: {lens.material}\n")
            f.write(f"  Refractive Index: {lens.refractive_index:.4f}\n")

            f_length = lens.calculate_focal_length()
            if f_length:
                f.write(f"  Focal Length: {f_length:.3f} mm\n")

            f.write("\n")
            f.write("Generated by OpenLens\n")


def _zemax_curv(radius: float) -> str:
    """Curvature for the simplified .zmx dialect (0 for flat/infinite)."""
    if radius == 0 or abs(radius) > 1e10 or not math.isfinite(radius):
        return "0.0"
    return f"{1.0 / radius}"


def _zemax_conic(is_parabolic: bool, conic_constant: float) -> Optional[float]:
    """CONI value for a surface, or None when it is spherical."""
    if is_parabolic:
        return -1.0
    if abs(conic_constant) > EPSILON:
        return conic_constant
    return None


def _zemax_material(material: str) -> str:
    """Render a material name as a single .zmx GLAS argument.

    A .zmx GLAS line is a keyword plus one glass name; real files use names
    such as ``N-BK7`` with no whitespace. OpenLens also has ``Fused Silica``
    and user-imported AGF names, so quote anything with whitespace. The
    importer strips the quotes again.
    """
    name = (material or "BK7").strip() or "BK7"
    if any(ch.isspace() for ch in name):
        return f'"{name}"'
    return name


def _material_design_index(material: str, wavelength: float = WAVELENGTH_D_LINE) -> float:
    """The catalog refractive index of *material* at *wavelength*, in air.

    A .zmx GLAS line names its glass and says nothing about its index, so the
    catalog is the only source that knows what F2 is. Resolving through
    DEFAULT_MATERIAL_INDICES alone was a six-glass table: every other glass
    was stored as BK7 while the name (and therefore the dispersion) stayed
    the real one, so the paraxial numbers and the traced ones described
    different glasses.

    The fallback keeps imports working for names the catalog does not hold,
    including the display names the table exists for.

    Args:
        material: Glass name as written in the file.
        wavelength: Design wavelength in nm.
    """
    try:
        database = get_material_database()
        if database.has_material(material):
            return database.get_refractive_index(material, wavelength)
    except (ArithmeticError, KeyError, OSError, ValueError) as e:
        # An unreadable catalog must not fail the import; the static table
        # below still gives a usable design index.
        logger.debug("Zemax import: catalog lookup for %r failed: %s", material, e)

    for name, index in DEFAULT_MATERIAL_INDICES.items():
        if name.lower() == material.lower():
            return index
    return REFRACTIVE_INDEX_BK7


def _zemax_diam(full_aperture: float) -> float:
    """Convert an OpenLens full aperture to Zemax's semi-diameter.

    Zemax DIAM is a semi-diameter. OpenLens stores the clear aperture (and
    mechanical diameter) as a full width, so writing it verbatim made a 25 mm
    lens appear as 50 mm in Zemax.
    """
    return full_aperture / 2.0


class ZemaxSystemExporter:
    """Export a full multi-element system to the simplified .zmx dialect.

    Layout mirrors :class:`ZemaxExporter`: OBJ surface, per-element
    front/back STANDARD surfaces carrying center thickness (front DISZ),
    gap to the next surface (back DISZ), clear-aperture DIAMs, GLAS and
    COAT lines, an explicit STOP surface inside the stop gap when the
    system defines one, and a trailing image surface.

    The dialect carries one semi-diameter per surface and no separate
    mechanical diameter, so the blank diameter is not represented: the
    importer reconstructs it from the apertures (the larger of the two).
    """

    @staticmethod
    def export_system(system: OpticalSystem, filename: str) -> None:
        """Write the system prescription to a .zmx file."""
        stop = system.get_aperture_stop()
        stop_gap = stop["gap_index"] if stop is not None else None
        stop_dia = stop.get("diameter") if stop is not None else None

        with atomic_write_text(filename) as f:
            f.write("! OpenLens System Export\n")
            f.write(f"! {system.name}\n")
            f.write("VERS 140000\n")
            f.write("MODE SEQ\n")
            f.write("\n")

            f.write("SURF 0\n")
            f.write("  TYPE STANDARD\n")
            f.write("  CURV 0.0\n")
            f.write("  DISZ INFINITY\n")
            f.write("\n")

            surf = 1
            gaps = list(system.air_gaps)
            for i, element in enumerate(system.elements):
                lens = element.lens
                # Front surface carries the center thickness.
                f.write(f"SURF {surf}\n")
                f.write("  TYPE STANDARD\n")
                f.write(f"  CURV {_zemax_curv(lens.get_effective_radius_1())}\n")
                conic = _zemax_conic(lens.is_parabolic_1, lens.conic_constant_1)
                if conic is not None:
                    f.write(f"  CONI {conic:g}\n")
                f.write(f"  DISZ {lens.thickness}\n")
                f.write(f"  DIAM {_zemax_diam(lens.get_clear_aperture_1())}\n")
                f.write(f"  GLAS {_zemax_material(lens.material)}\n")
                f.write(f"  WAVE {lens.wavelength:g}\n")
                if any(abs(value) > EPSILON for value in (element.decenter_y, element.decenter_z)):
                    f.write(f"  DECE {element.decenter_y:g} {element.decenter_z:g}\n")
                if any(
                    abs(value) > EPSILON
                    for value in (element.tilt_x, element.tilt_y, element.tilt_z)
                ):
                    f.write(f"  TILT {element.tilt_x:g} {element.tilt_y:g} {element.tilt_z:g}\n")
                coat = lens.coating_label(1)
                if coat != "Uncoated":
                    f.write(f"  COAT {coat}\n")
                f.write("\n")
                surf += 1

                # Back surface carries the distance to the next surface:
                # stop plane, next front vertex, or image.
                if stop_gap is not None and stop_gap == i:
                    back_disz = stop["position"] - (element.position + lens.thickness)
                    stop_remainder = gaps[i].thickness - back_disz
                elif i < len(gaps):
                    back_disz = gaps[i].thickness
                    stop_remainder = None
                else:
                    back_disz = 100.0
                    stop_remainder = None
                f.write(f"SURF {surf}\n")
                f.write("  TYPE STANDARD\n")
                f.write(f"  CURV {_zemax_curv(lens.get_effective_radius_2())}\n")
                conic = _zemax_conic(lens.is_parabolic_2, lens.conic_constant_2)
                if conic is not None:
                    f.write(f"  CONI {conic:g}\n")
                f.write(f"  DIAM {_zemax_diam(lens.get_clear_aperture_2())}\n")
                coat = lens.coating_label(2)
                if coat != "Uncoated":
                    f.write(f"  COAT {coat}\n")
                f.write(f"  DISZ {back_disz}\n")
                f.write("\n")
                surf += 1

                if stop_remainder is not None:
                    f.write(f"SURF {surf}\n")
                    f.write("  TYPE STANDARD\n")
                    f.write("  STOP\n")
                    f.write("  CURV 0.0\n")
                    if stop_dia:
                        f.write(f"  DIAM {_zemax_diam(stop_dia)}\n")
                    f.write(f"  DISZ {stop_remainder}\n")
                    f.write("\n")
                    surf += 1

            f.write(f"SURF {surf}\n")
            f.write("  TYPE STANDARD\n")
            f.write("\n")


class ZemaxSystemImporter:
    """Import the simplified .zmx dialect back into an OpticalSystem.

    Understands SURF blocks with TYPE/CURV/DISZ/DIAM/GLAS/STOP/COAT as
    written by :class:`ZemaxExporter` and :class:`ZemaxSystemExporter`
    (plus tolerant handling of foreign sequential files: unknown keywords
    are ignored, OBJ/IMA surfaces are skipped). COAT labels carry no
    stack data and are not restored (documented).
    """

    @staticmethod
    def _parse_surfaces(text: str) -> List[Dict[str, Any]]:
        surfaces: List[Dict[str, Any]] = []
        current: Optional[Dict[str, Any]] = None
        for raw in text.splitlines():
            line = raw.strip()
            if not line or line.startswith("!") or line.startswith("#"):
                continue
            head = line.split(None, 1)
            if head[0] == "SURF" and len(head) == 2 and head[1].split()[0].lstrip("-").isdigit():
                if current is not None:
                    surfaces.append(current)
                current = {"id": int(head[1].split()[0])}
                continue
            if current is None:
                continue
            key = head[0]
            rest = head[1] if len(head) > 1 else ""
            if key == "STOP":
                current["stop"] = True
            elif key in ("CURV", "DISZ", "DIAM", "CONI"):
                token = rest.split()[0] if rest.split() else ""
                if token.upper() == "INFINITY":
                    # Curvature INFINITY is the format's spelling of a plano
                    # surface (radius infinity), not a curvature. Store zero
                    # so it takes the same path as CURV 0; for the linear
                    # keywords INFINITY really is an unbounded value.
                    current[key.lower()] = 0.0 if key == "CURV" else float("inf")
                else:
                    try:
                        current[key.lower()] = float(token)
                    except ValueError:
                        logger.debug("Zemax import: bad %s value %r", key, token)
            elif key == "WAVE":
                token = rest.split()[0] if rest.split() else ""
                try:
                    current["wave"] = float(token)
                except ValueError:
                    logger.debug("Zemax import: bad WAVE value %r", token)
            elif key in ("DECE", "TILT"):
                try:
                    numbers = [float(value) for value in rest.split()]
                except ValueError:
                    logger.debug("Zemax import: bad %s values %r", key, rest)
                    continue
                if key == "DECE" and len(numbers) >= 2:
                    current["dece"] = (numbers[0], numbers[1])
                elif key == "TILT" and len(numbers) >= 3:
                    current["tilt"] = (numbers[0], numbers[1], numbers[2])
            elif key == "GLAS":
                # A glass name may contain spaces - real files use names like
                # "Fused Silica" - so take the whole argument, and accept the
                # quotes our own exporter adds for exactly that reason.
                value = rest.strip()
                if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
                    value = value[1:-1]
                current["glas"] = value or "BK7"
            elif key == "TYPE":
                current["type"] = rest.split()[0] if rest.split() else ""
        if current is not None:
            surfaces.append(current)
        return surfaces

    @staticmethod
    def _build_validated_lens(
        index: int,
        r1: Optional[float],
        r2: Optional[float],
        thickness: float,
        diameter: float,
        material: str,
        ca1: Optional[float],
        ca2: Optional[float],
        conic1: float = 0.0,
        conic2: float = 0.0,
        wavelength: float = WAVELENGTH_D_LINE,
    ) -> Optional[Lens]:
        """Validate one imported element and build a Lens, or return None.

        A .zmx file is untrusted input: DISZ can be negative and DIAM/CA1 can
        exceed any sane value. Rather than inject a physically impossible
        element into the system, reject it with a warning and let the import
        continue with the remaining surfaces.

        Args:
            index: 1-based element number, used for the element name.
            r1: Front radius of curvature (mm); ``inf`` for a plano surface,
                or None when the front CURV was not a real number.
            r2: Back radius of curvature (mm); ``inf`` for a plano surface,
                or None when the back CURV was not a real number.
            thickness: Center thickness (mm).
            diameter: Mechanical diameter (mm).
            material: Glass name from the GLAS keyword.
            ca1: Front clear aperture (mm), or None for full diameter.
            ca2: Back clear aperture (mm), or None for full diameter.
            conic1: Front conic constant from CONI (0.0 when absent).
            conic2: Back conic constant from CONI.
            wavelength: Design wavelength in nm from the WAVE keyword.

        Returns:
            The validated Lens, or None if validation failed.
        """
        if r1 is None or r2 is None:
            side = "front" if r1 is None else "back"
            logger.warning(
                "Zemax import: element %d dropped, %s curvature (CURV) is not finite",
                index,
                side,
            )
            return None

        if ca1 is not None and ca1 > diameter:
            logger.warning(
                "Zemax import: element %d dropped, front clear aperture "
                "(%.3f mm) exceeds diameter (%.3f mm)",
                index,
                ca1,
                diameter,
            )
            return None

        # validate_lens_parameters rejects inf radii because a literal 0 is an
        # upstream mistake. A .zmx CURV of 0.0 legitimately means a plano
        # surface, so probe with the largest allowed finite radius.
        probe = min(
            abs(r) if math.isfinite(r) and r != 0.0 else MAX_RADIUS_OF_CURVATURE for r in (r1, r2)
        )
        if probe == 0.0:
            logger.warning("Zemax import: element %d dropped, zero radius", index)
            return None

        # Preserve the glass name as written: it is shown in the UI, and the
        # catalog lookup accepts it in any case or punctuation.
        material_name = (material or "BK7").strip() or "BK7"
        try:
            wavelength = validate_wavelength(wavelength)
        except ValidationError as exc:
            logger.warning("Zemax import: element %d uses the default wavelength: %s", index, exc)
            wavelength = WAVELENGTH_D_LINE
        n = _material_design_index(material_name, wavelength)
        try:
            validate_lens_parameters(
                radius1=probe if not math.isfinite(r1) else r1,
                radius2=probe if not math.isfinite(r2) else r2,
                thickness=thickness,
                diameter=diameter,
                refractive_index=n,
                conic_constant_1=conic1,
                conic_constant_2=conic2,
            )
            # Clear apertures are relative to the diameter, so they can only be
            # checked once the diameter itself has been accepted.
            validate_clear_aperture(ca1, diameter, "clear aperture 1")
            validate_clear_aperture(ca2, diameter, "clear aperture 2")
        except ValidationError as exc:
            logger.warning("Zemax import: element %d dropped: %s", index, exc)
            return None

        # CONI -1 is a paraboloid. OpenLens stores it as a sag at the clear
        # aperture, which follows from the vertex radius and that aperture:
        # the conic term vanishes for k = -1 and z(r) = r² / (2R).
        semi = diameter / 2.0
        is_parabolic_1 = conic1 == -1.0
        is_parabolic_2 = conic2 == -1.0
        sag_1 = semi * semi / (2.0 * r1) if is_parabolic_1 and math.isfinite(r1) else 0.0
        sag_2 = semi * semi / (2.0 * r2) if is_parabolic_2 and math.isfinite(r2) else 0.0

        return Lens(
            name=f"Element {index}",
            radius_of_curvature_1=r1,
            radius_of_curvature_2=r2,
            thickness=thickness,
            diameter=diameter,
            material=material_name,
            refractive_index=n,
            clear_aperture_1=ca1,
            clear_aperture_2=ca2,
            is_parabolic_1=is_parabolic_1,
            parabolic_sag_1=sag_1,
            is_parabolic_2=is_parabolic_2,
            parabolic_sag_2=sag_2,
            conic_constant_1=conic1,
            conic_constant_2=conic2,
            wavelength=wavelength,
        )

    @staticmethod
    def _parse_unit_scale(text: str) -> float:
        """Millimetres per length unit declared by the file's UNIT header.

        Zemax writes ``UNIT MM`` or ``UNIT INCH``; older files also use
        ``UNIT IN``. A file with no UNIT line is read as millimetres, which is
        what Zemax assumes. An explicit unknown unit is reported and also read
        as millimetres: refusing the whole file would lose the surfaces that
        are otherwise usable, but silently guessing a factor would be worse.

        Args:
            text: The whole .zmx file.

        Returns:
            Factor that converts a length in the file to millimetres.
        """
        for raw in text.splitlines():
            tokens = raw.strip().split()
            if len(tokens) < 2 or tokens[0].upper() != "UNIT":
                continue
            unit = tokens[1].upper()
            if unit in ("MM", "MILLIMETER", "MILLIMETRE", "MILLIMETERS", "MILLIMETRES"):
                return 1.0
            if unit in ("IN", "INCH", "INCHES"):
                return 25.4
            logger.warning("Zemax import: unknown length unit %r, assuming millimetres", tokens[1])
            return 1.0
        return 1.0

    @staticmethod
    def import_system(filename: str, name: str = "Imported System") -> OpticalSystem:
        """Read a .zmx file into an OpticalSystem.

        All lengths and curvatures are normalised to millimetres once, right
        after parsing, according to the file's UNIT header. Every consumer
        below then works in the application's single unit.

        Args:
            filename: Path to the .zmx file.
            name: Name for the rebuilt system.

        Returns:
            OpticalSystem with elements, gaps, and stop (when present).

        Raises:
            ValidationError: If the file exceeds the import size limit.
        """
        reject_oversized_file(filename)
        with open(filename) as f:
            text = f.read()
        surfaces = ZemaxSystemImporter._parse_surfaces(text)
        scale = ZemaxSystemImporter._parse_unit_scale(text)
        if scale != 1.0:
            # Curvature is the inverse of a length, so it scales the other
            # way; DISZ and DIAM are lengths. Non-finite values are marker
            # values (DISZ INFINITY) and stay as they are.
            for surf in surfaces:
                for key, factor in (("curv", 1.0 / scale), ("disz", scale), ("diam", scale)):
                    value = surf.get(key)
                    if isinstance(value, (int, float)) and math.isfinite(value):
                        surf[key] = value * factor
                # DECE is a length; TILT is degrees and WAVE is nanometres,
                # so neither of those follows the file's length unit.
                if "dece" in surf:
                    surf["dece"] = tuple(value * scale for value in surf["dece"])

        system = OpticalSystem(name=name)
        pending_front: Optional[Dict[str, Any]] = None
        pending_stop: Optional[Dict[str, Any]] = None
        cursor_x = 0.0
        last_back_x: Optional[float] = None

        def _curv_to_radius(curv: Optional[float]) -> Optional[float]:
            """Radius for a CURV value, ``None`` when the value is not real.

            A non-finite curvature has no radius: 1/nan is nan, and 1/inf or
            1/-inf is zero, which the Lens model would turn into a flat
            surface. Both would be invented geometry, so the caller drops the
            element instead. ``CURV 0`` (and the INFINITY token, normalised by
            the parser) means a plano surface.
            """
            if curv is None or abs(curv) < 1e-12:
                return float("inf")
            if not math.isfinite(curv):
                return None
            return 1.0 / curv

        for surf in surfaces:
            if surf.get("type", "STANDARD").upper() not in ("STANDARD", ""):
                continue
            disz = surf.get("disz", 0.0) or 0.0
            if disz >= float("inf"):
                continue  # OBJ/IMA markers carry no geometry.
            if surf.get("stop"):
                # STOP is a flag on a surface, not a surface kind: it may be
                # the front (or back) surface of an element. Record it and
                # carry on with the normal handling below. Continuing here
                # used to skip the GLAS check, so a lens whose front surface
                # was the stop never opened and the element vanished.
                diam = surf.get("diam")
                pending_stop = {
                    "position": cursor_x,
                    "diameter": None if diam is None else diam * 2.0,
                }
            if "glas" in surf:
                # Front surface opens an element.
                gap_before = 0.0 if last_back_x is None else max(0.0, cursor_x - last_back_x)
                diam = surf.get("diam")
                pending_front = {
                    "r1": _curv_to_radius(surf.get("curv", 0.0)),
                    "thickness": disz,
                    # DIAM is a semi-diameter; the app stores full apertures.
                    "ca1": None if diam is None else diam * 2.0,
                    "conic1": surf.get("coni", 0.0),
                    "material": surf.get("glas", "BK7"),
                    "gap_before": gap_before,
                    "wave": surf.get("wave", WAVELENGTH_D_LINE),
                    "dece": surf.get("dece", (0.0, 0.0)),
                    "tilt": surf.get("tilt", (0.0, 0.0, 0.0)),
                }
                cursor_x += disz
                continue
            if pending_front is not None:
                # Back surface closes the element.
                diam = surf.get("diam")
                ca2 = None if diam is None else diam * 2.0
                ca1 = pending_front.get("ca1")
                # The mechanical diameter is the larger of the two clear
                # apertures. The .zmx dialect carries one semi-diameter per
                # surface and no separate mechanical diameter, so the smallest
                # blank that holds both apertures is the best reconstruction
                # available. Taking the back surface alone dropped every
                # element whose front aperture was the larger one (the
                # validation then saw a diameter smaller than the front clear
                # aperture and rejected the whole element).
                apertures = [aperture for aperture in (ca1, ca2) if aperture is not None]
                diameter = max(apertures) if apertures else 25.0
                lens = ZemaxSystemImporter._build_validated_lens(
                    index=len(system.elements) + 1,
                    r1=pending_front["r1"],
                    r2=_curv_to_radius(surf.get("curv", 0.0)),
                    thickness=pending_front["thickness"],
                    diameter=diameter,
                    material=pending_front["material"],
                    ca1=pending_front.get("ca1"),
                    ca2=ca2,
                    conic1=pending_front.get("conic1", 0.0),
                    conic2=surf.get("coni", 0.0),
                    wavelength=pending_front.get("wave", WAVELENGTH_D_LINE),
                )
                if lens is not None:
                    system.add_lens(lens, air_gap_before=pending_front["gap_before"])
                    # The transform belongs to the element, and the front
                    # vertex is the element's origin, so it is written on the
                    # front surface.
                    decenter_y, decenter_z = pending_front.get("dece", (0.0, 0.0))
                    tilt_x, tilt_y, tilt_z = pending_front.get("tilt", (0.0, 0.0, 0.0))
                    if any(
                        abs(value) > EPSILON
                        for value in (decenter_y, decenter_z, tilt_x, tilt_y, tilt_z)
                    ):
                        system.set_element_alignment(
                            len(system.elements) - 1,
                            decenter_y=decenter_y,
                            decenter_z=decenter_z,
                            tilt_x=tilt_x,
                            tilt_y=tilt_y,
                            tilt_z=tilt_z,
                        )
                    last_back_x = cursor_x
                pending_front = None
                cursor_x += disz
                continue
            cursor_x += disz

        if pending_stop is not None:
            # Map the stop plane onto the rebuilt gap list.
            stop_x = pending_stop["position"]
            for gi, gap in enumerate(system.air_gaps):
                if gap.position <= stop_x <= gap.position + gap.thickness + 1e-9:
                    try:
                        system.set_aperture_stop(gi, pending_stop["diameter"])
                    except ValueError as e:
                        logger.debug("Zemax import: stop dropped: %s", e)
                    break
        return system
