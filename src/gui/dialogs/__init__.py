"""
OpenLens PySide6 Dialogs
"""

from .startup import StartupDialog

# AnalysisPlotDialog and image_sim need matplotlib, which AGENTS.md classes
# as optional. Importing them eagerly at module scope meant a plain
# `pip install PySide6` died with a raw ModuleNotFoundError during startup -
# no editor, no message - even though the lens editor, assembly builder and
# the QPainter-based visualisations need no matplotlib at all.
#
# These names resolve to None when matplotlib is missing. Callers should go
# through require_analysis_plot_dialog(), which raises a helpful error the
# GUI can turn into a message box.
ANALYSIS_PLOTS_AVAILABLE = True
try:
    from .analysis_plots import AnalysisPlotDialog
except ImportError as _exc:  # pragma: no cover - depends on the environment
    ANALYSIS_PLOTS_AVAILABLE = False
    AnalysisPlotDialog = None  # type: ignore[assignment]
    _ANALYSIS_PLOTS_IMPORT_ERROR = _exc
else:
    _ANALYSIS_PLOTS_IMPORT_ERROR = None  # type: ignore[assignment]


def require_analysis_plot_dialog():
    """Return AnalysisPlotDialog, or raise ImportError explaining the need.

    Import matplotlib rather than returning None, so a caller that forgets
    this helper still fails loudly instead of calling None().

    Raises:
        ImportError: If matplotlib (or PySide6's Qt backend) is unavailable.
    """
    if AnalysisPlotDialog is not None:
        return AnalysisPlotDialog
    raise ImportError(
        "The analysis plots require 'matplotlib'. Install it with 'pip install matplotlib'."
    ) from _ANALYSIS_PLOTS_IMPORT_ERROR


__all__ = [
    "StartupDialog",
    "AnalysisPlotDialog",
    "ANALYSIS_PLOTS_AVAILABLE",
    "require_analysis_plot_dialog",
]
