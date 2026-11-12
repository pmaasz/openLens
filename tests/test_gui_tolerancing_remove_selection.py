"""#669: Remove must only delete an operand the user actually selected."""

import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication, QWidget

    PYSIDE_AVAILABLE = True
    _PYSIDE_ERROR = ""
except ImportError as _e:  # pragma: no cover - environment guard
    PYSIDE_AVAILABLE = False
    _PYSIDE_ERROR = str(_e)

if PYSIDE_AVAILABLE:
    app = QApplication.instance() or QApplication(sys.argv)


@unittest.skipUnless(PYSIDE_AVAILABLE, f"PySide6 not available: {_PYSIDE_ERROR}")
class TestRemoveToleranceSelection(unittest.TestCase):
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
        from openlens.tolerancing import ToleranceOperand, ToleranceType

        self.lens = Lens(
            name="L",
            radius_of_curvature_1=50.0,
            radius_of_curvature_2=-50.0,
            refractive_index=1.5168,
            thickness=5.0,
            diameter=25.0,
        )
        self.window = self._FakeWindow(self.lens)
        self.window._tol_operands.extend(
            [
                ToleranceOperand(0, ToleranceType.RADIUS_1, -0.1, 0.1),
                ToleranceOperand(0, ToleranceType.RADIUS_2, -0.1, 0.1),
                ToleranceOperand(0, ToleranceType.THICKNESS, -0.05, 0.05),
            ]
        )
        self.tab = TolerancingTab(self.window)
        self.tab._update_tolerance_operands_display()

    def tearDown(self):
        self.tab.close()
        self.tab.deleteLater()
        self.window.close()
        self.window.deleteLater()
        QApplication.processEvents()

    def test_remove_with_nothing_selected_is_a_no_op(self):
        before = [(o.param_type.value, o.min_val) for o in self.window._tol_operands]
        self.assertEqual(self.tab._tol_table.selectedIndexes(), [])

        self.tab._on_remove_tolerance()

        after = [(o.param_type.value, o.min_val) for o in self.window._tol_operands]
        self.assertEqual(before, after)
        self.assertEqual(self.tab._tol_table.rowCount(), len(before))

    def test_remove_button_is_disabled_without_a_selection(self):
        self.assertFalse(self.tab._remove_btn.isEnabled())

        self.tab._tol_table.selectRow(0)
        self.assertTrue(self.tab._remove_btn.isEnabled())

    def test_selecting_a_row_removes_that_operand(self):
        self.tab._tol_table.selectRow(0)

        self.tab._on_remove_tolerance()

        remaining = [o.param_type.value for o in self.window._tol_operands]
        self.assertEqual(remaining, ["Radius 2", "Thickness"])


if __name__ == "__main__":
    unittest.main()
