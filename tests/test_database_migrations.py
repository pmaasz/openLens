"""Regression: every historical database shape must migrate, or be refused.

Two distinct failures lived in the ``version == 0`` branch:

1. Databases written before the ``user_version`` pragma existed carry
   ``user_version = 0`` but already hold a ``lenses`` table in the v1 shape.
   The branch assumed a brand-new file, so ``CREATE TABLE IF NOT EXISTS`` did
   nothing, the version was stamped 5, and none of the columns added since v1
   (``is_parabolic_*``, ``clear_aperture_*``, ``bevel_*``, ``coating_*``) was
   ever added. Because the version then read 5, no later launch would add them
   either, and every save failed with
   "table lenses has no column named is_parabolic_1" - permanently, for a file
   the user still had.

2. A database stamped by a *newer* OpenLens than the running one
   (``user_version = 99``) opened happily and was written to, so an old build
   could silently corrupt a newer library.

Each historical version is exercised from a hand-built fixture, so a new
migration step that forgets an older shape fails here rather than on a user's
data.
"""

import json
import os
import sqlite3
import tempfile
import unittest

from openlens.database import SCHEMA_VERSION, DatabaseManager, UnsupportedSchemaVersionError

# Columns the v1 schema did not have, in the order the ladder adds them.
LENS_COLUMNS_ADDED_AFTER_V1 = (
    "is_parabolic_1",
    "parabolic_sag_1",
    "is_parabolic_2",
    "parabolic_sag_2",
    "clear_aperture_1",
    "clear_aperture_2",
    "bevel_1",
    "bevel_2",
    "coating_1",
    "coating_2",
)

V1_LENSES_DDL = """
    CREATE TABLE lenses (
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
        metadata TEXT
    )
"""

V1_ASSEMBLIES_DDL = """
    CREATE TABLE assemblies (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        created_at TEXT,
        modified_at TEXT,
        metadata TEXT
    )
"""

V1_ASSEMBLY_ELEMENTS_DDL = """
    CREATE TABLE assembly_elements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        assembly_id TEXT NOT NULL,
        lens_id TEXT NOT NULL,
        position REAL NOT NULL,
        order_index INTEGER NOT NULL,
        FOREIGN KEY (assembly_id) REFERENCES assemblies (id) ON DELETE CASCADE,
        FOREIGN KEY (lens_id) REFERENCES lenses (id)
    )
"""

V1_AIR_GAPS_DDL = """
    CREATE TABLE assembly_air_gaps (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        assembly_id TEXT NOT NULL,
        thickness REAL NOT NULL,
        position REAL NOT NULL,
        order_index INTEGER NOT NULL,
        FOREIGN KEY (assembly_id) REFERENCES assemblies (id) ON DELETE CASCADE
    )
"""

ASSEMBLY_COLUMNS_ADDED_AFTER_V1 = (
    "aperture_stop_gap",
    "aperture_stop_diameter",
)

ELEMENT_AXES_ADDED_AFTER_V1 = (
    "decenter_y",
    "decenter_z",
    "tilt_x",
    "tilt_y",
    "tilt_z",
)


def _make_v1_db(path, stamp_version=1):
    """Build the v1 schema on disk, optionally leaving user_version at 0.

    ``stamp_version=0`` reproduces the pre-pragma era: real tables, no version
    marker at all.
    """
    conn = sqlite3.connect(path)
    conn.execute(V1_LENSES_DDL)
    conn.execute(V1_ASSEMBLIES_DDL)
    conn.execute(V1_ASSEMBLY_ELEMENTS_DDL)
    conn.execute(V1_AIR_GAPS_DDL)
    conn.execute(
        "INSERT INTO lenses (id, name, radius1, radius2, thickness, material,"
        " refractive_index, diameter, created_at, modified_at, metadata)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "legacy-1",
            "Legacy Lens",
            100.0,
            -100.0,
            5.0,
            "BK7",
            1.5168,
            40.0,
            "2024-01-01T00:00:00",
            "2024-01-01T00:00:00",
            json.dumps({"lens_type": "Biconvex"}),
        ),
    )
    if stamp_version is not None:
        conn.execute(f"PRAGMA user_version = {stamp_version}")
    conn.commit()
    conn.close()


