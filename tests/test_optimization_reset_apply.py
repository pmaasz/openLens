"""Regression: Reset must undo Apply everywhere, not just in the title bar.

After Apply, ``_lenses`` and the editor hold the optimised copy. Reset used to
assign only ``_parent._current_lens = original``: it did not put the original
back into ``_lenses`` and did not call ``_lens_editor.load_lens``. So the editor
kept editing an object that was no longer current, and the next reconciling save
swapped by id and discarded those edits.

Apply also overwrote any edits made since the run started, without a word.
"""

import os
import sys
import unittest

if os.environ.get("DISPLAY", "") == "" and sys.platform.startswith("linux"):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QWidget

    PYSIDE_AVAILABLE = True
except ImportError:  # pragma: no cover - environment guard
    QWidget = None
    PYSIDE_AVAILABLE = False

if PYSIDE_AVAILABLE:
    from PySide6.QtWidgets import QApplication

    QApplication.instance() or QApplication([])

from openlens.lens import Lens
from openlens.optical_system import OpticalSystem


def _lens(radius=60.0):
    return Lens(
        name="Crown",
        radius_of_curvature_1=radius,
        radius_of_curvature_2=-radius,
        thickness=6.0,
        diameter=30.0,
        material="N-BK7",
        refractive_index=1.5168,
    )


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 not available")
class _Fixture(unittest.TestCase):
    """A stand-in main window with the parts the tab actually reaches for."""

    def setUp(self):
        from openlens.gui.tabs.optimization_tab import OptimizationTab

        outer = self

        class _Editor:
            def __init__(self):
                self.loaded = []

            def load_lens(self, lens):
                self.loaded.append(lens)

        class _AsmTab:
            def __init__(self):
                self._optical_system = None

        class _Parent(QWidget):
            def __init__(self):
                super().__init__()
                self._lenses = []
                self._assemblies = []
                self._current_lens = None
                self._current_assembly = None
                self._optical_system = None
                self._lens_editor = _Editor()
                self._assembly_tab_widget = _AsmTab()
                self.saved = 0
                self.status = []
                self.refreshes = 0
                self.current_history = []

            def _update_status(self, message):
                self.status.append(message)

            def _update_all_tabs(self):
                self.refreshes += 1

            def _save_to_database(self):
                self.saved += 1

            def _set_current_item(self, item, is_assembly=False):
                # Mirrors openlens/__main__.py's _set_current_item, deliberately
                # *unfaithfully in one direction*: the real lens branch reloads
                # the editor and the real assembly branch sets `_optical_system`
                # (via _load_assembly), but neither touches
                # `_assembly_tab_widget._optical_system`. Making the stub do so
                # would hide a real defect - that field is what
                # openlens/__main__.py:570 reads when the assembly editor reports a
                # modification, so if it still points at the superseded system
                # the user's edits land on the wrong object.
                outer.recorded = item
                if is_assembly:
                    self._current_assembly = item
                    self._current_lens = None
                    self._optical_system = item
                else:
                    self._current_lens = item
                    self._current_assembly = None
                    self._lens_editor.load_lens(item)
                self.current_history.append((item, is_assembly))

        self.parent = _Parent()
        self.addCleanup(self.parent.deleteLater)
        self.tab = OptimizationTab(self.parent)
        self.addCleanup(self.tab.deleteLater)
        self.recorded = None

    def _apply_then_reset(self, lens):
        """Run Apply then Reset on one lens, as the buttons would."""
        self.parent._lenses.append(lens)
        self.parent._current_lens = lens
        self.tab._opt_original_target = lens
        self.tab._opt_run_start_stamp = lens.modified_at

        optimised = _lens(35.0)
        optimised.id = lens.id
        self.tab._opt_pending_target = optimised
        self.tab._on_apply_optimization()

        self.tab._on_reset_optimization()
        return lens, optimised


class TestResetRestoresTheLibrary(_Fixture):
    def test_the_library_holds_the_original_after_reset(self):
        lens, _optimised = self._apply_then_reset(_lens())

        self.assertEqual(
            len(self.parent._lenses),
            1,
            msg="Reset left a second entry in the library",
        )
        self.assertIs(
            self.parent._lenses[0],
            lens,
            msg="Reset put the current pointer back but left the optimised copy "
            "in the library, so the next save swaps by id and discards edits",
        )

    def test_the_editor_is_reloaded_with_the_original(self):
        lens, _optimised = self._apply_then_reset(_lens())

        self.assertIs(
            self.parent._lens_editor.loaded[-1],
            lens,
            msg="the editor kept editing an object that is no longer current",
        )

    def test_the_editor_holds_the_same_object_as_the_library(self):
        """The defect in one assertion: editor object == library object."""
        self._apply_then_reset(_lens())

        self.assertIs(
            self.parent._lens_editor.loaded[-1],
            self.parent._lenses[0],
            msg="the editor and the library disagree about which object is "
            "current, so the next reconciling save discards edits",
        )

    def test_the_lens_id_is_stable_across_reset(self):
        """Reconciling save matches by id; a new id would duplicate the entry."""
        lens, _optimised = self._apply_then_reset(_lens())

        self.assertEqual(self.parent._lenses[0].id, lens.id)

    def test_reset_after_reset_is_harmless(self):
        self._apply_then_reset(_lens())

        self.tab._on_reset_optimization()

        self.assertEqual(len(self.parent._lenses), 1)

    def test_reset_with_nothing_to_reset_is_reported(self):
        self.tab._opt_original_target = None

        self.tab._on_reset_optimization()

        self.assertIn("no original", self.tab._opt_results_text.toPlainText().lower())


