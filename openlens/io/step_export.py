import logging
import math

logger = logging.getLogger(__name__)

"""
STEP Export Module for OpenLens.
Generates ISO 10303-21 (STEP) files for optical components.
Supports AP203/AP214 geometry (Manifold Solid B-Rep).
"""

from datetime import datetime
from typing import List, Any, Optional
from ..atomic import atomic_write_text
from ..constants import EPSILON
from ..geometry import LensGeometry
from ..transform import Matrix4x4
from ..vector3 import vec3


class StepRef(int):
    """A STEP entity reference, serialized as ``#id``.

    ISO 10303-21 has no integer type that means "entity id" by itself. A bare
    ``44`` in an argument position is a real number, so an id written that way
    severs every topology-to-geometry link and no CAD system can open the
    file. But several attributes legitimately take integer *values* - a
    representation context's dimension exponent, for one - so a plain ``int``
    cannot be treated as a reference without corrupting those.

    ``add_entity`` returns this type, so every id it hands back is written as
    a reference wherever it is passed on, while integer literals at the call
    site stay integer literals.
    """


class StepEnum(str):
    """A Part 21 enumeration, serialized bare as ``.T.``.

    Enumerations must not be quoted, so they cannot be passed as ordinary
    text: before this marker the writer guessed from the first character,
    which also meant an ordinary name starting with ``.`` was silently
    written as syntax.
    """

    def __new__(cls, value: str) -> "StepEnum":
        if not (len(value) > 2 and value.startswith(".") and value.endswith(".")):
            raise ValueError(f"not a Part 21 enumeration: {value!r}")
        return super().__new__(cls, value)


class StepDerived(str):
    """Part 21's derived-attribute placeholder, serialized as ``*``.

    ``*`` in an argument position means "not present in this mapping"; it is
    not a string, and a name that is an asterisk must stay quoted.
    """

    def __new__(cls) -> "StepDerived":
        return super().__new__(cls, "*")


class StepTyped(str):
    """A typed parameter, serialized bare: ``LENGTH_MEASURE(1.E-06)``.

    Part 21 selects take a typed value - an uncertainty is a
    ``LENGTH_MEASURE``, not a bare real - so the type name is part of the
    syntax. Construct this only from constants written here or in the
    exporter, never from user text.
    """


#: Enumeration values used by the exporter. ``STEP_FALSE`` exists for
#: completeness; booleans render through the bool branch of _format_scalar.
STEP_TRUE = StepEnum(".T.")
STEP_FALSE = StepEnum(".F.")
STEP_DERIVED = StepDerived()


