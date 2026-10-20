"""Flow: Edit > Undo/Redo for lens property edits (#566)."""

from PySide6.QtGui import QKeySequence

from .conftest import requires_pyside

pytestmark = requires_pyside


def _fresh_lens(window):
    window._on_new_lens()
    assert window._current_lens is not None
    return window._lens_editor, window._current_lens


def test_edit_menu_undo_redo_changes_model_and_widget(main_window):
    editor, lens = _fresh_lens(main_window)
    original = lens.radius_of_curvature_1

    editor._r1_input.setValue(original + 10.0)

    assert lens.radius_of_curvature_1 == original + 10.0
    assert main_window._undo_action.isEnabled()
    assert not main_window._redo_action.isEnabled()

    main_window._undo_action.trigger()

    assert lens.radius_of_curvature_1 == original
    assert editor._r1_input.value() == original
    assert main_window._redo_action.isEnabled()

    main_window._redo_action.trigger()

    assert lens.radius_of_curvature_1 == original + 10.0
    assert editor._r1_input.value() == original + 10.0


def test_undo_redo_actions_are_in_the_edit_menu_with_shortcuts(main_window):
    edit_action = next(
        action for action in main_window.menuBar().actions() if action.text() == "Edit"
    )
    edit_menu = edit_action.menu()

    assert main_window._undo_action in edit_menu.actions()
    assert main_window._redo_action in edit_menu.actions()
    assert (
        main_window._undo_action.shortcut().toString() == QKeySequence(QKeySequence.Undo).toString()
    )
    assert (
        main_window._redo_action.shortcut().toString() == QKeySequence(QKeySequence.Redo).toString()
    )


def test_undo_is_persisted_through_the_normal_debounced_save(main_window, monkeypatch):
    editor, lens = _fresh_lens(main_window)
    original = lens.radius_of_curvature_1
    saves = []
    monkeypatch.setattr(
        main_window,
        "_save_to_database",
        lambda reconcile=True: saves.append(reconcile) or True,
    )

    editor._r1_input.setValue(original + 5.0)
    main_window._flush_pending_edit()
    saves.clear()

    main_window._undo_action.trigger()
    main_window._flush_pending_edit()

    # The per-edit autosave deliberately skips whole-library reconciliation.
    assert saves == [False]


def test_showing_the_assembly_editor_clears_the_lens_history(main_window):
    editor, _ = _fresh_lens(main_window)
    editor._r1_input.setValue(editor._r1_input.value() + 5.0)
    assert editor.undo_stack.canUndo()

    main_window._show_assembly_editor(True)

    assert not editor.undo_stack.canUndo()
    assert not main_window._undo_action.isEnabled()
