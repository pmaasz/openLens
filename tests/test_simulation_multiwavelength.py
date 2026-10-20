#!/usr/bin/env python3
"""Multi-wavelength simulation and white light (#72).

The simulation picker already put a wavelength on each ``Ray``, but the
tracers cached ``lens.refractive_index`` and ignored it, so every wavelength
followed the same path. These tests pin the wavelength-resolved index in the
tracers, the multi-trace visualization groups, and the tab's wavelength list.
"""

import os
import sys
import unittest

if os.environ.get("DISPLAY", "") == "" and sys.platform.startswith("linux"):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication, QWidget

    PYSIDE_AVAILABLE = True
except ImportError:  # pragma: no cover - environment guard
    QApplication = None
    QWidget = None
    PYSIDE_AVAILABLE = False

if PYSIDE_AVAILABLE:
    _app = QApplication.instance() or QApplication(sys.argv)

from openlens.constants import NM_TO_MM, WAVELENGTH_BLUE, WAVELENGTH_GREEN, WAVELENGTH_RED
from openlens.lens import Lens
from openlens.optical_system import create_doublet
from openlens.ray import Ray
from openlens.ray_tracer import LensRayTracer, SystemRayTracer


def _flint_lens():
    return Lens(
        name="Flint",
        radius_of_curvature_1=60.0,
        radius_of_curvature_2=-60.0,
        thickness=6.0,
        diameter=30.0,
        material="SF11",
    )