class StepWriter:
    """Helper to generate STEP file content."""

    def __init__(self):
        self.lines = []
        self.id_counter = 1

    def get_id(self):
        """Get next available ID."""
        return self.id_counter

    @classmethod
    def _escape_text(cls, text: str) -> str:
        """Escape the body of a Part 21 string literal.

        Three rules, none of which the writer used to apply:

        - a literal apostrophe is doubled, Part 21's only escape inside a
          literal (and what ``step_reader`` expects back);
        - a literal backslash is doubled, because a single backslash starts
          an escape sequence;
        - non-ASCII characters are encoded as ``\\X2\\<UTF-16BE>\\X0\\``.
          Part 21 text is ASCII; a raw ``ü`` makes the file invalid.
          Adjacent non-ASCII characters share one directive.
        """
        parts: List[str] = []
        hex_run: List[str] = []

        def flush_hex() -> None:
            if hex_run:
                parts.append("\\X2\\" + "".join(hex_run) + "\\X0\\")
                hex_run.clear()

        for ch in text:
            if ch == "\\":
                flush_hex()
                parts.append("\\\\")
            elif ch == "'":
                flush_hex()
                parts.append("''")
            elif ord(ch) < 128:
                flush_hex()
                parts.append(ch)
            else:
                hex_run.append(ch.encode("utf-16-be").hex().upper())
        flush_hex()
        return "".join(parts)

    @classmethod
    def _format_text(cls, text: str) -> str:
        """Render a string argument as a quoted, escaped STEP literal.

        Always quoted: this used to return strings that started with ``#``,
        ``.``, ``*`` or ``$``, or that ``float()`` could parse, unquoted on
        the guess that they were pre-written syntax. Names like ``50``,
        ``Infinity`` and ``#3 doublet`` are text, and guessing turned them
        into a real number or a dangling reference. Syntax now travels as
        ``StepRef``/``StepEnum``/``StepDerived`` markers or Python types.

        ``&``, ``<`` and ``>`` need no escape: Part 21 text files carry them
        literally.
        """
        return "'" + cls._escape_text(text) + "'"

    @classmethod
    def _format_scalar(cls, arg: Any) -> str:
        """Render one argument value in ISO-10303-21 syntax."""
        if isinstance(arg, StepRef):
            return f"#{int(arg)}"
        # Before str and bool/int: the markers subclass str.
        if isinstance(arg, (StepEnum, StepDerived, StepTyped)):
            return str(arg)
        if isinstance(arg, bool):  # must precede int: bool subclasses it
            return ".T." if arg else ".F."
        if isinstance(arg, str):
            return cls._format_text(arg)
        if isinstance(arg, int):
            # Integer-valued attribute, not a reference (a representation
            # context's dimension exponent, for one). References arrive as
            # StepRef from add_entity.
            return str(arg)
        if isinstance(arg, float):
            return f"{arg:.6f}"
        if arg is None:
            return "$"
        return str(arg)

    def add_entity(self, name: str, args: List[Any]) -> StepRef:
        """Add a STEP entity and return its ID as an entity reference."""
        idx = self.id_counter
        self.id_counter += 1

        arg_strs = [self._format_arg(arg) for arg in args]

        line = f"#{idx}={name}({','.join(arg_strs)});"
        self.lines.append(line)
        return StepRef(idx)

    @classmethod
    def _format_arg(cls, arg: Any) -> str:
        """Render one argument, as an aggregate when it is a list or tuple."""
        if isinstance(arg, (list, tuple)):
            return f"({','.join(cls._format_scalar(item) for item in arg)})"
        return cls._format_scalar(arg)

    def add_complex_entity(self, parts: List[tuple]) -> StepRef:
        """Add a complex entity and return its ID as an entity reference.

        Part 21 writes an instance that is several entity types at once - a
        millimetre is a ``LENGTH_UNIT`` *and* a ``NAMED_UNIT`` *and* an
        ``SI_UNIT`` - as one instance whose type names are concatenated:
        ``#7=(LENGTH_UNIT()NAMED_UNIT(*)SI_UNIT(.MILLI.,.METRE.));``.

        Args:
            parts: ``(entity_name, arguments)`` pairs, in schema order.
        """
        idx = self.id_counter
        self.id_counter += 1

        body = "".join(
            f"{name}({','.join(self._format_arg(arg) for arg in args)})" for name, args in parts
        )
        self.lines.append(f"#{idx}=({body});")
        return StepRef(idx)

    def generate(self) -> str:
        """Generate full STEP file content."""
        header = f"""ISO-10303-21;
HEADER;
FILE_DESCRIPTION(('OpenLens Export'),'2;1');
FILE_NAME('openlens_export.step','{datetime.now().strftime("%Y-%m-%dT%H:%M:%S")}',('User'),('OpenLens'),'OpenLens','OpenLens','');
FILE_SCHEMA(('AUTOMOTIVE_DESIGN {{ 1 0 10303 214 1 1 1 1 }}'));
ENDSEC;
DATA;"""

        footer = """ENDSEC;
END-ISO-10303-21;"""

        return header + "\n" + "\n".join(self.lines) + "\n" + footer


def _is_flat_radius(radius: float) -> bool:
    """Whether the writer treats a vertex radius as planar.

    This is the writer's own threshold, kept so a near-flat sphere keeps
    exporting exactly as before.
    """
    return abs(radius) < 1e-10 or abs(radius) > 1e10 or abs(radius) > 10000


def _sphere_sag(radius: float, height: float) -> float:
    """Sag of a spherical surface of ``radius`` at ``height``."""
    if _is_flat_radius(radius) or not math.isfinite(radius):
        return 0.0
    radius_abs = abs(radius)
    y = min(abs(height), radius_abs)
    sag = radius_abs - math.sqrt(max(0.0, radius_abs * radius_abs - y * y))
    return sag if radius > 0 else -sag


def _conic_profile(lens: Any, side: int) -> Optional[str]:
    """Name the non-spherical profile of one lens surface, or ``None``.

    Parabolic surfaces store their sag at the rim instead of a conic
    constant, so their effective vertex radius is not the stored radius.
    A parabolic surface whose stored sag is zero is a plane.
    """
    if getattr(lens, f"is_parabolic_{side}", False):
        sag = getattr(lens, f"parabolic_sag_{side}", 0.0)
        diameter = getattr(lens, "diameter", 0.0)
        if abs(sag) < EPSILON or abs(diameter) < EPSILON:
            return None
        return "parabolic"

    radius = getattr(lens, f"radius_of_curvature_{side}", 0.0)
    conic_constant = getattr(lens, f"conic_constant_{side}", 0.0)
    if abs(conic_constant) > EPSILON and not _is_flat_radius(radius):
        return f"conic (K={conic_constant:g})"
    return None


def _surface_is_flat(lens: Any, side: int) -> bool:
    """Whether a surface is exactly planar for the exported B-rep.

    A zero-sag parabolic surface is a plane even though its radius attribute
    is finite, so the radius alone is not enough to decide.
    """
    if _conic_profile(lens, side) is not None:
        return False
    if getattr(lens, f"is_parabolic_{side}", False):
        return True
    return _is_flat_radius(getattr(lens, f"radius_of_curvature_{side}", 0.0))


