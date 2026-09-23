"""Flow: Lens Editor manual QA -> automated.

Manual checklist replaced:
- create new lens, editor shows it
- edit R1/R2/thickness/diameter spinboxes -> model + labels + viz update
- edge-lock on/off behavior smoke
- duplicate lens
- tab switching across all 6 tabs without crash
"""

from PySide6.QtWidgets import QApplication

from .conftest import requires_pyside
from .pages import MainWindowPO

pytestmark = requires_pyside


def test_create_and_edit_lens_flow(main_window, qtbot):
    po = MainWindowPO(main_window, qtbot)
    lens = po.new_lens()
    assert lens is not None

    po.edit_current_lens(r1=60.0, r2=-60.0, thickness=6.0, diameter=30.0)
    cur = main_window._current_lens
    assert cur.radius_of_curvature_1 == 60.0
    assert cur.radius_of_curvature_2 == -60.0
    assert cur.thickness == 6.0
    assert cur.diameter == 30.0
    # Labels reflect model (no widget-side lensmaker duplication).
    assert "mm" in main_window._lens_editor._focal_label.text()


def test_lens_editor_validation_and_feasibility_labels(main_window, qtbot):
    po = MainWindowPO(main_window, qtbot)
    po.new_lens()
    # Infeasible geometry surfaces a warning instead of silently clamping.
    # Edge-lock off so thickness does not auto-compensate (cf. test_gui.py).
    main_window._lens_editor._lock_edge_check.setChecked(False)
    po.edit_current_lens(r1=86.63, r2=-109.97, thickness=5.0, diameter=50.0)
    ed = main_window._lens_editor
    QApplication.processEvents()
    assert not ed._feas_warning_label.isHidden()


def test_duplicate_and_tab_switching_flow(main_window, qtbot):
    po = MainWindowPO(main_window, qtbot)
    po.new_lens()
    dup = po.duplicate_current_lens()
    assert "(copy)" in dup.name

    for tab in ("lens_editor", "simulation", "performance", "optimization", "tolerancing"):
        po.switch_tab(tab)
    # Assembly tab becomes visible only with an assembly active.
    po.new_assembly()
    po.switch_tab("assembly")
    assert main_window._editor_tabs.isTabVisible(1)
