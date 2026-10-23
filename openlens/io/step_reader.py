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

from ..validation import reject_oversized_file

logger = logging.getLogger(__name__)

# A Part 21 string literal is '...' with any apostrophe doubled (''), so the
# body may not contain a lone quote. Matching that here keeps an exported name
# or label containing an apostrophe from silently dropping its points.
# Non-capturing, so the group numbers below are unchanged.
_LITERAL_BODY = r"(?:[^']|'')*"

_SOLID_RE = re.compile(rf"#(\d+)=MANIFOLD_SOLID_BREP\('({_LITERAL_BODY})',#?[\d.]+\);")
_POINT_RE = re.compile(rf"#(\d+)=CARTESIAN_POINT\('{_LITERAL_BODY}',\(([^)]*)\)\);")

# A spherical surface references an AXIS2_PLACEMENT_3D, whose origin is the
# sphere's centre. Those centres are emitted as CARTESIAN_POINTs in the same
# block as the solid, but they do not bound it: excluding them keeps the
# reported extent from becoming the distance between curvature centres.
_SPHERE_RE = re.compile(r"#(\d+)=SPHERICAL_SURFACE\([^,]*,#(\d+)")
_PLACEMENT_RE = re.compile(r"#(\d+)=AXIS2_PLACEMENT_3D\([^,]*,#(\d+)")

# Encoding directives the writer emits for non-ASCII text: \X2\ is UTF-16
# code units, \X4\ UTF-32 code points (only \X2\ is produced today).
_X2_RE = re.compile(r"\\X2\\([0-9A-Fa-f]+)\\X0\\")
_X4_RE = re.compile(r"\\X4\\([0-9A-Fa-f]+)\\X0\\")
_X_ENCODINGS = ((_X2_RE, "utf-16-be"), (_X4_RE, "utf-32-be"))


def _unescape(name: str) -> str:
    """Undo the Part 21 escapes that ``StepWriter`` applies.

    Scanned left to right rather than by ``str.replace``: the writer doubles a
    literal backslash, so a name that literally contains ``\\X2\\00FC\\X0\\``
    arrives as ``\\\\X2\\\\00FC\\\\X0\\\\`` and must come back as text. A
    replacement pass that looked for ``\\X2\\`` first would decode the
    doublings it happens to contain.
    """
    out: List[str] = []
    i = 0
    while i < len(name):
        ch = name[i]
        if ch == "'" and name.startswith("''", i):
            out.append("'")
            i += 2
            continue
        if ch == "\\":
            if name.startswith("\\\\", i):
                out.append("\\")
                i += 2
                continue
            for pattern, encoding in _X_ENCODINGS:
                match = pattern.match(name, i)
                if match:
                    try:
                        out.append(bytes.fromhex(match.group(1)).decode(encoding))
                    except (ValueError, UnicodeDecodeError):
                        # A malformed directive is not a reason to drop the
                        # name; keep it exactly as it was written.
                        out.append(match.group(0))
                    i = match.end()
                    break
            else:
                out.append(ch)
                i += 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def read_step_solids(filename: str) -> List[Dict[str, Any]]:
    """Read solids with their point clouds from an OpenLens STEP file.

    Args:
        filename: Path to a ``.step`` file.

    Returns:
        List of dicts with ``id``, ``name``, ``points`` (list of
        ``(x, y, z)`` tuples in file order), ``z_min`` and ``z_max``
        (None when a solid owns no points).

    Raises:
        ValidationError: If the file exceeds the import size limit.
    """
    reject_oversized_file(filename)
    with open(filename) as f:
        content = f.read()

    solids_raw = list(_SOLID_RE.finditer(content))
    points_raw = list(_POINT_RE.finditer(content))

    # Points that are centres of spherical surfaces must not count towards a
    # solid's extent: they sit at z = vertex +/- R, far outside the lens.
    placement_origin: Dict[int, int] = {}
    for placement in _PLACEMENT_RE.finditer(content):
        try:
            placement_origin[int(placement.group(1))] = int(placement.group(2))
        except ValueError:
            continue
    sphere_centre_ids: set = set()
    for sphere in _SPHERE_RE.finditer(content):
        try:
            placement_id = int(sphere.group(2))
        except ValueError:
            continue
        origin_id = placement_origin.get(placement_id)
        if origin_id is not None:
            sphere_centre_ids.add(origin_id)

    solids = []
    prev_end = 0
    for match in solids_raw:
        block_points: List[Tuple[float, float, float]] = []
        for point in points_raw:
            if prev_end < point.start() <= match.end():
                point_id = int(point.group(1))
                if point_id in sphere_centre_ids:
                    continue
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
