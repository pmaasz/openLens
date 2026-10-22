import sqlite3
import json
import logging
from contextlib import contextmanager
from typing import List, Dict, Any, Iterator, Optional

from .paths import ensure_parent_dir, resolve_db_path

logger = logging.getLogger(__name__)

# The schema version this build writes. Deliberately local rather than in
# openlens/constants.py: it is meaningless anywhere except the migration ladder in
# DatabaseManager._initialize_db, and keeping it there keeps this module free
# of intra-package imports.
SCHEMA_VERSION = 7


def _coating_json(value) -> Optional[str]:
    """Encode a coating stack for its TEXT column (None = uncoated)."""
    if value is None:
        return None
    if isinstance(value, (list, tuple)) and len(value) == 0:
        return None
    return json.dumps(list(value))


def _coating_parse(raw) -> Optional[list]:
    """Decode a coating TEXT column back to a layer list (None = uncoated)."""
    if raw is None:
        return None
    try:
        parsed = json.loads(raw)
    except (ValueError, TypeError):
        return None
    if not parsed:
        return None
    return parsed


def _metadata_merge(target: Dict[str, Any], raw: Any, what: str) -> Dict[str, Any]:
    """Merge a metadata JSON blob into ``target``, tolerating a bad blob.

    Mirrors :func:`_coating_parse`. A truncated or hand-edited blob used to
    raise JSONDecodeError straight out of load_all, and LensStorage.load_lenses
    catches broad Exception and returns [] - so one corrupt row left the user
    looking at an entirely empty library with only a log line to explain it.
    A blob that is valid JSON but not an object raises TypeError/ValueError
    from dict.update, so that is caught too.

    Returns the parsed object (empty when absent or unusable). The blob is
    merged flat into ``target`` so keys written by older builds - ``lens_type``,
    ``wavelength`` and friends, which never had columns - keep resolving
    against the row dict. Returning it is also what lets the caller hand it to
    the model as its own ``metadata`` attribute: a reloaded Lens used to come
    back with no ``metadata`` at all, so a saved tolerance set vanished.
    """
    if not raw:
        return {}
    if isinstance(raw, (dict, list)):
        meta = raw
    else:
        try:
            meta = json.loads(raw)
        except (ValueError, TypeError) as e:
            logger.warning("Ignoring unparseable %s metadata: %s", what, e)
            return {}
    if not isinstance(meta, dict):
        logger.warning(
            "Ignoring %s metadata: expected an object, got %s", what, type(meta).__name__
        )
        return {}
    target.update(meta)
    return dict(meta)


def _metadata_payload(source: Dict[str, Any], column_keys) -> str:
    """Build the flat metadata blob for a row.

    Anything without a dedicated column goes in the blob, and so does the
    model's own ``metadata`` dict - flattened into the same level rather than
    nested. Nesting would write ``{"metadata": {"metadata": ...}}`` and would
    break every existing reader, which expects the blob to be flat.
    """
    blob = {k: v for k, v in source.items() if k not in column_keys}
    nested = source.get("metadata") or {}
    if isinstance(nested, dict):
        blob.update(nested)
    return json.dumps(blob)


class LensInUseError(RuntimeError):
    """Raised when deleting a lens that is still used by assemblies.

    Attributes:
        lens_id: Id of the lens that could not be deleted.
        assemblies: List of (assembly_id, assembly_name) referencing it.
    """

    def __init__(self, lens_id: str, assemblies):
        self.lens_id = lens_id
        self.assemblies = list(assemblies)
        names = ", ".join(f"'{name}' (id={aid})" for aid, name in assemblies)
        super().__init__(
            f"Lens {lens_id} is still used by {len(self.assemblies)} "
            f"assembly(ies): {names}. Remove it from those assemblies first."
        )


class UnsupportedSchemaVersionError(RuntimeError):
    """Raised when a database was written by a newer OpenLens than this one.

    Migrating downwards would drop columns the newer build relies on and
    corrupt the library, so the file is refused instead of being opened.

    Attributes:
        found: ``user_version`` recorded in the database.
        supported: The highest schema version this build understands.
        path: The database file that was refused.
    """

    def __init__(self, found: int, supported: int, path: str):
        self.found = found
        self.supported = supported
        self.path = path
        super().__init__(
            f"Database '{path}' has schema version {found}, but this OpenLens "
            f"only supports up to version {supported}. It was written by a newer "
            "OpenLens; upgrade OpenLens rather than opening this file with an "
            "older build, which would downgrade the library and lose data."
        )


