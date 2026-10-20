"""Tests package for openLens.

The test run must never write the developer's real user data. Two defaults are
now per-user files: the SQLite library and the material catalog. A number of
tests construct ``MaterialDatabase()`` (or ``LensStorage()``) with no path and
then add material, and before this guard those writes landed in the checkout's
``data/materials.json`` - which is how ``TEST_GLASS`` and friends ended up in a
real catalog.

``setdefault`` rather than assignment: an explicit override from the developer
or CI still wins.

This module also owns the one ``QApplication`` for the whole suite. Each GUI
test module used to create its own and keep it in a module global; when only a
few such modules run, the globals were cleared in an arbitrary order during
interpreter shutdown and Qt tore down around live widgets, segfaulting
(#557). ``ensure_qapp()`` keeps a single strong reference here, and the atexit
hook delivers pending deletions while the application is still alive.
"""

import atexit
import os
import shutil
import sys
import tempfile
from pathlib import Path

_TEST_DATA_DIR = Path(tempfile.mkdtemp(prefix="openlens-tests-"))

os.environ.setdefault("OPENLENS_DATA_DIR", str(_TEST_DATA_DIR))
os.environ.setdefault("OPENLENS_MATERIALS_PATH", str(_TEST_DATA_DIR / "materials.json"))

#: The suite's only QApplication; see module docstring.
_qapp = None


def ensure_qapp():
    """Return the shared QApplication, creating it on first use.

    Every GUI test module must go through this instead of calling
    ``QApplication(...)`` itself: the reference kept here outlives the test
    modules, so Qt is not torn down under widgets that are still alive.

    Returns:
        The process-wide QApplication instance.
    """
    global _qapp
    if _qapp is None:
        if sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
            os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        _qapp = QApplication.instance() or QApplication([])
    return _qapp


def flush_qt() -> None:
    """Deliver pending deleteLater events while the application is alive.

    Widgets closed by a test are only scheduled for deletion. Without a flush
    they can outlive their module and be destroyed after Qt has started
    shutting down, which is what makes the small-module run crash.
    """
    from PySide6.QtCore import QCoreApplication, QEvent
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        return
    app.processEvents()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()


@atexit.register
def _flush_qt_before_exit() -> None:
    if _qapp is None:
        return
    flush_qt()
    _qapp.closeAllWindows()
    flush_qt()


atexit.register(shutil.rmtree, str(_TEST_DATA_DIR), True)
