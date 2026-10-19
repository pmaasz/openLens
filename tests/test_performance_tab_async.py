"""Regression: the Performance tab must not compute on the GUI thread.

#465: the spot diagram, ray fan, field curves and "Calculate Metrics" handlers
traced their rays *before* returning, and image simulation called
``ImageQualityAnalyzer.simulate_image`` directly in the button handler. A
multi-second analysis therefore froze the window exactly like a hang, while
PSF, MTF, wavefront and ghost already computed in an ``AnalysisWorker``.

These tests hold the remaining handlers to the same contract: the handler must
return immediately, the analysis must run in a worker, and the finished plot or
report must still be painted. They drive a real QApplication and event loop so
the worker signal round-trip is exercised.
"""

import math
import os
import sys
import threading
import time
import unittest
from unittest import mock

import numpy as np

if os.environ.get("DISPLAY", "") == "" and sys.platform.startswith("linux"):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtCore import QEventLoop, QTimer
    from PySide6.QtWidgets import QApplication, QWidget

    PYSIDE_AVAILABLE = True
except ImportError:  # pragma: no cover - environment guard
    PYSIDE_AVAILABLE = False

_app = None


def _ensure_app():
    global _app
    if _app is None:
        _app = QApplication.instance() or QApplication(sys.argv[:1])
    return _app


if PYSIDE_AVAILABLE:
    _ensure_app()


def _run_until(predicate, timeout_ms=10000):
    """Spin the event loop until ``predicate()`` or the timeout."""
    loop = QEventLoop()
    elapsed = {"ms": 0}
    timer = QTimer()

    def _check():
        if predicate() or elapsed["ms"] >= timeout_ms:
            loop.quit()

    timer.timeout.connect(_check)
    timer.start(10)
    loop.exec()
    timer.stop()
    return predicate()


def _lens(radius=60.0):
    from openlens.lens import Lens

    return Lens(
        name="Crown",
        radius_of_curvature_1=radius,
        radius_of_curvature_2=-radius,
        thickness=6.0,
        diameter=30.0,
        material="N-BK7",
        refractive_index=1.5168,
    )


