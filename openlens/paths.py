"""Where OpenLens keeps the user's data.

The database used to be opened as the bare relative name ``"openlens.db"``, which
SQLite resolves against the **current working directory**. Launching the app from
a desktop launcher, an IDE, or ``python /path/to/openlens.py`` therefore created
a brand new empty database in whatever folder happened to be current - which
looks exactly like data loss, because the real database is still sitting
somewhere else with everything in it.

User data belongs in a per-user directory. The path is resolved in one place
here, at call time, so an environment variable set after import still takes
effect.
"""

import logging
import os
import shutil
import sys
from pathlib import Path
from typing import Optional

from .constants import DEFAULT_DB_FILE, DEFAULT_MATERIALS_FILE, DEFAULT_MOUNTS_FILE

logger = logging.getLogger(__name__)

#: Overrides the resolved database path. Set it to point several installs at one
#: shared database, to use a scratch file in tests, or to relocate an existing
#: data set without moving anything.
DB_PATH_ENV_VAR = "OPENLENS_DB_PATH"

#: Overrides the user data directory itself, for the same reasons.
DATA_DIR_ENV_VAR = "OPENLENS_DATA_DIR"

#: Overrides the material catalog path. The catalog is user-editable and the
#: application writes to it, so it must never default to the installed package.
MATERIALS_PATH_ENV_VAR = "OPENLENS_MATERIALS_PATH"

#: Overrides the custom-mount configuration path.
MOUNTS_PATH_ENV_VAR = "OPENLENS_MOUNTS_PATH"

#: The directory name used under the platform's per-user data root.
APP_DIR_NAME = "openlens"


def user_data_dir() -> Path:
    """The per-user directory OpenLens stores data in.

    Follows each platform's convention without adding a dependency for it:
    ``$XDG_DATA_HOME/openlens`` (or ``~/.local/share/openlens``) on Linux,
    ``~/Library/Application Support/openlens`` on macOS, and
    ``%APPDATA%\\openlens`` on Windows. ``platformdirs`` would say the same
    thing, but it is not a declared dependency and the rule is short enough to
    state outright.

    The directory is *not* created here - a path getter with a filesystem
    side effect is a surprise waiting to happen in tests and read-only installs.

    Returns:
        The directory, which may not exist yet.
    """
    override = os.environ.get(DATA_DIR_ENV_VAR)
    if override:
        return Path(override).expanduser()

    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.environ.get("LOCALAPPDATA")
        root = Path(base).expanduser() if base else Path.home() / "AppData" / "Roaming"
    elif sys.platform == "darwin":
        root = Path.home() / "Library" / "Application Support"
    else:
        xdg = os.environ.get("XDG_DATA_HOME")
        root = Path(xdg).expanduser() if xdg else Path.home() / ".local" / "share"

    return root / APP_DIR_NAME


def default_db_path() -> Path:
    """The database file OpenLens uses when nothing else is specified.

    Returns:
        The path from ``$OPENLENS_DB_PATH`` if it is set, otherwise
        ``<user data dir>/openlens.db``.
    """
    override = os.environ.get(DB_PATH_ENV_VAR)
    if override:
        return Path(override).expanduser()
    return user_data_dir() / DEFAULT_DB_FILE


def default_materials_path() -> Path:
    """The writable material catalog OpenLens uses by default.

    Returns:
        The path from ``$OPENLENS_MATERIALS_PATH`` if set, otherwise
        ``<user data dir>/materials.json``.

    The catalog is user data: ``add_material`` writes the whole file. The old
    default was ``<package>/../data/materials.json``, which on an installed copy
    resolved inside site-packages - not shipped, and not writable without root.
    It also made ``MaterialDatabase()`` in tests write to the developer's real
    catalog, silently mixing test glasses into it.
    """
    override = os.environ.get(MATERIALS_PATH_ENV_VAR)
    if override:
        return Path(override).expanduser()
    return user_data_dir() / DEFAULT_MATERIALS_FILE


def default_mounts_path() -> Path:
    """The JSON file holding user-defined lens mounts.

    Returns:
        The path from ``$OPENLENS_MOUNTS_PATH`` if set, otherwise
        ``<user data dir>/mounts.json``.

    The file is user data and the mount manager writes it. It therefore lives
    under the per-user data directory, never beside the installed package.
    """
    override = os.environ.get(MOUNTS_PATH_ENV_VAR)
    if override:
        return Path(override).expanduser()
    return user_data_dir() / DEFAULT_MOUNTS_FILE


