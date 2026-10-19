"""Atomic file writes.

Writing with ``open(path, "w")`` truncates the target immediately, so any
failure after that point (a serialiser raising partway, a T-05 style
geometry check, an interrupt) leaves the user with a truncated file *and*
the previous good one already gone.

These helpers write to a temporary file in the same directory and then
``os.replace`` it over the target, which is atomic on POSIX and Windows as
long as both paths are on the same filesystem - hence the same directory.
The temporary file is removed on any failure, so the original is never
modified unless the write fully succeeded.
"""

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, TextIO


def _temp_path(path: Path) -> Path:
    # Same directory, so os.replace stays within one filesystem. The suffix
    # keeps partial files recognisable if the process dies outright.
    return path.with_name(path.name + ".tmp")


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
    # save()'s documented failure behaviour on a bad path.
    tmp = _temp_path(target)
    try:
        with open(tmp, "w", encoding=encoding) as handle:
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
    try:
        with open(tmp, "wb") as handle:
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
