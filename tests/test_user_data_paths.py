"""Regression: user data must not depend on the working directory.

The database was opened as the bare relative name ``"openlens.db"``, which SQLite
resolves against the current working directory. Launching the app from a desktop
launcher, an IDE, or ``python /path/to/openlens/__main__.py`` therefore created a brand new
empty database in whatever folder happened to be current - which looks exactly like
data loss, because the real database is still sitting somewhere else with everything
in it.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from openlens import paths
from openlens.paths import (
    DB_PATH_ENV_VAR,
    default_db_path,
    migrate_legacy_db,
    resolve_db_path,
    user_data_dir,
)


class _Env(unittest.TestCase):
    """Run each test with a known data dir, restoring the real one afterwards.

    Must subclass TestCase, or unittest silently ignores every class built on
    it - the suite reports a small number of tests and looks fine.
    """

    def setUp(self):
        self._real = {
            k: os.environ.get(k)
            for k in (paths.DB_PATH_ENV_VAR, paths.DATA_DIR_ENV_VAR, "XDG_DATA_HOME")
        }
        for k in self._real:
            os.environ.pop(k, None)
        self.addCleanup(self._restore)

    def _restore(self):
        for k, v in self._real.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


class TestTheDefaultIsNotRelative(_Env):
    """The whole point: two working directories must not mean two databases."""

    def test_the_default_path_is_absolute(self):
        self.assertTrue(
            default_db_path().is_absolute(),
            "a relative database path is resolved against the working directory, "
            "so launching from elsewhere opens a different database",
        )

    def test_the_default_lives_under_a_per_user_directory(self):
        self.assertNotEqual(
            default_db_path().parent,
            Path("."),
            msg="the database still lands in whatever folder we happen to be in",
        )

    def test_the_working_directory_does_not_change_the_path(self):
        first = default_db_path()

        elsewhere = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(elsewhere, ignore_errors=True))
        with mock.patch.object(paths.os, "getcwd", return_value=elsewhere):
            second = default_db_path()

        self.assertEqual(first, second, "the resolved path moved when the working directory did")

    def test_the_path_is_below_the_data_directory(self):
        self.assertEqual(
            default_db_path().parent,
            user_data_dir(),
            "the database and the data directory disagree",
        )


class TestTheResolutionFollowsThePlatform(_Env):
    def test_xdg_data_home_is_honoured_on_linux(self):
        if sys.platform == "win32" or sys.platform == "darwin":
            self.skipTest("Linux convention")

        os.environ["XDG_DATA_HOME"] = "/tmp/xdg-example"

        self.assertEqual(user_data_dir(), Path("/tmp/xdg-example") / paths.APP_DIR_NAME)

    def test_linux_falls_back_to_local_share(self):
        if sys.platform == "win32" or sys.platform == "darwin":
            self.skipTest("Linux convention")
        os.environ.pop("XDG_DATA_HOME", None)

        self.assertEqual(
            user_data_dir(),
            Path.home() / ".local" / "share" / paths.APP_DIR_NAME,
        )

    def test_macos_uses_application_support(self):
        if sys.platform != "darwin":
            self.skipTest("macOS convention")

        self.assertEqual(
            user_data_dir(),
            Path.home() / "Library" / "Application Support" / paths.APP_DIR_NAME,
        )

    def test_windows_uses_appdata(self):
        if sys.platform != "win32":
            self.skipTest("Windows convention")
        os.environ["APPDATA"] = "C:\\Users\\x\\AppData\\Roaming"

        self.assertEqual(
            user_data_dir(),
            Path("C:\\Users\\x\\AppData\\Roaming") / paths.APP_DIR_NAME,
        )

    def test_the_data_dir_env_var_wins(self):
        os.environ[paths.DATA_DIR_ENV_VAR] = "/tmp/override-data"

        self.assertEqual(user_data_dir(), Path("/tmp/override-data"))

    def test_the_data_dir_is_not_created_by_asking_for_it(self):
        """A path getter with a filesystem side effect surprises everyone."""
        target = Path(tempfile.mkdtemp()) / "not-yet"
        os.environ[paths.DATA_DIR_ENV_VAR] = str(target)

        user_data_dir()

        self.assertFalse(target.exists(), "asking for the path created it")


class TestTheEnvVarOverride(_Env):
    def test_the_db_env_var_wins(self):
        os.environ[DB_PATH_ENV_VAR] = "/tmp/scratch.db"

        self.assertEqual(default_db_path(), Path("/tmp/scratch.db"))

    def test_an_explicit_argument_wins_over_the_env_var(self):
        os.environ[DB_PATH_ENV_VAR] = "/tmp/scratch.db"

        self.assertEqual(resolve_db_path("/tmp/explicit.db"), "/tmp/explicit.db")

    def test_none_falls_through_to_the_default(self):
        os.environ[DB_PATH_ENV_VAR] = "/tmp/scratch.db"

        self.assertEqual(resolve_db_path(None), "/tmp/scratch.db")

    def test_an_empty_string_is_treated_as_unset(self):
        os.environ[DB_PATH_ENV_VAR] = ""

        self.assertEqual(
            resolve_db_path(None),
            str(default_db_path()),
            msg="an empty env var produced an empty database path",
        )

    def test_a_tilde_is_expanded(self):
        os.environ[DB_PATH_ENV_VAR] = "~/scratch.db"

        self.assertFalse(
            str(default_db_path()).startswith("~"),
            "a literal '~' in a database path opens a file called '~'",
        )


class TestResolutionHappensAtCallTimeNotImportTime(_Env):
    """A default argument is evaluated once, when the module loads."""

    def test_the_env_var_is_read_on_every_call(self):
        first = default_db_path()

        os.environ[DB_PATH_ENV_VAR] = "/tmp/later.db"
        second = default_db_path()

        self.assertNotEqual(first, second, "the path was frozen at import time")

    def test_no_default_argument_freezes_the_path(self):
        import inspect

        from openlens.database import DatabaseManager
        from openlens.gui.storage import LensStorage

        for target, param in (
            (DatabaseManager.__init__, "db_path"),
            (LensStorage.__init__, "storage_file"),
        ):
            with self.subTest(target=target.__qualname__):
                default = inspect.signature(target).parameters[param].default
                self.assertIsNone(
                    default,
                    "a filename as a default argument is resolved at import, "
                    "before any test or launcher can set the environment",
                )


class TestMigration(_Env):
    def setUp(self):
        super().setUp()
        self.cwd = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(self.cwd, ignore_errors=True))
        self.target_dir = Path(tempfile.mkdtemp()) / "data"
        self.addCleanup(
            lambda: __import__("shutil").rmtree(self.target_dir.parent, ignore_errors=True)
        )
        os.environ[paths.DATA_DIR_ENV_VAR] = str(self.target_dir)
        self.legacy = Path(self.cwd) / "openlens.db"

    def _in_cwd(self):
        """Actually chdir.

        ``Path("openlens.db")`` resolves against the *process* working
        directory and never asks ``os.getcwd()``, so patching that function
        changes nothing and the test silently passes or fails for the wrong
        reason.
        """
        previous = os.getcwd()
        os.chdir(self.cwd)
        self.addCleanup(lambda: os.chdir(previous))

    def test_a_database_in_the_working_directory_is_moved(self):
        self._in_cwd()
        self.legacy.write_text("the user's lenses")

        result = migrate_legacy_db()

        self.assertEqual(result, self.target_dir / "openlens.db")
        self.assertFalse(self.legacy.exists(), "the old file was left behind")
        self.assertEqual(
            (self.target_dir / "openlens.db").read_text(),
            "the user's lenses",
            msg="the migration did not carry the data with it",
        )

    def test_nothing_to_migrate_is_not_an_error(self):
        self._in_cwd()
        self.assertIsNone(migrate_legacy_db())

    def test_an_existing_destination_is_never_overwritten(self):
        self._in_cwd()
        """The one outcome here that could destroy someone's library."""
        self.legacy.write_text("old library")
        self.target_dir.mkdir(parents=True)
        (self.target_dir / "openlens.db").write_text("current library")

        result = migrate_legacy_db()

        self.assertIsNone(result)
        self.assertEqual(
            (self.target_dir / "openlens.db").read_text(),
            "current library",
            msg="the migration overwrote the live database",
        )
        self.assertTrue(self.legacy.exists(), "the old file was destroyed anyway")

    def test_the_env_var_suppresses_migration(self):
        self._in_cwd()
        """The user has said where the database is; do not argue."""
        os.environ[DB_PATH_ENV_VAR] = "/tmp/explicit.db"
        self.legacy.write_text("data")

        self.assertIsNone(migrate_legacy_db())
        self.assertTrue(self.legacy.exists())

    def test_the_new_directory_is_created(self):
        self._in_cwd()
        self.legacy.write_text("data")

        migrate_legacy_db()

        self.assertTrue(self.target_dir.is_dir())

    def test_a_directory_in_the_way_is_reported_not_raised(self):
        self._in_cwd()
        """A permissions problem must not stop the app from starting."""
        self.legacy.write_text("data")
        os.environ[paths.DATA_DIR_ENV_VAR] = "/proc/definitely/not/writable"

        self.assertIsNone(migrate_legacy_db())
        self.assertTrue(self.legacy.exists())


