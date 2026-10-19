"""Regression: deleting must actually remove the row.

Both delete paths removed the item from an in-memory list and then called
``save_lenses(remaining)``. That method defaults to ``reconcile=False``, and
its own docstring says it "only inserts or replaces rows and never reconciles
deletions" - so nothing was ever deleted. The CLI printed "Lens deleted
successfully!" and the lens reappeared on the next start.

Two further problems in the dialog path:

- it constructed its own ``LensStorage("openlens.db")``, so it ignored
  whatever database the rest of the app was using;
- it bypassed ``delete_item``, which is the only thing that enforces the
  "lens is still used by an assembly" guard, so an assembly could be left
  pointing at a deleted lens.

These tests go through a real SQLite file: delete, then reopen and check.
"""

import os
import sys
import tempfile
import unittest
from unittest import mock

if os.environ.get("DISPLAY", "") == "" and sys.platform.startswith("linux"):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication, QListWidget, QMessageBox

    from openlens.gui.dialogs.startup import StartupDialog
    from openlens.gui.storage import LensStorage
    from openlens.lens import Lens
    from openlens.optical_system import OpticalSystem

    PYSIDE_AVAILABLE = True
    _PYSIDE_ERROR = None
except ImportError as _e:
    QApplication = QMessageBox = QListWidget = None  # type: ignore
    StartupDialog = LensStorage = Lens = OpticalSystem = None  # type: ignore
    PYSIDE_AVAILABLE = False
    _PYSIDE_ERROR = _e

if PYSIDE_AVAILABLE:
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)


class _DbCase(unittest.TestCase):
    """A real database seeded with two named lenses."""

    def setUp(self):
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        self.path = tmp.name

        storage = LensStorage(self.path)
        for index, name in enumerate(("Alpha", "Beta"), start=1):
            lens = Lens(name=name)
            lens.id = f"lens-{index}"
            storage.save_lenses([lens], show_status=False)

        def cleanup():
            for suffix in ("", "-shm", "-wal"):
                if os.path.exists(self.path + suffix):
                    os.remove(self.path + suffix)

        self.addCleanup(cleanup)

    def _stored_names(self):
        return [item.name for item in LensStorage(self.path).load_lenses()]

    def _stored_ids(self):
        return [item.id for item in LensStorage(self.path).load_lenses()]


class TestCliDeleteRemovesTheRow(_DbCase):
    """LensManager.delete_lens."""

    def _manager(self):
        from openlens.lens_editor import LensManager

        return LensManager(self.path)

    def test_deleted_lens_does_not_come_back(self):
        """The whole point: the row has to be gone from the file."""
        manager = self._manager()
        self.assertEqual([lens.name for lens in manager.lenses], ["Alpha", "Beta"])

        with mock.patch("builtins.input", side_effect=["1", "yes"]):
            manager.delete_lens()

        self.assertEqual(self._stored_names(), ["Beta"])

    def test_declining_leaves_the_row_alone(self):
        """A cancelled delete must not touch anything."""
        with mock.patch("builtins.input", side_effect=["1", "no"]):
            self._manager().delete_lens()

        self.assertEqual(self._stored_names(), ["Alpha", "Beta"])

    def test_the_other_lens_is_untouched(self):
        with mock.patch("builtins.input", side_effect=["2", "yes"]):
            self._manager().delete_lens()

        self.assertEqual(self._stored_names(), ["Alpha"])


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 not available")
class TestStartupDialogDeleteRemovesTheRow(_DbCase):
    """StartupDialog._on_delete."""

    def _dialog(self):
        return StartupDialog(storage=LensStorage(self.path))

    def test_deleted_item_does_not_come_back(self):
        dialog = self._dialog()
        self.addCleanup(dialog.close)
        widget = _widget_for(dialog._all_items)

        with mock.patch(
            "openlens.gui.dialogs.startup.QMessageBox.question", return_value=QMessageBox.Yes
        ):
            dialog._on_delete(widget, dialog._all_items, "lens")

        self.assertEqual(self._stored_names(), ["Beta"])

    def test_declining_leaves_the_row_alone(self):
        dialog = self._dialog()
        self.addCleanup(dialog.close)
        widget = _widget_for(dialog._all_items)

        with mock.patch(
            "openlens.gui.dialogs.startup.QMessageBox.question", return_value=QMessageBox.No
        ):
            dialog._on_delete(widget, dialog._all_items, "lens")

        self.assertEqual(self._stored_names(), ["Alpha", "Beta"])

    def test_uses_the_injected_database_not_the_hard_coded_one(self):
        """The dialog opened its own "openlens.db", ignoring the app's."""
        dialog = self._dialog()
        self.addCleanup(dialog.close)
        widget = _widget_for(dialog._all_items)

        with mock.patch(
            "openlens.gui.dialogs.startup.QMessageBox.question", return_value=QMessageBox.Yes
        ):
            dialog._on_delete(widget, dialog._all_items, "lens")

        # The deletion happened in the injected file, so it must be reflected
        # there and nowhere else.
        self.assertEqual(self._stored_ids(), ["lens-2"])


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 not available")
class TestStartupDialogRespectsTheInUseGuard(_DbCase):
    """delete_item refuses to remove a lens an assembly still uses."""

    def setUp(self):
        super().setUp()
        storage = LensStorage(self.path)
        system = OpticalSystem(name="Assembly")
        system.add_lens(LensStorage(self.path).load_lenses()[0])
        system.id = "asm-1"
        storage.save_lenses([system], show_status=False)

    def test_a_used_lens_is_not_deleted(self):
        dialog = StartupDialog(storage=LensStorage(self.path))
        self.addCleanup(dialog.close)

        widget = _widget_for(dialog._all_items, select_id="lens-1")

        with mock.patch(
            "openlens.gui.dialogs.startup.QMessageBox.question", return_value=QMessageBox.Yes
        ), mock.patch("openlens.gui.dialogs.startup.QMessageBox.warning") as warning:
            dialog._on_delete(widget, dialog._all_items, "lens")

        self.assertEqual(warning.call_count, 1, "the in-use guard was not reported")
        self.assertIn("lens-1", self._stored_ids())


def _widget_for(items, select_id=None):
    """A list widget with one row per item, with one row selected.

    ``_on_delete`` works off ``currentRow()``, so the widget is all a test
    needs to stand in for the real list view.

    ``select_id`` picks the row by id rather than defaulting to the first one:
    the order of ``load_lenses`` is not the insertion order. save_assembly
    re-inserts every lens it references, and SQLite's INSERT OR REPLACE
    deletes the old row, so a referenced lens moves to the end of the scan.
    """
    widget = QListWidget()
    for item in items:
        widget.addItem(item.name)
    row = 0
    if select_id is not None:
        row = next(
            (i for i, item in enumerate(items) if item.id == select_id),
            0,
        )
    widget.setCurrentRow(row)
    return widget


if __name__ == "__main__":
    unittest.main()
