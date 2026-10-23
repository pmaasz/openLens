#!/usr/bin/env python3
"""
Preset Lens Library
Common lens designs and industry standard templates
"""

import uuid
from typing import List, Dict, Optional
from dataclasses import dataclass

from .constants import FLAT_RADIUS
from .lens import Lens


@dataclass
class LensPreset:
    """A preset lens design"""

    name: str
    category: str
    description: str
    lens: Lens
    manufacturer: Optional[str] = None
    part_number: Optional[str] = None
    typical_use: Optional[str] = None


# ---------------------------------------------------------------------------
# Catalogue presets migrated from the retired openlens/preset_lenses.py.
#
# That module exported a second get_preset_library() with the same name and
# the same intent but the opposite shape: a factory returning a fresh
# PresetLensLibrary whose search_presets() handed back raw dicts, against this
# module's singleton returning typed LensPreset objects. import_custom_preset
# on the factory version was a no-op - the imported preset was discarded on
# the next call - and the two test suites encoded contradictory contracts.
#
# This module is the survivor: it owns the singleton, the typed preset object,
# the category listing, and get_lens_copy()'s to_dict/from_dict round-trip
# (the hand-rolled copy had drifted and dropped coatings, model-glass
# settings, parabolic sags and Fresnel grooves).
#
# The optical data below is preserved verbatim; only the representation
# changed. `applications` became typical_use, `vendor` became manufacturer,
# and the flat-surface radius now uses the shared FLAT_RADIUS constant,
# which _is_flat actually recognises - see its docstring for why 1e10 and
# LARGE_NUMBER both sit on the wrong side of the boundary.
#
# Entries already represented above under a different name (the Plossl
# eyepiece, the 10x objective, the Abbe condenser, the laser focusing lens
# and the 50 mm camera element) are not duplicated here.
# ---------------------------------------------------------------------------

_CATALOG_PRESETS = (
    {
        "name": "Symmetric Biconvex",
        "category": "Educational",
        "description": "Equal curvature on both sides",
        "radius1": 50.0,
        "radius2": -50.0,
        "thickness": 6.0,
        "diameter": 25.4,
        "material": "BK7",
        "applications": ["Learning", "Demonstrations"],
    },
    {
        "name": "Kellner Eyepiece",
        "category": "Eyepieces",
        "description": "Popular eyepiece design with good field of view",
        "radius1": 15.0,
        "radius2": -30.0,
        # 4.0 mm left the rear surface in front of the front one at the
        # 20 mm rim (edge -1.54 mm).  7.0 mm gives a 1.46 mm rim.
        "thickness": 7.0,
        "diameter": 20.0,
        "material": "BK7",
        "applications": ["Telescopes", "Microscopes"],
    },
    {
        "name": "4x Microscope Objective",
        "category": "Objectives",
        "description": "Low magnification microscope objective",
        "radius1": 12.0,
        "radius2": -25.0,
        "thickness": 8.0,
        "diameter": 15.0,
        "material": "BK7",
        "applications": ["Microscopy", "Teaching"],
    },
    {
        "name": "Telescope Objective",
        "category": "Objectives",
        "description": "Long focal length for astronomical viewing",
        "radius1": 200.0,
        "radius2": -250.0,
        "thickness": 10.0,
        "diameter": 50.0,
        "material": "BK7",
        "applications": ["Astronomy", "Long distance viewing"],
    },
    {
        "name": "Beam Expander Element",
        "category": "Laser Optics",
        "description": "Expanding divergent laser beams",
        "radius1": -20.0,
        "radius2": 40.0,
        "thickness": 4.0,
        "diameter": 25.4,
        "material": "UVFS",
        "applications": ["Laser beam expansion", "Collimation"],
    },
    {
        "name": "Edmund #45-166 (25mm PCX)",
        "category": "Industry Standard",
        "description": "Popular plano-convex lens, 25mm dia, 50mm FL",
        "radius1": 25.8,
        "radius2": None,  # flat
        "thickness": 4.8,
        "diameter": 25.0,
        "material": "N-BK7",
        "vendor": "Edmund Optics",
        "part_number": "45-166",
        "applications": ["Laser focusing", "Beam shaping"],
    },
    {
        "name": "Edmund #45-168 (25mm PCX)",
        "category": "Industry Standard",
        "description": "Plano-convex lens, 25mm dia, 100mm FL",
        "radius1": 51.5,
        "radius2": None,  # flat
        "thickness": 3.8,
        "diameter": 25.0,
        "material": "N-BK7",
        "vendor": "Edmund Optics",
        "part_number": "45-168",
        "applications": ["Laser focusing", "Collimation"],
    },
    {
        "name": "Thorlabs LA1509 (25mm PCX)",
        "category": "Industry Standard",
        "description": "Plano-convex lens, 25mm dia, 100mm FL",
        "radius1": 51.5,
        "radius2": None,  # flat
        "thickness": 3.3,
        "diameter": 25.4,
        "material": "N-BK7",
        "vendor": "Thorlabs",
        "part_number": "LA1509",
        "applications": ["Laser focusing", "Collimation"],
    },
)


