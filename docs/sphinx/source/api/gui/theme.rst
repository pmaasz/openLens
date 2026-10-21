Theme
=====

.. automodule:: openlens.gui.theme
   :members:
   :undoc-members:
   :show-inheritance:

Overview
--------

``openlens.gui.theme`` defines the dark and light palettes and the stylesheet
templates used by the desktop application. A palette is a plain dictionary;
the ``get_*_qss`` helpers fill the templates for a selected theme.

Example
-------

.. code-block:: python

    from openlens.gui.theme import DARK, LIGHT, get_app_stylesheet, get_palette

    palette = get_palette(DARK)
    stylesheet = get_app_stylesheet(LIGHT)
    application.setStyleSheet(stylesheet)
