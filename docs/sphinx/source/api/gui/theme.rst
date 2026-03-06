Theme Manager
=============

.. automodule:: src.gui.theme
   :members:
   :undoc-members:
   :show-inheritance:

Overview
--------

The ThemeManager class handles application theming and provides consistent colors
across the GUI.

Color Definitions
-----------------

The module defines standard colors used throughout the application:

.. code-block:: python

    COLORS = {
        'primary': '#2196F3',
        'secondary': '#757575',
        'success': '#4CAF50',
        'warning': '#FF9800',
        'error': '#F44336',
        'background': '#FFFFFF',
        'surface': '#F5F5F5',
        'text': '#212121',
        'text_secondary': '#757575',
    }

Example Usage
-------------

.. code-block:: python

    from src.gui.theme import ThemeManager, COLORS

    # Access color definitions
    primary_color = COLORS['primary']

    # Use theme manager
    theme = ThemeManager()
    theme.apply_theme(widget)
