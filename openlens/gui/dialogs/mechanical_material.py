"""Dialog for managing user-defined casing materials."""

import logging
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...mechanical_materials import MechanicalMaterialCatalog

logger = logging.getLogger(__name__)


class MechanicalMaterialDialog(QDialog):
    """Add and remove custom mechanical materials.

    Args:
        parent: Optional parent widget.
        catalog: Catalog to edit. None uses the process-wide catalog.
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        catalog: Optional[MechanicalMaterialCatalog] = None,
    ) -> None:
        super().__init__(parent)
        if catalog is None:
            from ...mechanical_materials import get_mechanical_material_catalog

            catalog = get_mechanical_material_catalog()
        self._catalog = catalog
        self.added_material: Optional[str] = None
        self.setWindowTitle("Manage Casing Materials")
        self.setMinimumWidth(420)
        self._build_ui()
        self._refresh()

    def _build_ui(self) -> None:
        """Build the custom-material list and add/remove controls."""
        layout = QVBoxLayout(self)

        note = QLabel(
            "Custom casing materials are shared by every assembly and saved in "
            "the OpenLens user data directory."
        )
        note.setWordWrap(True)
        layout.addWidget(note)

        self._custom_list = QListWidget()
        self._custom_list.setToolTip("Custom materials. Select one to remove it.")
        layout.addWidget(self._custom_list)

        add_group = QGroupBox("Add a material")
        form = QFormLayout(add_group)

        self._name_input = QLineEdit()
        self._name_input.setPlaceholderText("e.g. Invar")
        form.addRow("Name:", self._name_input)

        self._cte_input = QDoubleSpinBox()
        self._cte_input.setRange(0.0, 1.0e-3)
        self._cte_input.setDecimals(9)
        self._cte_input.setSingleStep(1.0e-6)
        self._cte_input.setValue(1.2e-6)
        self._cte_input.setToolTip("Linear coefficient of thermal expansion (1/K)")
        form.addRow("CTE (1/K):", self._cte_input)

        self._density_input = QDoubleSpinBox()
        self._density_input.setRange(0.0, 30.0)
        self._density_input.setDecimals(3)
        self._density_input.setSingleStep(0.1)
        self._density_input.setValue(8.0)
        self._density_input.setSuffix(" g/cm³")
        form.addRow("Density:", self._density_input)

        self._opaque_input = QCheckBox("Opaque inner wall")
        self._opaque_input.setChecked(True)
        form.addRow(self._opaque_input)
        layout.addWidget(add_group)

        buttons = QHBoxLayout()
        self._add_button = QPushButton("Add Material")
        self._add_button.clicked.connect(self._on_add)
        buttons.addWidget(self._add_button)

        self._remove_button = QPushButton("Remove Selected")
        self._remove_button.clicked.connect(self._on_remove)
        buttons.addWidget(self._remove_button)
        buttons.addStretch()
        layout.addLayout(buttons)

        close_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close_box.rejected.connect(self.reject)
        layout.addWidget(close_box)

    def _refresh(self) -> None:
        """Repopulate the custom-material list from the catalog."""
        self._custom_list.clear()
        for name, spec in self._catalog.get_available_materials().items():
            if not spec.get("custom"):
                continue
            self._custom_list.addItem(
                f"{name} — CTE {spec['cte']:.3e} 1/K, {spec['density']:.2f} g/cm³"
            )
            item = self._custom_list.item(self._custom_list.count() - 1)
            item.setData(Qt.ItemDataRole.UserRole, name)
        self._remove_button.setEnabled(self._custom_list.count() > 0)

    def _on_add(self, _checked: bool = False) -> None:
        """Add the entered material and persist it immediately."""
        name = self._name_input.text().strip()
        try:
            self._catalog.add_custom_material(
                name,
                self._cte_input.value(),
                self._density_input.value(),
                self._opaque_input.isChecked(),
            )
            self._catalog.save_custom_materials()
        except (OSError, ValueError) as exc:
            logger.warning("Could not add custom material: %s", exc)
            QMessageBox.warning(self, "Material not added", str(exc))
            return

        self.added_material = name
        self._name_input.clear()
        self._refresh()

    def _on_remove(self, _checked: bool = False) -> None:
        """Remove the selected custom material and persist the change."""
        item = self._custom_list.currentItem()
        if item is None:
            return
        name = item.data(Qt.ItemDataRole.UserRole)
        if not self._catalog.remove_custom_material(name):
            return
        try:
            self._catalog.save_custom_materials()
        except OSError as exc:
            logger.warning("Could not save custom materials: %s", exc)
            QMessageBox.warning(self, "Material catalog not saved", str(exc))
        self._refresh()