# Columns introduced by each version, as (table, column, declaration). A
# database stamped N has every entry from version 2 up to and including N -
# the ladder only ever adds forward, so the fixtures have to be cumulative or
# they describe a shape no released build ever wrote.
ADDED_IN_VERSION = {
    2: (
        ("lenses", "is_parabolic_1", "INTEGER NOT NULL DEFAULT 0"),
        ("lenses", "parabolic_sag_1", "REAL NOT NULL DEFAULT 0.0"),
        ("lenses", "is_parabolic_2", "INTEGER NOT NULL DEFAULT 0"),
        ("lenses", "parabolic_sag_2", "REAL NOT NULL DEFAULT 0.0"),
    ),
    3: (
        ("lenses", "clear_aperture_1", "REAL"),
        ("lenses", "clear_aperture_2", "REAL"),
        ("lenses", "bevel_1", "REAL NOT NULL DEFAULT 0.0"),
        ("lenses", "bevel_2", "REAL NOT NULL DEFAULT 0.0"),
    ),
    4: (
        ("assemblies", "aperture_stop_gap", "INTEGER"),
        ("assemblies", "aperture_stop_diameter", "REAL"),
        ("assembly_elements", "decenter_y", "REAL NOT NULL DEFAULT 0.0"),
        ("assembly_elements", "decenter_z", "REAL NOT NULL DEFAULT 0.0"),
        ("assembly_elements", "tilt_x", "REAL NOT NULL DEFAULT 0.0"),
        ("assembly_elements", "tilt_y", "REAL NOT NULL DEFAULT 0.0"),
        ("assembly_elements", "tilt_z", "REAL NOT NULL DEFAULT 0.0"),
    ),
    5: (
        ("lenses", "coating_1", "TEXT"),
        ("lenses", "coating_2", "TEXT"),
    ),
    6: (
        # Whether a lens is a library item in its own right, as opposed to
        # existing only as an assembly element.
        ("lenses", "is_library", "INTEGER"),
    ),
}


def _make_db_at_version(path, version):
    """Build the schema a build of the given version would have written."""
    _make_v1_db(path, stamp_version=version)

    conn = sqlite3.connect(path)
    for introduced in range(2, version + 1):
        for table, column, decl in ADDED_IN_VERSION[introduced]:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")
    conn.commit()
    conn.close()


def _user_version(path):
    conn = sqlite3.connect(path)
    try:
        return conn.execute("PRAGMA user_version").fetchone()[0]
    finally:
        conn.close()


def _columns(path, table):
    conn = sqlite3.connect(path)
    try:
        return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    finally:
        conn.close()


def _lens_dict(**overrides):
    data = {
        "id": "legacy-1",
        "name": "Legacy Lens",
        "radius_of_curvature_1": 100.0,
        "radius_of_curvature_2": -100.0,
        "thickness": 5.0,
        "material": "BK7",
        "refractive_index": 1.5168,
        "diameter": 40.0,
    }
    data.update(overrides)
    return data


class _TempDb(unittest.TestCase):
    """Base class giving each test a throwaway database path."""

    def setUp(self):
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        self.path = tmp.name
        self.addCleanup(self._cleanup)

    def _cleanup(self):
        for suffix in ("", "-shm", "-wal"):
            if os.path.exists(self.path + suffix):
                os.remove(self.path + suffix)


class TestUnstampedLegacyDatabase(_TempDb):
    """A pre-pragma database (user_version 0 with real tables) must migrate."""

    def setUp(self):
        super().setUp()
        _make_v1_db(self.path, stamp_version=0)

    def test_migration_reaches_the_current_version(self):
        """Opening an unstamped database must leave it at the current version."""
        DatabaseManager(self.path)
        self.assertEqual(_user_version(self.path), SCHEMA_VERSION)

    def test_migration_adds_every_column_added_since_v1(self):
        """Every column added since v1 must actually be present afterwards."""
        DatabaseManager(self.path)
        columns = _columns(self.path, "lenses")
        for column in LENS_COLUMNS_ADDED_AFTER_V1:
            self.assertIn(column, columns)

    def test_migration_adds_assembly_columns(self):
        """Aperture-stop and alignment columns must be added too."""
        DatabaseManager(self.path)
        self.assertLessEqual(
            set(ASSEMBLY_COLUMNS_ADDED_AFTER_V1), _columns(self.path, "assemblies")
        )
        self.assertLessEqual(
            set(ELEMENT_AXES_ADDED_AFTER_V1), _columns(self.path, "assembly_elements")
        )

    def test_saving_a_lens_succeeds(self):
        """The user-visible symptom: every save failed with a missing column."""
        db = DatabaseManager(self.path)
        db.save_lens(_lens_dict())

        rows = (
            sqlite3.connect(self.path)
            .execute("SELECT name, radius1 FROM lenses WHERE id = ?", ("legacy-1",))
            .fetchall()
        )
        self.assertEqual(rows, [("Legacy Lens", 100.0)])

    def test_existing_rows_survive_the_migration(self):
        """Migrating must not drop the lenses the user already had."""
        db = DatabaseManager(self.path)
        lenses = [item for item in db.load_all() if item.get("row_type") == "Lens"]

        self.assertEqual([lens["id"] for lens in lenses], ["legacy-1"])
        self.assertEqual(lenses[0]["name"], "Legacy Lens")

    def test_new_columns_have_usable_defaults(self):
        """Added columns must be readable on rows that predate them."""
        DatabaseManager(self.path)
        row = (
            sqlite3.connect(self.path)
            .execute(
                "SELECT is_parabolic_1, parabolic_sag_1, bevel_1, coating_1"
                " FROM lenses WHERE id = ?",
                ("legacy-1",),
            )
            .fetchone()
        )
        self.assertEqual(row, (0, 0.0, 0.0, None))


