"""Dialog for browsing read-only lens presets and creating copies."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from ...preset_library import LensPreset, get_preset_library


def _fmt(value: Optional[float], suffix: str = "") -> str:
    if value is None:
        return "N/A"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "N/A"
    if v != v or abs(v) == float("inf"):
        return "N/A"
    text = f"{v:.6g}"
    return f"{text}{suffix}" if suffix else text


class PresetBrowserDialog(QDialog):
    """Browse preset lenses and instantiate an independent copy."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New from Preset")
        self.resize(720, 480)
        self._library = get_preset_library()
        self._presets: list[LensPreset] = []
        self._selected: Optional[LensPreset] = None
        self._build_ui()
        self._refresh_list()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        filters = QHBoxLayout()
        filters.addWidget(QLabel("Category:"))
        self._category = QComboBox()
        self._category.addItem("All categories")
        for name in self._library.list_categories():
            self._category.addItem(name)
        self._category.currentTextChanged.connect(self._refresh_list)
        filters.addWidget(self._category)
        filters.addWidget(QLabel("Search:"))
        self._search = QLineEdit()
        self._search.setPlaceholderText("Name or description")
        self._search.textChanged.connect(self._refresh_list)
        filters.addWidget(self._search, 1)
        layout.addLayout(filters)

        body = QHBoxLayout()
        self._list = QListWidget()
        self._list.currentItemChanged.connect(self._on_selection_changed)
        body.addWidget(self._list, 1)

        self._details = QPlainTextEdit()
        self._details.setReadOnly(True)
        self._details.setPlaceholderText("Select a preset to see its summary.")
        body.addWidget(self._details, 1)
        layout.addLayout(body, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        self._create_btn = buttons.addButton("Create", QDialogButtonBox.ButtonRole.AcceptRole)
        self._create_btn.setEnabled(False)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _refresh_list(self) -> None:
        query = self._search.text().strip().lower()
        category = self._category.currentText()
        presets = self._library.list_presets(None if category == "All categories" else category)
        if query:
            presets = [
                p for p in presets if query in p.name.lower() or query in p.description.lower()
            ]
        self._presets = presets

        current_name = self._selected.name if self._selected else None
        self._list.blockSignals(True)
        self._list.clear()
        selected_item = None
        for preset in self._presets:
            item = QListWidgetItem(preset.name)
            item.setData(Qt.ItemDataRole.UserRole, preset.name)
            self._list.addItem(item)
            if preset.name == current_name:
                selected_item = item
        self._list.blockSignals(False)

        if selected_item is not None:
            self._list.setCurrentItem(selected_item)
        elif self._presets:
            self._list.setCurrentRow(0)
        else:
            self._selected = None
            self._details.setPlainText("No presets match the current filter.")
            self._create_btn.setEnabled(False)

    def _on_selection_changed(
        self, current: Optional[QListWidgetItem], _previous: Optional[QListWidgetItem]
    ) -> None:
        if current is None:
            self._selected = None
            self._details.clear()
            self._create_btn.setEnabled(False)
            return
        name = current.data(Qt.ItemDataRole.UserRole)
        preset = self._library.get_preset(str(name)) if name is not None else None
        self._selected = preset
        self._create_btn.setEnabled(preset is not None)
        self._details.setPlainText(self._format_preset(preset) if preset else "")

    def _format_preset(self, preset: LensPreset) -> str:
        lens = preset.lens
        focal = None
        try:
            focal = lens.calculate_focal_length()
        except Exception:
            focal = None
        lines = [
            f"Name: {preset.name}",
            f"Category: {preset.category}",
            f"Description: {preset.description}",
            f"Manufacturer: {preset.manufacturer or 'N/A'}",
            f"Part number: {preset.part_number or 'N/A'}",
            f"Typical use: {preset.typical_use or 'N/A'}",
            "",
            "Optical summary",
            f"Focal length: {_fmt(focal, ' mm')}",
            f"Diameter: {_fmt(getattr(lens, 'diameter', None), ' mm')}",
            f"Material: {getattr(lens, 'material', 'N/A')}",
        ]
        return "\n".join(lines)

    def selected_copy(self):
        """Return an independent copy of the selected preset lens, or None."""
        if self._selected is None:
            return None
        return self._library.get_lens_copy(self._selected.name)