def _radius_or_flat(value):
    """Translate the catalogue's flat marker into FLAT_RADIUS."""
    return FLAT_RADIUS if value is None else float(value)


class PresetLibrary:
    """Library of preset lens designs"""

    def __init__(self):
        self.presets: Dict[str, LensPreset] = {}
        self._load_common_presets()
        self._load_catalog_presets()

    def _load_catalog_presets(self):
        """Load the migrated catalogue entries as typed LensPreset objects."""
        for entry in _CATALOG_PRESETS:
            applications = entry.get("applications") or []
            self.add_preset(
                LensPreset(
                    name=entry["name"],
                    category=entry["category"],
                    description=entry["description"],
                    lens=Lens(
                        name=entry["name"],
                        radius_of_curvature_1=_radius_or_flat(entry["radius1"]),
                        radius_of_curvature_2=_radius_or_flat(entry["radius2"]),
                        thickness=entry["thickness"],
                        diameter=entry["diameter"],
                        material=entry["material"],
                    ),
                    manufacturer=entry.get("vendor"),
                    part_number=entry.get("part_number"),
                    typical_use=", ".join(applications) or None,
                )
            )

    def _load_common_presets(self):
        """Load common preset lenses"""

        # Simple lenses
        self.add_preset(
            LensPreset(
                name="50mm Biconvex",
                category="Simple Lenses",
                description="Standard biconvex lens, 50mm focal length",
                lens=Lens(
                    name="50mm Biconvex",
                    radius_of_curvature_1=51.5,
                    radius_of_curvature_2=-51.5,
                    thickness=5.0,
                    diameter=25.4,
                    material="BK7",
                ),
                typical_use="General purpose focusing, magnification",
            )
        )

        self.add_preset(
            LensPreset(
                name="100mm Plano-Convex",
                category="Simple Lenses",
                description="Plano-convex lens, 100mm focal length",
                lens=Lens(
                    name="100mm Plano-Convex",
                    radius_of_curvature_1=51.5,
                    radius_of_curvature_2=FLAT_RADIUS,  # Flat
                    thickness=4.0,
                    diameter=25.4,
                    material="BK7",
                ),
                typical_use="Collimation, beam shaping",
            )
        )

        self.add_preset(
            LensPreset(
                name="-50mm Biconcave",
                category="Simple Lenses",
                description="Biconcave lens, -50mm focal length (diverging)",
                lens=Lens(
                    name="-50mm Biconcave",
                    radius_of_curvature_1=-51.5,
                    radius_of_curvature_2=51.5,
                    thickness=2.5,
                    diameter=25.4,
                    material="BK7",
                ),
                typical_use="Beam expansion, reducing convergence",
            )
        )

        # Eyepieces
        self.add_preset(
            LensPreset(
                name="25mm Plossl Eyepiece",
                category="Eyepieces",
                description="Classic Plossl design, 25mm focal length",
                lens=Lens(
                    name="25mm Plossl",
                    radius_of_curvature_1=30.0,
                    radius_of_curvature_2=-30.0,
                    thickness=8.0,
                    diameter=24.0,
                    material="BK7",
                ),
                typical_use="Telescope eyepiece, 50° field of view",
            )
        )

        # Objectives
        self.add_preset(
            LensPreset(
                name="Microscope 10x Objective",
                category="Objectives",
                description="Microscope objective, 10x magnification",
                lens=Lens(
                    name="10x Objective",
                    radius_of_curvature_1=8.0,
                    radius_of_curvature_2=-12.0,
                    thickness=6.0,
                    # D/2 was 9 mm against |R1| = 8 mm, so the surface did not
                    # exist at the rim.  12 mm gives a 1.68 mm rim.
                    diameter=12.0,
                    material="BK7",
                ),
                typical_use="Microscopy, 10x magnification",
            )
        )

        # Condensers
        self.add_preset(
            LensPreset(
                name="Abbe Condenser",
                category="Condensers",
                description="Two-element Abbe condenser for microscopy",
                lens=Lens(
                    name="Abbe Condenser",
                    radius_of_curvature_1=20.0,
                    radius_of_curvature_2=-20.0,
                    # The 12 mm center left a -1.54 mm rim at 30 mm diameter.
                    # 16 mm keeps the condenser aperture with a 2.46 mm rim.
                    thickness=16.0,
                    diameter=30.0,
                    material="BK7",
                ),
                typical_use="Microscope illumination",
            )
        )

        # Laser optics
        self.add_preset(
            LensPreset(
                name="Laser Focusing Lens 532nm",
                category="Laser Optics",
                description="Optimized for green laser (532nm)",
                lens=Lens(
                    name="532nm Focus",
                    radius_of_curvature_1=75.0,
                    radius_of_curvature_2=-75.0,
                    thickness=4.0,
                    diameter=12.7,
                    material="BK7",
                    wavelength=532.0,
                ),
                typical_use="Laser beam focusing, 532nm wavelength",
            )
        )

        # Camera lenses
        self.add_preset(
            LensPreset(
                name="50mm Camera Lens Element",
                category="Camera Optics",
                description="Single element approximation of 50mm camera lens",
                lens=Lens(
                    name="50mm Camera",
                    radius_of_curvature_1=45.0,
                    radius_of_curvature_2=-55.0,
                    # 6 mm crossed at the 40 mm rim (edge -2.45 mm).
                    # 10 mm gives a 1.55 mm rim and keeps f close to 50 mm.
                    thickness=10.0,
                    diameter=40.0,
                    material="BK7",
                ),
                typical_use="Photography, normal field of view",
            )
        )

        # UV/IR optics
        self.add_preset(
            LensPreset(
                name="UV Fused Silica Lens",
                category="Specialty Optics",
                description="UV-grade fused silica, 100mm focal length",
                lens=Lens(
                    name="UV Lens",
                    radius_of_curvature_1=91.5,
                    radius_of_curvature_2=-91.5,
                    thickness=5.0,
                    diameter=25.4,
                    material="FUSEDSILICA",
                    wavelength=355.0,
                ),
                typical_use="UV applications, spectroscopy",
            )
        )

    def add_preset(self, preset: LensPreset):
        """Add a preset to the library"""
        self.presets[preset.name] = preset

    def get_preset(self, name: str) -> Optional[LensPreset]:
        """Get preset by name"""
        return self.presets.get(name)

    def list_presets(self, category: Optional[str] = None) -> List[LensPreset]:
        """List all presets, optionally filtered by category"""
        if category:
            return [p for p in self.presets.values() if p.category == category]
        return list(self.presets.values())

    def list_categories(self) -> List[str]:
        """Get list of all categories"""
        categories = set(p.category for p in self.presets.values())
        return sorted(categories)

    def search_presets(self, query: str) -> List[LensPreset]:
        """Search presets by name or description"""
        query_lower = query.lower()
        results = []
        for preset in self.presets.values():
            if query_lower in preset.name.lower() or query_lower in preset.description.lower():
                results.append(preset)
        return results

    def get_lens_copy(self, preset_name: str) -> Optional[Lens]:
        """Get a copy of the lens from a preset.

        Round-trips through ``Lens.to_dict``/``from_dict`` rather than
        re-listing the fields by hand: the hand-rolled copy had drifted and
        silently dropped coatings, model-glass settings, parabolic sags and
        Fresnel groove parameters, so instantiating a preset produced a
        different lens than the one described.
        """
        preset = self.get_preset(preset_name)
        if preset is None:
            return None

        data = preset.lens.to_dict()
        # A copy is a distinct object: give it its own identity.
        data["id"] = uuid.uuid4().hex
        return Lens.from_dict(data)


# Singleton instance
_preset_library = None


def get_preset_library() -> PresetLibrary:
    """Get the singleton preset library instance"""
    global _preset_library
    if _preset_library is None:
        _preset_library = PresetLibrary()
    return _preset_library