class TestPartiallyPresentLegacyTables(_TempDb):
    """An unstamped database may be missing some of the tables entirely."""

    def setUp(self):
        super().setUp()
        # Only `lenses` exists: the v0-era file predates the assembly tables.
        conn = sqlite3.connect(self.path)
        conn.execute(V1_LENSES_DDL)
        conn.commit()
        conn.close()

    def test_missing_tables_are_created_and_version_reaches_current(self):
        """Creation is idempotent, so the ladder can still add its columns."""
        DatabaseManager(self.path)

        self.assertEqual(_user_version(self.path), SCHEMA_VERSION)
        self.assertLessEqual(set(LENS_COLUMNS_ADDED_AFTER_V1), _columns(self.path, "lenses"))
        self.assertLessEqual(
            set(ASSEMBLY_COLUMNS_ADDED_AFTER_V1), _columns(self.path, "assemblies")
        )


class TestEveryHistoricalVersionMigrates(_TempDb):
    """Every version the app has ever written must reach the current one."""

    def test_each_stamped_version_migrates(self):
        for version in (1, 2, 3, 4):
            with self.subTest(version=version):
                path = self.path + f".v{version}"
                _make_db_at_version(path, version)
                self.addCleanup(self._remove, path)

                DatabaseManager(path)

                self.assertEqual(_user_version(path), SCHEMA_VERSION)
                self.assertLessEqual(set(LENS_COLUMNS_ADDED_AFTER_V1), _columns(path, "lenses"))

    def test_each_stamped_version_keeps_its_rows(self):
        """Migrating must not lose the lenses that were already stored."""
        for version in (1, 2, 3, 4, 5):
            with self.subTest(version=version):
                path = self.path + f".rows{version}"
                _make_db_at_version(path, version)
                self.addCleanup(self._remove, path)

                db = DatabaseManager(path)
                lenses = [item for item in db.load_all() if item.get("row_type") == "Lens"]

                self.assertEqual([lens["id"] for lens in lenses], ["legacy-1"])

    def test_unstamped_zero_version_migrates(self):
        """Version 0 with tables present is the legacy case under test."""
        path = self.path + ".v0"
        _make_v1_db(path, stamp_version=0)
        self.addCleanup(self._remove, path)

        DatabaseManager(path)

        self.assertEqual(_user_version(path), SCHEMA_VERSION)
        self.assertLessEqual(set(LENS_COLUMNS_ADDED_AFTER_V1), _columns(path, "lenses"))

    def test_reopening_a_migrated_database_is_a_no_op(self):
        """Migrations must be idempotent, not re-run on every launch."""
        path = self.path + ".twice"
        _make_v1_db(path, stamp_version=0)
        self.addCleanup(self._remove, path)

        DatabaseManager(path)
        columns_after_first = _columns(path, "lenses")
        DatabaseManager(path)

        self.assertEqual(_columns(path, "lenses"), columns_after_first)
        self.assertEqual(_user_version(path), SCHEMA_VERSION)

    def _remove(self, path):
        if os.path.exists(path):
            os.remove(path)


class TestFutureSchemaIsRefused(_TempDb):
    """A database from a newer OpenLens must not be opened or written."""

    def setUp(self):
        super().setUp()
        _make_v1_db(self.path, stamp_version=99)

    def test_opening_raises(self):
        with self.assertRaises(UnsupportedSchemaVersionError):
            DatabaseManager(self.path)

    def test_error_names_both_versions(self):
        """The message has to be actionable: what it found and what it wants."""
        with self.assertRaises(UnsupportedSchemaVersionError) as caught:
            DatabaseManager(self.path)

        message = str(caught.exception)
        self.assertIn("99", message)
        self.assertIn(str(SCHEMA_VERSION), message)

    def test_the_database_is_left_untouched(self):
        """Refusing must not downgrade or half-migrate the newer file."""
        with self.assertRaises(UnsupportedSchemaVersionError):
            DatabaseManager(self.path)

        self.assertEqual(_user_version(self.path), 99)
        self.assertNotIn("coating_1", _columns(self.path, "lenses"))


if __name__ == "__main__":
    unittest.main()
