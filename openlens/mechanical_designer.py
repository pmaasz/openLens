"""
Mechanical Design Module
Handles lens housing, mounting, and spacing calculations.
"""

# math.pi, not np.pi: this module's only use of numpy was the constant, and
# importing numpy here meant a missing numpy - a *soft* dependency everywhere
# else in the project - took down mechanical design too. It also misreported
# the failure as a missing pythonocc-core, because callers that catch ImportError
# around the CAD imports attribute it to the wrong package.
import logging
import math
from typing import List, Dict, Optional, Any
from dataclasses import dataclass

from .constants import DEFAULT_MOUNT_TYPE
from .mounts import MountCatalog

logger = logging.getLogger(__name__)


@dataclass
class LensMount:
    """Lens mounting specifications."""

    lens_diameter: float  # mm
    mount_type: str  # 'C-mount', 'M42', 'custom', etc.
    thread_diameter: float  # mm
    thread_pitch: float  # mm
    flange_distance: float  # mm
    clear_aperture: float  # mm

    def get_specifications(self) -> Dict[str, Any]:
        """Get mount specifications."""
        return {
            "lens_diameter": self.lens_diameter,
            "mount_type": self.mount_type,
            "thread_diameter": self.thread_diameter,
            "thread_pitch": self.thread_pitch,
            "flange_distance": self.flange_distance,
            "clear_aperture": self.clear_aperture,
        }


@dataclass
class LensCell:
    """Lens cell (housing) design."""

    inner_diameter: float  # mm
    outer_diameter: float  # mm
    length: float  # mm
    wall_thickness: float  # mm
    material: str  # 'aluminum', 'brass', 'plastic', etc.
    threads_external: bool
    threads_internal: bool

    def calculate_weight(self) -> float:
        """Calculate cell weight in grams."""
        # Material densities (g/cm³)
        densities = {
            "aluminum": 2.7,
            "brass": 8.5,
            "plastic": 1.2,
            "titanium": 4.5,
            "steel": 7.8,
        }

        density = densities.get(self.material.lower(), 2.7)

        # Volume calculation
        outer_volume = math.pi * (self.outer_diameter / 2) ** 2 * self.length
        inner_volume = math.pi * (self.inner_diameter / 2) ** 2 * self.length
        volume_mm3 = outer_volume - inner_volume
        volume_cm3 = volume_mm3 / 1000

        return volume_cm3 * density


@dataclass
class Spacer:
    """Lens spacing element."""

    thickness: float  # mm
    inner_diameter: float  # mm
    outer_diameter: float  # mm
    material: str
    tolerance: float  # mm

    def __repr__(self):
        return f"Spacer({self.thickness:.3f}mm, {self.material})"


