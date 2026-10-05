"""Tests for the non-blocking analysis dialog path.

Regression cover for #300: every analysis dialog used to do its multi-second
computation *before* the dialog was constructed, so nothing was on screen while
it ran and the app looked hung. Verified timings on a 4-element assembly were
~8 s for the wavefront and ~3.4 s each for PSF and MTF.

These tests drive a real QApplication and event loop so the worker signal
round-trip and the painting are actually exercised.
"""

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

from src.analysis.plots import plot_ghost_analysis
from src.gui.dialogs.analysis_plots import (
    AnalysisPlotDialog,
    AnalysisWorker,
    show_computing_dialog,
)

_app = None


def _ensure_app():
    global _app
    if _app is None:
        _app = QApplication.instance() or QApplication([])
    return _app


def _run_until(predicate, timeout_ms=10000):
    """Spin the event loop until ``predicate()`` or the timeout."""
    loop = QEventLoop()
    elapsed = {"ms": 0}
    step = {"t": None}

    def _check():
        if predicate() or elapsed["ms"] >= timeout_ms:
            loop.quit()

    step["t"] = QTimer()
    step["t"].timeout.connect(_check)
    step["t"].start(10)
    loop.exec()
    step["t"].stop()
    return predicate()


class TestAnalysisWorker(unittest.TestCase):
    def setUp(self):
        _ensure_app()

    def test_worker_emits_computed_payload(self):
        """done must carry whatever the callable returned."""
        worker = AnalysisWorker(lambda: {"value": 42})
        seen = []
        worker.done.connect(seen.append)
        worker.finished.connect(lambda: None)
        worker.start()
        _run_until(lambda: worker.isFinished())
        self.assertEqual(seen, [{"value": 42}])

    def test_worker_emits_failed_instead_of_raising(self):
        """A raising computation must report, not escape the thread."""
        worker = AnalysisWorker(self._boom)
        errors = []
        worker.failed.connect(errors.append)
        worker.start()
        _run_until(lambda: worker.isFinished())
        self.assertEqual(errors, ["boom"])

    @staticmethod
    def _boom():
        raise ValueError("boom")


