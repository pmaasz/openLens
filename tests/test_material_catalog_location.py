"""Regression: the material catalog must live in writable user data.

The default was ``<package>/../data/materials.json``. Three separate problems:

- ``data/`` is a sibling of the package and gitignored, so it is not part of a
  real installation at all;
- on an installed copy ``__file__`` is inside site-packages, so the old path
  resolved to ``site-packages/data/materials.json`` - not writable without root,
  and polluting the environment if it is;
- ``MaterialDatabase()`` in tests therefore wrote to the developer's **real**
  catalogue. ``TEST_GLASS``, ``TEST_FLINT`` and friends ended up in it, and
  every ``add_material()`` rewrote the whole file.

The default is now ``<user data dir>/materials.json``. An existing catalogue at
the old repository path is copied once at startup, never moved and never over
an existing destination. The test suite points both paths at a temporary
directory (``tests/__init__.py``), so a test cannot touch real user data even
when it constructs a database with no path.
"""

import inspect
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import openlens
import openlens.__main__
from openlens import paths
from openlens.material_database import MaterialDatabase, MaterialProperties

REPO_ROOT = Path(__file__).resolve().parent.parent


def _material(name="TEST_GUARD"):
    return MaterialProperties(name=name, catalog="TEST", nd=1.5, vd=60.0)


class _IsolatedUserData(unittest.TestCase):
    """Point the per-user data directory at a temp directory for each test."""

    def setUp(self):
        self.data_dir = Path(tempfile.mkdtemp(prefix="openlens-materials-"))
        self.addCleanup(shutil.rmtree, str(self.data_dir), True)

        patcher = mock.patch.dict(os.environ, {}, clear=False)
        patcher.start()
        self.addCleanup(patcher.stop)
        # tests/__init__.py sets these for the whole run; this test is about
        # what happens without that guard.
        os.environ.pop(paths.MATERIALS_PATH_ENV_VAR, None)
        os.environ.pop(paths.DATA_DIR_ENV_VAR, None)
        os.environ["XDG_DATA_HOME"] = str(self.data_dir)
        os.environ.pop("APPDATA", None)

    @property
    def expected_path(self):
        return self.data_dir / paths.APP_DIR_NAME / "materials.json"


class TestTheDefaultPathIsUserData(_IsolatedUserData):
    def test_the_default_lives_under_the_user_data_directory(self):
        self.assertEqual(paths.default_materials_path(), self.expected_path)

    def test_the_default_matches_the_rest_of_the_apps_user_data(self):
        self.assertEqual(paths.default_materials_path().parent, paths.user_data_dir())

    def test_the_default_is_absolute(self):
        """A relative default depends on the process's working directory."""
        self.assertTrue(paths.default_materials_path().is_absolute())

    def test_the_default_is_not_inside_the_installed_package(self):
        package_dir = Path(openlens.__file__).resolve().parent

        self.assertFalse(
            package_dir in paths.default_materials_path().resolve().parents,
            "the writable catalog is inside the package - site-packages is "
            "read-only on a system install",
        )

    def test_the_default_is_not_inside_the_source_tree(self):
        self.assertFalse(
            REPO_ROOT in paths.default_materials_path().resolve().parents,
            "a default inside the checkout makes the path depend on the repo "
            "layout rather than on where user data belongs",
        )

    def test_the_override_wins(self):
        override = self.data_dir / "elsewhere" / "custom.json"
        os.environ[paths.MATERIALS_PATH_ENV_VAR] = str(override)

        self.assertEqual(paths.default_materials_path(), override)

    def test_the_legacy_path_is_the_repository_data_directory(self):
        self.assertEqual(paths.legacy_materials_path(), REPO_ROOT / "data" / "materials.json")


class TestAFreshInstallHasAUsableCatalog(_IsolatedUserData):
    def test_built_in_materials_load_with_no_file_on_disk(self):
        self.assertFalse(self.expected_path.exists())

        db = MaterialDatabase()

        self.assertGreater(len(db.materials), 0)
        self.assertIn("BK7", db.materials)

    def test_reading_does_not_create_a_catalog_file(self):
        MaterialDatabase()

        self.assertFalse(
            self.expected_path.exists(),
            "reading the catalog must not write to the user data directory",
        )

    def test_adding_a_material_writes_under_the_user_data_dir(self):
        db = MaterialDatabase()

        db.add_material(_material("USER_GLASS"))

        self.assertEqual(Path(db.db_path), self.expected_path)
        self.assertTrue(self.expected_path.is_file())

    def test_the_written_material_is_read_back(self):
        db = MaterialDatabase()
        db.add_material(_material("USER_GLASS"))

        reopened = MaterialDatabase()

        self.assertIn("USER_GLASS", reopened.materials)

    def test_saving_creates_a_missing_parent_directory(self):
        nested = self.data_dir / "a" / "b" / "materials.json"
        db = MaterialDatabase(db_path=str(nested))

        db.add_material(_material())

        self.assertTrue(nested.is_file())


