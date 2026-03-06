"""
OpenLens GUI Package

This package contains the graphical user interface components for the OpenLens
optical lens design application.

Modules:
    main_window: Main application window and coordinator
    theme: Theme management and dark mode styling
    tooltip: Tooltip widget for help text
    storage: Lens data persistence
    tabs: Tab components for different functionality areas

Example:
    >>> from src.gui import LensEditorWindow
    >>> import tkinter as tk
    >>> root = tk.Tk()
    >>> app = LensEditorWindow(root)
    >>> root.mainloop()
"""

# Import main components with graceful fallbacks
try:
    from .main_window import LensEditorWindow
except ImportError:
    LensEditorWindow = None  # type: ignore

from .tooltip import ToolTip
from .theme import ThemeManager, COLORS, setup_dark_mode
from .storage import LensStorage, load_lenses, save_lenses

# Import tab components
from .tabs import (
    BaseTab,
    SelectionTab,
    EditorTab,
    SimulationTab,
    PerformanceTab,
    ComparisonTab,
    ExportTab,
)

__all__ = [
    # Main window
    'LensEditorWindow',
    # UI Components
    'ToolTip',
    'ThemeManager',
    'COLORS',
    'setup_dark_mode',
    # Storage
    'LensStorage',
    'load_lenses',
    'save_lenses',
    # Tab components
    'BaseTab',
    'SelectionTab',
    'EditorTab',
    'SimulationTab',
    'PerformanceTab',
    'ComparisonTab',
    'ExportTab',
]
