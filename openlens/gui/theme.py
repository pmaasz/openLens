"""
Qt stylesheet generation for OpenLens.

All QSS is generated from the COLOR_* palette in constants.py, so the
application has a single source of truth for colors. Two structural
templates exist (dark and light) because the themes style different
widget sets; within a template every color comes from the palette.
"""

from ..constants import (
    COLOR_ACCENT,
    COLOR_BG_DARK,
    COLOR_BG_LIGHT,
    COLOR_BG_MEDIUM,
    COLOR_BORDER_DARK,
    COLOR_BORDER_LIGHT,
    COLOR_CODE_BG_DARK,
    COLOR_FG,
    COLOR_FG_DIM,
    COLOR_HOVER_LIGHT,
    COLOR_PLOT_AXIS_DARK,
    COLOR_PLOT_AXIS_LIGHT,
    COLOR_PLOT_GRID_DARK,
    COLOR_PLOT_GRID_LIGHT,
    COLOR_SURFACE_ALT_LIGHT,
    COLOR_SURFACE_LIGHT,
    COLOR_TEXT_DIM_LIGHT,
    COLOR_TEXT_ON_ACCENT,
    COLOR_TEXT_ON_LIGHT,
    COLOR_WINDOW_LIGHT,
)

DARK = "dark"
LIGHT = "light"

# Shared palette values per theme. The QSS templates consume them through
# @@name@@ tokens; the custom-painted views and the plots read them through
# get_palette(), so one lookup keeps every surface in step with the toggle.
_PALETTES = {
    DARK: {
        "window": COLOR_BG_DARK,
        "surface": COLOR_BG_MEDIUM,
        "hover": COLOR_BG_LIGHT,
        "text": COLOR_FG,
        "input_bg": COLOR_BG_MEDIUM,
        "border": COLOR_BORDER_DARK,
        "accent": COLOR_ACCENT,
        "accent_text": COLOR_TEXT_ON_ACCENT,
        "text_dim": COLOR_FG_DIM,
        "code_bg": COLOR_CODE_BG_DARK,
        "plot_bg": COLOR_BG_DARK,
        "plot_text": COLOR_FG,
        "plot_axis": COLOR_PLOT_AXIS_DARK,
        "plot_grid": COLOR_PLOT_GRID_DARK,
        "plot_spine": COLOR_BORDER_DARK,
        "canvas_border": COLOR_FG_DIM,
    },
    LIGHT: {
        "window": COLOR_WINDOW_LIGHT,
        "surface": COLOR_SURFACE_ALT_LIGHT,
        "hover": COLOR_HOVER_LIGHT,
        "text": COLOR_TEXT_ON_LIGHT,
        "input_bg": COLOR_SURFACE_LIGHT,
        "border": COLOR_BORDER_LIGHT,
        "accent": COLOR_ACCENT,
        "accent_text": COLOR_TEXT_ON_ACCENT,
        "text_dim": COLOR_TEXT_DIM_LIGHT,
        "code_bg": COLOR_SURFACE_LIGHT,
        "plot_bg": COLOR_SURFACE_LIGHT,
        "plot_text": COLOR_TEXT_ON_LIGHT,
        "plot_axis": COLOR_PLOT_AXIS_LIGHT,
        "plot_grid": COLOR_PLOT_GRID_LIGHT,
        "plot_spine": COLOR_BORDER_LIGHT,
        "canvas_border": COLOR_BORDER_LIGHT,
    },
}


def get_palette(theme: str = DARK) -> dict:
    """Return a copy of the colour palette for the given theme.

    Args:
        theme: Either "dark" or "light".

    Returns:
        A new dict; mutating it does not alter the shared palette or the
        generated stylesheets.
    """
    return dict(_PALETTES[theme])


def _fill(template: str, palette: dict) -> str:
    """Substitute @@name@@ tokens with palette values."""
    out = template
    for key, value in palette.items():
        out = out.replace("@@%s@@" % key, value)
    return out


# Full application sheet for the dark theme (superset of widget styling)
_APP_QSS_DARK = """
QMainWindow {
    background-color: @@window@@;
}
QWidget {
    background-color: @@window@@;
    color: @@text@@;
}
QGroupBox {
    color: @@text@@;
    border: 1px solid @@border@@;
    border-radius: 5px;
    margin-top: 10px;
    font-weight: bold;
    padding-top: 10px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
}
QDoubleSpinBox, QSpinBox, QLineEdit, QTextEdit, QTableWidget {
    background-color: @@surface@@;
    color: @@text@@;
    border: 1px solid @@border@@;
    padding: 3px;
}
QHeaderView::section {
    background-color: @@surface@@;
    color: @@text@@;
    padding: 4px;
    border: 1px solid @@border@@;
}
QTableCornerButton::section {
    background-color: @@surface@@;
    border: 1px solid @@border@@;
}
QPushButton {
    background-color: @@surface@@;
    color: @@text@@;
    border: 1px solid @@border@@;
    padding: 5px 15px;
}
QPushButton:hover {
    background-color: @@hover@@;
}
QPushButton:pressed {
    background-color: @@accent@@;
}
QListWidget {
    background-color: @@surface@@;
    color: @@text@@;
    border: 1px solid @@border@@;
}
QListWidget::item:selected {
    background-color: @@accent@@;
}
QLabel {
    color: @@text@@;
}
QTabWidget::pane {
    border: 1px solid @@border@@;
}
QTabBar::tab {
    background-color: @@surface@@;
    color: @@text@@;
    padding: 5px 10px;
}
QTabBar::tab:selected {
    background-color: @@accent@@;
}
QStatusBar {
    background-color: @@surface@@;
    color: @@text@@;
    border-top: 1px solid @@border@@;
}
QProgressBar {
    border: 1px solid @@border@@;
    border-radius: 2px;
    text-align: center;
    background-color: @@surface@@;
}
QProgressBar::chunk {
    background-color: @@accent@@;
}
"""

