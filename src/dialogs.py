"""
Custom dialog classes for openlens

Provides copyable message dialogs that allow users to select and copy
error messages, warnings, and information text.
"""

import tkinter as tk
from tkinter import ttk
from typing import Optional

# Import color constants
try:
    from .constants import (
        COLOR_BG_DARK, COLOR_BG_MEDIUM, COLOR_FG,
        COLOR_ACCENT, COLOR_WARNING, COLOR_ERROR
    )
except ImportError:
    try:
        from constants import (
            COLOR_BG_DARK, COLOR_BG_MEDIUM, COLOR_FG,
            COLOR_ACCENT, COLOR_WARNING, COLOR_ERROR
        )
    except ImportError:
        # Fallback colors
        COLOR_BG_DARK = "#1e1e1e"
        COLOR_BG_MEDIUM = "#2d2d2d"
        COLOR_FG = "#e0e0e0"
        COLOR_ACCENT = "#4a9eff"
        COLOR_WARNING = "#ff9800"
        COLOR_ERROR = "#f44336"


class CopyableMessageBox:
    """
    A custom message box that allows users to copy the message text.
    Replaces standard tkinter messagebox for error/warning/info dialogs.
    """
    
    @staticmethod
    def show(parent: Optional[tk.Widget], title: str, message: str, 
             icon_type: str = "info") -> None:
        """
        Show a message dialog with copyable text.
        
        Args:
            parent: Parent widget (can be None)
            title: Dialog title
            message: Message to display
            icon_type: One of "info", "warning", "error"
        """
        dialog = tk.Toplevel(parent)
        dialog.title(title)
        if parent:
            dialog.transient(parent)
        dialog.grab_set()
        
        # Size and position
        width, height = 500, 220
        dialog.geometry(f"{width}x{height}")
        dialog.minsize(400, 180)
        
        # Center on parent or screen
        if parent:
            x = parent.winfo_rootx() + (parent.winfo_width() - width) // 2
            y = parent.winfo_rooty() + (parent.winfo_height() - height) // 2
            dialog.geometry(f"+{max(0, x)}+{max(0, y)}")
        
        # Configure dark mode
        dialog.configure(bg=COLOR_BG_DARK)
        
        # Main frame
        main_frame = tk.Frame(dialog, bg=COLOR_BG_DARK, padx=20, pady=15)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Icon and title row
        icon_map = {
            "info": "ℹ️",
            "warning": "⚠️", 
            "error": "❌"
        }
        
        header_frame = tk.Frame(main_frame, bg=COLOR_BG_DARK)
        header_frame.pack(fill=tk.X, pady=(0, 10))
        
        icon_label = tk.Label(header_frame, text=icon_map.get(icon_type, "ℹ️"),
                             font=("Arial", 20), bg=COLOR_BG_DARK, fg=COLOR_FG)
        icon_label.pack(side=tk.LEFT, padx=(0, 10))
        
        title_label = tk.Label(header_frame, text=title,
                              font=("Arial", 12, "bold"), bg=COLOR_BG_DARK, fg=COLOR_FG)
        title_label.pack(side=tk.LEFT)
        
        # Message in a selectable Text widget
        text_frame = tk.Frame(main_frame, bg=COLOR_BG_MEDIUM, relief=tk.FLAT, bd=1)
        text_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        
        text_widget = tk.Text(text_frame, wrap=tk.WORD, height=5,
                             bg=COLOR_BG_MEDIUM, fg=COLOR_FG,
                             font=("Consolas", 10), relief=tk.FLAT,
                             padx=10, pady=10, cursor="xterm",
                             selectbackground=COLOR_ACCENT,
                             selectforeground=COLOR_FG,
                             insertbackground=COLOR_FG)
        text_widget.insert("1.0", message)
        text_widget.config(state="disabled")  # Read-only but still selectable
        text_widget.pack(fill=tk.BOTH, expand=True)
        
        # Enable text selection even when disabled
        def enable_select(event):
            text_widget.config(state="normal")
            text_widget.focus_set()
            return None
        
        def disable_edit(event):
            # Allow selection but prevent editing
            if event.keysym not in ('c', 'C', 'Control_L', 'Control_R', 
                                     'Left', 'Right', 'Up', 'Down',
                                     'Home', 'End', 'Shift_L', 'Shift_R'):
                if not (event.state & 0x4):  # Not Ctrl key
                    return "break"
            return None
        
        text_widget.bind("<Button-1>", enable_select)
        text_widget.bind("<KeyPress>", disable_edit)
        
        # Button frame
        btn_frame = tk.Frame(main_frame, bg=COLOR_BG_DARK)
        btn_frame.pack(fill=tk.X)
        
        def copy_to_clipboard() -> None:
            dialog.clipboard_clear()
            dialog.clipboard_append(message)
            copy_btn.config(text="✓ Copied!")
            dialog.after(1500, lambda: copy_btn.config(text="Copy"))
        
        # Style for buttons
        btn_style = {
            'font': ('Arial', 10),
            'bg': COLOR_BG_MEDIUM,
            'fg': COLOR_FG,
            'activebackground': COLOR_ACCENT,
            'activeforeground': COLOR_FG,
            'relief': tk.FLAT,
            'padx': 15,
            'pady': 5,
            'cursor': 'hand2'
        }
        
        copy_btn = tk.Button(btn_frame, text="Copy", command=copy_to_clipboard, **btn_style)
        copy_btn.pack(side=tk.LEFT)
        
        ok_btn = tk.Button(btn_frame, text="OK", command=dialog.destroy, 
                          **{**btn_style, 'bg': COLOR_ACCENT})
        ok_btn.pack(side=tk.RIGHT)
        
        # Keyboard shortcuts
        dialog.bind("<Return>", lambda e: dialog.destroy())
        dialog.bind("<Escape>", lambda e: dialog.destroy())
        dialog.bind("<Control-c>", lambda e: copy_to_clipboard())
        
        # Focus OK button
        ok_btn.focus_set()
        
        # Wait for dialog to close
        dialog.wait_window()
    
    @staticmethod
    def showerror(parent: Optional[tk.Widget], title: str, message: str) -> None:
        """Show error dialog with copyable text."""
        CopyableMessageBox.show(parent, title, message, "error")
    
    @staticmethod
    def showwarning(parent: Optional[tk.Widget], title: str, message: str) -> None:
        """Show warning dialog with copyable text."""
        CopyableMessageBox.show(parent, title, message, "warning")
    
    @staticmethod
    def showinfo(parent: Optional[tk.Widget], title: str, message: str) -> None:
        """Show info dialog with copyable text."""
        CopyableMessageBox.show(parent, title, message, "info")