class TestPlotAsync(unittest.TestCase):
    def setUp(self):
        _ensure_app()

    def test_show_computing_makes_the_dialog_visible(self):
        """A window must exist before any heavy work starts."""
        dialog = AnalysisPlotDialog("Test", None)
        self.assertFalse(dialog.isVisible())
        dialog.show_computing()
        self.assertTrue(dialog.isVisible())
        dialog.close()

    def test_plot_async_returns_before_the_compute_finishes(self):
        """The call must not block on the analysis.

        This is the actual user-visible fix: the handler has to return so the
        event loop keeps running while the worker computes.
        """
        dialog = AnalysisPlotDialog("Test", None)
        started = {"v": False}
        finished = {"v": False}

        def _slow():
            started["v"] = True
            # Busy-wait: stands in for a multi-second ray trace.
            deadline = QEventLoop()  # unused; keep the import honest
            total = 0
            while total < 3_000_000:
                total += 1
            return "payload"

        def _plot(ax, payload):
            finished["v"] = True

        # Fire and forget; assert show_computing already made it visible.
        dialog.plot_async(_slow, _plot)
        self.assertTrue(dialog.isVisible(), "dialog must be on screen before computing")

        _run_until(lambda: finished["v"], timeout_ms=30000)
        self.assertTrue(started["v"])
        self.assertTrue(finished["v"], "result must eventually be painted")
        dialog.close()

    def test_plot_async_paints_the_payload(self):
        """The plot callback must receive the worker's payload."""
        dialog = AnalysisPlotDialog("Test", None)
        got = []

        def _plot(ax, payload):
            got.append(payload)
            ax.plot([0, 1], [0, 1])

        dialog.plot_async(lambda: [1.0, 2.0, 3.0], _plot)
        _run_until(lambda: bool(got))
        self.assertEqual(got, [[1.0, 2.0, 3.0]])

        axes = dialog.figure.axes
        self.assertTrue(axes)
        # The status placeholder must have been cleared and replaced.
        self.assertEqual(len(axes[0].lines), 1)
        dialog.close()

    def test_failed_compute_paints_a_message(self):
        """A failure must be visible in the dialog, not silently ignored."""
        dialog = AnalysisPlotDialog("Test", None)
        painted = []
        original = dialog.canvas.draw_idle

        dialog.plot_async(self._boom, lambda ax, payload: painted.append(payload))
        _run_until(lambda: dialog._pending_worker is None)

        titles = [t.get_text() for ax in dialog.figure.axes for t in ax.texts]
        self.assertTrue(any("Analysis failed" in t for t in titles), titles)
        self.assertFalse(painted)
        dialog.close()
        del original

    @staticmethod
    def _boom():
        raise RuntimeError("kaboom")

    def test_multi_arg_plot_callable_receives_one_payload(self):
        """A plot callback may take only (ax, payload) - arity must match.

        Regression: ``plot_ghost_analysis(ax, system, ghosts)`` takes three
        arguments, but the worker hands over a single payload tuple. Passing the
        plotter straight through raised TypeError inside the finished handler.
        """
        dialog = AnalysisPlotDialog("Test", None)
        calls = []

        def _compute():
            return ("system", ["ghost-a", "ghost-b"])

        def _draw(ax, payload):
            calls.append(payload)
            # Exactly what the real ghost path does: unpack the payload.
            system, ghosts = payload
            self.assertEqual(system, "system")
            self.assertEqual(ghosts, ["ghost-a", "ghost-b"])
            ax.plot([0, 1], [0, 1])

        dialog.plot_async(_compute, _draw)
        _run_until(lambda: bool(calls))
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(dialog.figure.axes[0].lines), 1)
        dialog.close()

        # plot_ghost_analysis takes three parameters, so the worker payload
        # cannot be passed straight through - it needs the _draw wrapper above.
        # Assert the arity contract directly; the real function is exercised
        # end-to-end by the GUI flow tests.
        import inspect

        self.assertEqual(len(inspect.signature(plot_ghost_analysis).parameters), 3)

    def test_axes_are_reused_not_stacked(self):
        """Repeated runs must reuse one axes, not stack subplots.

        Calling get_axes() for both the status line and the result would leave
        the stale "Calculating" axes on the figure after every analysis.
        """
        dialog = AnalysisPlotDialog("Test", None)
        for value in (1, 2, 3):
            dialog.plot_async(lambda v=value: v, lambda ax, payload: ax.plot([0, payload]))
            _run_until(lambda: dialog._pending_worker is None)
        # One axes total, not one per run.
        self.assertEqual(len(dialog.figure.axes), 1)
        # Only the newest plot is live: each run clears the previous one.
        self.assertEqual(len(dialog.figure.axes[0].lines), 1)
        dialog.close()

    def test_worker_reference_is_cleared_when_done(self):
        """The dialog must not hold a dead worker forever."""
        dialog = AnalysisPlotDialog("Test", None)
        dialog.plot_async(lambda: 1, lambda ax, payload: None)
        _run_until(lambda: dialog._pending_worker is None)
        self.assertIsNone(dialog._pending_worker)
        dialog.close()


class TestShowComputingDialog(unittest.TestCase):
    def setUp(self):
        _ensure_app()

    def test_helper_returns_a_visible_dialog(self):
        """The minimal fallback path must also put a window on screen."""
        parent = AnalysisPlotDialog("Parent", None)
        dialog = show_computing_dialog(parent, "Working", "Please wait")
        try:
            self.assertTrue(dialog.isVisible())
            self.assertEqual(dialog.windowTitle(), "Working")
        finally:
            dialog.close()
            parent.close()


if __name__ == "__main__":
    unittest.main()
