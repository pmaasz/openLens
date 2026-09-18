"""Built-in example data: Nikon Series E 50mm f/1.8.

Provides the design prescription from ``US4234242A`` (Nakamura, Example 2,
f/1.8 embodiment) scaled from the patent's normalized ``f = 100 mm`` to the
real ``f = 50 mm`` (halve all radii and thicknesses; indices unchanged).

Full background and unscaled patent values live in
``docs/NIKON_SERIES_E_50MM.md``. This module is the single source of truth
for seeding that lens into SQLite databases as six individual lens rows
plus one six-element assembly row.

Seeding is idempotent and non-destructive: existing rows with the same
stable IDs are never overwritten. Storage stays pure -- call
:func:`ensure_nikon_series_e_example` from application startup, not from
:class:`DatabaseManager` itself, so unit-test temp databases stay clean.
"""

import logging
from typing import Any, Dict, List, Union

logger = logging.getLogger(__name__)

from .constants import WAVELENGTH_D_LINE
from .lens import Lens
from .optical_system import OpticalSystem

#: Stable IDs so re-seeding is a no-op instead of duplicating rows.
NIKON_SERIES_E_LENS_IDS = [
    "nikon-series-e-50mm-l1",
    "nikon-series-e-50mm-l2",
    "nikon-series-e-50mm-l3",
    "nikon-series-e-50mm-l4a",
    "nikon-series-e-50mm-l4b",
    "nikon-series-e-50mm-l5",
]

#: Stable assembly ID for the full six-element system.
NIKON_SERIES_E_ASSEMBLY_ID = "nikon-series-e-50mm-assembly"

#: Air gaps between consecutive elements (mm), patent d-values scaled to 50 mm.
#: Order: L1-L2, L2-L3, L3-L4a (stop space), L4a-L4b (cemented), L4b-L5.
NIKON_SERIES_E_AIR_GAPS = [0.095, 1.55, 8.82, 0.0, 0.095]

_LENS_SPECS = [
    {
        "seed_id": NIKON_SERIES_E_LENS_IDS[0],
        "name": "Series E 50/1.8 L1 (front positive)",
        "radius_of_curvature_1": 45.4915,
        "radius_of_curvature_2": 612.3255,
        "thickness": 3.39,
        "diameter": 28.0,
        "refractive_index": 1.713,
        "model_nd": 1.713,
        "model_vd": 53.9,
    },
    {
        "seed_id": NIKON_SERIES_E_LENS_IDS[1],
        "name": "Series E 50/1.8 L2 (positive meniscus)",
        "radius_of_curvature_1": 19.093,
        "radius_of_curvature_2": 32.098,
        "thickness": 4.36,
        "diameter": 28.0,
        "refractive_index": 1.713,
        "model_nd": 1.713,
        "model_vd": 53.9,
    },
    {
        "seed_id": NIKON_SERIES_E_LENS_IDS[2],
        "name": "Series E 50/1.8 L3 (negative meniscus)",
        "radius_of_curvature_1": 88.0105,
        "radius_of_curvature_2": 16.0455,
        "thickness": 0.97,
        "diameter": 28.0,
        "refractive_index": 1.64831,
        "model_nd": 1.64831,
        "model_vd": 33.8,
    },
    {
        "seed_id": NIKON_SERIES_E_LENS_IDS[3],
        "name": "Series E 50/1.8 L4a (cemented negative)",
        "radius_of_curvature_1": -17.5195,
        "radius_of_curvature_2": -65.1165,
        "thickness": 0.97,
        "diameter": 26.0,
        "refractive_index": 1.64831,
        "model_nd": 1.64831,
        "model_vd": 33.8,
    },
    {
        "seed_id": NIKON_SERIES_E_LENS_IDS[4],
        "name": "Series E 50/1.8 L4b (cemented positive)",
        "radius_of_curvature_1": -65.1165,
        "radius_of_curvature_2": -19.961,
        "thickness": 4.845,
        "diameter": 26.0,
        "refractive_index": 1.713,
        "model_nd": 1.713,
        "model_vd": 53.9,
    },
    {
        "seed_id": NIKON_SERIES_E_LENS_IDS[5],
        "name": "Series E 50/1.8 L5 (rear positive)",
        "radius_of_curvature_1": 70.962,
        "radius_of_curvature_2": -117.655,
        "thickness": 2.52,
        "diameter": 26.0,
        "refractive_index": 1.713,
        "model_nd": 1.713,
        "model_vd": 53.9,
    },
]


def _make_lens(spec: Dict[str, Any]) -> Lens:
    """Build one seed lens with a stable ID.

    Args:
        spec: One entry from ``_LENS_SPECS``.

    Returns:
        Lens with model-glass dispersion enabled (patent glasses are
        obsolete, so nd/Vd travel with the row for chromatic analysis).
    """
    lens = Lens(
        name=spec["name"],
        radius_of_curvature_1=spec["radius_of_curvature_1"],
        radius_of_curvature_2=spec["radius_of_curvature_2"],
        thickness=spec["thickness"],
        diameter=spec["diameter"],
        refractive_index=spec["refractive_index"],
        material="Custom (US4234242 patent glass)",
        wavelength_nm=WAVELENGTH_D_LINE,
        model_glass_mode=True,
        model_nd=spec["model_nd"],
        model_vd=spec["model_vd"],
    )
    lens.id = spec["seed_id"]
    return lens


