"""
OpenLens GUI Storage Module

Provides lens data persistence functionality for the GUI.
"""

import json
import logging
import os
from pathlib import Path
from typing import List, Optional, Callable, Any, TYPE_CHECKING

# Configure module logger
logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from ..lens import Lens
    from ..optical_system import OpticalSystem
    from ..validation import (
        validate_json_file_path,
        validate_file_path,
        ValidationError
    )
else:
    # Import Lens model (Runtime)
    try:
        from ..lens import Lens
    except ImportError:
        try:
            from lens import Lens
        except ImportError:
            logger.error("Could not import Lens model")
            class Lens:
                """Fallback Lens class."""
                pass
                
    # Import OpticalSystem model (Runtime)
    try:
        from ..optical_system import OpticalSystem
    except ImportError:
        try:
            from optical_system import OpticalSystem
        except ImportError:
            logger.warning("Could not import OpticalSystem model")
            class OpticalSystem:
                """Fallback OpticalSystem class."""
                pass

    # Import validation utilities (Runtime)
    try:
        from ..validation import (
            validate_json_file_path,
            validate_file_path,
            ValidationError
        )
    except ImportError:
        try:
            from validation import (
                validate_json_file_path,
                validate_file_path,
                ValidationError
            )
        except ImportError:
            # Fallback if validation module not available
            ValidationError = ValueError
            
            def validate_json_file_path(path: Any, **kwargs: Any) -> Path:
                """Fallback validation function."""
                return Path(path)
            
            def validate_file_path(path: Any, **kwargs: Any) -> Path:
                """Fallback validation function."""
                return Path(path)

    # Import DatabaseManager (Runtime)
    try:
        from ..database import DatabaseManager
    except ImportError:
        try:
            from database import DatabaseManager
        except ImportError:
            logger.warning("Could not import DatabaseManager")
            DatabaseManager = None


class LensStorage:
    """Handles lens data persistence to SQLite database.
    
    This class provides methods to load and save lens data using DatabaseManager.
    
    Args:
        storage_file: Path to the database file (defaults to openlens.db).
        status_callback: Optional callback function to report status messages.
    """
    
    def __init__(
        self,
        storage_file: str = "openlens.db",
        status_callback: Optional[Callable[[str], None]] = None
    ) -> None:
        """Initialize the storage handler.
        
        Args:
            storage_file: Path to the database file.
            status_callback: Optional callback for status messages.
        """
        # Maintain compatibility: if called with lenses.json, change to .db
        if storage_file.endswith(".json"):
            storage_file = storage_file.replace(".json", ".db")
            
        self.storage_file = storage_file
        self.status_callback = status_callback or (lambda msg: None)
        
        if DatabaseManager:
            self.db = DatabaseManager(self.storage_file)
        else:
            self.db = None
    
    def _update_status(self, message: str) -> None:
        """Update status via callback.
        
        Args:
            message: Status message to report.
        """
        if self.status_callback is not None:
            self.status_callback(message)
    
    def load_lenses(self) -> List[Any]:
        """Load lenses and optical systems from SQLite database.
        
        Returns:
            List of Lens and OpticalSystem objects loaded from the database.
            Returns empty list if database is unavailable or contains invalid data.
        """
        if not self.db:
            logger.error("DatabaseManager not available")
            return []

        try:
            # Load from DB
            data = self.db.load_all()
            
            # Load lenses and systems
            items = []
            for i, item_data in enumerate(data):
                try:
                    if item_data.get('type') == 'OpticalSystem':
                        items.append(OpticalSystem.from_dict(item_data))
                    else:
                        items.append(Lens.from_dict(item_data))
                except Exception as e:
                    logger.warning("Failed to load item %d: %s", i, e)
            
            return items
            
        except Exception as e:
            logger.error("Failed to load lenses from database: %s", e)
            return []
    
    def save_lenses(self, items: List[Any], show_status: bool = True) -> bool:
        """Save all lenses and optical systems to SQLite database.
        
        Args:
            items: List of Lens/OpticalSystem objects to save.
            show_status: Whether to show a status message on success.
        
        Returns:
            True if save was successful, False otherwise.
        """
        if not self.db:
            logger.error("DatabaseManager not available")
            return False

        try:
            # Serialize and save items to DB
            for item in items:
                item_dict = item.to_dict()
                if isinstance(item, OpticalSystem) or item_dict.get('type') == 'OpticalSystem':
                    self.db.save_assembly(item_dict)
                else:
                    self.db.save_lens(item_dict)
            
            # We might want to implement a sync mechanism if we need to remove items 
            # that are no longer in the list. But the current UI usually manages 
            # adding/updating. Deleting is handled separately? 
            # Let's check how deletion is handled in main_window.py.
            
            if show_status:
                self._update_status(f"Saved {len(items)} item(s) to database")
            return True
            
        except Exception as e:
            self._update_status(f"Error: Failed to save lenses: {e}")
            logger.error("Failed to save lenses: %s", e)
            return False


def load_lenses(storage_file: str = "openlens.db") -> List[Any]:
    """Convenience function to load lenses and systems from a database.
    
    Args:
        storage_file: Path to the database file.
    
    Returns:
        List of Lens/OpticalSystem objects.
    """
    storage = LensStorage(storage_file)
    return storage.load_lenses()


def save_lenses(
    items: List[Any],
    storage_file: str = "openlens.db",
    status_callback: Optional[Callable[[str], None]] = None
) -> bool:
    """Convenience function to save lenses and systems to a database.
    
    Args:
        items: List of Lens/OpticalSystem objects to save.
        storage_file: Path to the database file.
        status_callback: Optional callback for status messages.
    
    Returns:
        True if save was successful, False otherwise.
    """
    storage = LensStorage(storage_file, status_callback)
    return storage.save_lenses(items)

