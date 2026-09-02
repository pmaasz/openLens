"""
OpenLens PySide6 GUI Package
"""

try:
    from .widgets import LensEditorWidget, LensVisualizationWidget
    from .dialogs import StartupDialog
except ImportError:
    # GUI dependencies (PySide6) not available - e.g., headless CI
    LensEditorWidget = None  # type: ignore
    LensVisualizationWidget = None  # type: ignore
    StartupDialog = None  # type: ignore

__all__ = [
    'LensEditorWidget',
    'LensVisualizationWidget',
    'StartupDialog',
]