class TestTheRepositoryCatalogIsNotTouched(_IsolatedUserData):
    """#490: ``db_path=None`` used to mean "the developer's real catalog"."""

    def test_a_default_database_does_not_write_the_repository_catalog(self):
        repo_catalog = paths.legacy_materials_path()
        before = repo_catalog.read_bytes() if repo_catalog.exists() else None

        db = MaterialDatabase()
        db.add_material(_material("TEST_GUARD"))

        after = repo_catalog.read_bytes() if repo_catalog.exists() else None
        self.assertEqual(
            after,
            before,
            "constructing MaterialDatabase() and adding a material modified the "
            "catalog in the checkout",
        )

    def test_a_default_database_writes_somewhere_else(self):
        db = MaterialDatabase()

        self.assertNotEqual(Path(db.db_path).resolve(), paths.legacy_materials_path().resolve())
        self.assertFalse(
            paths.legacy_materials_path().resolve() in Path(db.db_path).resolve().parents
        )


class TestLegacyCatalogMigration(_IsolatedUserData):
    def setUp(self):
        super().setUp()
        self.legacy = self.data_dir / "legacy" / "materials.json"
        self.legacy.parent.mkdir(parents=True)
        self.legacy.write_text('{"LEGACY": {"name": "LEGACY"}}', encoding="utf-8")
        self.destination = self.data_dir / "user" / "materials.json"

    def test_the_catalog_is_copied(self):
        result = paths.migrate_legacy_materials(
            legacy=str(self.legacy), destination=str(self.destination)
        )

        self.assertEqual(result, self.destination)
        self.assertEqual(
            self.destination.read_text(encoding="utf-8"),
            self.legacy.read_text(encoding="utf-8"),
        )

    def test_the_legacy_file_is_left_in_place(self):
        """A checkout may be shared, version-controlled or read-only."""
        paths.migrate_legacy_materials(legacy=str(self.legacy), destination=str(self.destination))

        self.assertTrue(self.legacy.is_file())

    def test_an_existing_catalog_is_never_overwritten(self):
        self.destination.parent.mkdir(parents=True)
        self.destination.write_text('{"CURRENT": {}}', encoding="utf-8")

        result = paths.migrate_legacy_materials(
            legacy=str(self.legacy), destination=str(self.destination)
        )

        self.assertIsNone(result)
        self.assertEqual(self.destination.read_text(encoding="utf-8"), '{"CURRENT": {}}')

    def test_a_missing_legacy_file_is_a_noop(self):
        result = paths.migrate_legacy_materials(
            legacy=str(self.data_dir / "absent.json"),
            destination=str(self.destination),
        )

        self.assertIsNone(result)
        self.assertFalse(self.destination.exists())

    def test_the_destination_directory_is_created(self):
        self.assertFalse(self.destination.parent.exists())

        paths.migrate_legacy_materials(legacy=str(self.legacy), destination=str(self.destination))

        self.assertTrue(self.destination.parent.is_dir())

    def test_the_default_destination_is_the_user_catalog(self):
        result = paths.migrate_legacy_materials(legacy=str(self.legacy))

        self.assertEqual(result, self.expected_path)
        self.assertTrue(self.expected_path.is_file())

    def test_an_explicit_catalog_path_opts_out_of_migration(self):
        """The user said where the catalog is; do not copy a different file."""
        os.environ[paths.MATERIALS_PATH_ENV_VAR] = str(self.destination)

        result = paths.migrate_legacy_materials(legacy=str(self.legacy))

        self.assertIsNone(result)
        self.assertFalse(self.destination.exists())

    def test_the_migrated_catalog_is_loaded(self):
        legacy_db = MaterialDatabase(db_path=str(self.legacy))
        legacy_db.add_material(_material("KEPT_GLASS"))

        paths.migrate_legacy_materials(legacy=str(self.legacy))

        self.assertIn("KEPT_GLASS", MaterialDatabase().materials)


class TestTheGuiRunsTheMigration(unittest.TestCase):
    def test_main_migrates_the_catalog_before_the_window(self):
        """Test the call site, not just the helper - the recurring trap."""
        source = inspect.getsource(openlens.__main__.main)

        self.assertIn("migrate_legacy_materials", source)
        self.assertLess(
            source.index("migrate_legacy_materials"),
            source.index("OpenLensWindow("),
            "the catalog is migrated after the window is built, which is "
            "after the first MaterialDatabase may already have been created",
        )

    def test_a_migration_failure_does_not_stop_the_app(self):
        source = inspect.getsource(openlens.__main__.main)
        body = source[source.index("migrate_legacy_materials") :]

        self.assertIn(
            "except",
            body[: body.index("app = QApplication")],
            "an unwritable data directory would stop the application starting",
        )


class TestTheTestRunIsIsolated(unittest.TestCase):
    def test_the_suite_does_not_use_the_repository_catalog(self):
        """tests/__init__.py points the catalog at a temp directory."""
        configured = os.environ.get(paths.MATERIALS_PATH_ENV_VAR)

        self.assertIsNotNone(configured, "no test-wide catalog override is set")
        self.assertFalse(
            REPO_ROOT in Path(configured).resolve().parents,
            f"the test run is pointed at {configured}, which is inside the "
            "checkout - a writing test would modify the developer's catalog",
        )


if __name__ == "__main__":
    unittest.main()
