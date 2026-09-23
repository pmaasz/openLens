"""Pytest fixtures for automated GUI user-flow QA.

Headless-safe: forces QT_QPA_PLATFORM=offscreen when no DISPLAY is present,
wires OpenLensWindow to a hermetic temp SQLite DB so flows never touch the
production openlens.db, and processes the deferred library load deterministically.
"""

import os
import sys

import pytest

if os.environ.get("DISPLAY", "") == "" and sys.platform.startswith("linux"):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication
    from openlens import OpenLensWindow
    from src.gui.storage import LensStorage

    PYSIDE_AVAILABLE = True
except ImportError:
    QApplication = None  # type: ignore
    OpenLensWindow = None  # type: ignore
    LensStorage = None  # type: ignore
    PYSIDE_AVAILABLE = False

requires_pyside = pytest.mark.skipif(not PYSIDE_AVAILABLE, reason="PySide6 not available")


@pytest.fixture(scope="session")
def qapp():
    """Ensure a single QApplication for the session (pytest-qt also provides one)."""
    if not PYSIDE_AVAILABLE:
        pytest.skip("PySide6 not available")
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


@pytest.fixture()
def temp_db_path(tmp_path):
    """Hermetic SQLite path per test."""
    return str(tmp_path / "qa_test.db")


@pytest.fixture()
def main_window(qtbot, qapp, temp_db_path):
    """OpenLensWindow wired to a temp DB, shown offscreen, cleaned up after."""
    assert PYSIDE_AVAILABLE and OpenLensWindow is not None
    window = OpenLensWindow()
    # Redirect storage BEFORE the deferred singleShot load fires.
    window._storage = LensStorage(temp_db_path)
    window._db_path = temp_db_path
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window, timeout=5000)
    # Fire the deferred load deterministically against the temp DB.
    window._load_from_database()
    QApplication.processEvents()
    yield window
    window.close()
    for ext in ("", "-shm", "-wal"):
        try:
            if os.path.exists(temp_db_path + ext):
                os.remove(temp_db_path + ext)
        except OSError:
            pass
