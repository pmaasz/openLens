"""
OpenLens GUI Main Window Module

This module provides the main LensEditorWindow class for the OpenLens
application. It re-exports from the original lens_editor_gui module
for backward compatibility while providing a cleaner package structure.

The full implementation remains in src/lens_editor_gui.py to maintain
compatibility with existing code. This module provides:
- LensEditorWindow: The main application window class
- Helper utilities for GUI setup

Future versions may migrate more functionality into this module.
"""

import logging
from typing import TYPE_CHECKING

logger = logging.getLogger(__name__)

# Re-export the main window class from the original module
try:
    from ..lens_editor_gui import LensEditorWindow, ToolTip
except ImportError:
    try:
        from lens_editor_gui import LensEditorWindow, ToolTip
    except ImportError:
        logger.error("Could not import LensEditorWindow from lens_editor_gui")
        # Provide stub for type checking
        if TYPE_CHECKING:
            class LensEditorWindow:  # type: ignore
                """Stub class for type checking."""
                pass
            
            class ToolTip:  # type: ignore
                """Stub class for type checking."""
                pass

# Re-export theme and storage from this package
from .theme import ThemeManager, COLORS, setup_dark_mode
from .storage import LensStorage, load_lenses, save_lenses
from .tooltip import ToolTip as ToolTipWidget

__all__ = [
    'LensEditorWindow',
    'ToolTip',
    'ToolTipWidget',
    'ThemeManager',
    'COLORS',
    'setup_dark_mode',
    'LensStorage',
    'load_lenses',
    'save_lenses',
]
