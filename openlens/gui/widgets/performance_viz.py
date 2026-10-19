"""
OpenLens PySide6 Performance Visualization Widget
Specialized visualization for performance metrics (MTF, PSF, etc.)
"""

from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QColor
from typing import Any, Dict, Optional, TYPE_CHECKING

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
        painter.fillRect(self.rect(), QColor("#1e1e1e"))

        if not self._lens:
            painter.setPen(QColor("#888888"))
            painter.drawText(self.rect(), Qt.AlignCenter, "No metrics available")
            return

        # Just a placeholder for now - actual metrics are in AnalysisPlotDialog
        painter.setPen(QColor("#4fc3f7"))
        painter.drawText(20, 30, f"Performance: {self._lens.name}")
        if self._metrics:
            painter.drawText(20, 50, f"RMS Spot: {self._metrics.get('rms_spot', 0):.4f}")