@contextmanager
def _transaction(cursor: sqlite3.Cursor) -> Iterator[sqlite3.Cursor]:
    """Run a block as one immediate transaction on an autocommit connection.

    ``BEGIN IMMEDIATE`` takes the write lock up front, so two processes
    starting at once serialise here instead of interleaving their DDL. On any
    error the whole block is rolled back, which is what makes a migration
    all-or-nothing: DDL is transactional in SQLite, so a partial migration
    cannot survive.
    """
    cursor.execute("BEGIN IMMEDIATE")
    try:
        yield cursor
    except Exception:
        cursor.execute("ROLLBACK")
        raise
    cursor.execute("COMMIT")


def _table_columns(cursor: sqlite3.Cursor, table: str) -> set:
    """Column names of ``table`` (empty if it does not exist)."""
    cursor.execute(f"PRAGMA table_info({table})")
    return {row[1] for row in cursor.fetchall()}


def _table_exists(cursor: sqlite3.Cursor, table: str) -> bool:
    """Whether ``table`` is already present in the database."""
    cursor.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,))
    return cursor.fetchone() is not None


def _add_column(cursor: sqlite3.Cursor, table: str, column: str, decl: str) -> bool:
    """Add a column if absent. Returns True when it actually added one.

    Makes a migration idempotent: a database left half-migrated by an older
    build (or by a crash) already has some of the columns, and re-adding one
    would raise "duplicate column name" on every subsequent launch.
    """
    if column in _table_columns(cursor, table):
        return False
    cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")
    return True