class TestTheCallersUseIt(unittest.TestCase):
    """The resolution only helps if the callers ask for it."""

    def _sources(self):
        from openlens.database import DatabaseManager
        from openlens.gui.storage import LensStorage
        from openlens.lens_editor import LensManager
        import openlens.__main__

        import inspect

        return {
            "DatabaseManager": inspect.getsource(DatabaseManager.__init__),
            "LensStorage": inspect.getsource(LensStorage.__init__),
            "LensManager": inspect.getsource(LensManager.__init__),
            "openlens.db literal in the GUI entry module": openlens.__main__.__file__,
        }

    def test_no_bare_openlens_db_literal_remains(self):
        import subprocess

        result = subprocess.run(
            ["grep", "-rn", '"openlens.db"', "openlens/"],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        )
        remaining = [
            line
            for line in result.stdout.splitlines()
            if "DEFAULT_DB_FILE" not in line
            and "startup.py:41" not in line
            and not line.startswith("openlens/paths.py:")
        ]
        self.assertEqual(
            remaining,
            [],
            msg="a bare relative path is still hard-coded:\n" + "\n".join(remaining),
        )

    def test_the_seeding_check_compares_resolved_paths(self):
        """basename comparison seeds any temp file called openlens.db."""
        import inspect

        from openlens.lens_editor import LensManager

        source = inspect.getsource(LensManager.__init__)

        self.assertNotIn(
            'os.path.basename(self.storage_file) == "openlens.db"',
            source,
            "any scratch file named openlens.db is treated as the app database",
        )
        self.assertIn("default_db_path()", source)


