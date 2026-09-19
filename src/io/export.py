"""
ISO 10110 Drawing Export Module.
Generates SVG drawings of optical components and systems.
"""

from datetime import datetime

from ..optical_system import OpticalSystem
from ..lens import Lens
from ..geometry import LensGeometry


class ISO10110Generator:
    """Generates ISO 10110 compliant SVG drawings."""

    def __init__(self, system: OpticalSystem):
        self.system = system

    def generate_svg(self, filename: str, width: int = 800, height: int = 600):
        """Generate SVG file."""
        svg_content = self._render_svg(width, height)
        with open(filename, "w") as f:
            f.write(svg_content)

    def _render_svg(self, width: int, height: int) -> str:
        """Render SVG content."""
        scale = self._calculate_scale(width, height)
        center_x = width / 2
        center_y = height / 2

        # Header
        lines = [
            f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">',
            f"<defs>",
            f"<style>",
            f"  .lens {{ fill: #E0E0E0; stroke: black; stroke-width: 2; opacity: 0.8; }}",
            f"  .axis {{ stroke: black; stroke-width: 1; stroke-dasharray: 5,5; }}",
            f"  .text {{ font-family: Arial; font-size: 12px; }}",
            f"  .title {{ font-family: Arial; font-size: 16px; font-weight: bold; }}",
            f"  .table {{ fill: none; stroke: black; stroke-width: 1; }}",
            f"</style>",
            f"</defs>",
            f'<rect width="100%" height="100%" fill="white"/>',
            f'<text x="20" y="30" class="title">ISO 10110 Drawing: {self.system.name}</text>',
            f'<text x="20" y="50" class="text">Date: {datetime.now().strftime("%Y-%m-%d")}</text>',
        ]
        stop_getter = getattr(self.system, "get_aperture_stop", None)
        stop = stop_getter() if callable(stop_getter) else None
        if stop is not None:
            stop_dia = stop.get("diameter")
            stop_txt = (
                f"Aperture stop: gap {stop['gap_index']}"
                + (f", Ø{stop_dia:.2f}mm" if stop_dia else "")
            )
            lines.append(f'<text x="20" y="68" class="text">{stop_txt}</text>')

        # Optical Axis
        lines.append(
            f'<line x1="20" y1="{center_y}" x2="{width-20}" y2="{center_y}" class="axis"/>'
        )

        # Draw Lenses
        # Get flattened elements
        elements = self.system.elements

        # We need cumulative positions. OpticalSystem.elements.position is absolute Z?
        # Yes, standard `OpticalSystem.elements` has absolute `position`.

        # Center the system in X
        if elements:
            total_length = elements[-1].position + elements[-1].thickness
            start_x = center_x - (total_length * scale) / 2
        else:
            start_x = center_x

        # Aperture stop marker: vertical line at the stop plane.
        if stop is not None and elements:
            max_diam = max(e.lens.diameter for e in elements)
            stop_x = start_x + stop["position"] * scale
            stop_h = max_diam / 2 * scale + 10
            lines.append(
                f'<line x1="{stop_x:.2f}" y1="{center_y - stop_h:.2f}"'
                f' x2="{stop_x:.2f}" y2="{center_y + stop_h:.2f}"'
                f' stroke="black" stroke-width="1.5"/>'
            )
            lines.append(
                f'<text x="{stop_x:.2f}" y="{center_y - stop_h - 6:.2f}"'
                f' class="text" text-anchor="middle">STOP</text>'
            )

        for i, elem in enumerate(elements):
            lens = elem.lens
            pos_x = start_x + elem.position * scale

            # Draw lens profile
            path = self._generate_lens_path(lens, pos_x, center_y, scale)
            lines.append(f'<path d="{path}" class="lens"/>')

            # Label
            lines.append(
                f'<text x="{pos_x}" y="{center_y + lens.diameter/2*scale + 20}" class="text" text-anchor="middle">L{i+1}</text>'
            )

        # Draw ISO Table Block
        table_x = width - 490
        table_y = height - 150  # Start near bottom right
        # We don't need to pass height as it's calculated dynamically
        lines.append(self._generate_iso_table(table_x, table_y, 470, 0))

        # Title block (bottom-left) with drawing metadata.
        lines.append(self._generate_title_block(20, height - 170, 300, scale))

        # ISO 10110 notes block (left, below the header).
        lines.extend(self._generate_iso_notes(20, 100))

        # Dimension lines: total track below the profile, max OD at left.
        if elements:
            lines.extend(
                self._generate_dimensions(width, height, center_x, center_y, start_x, scale)
            )

        lines.append("</svg>")
        return "\n".join(lines)

    def _calculate_scale(self, width: int, height: int) -> float:
        """Calculate drawing scale to fit system."""
        if not self.system.elements:
            return 10.0

        # Bounds
        min_x = 0
        max_x = self.system.elements[-1].position + self.system.elements[-1].thickness
        max_diam = max(e.lens.diameter for e in self.system.elements)

        margin = 50
        avail_w = width - 2 * margin
        avail_h = height - 2 * margin

        scale_x = avail_w / (max_x if max_x > 0 else 10)
        scale_y = avail_h / (max_diam if max_diam > 0 else 10)

        return min(scale_x, scale_y) * 0.8  # 80% fit

    def _generate_title_block(self, x: float, y: float, w: float, scale: float) -> str:
        """Title block with drawing metadata (bottom-left)."""
        system = self.system
        efl = system.get_system_focal_length() if hasattr(system, "get_system_focal_length") else None
        bfl = (
            system.calculate_back_focal_length()
            if hasattr(system, "calculate_back_focal_length")
            else None
        )
        try:
            efl_txt = f"{efl:.2f} mm" if efl is not None else "—"
        except (TypeError, ValueError):
            efl_txt = "—"
        try:
            bfl_txt = f"{bfl:.2f} mm" if bfl is not None else "—"
        except (TypeError, ValueError):
            bfl_txt = "—"
        materials = sorted({e.lens.material for e in system.elements}) or ["—"]
        rows = [
            ("Title", system.name),
            ("Dwg No", f"{system.id[:8].upper()}-A"),
            ("Material", ", ".join(materials)),
            ("Units", "mm"),
            ("Scale", f"{scale:.2f} px/mm"),
            ("EFL / BFL", f"{efl_txt} / {bfl_txt}"),
            ("Surfaces", f"{2 * len(system.elements)}"),
            ("Date / Rev", f"{datetime.now().strftime('%Y-%m-%d')} / A"),
        ]
        row_h = 18
        total_h = 24 + len(rows) * row_h + 6
        parts = [
            f'<rect x="{x}" y="{y}" width="{w}" height="{total_h}" fill="white" stroke="black" stroke-width="1.5"/>',
            f'<text x="{x + 8}" y="{y + 17}" class="text" font-weight="bold">TITLE BLOCK</text>',
        ]
        for i, (key, value) in enumerate(rows):
            ry = y + 24 + i * row_h
            parts.append(
                f'<line x1="{x}" y1="{ry + row_h - 4}" x2="{x + w}" y2="{ry + row_h - 4}"'
                f' stroke="black" stroke-width="0.5"/>'
            )
            parts.append(f'<text x="{x + 8}" y="{ry + 12}" class="text">{key}:</text>')
            parts.append(f'<text x="{x + 110}" y="{ry + 12}" class="text">{value}</text>')
        return "\n".join(parts)

    def _generate_iso_notes(self, x: float, y: float) -> list:
        """ISO 10110 numbered notes, populated from model data where known."""
        elements = self.system.elements
        max_tilt = 0.0
        for elem in elements:
            for attr in ("tilt_x", "tilt_y"):
                max_tilt = max(max_tilt, abs(float(getattr(elem, attr, 0.0) or 0.0)))
        if max_tilt > 0:
            centering = f"≤ {max_tilt * 60:.1f}' element tilt (max over assembly)"
        else:
            centering = "TBD (assembly nominally centered)"
        coats = []
        for i, elem in enumerate(elements):
            c1 = elem.lens.coating_label(1) if hasattr(elem.lens, "coating_label") else "—"
            c2 = elem.lens.coating_label(2) if hasattr(elem.lens, "coating_label") else "—"
            coats.append(f"L{i + 1}: {c1}/{c2}")
        notes = [
            "0/ General: all dimensions in mm; surfaces numbered front to back.",
            "1/ Bubbles and inclusions: — (no data).",
            "2/ Stress birefringence: — (no data).",
            "3/ Surface form deviation: TBD (no figure data).",
            f"4/ Centering: {centering}.",
            "5/ Surface imperfection: TBD (e.g. 5/ 3x0.16).",
            f"6/ Coating: {'; '.join(coats) if coats else '—'}.",
            "7/ Laser damage threshold: — (no data).",
        ]
        lines = [f'<text x="{x}" y="{y}" class="text" font-weight="bold">ISO 10110 NOTES</text>']
        for i, note in enumerate(notes):
            lines.append(f'<text x="{x}" y="{y + 18 + i * 15}" class="text">{note}</text>')
        return lines

    def _generate_dimensions(
        self,
        width: int,
        height: int,
        center_x: float,
        center_y: float,
        start_x: float,
        scale: float,
    ) -> list:
        """Overall-length and max-diameter dimension lines."""
        elements = self.system.elements
        total_length = elements[-1].position + elements[-1].thickness
        max_diam = max(e.lens.diameter for e in elements)
        x0 = start_x
        x1 = start_x + total_length * scale
        dim_y = center_y + max_diam / 2 * scale + 44
        y_top = center_y - max_diam / 2 * scale
        y_bot = center_y + max_diam / 2 * scale
        dim_x = x0 - 34
        parts = [
            # Total track dimension below the profile.
            f'<line x1="{x0:.2f}" y1="{dim_y:.2f}" x2="{x1:.2f}" y2="{dim_y:.2f}"'
            f' stroke="black" stroke-width="1"/>',
            f'<line x1="{x0:.2f}" y1="{dim_y - 5:.2f}" x2="{x0:.2f}" y2="{dim_y + 5:.2f}"'
            f' stroke="black" stroke-width="1"/>',
            f'<text x="{(x0 + x1) / 2:.2f}" y="{dim_y + 16:.2f}" class="text"'
            f' text-anchor="middle">{total_length:.2f} mm</text>',
            # Max OD dimension left of the profile.
            f'<line x1="{dim_x:.2f}" y1="{y_top:.2f}" x2="{dim_x:.2f}" y2="{y_bot:.2f}"'
            f' stroke="black" stroke-width="1"/>',
            f'<text x="{dim_x - 6:.2f}" y="{center_y:.2f}" class="text"'
            f' text-anchor="end">Ø{max_diam:.2f}</text>',
        ]
        return parts

    def _generate_lens_path(self, lens: Lens, x: float, y: float, scale: float) -> str:
        """Generate SVG path for a lens cross-section."""
        # Use centralized geometry logic
        polyline = LensGeometry.get_lens_polyline(lens)

        path_cmds = []
        for i, (z, r) in enumerate(polyline):
            cmd = "M" if i == 0 else "L"
            # Apply scale and translation
            # z is axial position relative to lens vertex 1
            # r is height from optical axis
            svg_x = x + z * scale
            svg_y = y - r * scale  # Invert r because SVG Y is down
            path_cmds.append(f"{cmd} {svg_x:.2f} {svg_y:.2f}")

        path_cmds.append("Z")
        return " ".join(path_cmds)

    def _generate_iso_table(self, x: float, y: float, w: float, h: float) -> str:
        """Generate SVG table for system data."""
        lines = []

        # Calculate dynamic height based on elements
        num_surfaces = len(self.system.elements) * 2 if self.system.elements else 0
        header_h = 25
        row_h = 20
        total_h = header_h + num_surfaces * row_h + 10

        # Adjust y to align bottom if needed, but here we just draw down from y

        # Background
        lines.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{total_h}" fill="white" stroke="black" stroke-width="1"/>'
        )

        # Headers
        headers = ["Surf", "Radius", "Thick", "Mat", "Diam", "CA", "Coat", "Bev"]
        col_x = [x + 10, x + 50, x + 110, x + 160, x + 210, x + 260, x + 310, x + 375]

        # Draw Header Row
        lines.append(
            f'<line x1="{x}" y1="{y+header_h}" x2="{x+w}" y2="{y+header_h}" stroke="black" stroke-width="1"/>'
        )
        for i, header in enumerate(headers):
            lines.append(
                f'<text x="{col_x[i]}" y="{y+18}" class="text" font-weight="bold">{header}</text>'
            )

        # Draw Rows
        curr_y = y + header_h + 15
        surf_idx = 1

        for elem in self.system.elements:
            lens = elem.lens

            # Surface 1 (Front)
            lines.append(f'<text x="{col_x[0]}" y="{curr_y}" class="text">{surf_idx}</text>')
            lines.append(
                f'<text x="{col_x[1]}" y="{curr_y}" class="text">{lens.radius_of_curvature_1:.2f}</text>'
            )
            lines.append(
                f'<text x="{col_x[2]}" y="{curr_y}" class="text">{lens.thickness:.2f}</text>'
            )
            lines.append(f'<text x="{col_x[3]}" y="{curr_y}" class="text">{lens.material}</text>')
            lines.append(
                f'<text x="{col_x[4]}" y="{curr_y}" class="text">{lens.diameter:.2f}</text>'
            )
            lines.append(
                f'<text x="{col_x[5]}" y="{curr_y}" class="text">{lens.get_clear_aperture_1():.2f}</text>'
            )
            lines.append(
                f'<text x="{col_x[6]}" y="{curr_y}" class="text">{lens.coating_label(1)}</text>'
            )
            lines.append(
                f'<text x="{col_x[7]}" y="{curr_y}" class="text">{lens.bevel_1:.2f}</text>'
            )
            curr_y += row_h
            surf_idx += 1

            # Surface 2 (Back)
            lines.append(f'<text x="{col_x[0]}" y="{curr_y}" class="text">{surf_idx}</text>')
            lines.append(
                f'<text x="{col_x[1]}" y="{curr_y}" class="text">{lens.radius_of_curvature_2:.2f}</text>'
            )
            # Thickness is usually to next surface. For single lens, it's air?
            # Let's put "-" for back surface thickness unless we have air gap info
            lines.append(f'<text x="{col_x[2]}" y="{curr_y}" class="text">-</text>')
            lines.append(f'<text x="{col_x[3]}" y="{curr_y}" class="text"></text>')
            lines.append(
                f'<text x="{col_x[4]}" y="{curr_y}" class="text">{lens.diameter:.2f}</text>'
            )
            lines.append(
                f'<text x="{col_x[5]}" y="{curr_y}" class="text">{lens.get_clear_aperture_2():.2f}</text>'
            )
            lines.append(
                f'<text x="{col_x[6]}" y="{curr_y}" class="text">{lens.coating_label(2)}</text>'
            )
            lines.append(
                f'<text x="{col_x[7]}" y="{curr_y}" class="text">{lens.bevel_2:.2f}</text>'
            )
            curr_y += row_h
            surf_idx += 1

        return "\n".join(lines)
