"""Window-independent library persistence orchestration.

The window keeps selection, editor synchronization, tolerance state, load
adoption, delete re-pointing and the user-facing error paths. This module only
sequences the storage calls, partitions the loaded library and classifies
failures. It must not import Qt so the sequencing can be tested headlessly.
"""

from dataclasses import dataclass
from typing import Any, Callable, Iterable, List, Optional

from openlens.database import LensInUseError
from openlens.lens import Lens


@dataclass(frozen=True)
class LibraryLoad:
    """Result of loading the stored library.

    Attributes:
        lenses: Standalone lenses. Empty on failure.
        assemblies: Optical assemblies. Empty on failure.
        error: Exception text on failure, otherwise ``None``.
        cause: The original exception on failure, for callers that need to
            classify it (the window only needs the message).
    """

    lenses: List[Any]
    assemblies: List[Any]
    error: Optional[str] = None
    cause: Optional[BaseException] = None

    @property
    def ok(self) -> bool:
        """Whether the load succeeded."""
        return self.error is None


@dataclass(frozen=True)
class LibrarySave:
    """Result of saving the library snapshot.

    Attributes:
        ok: Whether the storage accepted the snapshot.
        count: Number of unique items that were handed to the storage.
        error: Failure text, including ``LensStorage.last_error``.
        cause: The original exception when the storage raised.
    """

    ok: bool
    count: int = 0
    error: Optional[str] = None
    cause: Optional[BaseException] = None


@dataclass(frozen=True)
class LibraryDelete:
    """Result of deleting one library item.

    Attributes:
        ok: Whether the storage deleted the item.
        blocked: True when the item is still referenced by an assembly.
        error: Failure text.
        cause: The original exception, including ``LensInUseError``.
    """

    ok: bool
    blocked: bool = False
    error: Optional[str] = None
    cause: Optional[BaseException] = None


class LibraryService:
    """Sequence library persistence without a window or Qt event loop."""

    def __init__(self, storage_provider: Callable[[], Any]) -> None:
        """Create the service.

        Args:
            storage_provider: Returns the current ``LensStorage``. Deliberately
                late-bound: tests replace ``window._storage`` after the window
                is constructed, so the service must resolve it per call.
        """
        self._storage_provider = storage_provider

    def load(self) -> LibraryLoad:
        """Load and partition the stored library.

        Returns:
            The loaded lenses/assemblies, or a failure result. A storage that
            swallows its own errors and returns an empty list is indistinguishable
            from an empty library here; that is a storage-layer limitation, not
            something this service hides.
        """
        try:
            items = list(self._storage_provider().load_lenses())
        except Exception as exc:
            return LibraryLoad([], [], error=str(exc), cause=exc)

        lenses = [item for item in items if not self._is_assembly(item)]
        assemblies = [item for item in items if self._is_assembly(item)]
        return LibraryLoad(lenses, assemblies)

    def save(self, items: Iterable[Any], *, reconcile: bool = True) -> LibrarySave:
        """Save a library snapshot, de-duplicated by id.

        Args:
            items: Every stored lens and assembly.
            reconcile: Remove rows missing from the snapshot. Explicit saves
                and reloads pass True; the per-edit autosave passes False
                because reconciliation is too expensive for that path.

        Returns:
            The save result. Storage rejections honour ``last_error`` so the
            window can explain the failure.
        """
        try:
            unique: dict[Any, Any] = {}
            for item in items:
                if hasattr(item, "id"):
                    unique[item.id] = item

            storage = self._storage_provider()
            if not storage.save_lenses(
                list(unique.values()), reconcile=reconcile, library_snapshot=True
            ):
                return LibrarySave(
                    False,
                    error=getattr(storage, "last_error", None) or "the database rejected the save",
                )

            return LibrarySave(True, count=len(unique))
        except Exception as exc:
            return LibrarySave(False, error=str(exc), cause=exc)

    def delete(self, item_id: str) -> LibraryDelete:
        """Delete one item from storage.

        The window deletes from the database first and only mutates memory and
        the editors after a successful result, so no re-pointing belongs here.

        Args:
            item_id: Id of the lens or assembly to delete.

        Returns:
            The delete result; ``blocked=True`` when an assembly still uses
            the lens.
        """
        try:
            self._storage_provider().delete_item(item_id)
            return LibraryDelete(True)
        except LensInUseError as exc:
            return LibraryDelete(False, blocked=True, error=str(exc), cause=exc)
        except Exception as exc:
            return LibraryDelete(False, error=str(exc), cause=exc)

    @staticmethod
    def duplicate_lens(lens: Lens, *, suffix: str = " (copy)") -> Lens:
        """Return a copy of *lens* with a fresh id and a ``(copy)`` name.

        Args:
            lens: Lens to clone.
            suffix: Appended to the name.

        Returns:
            A new lens with the same optical properties and metadata.
        """
        data = lens.to_dict()
        # Pop identity so the constructor mints a fresh uuid4 id; keeping it
        # would collide with the original on INSERT OR REPLACE.
        data.pop("id", None)
        data["name"] = f"{lens.name}{suffix}"
        return Lens.from_dict(data)

    @staticmethod
    def _is_assembly(item: Any) -> bool:
        """Return whether *item* is an OpticalSystem rather than a Lens."""
        return hasattr(item, "elements") and hasattr(item, "air_gaps")