def legacy_materials_path() -> Path:
    """Where the catalog lived before it moved to the user data directory.

    Only a migration *source*. It deliberately does not serve as a fallback
    data source: on an installed copy it resolves under site-packages and is
    absent, and reading from it silently is what made the old default write
    into the package in the first place.

    Returns:
        ``<repository root>/data/materials.json`` for a source checkout.
    """
    return Path(__file__).resolve().parent.parent / "data" / DEFAULT_MATERIALS_FILE


def resolve_db_path(storage_file: Optional[str] = None) -> str:
    """The path to actually open, given an optional explicit one.

    Callers pass ``None`` by default rather than a literal filename. A default
    argument is evaluated once, at import, so it would freeze the resolved path
    before a test or a launcher had a chance to set the environment.

    Args:
        storage_file: An explicitly requested path, or None for the default.

    Returns:
        The path as a string.
    """
    if storage_file:
        return str(storage_file)
    return str(default_db_path())


def ensure_parent_dir(db_path: str) -> None:
    """Create the directory holding *db_path*, if it is missing.

    Args:
        db_path: The database file path.

    Returns:
        None
    """
    parent = Path(db_path).expanduser().parent
    if str(parent) and not parent.exists():
        try:
            parent.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.warning("Could not create data directory %s: %s", parent, e)


def migrate_legacy_db(legacy: Optional[str] = None) -> Optional[Path]:
    """Move a database left in the working directory to the user data dir.

    Only when the destination does not exist. If both are present the user's data
    wins and the old file is left completely alone - overwriting it is the one
    outcome here that could destroy someone's library.

    Args:
        legacy: The old database path, or None for ``./openlens.db``.

    Returns:
        The new location if a migration happened, else None.
    """
    if os.environ.get(DB_PATH_ENV_VAR):
        # The user has said exactly where the database is. Relocating it would
        # be arguing with them.
        return None

    old = Path(legacy or DEFAULT_DB_FILE).expanduser()
    if not old.is_file():
        return None

    target = default_db_path()
    if target.exists():
        logger.info(
            "Found a database at %s but the app's database is already at %s; "
            "leaving %s untouched",
            old,
            target,
            old,
        )
        return None

    ensure_parent_dir(str(target))
    try:
        shutil.move(str(old), str(target))
    except OSError as e:
        logger.warning("Could not move %s to %s: %s", old, target, e)
        return None

    logger.info("Moved the database from %s to %s", old, target)
    return target


def migrate_legacy_materials(
    legacy: Optional[str] = None, destination: Optional[str] = None
) -> Optional[Path]:
    """Copy a catalog left in the repository's ``data/`` directory.

    The old default path was ``<package>/../data/materials.json``. Existing
    users have a catalog there and would otherwise appear to lose every custom
    glass the moment the default moved to the user data directory.

    A **copy**, not a move: the file belongs to a checkout that may be shared,
    under version control, or read-only, and deleting it is not this function's
    business. It never overwrites an existing destination - the user's current
    catalog wins - and a missing legacy file is a no-op, which is the normal
    case for an installed copy.

    Args:
        legacy: The old catalog path, or None for the repository's ``data/``.
        destination: The target path, or None for the default user path.

    Returns:
        The new catalog path if a copy happened, else None.
    """
    if destination is None and os.environ.get(MATERIALS_PATH_ENV_VAR):
        # The user has said exactly where the catalog is. Copying a different
        # file over it - or beside it - would be arguing with them.
        return None

    old = Path(legacy).expanduser() if legacy else legacy_materials_path()
    if not old.is_file():
        return None

    target = Path(destination).expanduser() if destination else default_materials_path()
    if target.exists():
        logger.info(
            "Found a catalog at %s but the user catalog is already at %s; "
            "leaving the destination untouched",
            old,
            target,
        )
        return None

    ensure_parent_dir(str(target))
    try:
        shutil.copy2(str(old), str(target))
    except OSError as e:
        logger.warning("Could not copy the catalog from %s to %s: %s", old, target, e)
        return None

    logger.info("Copied the material catalog from %s to %s", old, target)
    return target
