"""
OpenLens GUI Performance Tab Module

Provides the aberration analysis tab component.
"""

import tkinter as tk
from tkinter import ttk
from typing import Optional, Dict, Any, Callable, TYPE_CHECKING

from .base_tab import BaseTab

if TYPE_CHECKING:
    from ...lens import Lens


class PerformanceTab(BaseTab):
    """Tab component for aberration analysis and performance metrics.
    
    This tab provides functionality for:
    - Calculating optical aberrations
    - Displaying performance metrics
    - Quality analysis
    
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
        """Initialize the performance tab."""
        self.get_current_lens = get_current_lens or (lambda: None)
        self.controller = None
        
        super().__init__(parent, colors, on_status_update)
    
    def setup_ui(self) -> None:
        """Set up the performance tab UI."""
        try:
            from ...gui_controllers import PerformanceController
        except ImportError:
            try:
                from gui_controllers import PerformanceController
            except ImportError:
                label = ttk.Label(
                    self.frame,
                    text="Performance tab - Controller not available"
                )
                label.pack(padx=20, pady=20)
                return
        
        self.controller = PerformanceController(
            parent_window=None,
            colors=self.colors,
            get_current_lens=self.get_current_lens
        )
        self.controller.setup_ui(self.frame)
    
    def refresh(self) -> None:
        """Refresh the performance display."""
        if self.controller:
            self.controller.analyze_performance()
    
    def analyze(self) -> None:
        """Run aberration analysis."""
        if self.controller:
            self.controller.analyze_performance()
