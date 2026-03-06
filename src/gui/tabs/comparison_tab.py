"""
OpenLens GUI Comparison Tab Module

Provides the lens comparison tab component.
"""

import tkinter as tk
from tkinter import ttk
from typing import Optional, Dict, Any, List, Callable, TYPE_CHECKING

from .base_tab import BaseTab

if TYPE_CHECKING:
    from ...lens import Lens


class ComparisonTab(BaseTab):
    """Tab component for comparing multiple lenses.
    
    This tab provides functionality for:
    - Selecting multiple lenses to compare
    - Side-by-side property comparison
    - Performance comparison charts
    
    Args:
        parent: The parent notebook widget.
        colors: Color scheme dictionary.
        lens_list: Reference to the list of lenses.
        on_status_update: Callback for status messages.
    """
    
    def __init__(
        self,
        parent: ttk.Notebook,
        colors: Dict[str, str],
        lens_list: List['Lens'],
        on_status_update: Optional[Callable[[str], None]] = None
    ) -> None:
        """Initialize the comparison tab."""
        self.lens_list = lens_list
        self.controller = None
        
        super().__init__(parent, colors, on_status_update)
    
    def setup_ui(self) -> None:
        """Set up the comparison tab UI."""
        try:
            from ...gui_controllers import ComparisonController
        except ImportError:
            try:
                from gui_controllers import ComparisonController
            except ImportError:
                label = ttk.Label(
                    self.frame,
                    text="Comparison tab - Controller not available"
                )
                label.pack(padx=20, pady=20)
                return
        
        self.controller = ComparisonController(
            parent_window=None,
            colors=self.colors,
            lens_list=self.lens_list
        )
        self.controller.setup_ui(self.frame)
    
    def refresh(self) -> None:
        """Refresh the comparison display."""
        if self.controller:
            self.controller.refresh_lens_list(self.lens_list)
    
    def compare_lenses(self, lenses: List['Lens']) -> None:
        """Compare the specified lenses.
        
        Args:
            lenses: List of lenses to compare.
        """
        if self.controller:
            self.controller.compare_lenses(lenses)
