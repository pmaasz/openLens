"""Wizard that creates a lens or doublet from a target specification."""

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from ...constants import WAVELENGTH_GREEN
from ...lens import Lens
from ...optical_system import OpticalSystem
from ...target_design import (
    TargetDesignResult,
    design_doublet_from_target,
    design_singlet_from_target,
)


class TargetLensWizardDialog(QDialog):
    """Compute a starting design from targets and preview it before adding."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Lens from Target")
        self.setModal(True)
        self.resize(560, 520)
        self._result = TargetDesignResult()
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        form = QFormLayout()
        self._type = QComboBox()
        self._type.addItems(["Singlet", "Achromatic doublet"])
        self._type.currentIndexChanged.connect(self._on_type_changed)
        form.addRow("Design", self._type)

        self._efl = QDoubleSpinBox()
        self._efl.setRange(-100000.0, 100000.0)
        self._efl.setDecimals(3)
        self._efl.setValue(50.0)
        self._efl.setSuffix(" mm")
        form.addRow("Target focal length", self._efl)

        self._diameter_mode = QComboBox()
        self._diameter_mode.addItems(["Diameter", "f-number"])
        self._diameter_mode.currentIndexChanged.connect(self._on_diameter_mode_changed)
        self._diameter = QDoubleSpinBox()
        self._diameter.setRange(0.1, 100000.0)
        self._diameter.setDecimals(3)
        self._diameter.setValue(25.0)
        self._diameter.setSuffix(" mm")
        self._f_number = QDoubleSpinBox()
        self._f_number.setRange(0.1, 10000.0)
        self._f_number.setDecimals(3)
        self._f_number.setValue(2.0)
        self._f_number.setEnabled(False)
        size_row = QHBoxLayout()
        size_row.addWidget(self._diameter_mode)
        size_row.addWidget(self._diameter)
        size_row.addWidget(self._f_number)
        form.addRow("Aperture", size_row)

        self._sensor = QDoubleSpinBox()
        self._sensor.setRange(0.1, 10000.0)
        self._sensor.setDecimals(3)
        self._sensor.setValue(36.0)
        self._sensor.setSuffix(" mm")
        form.addRow("Sensor size", self._sensor)

        self._material = QComboBox()
        self._material.setEditable(True)
        self._material.addItems(self._material_choices())
        if self._material.findText("BK7") >= 0:
            self._material.setCurrentText("BK7")
        form.addRow("Material", self._material)

        self._flint = QComboBox()
        self._flint.setEditable(True)
        self._flint.addItems(self._material_choices())
        if self._flint.findText("SF11") >= 0:
            self._flint.setCurrentText("SF11")
        self._flint_label = QLabel("Flint material")
        form.addRow(self._flint_label, self._flint)

        self._wavelength = QDoubleSpinBox()
        self._wavelength.setRange(200.0, 2000.0)
        self._wavelength.setDecimals(1)
        self._wavelength.setValue(float(WAVELENGTH_GREEN))
        self._wavelength.setSuffix(" nm")
        form.addRow("Design wavelength", self._wavelength)

        layout.addLayout(form)

        design_btn = QPushButton("Design / Preview")
        design_btn.clicked.connect(self._on_design)
        layout.addWidget(design_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        self._preview = QPlainTextEdit()
        self._preview.setReadOnly(True)
        self._preview.setPlaceholderText(
            "Set targets and click Design / Preview. Nothing is added until you confirm."
        )
        layout.addWidget(self._preview, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        self._add_btn = buttons.addButton("Add to Library", QDialogButtonBox.ButtonRole.AcceptRole)
        self._add_btn.setEnabled(False)
        self._add_btn.clicked.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._on_type_changed()
        self._on_diameter_mode_changed()

    def _material_choices(self):
        try:
            from ...material_database import get_material_database

            names = get_material_database().list_materials()
            if names:
                return names
        except Exception:
            pass
        return ["BK7", "SF11", "F2", "N-BK7", "Fused Silica"]

    def _on_type_changed(self) -> None:
        doublet = self._type.currentIndex() == 1
        self._flint_label.setVisible(doublet)
        self._flint.setVisible(doublet)
        self._result = TargetDesignResult()
        self._add_btn.setEnabled(False)

    def _on_diameter_mode_changed(self) -> None:
        by_f = self._diameter_mode.currentIndex() == 1
        self._diameter.setEnabled(not by_f)
        self._f_number.setEnabled(by_f)

    def _effective_diameter(self) -> float:
        if self._diameter_mode.currentIndex() == 1:
            return abs(self._efl.value() / self._f_number.value())
        return self._diameter.value()

    def _on_design(self) -> None:
        efl = self._efl.value()
        diameter = self._effective_diameter()
        wavelength = self._wavelength.value()
        material = self._material.currentText().strip() or "BK7"
        if self._type.currentIndex() == 1:
            flint = self._flint.currentText().strip() or "SF11"
            self._result = design_doublet_from_target(
                focal_length_mm=efl,
                diameter_mm=diameter,
                crown_material=material,
                flint_material=flint,
                wavelength_nm=wavelength,
            )
        else:
            self._result = design_singlet_from_target(
                focal_length_mm=efl,
                diameter_mm=diameter,
                material=material,
                wavelength_nm=wavelength,
            )
        self._preview.setPlainText(self._format_result(self._result))
        self._add_btn.setEnabled(self._result.ok)

    def _format_result(self, result: TargetDesignResult) -> str:
        lines = []
        merit = result.merit or {}
        target_f = merit.get("target_focal_length_mm")
        achieved_f = merit.get("achieved_focal_length_mm")
        diameter = merit.get("diameter_mm", self._effective_diameter())
        fnum = merit.get("f_number")
        if target_f is not None:
            lines.append(f"Target focal length: {target_f:.3f} mm")
        if achieved_f is not None:
            lines.append(f"Achieved focal length: {achieved_f:.3f} mm")
        if diameter is not None:
            lines.append(f"Diameter: {diameter:.3f} mm")
        if fnum is not None:
            lines.append(f"f-number: f/{fnum:.3f}")
        edge = merit.get("edge_thickness_mm")
        if edge is not None:
            lines.append(f"Edge thickness: {edge:.3f} mm")
        sensor = self._sensor.value()
        if achieved_f and abs(achieved_f) > 0:
            import math

            fov = 2.0 * math.degrees(math.atan((sensor / 2.0) / abs(achieved_f)))
            lines.append(f"Approx. horizontal FOV ({sensor:.2f} mm sensor): {fov:.2f}°")
        if result.warnings:
            lines.append("")
            lines.append("Warnings:")
            for warning in result.warnings:
                lines.append(f"- {warning}")
        elif result.ok:
            lines.append("")
            lines.append("The starting design is feasible.")
        if not result.ok and not result.warnings:
            lines.append("No design could be produced for this target.")
        if result.ok and result.target is not None:
            target = result.target
            if isinstance(target, OpticalSystem):
                lines.append("")
                lines.append(f"Elements: {len(target.elements)}")
                for element in target.elements:
                    lens = element.lens
                    lines.append(
                        f"- {lens.name}: R1={_fmt(lens.radius_of_curvature_1)} mm, "
                        f"R2={_fmt(lens.radius_of_curvature_2)} mm, "
                        f"t={lens.thickness:.3f} mm, n={lens.refractive_index:.5f}"
                    )
            elif isinstance(target, Lens):
                lines.append("")
                lines.append(
                    f"R1={_fmt(target.radius_of_curvature_1)} mm, "
                    f"R2={_fmt(target.radius_of_curvature_2)} mm, "
                    f"t={target.thickness:.3f} mm, n={target.refractive_index:.5f}"
                )
        return "\n".join(lines) if lines else "No preview yet."

    def designed_target(self):
        """Return the previewed design, or None if nothing should be added."""
        return self._result.target if self._result.ok else None


def _fmt(value: float) -> str:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return str(value)
    if not (v == v) or abs(v) > 1e9:
        return "inf"
    return f"{v:.3f}"
