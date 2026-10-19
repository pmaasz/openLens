"""Logging configuration for the entry points.

Library modules only call ``logger.*``; the application decides where those
records go, exactly once, here. Two sinks are installed:

* stderr, so a failure is visible while the app is running (and in CI), and
* a rotating file in the user data directory, so a user can attach last
  session's warnings to a bug report after the window is gone.

The setup is idempotent: every handler carries a marker and repeated calls
only adjust the level. ``-v``/``--verbose`` keeps DEBUG records.
"""

import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Sequence, Optional

from .paths import user_data_dir

logger = logging.getLogger(__name__)

#: Name of the rotating log file inside the user data directory.
LOG_FILE_NAME = "openlens.log"
LOG_FILE_MAX_BYTES = 512 * 1024
LOG_FILE_BACKUP_COUNT = 2
LOG_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"

#: Verbose flags accepted by both entry points.
VERBOSE_FLAGS = ("-v", "--verbose")


def verbose_requested(argv: Optional[Sequence[str]] = None) -> bool:
    """Whether *argv* (default ``sys.argv[1:]``) asks for debug logging.

    Args:
        argv: Command-line arguments without the program name.

    Returns:
        True when ``-v`` or ``--verbose`` is present.
    """
    args = list(sys.argv[1:] if argv is None else argv)
    return any(flag in args for flag in VERBOSE_FLAGS)


def log_file_path() -> Path:
    """Return the rotating log file's path. The file is created on setup."""
    return user_data_dir() / LOG_FILE_NAME


def _install_rotating_file_handler(root: logging.Logger, path: Path) -> bool:
    """Add the rotating file handler; log and give up when it is not writable."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.handlers.RotatingFileHandler(
            str(path),
            maxBytes=LOG_FILE_MAX_BYTES,
            backupCount=LOG_FILE_BACKUP_COUNT,
            encoding="utf-8",
        )
    except OSError as error:
        logger.warning("Could not open the log file %s: %s", path, error)
        return False

    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    handler._openlens_handler = True
    root.addHandler(handler)
    return True


def setup_logging(verbose: bool = False, log_file: Optional[Path] = None) -> None:
    """Send log records to stderr and to a rotating log file; idempotent.

    Args:
        verbose: Keep DEBUG records (the entry points pass the ``-v`` flag).
        log_file: Overrides the log file path; defaults to
            ``<user data directory>/openlens.log``.

    Returns:
        None
    """
    root = logging.getLogger()
    root.setLevel(logging.DEBUG if verbose else logging.INFO)

    if any(getattr(handler, "_openlens_handler", False) for handler in root.handlers):
        return

    stream = logging.StreamHandler()
    stream.setFormatter(logging.Formatter(LOG_FORMAT))
    stream._openlens_handler = True
    root.addHandler(stream)

    _install_rotating_file_handler(root, log_file or log_file_path())
