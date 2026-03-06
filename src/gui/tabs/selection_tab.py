"""
OpenLens GUI Selection Tab Module

Provides the lens selection tab component.
"""

import tkinter as tk
from tkinter import ttk
from typing import Optional, Dict, Any, List, Callable, TYPE_CHECKING

from .base_tab import BaseTab

if TYPE_CHECKING:
    from ...lens import Lens


class SelectionTab(BaseTab):
    """Tab component for lens selection and management.
    
    This tab provides functionality for:
    - Browsing the lens library
    - Selecting lenses to edit
    - Creating new lenses
    - Deleting and duplicating lenses
    
    Args:
        parent: The parent notebook widget.
        colors: Color scheme dictionary.
        lens_list: Reference to the list of lenses.
        on_lens_selected: Callback when a lens is selected.
        on_create_new: Callback for creating a new lens.
        on_delete: Callback for deleting a lens.
        on_lens_updated: Callback when lens data changes.
        on_status_update: Callback for status messages.
    """
    
    def __init__(
        self,
        parent: ttk.Notebook,
        colors: Dict[str, str],
        lens_list: List['Lens'],
        on_lens_selected: Optional[Callable] = None,
        on_create_new: Optional[Callable] = None,
        on_delete: Optional[Callable] = None,
        on_lens_updated: Optional[Callable] = None,
        on_status_update: Optional[Callable[[str], None]] = None
    ) -> None:
        """Initialize the selection tab."""
        self.lens_list = lens_list
        self.on_lens_selected = on_lens_selected
        self.on_create_new = on_create_new
        self.on_delete = on_delete
        self.on_lens_updated = on_lens_updated
        self.controller = None
        
        # Call parent constructor (which calls setup_ui)
        super().__init__(parent, colors, on_status_update)
    
    def setup_ui(self) -> None:
        """Set up the selection tab UI.
        
        This method initializes the LensSelectionController which handles
        the actual UI creation.
        """
        # Import controller
        try:
            from ...gui_controllers import LensSelectionController
        except ImportError:
            try:
                from gui_controllers import LensSelectionController
            except ImportError:
                # Controller not available - create placeholder UI
                label = ttk.Label(
                    self.frame,
                    text="Selection tab - Controller not available"
                )
                label.pack(padx=20, pady=20)
                return
        
        # Create controller
        self.controller = LensSelectionController(
            parent_window=None,  # Will be set by main window
            lens_list=self.lens_list,
            colors=self.colors,
            on_lens_selected=self.on_lens_selected or (lambda lens: None),
            on_create_new=self.on_create_new or (lambda: None),
            on_delete=self.on_delete or (lambda: None),
            on_lens_updated=self.on_lens_updated or (lambda: None)
        )
        
        # Set up controller UI in our frame
        self.controller.setup_ui(self.frame)
    
    def refresh(self) -> None:
        """Refresh the lens list display."""
        if self.controller:
            self.controller.refresh_list(self.lens_list)
    
    def select_lens(self, lens: 'Lens') -> None:
        """Select a specific lens in the list.
        
        Args:
            lens: The lens to select.
        """
        if self.controller:
            self.controller.select_lens(lens)
    
    def get_selected_lens(self) -> Optional['Lens']:
        """Get the currently selected lens.
        
        Returns:
            The selected Lens object, or None if nothing is selected.
        """
        if self.controller:
            return self.controller.selected_lens
        return None