def _blocked(return_value, gate, started):
    """A stand-in for a multi-second analysis that waits for the test gate."""

    def _analyse(*args, **kwargs):
        started.set()
        gate.wait(1.0)
        return return_value

    return _analyse


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 not available")
class _AsyncTabFixture(unittest.TestCase):
    """A PerformanceTab over a stand-in parent with the *real* dialog registry.

    ``_open_analysis_dialog`` and its retirement helpers are borrowed from the
    real window rather than stubbed: a handler that opened a dialog which the
    quit-shutdown sweep cannot see would otherwise pass these tests.
    """

    def setUp(self):
        _ensure_app()
        from openlens.__main__ import OpenLensWindow
        from openlens.gui.tabs.performance_tab import PerformanceTab

        class _Parent(QWidget):
            _open_analysis_dialog = OpenLensWindow._open_analysis_dialog
            _on_analysis_dialog_closed = OpenLensWindow._on_analysis_dialog_closed
            _retire_analysis_dialog = OpenLensWindow._retire_analysis_dialog

            def __init__(self):
                super().__init__()
                self._current_assembly = None
                self._current_lens = None
                self._theme = "dark"
                self._analysis_dialogs = []
                self.status = []

            def _update_status(self, message):
                self.status.append(message)

        self.parent = _Parent()
        self.addCleanup(self._dispose_parent)
        self.tab = PerformanceTab(self.parent)
        self.addCleanup(self.tab.deleteLater)

        self.lens = _lens()
        self.parent._current_lens = self.lens
        self._gates = []

    def _event(self):
        gate = threading.Event()
        self._gates.append(gate)
        return gate

    def _metrics_finished(self):
        """True once no metrics worker is running.

        ``getattr`` keeps the pre-#465 code path (no ``_metrics_worker`` at
        all) from hanging the helper; those tests fail on the handler itself.
        """
        worker = getattr(self.tab, "_metrics_worker", None)
        return worker is None or worker.isFinished()

    def _dispose_parent(self):
        for gate in self._gates:
            gate.set()
        for dialog in list(self.parent._analysis_dialogs):
            worker = getattr(dialog, "_pending_worker", None)
            if worker is not None:
                worker.wait(5000)
            dialog.close()
            dialog.deleteLater()
        self.parent._analysis_dialogs.clear()
        self.parent.deleteLater()

    def _dialog(self):
        self.assertTrue(self.parent._analysis_dialogs, "no analysis dialog was opened")
        return self.parent._analysis_dialogs[-1]

    @staticmethod
    def _line_count(dialog, axis=0):
        try:
            return len(dialog.figure.axes[axis].lines)
        except (IndexError, AttributeError):
            return 0

    def assert_returns_before_compute(self, handler, started, gate, limit=0.7):
        """The handler must hand the analysis to a worker and return."""
        began = time.monotonic()
        handler()
        elapsed = time.monotonic() - began
        self.assertLess(
            elapsed,
            limit,
            msg=f"the handler blocked for {elapsed:.2f}s: the analysis ran on "
            "the GUI thread, so the window freezes",
        )
        self.assertTrue(
            _run_until(started.is_set, timeout_ms=5000),
            "the analysis never ran, so no worker was started",
        )
        gate.set()


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 not available")
class TestSpotDiagramIsOffTheGuiThread(_AsyncTabFixture):
    def test_the_handler_returns_and_the_dialog_is_registered(self):
        from openlens.analysis.psf_mtf import ImageQualityAnalyzer
        from openlens.gui.dialogs import analysis_plots

        gate = self._event()
        started = threading.Event()
        calls = []
        points = [(0.001, -0.002), (0.003, 0.0)]

        def _spot(*args, **kwargs):
            calls.append(kwargs)
            started.set()
            gate.wait(1.0)
            return points

        with mock.patch.object(
            ImageQualityAnalyzer, "calculate_spot_diagram", new=_spot
        ), mock.patch.object(analysis_plots.AnalysisPlotDialog, "exec", lambda self: 0):
            self.assert_returns_before_compute(self.tab._on_show_spot_diagram, started, gate)
            dialog = self._dialog()
            self.assertIn(
                dialog,
                self.parent._analysis_dialogs,
                msg="the dialog is not registered, so quitting cannot stop its worker",
            )
            self.assertTrue(
                _run_until(lambda: self._line_count(dialog) == 3),
                "the three field plots were never painted",
            )

        self.assertEqual(len(calls), 3)
        self.assertIn("Spot Diagram", dialog.windowTitle())


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 not available")
class TestRayFanIsOffTheGuiThread(_AsyncTabFixture):
    def test_the_handler_returns_before_the_trace_finishes(self):
        from openlens.aberrations import AberrationsCalculator
        from openlens.gui.dialogs import analysis_plots

        gate = self._event()
        started = threading.Event()
        calls = []

        def _ray_fan(*args, **kwargs):
            calls.append(kwargs)
            started.set()
            gate.wait(1.0)
            return {
                "pupil_coords": [-1.0, 0.0, 1.0],
                "transverse_aberration": [0.01, 0.0, -0.01],
            }

        with mock.patch.object(
            AberrationsCalculator, "calculate_ray_fan", new=_ray_fan
        ), mock.patch.object(analysis_plots.AnalysisPlotDialog, "exec", lambda self: 0):
            self.assert_returns_before_compute(self.tab._on_show_ray_fan, started, gate)
            dialog = self._dialog()
            # Three field curves plus the zero cross-hairs (axhline/axvline).
            self.assertTrue(
                _run_until(lambda: self._line_count(dialog) == 5),
                "the three field traces were never painted",
            )

        self.assertEqual(len(calls), 3)


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 not available")
class TestFieldCurvesAreOffTheGuiThread(_AsyncTabFixture):
    def test_the_handler_returns_before_the_traces_finish(self):
        from openlens.aberrations import AberrationsCalculator
        from openlens.gui.dialogs import analysis_plots

        gate = self._event()
        started = threading.Event()
        seen = []

        def _curvature(*args, **kwargs):
            seen.append(kwargs)
            started.set()
            gate.wait(1.0)
            return [0.0, 5.0, 10.0], [0.01, 0.02, 0.03], [0.02, 0.03, 0.04]

        def _distortion(*args, **kwargs):
            return [0.0, 5.0, 10.0], [0.0, 0.5, 1.0]

        with mock.patch.object(
            AberrationsCalculator, "calculate_field_curvature", new=_curvature
        ), mock.patch.object(
            AberrationsCalculator, "calculate_distortion_curve", new=_distortion
        ), mock.patch.object(
            analysis_plots.AnalysisPlotDialog, "exec", lambda self: 0
        ):
            self.assert_returns_before_compute(self.tab._on_show_field_curves, started, gate)
            dialog = self._dialog()
            # Left: sagittal + tangential. Right: distortion + its zero line.
            self.assertTrue(
                _run_until(
                    lambda: self._line_count(dialog, 0) == 2 and self._line_count(dialog, 1) == 2
                ),
                "both field-curve panels were never painted",
            )

        self.assertEqual(len(dialog.figure.axes), 2)
        self.assertTrue(seen)

    def test_the_field_range_comes_from_the_sensor_not_a_hardcoded_20_degrees(self):
        from openlens.aberrations import AberrationsCalculator
        from openlens.gui.dialogs import analysis_plots
        from openlens.optical_system import OpticalSystem

        seen = []
        self.tab._perf_sensor_size.setValue(12.0)

        def _curvature(*args, **kwargs):
            seen.append(kwargs)
            return [0.0], [0.0], [0.0]

        def _distortion(*args, **kwargs):
            return [0.0], [0.0]

        with mock.patch.object(
            AberrationsCalculator, "calculate_field_curvature", new=_curvature
        ), mock.patch.object(
            AberrationsCalculator, "calculate_distortion_curve", new=_distortion
        ), mock.patch.object(
            analysis_plots.AnalysisPlotDialog, "exec", lambda self: 0
        ):
            self.tab._on_show_field_curves()
            self.assertTrue(_run_until(lambda: bool(seen)))

        system = OpticalSystem(name=self.lens.name)
        system.add_lens(self.lens)
        expected = math.degrees(math.atan((12.0 / 2.0) / system.get_system_focal_length()))
        self.assertAlmostEqual(seen[0]["max_field_angle_deg"], expected, places=3)
        self.assertNotAlmostEqual(
            seen[0]["max_field_angle_deg"],
            20.0,
            places=3,
            msg="field curves still use the hardcoded 20 degree field",
        )


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 not available")
class TestMetricsRunOffTheGuiThread(_AsyncTabFixture):
    def test_the_handler_returns_before_the_metrics_finish(self):
        from openlens.aberrations import AberrationsCalculator

        gate = self._event()
        started = threading.Event()
        results = {"f_number": 2.8, "spherical": 0.01}

        with mock.patch.object(
            AberrationsCalculator,
            "calculate_all_aberrations",
            new=_blocked(results, gate, started),
        ):
            self.assert_returns_before_compute(
                self.tab._on_calculate_performance_metrics, started, gate
            )
            self.assertIn(
                "calculating",
                self.tab._perf_metrics_text.toPlainText().lower(),
                msg="the tab never told the user the analysis had started",
            )
            self.assertTrue(
                _run_until(
                    lambda: "OPTICAL PERFORMANCE METRICS"
                    in self.tab._perf_metrics_text.toPlainText()
                ),
                "the report was never painted after the worker finished",
            )
            self.assertTrue(_run_until(self._metrics_finished))

        self.assertIsNotNone(self.tab._cached_metrics_text)
        self.assertEqual(self.tab._cached_metrics.get("f_number"), 2.8)
        self.assertIs(self.tab._cached_metrics_for, self.lens)
        self.assertIsNone(self.tab._metrics_worker)

    def test_a_second_click_while_calculating_does_not_start_another_trace(self):
        from openlens.aberrations import AberrationsCalculator

        gate = self._event()
        started = threading.Event()
        calls = []

        def _aberrations(*args, **kwargs):
            calls.append(1)
            started.set()
            gate.wait(1.0)
            return {"f_number": 2.8}

        with mock.patch.object(
            AberrationsCalculator, "calculate_all_aberrations", new=_aberrations
        ):
            self.tab._on_calculate_performance_metrics()
            self.assertTrue(_run_until(started.is_set))
            self.tab._on_calculate_performance_metrics()
            gate.set()
            self.assertTrue(_run_until(self._metrics_finished))

        self.assertEqual(calls, [1])

    def test_an_edit_during_the_calculation_is_not_painted_as_current(self):
        from openlens.aberrations import AberrationsCalculator

        gate = self._event()
        started = threading.Event()

        with mock.patch.object(
            AberrationsCalculator,
            "calculate_all_aberrations",
            new=_blocked({"f_number": 2.8}, gate, started),
        ):
            self.tab._on_calculate_performance_metrics()
            self.assertTrue(_run_until(started.is_set))
            self.lens.radius_of_curvature_1 = 30.0
            gate.set()
            self.assertTrue(_run_until(self._metrics_finished))

        text = self.tab._perf_metrics_text.toPlainText()
        self.assertNotIn(
            "OPTICAL PERFORMANCE METRICS",
            text,
            msg="the report describes the design from before the edit",
        )
        self.assertIn("changed", text.lower())
        self.assertIsNone(self.tab._cached_metrics_text)


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 not available")
class TestImageSimulationIsOffTheGuiThread(unittest.TestCase):
    def setUp(self):
        _ensure_app()
        from openlens.gui.dialogs.image_sim import ImageSimulationDialog
        from openlens.optical_system import OpticalSystem

        system = OpticalSystem(name="Image Test")
        system.add_lens(_lens())
        self.dialog = ImageSimulationDialog(system, None)
        self.dialog._original_image = np.zeros((8, 8, 3))
        self._gates = []
        self.addCleanup(self._cleanup)

    def _cleanup(self):
        for gate in self._gates:
            gate.set()
        worker = getattr(self.dialog, "_pending_worker", None)
        if worker is not None:
            worker.wait(5000)
        self.dialog.close()
        self.dialog.deleteLater()

    def _start_blocked_simulation(self):
        from openlens.analysis.psf_mtf import ImageQualityAnalyzer

        gate = threading.Event()
        self._gates.append(gate)
        started = threading.Event()
        simulated = np.ones((8, 8, 3))

        def _simulate(*args, **kwargs):
            started.set()
            gate.wait(1.0)
            return simulated

        patcher = mock.patch.object(ImageQualityAnalyzer, "simulate_image", new=_simulate)
        patcher.start()
        self.addCleanup(patcher.stop)
        return gate, started, simulated

    def test_the_handler_returns_before_the_simulation_finishes(self):
        from openlens.gui.dialogs import image_sim

        gate, started, simulated = self._start_blocked_simulation()

        with mock.patch.object(image_sim.ImageSimulationDialog, "exec", lambda self: 0):
            began = time.monotonic()
            self.dialog._on_run_simulation()
            elapsed = time.monotonic() - began

        self.assertLess(
            elapsed,
            0.7,
            msg=f"the handler blocked for {elapsed:.2f}s: simulate_image ran on " "the GUI thread",
        )
        self.assertTrue(_run_until(started.is_set, timeout_ms=5000))
        worker = self.dialog._pending_worker
        self.assertIsNotNone(worker, "the simulation did not run in a worker")
        self.assertEqual(self.dialog._ax_sim.get_title(), "Calculating Simulation...")

        gate.set()
        self.assertTrue(
            _run_until(lambda: self.dialog._simulated_image is not None),
            "the simulated image was never painted",
        )
        self.assertTrue(np.array_equal(self.dialog._simulated_image, simulated))
        self.assertTrue(_run_until(worker.isFinished))

    def test_closing_the_dialog_stops_a_running_simulation(self):
        from openlens.gui.dialogs import image_sim

        gate, started, _ = self._start_blocked_simulation()
        self.dialog._on_run_simulation()
        self.assertTrue(_run_until(started.is_set, timeout_ms=5000))
        worker = self.dialog._pending_worker
        self.assertIsNotNone(worker)

        with mock.patch("openlens.gui.dialogs.image_sim.stop_worker", return_value=True) as stopped:
            self.dialog.close()

        stopped.assert_called_once_with(
            worker, image_sim.ImageSimulationDialog._WORKER_STOP_TIMEOUT_MS
        )
        self.assertIsNone(
            self.dialog._pending_worker,
            "the stopped worker's reference was kept",
        )
        gate.set()
        self.assertTrue(_run_until(worker.isFinished))

    def test_closing_keeps_the_reference_when_the_worker_will_not_stop(self):
        """Dropping a live QThread's last reference aborts the process."""
        gate, started, _ = self._start_blocked_simulation()
        self.dialog._on_run_simulation()
        self.assertTrue(_run_until(started.is_set, timeout_ms=5000))
        worker = self.dialog._pending_worker

        with mock.patch("openlens.gui.dialogs.image_sim.stop_worker", return_value=False):
            self.dialog.close()

        self.assertIs(
            self.dialog._pending_worker,
            worker,
            msg="the reference was dropped while the thread was still running",
        )
        gate.set()
        self.assertTrue(_run_until(worker.isFinished))
        self.dialog._pending_worker = None

    def test_accepting_the_dialog_stops_a_running_simulation(self):
        """The Close button calls accept(), which does not send a closeEvent."""
        gate, started, _ = self._start_blocked_simulation()
        self.dialog._on_run_simulation()
        self.assertTrue(_run_until(started.is_set, timeout_ms=5000))
        worker = self.dialog._pending_worker

        with mock.patch("openlens.gui.dialogs.image_sim.stop_worker", return_value=True) as stopped:
            self.dialog.accept()

        stopped.assert_called_once()
        self.assertIsNone(self.dialog._pending_worker)
        gate.set()
        self.assertTrue(_run_until(worker.isFinished))


if __name__ == "__main__":
    unittest.main()
