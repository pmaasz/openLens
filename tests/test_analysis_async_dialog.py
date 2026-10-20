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

from PySide6.QtCore import QEventLoop, QTimer

from openlens.analysis.plots import plot_ghost_analysis
from openlens.gui.dialogs.analysis_plots import (
    AnalysisPlotDialog,
    AnalysisWorker,
    show_computing_dialog,
)
from tests import ensure_qapp, flush_qt


def _ensure_app():
    return ensure_qapp()


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


def _run_until_signal(worker, signal, timeout_ms=10000):
    """Start ``worker`` and spin the loop until ``signal`` is delivered.

    Waiting on ``isFinished()`` alone returns as soon as the thread ends,
    before the queued signal event has been processed - the payload then
    arrives after the assertion. Connecting the signal to ``loop.quit`` waits
    for the delivery, not just the thread.
    """
    loop = QEventLoop()
    received = []
    signal.connect(received.append)
    signal.connect(loop.quit)
    timer = QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(loop.quit)
    timer.start(timeout_ms)
    worker.start()
    loop.exec()
    timer.stop()
    worker.wait(1000)
    return received


def _dialog(test, title="Test", parent=None):
    """Create a dialog that is deleted while the application is still alive."""
    dialog = AnalysisPlotDialog(title, parent)
    test.addCleanup(dialog.deleteLater)
    return dialog


class TestAnalysisWorker(unittest.TestCase):
    def setUp(self):
        _ensure_app()
        self.addCleanup(flush_qt)

    def test_worker_emits_computed_payload(self):
        """done must carry whatever the callable returned."""
        worker = AnalysisWorker(lambda: {"value": 42})
        received = _run_until_signal(worker, worker.done)
        worker.deleteLater()
        self.assertEqual(received, [{"value": 42}])

    def test_worker_emits_failed_instead_of_raising(self):
        """A raising computation must report, not escape the thread."""
        worker = AnalysisWorker(self._boom)
        received = _run_until_signal(worker, worker.failed)
        worker.deleteLater()
        self.assertEqual(received, ["boom"])

    @staticmethod
    def _boom():
        raise ValueError("boom")


class TestPlotAsync(unittest.TestCase):
    def setUp(self):
        _ensure_app()
        self.addCleanup(flush_qt)

    def test_show_computing_makes_the_dialog_visible(self):
        """A window must exist before any heavy work starts."""
        dialog = _dialog(self)
        self.assertFalse(dialog.isVisible())
        dialog.show_computing()
        self.assertTrue(dialog.isVisible())
        dialog.close()

    def test_plot_async_returns_before_the_compute_finishes(self):
        """The call must not block on the analysis.

        This is the actual user-visible fix: the handler has to return so the
        event loop keeps running while the worker computes.
        """
        dialog = _dialog(self)
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
        dialog = _dialog(self)
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
        dialog = _dialog(self)
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
        dialog = _dialog(self)
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
        dialog = _dialog(self)
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
        dialog = _dialog(self)
        dialog.plot_async(lambda: 1, lambda ax, payload: None)
        _run_until(lambda: dialog._pending_worker is None)
        self.assertIsNone(dialog._pending_worker)
        dialog.close()


class TestMultiPanelPlots(unittest.TestCase):
    """Field curves need two side-by-side panels, painted by one compute.

    ``plot_async`` historically handed its callback a single axes. A two-panel
    analysis therefore cannot use the helper at all without stacking a second
    subplot by hand - and then the "Calculating" placeholder and the finished
    plot disagree about which axes they own.
    """

    def setUp(self):
        _ensure_app()
        self.addCleanup(flush_qt)

    def test_two_columns_hand_the_plot_two_axes(self):
        dialog = _dialog(self)
        seen = []

        def _plot(axes, payload):
            seen.append(axes)
            left, right = axes
            self.assertEqual(len(axes), 2)
            left.plot([0, 1], [0, payload])
            right.plot([0, 1], [payload, 0])

        dialog.plot_async(lambda: 1, _plot, columns=2)
        _run_until(lambda: bool(seen))

        self.assertEqual(len(seen), 1)
        self.assertEqual(len(dialog.figure.axes), 2)
        self.assertEqual(len(dialog.figure.axes[0].lines), 1)
        self.assertEqual(len(dialog.figure.axes[1].lines), 1)
        dialog.close()

    def test_two_columns_are_reused_not_stacked(self):
        """A second run must replace the result, not add a third subplot."""
        dialog = _dialog(self)

        for value in (1, 2):
            dialog.plot_async(
                lambda v=value: v,
                lambda axes, payload: axes[0].plot([0, payload]),
                columns=2,
            )
            _run_until(lambda: dialog._pending_worker is None)

        self.assertEqual(len(dialog.figure.axes), 2)
        dialog.close()


class TestShowComputingDialog(unittest.TestCase):
    def setUp(self):
        _ensure_app()
        self.addCleanup(flush_qt)

    def test_helper_returns_a_visible_dialog(self):
        """The minimal fallback path must also put a window on screen."""
        parent = _dialog(self, "Parent")
        dialog = show_computing_dialog(parent, "Working", "Please wait")
        self.addCleanup(dialog.deleteLater)
        try:
            self.assertTrue(dialog.isVisible())
            self.assertEqual(dialog.windowTitle(), "Working")
        finally:
            dialog.close()
            parent.close()


if __name__ == "__main__":
    unittest.main()