# Full application sheet for the light theme
_APP_QSS_LIGHT = """
QMainWindow {
    background-color: @@window@@;
}
QWidget {
    background-color: @@window@@;
    color: @@text@@;
}
QGroupBox {
    color: @@text@@;
    border: 1px solid @@border@@;
    border-radius: 5px;
    margin-top: 10px;
    font-weight: bold;
    padding-top: 10px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
}
QDoubleSpinBox, QSpinBox {
    background-color: @@input_bg@@;
    color: @@text@@;
    border: 1px solid @@border@@;
    padding: 3px;
}
QPushButton {
    background-color: @@surface@@;
    color: @@text@@;
    border: 1px solid @@border@@;
    padding: 5px 15px;
}
QPushButton:hover {
    background-color: @@hover@@;
}
QPushButton:pressed {
    background-color: @@accent@@;
    color: @@accent_text@@;
}
QListWidget {
    background-color: @@input_bg@@;
    color: @@text@@;
    border: 1px solid @@border@@;
}
QListWidget::item:selected {
    background-color: @@accent@@;
    color: @@accent_text@@;
}
QLabel {
    color: @@text@@;
}
QTabWidget::pane {
    border: 1px solid @@border@@;
}
QTabBar::tab {
    background-color: @@surface@@;
    color: @@text@@;
    padding: 5px 10px;
}
QTabBar::tab:selected {
    background-color: @@accent@@;
    color: @@accent_text@@;
}
QStatusBar {
    background-color: @@surface@@;
    color: @@text@@;
}
"""

_APP_TEMPLATES = {DARK: _APP_QSS_DARK, LIGHT: _APP_QSS_LIGHT}

_STATUS_BAR_QSS = """
QStatusBar {
    background-color: @@surface@@;
    color: @@text@@;
    border-top: 1px solid @@border@@;
}
"""

_TAB_WIDGET_QSS = """
QTabWidget::pane {
    border: 1px solid @@border@@;
    background-color: @@window@@;
}
QTabBar::tab {
    background-color: @@surface@@;
    color: @@text@@;
    padding: 8px 16px;
    border: 1px solid @@border@@;
}
QTabBar::tab:selected {
    background-color: @@accent@@;
}
"""

_MENUBAR_QSS = """
QMenuBar {
    background-color: @@surface@@;
    color: @@text@@;
}
QMenuBar::item:selected {
    background-color: @@accent@@;
}
QMenu {
    background-color: @@surface@@;
    color: @@text@@;
    border: 1px solid @@border@@;
}
QMenu::item:selected {
    background-color: @@accent@@;
}
"""

_MONOSPACE_QSS = """
background-color: @@code_bg@@;
color: @@text@@;
font-family: Courier;
font-size: 10px;
"""


def get_app_stylesheet(theme: str = DARK) -> str:
    """Return the full application stylesheet for the given theme.

    Args:
        theme: Either "dark" or "light".

    Returns:
        The complete QSS string to pass to QApplication.setStyleSheet().
    """
    return _fill(_APP_TEMPLATES[theme], _PALETTES[theme])


def get_status_bar_qss(theme: str = DARK) -> str:
    """Return the status-bar stylesheet for the given theme."""
    return _fill(_STATUS_BAR_QSS, _PALETTES[theme])


def get_tab_widget_qss(theme: str = DARK) -> str:
    """Return the main editor tab-widget stylesheet for the given theme."""
    return _fill(_TAB_WIDGET_QSS, _PALETTES[theme])


def get_menubar_qss(theme: str = DARK) -> str:
    """Return the menu bar / context menu stylesheet for the given theme."""
    return _fill(_MENUBAR_QSS, _PALETTES[theme])


def get_monospace_qss(theme: str = DARK) -> str:
    """Return the monospace text/table stylesheet for the given theme.

    The results panes (optimization, tolerancing, performance) and the
    tolerancing table share this one look; it used to be copied into each
    tab with a hard-coded dark background.
    """
    return _fill(_MONOSPACE_QSS, _PALETTES[theme])