class DatabaseManager:
    """Handles SQLite database operations for Lens and OpticalSystem storage."""

    def __init__(self, db_path: Optional[str] = None):
        # Resolved at call time, not import time: a default argument is
        # evaluated once when the module loads, so an explicit path set after
        # import - by a test, or by $OPENLENS_DB_PATH - would be ignored.
        self.db_path = resolve_db_path(db_path)
        ensure_parent_dir(self.db_path)
        self._initialize_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Open a configured connection (autocommit mode).

        Callers are responsible for closing it; prefer the
        :meth:`_connection` context manager inside this class.
        """
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.isolation_level = None  # autocommit: explicit BEGIN for atomic blocks
        conn.row_factory = sqlite3.Row  # name-based access everywhere
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")  # Ensure foreign keys are enforced
        return conn

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        """Yield a configured connection that is always closed."""
        conn = self._get_connection()
        try:
            yield conn
        finally:
            conn.close()

    @contextmanager
    def _write_transaction(self) -> Iterator[sqlite3.Cursor]:
        """Run a block as one immediate transaction and commit it atomically.

        Yields:
            A cursor on a fresh autocommit connection, inside ``BEGIN
            IMMEDIATE``. Any exception rolls the whole block back.
        """
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("BEGIN IMMEDIATE")
            try:
                yield cursor
            except Exception:
                cursor.execute("ROLLBACK")
                raise
            cursor.execute("COMMIT")

    def _initialize_db(self):
        """Create tables if they don't exist and handle migrations.

        The whole version-detect-then-migrate sequence runs in one
        ``BEGIN IMMEDIATE`` transaction. Previously each ALTER and each
        ``PRAGMA user_version`` write was its own implicit transaction under
        autocommit, so a process that died between two ALTERs left
        ``user_version`` at the old value: the next launch replayed the same
        ALTERs and raised "duplicate column name", and because this runs
        unguarded from ``__init__`` every later launch failed identically.
        The app could never be started again without deleting the database.
        """
        with self._connection() as conn:
            cursor = conn.cursor()
            with _transaction(cursor):

                # Check version
                cursor.execute("PRAGMA user_version")
                version = cursor.fetchone()[0]

                if version > SCHEMA_VERSION:
                    # Written by a newer OpenLens. Refusing beats opening: a
                    # downgrade would leave the newer build's columns in place
                    # while stamping an older version over them.
                    raise UnsupportedSchemaVersionError(version, SCHEMA_VERSION, self.db_path)

                if version == 0:
                    # A database from before the user_version pragma existed
                    # also reads 0, but it already has real tables - the
                    # CREATE TABLE IF NOT EXISTS statements below do nothing,
                    # and stamping it as current would skip every column added
                    # since, leaving the file permanently unsaveable. Detect
                    # that and stamp it 1 so the ladder below adds the columns
                    # to whatever it already has.
                    legacy = any(
                        _table_exists(cursor, table)
                        for table in (
                            "lenses",
                            "assemblies",
                            "assembly_elements",
                            "assembly_air_gaps",
                        )
                    )

                    # Lenses table (v7 schema: parabolic and conic surfaces are
                    # explicit columns, not just metadata-blob passengers;
                    # per-surface clear apertures and bevels likewise).
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS lenses (
                            id TEXT PRIMARY KEY,
                            name TEXT NOT NULL,
                            radius1 REAL NOT NULL,
                            radius2 REAL NOT NULL,
                            thickness REAL NOT NULL,
                            material TEXT NOT NULL,
                            refractive_index REAL,
                            diameter REAL,
                            created_at TEXT,
                            modified_at TEXT,
                            is_parabolic_1 INTEGER NOT NULL DEFAULT 0,
                            parabolic_sag_1 REAL NOT NULL DEFAULT 0.0,
                            is_parabolic_2 INTEGER NOT NULL DEFAULT 0,
                            parabolic_sag_2 REAL NOT NULL DEFAULT 0.0,
                            conic_constant_1 REAL NOT NULL DEFAULT 0.0,
                            conic_constant_2 REAL NOT NULL DEFAULT 0.0,
                            clear_aperture_1 REAL,
                            clear_aperture_2 REAL,
                            bevel_1 REAL NOT NULL DEFAULT 0.0,
                            bevel_2 REAL NOT NULL DEFAULT 0.0,
                            coating_1 TEXT,
                            coating_2 TEXT,
                            is_library INTEGER NOT NULL DEFAULT 1,
                            metadata TEXT
                        )
                    """)

                    # Assemblies table (v4: aperture stop lives here)
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS assemblies (
                            id TEXT PRIMARY KEY,
                            name TEXT NOT NULL,
                            created_at TEXT,
                            modified_at TEXT,
                            aperture_stop_gap INTEGER,
                            aperture_stop_diameter REAL,
                            metadata TEXT
                        )
                    """)

                    # Assembly Elements table (junction table; v4 carries the
                    # per-element decenter/tilt so the tree's alignment survives)
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS assembly_elements (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            assembly_id TEXT NOT NULL,
                            lens_id TEXT NOT NULL,
                            position REAL NOT NULL,
                            order_index INTEGER NOT NULL,
                            decenter_y REAL NOT NULL DEFAULT 0.0,
                            decenter_z REAL NOT NULL DEFAULT 0.0,
                            tilt_x REAL NOT NULL DEFAULT 0.0,
                            tilt_y REAL NOT NULL DEFAULT 0.0,
                            tilt_z REAL NOT NULL DEFAULT 0.0,
                            FOREIGN KEY (assembly_id) REFERENCES assemblies (id) ON DELETE CASCADE,
                            FOREIGN KEY (lens_id) REFERENCES lenses (id)
                        )
                    """)

                    # Assembly Air Gaps table
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS assembly_air_gaps (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            assembly_id TEXT NOT NULL,
                            thickness REAL NOT NULL,
                            position REAL NOT NULL,
                            order_index INTEGER NOT NULL,
                            FOREIGN KEY (assembly_id) REFERENCES assemblies (id) ON DELETE CASCADE
                        )
                    """)

                    # A legacy file is stamped 1 so the ladder below adds every
                    # column it is missing; a genuinely new file is already at
                    # the current version.
                    cursor.execute(f"PRAGMA user_version = {1 if legacy else SCHEMA_VERSION}")

                # v1 -> v2: promote parabolic surfaces from the metadata blob
                # to explicit columns. Re-reads the version instead of testing
                # the value read above, so a legacy file stamped 1 just now
                # takes this step too. Existing rows keep DEFAULT 0
                # (spherical); rows whose metadata already carries parabolic keys
                # keep working because load merges metadata over columns.
                cursor.execute("PRAGMA user_version")
                if cursor.fetchone()[0] == 1:
                    _add_column(cursor, "lenses", "is_parabolic_1", "INTEGER NOT NULL DEFAULT 0")
                    _add_column(cursor, "lenses", "parabolic_sag_1", "REAL NOT NULL DEFAULT 0.0")
                    _add_column(cursor, "lenses", "is_parabolic_2", "INTEGER NOT NULL DEFAULT 0")
                    _add_column(cursor, "lenses", "parabolic_sag_2", "REAL NOT NULL DEFAULT 0.0")
                    cursor.execute("PRAGMA user_version = 2")

                # v2 -> v3: per-surface clear apertures (NULL = full diameter)
                # and 45-degree bevel face widths (0.0 = sharp edge).
                cursor.execute("PRAGMA user_version")
                if cursor.fetchone()[0] == 2:
                    _add_column(cursor, "lenses", "clear_aperture_1", "REAL")
                    _add_column(cursor, "lenses", "clear_aperture_2", "REAL")
                    _add_column(cursor, "lenses", "bevel_1", "REAL NOT NULL DEFAULT 0.0")
                    _add_column(cursor, "lenses", "bevel_2", "REAL NOT NULL DEFAULT 0.0")
                    cursor.execute("PRAGMA user_version = 3")

                # v3 -> v4: aperture stop on assemblies, decenter/tilt on
                # assembly elements.
                cursor.execute("PRAGMA user_version")
                if cursor.fetchone()[0] == 3:
                    _add_column(cursor, "assemblies", "aperture_stop_gap", "INTEGER")
                    _add_column(cursor, "assemblies", "aperture_stop_diameter", "REAL")
                    for axis in ("decenter_y", "decenter_z", "tilt_x", "tilt_y", "tilt_z"):
                        _add_column(
                            cursor,
                            "assembly_elements",
                            axis,
                            "REAL NOT NULL DEFAULT 0.0",
                        )
                    cursor.execute("PRAGMA user_version = 4")

                # v4 -> v5: per-surface coating stacks (JSON arrays of layer
                # dicts; NULL = uncoated).
                cursor.execute("PRAGMA user_version")
                if cursor.fetchone()[0] == 4:
                    _add_column(cursor, "lenses", "coating_1", "TEXT")
                    _add_column(cursor, "lenses", "coating_2", "TEXT")
                    cursor.execute("PRAGMA user_version = 5")

                # v5 -> v6: whether a lens is a library item in its own right.
                #
                # A lens row is written for every assembly element, so before
                # this column the database could not tell a lens the user keeps
                # in the library from one that exists only inside an assembly -
                # and load_all returned both, so every assembly's lenses
                # reappeared in the library lists after a reload.
                #
                # DEFAULT 1 keeps existing databases behaving exactly as they
                # did until the application next saves, at which point the
                # membership is recorded correctly.
                cursor.execute("PRAGMA user_version")
                if cursor.fetchone()[0] == 5:
                    _add_column(cursor, "lenses", "is_library", "INTEGER NOT NULL DEFAULT 1")
                    cursor.execute("PRAGMA user_version = 6")

                # v6 -> v7: conic constants are surface geometry, like the
                # parabolic flags. Default 0 keeps every existing lens
                # spherical.
                cursor.execute("PRAGMA user_version")
                if cursor.fetchone()[0] == 6:
                    _add_column(cursor, "lenses", "conic_constant_1", "REAL NOT NULL DEFAULT 0.0")
                    _add_column(cursor, "lenses", "conic_constant_2", "REAL NOT NULL DEFAULT 0.0")
                    cursor.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

    def set_library_membership(self, library_lens_ids, demote: bool = False) -> None:
        """Record which lenses are library items in their own right.

        A lens row exists for every assembly element, so the rows alone cannot
        distinguish a lens the user keeps in the library from one that exists
        only inside an assembly. The caller *does* know: it holds the library
        snapshot. Recording that here - rather than inferring it - is what keeps
        a shared lens visible while hiding a member-only one.

        Args:
            library_lens_ids: Ids of the lenses that belong in the library.
            demote: Whether lenses absent from *library_lens_ids* may be
                demoted to assembly-only. Only the caller that owns every
                stored object may do this; see the note in
                :meth:`LensStorage.save_lenses` about partial snapshots.

        Returns:
            None
        """
        with self._write_transaction() as cursor:
            self._save_membership_rows(cursor, library_lens_ids, demote)

    def _save_membership_rows(
        self, cursor: sqlite3.Cursor, library_lens_ids, demote: bool = False
    ) -> None:
        """Write library membership inside the caller's transaction."""
        library = {str(i) for i in library_lens_ids}
        if demote:
            cursor.execute("SELECT id FROM lenses")
            for row in cursor.fetchall():
                cursor.execute(
                    "UPDATE lenses SET is_library = ? WHERE id = ?",
                    (1 if row["id"] in library else 0, row["id"]),
                )
        else:
            for lens_id in library:
                cursor.execute("UPDATE lenses SET is_library = 1 WHERE id = ?", (lens_id,))

    def save_library(
        self,
        items: List[Dict[str, Any]],
        library_lens_ids,
        demote: bool = False,
    ) -> None:
        """Save a whole library snapshot in one transaction.

        A failure on any item rolls the whole snapshot back, so the stored
        library is always one consistent save rather than the first N items
        of a failed one.

        Args:
            items: Serialized lenses and optical systems. The
                ``"OpticalSystem"`` type marker selects the assembly writer.
            library_lens_ids: Ids of the lenses that belong in the library.
            demote: See :meth:`set_library_membership`.
        """
        with self._write_transaction() as cursor:
            for item_dict in items:
                if item_dict.get("type") == "OpticalSystem":
                    self._save_assembly_rows(cursor, item_dict)
                else:
                    self._save_lens_row(cursor, item_dict)
            self._save_membership_rows(cursor, library_lens_ids, demote)

    def save_lens(self, lens_dict: Dict[str, Any]):
        """Save or update a single lens."""
        try:
            with self._write_transaction() as cursor:
                self._save_lens_row(cursor, lens_dict)
        except Exception as e:
            logger.error("Failed to save lens: %s", e)
            raise

    def _save_lens_row(
        self,
        cursor: sqlite3.Cursor,
        lens_dict: Dict[str, Any],
        library_default: int = 1,
    ) -> None:
        """Insert/replace one lenses row inside the caller's transaction.

        Does not manage the transaction itself: ``save_assembly`` uses it so
        all writes for one assembly commit atomically, and the batch library
        save uses it so the whole snapshot commits at once.

        Args:
            cursor: Cursor inside the caller's transaction.
            lens_dict: Serialized lens. The model's own metadata is folded
                into the blob's top level, so the blob has one shape for
                every lens - standalone or an assembly member.
            library_default: The ``is_library`` value for a row that does not
                exist yet - a standalone lens is a library item (1), an
                assembly member is not (0). An existing row keeps the
                membership it already has: the statement replaces the row, so
                a column it does not mention falls back to the schema default
                and silently promoted every assembly member into the library.
        """
        lens_id = lens_dict.get("id")
        if "is_library" in lens_dict:
            # A row that was loaded from the database carries its membership.
            is_library = 1 if lens_dict.get("is_library") else 0
        else:
            existing = cursor.execute(
                "SELECT is_library FROM lenses WHERE id = ?", (lens_id,)
            ).fetchone()
            is_library = int(existing["is_library"]) if existing is not None else library_default

        cursor.execute(
            """
            INSERT OR REPLACE INTO lenses
            (id, name, radius1, radius2, thickness, material, refractive_index, diameter,
             created_at, modified_at,
             is_parabolic_1, parabolic_sag_1, is_parabolic_2, parabolic_sag_2,
             conic_constant_1, conic_constant_2,
             clear_aperture_1, clear_aperture_2, bevel_1, bevel_2,
             coating_1, coating_2,
             is_library, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                lens_id,
                lens_dict.get("name"),
                lens_dict.get("radius_of_curvature_1", lens_dict.get("radius1")),
                lens_dict.get("radius_of_curvature_2", lens_dict.get("radius2")),
                lens_dict.get("thickness"),
                lens_dict.get("material"),
                lens_dict.get("refractive_index"),
                lens_dict.get("diameter"),
                lens_dict.get("created_at"),
                lens_dict.get("modified_at"),
                1 if lens_dict.get("is_parabolic_1") else 0,
                float(lens_dict.get("parabolic_sag_1", 0.0) or 0.0),
                1 if lens_dict.get("is_parabolic_2") else 0,
                float(lens_dict.get("parabolic_sag_2", 0.0) or 0.0),
                float(lens_dict.get("conic_constant_1", 0.0) or 0.0),
                float(lens_dict.get("conic_constant_2", 0.0) or 0.0),
                lens_dict.get("clear_aperture_1"),
                lens_dict.get("clear_aperture_2"),
                float(lens_dict.get("bevel_1", 0.0) or 0.0),
                float(lens_dict.get("bevel_2", 0.0) or 0.0),
                _coating_json(lens_dict.get("coating_1")),
                _coating_json(lens_dict.get("coating_2")),
                is_library,
                json.dumps(
                    {
                        k: v
                        for k, v in lens_dict.items()
                        if k
                        not in [
                            "id",
                            "name",
                            "radius_of_curvature_1",
                            "radius_of_curvature_2",
                            "radius1",
                            "radius2",
                            "thickness",
                            "material",
                            "refractive_index",
                            "diameter",
                            "created_at",
                            "modified_at",
                            "is_parabolic_1",
                            "parabolic_sag_1",
                            "is_parabolic_2",
                            "parabolic_sag_2",
                            "conic_constant_1",
                            "conic_constant_2",
                            "clear_aperture_1",
                            "clear_aperture_2",
                            "bevel_1",
                            "bevel_2",
                            "coating_1",
                            "coating_2",
                            # A column, not metadata: copying it into the
                            # blob would store the membership twice and let
                            # the blob shadow the column on the way back.
                            "is_library",
                            # A row marker, not metadata either.
                            "row_type",
                            # The model's own metadata is folded into the
                            # blob below, so it must not be copied as a
                            # nested key: the reader drops the nested form
                            # ("metadata" is one of the model's own keys),
                            # and the user's settings were lost with it.
                            "metadata",
                        ]
                    }
                    | dict(lens_dict.get("metadata") or {})
                ),
            ),
        )

    def save_assembly(self, assembly_dict: Dict[str, Any]):
        """Save or update an optical system assembly.

        All writes (assembly row, elements, air gaps) happen inside a
        single BEGIN IMMEDIATE ... COMMIT block.
        """
        try:
            with self._write_transaction() as cursor:
                self._save_assembly_rows(cursor, assembly_dict)
        except Exception as e:
            logger.error("Failed to save assembly: %s", e)
            raise

    def _save_assembly_rows(self, cursor: sqlite3.Cursor, assembly_dict: Dict[str, Any]) -> None:
        """Write one assembly row, its elements and its air gaps.

        Runs inside the caller's transaction so a whole library save can
        commit all of its assemblies and lenses at once.
        """
        assembly_id = assembly_dict.get("id")
        # 1. Save assembly metadata
        cursor.execute(
            """
            INSERT OR REPLACE INTO assemblies
            (id, name, created_at, modified_at,
             aperture_stop_gap, aperture_stop_diameter, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (
                assembly_id,
                assembly_dict.get("name"),
                assembly_dict.get("created_at"),
                assembly_dict.get("modified_at"),
                assembly_dict.get("aperture_stop_gap"),
                assembly_dict.get("aperture_stop_diameter"),
                json.dumps(
                    {
                        k: v
                        for k, v in assembly_dict.items()
                        if k
                        not in [
                            "id",
                            "name",
                            "created_at",
                            "modified_at",
                            "aperture_stop_gap",
                            "aperture_stop_diameter",
                            "elements",
                            "air_gaps",
                            "metadata",
                        ]
                    }
                    | dict(assembly_dict.get("metadata") or {})
                ),
            ),
        )

        # 2. Clear existing elements and gaps for this assembly
        cursor.execute(
            "DELETE FROM assembly_elements WHERE assembly_id = ?",
            (assembly_id,),
        )
        cursor.execute(
            "DELETE FROM assembly_air_gaps WHERE assembly_id = ?",
            (assembly_id,),
        )

        # 3. Save elements
        for i, elem in enumerate(assembly_dict.get("elements", [])):
            lens_data = elem.get("lens")
            # library_default=0: a lens that exists only inside an assembly is
            # not a library item. The membership write that follows decides
            # the rest - it promotes the ids that really are in the library.
            self._save_lens_row(cursor, lens_data, library_default=0)

            cursor.execute(
                """
                INSERT INTO assembly_elements
                (assembly_id, lens_id, position, order_index,
                 decenter_y, decenter_z, tilt_x, tilt_y, tilt_z)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    assembly_id,
                    lens_data.get("id"),
                    elem.get("position"),
                    i,
                    float(elem.get("decenter_y", 0.0) or 0.0),
                    float(elem.get("decenter_z", 0.0) or 0.0),
                    float(elem.get("tilt_x", 0.0) or 0.0),
                    float(elem.get("tilt_y", 0.0) or 0.0),
                    float(elem.get("tilt_z", 0.0) or 0.0),
                ),
            )

        # 4. Save air gaps
        for i, gap in enumerate(assembly_dict.get("air_gaps", [])):
            cursor.execute(
                """
                INSERT INTO assembly_air_gaps (assembly_id, thickness, position, order_index)
                VALUES (?, ?, ?, ?)
            """,
                (assembly_id, gap.get("thickness"), gap.get("position"), i),
            )

    def load_all(self) -> List[Dict[str, Any]]:
        """Load all standalone lenses and assemblies.

        Every returned row carries a ``row_type`` of ``"Lens"`` or
        ``"OpticalSystem"``. The marker is deliberately not ``type``: the
        stored metadata blob is merged flat onto the row, and a lens's own
        ``type`` is its lens type (``"Biconvex"``, ...), so storing the marker
        under ``type`` meant the merge always overwrote it.

        "Standalone" is the operative word. A lens row that exists only as an
        element of an assembly is *not* a library item, and returning it as a
        top-level "Lens" made every assembly member reappear in the lens lists
        after a reload::

            [OpticalSystem A(L1, L2)]  ->  [Lens L1, Lens L2, OpticalSystem A]

        It then also made every full save try to delete each of them, which the
        in-use guard correctly refused - so each save reported one failure per
        assembly lens.

        Assembly members are still read, and kept in the lookup, because the
        assemblies below need them.
        """
        results = []
        lenses_lookup = {}

        with self._connection() as conn:
            cursor = conn.cursor()

            # 1. Load all lenses first (including those in assemblies).
            # is_library is what the save path recorded: a lens the user keeps
            # in the library stays visible even when an assembly also uses it.
            cursor.execute("SELECT * FROM lenses")
            for row in cursor.fetchall():
                lens = dict(row)
                lens["radius_of_curvature_1"] = lens["radius1"]
                lens["radius_of_curvature_2"] = lens["radius2"]
                del lens["radius1"]
                del lens["radius2"]
                lens["metadata"] = _metadata_merge(
                    lens, lens.pop("metadata", None), f"lens {lens['id']}"
                )
                # The row marker lives under its own key, set after the merge.
                # "type" belongs to the payload: Lens.to_dict()["type"] is the
                # lens type ("Biconvex"), and _metadata_merge flattens the blob
                # onto the row, so a marker stored under "type" was always
                # overwritten and every lens came back as "Biconvex". After the
                # merge, a stored blob cannot spoof the marker either (#488).
                lens["row_type"] = "Lens"
                # Coating TEXT columns decode to layer lists; an explicit
                # blob key (hand-written rows) wins, matching the
                # parabolic convention above.
                for _ckey in ("coating_1", "coating_2"):
                    _raw = lens.get(_ckey)
                    lens[_ckey] = _coating_parse(_raw) if isinstance(_raw, str) else _raw
                # Always available to assemblies, whether or not it is a
                # library item in its own right.
                lenses_lookup[lens["id"]] = lens
                if lens.get("is_library", 1):
                    results.append(lens)

            # 2. Load all assemblies
            cursor.execute("SELECT * FROM assemblies")
            for row in cursor.fetchall():
                assembly = dict(row)
                assembly_id = assembly["id"]

                # Load metadata
                assembly["metadata"] = _metadata_merge(
                    assembly, assembly.pop("metadata", None), f"assembly {assembly_id}"
                )
                # Same contract as the lens marker above.
                assembly["row_type"] = "OpticalSystem"

                # Load elements. Named columns only: both tables define an
                # 'id' column, so 'l.*' would create a duplicate key whose
                # winner depends on column order.
                cursor.execute(
                    """
                    SELECT l.id AS lens_pk,
                           l.name AS lens_name,
                           l.radius1 AS lens_radius1,
                           l.radius2 AS lens_radius2,
                           l.thickness AS lens_thickness,
                           l.material AS lens_material,
                           l.refractive_index AS lens_refractive_index,
                           l.diameter AS lens_diameter,
                            l.created_at AS lens_created_at,
                            l.modified_at AS lens_modified_at,
                             l.is_parabolic_1 AS lens_is_parabolic_1,
                             l.parabolic_sag_1 AS lens_parabolic_sag_1,
                             l.is_parabolic_2 AS lens_is_parabolic_2,
                             l.parabolic_sag_2 AS lens_parabolic_sag_2,
                             l.conic_constant_1 AS lens_conic_constant_1,
                             l.conic_constant_2 AS lens_conic_constant_2,
                             l.clear_aperture_1 AS lens_clear_aperture_1,
                             l.clear_aperture_2 AS lens_clear_aperture_2,
                             l.bevel_1 AS lens_bevel_1,
                             l.bevel_2 AS lens_bevel_2,
                             l.coating_1 AS lens_coating_1,
                             l.coating_2 AS lens_coating_2,
                             l.metadata AS lens_metadata,
                            ae.lens_id,
                            ae.position,
                            ae.decenter_y,
                            ae.decenter_z,
                            ae.tilt_x,
                            ae.tilt_y,
                            ae.tilt_z
                     FROM assembly_elements ae
                    JOIN lenses l ON ae.lens_id = l.id
                    WHERE ae.assembly_id = ?
                    ORDER BY ae.order_index
                """,
                    (assembly_id,),
                )

                elements = []
                for e_row in cursor.fetchall():
                    e_dict = dict(e_row)
                    lens_id = e_dict["lens_id"]

                    # Use the lens from lookup if possible to ensure identity
                    if lens_id in lenses_lookup:
                        lens_data = lenses_lookup[lens_id]
                    else:
                        lens_data = {
                            "id": e_dict["lens_pk"],
                            "name": e_dict["lens_name"],
                            "radius_of_curvature_1": e_dict["lens_radius1"],
                            "radius_of_curvature_2": e_dict["lens_radius2"],
                            "thickness": e_dict["lens_thickness"],
                            "material": e_dict["lens_material"],
                            "refractive_index": e_dict["lens_refractive_index"],
                            "diameter": e_dict["lens_diameter"],
                            "created_at": e_dict["lens_created_at"],
                            "modified_at": e_dict["lens_modified_at"],
                            "is_parabolic_1": bool(e_dict["lens_is_parabolic_1"]),
                            "parabolic_sag_1": e_dict["lens_parabolic_sag_1"],
                            "is_parabolic_2": bool(e_dict["lens_is_parabolic_2"]),
                            "parabolic_sag_2": e_dict["lens_parabolic_sag_2"],
                            "conic_constant_1": e_dict["lens_conic_constant_1"],
                            "conic_constant_2": e_dict["lens_conic_constant_2"],
                            "clear_aperture_1": e_dict["lens_clear_aperture_1"],
                            "clear_aperture_2": e_dict["lens_clear_aperture_2"],
                            "bevel_1": e_dict["lens_bevel_1"],
                            "bevel_2": e_dict["lens_bevel_2"],
                            "coating_1": _coating_parse(e_dict["lens_coating_1"]),
                            "coating_2": _coating_parse(e_dict["lens_coating_2"]),
                        }
                        lens_data["metadata"] = _metadata_merge(
                            lens_data, e_dict["lens_metadata"], f"lens {lens_id}"
                        )

                    elements.append(
                        {
                            "lens": lens_data,
                            "lens_id": lens_id,
                            "position": e_dict["position"],
                            "decenter_y": e_dict["decenter_y"],
                            "decenter_z": e_dict["decenter_z"],
                            "tilt_x": e_dict["tilt_x"],
                            "tilt_y": e_dict["tilt_y"],
                            "tilt_z": e_dict["tilt_z"],
                        }
                    )

                assembly["elements"] = elements

                # Load air gaps
                cursor.execute(
                    "SELECT * FROM assembly_air_gaps WHERE assembly_id = ? ORDER BY order_index",
                    (assembly_id,),
                )
                gaps = []
                for g_row in cursor.fetchall():
                    g_dict = dict(g_row)
                    gaps.append(
                        {
                            "thickness": g_dict["thickness"],
                            "position": g_dict["position"],
                        }
                    )
                assembly["air_gaps"] = gaps

                results.append(assembly)

        return results

    def all_ids(self) -> Dict[str, List[str]]:
        """Return every stored id grouped by kind: {'lenses': [...],
        'assemblies': [...]}. Lightweight helper for reconciliation."""
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM lenses")
            lens_ids = [r["id"] for r in cursor.fetchall()]
            cursor.execute("SELECT id FROM assemblies")
            asm_ids = [r["id"] for r in cursor.fetchall()]
        return {"lenses": lens_ids, "assemblies": asm_ids}

    def lens_ids_used_by_assemblies(self) -> set:
        """Ids of every lens currently placed in at least one assembly.

        These are not library items in their own right, so reconciliation has
        no business trying to delete them - the in-use guard refuses, and one
        refusal per assembly lens on every save reads as an application fault
        rather than the guard doing its job.

        Returns:
            The set of referenced lens ids.
        """
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT lens_id FROM assembly_elements")
            return {row["lens_id"] for row in cursor.fetchall()}

    def get_referencing_assemblies(self, lens_id: str) -> List[tuple]:
        """Return (assembly_id, assembly_name) pairs using this lens."""
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT a.id, a.name
                FROM assembly_elements ae
                JOIN assemblies a ON a.id = ae.assembly_id
                WHERE ae.lens_id = ?
                ORDER BY a.name
            """,
                (lens_id,),
            )
            return [(row["id"], row["name"]) for row in cursor.fetchall()]

    def update_assembly_stop(self, assembly_id: str, gap: object, diameter: object) -> None:
        """Set just the aperture-stop columns of one assembly.

        Additive helper for seeding: fills a missing stop without touching
        elements, gaps, or user edits.
        """
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("BEGIN IMMEDIATE")
            try:
                cursor.execute(
                    "UPDATE assemblies SET aperture_stop_gap = ?,"
                    " aperture_stop_diameter = ? WHERE id = ?",
                    (gap, diameter, assembly_id),
                )
                cursor.execute("COMMIT")
            except Exception as e:
                cursor.execute("ROLLBACK")
                logger.error("Failed to update stop for %s: %s", assembly_id, e)
                raise

    def delete_item(self, item_id: str):
        """Delete a lens or assembly by ID (atomic).

        Deleting a lens that is still placed in any assembly is refused
        with :class:`LensInUseError` instead of an opaque foreign-key
        error; remove the element from the assembly first. Deleting an
        assembly cascades its element and air-gap rows.
        """
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("BEGIN IMMEDIATE")
            try:
                # Lens branch: refuse while still referenced by any assembly.
                refs = []
                if conn.execute("SELECT 1 FROM lenses WHERE id = ?", (item_id,)).fetchone():
                    cursor.execute(
                        """
                        SELECT a.id, a.name
                        FROM assembly_elements ae
                        JOIN assemblies a ON a.id = ae.assembly_id
                        WHERE ae.lens_id = ?
                        ORDER BY a.name
                    """,
                        (item_id,),
                    )
                    refs = [(r["id"], r["name"]) for r in cursor.fetchall()]
                    if refs:
                        raise LensInUseError(item_id, refs)

                cursor.execute("DELETE FROM assemblies WHERE id = ?", (item_id,))
                cursor.execute("DELETE FROM lenses WHERE id = ?", (item_id,))
                cursor.execute("COMMIT")
            except Exception as e:
                cursor.execute("ROLLBACK")
                if isinstance(e, LensInUseError):
                    # The guard working as designed, not a failure. This used to
                    # be logged at ERROR, so every full save of a library with
                    # assemblies reported one failure per assembly lens - the
                    # application reading as broken while behaving correctly.
                    logger.debug(
                        "Refused to delete %s: still in assembly %s",
                        item_id,
                        ", ".join(name for _id, name in e.assemblies) or "an assembly",
                    )
                else:
                    logger.error("Failed to delete item %s: %s", item_id, e)
                raise