class MechanicalDesigner:
    """Design mechanical components for optical systems."""

    # Standard mount specifications (the authoritative table lives in mounts).
    STANDARD_MOUNTS = MountCatalog.STANDARD_MOUNTS

    #: Axial clearance a lens cell carries beyond the element's centre
    #: thickness. Documented because the mechanical total exceeds the optical
    #: stack by this much per element.
    CELL_MARGIN_MM = 5.0

    def __init__(
        self,
        optical_system=None,
        mount_catalog: Optional[MountCatalog] = None,
    ) -> None:
        self.optical_system = optical_system
        self.mount_catalog = mount_catalog or MountCatalog()
        self.lens_cells: List[LensCell] = []
        self.spacers: List[Spacer] = []
        self.mounts: List[LensMount] = []

    def get_available_mounts(self) -> Dict[str, Dict[str, Any]]:
        """Return standard and custom mounts available for design."""
        return self.mount_catalog.get_available_mounts()

    def add_custom_mount(
        self,
        name: str,
        flange_distance: float,
        thread_diameter: float = 0.0,
        thread_pitch: float = 0.0,
    ) -> Dict[str, Any]:
        """Add a user-defined mount to this designer's catalog."""
        return self.mount_catalog.add_custom_mount(
            name, flange_distance, thread_diameter, thread_pitch
        )

    def remove_custom_mount(self, name: str) -> bool:
        """Remove a user-defined mount from this designer's catalog."""
        return self.mount_catalog.remove_custom_mount(name)

    def save_custom_mounts(self):
        """Persist the user-defined mounts and return the config path."""
        return self.mount_catalog.save_custom_mounts()

    def load_custom_mounts(self) -> Dict[str, Dict[str, Any]]:
        """Reload user-defined mounts and return them."""
        return self.mount_catalog.load_custom_mounts()

    def design_lens_cells(
        self, wall_thickness: float = 2.0, material: str = "aluminum"
    ) -> List[LensCell]:
        """Design lens cells for all elements in the system.

        The cell length is the element's centre thickness plus
        ``CELL_MARGIN_MM`` for the retaining shoulder and cement clearance.
        """
        self.lens_cells.clear()

        elements = getattr(self.optical_system, "elements", None)
        if elements:
            # OpticalSystem wraps lenses in LensElement objects
            lenses = [getattr(e, "lens", e) for e in elements]
        else:
            # Duck-typed systems may expose a plain lens list
            lenses = getattr(self.optical_system, "lenses", [])

        for lens in lenses:
            # Get lens diameter
            if hasattr(lens, "diameter"):
                lens_diameter = lens.diameter
            else:
                lens_diameter = 25.4  # Default 1 inch

            # Design cell
            inner_diameter = lens_diameter + 0.1  # Clearance
            outer_diameter = inner_diameter + 2 * wall_thickness

            # Length from the element's own thickness. ``Lens`` exposes
            # ``thickness``; the old probe for ``center_thickness`` never
            # matched, so every cell was the 10 mm fallback regardless of the
            # element it had to hold.
            center_thickness = getattr(lens, "center_thickness", None)
            if center_thickness is None:
                center_thickness = getattr(lens, "thickness", None)
            if center_thickness is None:
                logger.warning(
                    "Mechanical design: lens %r exposes neither center_thickness nor "
                    "thickness; using the %.1f mm fallback cell length",
                    getattr(lens, "name", lens),
                    10.0,
                )
                length = 10.0
            else:
                length = float(center_thickness) + self.CELL_MARGIN_MM

            cell = LensCell(
                inner_diameter=inner_diameter,
                outer_diameter=outer_diameter,
                length=length,
                wall_thickness=wall_thickness,
                material=material,
                threads_external=True,
                threads_internal=True,
            )

            self.lens_cells.append(cell)

        return self.lens_cells

    def _default_spacings(self, num_lenses: int) -> List[float]:
        """Air gap before each element after the first, in axial order."""
        gaps = list(getattr(self.optical_system, "air_gaps", None) or [])
        if gaps:
            return [float(getattr(gap, "thickness", gap)) for gap in gaps]

        spacing = getattr(self.optical_system, "element_spacing", None)
        if spacing is not None:
            return list(spacing)

        # Neither model exposes gaps; keep the historical default so a
        # duck-typed target still gets a spacer between each pair.
        return [10.0] * max(num_lenses - 1, 0)

    def calculate_spacers(
        self, target_spacing: Optional[List[float]] = None, tolerance: float = 0.1
    ) -> List[Spacer]:
        """Calculate required spacers between lens elements.

        Without an explicit ``target_spacing`` the spacers are the system's
        own air gaps; the old probe for ``element_spacing`` never matched an
        ``OpticalSystem``, so every spacer was a fabricated 10 mm.
        """
        self.spacers.clear()

        elements = getattr(self.optical_system, "elements", None)
        if elements:
            num_lenses = len(elements)
        elif hasattr(self.optical_system, "lenses"):
            num_lenses = len(self.optical_system.lenses)
        else:
            return []

        if target_spacing is None:
            target_spacing = self._default_spacings(num_lenses)

        for i, spacing in enumerate(target_spacing):
            # Determine spacer dimensions
            if i < len(self.lens_cells):
                inner_dia = self.lens_cells[i].inner_diameter - 2.0
                outer_dia = self.lens_cells[i].outer_diameter
            else:
                inner_dia = 20.0
                outer_dia = 30.0

            spacer = Spacer(
                thickness=spacing,
                inner_diameter=inner_dia,
                outer_diameter=outer_dia,
                material="aluminum",
                tolerance=tolerance,
            )

            self.spacers.append(spacer)

        return self.spacers

    def design_mount(
        self, mount_type: str = DEFAULT_MOUNT_TYPE, lens_diameter: Optional[float] = None
    ) -> LensMount:
        """Design lens mount interface."""
        specs = self.mount_catalog.get_mount(mount_type)
        if specs is None:
            raise ValueError(f"Unknown mount type: {mount_type}")

        if lens_diameter is None:
            if self.lens_cells:
                lens_diameter = self.lens_cells[0].outer_diameter
            else:
                lens_diameter = 25.4

        mount = LensMount(
            lens_diameter=lens_diameter,
            mount_type=mount_type,
            thread_diameter=specs["thread_diameter"],
            thread_pitch=specs["thread_pitch"],
            flange_distance=specs["flange_distance"],
            clear_aperture=lens_diameter * 0.8,
        )

        self.mounts.append(mount)
        return mount

    def calculate_total_length(self) -> float:
        """Total mechanical length of the cells and the spacers.

        Cells carry ``CELL_MARGIN_MM`` each beyond the element thickness, so
        the total exceeds the optical stack length by
        ``number_of_elements * CELL_MARGIN_MM``.
        """
        total = 0.0

        for cell in self.lens_cells:
            total += cell.length

        for spacer in self.spacers:
            total += spacer.thickness

        return total

    def suggest_housing(
        self,
        wall: float = 2.0,
        clearance: float = 0.25,
        flange: float = 2.0,
        material: str = "aluminum",
        mount: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Derive STEP-exportable housing parts from the optical system.

        Returns part dicts (``name``/``z0``/``z1``/``r_inner``/``r_outer``)
        for one spacer per positive air gap plus a barrel spanning the
        stack. Spacer bores clear the smaller neighbor clear aperture;
        the barrel bore clears the largest element OD. A ``mount`` string
        (e.g. ``"M42x1.0"``) is recorded in the barrel name as a thread
        specification — threads are specified, not modeled, without a CAD
        kernel.
        """
        elements = list(getattr(self.optical_system, "elements", []) or [])
        if not elements:
            return []
        gaps = list(getattr(self.optical_system, "air_gaps", []) or [])

        def _ca(lens) -> float:
            values = [float(lens.diameter)]
            for attr in ("get_clear_aperture_1", "get_clear_aperture_2"):
                getter = getattr(lens, attr, None)
                if callable(getter):
                    try:
                        values.append(float(getter()))
                    except (TypeError, ValueError):
                        pass
            return min(values)

        ods = [float(e.lens.diameter) for e in elements]
        bore = max(ods) + clearance
        parts: List[Dict[str, Any]] = []
        for i, gap in enumerate(gaps):
            thickness = float(getattr(gap, "thickness", gap) or 0.0)
            if thickness <= 0 or i + 1 >= len(elements):
                continue
            z0 = float(gap.position)
            neighbors = [elements[i].lens, elements[i + 1].lens]
            inner = min(_ca(lens) for lens in neighbors)
            parts.append(
                {
                    "name": f"Spacer {i + 1} (gap {i}, {material})",
                    "z0": z0,
                    "z1": z0 + thickness,
                    "r_inner": inner / 2,
                    "r_outer": bore / 2,
                    "material": material,
                }
            )
        total = float(self.optical_system.get_total_length())
        barrel_name = f"Barrel ({material}"
        barrel_name += f", thread {mount}" if mount else ""
        barrel_name += ")"
        parts.append(
            {
                "name": barrel_name,
                "z0": -flange,
                "z1": total + flange,
                "r_inner": bore / 2,
                "r_outer": bore / 2 + wall,
                "material": material,
            }
        )
        return parts

    def calculate_total_weight(self) -> float:
        """Calculate total weight of mechanical assembly in grams."""
        total = 0.0

        for cell in self.lens_cells:
            total += cell.calculate_weight()

        # Spacer weights (simplified)
        for spacer in self.spacers:
            volume_cm3 = (
                math.pi
                * ((spacer.outer_diameter / 2) ** 2 - (spacer.inner_diameter / 2) ** 2)
                * spacer.thickness
            ) / 1000
            total += volume_cm3 * 2.7  # Aluminum density

        return total

    def generate_bom(self) -> List[Dict[str, Any]]:
        """Generate Bill of Materials."""
        bom = []

        # Lens cells
        for i, cell in enumerate(self.lens_cells):
            bom.append(
                {
                    "item": f"Lens Cell {i+1}",
                    "part_number": f"LC-{i+1:02d}",
                    "description": f"Lens housing, {cell.material}",
                    "quantity": 1,
                    "dimensions": f"OD={cell.outer_diameter:.1f}mm, L={cell.length:.1f}mm",
                    "weight_g": cell.calculate_weight(),
                    "material": cell.material,
                }
            )

        # Spacers
        for i, spacer in enumerate(self.spacers):
            bom.append(
                {
                    "item": f"Spacer {i+1}",
                    "part_number": f"SP-{i+1:02d}",
                    "description": f"Spacing ring, {spacer.material}",
                    "quantity": 1,
                    "dimensions": f"t={spacer.thickness:.2f}mm ±{spacer.tolerance:.2f}mm",
                    "weight_g": 0.0,  # Calculated separately
                    "material": spacer.material,
                }
            )

        # Mounts
        for i, mount in enumerate(self.mounts):
            if mount.thread_diameter > 0:
                dimensions = f"Thread={mount.thread_diameter:.1f}mm"
            else:
                dimensions = f"Bayonet, flange={mount.flange_distance:.2f}mm"
            bom.append(
                {
                    "item": f"Mount Adapter {i+1}",
                    "part_number": f"MT-{i+1:02d}",
                    "description": f"{mount.mount_type} adapter",
                    "quantity": 1,
                    "dimensions": dimensions,
                    "weight_g": 0.0,
                    "material": "aluminum",
                }
            )

        return bom

    def generate_assembly_instructions(self) -> List[str]:
        """Generate assembly instructions."""
        instructions = []
        instructions.append("Lens Assembly Instructions")
        instructions.append("=" * 50)
        instructions.append("")

        instructions.append("Required Tools:")
        instructions.append("- Lens spanner wrench")
        instructions.append("- Torque driver (2-5 Nm)")
        instructions.append("- Lint-free gloves")
        instructions.append("- Lens tissue")
        instructions.append("")

        instructions.append("Assembly Steps:")

        step = 1
        for i, cell in enumerate(self.lens_cells):
            instructions.append(f"{step}. Install Lens {i+1} into Cell {i+1}")
            instructions.append("   - Clean lens surfaces")
            instructions.append("   - Insert lens into cell")
            instructions.append("   - Secure with retaining ring")
            instructions.append("")
            step += 1

            if i < len(self.spacers):
                instructions.append(f"{step}. Add Spacer {i+1} ({self.spacers[i].thickness:.2f}mm)")
                instructions.append("   - Verify spacer thickness with calipers")
                instructions.append("   - Thread onto previous cell")
                instructions.append("")
                step += 1

        if self.mounts:
            instructions.append(f"{step}. Attach mount adapter")
            instructions.append(f"   - Thread {self.mounts[0].mount_type} adapter")
            instructions.append("   - Torque to specification")
            instructions.append("")

        instructions.append("Quality Checks:")
        instructions.append("- Verify all threads engaged properly")
        instructions.append("- Check lens alignment")
        instructions.append("- Test mechanical focus")
        instructions.append("- Inspect for dust/contamination")

        return instructions

    def export_cad_parameters(self) -> Dict[str, Any]:
        """Export parameters for CAD modeling."""
        return {
            "lens_cells": [
                {
                    "id": i,
                    "inner_diameter": cell.inner_diameter,
                    "outer_diameter": cell.outer_diameter,
                    "length": cell.length,
                    "wall_thickness": cell.wall_thickness,
                    "material": cell.material,
                }
                for i, cell in enumerate(self.lens_cells)
            ],
            "spacers": [
                {
                    "id": i,
                    "thickness": spacer.thickness,
                    "inner_diameter": spacer.inner_diameter,
                    "outer_diameter": spacer.outer_diameter,
                    "tolerance": spacer.tolerance,
                }
                for i, spacer in enumerate(self.spacers)
            ],
            "total_length": self.calculate_total_length(),
            "total_weight": self.calculate_total_weight(),
        }

    def check_clearances(self) -> List[Dict[str, Any]]:
        """Check mechanical clearances and interferences."""
        issues = []

        # Check lens cells fit together
        for i in range(len(self.lens_cells) - 1):
            cell1 = self.lens_cells[i]
            cell2 = self.lens_cells[i + 1]

            # Check if threads are compatible
            if cell1.threads_external and cell2.threads_internal:
                # Should be compatible
                pass
            else:
                issues.append(
                    {
                        "type": "threading",
                        "location": f"Between Cell {i+1} and Cell {i+2}",
                        "message": "Threading mismatch",
                    }
                )

        # Check spacer fit
        for i, spacer in enumerate(self.spacers):
            if i < len(self.lens_cells):
                cell = self.lens_cells[i]
                if spacer.outer_diameter > cell.outer_diameter:
                    issues.append(
                        {
                            "type": "clearance",
                            "location": f"Spacer {i+1}",
                            "message": "Spacer OD exceeds cell OD",
                        }
                    )

        return issues