class TestTracersUseTheWavelength(unittest.TestCase):
    def setUp(self):
        self.lens = _flint_lens()

    def test_default_tracer_keeps_the_stored_index(self):
        tracer = LensRayTracer(self.lens)

        self.assertAlmostEqual(tracer.n, self.lens.refractive_index, places=12)

    def test_wavelength_selects_the_dispersive_index(self):
        blue = LensRayTracer(self.lens, wavelength_nm=486.1)
        red = LensRayTracer(self.lens, wavelength_nm=656.3)

        self.assertAlmostEqual(blue.n, self.lens.refractive_index_at(486.1), places=12)
        self.assertAlmostEqual(red.n, self.lens.refractive_index_at(656.3), places=12)
        self.assertGreater(blue.n, red.n, "normal dispersion should raise blue's index")

    def test_system_tracer_propagates_the_wavelength_to_every_element(self):
        system = create_doublet(focal_length=100.0, diameter=40.0)

        tracer = SystemRayTracer(system, wavelength_nm=486.1)

        self.assertEqual(len(tracer._tracers), len(system.elements))
        for element, element_tracer in zip(system.elements, tracer._tracers):
            self.assertAlmostEqual(
                element_tracer.n,
                element.lens.refractive_index_at(486.1),
                places=12,
            )

    def test_different_wavelengths_follow_different_paths(self):
        def exit_angle(wavelength):
            tracer = LensRayTracer(self.lens, wavelength_nm=wavelength)
            ray = Ray(-100.0, 5.0, angle_rad=0.0, wavelength_mm=wavelength * NM_TO_MM)
            tracer.trace_ray(ray)
            return ray.angle

        blue = exit_angle(486.1)
        red = exit_angle(656.3)

        self.assertNotAlmostEqual(
            blue,
            red,
            places=6,
            msg="both wavelengths refracted identically; the tracer ignored dispersion",
        )


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 not available")
class TestMultiWavelengthVisualization(unittest.TestCase):
    def setUp(self):
        from openlens.gui.widgets.simulation_viz import SimulationVisualizationWidget

        self.lens = _flint_lens()
        self.widget = SimulationVisualizationWidget()
        self.addCleanup(self.widget.deleteLater)

    def test_each_wavelength_gets_its_own_ray_group_and_colour(self):
        self.widget.run_simulation(
            self.lens, num_rays=3, wavelengths=[WAVELENGTH_BLUE, WAVELENGTH_RED]
        )

        self.assertEqual(self.widget._wavelengths, [WAVELENGTH_BLUE, WAVELENGTH_RED])
        self.assertEqual(len(self.widget._ray_groups), 2)
        self.assertEqual(len(self.widget._rays), 6)

        colours = []
        for wavelength, (colour, group) in zip(self.widget._wavelengths, self.widget._ray_groups):
            colours.append(colour.name())
            self.assertEqual(len(group), 3)
            for ray in group:
                self.assertAlmostEqual(ray.wavelength, wavelength * NM_TO_MM, places=12)

        self.assertEqual(len(set(colours)), 2, f"groups share one colour: {colours}")

    def test_duplicate_wavelengths_are_traced_once(self):
        self.widget.run_simulation(
            self.lens, num_rays=2, wavelengths=[WAVELENGTH_GREEN, WAVELENGTH_GREEN]
        )

        self.assertEqual(self.widget._wavelengths, [WAVELENGTH_GREEN])
        self.assertEqual(len(self.widget._ray_groups), 1)

    def test_single_wavelength_calls_still_work(self):
        self.widget.run_simulation(self.lens, num_rays=3, wavelength=WAVELENGTH_RED)

        self.assertEqual(self.widget._wavelengths, [WAVELENGTH_RED])
        self.assertEqual(self.widget._wavelength, WAVELENGTH_RED)
        self.assertEqual(len(self.widget._ray_groups), 1)
        self.assertEqual(len(self.widget._rays), 3)

    def test_refresh_retraces_every_selected_wavelength(self):
        self.widget.run_simulation(
            self.lens, num_rays=3, wavelengths=[WAVELENGTH_BLUE, WAVELENGTH_RED]
        )
        before = [
            [tuple(ray.path[-1]) for ray in group] for _colour, group in self.widget._ray_groups
        ]

        self.lens.thickness = 12.0
        self.widget.refresh()

        self.assertEqual(self.widget._wavelengths, [WAVELENGTH_BLUE, WAVELENGTH_RED])
        self.assertEqual(len(self.widget._ray_groups), 2)
        after = [
            [tuple(ray.path[-1]) for ray in group] for _colour, group in self.widget._ray_groups
        ]
        self.assertNotEqual(after, before, "refresh did not re-trace the wavelength groups")


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 not available")
class TestSimulationTabWavelengthSelection(unittest.TestCase):
    def setUp(self):
        from openlens.gui.tabs.simulation_tab import SimulationTab

        class _Parent(QWidget):
            def __init__(self):
                super().__init__()
                self._current_assembly = None
                self._current_lens = None

        self.parent = _Parent()
        self.addCleanup(self.parent.deleteLater)
        self.tab = SimulationTab(self.parent)
        self.addCleanup(self.tab.deleteLater)

    def _select_preset(self, wavelength):
        from openlens.gui.tabs.simulation_tab import SIMULATION_WAVELENGTHS

        index = next(
            index
            for index, (nanometres, _label) in enumerate(SIMULATION_WAVELENGTHS)
            if abs(nanometres - wavelength) < 1e-9
        )
        self.tab._sim_wavelength.setCurrentIndex(index)

    def test_the_default_selection_is_photopic_green(self):
        self.assertEqual(self.tab._selected_wavelengths(), [WAVELENGTH_GREEN])

    def test_presets_can_be_added_and_removed(self):
        self._select_preset(WAVELENGTH_RED)

        self.tab._add_wavelength()

        self.assertEqual(self.tab._selected_wavelengths(), [WAVELENGTH_GREEN, WAVELENGTH_RED])

        row = self.tab._sim_wavelengths.currentRow()
        self.tab._remove_wavelength()

        self.assertEqual(self.tab._selected_wavelengths(), [WAVELENGTH_GREEN])
        self.assertEqual(self.tab._sim_wavelengths.count(), 1)
        self.assertGreaterEqual(row, 0)

    def test_the_same_wavelength_is_not_added_twice(self):
        self._select_preset(WAVELENGTH_GREEN)

        self.tab._add_wavelength()

        self.assertEqual(self.tab._sim_wavelengths.count(), 1)
        self.assertEqual(self.tab._selected_wavelengths(), [WAVELENGTH_GREEN])

    def test_a_custom_wavelength_can_be_added(self):
        from openlens.gui.tabs.simulation_tab import CUSTOM_WAVELENGTH_INDEX

        self.tab._sim_wavelength.setCurrentIndex(CUSTOM_WAVELENGTH_INDEX)
        self.tab._sim_custom_wavelength.setValue(532.0)

        self.tab._add_wavelength()

        self.assertEqual(self.tab._selected_wavelengths(), [532.0, WAVELENGTH_GREEN])

    def test_white_light_replaces_the_list_with_a_spectrum_and_restores_it(self):
        from openlens.gui.tabs.simulation_tab import WHITE_LIGHT_WAVELENGTHS

        self._select_preset(WAVELENGTH_RED)
        self.tab._add_wavelength()

        self.tab._sim_white_light.setChecked(True)

        self.assertEqual(self.tab._selected_wavelengths(), list(WHITE_LIGHT_WAVELENGTHS))
        self.assertFalse(self.tab._sim_wavelengths.isEnabled())

        self.tab._sim_white_light.setChecked(False)

        self.assertEqual(self.tab._selected_wavelengths(), [WAVELENGTH_GREEN, WAVELENGTH_RED])
        self.assertTrue(self.tab._sim_wavelengths.isEnabled())

    def test_white_light_spectrum_is_visible_sorted_and_unique(self):
        from openlens.gui.tabs.simulation_tab import WHITE_LIGHT_WAVELENGTHS

        self.assertGreaterEqual(len(WHITE_LIGHT_WAVELENGTHS), 5)
        self.assertEqual(list(WHITE_LIGHT_WAVELENGTHS), sorted(set(WHITE_LIGHT_WAVELENGTHS)))
        self.assertGreaterEqual(min(WHITE_LIGHT_WAVELENGTHS), 400.0)
        self.assertLessEqual(max(WHITE_LIGHT_WAVELENGTHS), 700.0)

    def test_run_passes_every_selected_wavelength_to_the_view(self):
        from openlens.gui.widgets.simulation_viz import SimulationVisualizationWidget

        calls = []

        class _Recording(SimulationVisualizationWidget):
            def run_simulation(self, *args, **kwargs):
                calls.append((args, kwargs))

        self.parent._current_lens = _flint_lens()
        self.tab._sim_viz = _Recording(self.tab)
        self._select_preset(WAVELENGTH_RED)
        self.tab._add_wavelength()

        self.tab._on_run_simulation()

        self.assertEqual(calls[-1][1]["wavelengths"], [WAVELENGTH_GREEN, WAVELENGTH_RED])

    def test_run_passes_the_white_light_spectrum(self):
        from openlens.gui.tabs.simulation_tab import WHITE_LIGHT_WAVELENGTHS
        from openlens.gui.widgets.simulation_viz import SimulationVisualizationWidget

        calls = []

        class _Recording(SimulationVisualizationWidget):
            def run_simulation(self, *args, **kwargs):
                calls.append((args, kwargs))

        self.parent._current_lens = _flint_lens()
        self.tab._sim_viz = _Recording(self.tab)
        self.tab._sim_white_light.setChecked(True)

        self.tab._on_run_simulation()

        self.assertEqual(calls[-1][1]["wavelengths"], list(WHITE_LIGHT_WAVELENGTHS))


if __name__ == "__main__":
    unittest.main()
