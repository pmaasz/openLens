"""
OpenLens GUI Theme Module

Provides theme management and dark mode styling for the GUI.
"""

import tkinter as tk
from tkinter import ttk
from typing import Dict, Any, Optional

# Import color constants
try:
    from ..constants import COLOR_BG_DARK
except ImportError:
    try:
        from constants import COLOR_BG_DARK
    except ImportError:
        COLOR_BG_DARK = '#252526'


# Sun Valley Dark inspired color scheme
COLORS: Dict[str, str] = {
    'bg': '#1c1c1c',           # Main window background
    'fg': '#ffffff',           # Main text
    'bg_dark': '#202020',      # Darker sections (tab background)
    'bg_light': '#2c2c2c',     # Lighter sections (card/surface)
    'accent': '#005fb8',       # Accent color (blue)
    'accent_hover': '#1a6dc4', # Accent hover
    'border': '#454545',       # Border color
    'input_bg': '#383838',     # Input field background
    'button_bg': '#333333',    # Button background
    'button_hover': '#454545', # Button hover
    'success': '#6cc417',      # Success green
    'warning': '#fca130',      # Warning orange
    'error': '#ff4d4f',        # Error red
    'text_dim': '#a0a0a0',     # Dimmed text
    'selected': '#37373d',     # Selected item
    'entry_bg': '#2b2b2b',     # Keep for compatibility
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
    
    def __init__(self, root: tk.Tk, colors: Optional[Dict[str, str]] = None) -> None:
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
            bordercolor=self.colors['border'],
            labelmargins=5
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
            foreground=self.colors['fg'],
            padding=2
        )
        
        # Button styles
        style.configure(
            'TButton',
            background=self.colors['button_bg'],
            foreground=self.colors['fg'],
            bordercolor=self.colors['border'],
            focuscolor=self.colors['accent'],
            lightcolor=self.colors['bg_light'],
            darkcolor=self.colors['bg_dark'],
            padding=[8, 4],
            relief='flat'
        )
        
        style.map(
            'TButton',
            background=[
                ('active', self.colors['button_hover']),
                ('pressed', self.colors['accent'])
            ],
            foreground=[('active', self.colors['fg'])],
            bordercolor=[('active', self.colors['accent'])]
        )
        
        # Entry styles
        style.configure(
            'TEntry',
            fieldbackground=self.colors['input_bg'],
            background=self.colors['input_bg'],
            foreground=self.colors['fg'],
            bordercolor=self.colors['border'],
            insertcolor=self.colors['fg'],
            padding=5,
            relief='flat'
        )
        
        # Readonly entry style (darker background to indicate readonly)
        style.map(
            'TEntry',
            fieldbackground=[('readonly', self.colors['bg_dark'])],
            foreground=[('readonly', self.colors['text_dim'])],
            bordercolor=[('focus', self.colors['accent'])]
        )
        
        # Combobox styles
        style.configure(
            'TCombobox',
            fieldbackground=self.colors['input_bg'],
            background=self.colors['input_bg'],
            foreground=self.colors['fg'],
            bordercolor=self.colors['border'],
            arrowcolor=self.colors['fg'],
            selectbackground=self.colors['accent'],
            selectforeground=self.colors['fg'],
            padding=5
        )
        
        style.map(
            'TCombobox',
            fieldbackground=[('readonly', self.colors['input_bg'])],
            selectbackground=[('readonly', self.colors['accent'])],
            selectforeground=[('readonly', self.colors['fg'])],
            bordercolor=[('focus', self.colors['accent'])]
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


def setup_dark_mode(root: tk.Tk, colors: Optional[Dict[str, str]] = None) -> ThemeManager:
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
