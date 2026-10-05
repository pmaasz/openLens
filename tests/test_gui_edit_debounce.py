"""Tests for the debounced GUI edit path and non-computational tab refresh.

Regression cover for #299: every spinbox ``valueChanged`` and every name
keystroke called ``_save_to_database()`` and ``_update_all_tabs()`` directly,
and ``PerformanceTab.refresh()`` re-ran ``calculate_all_aberrations()`` plus
``calculate_chromatic_aberration()`` on the GUI thread. Measured on master,
four name keystrokes blocked for ~1.0 s (~255 ms each), a single
``PerformanceTab.refresh()`` cost ~315 ms, and one 3D canvas redraw ~120 ms.

These tests drive a real ``OpenLensWindow`` so the timers, tab stack and
widget visibility behave as they do in the app.
"""

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

import openlens
from src.lens import Lens

_app = None
_window = None


def _ensure_app():
    global _app
    if _app is None:
        _app = QApplication.instance() or QApplication([])
    return _app


def _spin_until(predicate, timeout_ms=6000):
    """Run the event loop until ``predicate()`` holds or time runs out."""
    loop = QEventLoop()
    steps = {"n": 0}
    timer = QTimer()

    def _tick():
        steps["n"] += 1
        if predicate() or steps["n"] * 10 >= timeout_ms:
            loop.quit()

    timer.timeout.connect(_tick)
    timer.start(10)
    loop.exec()
    timer.stop()
    return predicate()


def _pump(ms=0):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def _real_window():
    """One shared real window; building it is expensive."""
    global _window
    _ensure_app()
    if _window is None:
        _window = openlens.OpenLensWindow(action=None, data=None)
        # Shown so isVisible() is meaningful: Qt reports False for the children
        # of a window that was never shown, which would make the 3D-visibility
        # tests pass for the wrong reason.
        _window.show()
        _pump(80)
    return _window


class _WindowCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.window = _real_window()

    def setUp(self):
        self.window = _real_window()
        # Start each test from a clean debounce state.
        if getattr(self.window, "_edit_timer", None) is not None:
            self.window._edit_timer.stop()
        self.window._pending_edit_status = None


class TestPerformanceTabRefreshIsNotComputational(_WindowCase):
    """refresh() must repaint from cache, not re-trace."""

    def setUp(self):
        super().setUp()
        self.tab = self.window._perf_tab
        self.lens = self.window._current_lens
        self.tab.refresh()
        # Establish a baseline cache from the explicit path.
        self.tab._on_calculate_performance_metrics()

    def test_refresh_does_not_call_the_calculator(self):
        """The trace must not run on a refresh."""
        calls = []
        original = self.tab._on_calculate_performance_metrics
        self.tab._on_calculate_performance_metrics = lambda: calls.append(1)
        try:
            self.tab.refresh()
        finally:
            self.tab._on_calculate_performance_metrics = original
        self.assertEqual(calls, [], "refresh() must not compute metrics")

    def test_refresh_before_calculation_prompts_the_user(self):
        """With no cached metrics, refresh must say so rather than show a blank."""
        saved = (
            self.tab._cached_metrics_text,
            self.tab._cached_metrics,
            self.tab._cached_metrics_for,
        )
        self.tab._cached_metrics_text = None
        self.tab._cached_metrics = None
        self.tab._cached_metrics_for = None
        try:
            self.tab.refresh()
        finally:
            (
                self.tab._cached_metrics_text,
                self.tab._cached_metrics,
                self.tab._cached_metrics_for,
            ) = saved
        self.assertIn("Calculate Metrics", self.tab._perf_metrics_text.toPlainText())

    def test_cached_metrics_are_repainted(self):
        """After an explicit calculation, refresh shows the cached result."""
        self.tab.refresh()
        text = self.tab._perf_metrics_text.toPlainText()
        self.assertIn("OPTICAL PERFORMANCE METRICS", text)

    def test_cache_is_per_model(self):
        """Switching targets must not show the previous model's metrics."""
        other = Lens(
            name="Other",
            radius_of_curvature_1=50.0,
            radius_of_curvature_2=-50.0,
            thickness=4.0,
            diameter=20.0,
        )
        self.tab._cached_metrics_for = self.window._current_lens
        self.tab._cached_metrics_text = "SENTINEL"

        self.window._current_lens = other
        try:
            self.tab.refresh()
        finally:
            self.window._current_lens = self.lens
        self.assertNotEqual(self.tab._perf_metrics_text.toPlainText(), "SENTINEL")
        self.assertIn("Calculate Metrics", self.tab._perf_metrics_text.toPlainText())

    def test_no_active_system_clears_the_display(self):
        """Deselecting everything must not leave stale metrics on screen."""
        saved_lens, saved_asm = self.window._current_lens, self.window._current_assembly
        self.window._current_lens = None
        self.window._current_assembly = None
        try:
            self.tab.refresh()
        finally:
            self.window._current_lens, self.window._current_assembly = saved_lens, saved_asm
        self.assertNotIn("OPTICAL PERFORMANCE METRICS", self.tab._perf_metrics_text.toPlainText())

    def test_calculate_button_populates_the_cache(self):
        """The explicit path must still work and must cache its result."""
        self.tab._cached_metrics_text = None
        self.tab._cached_metrics = None
        self.tab._cached_metrics_for = None
        self.tab._on_calculate_performance_metrics()
        self.assertIsNotNone(self.tab._cached_metrics_text)
        self.assertIsNotNone(self.tab._cached_metrics)
        self.assertIs(self.tab._cached_metrics_for, self.lens)


