"""Atomic file writes.

Writing with ``open(path, "w")`` truncates the target immediately, so any
failure after that point (a serialiser raising partway, a T-05 style
geometry check, an interrupt) leaves the user with a truncated file *and*
the previous good one already gone.

These helpers write to a temporary file in the same directory and then
``os.replace`` it over the target, which is atomic on POSIX and Windows as
long as both paths are on the same filesystem - hence the same directory.
The temporary name is unique per call, so concurrent writers of one target do
not share (and destroy) each other's temporary file. The temporary file is
removed on any failure, so the original is never modified unless the write
fully succeeded.
"""

import os
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, TextIO


def _temp_path(path: Path) -> Path:
    # Unique per write. Deriving the name from the target alone made every
    # concurrent writer - two threads, two processes, a worker and the GUI -
    # use the same inode; the first os.replace() moved it away and the others
    # failed with FileNotFoundError after writing their payload. The prefix
    # keeps abandoned files recognisable and the directory is unchanged so
    # os.replace stays within one filesystem.
    return path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")


def _discard(path: Path) -> None:
    try:
        os.unlink(path)
    except OSError:
        pass


@contextmanager
def atomic_write_text(path: Any, encoding: str = "utf-8") -> Iterator[TextIO]:
    """Yield a text handle whose contents replace ``path`` only on success.

    Args:
        path: Destination file path.
        encoding: Text encoding for the temporary file.

    Yields:
        An open write-mode text handle.

    Raises:
        Whatever the caller raised; the destination is left untouched.
    """
    target = Path(path)
    # Deliberately no mkdir: creating missing parent directories would change
    # save()'s documented failure behaviour on a bad path. "x" keeps the
    # unique name exclusive; a collision must not truncate another writer.
    tmp = _temp_path(target)
    handle = open(tmp, "x", encoding=encoding)
    try:
        with handle:
            yield handle
        os.replace(tmp, target)
    except BaseException:
        _discard(tmp)
        raise


@contextmanager
def atomic_write_bytes(path: Any) -> Iterator[Any]:
    """Binary counterpart of :func:`atomic_write_text`."""
    target = Path(path)
    tmp = _temp_path(target)
    handle = open(tmp, "xb")
    try:
        with handle:
            yield handle
        os.replace(tmp, target)
    except BaseException:
        _discard(tmp)
        raise


def atomic_write_json(path: Any, payload: Any, indent: int = 2) -> None:
    """Serialise ``payload`` as JSON, replacing ``path`` only on success."""
    import json

    with atomic_write_text(path) as handle:
        json.dump(payload, handle, indent=indent)
