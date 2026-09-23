"""Flow: Library persistence + save/load manual QA -> automated.

Manual checklist replaced:
- spinbox edit reaches SQLite row (upsert, no duplicates)
- Save / Reload round-trip keeps edits
- Lens menu quick-switch selects correct member
- delete-blocked guard: lens in use by assembly cannot be deleted
"""

from PySide6.QtWidgets import QApplication

from .conftest import requires_pyside
from .pages import MainWindowPO

pytestmark = requires_pyside


def _rows_for(window, lens_id):
    from src.gui.storage import LensStorage

    return [x for x in LensStorage(window._db_path).load_lenses() if x.id == lens_id]


def test_spinbox_edit_persists_and_upserts(main_window, qtbot):
    po = MainWindowPO(main_window, qtbot)
    lens = main_window._current_lens
    po.edit_current_lens(r1=60.0, diameter=30.0)
    rows = _rows_for(main_window, lens.id)
    assert len(rows) == 1
    assert rows[0].radius_of_curvature_1 == 60.0
    assert rows[0].diameter == 30.0

    po.edit_current_lens(r1=80.0)
    rows = _rows_for(main_window, lens.id)
    assert len(rows) == 1
    assert rows[0].radius_of_curvature_1 == 80.0


def test_save_reload_round_trip(main_window, qtbot):
    po = MainWindowPO(main_window, qtbot)
    po.edit_current_lens(thickness=7.0)
    main_window._on_save()
    QApplication.processEvents()
    main_window._on_open()  # reload from DB
    QApplication.processEvents()
    assert main_window._current_lens.thickness == 7.0


def test_lens_menu_switch_and_delete_guards(main_window, qtbot):
    po = MainWindowPO(main_window, qtbot)
    po.new_lens()
    po.new_lens()
    assert len(main_window._lenses) >= 3

    main_window._switch_to_lens(0)
    assert main_window._current_lens is main_window._lenses[0]
    main_window._rebuild_lens_menu()
    QApplication.processEvents()

    # Lens-in-use guard: deleting a lens referenced by an assembly refuses
    # without touching memory or DB (warning dialog, no exception to user).
    po.new_assembly()
    asm_tab = main_window._assembly_tab_widget
    asm_tab.refresh()
    asm_tab._assembly_lens_list.setCurrentRow(0)
    po.click_button(asm_tab, "Add to System")
    main_window._on_save()
    used_lens_id = asm_tab._optical_system.elements[0].lens.id
    used = next(x for x in main_window._lenses if x.id == used_lens_id)
    main_window._set_current_item(used)
    before = len(main_window._lenses)
    # Silence the warning dialog in headless runs.
    from PySide6.QtWidgets import QMessageBox

    qtbot.wait(10)
    orig = QMessageBox.warning
    QMessageBox.warning = lambda *a, **k: QMessageBox.Ok
    try:
        main_window._on_delete_lens()
    finally:
        QMessageBox.warning = orig
    QApplication.processEvents()
    assert len(main_window._lenses) == before
    assert _rows_for(main_window, used_lens_id)
