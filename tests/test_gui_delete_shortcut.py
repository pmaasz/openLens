"""Regression: the Delete shortcut must not silently destroy a lens.

Edit > Delete Lens was bound to the bare ``Delete`` key at window level. Text
fields consume that key, but tables and lists do not, so with focus in the
tolerance table or an assembly list a single keystroke removed the current lens
from memory *and* the database - no confirmation and no undo. The startup
dialog's delete did ask first; this path did not.

Two halves are asserted here:

* the shortcut is no longer the bare Delete key, so a table or list keeps the
  Delete key for itself, and
* the user-facing action asks before deleting.

A note on method: this asserts the action's shortcut sequence and the slot's
behaviour rather than sending a synthetic ``Delete`` key event. An offscreen
window is never activated, so window-level shortcuts do not fire at all and a
synthetic key test passes whether or not the shortcut is bound to Delete - it
would be a green test that proves nothing. Driving the slot directly also keeps
the assertion independent of Qt's keyboard routing.
"""

import os
import sys
import tempfile
import unittest
from unittest import mock

# Headless environments (CI): fall back to Qt's offscreen platform before
# any QApplication is created. A real DISPLAY always wins.
if os.environ.get("DISPLAY", "") == "" and sys.platform.startswith("linux"):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication, QMessageBox

    from openlens import OpenLensWindow

    PYSIDE_AVAILABLE = True
    _PYSIDE_ERROR = None
except ImportError as _e:
    QApplication = QMessageBox = None  # type: ignore
    OpenLensWindow = None  # type: ignore
    PYSIDE_AVAILABLE = False
    _PYSIDE_ERROR = _e

if PYSIDE_AVAILABLE:
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)

    _YES = QMessageBox.Yes
    _NO = QMessageBox.No


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 not available")
class TestDeleteLensShortcutSafety(unittest.TestCase):
    """Delete Lens must be deliberate, never a stray keystroke."""

    def setUp(self):
        from src.gui.storage import LensStorage

        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
        self.storage = LensStorage(self.temp_db)
        self.window = OpenLensWindow()
        self.window._storage = self.storage
        self.window._db_path = self.temp_db
        self.window._lenses = []
        self.window._assemblies = []
        self.window._current_lens = None
        self.window._current_assembly = None
        self.window._load_default_lens()
        self.window._on_new_lens()
        self.window._save_to_database()

    def tearDown(self):
        self.window.close()
        for path in (self.temp_db, self.temp_db + "-shm", self.temp_db + "-wal"):
            if os.path.exists(path):
                os.remove(path)

    def _delete_shortcut(self):
        """The Edit > Delete Lens shortcut string, or None if the action is gone.

        Read while the owning menu is still referenced: the action is owned in
        C++ by the Edit menu, and PySide6 will raise "Internal C++ object
        already deleted" if it is touched after its owner goes away.
        """
        for menu_bar_action in self.window.menuBar().actions():
            menu = menu_bar_action.menu()
            if menu is None:
                continue
            for entry in menu.actions():
                if entry.text() == "Delete Lens":
                    self._keep_alive = (menu, entry)
                    return entry.shortcut().toString()
        return None

    def test_delete_shortcut_is_not_the_bare_delete_key(self):
        """The shortcut must be qualified, so tables can use Delete themselves."""
        sequence = self._delete_shortcut()
        self.assertIsNotNone(sequence, "Edit > Delete Lens action is missing")
        self.assertNotEqual(sequence, "Del", "Delete Lens is still bound to the bare Delete key")

    def test_delete_shortcut_matches_the_help_dialog(self):
        """The Keyboard Shortcuts help must not advertise the old binding."""
        for menu_bar_action in self.window.menuBar().actions():
            menu = menu_bar_action.menu()
            if menu is None:
                continue
            for entry in menu.actions():
                if entry.text() == "Keyboard Shortcuts":
                    self._keep_alive = menu
                    with mock.patch("openlens.QMessageBox.information") as info:
                        self.window._on_show_shortcuts()
                    help_text = info.call_args[0][2]
                    self.assertNotIn("\nDelete        Delete Lens", help_text)

    def test_deleting_through_the_action_asks_first(self):
        """Declining the confirmation must leave memory and database alone."""
        asked = []

        self.window._current_lens = self.window._lenses[-1]
        target_name = self.window._current_lens.name
        before = len(self.window._lenses)

        with mock.patch(
            "openlens.QMessageBox.question", side_effect=lambda *a, **k: asked.append(a) or _NO
        ):
            self.window._confirm_and_delete_lens()

        self.assertTrue(asked, "no confirmation was requested")
        self.assertEqual(
            len(self.window._lenses), before, "the lens was deleted without confirmation"
        )
        self.assertTrue(
            any(target_name in str(a) for a in asked), "the confirmation did not name the lens"
        )

    def test_confirming_the_prompt_deletes_the_lens(self):
        """Answering Yes must go through to the real deletion."""
        self.window._current_lens = self.window._lenses[-1]
        target_name = self.window._current_lens.name
        before = len(self.window._lenses)

        with mock.patch("openlens.QMessageBox.question", return_value=_YES):
            self.window._confirm_and_delete_lens()

        self.assertEqual(len(self.window._lenses), before - 1)
        self.assertNotIn(target_name, [lens.name for lens in self.window._lenses])

    def test_cancelling_the_prompt_is_reported_to_the_user(self):
        """Declining must say so rather than looking like it did nothing."""
        self.window._current_lens = self.window._lenses[-1]

        with mock.patch("openlens.QMessageBox.question", return_value=_NO):
            self.window._confirm_and_delete_lens()

        self.assertIn("ancel", self.window.statusBar().currentMessage())

    def test_prompt_offers_no_as_the_default(self):
        """Enter must not mean delete: No has to be the default button."""
        with mock.patch("openlens.QMessageBox.question", return_value=_NO) as question:
            self.window._confirm_and_delete_lens()

        self.assertEqual(question.call_count, 1)
        buttons = question.call_args[0][3]
        self.assertEqual(buttons, _YES | _NO)
        self.assertEqual(question.call_args.kwargs.get("defaultButton", buttons), _NO)


if __name__ == "__main__":
    unittest.main()
