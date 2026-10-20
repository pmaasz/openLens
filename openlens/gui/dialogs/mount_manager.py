"""Dialog for managing user-defined lens mounts."""

import logging
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
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

from ...mounts import MountCatalog

logger = logging.getLogger(__name__)


class MountManagerDialog(QDialog):
    """Add and remove custom mounts stored beside the material catalog.

    Args:
        parent: Optional parent widget.
        catalog: Mount catalog to edit. None creates one using the default
            user configuration path.
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        catalog: Optional[MountCatalog] = None,
    ) -> None:
        super().__init__(parent)
        self._catalog = catalog or MountCatalog()
        self.setWindowTitle("Manage Mounts")
        self.setMinimumWidth(420)
        self._build_ui()
        self._refresh()

    def _build_ui(self) -> None:
        """Build the custom-mount list and add/remove controls."""
        layout = QVBoxLayout(self)

        note = QLabel(
            "Custom mounts are shared by every lens and saved in the OpenLens "
            "user data directory."
        )
        note.setWordWrap(True)
        layout.addWidget(note)

        self._custom_list = QListWidget()
        self._custom_list.setToolTip("Custom mounts. Select one to remove it.")
        layout.addWidget(self._custom_list)

        add_group = QGroupBox("Add a mount")
        form = QFormLayout(add_group)

        self._name_input = QLineEdit()
        self._name_input.setPlaceholderText("e.g. Lab M42 adapter")
        form.addRow("Name:", self._name_input)

        self._flange_input = QDoubleSpinBox()
        self._flange_input.setRange(0.01, 500.0)
        self._flange_input.setDecimals(3)
        self._flange_input.setSingleStep(0.1)
        self._flange_input.setSuffix(" mm")
        self._flange_input.setValue(17.526)
        self._flange_input.setToolTip("Distance from the mounting face to the sensor plane")
        form.addRow("Flange distance:", self._flange_input)
        layout.addWidget(add_group)

        buttons = QHBoxLayout()
        self._add_button = QPushButton("Add Mount")
        self._add_button.clicked.connect(self._on_add)
        buttons.addWidget(self._add_button)

        self._remove_button = QPushButton("Remove Selected")
        self._remove_button.clicked.connect(self._on_remove)
        buttons.addWidget(self._remove_button)
        buttons.addStretch()
        layout.addLayout(buttons)

        close_box = QDialogButtonBox(QDialogButtonBox.Close)
        close_box.rejected.connect(self.reject)
        layout.addWidget(close_box)

    def _refresh(self) -> None:
        """Repopulate the custom-mount list from the catalog."""
        self._custom_list.clear()
        mounts = self._catalog.get_available_mounts()
        for name, spec in mounts.items():
            if not spec.get("custom"):
                continue
            item_text = f"{name} — {spec['flange_distance']:.3f} mm"
            self._custom_list.addItem(item_text)
            item = self._custom_list.item(self._custom_list.count() - 1)
            item.setData(Qt.UserRole, name)
        self._remove_button.setEnabled(self._custom_list.count() > 0)

    def _on_add(self, _checked: bool = False) -> None:
        """Add the entered mount and persist it immediately."""
        try:
            self._catalog.add_custom_mount(self._name_input.text(), self._flange_input.value())
            self._catalog.save_custom_mounts()
        except (OSError, ValueError) as exc:
            logger.warning("Could not add custom mount: %s", exc)
            QMessageBox.warning(self, "Mount not added", str(exc))
            return

        self._name_input.clear()
        self._refresh()

    def _on_remove(self, _checked: bool = False) -> None:
        """Remove the selected custom mount and persist the change."""
        item = self._custom_list.currentItem()
        if item is None:
            return
        name = item.data(Qt.UserRole)
        try:
            removed = self._catalog.remove_custom_mount(name)
            if removed:
                self._catalog.save_custom_mounts()
        except OSError as exc:
            logger.warning("Could not remove custom mount %r: %s", name, exc)
            QMessageBox.warning(self, "Mount not removed", str(exc))
            return
        if removed:
            self._refresh()
