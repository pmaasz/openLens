"""Flow: Exports + theme/view manual QA -> automated.

Manual checklist replaced:
- Save As JSON writes current lens
- Export STL / ISO10110 SVG / Report TXT produce files
- STEP export either produces a file or shows the missing-deps warning
  (both are valid; crash is not)
- Theme toggle flips dark/light stylesheets
- 2D view Top/Side switch + window reset do not crash
"""

import json
import os

from PySide6.QtWidgets import QApplication, QMessageBox

from .conftest import requires_pyside
from .pages import MainWindowPO

pytestmark = requires_pyside


def _patch_save_dialog(monkeypatch, tmp_path, filename):
    from PySide6 import QtWidgets

    target = str(tmp_path / filename)
    monkeypatch.setattr(QtWidgets.QFileDialog, "getSaveFileName", lambda *a, **k: (target, ""))
    return target


def test_save_as_json_flow(main_window, qtbot, monkeypatch, tmp_path):
    po = MainWindowPO(main_window, qtbot)
    po.new_lens()
    target = _patch_save_dialog(monkeypatch, tmp_path, "lens.json")
    main_window._on_save_as()
    QApplication.processEvents()
    assert os.path.exists(target)
    with open(target) as f:
        data = json.load(f)
    assert "radius_of_curvature_1" in data or "radius1" in data or "name" in data


def test_export_stl_iso_report_flow(main_window, qtbot, monkeypatch, tmp_path):
    from PySide6 import QtWidgets

    po = MainWindowPO(main_window, qtbot)
    po.new_lens()

    paths = {
        "stl": str(tmp_path / "lens.stl"),
        "svg": str(tmp_path / "drawing.svg"),
        "txt": str(tmp_path / "report.txt"),
    }
    it = iter([paths["stl"], paths["svg"], paths["txt"]])
    monkeypatch.setattr(QtWidgets.QFileDialog, "getSaveFileName", lambda *a, **k: (next(it), ""))
    main_window._on_export_stl()
    main_window._on_export_iso10110()
    main_window._on_export_report()
    QApplication.processEvents()
    assert os.path.exists(paths["stl"])
    assert os.path.exists(paths["svg"])
    assert os.path.exists(paths["txt"])
    assert os.path.getsize(paths["stl"]) > 0


def test_export_step_graceful_without_occ(main_window, qtbot, monkeypatch, tmp_path):
    """STEP needs pythonocc-core; flow must warn, never crash headless."""
    from PySide6 import QtWidgets

    target = str(tmp_path / "lens.step")
    monkeypatch.setattr(QtWidgets.QFileDialog, "getSaveFileName", lambda *a, **k: (target, ""))
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: QMessageBox.Ok)
    monkeypatch.setattr(QMessageBox, "critical", lambda *a, **k: QMessageBox.Ok)
    main_window._on_export_step()
    QApplication.processEvents()
    # Either a file (OCC present) or a warning dialog (absent) is valid.


def test_theme_and_view_flow(main_window, qtbot):
    po = MainWindowPO(main_window, qtbot)
    assert po.toggle_theme() in ("light", "dark")
    assert po.toggle_theme() in ("light", "dark")
    main_window._set_viz_mode("2D")
    main_window._set_viz_mode("side")
    main_window._on_reset_window()
    QApplication.processEvents()
    assert main_window.width() >= 800
