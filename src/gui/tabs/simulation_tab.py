"""
OpenLens GUI Simulation Tab Module

Provides the ray tracing simulation tab component.
"""

import tkinter as tk
from tkinter import ttk
from typing import Optional, Dict, Any, Callable, TYPE_CHECKING

from .base_tab import BaseTab

if TYPE_CHECKING:
    from ...lens import Lens


class SimulationTab(BaseTab):
    """Tab component for ray tracing simulation.
    
    This tab provides functionality for:
    - Running ray tracing simulations
    - Visualizing ray paths through the lens
    - Adjusting simulation parameters
    
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
        """Initialize the simulation tab."""
        self.get_current_lens = get_current_lens or (lambda: None)
        self.controller = None
        
        super().__init__(parent, colors, on_status_update)
    
    def setup_ui(self) -> None:
        """Set up the simulation tab UI."""
        try:
            from ...gui_controllers import SimulationController
        except ImportError:
            try:
                from gui_controllers import SimulationController
            except ImportError:
                label = ttk.Label(
                    self.frame,
                    text="Simulation tab - Controller not available"
                )
                label.pack(padx=20, pady=20)
                return
        
        self.controller = SimulationController(
            parent_window=None,
            colors=self.colors,
            get_current_lens=self.get_current_lens
        )
        self.controller.setup_ui(self.frame)
    
    def refresh(self) -> None:
        """Refresh the simulation display."""
        pass  # Simulation refreshes on demand
    
    def run_simulation(self) -> None:
        """Run the ray tracing simulation."""
        if self.controller:
            self.controller.run_simulation()
