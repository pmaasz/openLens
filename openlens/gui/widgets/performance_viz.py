"""
OpenLens PySide6 Performance Visualization Widget
Specialized visualization for performance metrics (MTF, PSF, etc.)
"""

from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QColor
from typing import Any, Dict, Optional, TYPE_CHECKING

from ..theme import DARK, get_palette

if TYPE_CHECKING:
    from PySide6.QtGui import QPaintEvent

    from ...lens import Lens


class PerformanceVisualizationWidget(QWidget):
    """Specialized visualization for performance metrics (MTF, PSF, etc.)"""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialize the widget with no lens or metrics loaded.

        Args:
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self.setMinimumSize(400, 300)
        self._lens = None
        self._metrics = None
        self._theme = DARK
        self.set_theme(DARK)

    def set_theme(self, theme: str = DARK) -> None:
        """Repaint with *theme*'s canvas colours.

        Args:
            theme: "dark" or "light".
        """
        palette = get_palette(theme)
        self._theme = theme
        self._bg_color = QColor(palette["plot_bg"])
        self._accent_color = QColor(palette["accent"])
        self._dim_color = QColor(palette["text_dim"])
        self._text_color = QColor(palette["plot_text"])
        self.update()

    def update_lens(self, lens: "Lens") -> None:
        """Set the lens to report performance for and schedule a repaint.

        Args:
            lens: The lens model whose name is displayed.
        """
        self._lens = lens
        self.update()

    def update_metrics(self, metrics: Optional[Dict[str, Any]]) -> None:
        """Set the performance metrics to display and schedule a repaint.

        Args:
            metrics: Mapping of metric names to values (e.g.
                ``{'rms_spot': 0.012}``), or None to clear them.
        """
        self._metrics = metrics
        self.update()

    def paintEvent(self, event: "QPaintEvent") -> None:
        """Paint the placeholder performance summary."""
        painter = QPainter(self)
        painter.fillRect(self.rect(), self._bg_color)

        if not self._lens:
            painter.setPen(self._dim_color)
            painter.drawText(self.rect(), Qt.AlignCenter, "No metrics available")
            return

        # Just a placeholder for now - actual metrics are in AnalysisPlotDialog
        painter.setPen(self._accent_color)
        painter.drawText(20, 30, f"Performance: {self._lens.name}")
        if self._metrics:
            painter.drawText(20, 50, f"RMS Spot: {self._metrics.get('rms_spot', 0):.4f}")
