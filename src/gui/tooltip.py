"""
OpenLens GUI Tooltip Module

Provides tooltip widget functionality for the GUI.
"""

import tkinter as tk
from typing import Optional

# Import constants
try:
    from ..constants import (
        TOOLTIP_OFFSET_X, TOOLTIP_OFFSET_Y,
        COLOR_BG_DARK, COLOR_FG,
        PADDING_SMALL,
    )
except ImportError:
    try:
        from constants import (
            TOOLTIP_OFFSET_X, TOOLTIP_OFFSET_Y,
            COLOR_BG_DARK, COLOR_FG,
            PADDING_SMALL,
        )
    except ImportError:
        # Fallback defaults
        TOOLTIP_OFFSET_X = 25
        TOOLTIP_OFFSET_Y = 25
        COLOR_BG_DARK = '#252526'
        COLOR_FG = '#e0e0e0'
        PADDING_SMALL = 5


class ToolTip:
    """Simple tooltip for tkinter widgets.
    
    Displays a small popup with help text when hovering over a widget.
    
    Args:
        widget: The tkinter widget to attach the tooltip to.
        text: The text to display in the tooltip.
    
    Example:
        >>> button = tk.Button(root, text="Click me")
        >>> ToolTip(button, "This button does something")
    """
    
    def __init__(self, widget: tk.Widget, text: str) -> None:
        """Initialize tooltip with widget binding.
        
        Args:
            widget: The tkinter widget to attach the tooltip to.
            text: The text to display in the tooltip.
        """
        self.widget = widget
        self.text = text
        self.tooltip: Optional[tk.Toplevel] = None
        self.widget.bind("<Enter>", self.show_tooltip)
        self.widget.bind("<Leave>", self.hide_tooltip)
    
    def show_tooltip(self, event: Optional[tk.Event] = None) -> None:
        """Show the tooltip near the widget.
        
        Args:
            event: The mouse enter event (optional).
        """
        x, y, _, _ = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + TOOLTIP_OFFSET_X
        y += self.widget.winfo_rooty() + TOOLTIP_OFFSET_Y
        
        self.tooltip = tk.Toplevel(self.widget)
        self.tooltip.wm_overrideredirect(True)
        self.tooltip.wm_geometry(f"+{x}+{y}")
        
        label = tk.Label(
            self.tooltip,
            text=self.text,
            background=COLOR_BG_DARK,
            foreground=COLOR_FG,
            relief=tk.SOLID,
            borderwidth=1,
            font=("Arial", 9),
            padx=PADDING_SMALL,
            pady=3
        )
        label.pack()
    
    def hide_tooltip(self, event: Optional[tk.Event] = None) -> None:
        """Hide and destroy the tooltip.
        
        Args:
            event: The mouse leave event (optional).
        """
        if self.tooltip:
            self.tooltip.destroy()
            self.tooltip = None
