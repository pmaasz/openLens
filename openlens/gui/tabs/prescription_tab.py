"""Read-only prescription table with CSV export."""

import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from ...prescription import COLUMNS, build_prescription_rows, rows_to_csv
from .base_tab import BaseTab

logger = logging.getLogger(__name__)

_HEADERS = [
    "Surface",
    "Radius",
    "Conic / Parabolic",
    "Thickness / Air Gap",
    "Material / Glass",
    "Clear Semi-Diameter",
    "Mechanical Semi-Diameter",
    "Coating",
    "Stop",
]


class PrescriptionTab(BaseTab):
    """Show the current lens or assembly as a surface prescription table."""

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        title = QLabel("Prescription")
        title.setStyleSheet("font-weight: bold; font-size: 13px;")
        layout.addWidget(title)

        self._hint = QLabel("Read-only. Values update when the design changes.")
        layout.addWidget(self._hint)

        self._table = QTableWidget(0, len(COLUMNS))
        self._table.setHorizontalHeaderLabels(_HEADERS)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(True)
        layout.addWidget(self._table, 1)

        buttons = QHBoxLayout()
        copy_btn = QPushButton("Copy as CSV")
        copy_btn.clicked.connect(self._on_copy_csv)
        export_btn = QPushButton("Export CSV")
        export_btn.clicked.connect(self._on_export_csv)
        buttons.addWidget(copy_btn)
        buttons.addWidget(export_btn)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        self._rows: list[dict[str, str]] = []

    def refresh(self) -> None:
        target = self._active_target()
        self._rows = build_prescription_rows(target)
        self._table.setRowCount(len(self._rows))
        for row_idx, row in enumerate(self._rows):
            for col_idx, key in enumerate(COLUMNS):
                item = QTableWidgetItem(str(row.get(key, "")))
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self._table.setItem(row_idx, col_idx, item)
        if not self._rows:
            self._table.setRowCount(0)

    def _csv_text(self) -> str:
        return rows_to_csv(self._rows)

    def _on_copy_csv(self) -> None:
        QApplication.clipboard().setText(self._csv_text())
        if self._parent and hasattr(self._parent, "_update_status"):
            self._parent._update_status("Prescription copied as CSV")

    def _on_export_csv(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Prescription CSV", "prescription.csv", "CSV files (*.csv)"
        )
        if not path:
            return
        if not path.lower().endswith(".csv"):
            path += ".csv"
        try:
            with open(path, "w", encoding="utf-8", newline="") as fh:
                fh.write(self._csv_text())
        except OSError as e:
            logger.error("Prescription CSV export failed: %s", e)
            QMessageBox.critical(self, "Export Error", f"Could not write {path}: {e}")
            return
        if self._parent and hasattr(self._parent, "_update_status"):
            self._parent._update_status(f"Prescription exported to {path}")
