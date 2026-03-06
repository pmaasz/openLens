"""
OpenLens GUI Export Tab Module

Provides the export functionality tab component.
"""

import tkinter as tk
from tkinter import ttk
from typing import Optional, Dict, Any, Callable, TYPE_CHECKING

from .base_tab import BaseTab

if TYPE_CHECKING:
    from ...lens import Lens


class ExportTab(BaseTab):
    """Tab component for exporting lens data.
    
    This tab provides functionality for:
    - Exporting to JSON format
    - Exporting to STL for 3D printing
    - Exporting lens specifications
    
    Args:
        parent: The parent notebook widget.
        colors: Color scheme dictionary.
        get_current_lens: Callback to get the current lens.
        on_status_update: Callback for status messages.
    """
    
    def __init__(
        self,
        parent: ttk.Notebook,
        colors: Dict[str, str],
        get_current_lens: Optional[Callable[[], Optional['Lens']]] = None,
        on_status_update: Optional[Callable[[str], None]] = None
    ) -> None:
        """Initialize the export tab."""
        self.get_current_lens = get_current_lens or (lambda: None)
        self.controller = None
        
        super().__init__(parent, colors, on_status_update)
    
    def setup_ui(self) -> None:
        """Set up the export tab UI."""
        try:
            from ...gui_controllers import ExportController
        except ImportError:
            try:
                from gui_controllers import ExportController
            except ImportError:
                label = ttk.Label(
                    self.frame,
                    text="Export tab - Controller not available"
                )
                label.pack(padx=20, pady=20)
                return
        
        self.controller = ExportController(
            parent_window=None,
            colors=self.colors,
            get_current_lens=self.get_current_lens
        )
        self.controller.setup_ui(self.frame)
    
    def refresh(self) -> None:
        """Refresh the export display."""
        pass  # Export tab doesn't need refresh
    
    def export_json(self) -> None:
        """Export current lens to JSON."""
        if self.controller:
            self.controller.export_json()
    
    def export_stl(self) -> None:
        """Export current lens to STL."""
        if self.controller:
            self.controller.export_stl()
