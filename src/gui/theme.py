"""
OpenLens GUI Theme Module

Provides theme management and dark mode styling for the GUI.
"""

import tkinter as tk
from tkinter import ttk
from typing import Dict, Any

# Import color constants
try:
    from ..constants import COLOR_BG_DARK
except ImportError:
    try:
        from constants import COLOR_BG_DARK
    except ImportError:
        COLOR_BG_DARK = '#252526'


# Dark mode color scheme
COLORS: Dict[str, str] = {
    'bg': '#1e1e1e',           # Main background
    'fg': '#e0e0e0',           # Main text
    'bg_dark': COLOR_BG_DARK,  # Darker sections
    'bg_light': '#2d2d2d',     # Lighter sections
    'accent': '#0078d4',       # Accent color (blue)
    'accent_hover': '#1e88e5', # Accent hover
    'border': '#3f3f3f',       # Border color
    'success': '#4caf50',      # Success green
    'warning': '#ff9800',      # Warning orange
    'error': '#f44336',        # Error red
    'text_dim': '#b0b0b0',     # Dimmed text
    'selected': '#37373d',     # Selected item
    'entry_bg': '#2b2b2b',     # Entry field background
    'button_bg': '#3c3c3c',    # Button background
}


class ThemeManager:
    """Manages the application theme and dark mode styling.
    
    This class provides methods to configure ttk styles for a consistent
    dark mode appearance across all widgets.
    
    Args:
        root: The root Tk window to apply theming to.
        colors: Optional custom color dictionary. Defaults to COLORS.
    
    Example:
        >>> root = tk.Tk()
        >>> theme = ThemeManager(root)
        >>> theme.setup_dark_mode()
    """
    
    def __init__(self, root: tk.Tk, colors: Dict[str, str] = None) -> None:
        """Initialize the theme manager.
        
        Args:
            root: The root Tk window.
            colors: Optional custom color dictionary.
        """
        self.root = root
        self.colors = colors or COLORS
    
    def setup_dark_mode(self) -> None:
        """Configure dark mode theme for the application.
        
        Applies dark mode styling to all ttk widgets including frames,
        labels, buttons, entries, comboboxes, and notebooks.
        """
        # Configure root window
        self.root.configure(bg=self.colors['bg'])
        
        # Create custom ttk style
        style = ttk.Style()
        style.theme_use('clam')  # Use clam theme as base
        
        # Configure general ttk styles
        style.configure(
            '.',
            background=self.colors['bg'],
            foreground=self.colors['fg'],
            bordercolor=self.colors['border'],
            darkcolor=self.colors['bg_dark'],
            lightcolor=self.colors['bg_light'],
            troughcolor=self.colors['bg_dark'],
            focuscolor=self.colors['accent'],
            selectbackground=self.colors['accent'],
            selectforeground=self.colors['fg']
        )
        
        # Frame styles
        style.configure('TFrame', background=self.colors['bg'])
        
        style.configure(
            'TLabelframe',
            background=self.colors['bg'],
            foreground=self.colors['fg'],
            bordercolor=self.colors['border']
        )
        
        style.configure(
            'TLabelframe.Label',
            background=self.colors['bg'],
            foreground=self.colors['fg']
        )
        
        # Label styles
        style.configure(
            'TLabel',
            background=self.colors['bg'],
            foreground=self.colors['fg']
        )
        
        # Button styles
        style.configure(
            'TButton',
            background=self.colors['button_bg'],
            foreground=self.colors['fg'],
            bordercolor=self.colors['border'],
            focuscolor=self.colors['accent'],
            lightcolor=self.colors['bg_light'],
            darkcolor=self.colors['bg_dark']
        )
        
        style.map(
            'TButton',
            background=[
                ('active', self.colors['accent']),
                ('pressed', self.colors['bg_dark'])
            ],
            foreground=[('active', self.colors['fg'])]
        )
        
        # Entry styles
        style.configure(
            'TEntry',
            fieldbackground=self.colors['entry_bg'],
            background=self.colors['entry_bg'],
            foreground=self.colors['fg'],
            bordercolor=self.colors['border'],
            insertcolor=self.colors['fg']
        )
        
        # Readonly entry style (darker background to indicate readonly)
        style.map(
            'TEntry',
            fieldbackground=[('readonly', self.colors['bg_dark'])],
            foreground=[('readonly', self.colors['text_dim'])]
        )
        
        # Combobox styles
        style.configure(
            'TCombobox',
            fieldbackground=self.colors['entry_bg'],
            background=self.colors['entry_bg'],
            foreground=self.colors['fg'],
            bordercolor=self.colors['border'],
            arrowcolor=self.colors['fg'],
            selectbackground=self.colors['accent'],
            selectforeground=self.colors['fg']
        )
        
        style.map(
            'TCombobox',
            fieldbackground=[('readonly', self.colors['entry_bg'])],
            selectbackground=[('readonly', self.colors['accent'])],
            selectforeground=[('readonly', self.colors['fg'])]
        )
        
        # Separator style
        style.configure('TSeparator', background=self.colors['border'])
        
        # Notebook (tab) styles
        style.configure(
            'TNotebook',
            background=self.colors['bg'],
            bordercolor=self.colors['border'],
            tabmargins=[2, 5, 2, 0]
        )
        
        style.configure(
            'TNotebook.Tab',
            background=self.colors['bg_dark'],
            foreground=self.colors['fg'],
            padding=[20, 10],
            bordercolor=self.colors['border']
        )
        
        style.map(
            'TNotebook.Tab',
            background=[
                ('selected', self.colors['accent']),
                ('active', self.colors['bg_light'])
            ],
            foreground=[
                ('selected', self.colors['fg']),
                ('active', self.colors['fg'])
            ],
            expand=[('selected', [1, 1, 1, 0])]
        )


def setup_dark_mode(root: tk.Tk, colors: Dict[str, str] = None) -> ThemeManager:
    """Convenience function to set up dark mode on a root window.
    
    Args:
        root: The root Tk window.
        colors: Optional custom color dictionary.
    
    Returns:
        The ThemeManager instance for further customization.
    
    Example:
        >>> root = tk.Tk()
        >>> theme = setup_dark_mode(root)
    """
    theme = ThemeManager(root, colors)
    theme.setup_dark_mode()
    return theme
