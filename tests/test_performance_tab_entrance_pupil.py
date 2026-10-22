#!/usr/bin/env python3
"""The Performance tab must evaluate the entrance pupil it displays.

The tab read its "Entrance Pupil" spin box, printed the value in the report,
and built the aberration calculator without it, so every pupil produced the
same f-number and the same metrics. The "Object Distance" spin box was worse:
the aberration model only supports an object at infinity, so the widget's
value was never usable at all.
"""

import os
import re
import sys
import unittest
from unittest import mock

if os.environ.get("DISPLAY", "") == "" and sys.platform.startswith("linux"):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QWidget

    PYSIDE_AVAILABLE = True
except ImportError:  # pragma: no cover - environment guard
    PYSIDE_AVAILABLE = False


class _Signal:
    """The subset of a Qt signal the tab connects to."""

    def __init__(self):
        self._slots = []

    def connect(self, slot):
        self._slots.append(slot)

    def emit(self, *args):
        for slot in list(self._slots):
            slot(*args)


class _InlineWorker:
    """Run the tab's computation on the calling thread, then signal it."""

    def __init__(self, compute, parent=None):
        self._compute = compute
        self.done = _Signal()
        self.failed = _Signal()
        self.finished = _Signal()

    def isRunning(self):
        return False

    def start(self):
        try:
            payload = self._compute()
        except Exception as exc:  # noqa: BLE001 - surfaced via failed, as the real worker
            self.failed.emit(str(exc))
        else:
            self.done.emit(payload)
        finally:
            self.finished.emit()


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 not available")
class TestPerformanceTabEntrancePupil(unittest.TestCase):
    def setUp(self):
        from tests import ensure_qapp, flush_qt

        ensure_qapp()
        self.addCleanup(flush_qt)

        from openlens.gui.tabs.performance_tab import PerformanceTab
        from openlens.lens import Lens

        class _Parent(QWidget):
            def __init__(self):
                super().__init__()
                self._current_assembly = None
                self._current_lens = None
                self.status = []

            def _update_status(self, message):
                self.status.append(message)

        self.parent = _Parent()
        self.addCleanup(self.parent.deleteLater)
        self.tab = PerformanceTab(self.parent)
        self.addCleanup(self.tab.deleteLater)

        self.parent._current_lens = Lens(
            name="Singlet",
            radius_of_curvature_1=100.0,
            radius_of_curvature_2=-100.0,
            thickness=5.0,
            diameter=25.0,
            refractive_index=1.5168,
        )

    def _report(self, pupil: float) -> str:
        from openlens.gui.tabs import performance_tab

        self.tab._perf_entrance_pupil.setValue(pupil)
        with mock.patch.object(performance_tab, "AnalysisWorker", _InlineWorker):
            self.tab._on_calculate_performance_metrics()
        return self.tab._perf_metrics_text.toPlainText()

    @staticmethod
    def _f_number(text: str) -> float:
        match = re.search(r"f-number \(f/#\): ([0-9.]+)", text)
        if match is None:
            raise AssertionError(f"the report has no f-number:\n{text}")
        return float(match.group(1))

    def test_the_report_evaluates_the_pupil_it_shows(self):
        text = self._report(10.0)

        self.assertIn("Entrance Pupil: 10.00 mm", text)
        self.assertIn("f-number (f/#):", text)

    def test_changing_the_pupil_changes_the_f_number(self):
        narrow = self._f_number(self._report(10.0))
        wide = self._f_number(self._report(20.0))

        self.assertAlmostEqual(wide, narrow / 2.0, places=1)

    def test_a_pupil_wider_than_the_lens_is_reported_clamped(self):
        text = self._report(100.0)

        self.assertIn("Entrance Pupil: 25.00 mm", text)

    def test_the_object_distance_is_stated_as_infinity(self):
        text = self._report(10.0)

        self.assertIn("Object Distance: infinity", text)
        self.assertNotIn("Object Distance: 1000", text)

    def test_the_finite_object_distance_control_is_gone(self):
        self.assertFalse(
            hasattr(self.tab, "_perf_object_distance"),
            "the tab still offers an object distance the aberration model " "cannot honour",
        )


if __name__ == "__main__":
    unittest.main()
