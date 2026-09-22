"""Minimal STEP reader for OpenLens exports.

Parses the entity subset written by ``StepWriter`` (no CAD kernel here):
MANIFOLD_SOLID_BREP solid names and CARTESIAN_POINT coordinates. Points
are attributed to the solid whose entity block contains them (our writer
emits each solid's geometry immediately before its solid entity). This is
an import-back check for our own writer — it verifies assembly structure
(solid count, names, axial extents), not general STEP interoperability.
"""

import logging
import re
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)

_SOLID_RE = re.compile(r"#(\d+)=MANIFOLD_SOLID_BREP\('((?:[^']|'')*)',#?[\d.]+\);")
_POINT_RE = re.compile(r"#(\d+)=CARTESIAN_POINT\('[^']*',\(([^)]*)\)\);")


def _unescape(name: str) -> str:
    return name.replace("''", "'")


def read_step_solids(filename: str) -> List[Dict[str, Any]]:
    """Read solids with their point clouds from an OpenLens STEP file.

    Args:
        filename: Path to a ``.step`` file.

    Returns:
        List of dicts with ``id``, ``name``, ``points`` (list of
        ``(x, y, z)`` tuples in file order), ``z_min`` and ``z_max``
        (None when a solid owns no points).
    """
    with open(filename) as f:
        content = f.read()

    solids_raw = list(_SOLID_RE.finditer(content))
    points_raw = list(_POINT_RE.finditer(content))

    solids = []
    prev_end = 0
    for match in solids_raw:
        block_points: List[Tuple[float, float, float]] = []
        for point in points_raw:
            if prev_end < point.start() <= match.end():
                try:
                    coords = tuple(float(v) for v in point.group(2).split(","))
                except ValueError:
                    continue
                if len(coords) == 3:
                    block_points.append(coords)
        prev_end = match.end()
        zs = [p[2] for p in block_points]
        solids.append(
            {
                "id": int(match.group(1)),
                "name": _unescape(match.group(2)),
                "points": block_points,
                "z_min": min(zs) if zs else None,
                "z_max": max(zs) if zs else None,
            }
        )
    return solids
