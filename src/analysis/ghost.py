from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

from ..ray_tracer import Ray3D, LensRayTracer3D, RefractionResult, vec3
from ..optical_system import OpticalSystem
from ..constants import WAVELENGTH_GREEN, NM_TO_MM


@dataclass
class GhostPath:
    """Represents a ghost path (2 reflections) through the system."""

    reflection_1_index: int  # Index of first reflection surface
    reflection_2_index: int  # Index of second reflection surface
    rays: List[Ray3D] = field(default_factory=list)
    intensity: float = 0.0

    @property
    def ray_count(self) -> int:
        return len(self.rays)


class GhostAnalyzer:
    """
    Analyzes ghost reflections in an optical system.
    Focuses on 2nd order ghosts (2 reflections).

    Known limits (deliberate, documented here rather than hidden):
    - Reflection strength uses bulk Fresnel R from the glass index, corrected
      for per-surface coatings at normal incidence (see _coating_correction):
      ghosts in AR-coated systems use the coated R of the two reflecting
      surfaces, while transmission losses along the path stay bare-Fresnel.
    - Rays that reflect twice but miss the exit leg are still counted in
      the path intensity: conservative flare estimate, since their energy
      still scatters inside the housing.
    """

    def __init__(self, system: OpticalSystem):
        self.system = system
        self.surfaces = self._build_surface_list()

    def _build_surface_list(self) -> List[Dict[str, Any]]:
        """Map linear list of surfaces."""
        surfaces = []
        for i, elem in enumerate(self.system.elements):
            # Front
            surfaces.append(
                {
                    "element": elem,
                    "lens": elem.lens,
                    "type": "front",
                    "id": 2 * i,
                    "name": f"{elem.lens.name} (Front)",
                }
            )
            # Back
            surfaces.append(
                {
                    "element": elem,
                    "lens": elem.lens,
                    "type": "back",
                    "id": 2 * i + 1,
                    "name": f"{elem.lens.name} (Back)",
                }
            )
        return surfaces

    def trace_ghosts(
        self, num_rays: int = 3, wavelength: float = WAVELENGTH_GREEN * NM_TO_MM
    ) -> List[GhostPath]:
        """
        Trace all valid 2nd order ghost paths.

        Args:
            num_rays: Number of rays to trace per ghost path (for validation)
            wavelength: Wavelength in mm

        Returns:
            List of GhostPath objects with successful rays
        """
        ghosts = []
        n_surf = len(self.surfaces)

        # Iterate over all pairs (i, j) where i > j (reflection order: i then j)
        # i is deeper in the system, j is shallower
        for i in range(n_surf):
            for j in range(i):  # j < i
                path = self._trace_ghost_path(i, j, num_rays, wavelength)
                if path and path.rays:
                    ghosts.append(path)

        return ghosts

    def _trace_ghost_path(
        self, i: int, j: int, num_rays: int, wavelength: float
    ) -> Optional[GhostPath]:
        """Trace a specific ghost sequence: Forward->i(Refl)->Backward->j(Refl)->Forward."""
        rays = []

        # Generate source rays
        # Simple grid or line on X-axis (Y varies)
        if not self.system.elements:
            return None

        first_pos = self.system.elements[0].position
        start_x = first_pos - 20.0

        # Determine aperture size for ray generation
        first_lens = self.system.elements[0].lens
        max_height = first_lens.diameter / 2 * 0.9

        for r_idx in range(num_rays):
            if num_rays == 1:
                y = 0
            else:
                y = -max_height + 2 * max_height * r_idx / (num_rays - 1)

            origin = vec3(start_x, y, 0)
            direction = vec3(1, 0, 0)  # +X
            ray = Ray3D(origin, direction, wavelength=wavelength)

            # 1. Forward Trace: 0 to i (exclusive of reflection)
            # Trace refractively through all surfaces before i
            if not self._trace_sequence(ray, 0, i - 1, "refract"):
                continue

            # 2. First Reflection at i
            # Note: We must hit surface i
            if not self._interact(ray, i, "reflect"):
                continue

            # 3. Backward Trace: i-1 down to j+1
            # Ray is now traveling backwards
            if i - 1 >= j + 1:
                if not self._trace_sequence_backward(ray, i - 1, j + 1):
                    continue

            # 4. Second Reflection at j
            if not self._interact(ray, j, "reflect"):
                continue

            # 5. Forward Trace: j+1 to End
            # Ray is traveling forward again
            if not self._trace_sequence(ray, j + 1, len(self.surfaces) - 1, "refract"):
                # It's okay if it doesn't make it all the way out (vignetted ghost)
                # But typically we want to see where it goes.
                # If terminated, we still keep the ray to show vignetting?
                # For now, only keep if it survives or at least reflects twice.
                pass

            # If we made it past the second reflection, we count it as a ghost ray
            rays.append(ray)

        if not rays:
            return None

        # Calculate average intensity of the ghost path, corrected for any
        # AR coatings on the two reflecting surfaces (normal-incidence
        # estimate at the ghost wavelength; see _coating_correction).
        avg_intensity = sum(r.intensity for r in rays) / len(rays)
        avg_intensity *= self._coating_correction(i, j, wavelength)

        return GhostPath(i, j, rays, intensity=avg_intensity)

    def _coating_correction(self, i: int, j: int, wavelength_mm: float) -> float:
        """Coated-to-bare reflection ratio for two ghost surfaces.

        The traced rays carry bare-Fresnel reflection losses; each coated
        reflecting surface scales the path by Rc/Rb at normal incidence.
        Uncoated surfaces contribute 1.0.
        """
        factor = 1.0
        wavelength_nm = wavelength_mm / NM_TO_MM
        for surf_idx in (i, j):
            surf = self.surfaces[surf_idx]
            lens = surf["lens"]
            surface = 1 if surf["type"] == "front" else 2
            stack = lens.get_coating_1() if surface == 1 else lens.get_coating_2()
            if not stack:
                continue
            bare = lens.bare_reflectance(wavelength_nm)
            if bare < 1e-12:
                continue
            factor *= lens.coating_reflectance(surface, wavelength_nm) / bare
        return factor

    def _interact(self, ray: Ray3D, surf_idx: int, interaction: str) -> bool:
        """Single surface interaction; True only on the required outcome.

        (RefractionResult is a plain Enum, so every member is truthy: the
        comparison must be explicit, otherwise misses never abort a path.)
        """
        surf = self.surfaces[surf_idx]
        tracer = LensRayTracer3D(surf["lens"], x_offset=surf["element"].position)
        result = tracer.trace_surface(ray, surf["type"], interaction)
        if interaction == "reflect":
            return result is RefractionResult.REFLECTED
        return result is RefractionResult.REFRACTED

    def _trace_sequence(self, ray: Ray3D, start_idx: int, end_idx: int, interaction: str) -> bool:
        """Trace forward sequence of interactions."""
        if start_idx > end_idx:
            return True

        for k in range(start_idx, end_idx + 1):
            if not self._interact(ray, k, interaction):
                return False
        return True

    def _trace_sequence_backward(self, ray: Ray3D, start_idx: int, end_idx: int) -> bool:
        """Trace backward sequence of interactions (always refract)."""
        if start_idx < end_idx:
            return True

        for k in range(start_idx, end_idx - 1, -1):
            if not self._interact(ray, k, "refract"):
                return False
        return True
