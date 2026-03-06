"""
OpenLens GUI Base Tab Module

Provides the abstract base class for tab components.
"""

import tkinter as tk
from tkinter import ttk
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ..theme import ThemeManager


class BaseTab(ABC):
    """Abstract base class for GUI tab components.
    
    This class provides a common interface for all tab components in the
    OpenLens GUI application. Each tab should inherit from this class
    and implement the abstract methods.
    
    Args:
        parent: The parent widget (typically a ttk.Notebook).
        colors: Color scheme dictionary for theming.
        on_status_update: Callback for status bar updates.
    
    Attributes:
        frame: The main frame widget for this tab.
        colors: Color scheme dictionary.
        status_callback: Callback for status updates.
    """
    
    def __init__(
        self,
        parent: ttk.Notebook,
        colors: Dict[str, str],
        on_status_update: Optional[callable] = None
    ) -> None:
        """Initialize the base tab.
        
        Args:
            parent: The parent notebook widget.
            colors: Color scheme dictionary.
            on_status_update: Callback for status messages.
        """
        self.parent = parent
        self.colors = colors
        self.status_callback = on_status_update or (lambda msg: None)
        
        # Create main frame
        self.frame = ttk.Frame(parent)
        
        # Set up UI (implemented by subclasses)
        self.setup_ui()
    
    @abstractmethod
    def setup_ui(self) -> None:
        """Set up the tab's user interface.
        
        Subclasses must implement this method to create their UI components.
        """
        pass
    
    @abstractmethod
    def refresh(self) -> None:
        """Refresh the tab's display.
        
        Subclasses should implement this to update their display when
        data changes.
        """
        pass
    
    def update_status(self, message: str) -> None:
        """Update the status bar.
        
        Args:
            message: Status message to display.
        """
        self.status_callback(message)
    
    def get_frame(self) -> ttk.Frame:
        """Get the tab's main frame widget.
        
        Returns:
            The ttk.Frame containing this tab's content.
        """
        return self.frame
    
    def on_tab_selected(self) -> None:
        """Called when this tab is selected.
        
        Override this method to perform actions when the tab becomes active.
        """
        pass
    
    def on_tab_deselected(self) -> None:
        """Called when this tab is deselected.
        
        Override this method to perform cleanup when leaving the tab.
        """
        pass