class TestThreeDimensionalRedrawIsDeferred(_WindowCase):
    """The 3D matplotlib canvas costs ~120 ms per redraw; the 2D one ~0 ms."""

    def setUp(self):
        super().setUp()
        self.viz = self.window._lens_editor._viz_widget
        self.lens = self.window._current_lens
        self.viz._viz_tabs.setCurrentIndex(0)
        _pump(20)

    def test_hidden_3d_view_is_not_redrawn(self):
        """With the 3D tab hidden, update_lens must not touch the 3D canvas."""
        calls = []
        original = self.viz._3d_widget.update_lens
        self.viz._3d_widget.update_lens = lambda lens: calls.append(lens)
        try:
            self.viz.update_lens(self.lens)
        finally:
            self.viz._3d_widget.update_lens = original
        self.assertEqual(calls, [], "3D redraw must be deferred while hidden")
        self.assertTrue(self.viz._3d_dirty)

    def test_2d_view_is_always_updated(self):
        """Deferring 3D must not stop the cheap 2D update."""
        calls = []
        original = self.viz._2d_widget.update_lens
        self.viz._2d_widget.update_lens = lambda lens: calls.append(lens)
        try:
            self.viz.update_lens(self.lens)
        finally:
            self.viz._2d_widget.update_lens = original
        self.assertEqual(calls, [self.lens])

    def test_showing_the_3d_tab_flushes_the_deferred_update(self):
        """Switching to 3D must apply the redraw that was skipped."""
        calls = []
        original = self.viz._3d_widget.update_lens
        self.viz._3d_widget.update_lens = lambda lens: calls.append(lens)
        try:
            self.viz.update_lens(self.lens)
            self.assertEqual(calls, [])
            self.viz._on_tab_changed(1)
        finally:
            self.viz._3d_widget.update_lens = original
        self.assertEqual(calls, [self.lens])
        self.assertFalse(self.viz._3d_dirty)

    def test_update_while_visible_redraws_immediately(self):
        """Once 3D is on screen, edits must show at once."""
        self.viz._viz_tabs.setCurrentIndex(1)
        _pump(20)
        calls = []
        original = self.viz._3d_widget.update_lens
        self.viz._3d_widget.update_lens = lambda lens: calls.append(lens)
        try:
            self.viz.update_lens(self.lens)
        finally:
            self.viz._3d_widget.update_lens = original
            self.viz._viz_tabs.setCurrentIndex(0)
        self.assertEqual(calls, [self.lens])
        self.assertFalse(self.viz._3d_dirty)


class TestEditDebounce(_WindowCase):
    """A burst of edits must collapse into one save and one refresh."""

    def setUp(self):
        super().setUp()
        self.saves = []
        self.refreshes = []
        self._orig_save = self.window._save_to_database
        self._orig_refresh = self.window._update_all_tabs
        self._orig_status = self.window._update_status
        self.window._save_to_database = lambda reconcile=True: self.saves.append(reconcile)
        self.window._update_all_tabs = lambda: self.refreshes.append(1)
        self.window._update_status = lambda text: None

    def tearDown(self):
        self.window._save_to_database = self._orig_save
        self.window._update_all_tabs = self._orig_refresh
        self.window._update_status = self._orig_status

    def test_burst_of_edits_commits_once(self):
        """Typing a word must not save once per character."""
        for i in range(8):
            self.window._schedule_edit_commit(f"edit {i}")
        self.assertEqual(self.saves, [], "no save before the quiet period")

        self.assertTrue(_spin_until(lambda: bool(self.saves)))
        _pump(300)
        self.assertEqual(len(self.saves), 1, "burst must collapse to one save")
        self.assertEqual(len(self.refreshes), 1)

    def test_commit_passes_reconcile_false(self):
        """The per-edit path must not pay for a full reconcile."""
        self.window._schedule_edit_commit("x")
        self.assertTrue(_spin_until(lambda: bool(self.saves)))
        self.assertEqual(self.saves, [False])

    def test_lens_modified_path_is_debounced(self):
        """The real signal handler must go through the debounce."""
        self.window._on_lens_modified(self.window._current_lens)
        self.assertEqual(self.saves, [])
        self.assertTrue(_spin_until(lambda: bool(self.saves)))
        self.assertEqual(len(self.saves), 1)

    def test_refresh_runs_even_if_the_save_raises(self):
        """A failed save must not leave the tabs showing stale data."""
        # The commit runs from a QTimer, so under pytest-qt the raise escapes
        # through the event loop and pytest-qt converts any exception caught
        # there into a test failure. Drive the slot directly instead - the timer
        # plumbing is not what this test is about.
        saved = []

        def _boom(reconcile=True):
            saved.append(reconcile)
            raise RuntimeError("disk full")

        self.window._save_to_database = _boom
        self.window._schedule_edit_commit("x")

        with self.assertRaises(RuntimeError):
            self.window._commit_pending_edit()
        self.assertEqual(saved, [False])
        self.assertEqual(len(self.refreshes), 1)

    def test_flush_applies_a_pending_edit_immediately(self):
        """File > Open must not read the disk before the pending save lands."""
        self.window._schedule_edit_commit("x")
        self.assertEqual(self.saves, [])

        self.window._flush_pending_edit()
        self.assertEqual(len(self.saves), 1, "flush must commit now")
        self.assertEqual(len(self.refreshes), 1)

    def test_flush_is_a_noop_when_nothing_is_pending(self):
        """Flushing an idle window must not write to the database."""
        self.window._flush_pending_edit()
        self.assertEqual(self.saves, [])
        self.assertEqual(self.refreshes, [])

    def test_explicit_save_still_reconciles_by_default(self):
        """The public save path keeps reconcile=True for File > Save."""
        import inspect

        sig = inspect.signature(openlens.OpenLensWindow._save_to_database)
        self.assertIs(sig.parameters["reconcile"].default, True)


if __name__ == "__main__":
    unittest.main()