def build_nikon_series_e_lenses() -> List[Lens]:
    """Build the six individual Series E elements with stable IDs.

    Returns:
        List of six Lens objects (L1, L2, L3, L4a, L4b, L5).
    """
    return [_make_lens(spec) for spec in _LENS_SPECS]


def build_nikon_series_e_system() -> OpticalSystem:
    """Build the full six-element Series E assembly with stable IDs.

    Returns:
        OpticalSystem named for the lens, with patent air gaps between
        elements (L4a-L4b cemented with a zero gap).
    """
    system = OpticalSystem(name="Nikon Series E 50mm f/1.8 (US4234242 Ex.2)")
    system.id = NIKON_SERIES_E_ASSEMBLY_ID
    for i, lens in enumerate(build_nikon_series_e_lenses()):
        gap_before = 0.0 if i == 0 else NIKON_SERIES_E_AIR_GAPS[i - 1]
        system.add_lens(lens, air_gap_before=gap_before)
    return system


def get_nikon_series_e_lens_dicts() -> List[Dict[str, Any]]:
    """Return seed lens rows ready for ``DatabaseManager.save_lens``.

    Returns:
        List of six lens dicts with stable IDs.
    """
    return [lens.to_dict() for lens in build_nikon_series_e_lenses()]


def get_nikon_series_e_assembly_dict() -> Dict[str, Any]:
    """Return the seed assembly dict ready for ``save_assembly``.

    Returns:
        Assembly dict whose element lens dicts carry the same stable IDs
        as :func:`get_nikon_series_e_lens_dicts`, so saving the assembly
        also materializes the individual lens rows.
    """
    return build_nikon_series_e_system().to_dict()


def is_nikon_series_e_seeded(db: Any) -> bool:
    """Check whether all seed rows are already present.

    Args:
        db: A ``DatabaseManager`` instance.

    Returns:
        True when all six lens IDs and the assembly ID exist.
    """
    existing = db.all_ids()
    have_lenses = set(existing.get("lenses", []))
    have_assemblies = set(existing.get("assemblies", []))
    return all(lid in have_lenses for lid in NIKON_SERIES_E_LENS_IDS) and (
        NIKON_SERIES_E_ASSEMBLY_ID in have_assemblies
    )


def ensure_nikon_series_e_example(db_or_path: Union[str, Any]) -> bool:
    """Ensure the Series E example exists; insert only missing rows.

    Never overwrites existing rows, so user edits to a seed lens survive
    re-seeding. When the assembly is missing but some lenses already exist,
    the assembly is built from the current database rows (not the patent
    defaults) to avoid clobbering those edits.

    Args:
        db_or_path: A ``DatabaseManager`` or a filesystem path to open.

    Returns:
        True if any row was inserted, False if everything already existed.
    """
    from .database import DatabaseManager

    close_after = False
    if isinstance(db_or_path, str):
        db = DatabaseManager(db_or_path)
        close_after = True
    else:
        db = db_or_path

    try:
        if is_nikon_series_e_seeded(db):
            return False

        existing = db.all_ids()
        have_lenses = set(existing.get("lenses", []))
        have_assemblies = set(existing.get("assemblies", []))
        inserted = False

        seed_dicts = {d["id"]: d for d in get_nikon_series_e_lens_dicts()}
        for lid in NIKON_SERIES_E_LENS_IDS:
            if lid not in have_lenses:
                db.save_lens(seed_dicts[lid])
                inserted = True

        if NIKON_SERIES_E_ASSEMBLY_ID not in have_assemblies:
            # Re-read current lens rows so pre-existing (possibly edited)
            # lenses are referenced as-is instead of being overwritten.
            current = {
                r["id"]: r
                for r in db.load_all()
                if r.get("id") in set(NIKON_SERIES_E_LENS_IDS)
            }
            for lid in NIKON_SERIES_E_LENS_IDS:
                current.setdefault(lid, seed_dicts[lid])
            positions = [0.0]
            running = 0.0
            lens_list = [current[lid] for lid in NIKON_SERIES_E_LENS_IDS]
            for i, lens_dict in enumerate(lens_list):
                positions[-1] = running
                running += float(lens_dict["thickness"])
                if i < len(NIKON_SERIES_E_AIR_GAPS):
                    running += NIKON_SERIES_E_AIR_GAPS[i]
                    positions.append(running)
            assembly_dict = {
                "id": NIKON_SERIES_E_ASSEMBLY_ID,
                "name": "Nikon Series E 50mm f/1.8 (US4234242 Ex.2)",
                "elements": [
                    {"lens": lens_dict, "position": positions[i]}
                    for i, lens_dict in enumerate(lens_list)
                ],
                "air_gaps": [
                    {"thickness": gap, "position": 0.0}
                    for gap in NIKON_SERIES_E_AIR_GAPS
                ],
            }
            db.save_assembly(assembly_dict)
            inserted = True

        if inserted:
            logger.info("Seeded Nikon Series E 50mm f/1.8 example data")
        return inserted
    finally:
        if close_after:
            pass