class TestEndToEndAcrossWorkingDirectories(unittest.TestCase):
    def test_the_same_library_from_two_directories(self):
        """The failure this fixes, stated as a test: two cwds, one library."""
        data_dir = Path(tempfile.mkdtemp()) / "data"
        self.addCleanup(lambda: __import__("shutil").rmtree(data_dir.parent, ignore_errors=True))
        os.environ[paths.DATA_DIR_ENV_VAR] = str(data_dir)
        self.addCleanup(lambda: os.environ.pop(paths.DATA_DIR_ENV_VAR, None))

        from openlens.database import DatabaseManager

        here = tempfile.mkdtemp()
        there = tempfile.mkdtemp()
        for d in (here, there):
            self.addCleanup(lambda d=d: __import__("shutil").rmtree(d, ignore_errors=True))

        first = DatabaseManager()
        with mock.patch.object(paths.os, "getcwd", return_value=here):
            from_here = DatabaseManager().db_path
        with mock.patch.object(paths.os, "getcwd", return_value=there):
            from_there = DatabaseManager().db_path

        self.assertEqual(
            from_here,
            from_there,
            "the same application found two different databases",
        )
        self.assertEqual(from_here, first.db_path)


class TestTheAppRunsTheMigration(unittest.TestCase):
    """Testing migrate_legacy_db does not prove anything calls it.

    With the call removed from main(), every other test here still passed and
    a user upgrading would silently keep an orphaned database.
    """

    def test_main_migrates_before_opening_anything(self):
        import inspect

        import openlens.__main__ as openlens

        source = inspect.getsource(openlens.main)

        self.assertIn(
            "migrate_legacy_db",
            source,
            "main() never runs the migration, so an existing database is left "
            "behind in the working directory",
        )

    def test_the_migration_runs_before_the_window_is_built(self):
        """Order matters: moving the file after it is opened does nothing."""
        import inspect

        import openlens.__main__ as openlens

        source = inspect.getsource(openlens.main)

        self.assertLess(
            source.index("migrate_legacy_db"),
            source.index("OpenLensWindow("),
            "the migration runs after the window is built, so the database has "
            "already been opened from the old location",
        )

    def test_a_failing_migration_does_not_stop_the_app_starting(self):
        import inspect

        import openlens.__main__ as openlens

        source = inspect.getsource(openlens.main)
        body = source[source.index("migrate_legacy_db") :]

        self.assertIn(
            "except",
            body[: body.index("app = QApplication")],
            "an unwritable data directory would stop the application starting",
        )


if __name__ == "__main__":
    unittest.main()
