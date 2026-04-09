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


class LensStorage:
    """Handles lens data persistence to JSON files.
    
    This class provides methods to load and save lens data with proper
    validation and error handling.
    
    Args:
        storage_file: Path to the JSON storage file.
        status_callback: Optional callback function to report status messages.
    
    Example:
        >>> storage = LensStorage("lenses.json")
        >>> lenses = storage.load_lenses()
        >>> storage.save_lenses(lenses)
    """
    
    def __init__(
        self,
        storage_file: str = "lenses.json",
        status_callback: Optional[Callable[[str], None]] = None
    ) -> None:
        """Initialize the storage handler.
        
        Args:
            storage_file: Path to the JSON storage file.
            status_callback: Optional callback for status messages.
        """
        self.storage_file = storage_file
        self.status_callback = status_callback if status_callback is not None else None
    
    def _update_status(self, message: str) -> None:
        """Update status via callback.
        
        Args:
            message: Status message to report.
        """
        if self.status_callback is not None:
            self.status_callback(message)
    
    def load_lenses(self) -> List[Any]:
        """Load lenses and optical systems from JSON storage file with path validation.
        
        Returns:
            List of Lens and OpticalSystem objects loaded from the file.
            Returns empty list if file doesn't exist or contains invalid data.
        """
        try:
            # Validate file path
            file_path = validate_file_path(
                self.storage_file,
                must_exist=True,
                create_parent=False
            )
            
            # Read and parse JSON
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Validate JSON structure
            if not isinstance(data, list):
                logger.warning("Storage file contains invalid data structure")
                return []
            
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
            
        except ValidationError:
            # File doesn't exist - return empty list
            return []
        except json.JSONDecodeError as e:
            logger.error("Invalid JSON in storage file: %s", e)
            return []
        except Exception as e:
            logger.error("Failed to load lenses: %s", e)
            return []
    
    def save_lenses(self, items: List[Any]) -> bool:
        """Save all lenses and optical systems to JSON storage file.
        
        Args:
            items: List of Lens/OpticalSystem objects to save.
        
        Returns:
            True if save was successful, False otherwise.
        """
        try:
            # Validate and prepare file path
            file_path = validate_json_file_path(
                self.storage_file,
                must_exist=False
            )
            
            # Ensure parent directory exists and is writable
            parent_dir = file_path.parent
            if not parent_dir.exists():
                parent_dir.mkdir(parents=True, exist_ok=True)
            
            if not os.access(parent_dir, os.W_OK):
                self._update_status(f"Error: Directory is not writable: {parent_dir}")
                return False
            
            # Serialize items to JSON
            data = [item.to_dict() for item in items]
            
            # Write to file with atomic operation (write to temp, then rename)
            temp_path = file_path.with_suffix('.tmp')
            try:
                with open(temp_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                
                # Atomic rename
                temp_path.replace(file_path)
                
                # Don't show status message - let the caller decide what to display
                return True
                
            finally:
                # Clean up temp file if it still exists
                if temp_path.exists():
                    temp_path.unlink()
            
        except ValidationError as e:
            self._update_status(f"Error: Invalid file path: {e}")
            return False
        except PermissionError as e:
            self._update_status(f"Error: Permission denied: {e}")
            return False
        except OSError as e:
            self._update_status(f"Error: OS error when saving: {e}")
            return False
        except Exception as e:
            self._update_status(f"Error: Failed to save lenses: {e}")
            return False


def load_lenses(storage_file: str = "lenses.json") -> List[Any]:
    """Convenience function to load lenses and systems from a file.
    
    Args:
        storage_file: Path to the JSON storage file.
    
    Returns:
        List of Lens/OpticalSystem objects.
    """
    storage = LensStorage(storage_file)
    return storage.load_lenses()


def save_lenses(
    items: List[Any],
    storage_file: str = "lenses.json",
    status_callback: Optional[Callable[[str], None]] = None
) -> bool:
    """Convenience function to save lenses and systems to a file.
    
    Args:
        items: List of Lens/OpticalSystem objects to save.
        storage_file: Path to the JSON storage file.
        status_callback: Optional callback for status messages.
    
    Returns:
        True if save was successful, False otherwise.
    """
    storage = LensStorage(storage_file, status_callback)
    return storage.save_lenses(items)