class TestResetRestoresAnAssembly(_Fixture):
    def test_the_assembly_library_holds_the_original_after_reset(self):
        system = OpticalSystem(name="Doublet")
        system.add_lens(_lens(50.0))
        original_first = system.elements[0].lens

        self.parent._assemblies.append(system)
        self.parent._current_assembly = system
        self.tab._opt_original_target = system
        self.tab._opt_run_start_stamp = system.modified_at

        optimised = OpticalSystem(name="Doublet")
        optimised.add_lens(_lens(30.0))
        optimised.id = system.id
        self.tab._opt_pending_target = optimised
        self.tab._on_apply_optimization()
        self.tab._on_reset_optimization()

        self.assertEqual(len(self.parent._assemblies), 1)
        self.assertIs(self.parent._assemblies[0], system)
        self.assertIs(
            self.parent._assemblies[0].elements[0].lens,
            original_first,
            msg="the assembly was replaced wholesale rather than restored",
        )

    def test_the_assembly_tab_is_pointed_at_the_original(self):
        """openlens/__main__.py:570 reads this when the assembly editor reports a change.

        If it still points at the system that was replaced, the user's next
        edit lands on an object that is no longer in the library.
        """
        system = OpticalSystem(name="Doublet")
        system.add_lens(_lens(50.0))
        self.parent._assemblies.append(system)
        self.parent._current_assembly = system
        self.tab._opt_original_target = system
        self.tab._opt_run_start_stamp = system.modified_at

        optimised = OpticalSystem(name="Doublet")
        optimised.add_lens(_lens(30.0))
        optimised.id = system.id
        self.tab._opt_pending_target = optimised
        self.tab._on_apply_optimization()

        self.assertIs(
            self.parent._assembly_tab_widget._optical_system,
            optimised,
            msg="after Apply the assembly editor still reports edits against the "
            "system that was replaced, so they are discarded",
        )

        self.tab._on_reset_optimization()

        self.assertIs(self.parent._assembly_tab_widget._optical_system, system)


class TestApplyWarnsAboutEditsMadeWhileRunning(_Fixture):
    """Apply replaces the design wholesale; edits made meanwhile are lost."""

    def _shown(self):
        return self.tab._opt_results_text.toPlainText()

    def test_no_warning_when_nothing_changed(self):
        lens = _lens()
        self.parent._lenses.append(lens)
        self.tab._opt_original_target = lens
        self.tab._opt_run_start_stamp = lens.modified_at
        self.tab._opt_pending_target = _lens(35.0)

        self.tab._on_apply_optimization()

        self.assertNotIn(
            "warning",
            self._shown().lower(),
            msg="warned about edits the user never made",
        )

    def test_a_warning_when_the_lens_was_edited_during_the_run(self):
        lens = _lens()
        self.parent._lenses.append(lens)
        self.tab._opt_original_target = lens
        self.tab._opt_run_start_stamp = lens.modified_at

        # The user keeps working while the optimizer runs.
        lens.radius_of_curvature_1 = 45.0
        lens.modified_at = "2026-01-01T00:00:00"

        self.tab._opt_pending_target = _lens(35.0)
        self.tab._on_apply_optimization()

        self.assertIn(
            "edited while the optimizer was running",
            self._shown().lower(),
            msg="edits made during the run are discarded with no warning",
        )

    def test_the_warning_names_the_design(self):
        lens = _lens()
        self.parent._lenses.append(lens)
        self.tab._opt_original_target = lens
        self.tab._opt_run_start_stamp = lens.modified_at
        lens.modified_at = "2026-01-01T00:00:00"

        self.tab._opt_pending_target = _lens(35.0)
        self.tab._on_apply_optimization()

        self.assertIn(lens.name, self._shown())

    def test_no_warning_without_a_recorded_start_stamp(self):
        """No snapshot means no claim - rather than a wrong one."""
        lens = _lens()
        self.parent._lenses.append(lens)
        self.tab._opt_original_target = lens
        self.tab._opt_run_start_stamp = None

        self.tab._opt_pending_target = _lens(35.0)
        self.tab._on_apply_optimization()

        self.assertNotIn("warning", self._shown().lower())


class TestApplyAndResetShareOnePath(_Fixture):
    """The two buttons must not drift apart again."""

    def test_both_call_the_same_folding_helper(self):
        import inspect

        from openlens.gui.tabs.optimization_tab import OptimizationTab

        apply_src = inspect.getsource(OptimizationTab._on_apply_optimization)
        reset_src = inspect.getsource(OptimizationTab._on_reset_optimization)

        self.assertIn("_fold_target_into_library", apply_src)
        self.assertIn(
            "_fold_target_into_library",
            reset_src,
            msg="Reset bypassed the shared path, which is how it came to update "
            "only one of the places Apply updates",
        )

    def test_the_folded_target_is_what_becomes_current(self):
        lens = _lens()
        self.parent._lenses.append(lens)
        self.tab._opt_original_target = lens
        self.tab._opt_run_start_stamp = lens.modified_at
        optimised = _lens(35.0)
        optimised.id = lens.id
        self.tab._opt_pending_target = optimised

        self.tab._on_apply_optimization()

        self.assertIs(self.recorded, optimised)
        self.assertIs(self.parent._current_lens, optimised)


if __name__ == "__main__":
    unittest.main()
