"""Flow: Edit > Undo/Redo for assembly edits (#586)."""

from PySide6.QtWidgets import QApplication

from .conftest import requires_pyside

pytestmark = requires_pyside


def _assembly_with_lens(window):
    window._on_new_lens()
    window._on_new_assembly()
    tab = window._assembly_tab_widget
    tab.refresh()
    QApplication.processEvents()
    assert tab._assembly_lens_list.count() > 0
    tab._assembly_lens_list.setCurrentRow(0)
    tab._on_add_lens_to_system()
    QApplication.processEvents()
    return tab


def test_assembly_add_undo_redo_via_edit_menu(main_window):
    tab = _assembly_with_lens(main_window)
    assert len(tab._optical_system.elements) == 1
    assert tab.undo_stack.canUndo()
    assert main_window._undo_action.isEnabled()
    assert not main_window._redo_action.isEnabled()

    main_window._undo_action.trigger()

    assert tab._optical_system.elements == []
    assert tab._system_list.count() == 0
    assert main_window._redo_action.isEnabled()

    main_window._redo_action.trigger()

    assert len(tab._optical_system.elements) == 1
    assert tab._system_list.count() == 1


def test_undo_is_persisted_through_the_normal_debounced_save(main_window, monkeypatch):
    saves = []
    monkeypatch.setattr(
        main_window,
        "_save_to_database",
        lambda reconcile=True: saves.append(reconcile) or True,
    )

    tab = _assembly_with_lens(main_window)
    main_window._flush_pending_edit()
    saves.clear()

    main_window._undo_action.trigger()
    main_window._flush_pending_edit()

    assert tab._optical_system.elements == []
    assert saves == [False]


def test_switching_assemblies_clears_history(main_window):
    tab = _assembly_with_lens(main_window)
    assert tab.undo_stack.canUndo()

    main_window._on_new_assembly()
    QApplication.processEvents()

    assert tab._optical_system is main_window._current_assembly
    assert tab.undo_stack.count() == 0
    assert not main_window._undo_action.isEnabled()


def test_switching_to_the_lens_editor_clears_assembly_history(main_window):
    tab = _assembly_with_lens(main_window)
    assert tab.undo_stack.canUndo()

    main_window._on_new_lens()
    QApplication.processEvents()

    assert tab.undo_stack.count() == 0
    assert not main_window._undo_action.isEnabled()
    assert not main_window._redo_action.isEnabled()
