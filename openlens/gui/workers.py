"""
OpenLens GUI background workers
Reusable QThread helpers for running analyses off the GUI thread
"""

import logging
from typing import Any, Callable, Optional

from PySide6.QtCore import QObject, QThread, Signal

logger = logging.getLogger(__name__)


class AnalysisWorker(QThread):
    """Runs one computation off the GUI thread and hands back its payload.

    Every analysis (plot or metric) used to do its multi-second computation
    *before* creating a window, so nothing was on screen and the app simply
    looked hung. Computing in a worker lets the caller be up and repainting
    first.

    Only the computation runs here; painting stays on the GUI thread, which Qt
    requires and the queued signal connection provides.
    """

    #: Emitted with whatever ``compute()`` returned.
    done = Signal(object)
    #: Emitted with the failure message when ``compute()`` raises.
    failed = Signal(str)

    def __init__(self, compute: Callable[[], Any], parent: Optional[QObject] = None) -> None:
        """Initialize the worker.

        Args:
            compute: Zero-argument callable doing the heavy work.
            parent: Optional owning object, for orderly teardown.
        """
        super().__init__(parent)
        self._compute = compute

    def run(self) -> None:
        """Execute the computation, reporting success or failure."""
        try:
            self.done.emit(self._compute())
        except Exception as exc:  # noqa: BLE001 - reported to the user via failed
            logger.error("Analysis computation failed: %s", exc, exc_info=True)
            self.failed.emit(str(exc))


def stop_worker(worker: Any, timeout_ms: int = 3000) -> bool:
    """Stop one QThread and report whether it actually stopped.

    Cooperative first, then terminate, then wait. Terminating a thread
    mid-write can leave a partially updated object behind, so it is only
    reached when the worker ignored the request - typically because it is
    inside one long evaluation with no callback boundary to return at.

    Shared by the main window's quit sweep and the image-simulation dialog, so
    there is exactly one stop policy.

    Args:
        worker: The QThread to stop, or None.
        timeout_ms: How long to wait for the cooperative request before
            escalating to terminate().

    Returns:
        True once the thread is known to be finished, so its last Python
        reference can safely be dropped.
    """
    if worker is None:
        return True

    try:
        if not worker.isRunning():
            return True
    except Exception as e:
        # Unknown state: report "not stopped" rather than guess, so the
        # caller keeps the reference. Dropping a live QThread's last
        # reference makes CPython destroy it and ~QThread aborts.
        logger.debug("Could not query worker state: %s", e)
        return False

    try:
        worker.requestInterruption()
        if not worker.wait(timeout_ms):
            worker.terminate()
            worker.wait()
    except Exception as e:
        logger.warning("Could not stop worker cleanly: %s", e)
        return False

    return True
