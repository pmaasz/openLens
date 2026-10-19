"""
OpenLens GUI Storage Module

Provides lens data persistence functionality for the GUI.
"""

import logging
from typing import List, Optional, Callable, Any

# Configure module logger
logger = logging.getLogger(__name__)

from ..lens import Lens
from ..optical_system import OpticalSystem
from ..database import DatabaseManager, LensInUseError
from ..paths import resolve_db_path


class LensStorage:
    """Handles lens data persistence to SQLite database.

    This class provides methods to load and save lens data using DatabaseManager.

    Args:
        storage_file: Path to the database file. None uses the per-user
            database; see ``openlens.paths``.
        status_callback: Optional callback function to report status messages.
    """

    def __init__(
        self,
        storage_file: Optional[str] = None,
        status_callback: Optional[Callable[[str], None]] = None,
    ) -> None:
        """Initialize the storage handler.

        Args:
            storage_file: Path to the database file.
            status_callback: Optional callback for status messages.
        """
        # Resolved here so that every later use - including the module-level
        # helpers that construct their own LensStorage - names the same file.
        self.storage_file = resolve_db_path(storage_file)
        self.status_callback = status_callback or (lambda msg: None)
        # The message of the most recent failure, or None after a successful
        # save. save_lenses catches the exception and only returns False, so a
        # caller that has to explain the failure to a user has no other way to
        # learn what actually went wrong.
        self.last_error: Optional[str] = None

        if DatabaseManager:
            self.db = DatabaseManager(self.storage_file)
        else:
            self.db = None

    def _update_status(self, message: str) -> None:
        """Update status via callback.

        Args:
            message: Status message to report.
        """
        if self.status_callback is not None:
            self.status_callback(message)

    def load_lenses(self) -> List[Any]:
        """Load lenses and optical systems from SQLite database.

        Returns:
            List of Lens and OpticalSystem objects loaded from the database.
            Returns empty list if database is unavailable or contains invalid data.
        """
        if not self.db:
            logger.error("DatabaseManager not available")
            return []

        try:
            # Load from DB
            data = self.db.load_all()

            # 1. Load all lenses first and create a lookup
            lens_lookup = {}
            items = []

            # Pass 1: Create Lens objects
            for item_data in data:
                # row_type is the row marker; "type" is the payload's own type
                # (for a lens, the lens type: "Biconvex", ...). Dispatching on
                # "type" happened to work only because the merge overwrote the
                # marker - and it left the lens type as the only value, so a
                # filter on type == "Lens" matched nothing (#488).
                if item_data.get("row_type") != "OpticalSystem":
                    try:
                        lens = Lens.from_dict(item_data)
                        lens_lookup[lens.id] = lens
                        items.append(lens)
                    except Exception as e:
                        logger.warning("Failed to load lens: %s", e)

            # Pass 2: Create OpticalSystem objects using the lookup
            for item_data in data:
                if item_data.get("row_type") == "OpticalSystem":
                    try:
                        system = OpticalSystem.from_dict(item_data)
                        # Refresh references to ensure identity match with Pass 1 lenses
                        if hasattr(system, "refresh_references"):
                            system.refresh_references(lens_lookup)
                        items.append(system)
                    except Exception as e:
                        logger.warning("Failed to load assembly: %s", e)

            return items

        except Exception as e:
            logger.error("Failed to load lenses from database: %s", e)
            return []

    def delete_item(self, item_id: str) -> bool:
        """Delete a lens or assembly from the database by id.

        Must be called for every removal; save_lenses() only
        inserts/replaces rows and never reconciles deletions.

        Args:
            item_id: Id of the lens or assembly to remove.

        Returns:
            bool: True on success.

        Raises:
            LensInUseError: The lens is still placed in an assembly.
        """
        if not self.db:
            logger.error("DatabaseManager not available")
            return False
        self.db.delete_item(item_id)
        self._update_status(f"Deleted {item_id} from database")
        return True

    def save_lenses(
        self,
        items: List[Any],
        show_status: bool = True,
        reconcile: bool = False,
        library_snapshot: bool = False,
    ) -> bool:
        """Save lenses/optical systems to the SQLite database.

        Args:
            items: Lens/OpticalSystem objects to persist.
            show_status: Whether to report a status message on success.
            reconcile: If True, treat `items` as a COMPLETE library
                snapshot and delete database rows whose ids are absent
                from it (removal reconciliation). Only enable this when
                the caller owns every stored object - partial lists
                (e.g. the CLI lens-only view) must keep the default to
                avoid wiping assemblies.

        Returns:
            True if save was successful, False otherwise.
        """
        if not self.db:
            logger.error("DatabaseManager not available")
            self.last_error = "DatabaseManager not available"
            return False

        try:
            # Serialize and save items to DB
            for item in items:
                item_dict = item.to_dict()
                if isinstance(item, OpticalSystem) or item_dict.get("type") == "OpticalSystem":
                    self.db.save_assembly(item_dict)
                else:
                    self.db.save_lens(item_dict)

            # Record library membership. Promotion is always safe: a lens handed to us as
            # a library item is one. Demotion is not - save_lenses is free to
            # receive a *partial* list (the CLI's lens-only view passes one),
            # and reading "absent from this list" as "not a library item" would
            # silently delete every library lens whenever a single assembly was
            # saved. Only reconcile, which by contract means the caller owns
            # every stored object, is allowed to demote.
            self.db.set_library_membership(
                (
                    item.id
                    for item in items
                    if not isinstance(item, OpticalSystem)
                    and getattr(item, "type", None) != "OpticalSystem"
                ),
                demote=library_snapshot or reconcile,
            )

            if reconcile:
                self._reconcile(items)

            self.last_error = None
            if show_status:
                self._update_status(f"Saved {len(items)} item(s) to database")
            return True

        except Exception as e:
            self.last_error = str(e)
            self._update_status(f"Error: Failed to save lenses: {e}")
            logger.error("Failed to save lenses: %s", e)
            return False

    def _reconcile(self, items: List[Any]) -> None:
        """Delete rows whose ids are absent from the full snapshot."""
        keep = {item.id for item in items if hasattr(item, "id")}
        existing = self.db.all_ids()

        # Assemblies first: removing them releases lens references so the
        # lens pass cannot trip the in-use guard for stale pairs.
        removed = 0
        for asm_id in existing["assemblies"]:
            if asm_id not in keep:
                self.db.delete_item(asm_id)
                removed += 1

        for lens_id in existing["lenses"]:
            if lens_id in keep:
                continue
            if lens_id in self.db.lens_ids_used_by_assemblies():
                # An assembly kept in the snapshot still holds this lens, so the
                # delete below cannot succeed - the in-use guard would refuse it.
                # Not attempted: a doomed attempt is not a safety net, it is just
                # one refusal per assembly lens on every save.
                logger.debug("Reconciliation kept assembly lens %s", lens_id)
                continue
            try:
                self.db.delete_item(lens_id)
                removed += 1
            except Exception as e:
                # LensInUseError: an assembly kept in the snapshot still
                # references this lens; keep the row rather than fail the
                # whole save.
                logger.warning("Reconciliation kept lens %s: %s", lens_id, e)
        if removed:
            logger.info("Reconciliation removed %d stale row(s)", removed)


def delete_item(storage_file: Optional[str] = None, item_id: str = "") -> bool:
    """Delete a single lens/assembly from the database (convenience)."""
    return LensStorage(storage_file).delete_item(item_id)


def load_lenses(storage_file: Optional[str] = None) -> List[Any]:
    """Convenience function to load lenses and systems from a database.

    Args:
        storage_file: Path to the database file.

    Returns:
        List of Lens/OpticalSystem objects.
    """
    storage = LensStorage(storage_file)
    return storage.load_lenses()


def save_lenses(
    items: List[Any],
    storage_file: Optional[str] = None,
    status_callback: Optional[Callable[[str], None]] = None,
) -> bool:
    """Convenience function to save lenses and systems to a database.

    Args:
        items: List of Lens/OpticalSystem objects to save.
        storage_file: Path to the database file.
        status_callback: Optional callback for status messages.

    Returns:
        True if save was successful, False otherwise.
    """
    storage = LensStorage(storage_file, status_callback)
    return storage.save_lenses(items)