#: The optical model runs along +X with lateral offsets in Y/Z; STEP writes
#: the optical axis along +Z with the cross-section in X/Y. These permutations
#: convert a point or direction between the two frames.
_MODEL_TO_STEP = Matrix4x4(
    [
        [0.0, 1.0, 0.0, 0.0],
        [0.0, 0.0, 1.0, 0.0],
        [1.0, 0.0, 0.0, 0.0],
        [0.0, 0.0, 0.0, 1.0],
    ]
)
_STEP_TO_MODEL = Matrix4x4(
    [
        [0.0, 0.0, 1.0, 0.0],
        [1.0, 0.0, 0.0, 0.0],
        [0.0, 1.0, 0.0, 0.0],
        [0.0, 0.0, 0.0, 1.0],
    ]
)


def _flat_element_transform(element: Any) -> Matrix4x4:
    """The model transform stored on a flat element record.

    Mirrors ``OpticalNode.get_local_transform`` (T * R) for systems whose
    records are not backed by a tree.
    """
    translation = Matrix4x4.from_translation(
        float(getattr(element, "position", 0.0)),
        float(getattr(element, "decenter_y", 0.0)),
        float(getattr(element, "decenter_z", 0.0)),
    )
    rotation = Matrix4x4.from_euler(
        float(getattr(element, "tilt_x", 0.0)),
        float(getattr(element, "tilt_y", 0.0)),
        float(getattr(element, "tilt_z", 0.0)),
    )
    return translation * rotation


def _rotates(matrix: Matrix4x4) -> bool:
    """Whether an affine transform rotates rather than only translates."""
    return any(
        abs(matrix.m[row][col] - (1.0 if row == col else 0.0)) > 1e-12
        for row in range(3)
        for col in range(3)
    )


def _direction_tuple(matrix: Matrix4x4, direction: tuple) -> tuple:
    """Transform a direction (translation ignored) into a STEP tuple."""
    vector = matrix.multiply_vector(vec3(*direction))
    return (vector.x, vector.y, vector.z)


