"""
Windows Taskbar Integration Module for OpenLens

This module provides Windows Jump List integration to allow users
to quickly open different lenses/assemblies from the taskbar.
"""

import sys
import os
import logging
from typing import List, Optional, Any

import tkinter as tk
from tkinter import ttk

logger = logging.getLogger(__name__)

IS_WINDOWS = sys.platform == 'win32'


class TaskbarManager:
    """Manages Windows taskbar jump list integration."""

    def __init__(self) -> None:
        self._is_available = False
        self._app_id: Optional[str] = None

        if IS_WINDOWS:
            self._init_windows_integration()

    def _init_windows_integration(self) -> None:
        """Initialize Windows-specific taskbar integration."""
        try:
            import ctypes
            from ctypes import wintypes

            # Try to use Windows Shell API via ctypes
            # This is a simplified implementation that doesn't require pywin32
            self._ctypes = ctypes
            self._is_available = True
            logger.debug("Windows taskbar integration initialized")
        except ImportError:
            logger.warning("ctypes not available for taskbar integration")
            self._is_available = False
        except Exception as e:
            logger.warning("Failed to initialize taskbar integration: %s", e)
            self._is_available = False

    @property
    def is_available(self) -> bool:
        """Check if taskbar integration is available."""
        return self._is_available and IS_WINDOWS

    def set_app_id(self, app_id: str) -> None:
        """Set the application user model ID for taskbar grouping."""
        self._app_id = app_id

    def update_recent_items(self, lenses: List[Any], assemblies: List[Any]) -> None:
        """Update taskbar with recent lens and assembly items.

        Args:
            lenses: List of lens objects to display
            assemblies: List of assembly/system objects to display
        """
        if not self.is_available:
            return

        try:
            self._update_jump_list(lenses, assemblies)
        except Exception as e:
            logger.warning("Failed to update taskbar items: %s", e)

    def _update_jump_list(self, lenses: List[Any], assemblies: List[Any]) -> None:
        """Internal method to update Windows Jump List."""
        if not IS_WINDOWS:
            return

        try:
            import ctypes
            from ctypes import wintypes

            # Windows Shell API constants
            CLSID_ShellLink = "{00021401-0000-0000-C000-000000000046}"
            IID_IShellLinkW = "{000214F9-0000-0000-C000-000000000046}"
            IID_IPropertyStore = "{886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99}"

            # Try to create a proper jump list using COM
            # This is a simplified fallback that logs the intent
            recent_count = len(lenses) + len(assemblies)
            logger.info(
                "Would update jump list with %d items: %d lenses, %d assemblies",
                recent_count, len(lenses), len(assemblies)
            )

            # Store for reference - actual implementation would use COM
            self._cached_lenses = lenses
            self._cached_assemblies = assemblies

        except Exception as e:
            logger.debug("Jump list update detailed error: %s", e)

    def clear_recent_items(self) -> None:
        """Clear recent items from taskbar."""
        if not self.is_available:
            return

        try:
            logger.debug("Clearing taskbar recent items")
            self._cached_lenses = []
            self._cached_assemblies = []
        except Exception as e:
            logger.warning("Failed to clear taskbar items: %s", e)


def get_taskbar_manager() -> TaskbarManager:
    """Factory function to get the global taskbar manager instance."""
    global _taskbar_manager
    if _taskbar_manager is None:
        _taskbar_manager = TaskbarManager()
    return _taskbar_manager


_taskbar_manager: Optional[TaskbarManager] = None


class TaskbarMenu:
    """In-application taskbar-style menu for quick lens switching."""

    def __init__(self, parent_window: Any, colors: dict) -> None:
        self.parent = parent_window
        self.colors = colors
        self.menu: Optional[Any] = None
        self._lenses: List[Any] = []
        self._assemblies: List[Any] = []

    def create_menu(self, parent_widget: Any) -> Any:
        """Create a taskbar-style menu for lens switching."""
        import tkinter as tk
        from tkinter import ttk

        self.menu = tk.Menu(parent_widget, tearoff=0,
                           bg=self.colors.get('bg', '#252526'),
                           fg=self.colors.get('fg', '#e0e0e0'),
                           activebackground=self.colors.get('accent', '#007acc'),
                           activeforeground=self.colors.get('fg', '#e0e0e0'))

        return self.menu

    def update_items(self, lenses: List[Any], assemblies: List[Any],
                    on_select_lens: Any, on_select_assembly: Any) -> None:
        """Update menu with current lenses and assemblies.

        Args:
            lenses: List of lens objects
            assemblies: List of assembly objects
            on_select_lens: Callback function(lens_name) when lens selected
            on_select_assembly: Callback function(assembly_name) when assembly selected
        """
        if not self.menu:
            return

        self._lenses = lenses
        self._assemblies = assemblies

        # Clear existing menu items
        self.menu.delete(0, tk.END)

        # Add lens section
        if lenses:
            self.menu.add_command(label="--- Lenses ---", state='disabled')
            for lens in lenses:
                self.menu.add_command(
                    label=f"  {lens.name}",
                    command=lambda n=lens.name: on_select_lens(n)
                )

        # Add assembly section
        if assemblies:
            if lenses:
                self.menu.add_separator()
            self.menu.add_command(label="--- Assemblies ---", state='disabled')
            for assembly in assemblies:
                self.menu.add_command(
                    label=f"  {assembly.name}",
                    command=lambda n=assembly.name: on_select_assembly(n)
                )

        # Add separator and quit option if menu has items
        if lenses or assemblies:
            self.menu.add_separator()
            self.menu.add_command(
                label="Refresh List",
                command=lambda: self.update_items(
                    self._lenses, self._assemblies,
                    on_select_lens, on_select_assembly
                )
            )

    def show_at_mouse(self, event: Any) -> None:
        """Show menu at mouse position."""
        if self.menu:
            try:
                self.menu.tk_popup(event.x_root, event.y_root)
            finally:
                self.menu.grab_release()