"""Snap model glasses to the nearest real catalog glasses.

Continuous index/Abbe optimization can land on a glass that does not exist.
This module provides the search and the substitution pass that turns such a
pair back into a manufacturable catalog material, and reports the merit
before and after so the designer can see what the snap cost.
"""

import logging
import math
from dataclasses import dataclass, field
from typing import Iterable, List, Optional, Sequence, Tuple

from .material_database import MaterialProperties, get_material_database

logger = logging.getLogger(__name__)

#: Weight of one refractive-index unit in the nearest-glass distance. One
#: index step is worth 100 Abbe steps at the default weights, which keeps
#: both axes visible on the usual nd/Vd glass map.
DEFAULT_ND_WEIGHT = 1.0
DEFAULT_VD_WEIGHT = 0.01


@dataclass(frozen=True)
class GlassMatch:
    """A catalog glass and its weighted distance from a requested pair."""

    material: MaterialProperties
    distance: float


@dataclass(frozen=True)
class GlassSubstitution:
    """One element's before/after material report."""

    element_index: int
    before_material: str
    before_nd: float
    before_vd: float
    after_material: str
    after_nd: float
    after_vd: float
    changed: bool


@dataclass
class SubstitutionReport:
    """The substitutions applied to a system and their merit change."""

    substitutions: List[GlassSubstitution] = field(default_factory=list)
    merit_before: Optional[float] = None
    merit_after: Optional[float] = None

    @property
    def changed(self) -> bool:
        """Whether any element moved to a different material."""
        return any(item.changed for item in self.substitutions)

    @property
    def merit_change(self) -> Optional[float]:
        """``after - before``, or None when merit was not evaluated."""
        if self.merit_before is None or self.merit_after is None:
            return None
        return self.merit_after - self.merit_before

    def format(self) -> str:
        """Plain-text before/after table for the GUI."""
        lines = ["Glass substitution", ""]
        for item in self.substitutions:
            lines.append(
                f"Element {item.element_index + 1}: "
                f"{item.before_material} ({item.before_nd:.4f}, {item.before_vd:.2f})"
                f" -> {item.after_material} "
                f"({item.after_nd:.4f}, {item.after_vd:.2f})"
                + ("" if item.changed else "  [unchanged]")
            )
        if not self.substitutions:
            lines.append("No lens elements to substitute.")
        if self.merit_change is not None:
            lines.append("")
            lines.append(f"Merit before: {self.merit_before:.6g}")
            lines.append(f"Merit after:  {self.merit_after:.6g}")
            lines.append(f"Merit change: {self.merit_change:+.6g}")
        return "\n".join(lines)


