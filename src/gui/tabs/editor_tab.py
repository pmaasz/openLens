"""
OpenLens GUI Editor Tab Module

Provides the lens editor tab component.
"""

import tkinter as tk
from tkinter import ttk
from typing import Optional, Dict, Any, Callable, TYPE_CHECKING

from .base_tab import BaseTab

if TYPE_CHECKING:
    from ...lens import Lens


class EditorTab(BaseTab):
    """Tab component for editing lens properties.
    
    This tab provides functionality for:
    - Editing lens parameters (radii, thickness, refractive index)
    - Viewing calculated properties (focal length, power)
    - Setting lens name and type
    
    Args:
        parent: The parent notebook widget.
        colors: Color scheme dictionary.
        on_lens_changed: Callback when lens properties change.
        on_status_update: Callback for status messages.
    """
    
    def __init__(
        self,
        parent: ttk.Notebook,
        colors: Dict[str, str],
        on_lens_changed: Optional[Callable] = None,
        on_status_update: Optional[Callable[[str], None]] = None
    ) -> None:
        """Initialize the editor tab."""
        self.on_lens_changed = on_lens_changed
        self.controller = None
        self.current_lens: Optional['Lens'] = None
        
        super().__init__(parent, colors, on_status_update)
    
    def setup_ui(self) -> None:
        """Set up the editor tab UI."""
        try:
            from ...gui_controllers import LensEditorController
        except ImportError:
            try:
                from gui_controllers import LensEditorController
            except ImportError:
                label = ttk.Label(
                    self.frame,
                    text="Editor tab - Controller not available"
                )
                label.pack(padx=20, pady=20)
                return
        
        self.controller = LensEditorController(
            parent_window=None,
            colors=self.colors,
            on_lens_changed=self.on_lens_changed or (lambda lens: None)
        )
        self.controller.setup_ui(self.frame)
    
    def refresh(self) -> None:
        """Refresh the editor display."""
        if self.controller and self.current_lens:
            self.controller.load_lens(self.current_lens)
    
    def load_lens(self, lens: 'Lens') -> None:
        """Load a lens into the editor.
        
        Args:
            lens: The lens to edit.
        """
        self.current_lens = lens
        if self.controller:
            self.controller.load_lens(lens)
    
    def get_edited_lens(self) -> Optional['Lens']:
        """Get the lens with current edits applied.
        
        Returns:
            The edited Lens object.
        """
        if self.controller:
            return self.controller.get_lens()
        return self.current_lens
