#!/usr/bin/env python3
"""
openlens - Main Entry Point
Launches the optical lens design application
"""

import logging
import os
import sys

# Add src to path so imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Import logging constants
try:
    from constants import (
        DEFAULT_LOG_LEVEL,
        DEFAULT_LOG_FORMAT,
        LOG_FORMAT_DEBUG,
        LOG_DATE_FORMAT,
        LOG_LEVEL_ENV_VAR
    )
except ImportError:
    # Fallback defaults if constants not available
    DEFAULT_LOG_LEVEL = "WARNING"
    DEFAULT_LOG_FORMAT = "%(levelname)s: %(message)s"
    LOG_FORMAT_DEBUG = "%(asctime)s - %(name)s:%(lineno)d - %(levelname)s - %(message)s"
    LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
    LOG_LEVEL_ENV_VAR = "OPENLENS_LOG_LEVEL"


def setup_logging() -> None:
    """
    Configure logging for the application.
    
    Log level can be controlled via the OPENLENS_LOG_LEVEL environment variable.
    Valid values: DEBUG, INFO, WARNING, ERROR, CRITICAL
    """
    # Get log level from environment variable, default to WARNING
    log_level_str = os.environ.get(LOG_LEVEL_ENV_VAR, DEFAULT_LOG_LEVEL)
    
    # Map string to logging level
    log_level = getattr(logging, log_level_str.upper(), logging.WARNING)
    
    # Use detailed format for DEBUG level
    if log_level == logging.DEBUG:
        log_format = LOG_FORMAT_DEBUG
    else:
        log_format = DEFAULT_LOG_FORMAT
    
    logging.basicConfig(
        level=log_level,
        format=log_format,
        datefmt=LOG_DATE_FORMAT
    )
    
    # Log the configuration if in debug mode
    logger = logging.getLogger(__name__)
    logger.debug("Logging configured with level: %s", log_level_str)


def main() -> None:
    """Main entry point for the OpenLens application."""
    setup_logging()
    
    from lens_editor_gui import main as gui_main
    gui_main()


if __name__ == "__main__":
    main()