class GlassSubstituter:
    """Nearest-catalog-glass search and substitution for lens elements."""

    def __init__(
        self,
        database=None,
        catalog: Optional[str] = None,
        nd_weight: float = DEFAULT_ND_WEIGHT,
        vd_weight: float = DEFAULT_VD_WEIGHT,
    ) -> None:
        """Create a substituter.

        Args:
            database: ``MaterialDatabase`` to search. None uses the shared
                application catalog.
            catalog: Optional catalog name filter ("Schott", "Ohara", ...).
            nd_weight: Weight of the refractive-index difference. Must be
                positive.
            vd_weight: Weight of the Abbe-number difference. Must be positive.
        """
        if nd_weight <= 0 or vd_weight <= 0:
            raise ValueError("glass-distance weights must be positive")
        self.database = database or get_material_database()
        self.catalog = catalog
        self.nd_weight = float(nd_weight)
        self.vd_weight = float(vd_weight)

    def materials(self) -> List[MaterialProperties]:
        """Catalog entries usable for substitution, sorted by name."""
        entries = []
        for material in self.database.materials.values():
            if self.catalog and material.catalog.upper() != self.catalog.upper():
                continue
            if not (math.isfinite(material.nd) and math.isfinite(material.vd)):
                continue
            if material.nd <= 0 or material.vd <= 0:
                continue
            entries.append(material)
        return sorted(entries, key=lambda item: item.name)

    def nearest(self, nd: float, vd: float) -> Optional[GlassMatch]:
        """Return the closest catalog glass to ``(nd, vd)``, or None.

        The distance is
        ``sqrt((nd_weight*(nd-nd'))**2 + (vd_weight*(vd-vd'))**2)``.
        Ties are broken by material name so the answer is deterministic.
        """
        nd = _finite_positive(nd, "refractive index")
        vd = _finite_positive(vd, "Abbe number")
        best: Optional[GlassMatch] = None
        for material in self.materials():
            distance = math.hypot(
                self.nd_weight * (material.nd - nd),
                self.vd_weight * (material.vd - vd),
            )
            if best is None or (distance, material.name) < (
                best.distance,
                best.material.name,
            ):
                best = GlassMatch(material, distance)
        return best

    def substitute_lens(self, lens, element_index: int = 0) -> GlassSubstitution:
        """Snap one lens to its nearest catalog glass.

        The lens's current glass is taken from its model nd/Vd when it is in
        model-glass mode, otherwise from the catalog entry its material names.
        A lens already on a catalog glass is left untouched.
        """
        current_nd, current_vd = lens_glass_pair(lens, self.database)
        match = self.nearest(current_nd, current_vd)
        if match is None:
            raise ValueError("the material catalog has no usable glasses")

        material = match.material
        changed = lens.material != material.name or bool(getattr(lens, "model_glass_mode", False))
        report = GlassSubstitution(
            element_index=element_index,
            before_material=lens.material,
            before_nd=current_nd,
            before_vd=current_vd,
            after_material=material.name,
            after_nd=material.nd,
            after_vd=material.vd,
            changed=changed,
        )
        if changed:
            lens.material = material.name
            lens.model_glass_mode = False
            lens.model_nd = material.nd
            lens.model_vd = material.vd
            # Store the catalog's d-line index directly. A few imported
            # materials carry nd/Vd without Sellmeier coefficients; asking
            # the catalog for a wavelength would return 1.0 for those.
            lens.refractive_index = material.nd
        return report

    def substitute_system(
        self,
        system,
        element_indices: Optional[Iterable[int]] = None,
        targets: Optional[Sequence] = None,
        constraints: Optional[dict] = None,
    ) -> SubstitutionReport:
        """Substitute selected elements and report the merit change.

        Args:
            system: ``OpticalSystem`` to modify in place.
            element_indices: Element indices to snap. None means every lens.
            targets: Optimization targets used to evaluate the merit. None
                skips the merit evaluation.
            constraints: Optional merit-function constraints.
        """
        indices = (
            list(range(len(system.elements)))
            if element_indices is None
            else sorted({int(index) for index in element_indices})
        )
        if any(index < 0 or index >= len(system.elements) for index in indices):
            raise IndexError("element index is outside the system")

        merit_before = None
        merit_after = None
        if targets:
            from .optimizer import MeritFunction

            merit_before = MeritFunction(system, list(targets), constraints).evaluate(system)

        substitutions = [
            self.substitute_lens(system.elements[index].lens, index) for index in indices
        ]

        if targets:
            from .optimizer import MeritFunction

            merit_after = MeritFunction(system, list(targets), constraints).evaluate(system)

        return SubstitutionReport(
            substitutions=substitutions,
            merit_before=merit_before,
            merit_after=merit_after,
        )


def find_nearest_glass(
    nd: float,
    vd: float,
    database=None,
    catalog: Optional[str] = None,
    nd_weight: float = DEFAULT_ND_WEIGHT,
    vd_weight: float = DEFAULT_VD_WEIGHT,
) -> Optional[MaterialProperties]:
    """Return the closest catalog material to ``(nd, vd)``, or None."""
    match = GlassSubstituter(
        database=database,
        catalog=catalog,
        nd_weight=nd_weight,
        vd_weight=vd_weight,
    ).nearest(nd, vd)
    return match.material if match else None


def substitute_glasses(
    system,
    element_indices: Optional[Iterable[int]] = None,
    targets: Optional[Sequence] = None,
    constraints: Optional[dict] = None,
    database=None,
    catalog: Optional[str] = None,
) -> SubstitutionReport:
    """Convenience wrapper around :class:`GlassSubstituter` for one system."""
    return GlassSubstituter(database=database, catalog=catalog).substitute_system(
        system,
        element_indices=element_indices,
        targets=targets,
        constraints=constraints,
    )


def lens_glass_pair(lens, database=None) -> Tuple[float, float]:
    """The nd/Vd pair a lens currently represents.

    Args:
        lens: Lens whose glass pair is wanted.
        database: Material catalog used to resolve a named material. None
            uses the shared application catalog.
    """
    database = database or get_material_database()
    if getattr(lens, "model_glass_mode", False):
        return float(lens.model_nd), float(lens.model_vd)
    material = database.get_material(lens.material)
    if material is not None:
        return float(material.nd), float(material.vd)
    return float(lens.refractive_index), float(getattr(lens, "model_vd", 64.17))


def _finite_positive(value, label: str) -> float:
    """Return ``value`` as a finite positive float, or raise ValueError."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label} must be a positive number, got {value!r}") from None
    if not math.isfinite(number) or number <= 0:
        raise ValueError(f"{label} must be a positive number, got {value!r}")
    return number
