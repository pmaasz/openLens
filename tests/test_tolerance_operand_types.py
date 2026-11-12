"""#670: the Add Tolerance dialog must not offer operands the analysis skips."""

import os
import sys
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication, QComboBox, QDialog, QWidget

    PYSIDE_AVAILABLE = True
    _PYSIDE_ERROR = ""
except ImportError as _e:  # pragma: no cover - environment guard
    PYSIDE_AVAILABLE = False
    _PYSIDE_ERROR = str(_e)

if PYSIDE_AVAILABLE:
    app = QApplication.instance() or QApplication(sys.argv)

from openlens.tolerancing import ToleranceType, randomisable_tolerance_types


class TestRandomisableToleranceTypes(unittest.TestCase):
    def test_focus_is_never_offered(self):
        for index, count in ((0, 1), (0, 2), (1, 2), (2, 5)):
            with self.subTest(element=index, elements=count):
                self.assertNotIn(ToleranceType.FOCUS, randomisable_tolerance_types(index, count))

    def test_the_first_element_has_no_axial_despace_or_preceding_gap(self):
        offered = randomisable_tolerance_types(0, 2)
        self.assertNotIn(ToleranceType.DECENTER_X, offered)
        self.assertIn(ToleranceType.AIR_GAP, offered)

    def test_the_last_element_has_no_gap_after_it(self):
        offered = randomisable_tolerance_types(1, 2)
        self.assertIn(ToleranceType.DECENTER_X, offered)
        self.assertNotIn(ToleranceType.AIR_GAP, offered)

    def test_a_single_lens_offers_neither_structural_gap_operand(self):
        offered = randomisable_tolerance_types(0, 1)
        self.assertNotIn(ToleranceType.DECENTER_X, offered)
        self.assertNotIn(ToleranceType.AIR_GAP, offered)
        self.assertIn(ToleranceType.RADIUS_1, offered)


@unittest.skipUnless(PYSIDE_AVAILABLE, f"PySide6 not available: {_PYSIDE_ERROR}")
class TestAddToleranceDialogTypes(unittest.TestCase):
    class _FakeWindow(QWidget):
        def __init__(self, target):
            super().__init__()
            self._target = target
            self._tol_operands = []

        def _active_target(self):
            return self._target

    def setUp(self):
        from openlens.gui.tabs.tolerancing_tab import TolerancingTab
        from openlens.lens import Lens
        from openlens.optical_system import OpticalSystem

        lens = Lens(
            name="L",
            radius_of_curvature_1=50.0,
            radius_of_curvature_2=-50.0,
            refractive_index=1.5168,
            thickness=5.0,
            diameter=25.0,
        )
        system = OpticalSystem(name="Doublet")
        system.add_lens(lens)
        system.add_lens(Lens(name="L2", diameter=25.0), air_gap_before=2.0)

        self.window = self._FakeWindow(system)
        self.tab = TolerancingTab(self.window)

    def tearDown(self):
        self.tab.close()
        self.tab.deleteLater()
        self.window.close()
        self.window.deleteLater()
        QApplication.processEvents()

    @staticmethod
    def _combos(dialog):
        return dialog.findChildren(QComboBox)

    def test_the_dialog_does_not_offer_focus(self):
        seen = {}

        def fake_exec(dialog):
            seen["combos"] = self._combos(dialog)
            return 0

        with mock.patch.object(QDialog, "exec", fake_exec):
            self.tab._on_add_tolerance()

        type_combo = next(
            c for c in seen["combos"] if c.findText(ToleranceType.RADIUS_1.value) >= 0
        )
        offered = [type_combo.itemText(i) for i in range(type_combo.count())]
        self.assertNotIn(ToleranceType.FOCUS.value, offered)
        self.assertNotIn(ToleranceType.DECENTER_X.value, offered)

    def test_the_type_list_follows_the_selected_element(self):
        seen = {}

        def fake_exec(dialog):
            combos = self._combos(dialog)
            elem_combo = next(c for c in combos if c.findText("1") >= 0 and c.findText("0") >= 0)
            type_combo = next(c for c in combos if c.findText(ToleranceType.RADIUS_1.value) >= 0)
            elem_combo.setCurrentIndex(1)
            seen["offered"] = [type_combo.itemText(i) for i in range(type_combo.count())]
            return 0

        with mock.patch.object(QDialog, "exec", fake_exec):
            self.tab._on_add_tolerance()

        self.assertIn(ToleranceType.DECENTER_X.value, seen["offered"])
        self.assertNotIn(ToleranceType.AIR_GAP.value, seen["offered"])
        self.assertNotIn(ToleranceType.FOCUS.value, seen["offered"])


if __name__ == "__main__":
    unittest.main()