class StepExporter:
    """Exports optical systems to STEP format."""

    def __init__(self, system=None):
        self.system = system
        self.writer = StepWriter()
        self.axis_id = 0
        self.dir_z = 0
        self.dir_x = 0

    def export(self, filename: str, housing: Optional[list] = None) -> dict:
        """Export the current system to a STEP file.

        Safe to call repeatedly on one exporter: the entity buffer is reset
        first. It used to be created only in __init__, so a second export
        appended a fresh context and a second copy of every solid to the
        first export's lines - 48 entities after one call, 96 after two, with
        two MANIFOLD_SOLID_BREPs in one file.

        Args:
            filename: Output path.
            housing: Optional iterable of housing-part dicts with keys
                ``name``, ``z0``, ``z1``, ``r_inner``, ``r_outer`` (all mm)
                describing annular tube solids (spacers, barrel, retainers).
                See ``mechanical_designer.suggest_housing``.

        Returns:
            A summary dict: ``shapes`` (solids written), ``skipped`` (count of
            parts that could not be exported) and ``skipped_parts`` (their
            names). Previously this returned None, so callers ignoring the
            result are unaffected. A malformed part used to be logged at
            DEBUG, which is invisible at default verbosity - the drawing came
            out with silently missing solids and nothing said so.

        Raises:
            ValueError: If a lens has a parabolic or general conic surface.
                A ``SPHERICAL_SURFACE`` cannot pass through the modelled rim,
                so the solid would not close. Refusing leaves no file: the
                buffer is only written once every part has been built.
        """
        # Start from a clean buffer and a clean id sequence.
        self.writer = StepWriter()
        self.axis_id = 0
        self.dir_z = 0
        self.dir_x = 0
        self.dir_y = 0
        self.origin = 0
        self.axis2_placement = 0
        self.context = 0
        self.uncertainty = 0
        self.related_context = 0
        self.geom_context = 0
        self.length_unit = 0
        self.application_context = 0
        self._solid_index = 0

        # Standard setup entities
        self._create_context()

        shape_ids = []
        skipped: list = []

        # Export each lens
        if hasattr(self.system, "elements") and hasattr(self.system, "air_gaps"):
            for elem, placement in zip(self.system.elements, self._element_placements()):
                solid_id = self._export_lens_solid(elem.lens, 0.0, placement)
                if solid_id:
                    shape_ids.append(solid_id)
        elif hasattr(self.system, "radius_of_curvature_1"):
            # Single lens
            solid_id = self._export_lens_solid(self.system, 0.0)
            if solid_id:
                shape_ids.append(solid_id)
        else:
            # Fallback for dict or other objects
            try:
                # Try to use it as a single lens if it has necessary attributes
                solid_id = self._export_lens_solid(self.system, 0.0)
                if solid_id:
                    shape_ids.append(solid_id)
            except (AttributeError, KeyError) as e:
                skipped.append("system")
                logger.warning(
                    "STEP solid export skipped - object exposes neither a lens "
                    "nor elements/air_gaps: %s",
                    e,
                )

        # Export housing parts (spacers, barrel, retainers) as tube solids.
        for part in housing or []:
            name = str(part.get("name", "part")) if isinstance(part, dict) else "part"
            try:
                solid_id = self._export_tube_solid(
                    name,
                    float(part["z0"]),
                    float(part["z1"]),
                    float(part["r_inner"]),
                    float(part["r_outer"]),
                )
                if solid_id:
                    shape_ids.append(solid_id)
                else:
                    # _export_tube_solid rejected the dimensions; it has already
                    # logged, but the part still has to be counted.
                    skipped.append(name)
            except (KeyError, TypeError, ValueError) as e:
                skipped.append(name)
                logger.warning(
                    "STEP housing part %r skipped - malformed or missing "
                    "z0/z1/r_inner/r_outer: %s",
                    name,
                    e,
                )

        # Create Root Product Definition if needed
        # For simplicity, we just leave the geometric entities in the file.
        # Most viewers will find the MANIFOLD_SOLID_BREP entities.
        # But properly we should link them to a PRODUCT.

        self._create_product_structure(shape_ids)

        # Write file
        with atomic_write_text(filename) as f:
            f.write(self.writer.generate())

        # Surface the omissions. A mechanical drawing that silently lost its
        # barrel and spacers is worse than one that says so.
        if skipped:
            logger.warning(
                "STEP export wrote %d solid(s) but skipped %d part(s): %s",
                len(shape_ids),
                len(skipped),
                ", ".join(skipped),
            )
        return {"shapes": len(shape_ids), "skipped": len(skipped), "skipped_parts": skipped}

    def _create_context(self):
        """Create the units, contexts and directions the solids refer to.

        The file has to say what its numbers mean and which context it
        belongs to. It used to refer to ``'#unit_mm'`` and
        ``'#application_context'`` as text - references no reader resolves -
        and neither entity was written anywhere, so the exported geometry had
        no length unit at all.
        """
        # Directions
        self.dir_z = self.writer.add_entity("DIRECTION", ["axis_z", (0.0, 0.0, 1.0)])
        self.dir_x = self.writer.add_entity("DIRECTION", ["axis_x", (1.0, 0.0, 0.0)])
        self.dir_y = self.writer.add_entity("DIRECTION", ["axis_y", (0.0, 1.0, 0.0)])

        self.origin = self.writer.add_entity("CARTESIAN_POINT", ["origin", (0.0, 0.0, 0.0)])

        self.axis2_placement = self.writer.add_entity(
            "AXIS2_PLACEMENT_3D", ["global_axis", self.origin, self.dir_z, self.dir_x]
        )

        # Length unit: millimetres, the model's own unit. A millimetre is a
        # length unit, a named unit and an SI unit at once, which Part 21
        # writes as one complex entity.
        self.length_unit = self.writer.add_complex_entity(
            [
                ("LENGTH_UNIT", []),
                ("NAMED_UNIT", [STEP_DERIVED]),
                ("SI_UNIT", [StepEnum(".MILLI."), StepEnum(".METRE.")]),
            ]
        )

        self.uncertainty = self.writer.add_entity(
            "UNCERTAINTY_MEASURE_WITH_UNIT",
            [
                StepTyped("LENGTH_MEASURE(1.E-06)"),
                self.length_unit,
                "distance_accuracy_value",
                "confusion accuracy",
            ],
        )

        # Contexts. The product and mechanical contexts name the application
        # context, so it has to exist first.
        self.application_context = self.writer.add_entity(
            "APPLICATION_CONTEXT",
            ["core data for automotive mechanical design processes"],
        )

        self.related_context = self.writer.add_entity(
            "PRODUCT_CONTEXT",
            ["part definition", self.application_context, "mechanical"],
        )

        self.context = self.writer.add_entity(
            "MECHANICAL_CONTEXT", ["3D Mechanical Context", self.application_context]
        )

        # The geometric context carries the dimension count, the uncertainty
        # and the units together; without the unit assignment the solids'
        # coordinates are unitless numbers.
        self.geom_context = self.writer.add_complex_entity(
            [
                ("GEOMETRIC_REPRESENTATION_CONTEXT", [3]),
                ("GLOBAL_UNCERTAINTY_ASSIGNED_CONTEXT", [[self.uncertainty]]),
                ("GLOBAL_UNIT_ASSIGNED_CONTEXT", [[self.length_unit]]),
                ("REPRESENTATION_CONTEXT", ["", ""]),
            ]
        )

    def _element_placements(self) -> List[Matrix4x4]:
        """Global STEP placement of each flat element record, in export order.

        The optical tree owns the transform (a group can move its children);
        the flat records are what the export iterates. They are paired by
        identity, so a stale or reordered list cannot apply one element's
        alignment to another - the fallback uses the record's own fields.

        Returns:
            One 4x4 matrix per element, mapping the exporter's local
            coordinates to the assembly's STEP coordinates.
        """
        elements = list(getattr(self.system, "elements", []))
        nodes = []
        root = getattr(self.system, "root", None)
        if root is not None and hasattr(root, "get_flat_list"):
            try:
                nodes = [
                    node
                    for node, _position in root.get_flat_list()
                    if getattr(node, "is_element", False)
                ]
            except (AttributeError, TypeError, ValueError):
                nodes = []

        placements = []
        for index, element in enumerate(elements):
            node = nodes[index] if index < len(nodes) else None
            if node is not None and getattr(node, "element_model", None) is element.lens:
                model_transform = node.get_global_transform()
            else:
                model_transform = _flat_element_transform(element)
            placements.append(_MODEL_TO_STEP * model_transform * _STEP_TO_MODEL)
        return placements

    def _export_lens_solid(self, lens, z_offset, placement: Optional[Matrix4x4] = None):
        """Create B-Rep solid for a lens.

        Args:
            lens: Lens model to write.
            z_offset: Local axial position of the first vertex (mm).
            placement: Optional transform from the solid's local coordinates
                to the assembly's STEP coordinates (element decenter/tilt).
                ``None`` leaves the solid in its local frame.
        """
        r1 = lens.radius_of_curvature_1
        r2 = lens.radius_of_curvature_2
        thick = lens.thickness
        diam = lens.diameter
        h = diam / 2.0

        # A sphere cannot follow a parabola or a general conic: at the rim it
        # would not pass through the point the model puts there, so the B-rep
        # would not close. This writer has no analytic non-spherical surface
        # entity, and a STEP file is CAD/manufacturing input, so refuse the
        # lens rather than emit a plausible-looking wrong shape.
        for side, label in ((1, "front"), (2, "back")):
            profile = _conic_profile(lens, side)
            if profile is None:
                continue
            stored_radius = getattr(lens, f"radius_of_curvature_{side}")
            modelled_sag = lens.get_sag_1(h) if side == 1 else lens.get_sag_2(h)
            sphere_sag = _sphere_sag(stored_radius, h)
            raise ValueError(
                f"STEP export writes spherical and flat surfaces only; lens "
                f"{getattr(lens, 'name', '?')!r} has a {profile} {label} "
                f"surface. At the rim (h={h:g} mm) the model sags "
                f"{modelled_sag:.6f} mm but a sphere of radius "
                f"{stored_radius:g} mm sags {sphere_sag:.6f} mm, so the "
                f"exported rim would not lie on the exported surface."
            )

        def point(x: float, y: float, z: float) -> tuple:
            """Place one local point in the assembly."""
            if placement is None:
                return (x, y, z)
            placed = placement.multiply_point(vec3(x, y, z))
            return (placed.x, placed.y, placed.z)

        # Directions rotate with the element; the global axis entities can be
        # reused when the element is only translated.
        if placement is not None and _rotates(placement):
            self._solid_index += 1
            axis_z = self.writer.add_entity(
                "DIRECTION",
                [
                    f"element_axis_z_{self._solid_index}",
                    _direction_tuple(placement, (0.0, 0.0, 1.0)),
                ],
            )
            axis_x = self.writer.add_entity(
                "DIRECTION",
                [
                    f"element_axis_x_{self._solid_index}",
                    _direction_tuple(placement, (1.0, 0.0, 0.0)),
                ],
            )
        else:
            axis_z, axis_x = self.dir_z, self.dir_x

        # Rim sag from the single source of truth (Lens.get_sag_1/2).
        # Near-flat surfaces stay exactly planar for CAD topology; a
        # zero-sag parabola is flat even though its radius is finite.
        is_flat1 = _surface_is_flat(lens, 1)
        is_flat2 = _surface_is_flat(lens, 2)

        z_edge1 = z_offset + (0.0 if is_flat1 else lens.get_sag_1(h))  # z of top rim
        z_edge2 = z_offset + thick + (0.0 if is_flat2 else lens.get_sag_2(h))

        # --- Points ---
        # Vertex 1 (on axis)
        self.writer.add_entity("CARTESIAN_POINT", ["v1", point(0.0, 0.0, z_offset)])
        # Vertex 2 (on axis)
        self.writer.add_entity("CARTESIAN_POINT", ["v2", point(0.0, 0.0, z_offset + thick)])

        # Edge Point 1 (Start of edge loop 1) at (h, 0, z_edge1)
        p_e1 = self.writer.add_entity("CARTESIAN_POINT", ["e1", point(h, 0.0, z_edge1)])
        # Edge Point 2 (Start of edge loop 2) at (h, 0, z_edge2)
        p_e2 = self.writer.add_entity("CARTESIAN_POINT", ["e2", point(h, 0.0, z_edge2)])

        # --- Edge Curves (Circles) ---
        # Edge 1 Circle
        # Center at (0, 0, z_edge1)
        p_c1 = self.writer.add_entity("CARTESIAN_POINT", ["c1", point(0.0, 0.0, z_edge1)])
        axis_c1 = self.writer.add_entity("AXIS2_PLACEMENT_3D", ["axis_c1", p_c1, axis_z, axis_x])
        circle1 = self.writer.add_entity("CIRCLE", ["circle1", axis_c1, h])

        # Edge 2 Circle
        p_c2 = self.writer.add_entity("CARTESIAN_POINT", ["c2", point(0.0, 0.0, z_edge2)])
        axis_c2 = self.writer.add_entity("AXIS2_PLACEMENT_3D", ["axis_c2", p_c2, axis_z, axis_x])
        circle2 = self.writer.add_entity("CIRCLE", ["circle2", axis_c2, h])

        # --- Edges ---
        # We need a VERTEX_POINT for the seam (at angle 0)
        v_e1 = self.writer.add_entity("VERTEX_POINT", ["v_e1", p_e1])
        v_e2 = self.writer.add_entity("VERTEX_POINT", ["v_e2", p_e2])

        # EDGE_CURVE for Edge 1 (Full circle)
        # Note: STEP usually requires splitting closed curves into 1 or 2 segments?
        # A single EDGE_CURVE with same start/end vertex on a circle is allowed in some schemas,
        # but robust exporters use 2 semicircles or just declare it as an EDGE_LOOP with one edge.
        # Let's try single edge.
        edge1 = self.writer.add_entity("EDGE_CURVE", ["edge1", v_e1, v_e1, circle1, STEP_TRUE])

        # EDGE_CURVE for Edge 2
        edge2 = self.writer.add_entity("EDGE_CURVE", ["edge2", v_e2, v_e2, circle2, STEP_TRUE])

        # Longitudinal Seam Edge (connecting e1 to e2 along cylinder)
        # Line segment
        line_seam = self.writer.add_entity(
            "LINE",
            [
                "seam_line",
                p_e1,
                self.writer.add_entity("VECTOR", ["dir_z", axis_z, 1.0]),
            ],
        )
        self.writer.add_entity("EDGE_CURVE", ["edge_seam", v_e1, v_e2, line_seam, STEP_TRUE])

        # --- Loops ---
        # Loop 1 (Front Face boundary)
        # If R1>0 (Convex), normal points -Z (away from surface).
        # Loop orientation must be CCW around normal.
        # This is tricky.
        loop1 = self.writer.add_entity(
            "EDGE_LOOP",
            [
                "loop1",
                [
                    self.writer.add_entity(
                        "ORIENTED_EDGE", [STEP_DERIVED, STEP_DERIVED, edge1, STEP_TRUE]
                    )
                ],
            ],
        )

        # Loop 2 (Back Face boundary)
        loop2 = self.writer.add_entity(
            "EDGE_LOOP",
            [
                "loop2",
                [
                    self.writer.add_entity(
                        "ORIENTED_EDGE", [STEP_DERIVED, STEP_DERIVED, edge2, STEP_TRUE]
                    )
                ],
            ],
        )

        # Loop 3 (Cylinder boundary)
        # Needs 2 circles and seams?
        # Actually, if we just define the faces bounded by these loops...
        # Cylinder Face needs 2 loops (top and bottom).
        # Bounds: edge1 and edge2.

        # --- Surfaces ---
        # Surface 1 (Front)
        if is_flat1:
            plane1 = self.writer.add_entity("PLANE", ["plane1", axis_c1])  # Normal +Z
            surf1 = plane1
        else:
            # Sphere
            # Center of curvature
            if r1 > 0:
                c_z = z_offset + r1
            else:
                c_z = z_offset + r1  # r1 is negative

            p_center1 = self.writer.add_entity("CARTESIAN_POINT", ["center1", point(0.0, 0.0, c_z)])
            axis_s1 = self.writer.add_entity(
                "AXIS2_PLACEMENT_3D", ["axis_s1", p_center1, axis_z, axis_x]
            )
            surf1 = self.writer.add_entity("SPHERICAL_SURFACE", ["sphere1", axis_s1, abs(r1)])

        # Surface 2 (Back)
        if is_flat2:
            plane2 = self.writer.add_entity("PLANE", ["plane2", axis_c2])
            surf2 = plane2
        else:
            if r2 < 0:  # Convex back
                c_z = z_offset + thick - abs(r2)  # ? r2 is neg. Center at T+R2 (left)
                # Wait, if r2=-100. Center = T-100. Correct.
            else:  # Concave back
                c_z = z_offset + thick + r2

            p_center2 = self.writer.add_entity("CARTESIAN_POINT", ["center2", point(0.0, 0.0, c_z)])
            axis_s2 = self.writer.add_entity(
                "AXIS2_PLACEMENT_3D", ["axis_s2", p_center2, axis_z, axis_x]
            )
            surf2 = self.writer.add_entity("SPHERICAL_SURFACE", ["sphere2", axis_s2, abs(r2)])

        # Surface 3 (Rim): a custom profile is the revolved meridional chain,
        # so the exported rim is the same polyline the STL and views use.
        # Without one this stays the historical cylinder.
        if getattr(lens, "edge_profile", None):
            edge = LensGeometry.edge_profile_points(lens)
            sweep_points = [
                self.writer.add_entity(
                    "CARTESIAN_POINT",
                    [f"rim_p{index}", point(radius, 0.0, z_offset + x)],
                )
                for index, (x, radius) in enumerate(edge)
            ]
            sweep = self.writer.add_entity("POLYLINE", ["rim_profile", sweep_points])
            axis_rev = self.writer.add_entity(
                "AXIS2_PLACEMENT_3D", ["axis_rev", p_c1, axis_z, axis_x]
            )
            surf3 = self.writer.add_entity(
                "SURFACE_OF_REVOLUTION", ["rim_revolution", sweep, axis_rev]
            )
        else:
            axis_cyl = self.writer.add_entity(
                "AXIS2_PLACEMENT_3D", ["axis_cyl", p_c1, axis_z, axis_x]
            )
            surf3 = self.writer.add_entity("CYLINDRICAL_SURFACE", ["cyl", axis_cyl, h])

        # --- Faces ---
        # Face 1 (Front)
        # Bounds: loop1
        # Orientation depends on convex/concave.
        face1 = self.writer.add_entity(
            "ADVANCED_FACE",
            [
                "face1",
                [self.writer.add_entity("FACE_BOUND", ["b1", loop1, STEP_TRUE])],
                surf1,
                STEP_TRUE,
            ],
        )

        # Face 2 (Back)
        face2 = self.writer.add_entity(
            "ADVANCED_FACE",
            [
                "face2",
                [self.writer.add_entity("FACE_BOUND", ["b2", loop2, STEP_TRUE])],
                surf2,
                STEP_TRUE,
            ],
        )

        # Face 3 (Cylinder)
        # Bounds: loop1 and loop2
        # Need to orient edges correctly so they form a valid boundary for the cylinder
        # This is where single-edge loops are tricky for cylinders without seams.
        # But for STEP, we can try using the loops directly.

        # For a cylinder, we usually need a seam if we use a closed surface.
        # But let's try just listing the bounds.
        # One bound is the front circle, one is the back.

        b3_1 = self.writer.add_entity("FACE_BOUND", ["b3_1", loop1, STEP_TRUE])
        b3_2 = self.writer.add_entity("FACE_BOUND", ["b3_2", loop2, STEP_TRUE])

        face3 = self.writer.add_entity("ADVANCED_FACE", ["face3", [b3_1, b3_2], surf3, STEP_TRUE])

        # --- Shell ---
        shell = self.writer.add_entity("CLOSED_SHELL", ["shell", [face1, face2, face3]])

        # --- Solid ---
        # Carry the manufacturing aperture in the solid name so downstream
        # CAD keeps it even though the B-rep itself is built on the
        # mechanical outer diameter (bevel chamfer faces are not modeled).
        solid = self.writer.add_entity("MANIFOLD_SOLID_BREP", [f"{self._solid_label(lens)}", shell])

        return solid

    def _export_tube_solid(self, name: str, z0: float, z1: float, r_inner: float, r_outer: float):
        """Create a B-Rep annular tube solid (spacer, barrel, retainer).

        A hollow cylinder from z0 to z1 with inner radius r_inner and
        outer radius r_outer: two planar ring faces plus inner and outer
        cylindrical faces. Same hand-written, viewer-lenient style as the
        lens solids above (no CAD kernel in this environment).
        """
        if not (r_outer > r_inner > 0 and z1 > z0):
            logger.warning(
                "STEP tube %r skipped - need r_outer > r_inner > 0 and z1 > z0, "
                "got r_inner=%r r_outer=%r z0=%r z1=%r",
                name,
                r_inner,
                r_outer,
                z0,
                z1,
            )
            return None

        def _circle(label: str, z: float, r: float):
            pc = self.writer.add_entity("CARTESIAN_POINT", [f"{label}_c", (0.0, 0.0, z)])
            ax = self.writer.add_entity(
                "AXIS2_PLACEMENT_3D", [f"{label}_ax", pc, self.dir_z, self.dir_x]
            )
            return self.writer.add_entity("CIRCLE", [f"{label}", ax, r])

        def _edge(label: str, circle_id: int, z: float, r: float):
            pe = self.writer.add_entity("CARTESIAN_POINT", [f"{label}_p", (r, 0.0, z)])
            ve = self.writer.add_entity("VERTEX_POINT", [f"{label}_v", pe])
            return self.writer.add_entity("EDGE_CURVE", [f"{label}", ve, ve, circle_id, STEP_TRUE])

        def _loop(label: str, edge_id: int):
            oriented = self.writer.add_entity(
                "ORIENTED_EDGE", [STEP_DERIVED, STEP_DERIVED, edge_id, STEP_TRUE]
            )
            return self.writer.add_entity("EDGE_LOOP", [f"{label}", [oriented]])

        c_top_out = _circle(f"{name}_to", z1, r_outer)
        c_top_in = _circle(f"{name}_ti", z1, r_inner)
        c_bot_out = _circle(f"{name}_bo", z0, r_outer)
        c_bot_in = _circle(f"{name}_bi", z0, r_inner)

        e_top_out = _edge(f"{name}_to", c_top_out, z1, r_outer)
        e_top_in = _edge(f"{name}_ti", c_top_in, z1, r_inner)
        e_bot_out = _edge(f"{name}_bo", c_bot_out, z0, r_outer)
        e_bot_in = _edge(f"{name}_bi", c_bot_in, z0, r_inner)

        loop_top_out = _loop(f"{name}_lto", e_top_out)
        loop_top_in = _loop(f"{name}_lti", e_top_in)
        loop_bot_out = _loop(f"{name}_lbo", e_bot_out)
        loop_bot_in = _loop(f"{name}_lbi", e_bot_in)

        # Planar ring faces (outer bound + inner hole bound each).
        p_top = self.writer.add_entity("CARTESIAN_POINT", [f"{name}_pt", (0.0, 0.0, z1)])
        ax_top = self.writer.add_entity(
            "AXIS2_PLACEMENT_3D", [f"{name}_axt", p_top, self.dir_z, self.dir_x]
        )
        plane_top = self.writer.add_entity("PLANE", [f"{name}_plt", ax_top])
        face_top = self.writer.add_entity(
            "ADVANCED_FACE",
            [
                f"{name}_ft",
                [
                    self.writer.add_entity("FACE_BOUND", [f"{name}_bt1", loop_top_out, STEP_TRUE]),
                    self.writer.add_entity("FACE_BOUND", [f"{name}_bt2", loop_top_in, STEP_TRUE]),
                ],
                plane_top,
                STEP_TRUE,
            ],
        )

        p_bot = self.writer.add_entity("CARTESIAN_POINT", [f"{name}_pb", (0.0, 0.0, z0)])
        ax_bot = self.writer.add_entity(
            "AXIS2_PLACEMENT_3D", [f"{name}_axb", p_bot, self.dir_z, self.dir_x]
        )
        plane_bot = self.writer.add_entity("PLANE", [f"{name}_plb", ax_bot])
        face_bot = self.writer.add_entity(
            "ADVANCED_FACE",
            [
                f"{name}_fb",
                [
                    self.writer.add_entity("FACE_BOUND", [f"{name}_bb1", loop_bot_out, STEP_TRUE]),
                    self.writer.add_entity("FACE_BOUND", [f"{name}_bb2", loop_bot_in, STEP_TRUE]),
                ],
                plane_bot,
                STEP_TRUE,
            ],
        )

        # Cylindrical faces bounded by the ring loops.
        ax_cyl = self.writer.add_entity(
            "AXIS2_PLACEMENT_3D", [f"{name}_axc", p_bot, self.dir_z, self.dir_x]
        )
        surf_outer = self.writer.add_entity("CYLINDRICAL_SURFACE", [f"{name}_co", ax_cyl, r_outer])
        face_outer = self.writer.add_entity(
            "ADVANCED_FACE",
            [
                f"{name}_fo",
                [
                    self.writer.add_entity("FACE_BOUND", [f"{name}_bo1", loop_top_out, STEP_TRUE]),
                    self.writer.add_entity("FACE_BOUND", [f"{name}_bo2", loop_bot_out, STEP_TRUE]),
                ],
                surf_outer,
                STEP_TRUE,
            ],
        )
        surf_inner = self.writer.add_entity("CYLINDRICAL_SURFACE", [f"{name}_ci", ax_cyl, r_inner])
        face_inner = self.writer.add_entity(
            "ADVANCED_FACE",
            [
                f"{name}_fi",
                [
                    self.writer.add_entity("FACE_BOUND", [f"{name}_bi1", loop_top_in, STEP_TRUE]),
                    self.writer.add_entity("FACE_BOUND", [f"{name}_bi2", loop_bot_in, STEP_TRUE]),
                ],
                surf_inner,
                STEP_TRUE,
            ],
        )

        shell = self.writer.add_entity(
            "CLOSED_SHELL", ["shell", [face_top, face_bot, face_outer, face_inner]]
        )
        return self.writer.add_entity("MANIFOLD_SOLID_BREP", [f"{name}", shell])

    @staticmethod
    def _solid_label(lens) -> str:
        """Human-readable solid name with clear-aperture/bevel/coating data."""
        name = getattr(lens, "name", "lens")
        diameter = getattr(lens, "diameter", None)
        ca1 = getattr(lens, "clear_aperture_1", None)
        ca2 = getattr(lens, "clear_aperture_2", None)
        bevel_1 = float(getattr(lens, "bevel_1", 0.0) or 0.0)
        bevel_2 = float(getattr(lens, "bevel_2", 0.0) or 0.0)
        details = []
        if ca1 is not None or ca2 is not None:
            show1 = diameter if ca1 is None else ca1
            show2 = diameter if ca2 is None else ca2
            details.append(f"CA {show1}/{show2}")
        if bevel_1 or bevel_2:
            details.append(f"bevel {bevel_1}/{bevel_2}")
        coat1 = lens.coating_label(1) if hasattr(lens, "coating_label") else "Uncoated"
        coat2 = lens.coating_label(2) if hasattr(lens, "coating_label") else "Uncoated"
        if coat1 != "Uncoated" or coat2 != "Uncoated":
            details.append(f"coat {coat1}/{coat2}")
        if details:
            return f"{name} ({', '.join(details)})"
        return str(name)

    def _create_product_structure(self, shape_ids):
        """Create high-level product structure."""
        if not shape_ids:
            return

        # The ids from add_entity are StepRefs, so they are written as
        # references. Interpolating them into "#47" strings quoted them.
        self.writer.add_entity(
            "ADVANCED_BREP_SHAPE_REPRESENTATION",
            ["lens_geom", list(shape_ids), self.geom_context],
        )
