#!/usr/bin/env python3
"""Temperature conditioning for the simulation tab (#10).

The analyser already had an environmental model (thermal expansion + Schott
dn/dT + air index), but nothing in the GUI used it. These tests pin the
domain conditioning for a lens and a system, the Celsius/0 K controls, and
the simulation path that traces the conditioned target without mutating the
stored model.
"""

import math
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

from openlens.analysis.environmental import EnvironmentalAnalyzer
from openlens.constants import (
    ABSOLUTE_ZERO_C,
    DEFAULT_TEMPERATURE,
    WAVELENGTH_GREEN,
    WAVELENGTH_RED,
)
from openlens.lens import Lens
from openlens.material_database import get_material_database
from openlens.optical_system import OpticalSystem
from openlens.validation import ValidationError


def _lens(material="BK7", **kwargs):
    parameters = dict(
        name=f"{material} lens",
        radius_of_curvature_1=100.0,
        radius_of_curvature_2=-100.0,
        thickness=5.0,
        diameter=40.0,
        material=material,
    )
    parameters.update(kwargs)
    return Lens(**parameters)


class TestTemperatureConditioning(unittest.TestCase):
    def test_reference_temperature_returns_the_same_model(self):
        lens = _lens()

        conditioned = EnvironmentalAnalyzer.condition_at_temperature(lens, DEFAULT_TEMPERATURE)

        self.assertIs(conditioned, lens)

    def test_hot_lens_expands_geometry_and_sets_temperature(self):
        lens = _lens()
        alpha = get_material_database().get_material("BK7").thermal_expansion
        scaling = 1.0 + alpha * 100.0

        hot = EnvironmentalAnalyzer.condition_at_temperature(lens, 120.0)

        self.assertIsNot(hot, lens)
        self.assertAlmostEqual(hot.radius_of_curvature_1, 100.0 * scaling, places=9)
        self.assertAlmostEqual(hot.radius_of_curvature_2, -100.0 * scaling, places=9)
        self.assertAlmostEqual(hot.thickness, 5.0 * scaling, places=9)
        self.assertAlmostEqual(hot.diameter, 40.0 * scaling, places=9)
        self.assertEqual(hot.temperature, 120.0)

        # The stored model must survive a simulation untouched.
        self.assertEqual(lens.radius_of_curvature_1, 100.0)
        self.assertEqual(lens.thickness, 5.0)
        self.assertEqual(lens.temperature, DEFAULT_TEMPERATURE)

    def test_index_change_follows_the_material(self):
        database = get_material_database()
        changes = {}
        for material in ("BK7", "SF11"):
            cold = _lens(material)
            hot = EnvironmentalAnalyzer.condition_at_temperature(cold, 120.0)
            changes[material] = hot.refractive_index - cold.refractive_index
            self.assertAlmostEqual(
                hot.refractive_index,
                database.get_refractive_index(material, cold.wavelength, 120.0),
                places=12,
            )

        self.assertGreater(changes["SF11"], changes["BK7"])
        self.assertNotAlmostEqual(changes["BK7"], changes["SF11"], places=6)

    def test_system_expands_gaps_and_positions(self):
        system = OpticalSystem("Two elements")
        first = _lens("BK7", name="First", thickness=5.0)
        second = _lens("SF11", name="Second", thickness=4.0)
        system.add_lens(first)
        system.add_lens(second, air_gap_before=10.0)

        hot = EnvironmentalAnalyzer.condition_at_temperature(system, 120.0)

        self.assertIsNot(hot, system)
        self.assertAlmostEqual(
            hot.air_gaps[0].thickness,
            10.0 * (1.0 + EnvironmentalAnalyzer.DEFAULT_HOUSING_CTE * 100.0),
            places=9,
        )
        for element in hot.elements:
            self.assertEqual(element.lens.temperature, 120.0)
        self.assertAlmostEqual(
            hot.elements[1].position,
            hot.elements[0].lens.thickness + hot.air_gaps[0].thickness,
            places=9,
        )

        self.assertEqual(system.air_gaps[0].thickness, 10.0)
        self.assertEqual(system.elements[0].lens.temperature, DEFAULT_TEMPERATURE)

    def test_custom_glass_keeps_its_index_but_still_expands(self):
        custom = Lens(
            name="Custom",
            radius_of_curvature_1=100.0,
            radius_of_curvature_2=-100.0,
            thickness=5.0,
            diameter=40.0,
            material="Custom",
            refractive_index=1.7,
        )

        hot = EnvironmentalAnalyzer.condition_at_temperature(custom, 120.0)

        self.assertEqual(hot.refractive_index, 1.7)
        self.assertGreater(hot.radius_of_curvature_1, custom.radius_of_curvature_1)

    def test_absolute_zero_is_allowed_and_finite(self):
        lens = _lens()

        self.assertEqual(
            EnvironmentalAnalyzer.calculate_air_index(550.0, ABSOLUTE_ZERO_C, 1.0),
            1.0,
        )
        cold = EnvironmentalAnalyzer.condition_at_temperature(lens, ABSOLUTE_ZERO_C)

        self.assertEqual(cold.temperature, ABSOLUTE_ZERO_C)
        self.assertTrue(math.isfinite(cold.refractive_index))
        self.assertTrue(math.isfinite(cold.radius_of_curvature_1))

    def test_below_absolute_zero_is_rejected(self):
        with self.assertRaises(ValidationError):
            EnvironmentalAnalyzer.condition_at_temperature(_lens(), ABSOLUTE_ZERO_C - 0.01)


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 not available")
class TestSimulationTemperatureControls(unittest.TestCase):
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

    def test_control_is_celsius_with_absolute_zero_as_the_floor(self):
        control = self.tab._sim_temperature

        self.assertEqual(control.value(), DEFAULT_TEMPERATURE)
        self.assertEqual(control.minimum(), ABSOLUTE_ZERO_C)
        self.assertIn("°C", control.suffix())
        self.assertNotIn("F", control.suffix())

        control.setValue(-400.0)

        self.assertEqual(control.value(), ABSOLUTE_ZERO_C)

    def test_run_traces_the_live_model_with_a_conditioner(self):
        from openlens.gui.widgets.simulation_viz import SimulationVisualizationWidget

        calls = []

        class _Recording(SimulationVisualizationWidget):
            def run_simulation(self, *args, **kwargs):
                calls.append((args, kwargs))

        lens = _lens()
        self.parent._current_lens = lens
        self.tab._sim_viz = _Recording(self.tab)
        self.tab._sim_temperature.setValue(120.0)

        self.tab._on_run_simulation()

        # The widget gets the live model; the environment is applied at trace
        # time, so a later edit of the lens is not silently discarded.
        target = calls[-1][0][0]
        self.assertIs(target, lens)

        conditioner = calls[-1][1]["conditioner"]
        conditioned = conditioner(lens)
        self.assertIsNot(conditioned, lens)
        self.assertEqual(conditioned.temperature, 120.0)
        self.assertGreater(conditioned.radius_of_curvature_1, lens.radius_of_curvature_1)
        # The stored model is never mutated.
        self.assertEqual(lens.temperature, DEFAULT_TEMPERATURE)
        self.assertEqual(calls[-1][1]["wavelengths"], [WAVELENGTH_GREEN])

    def test_reference_temperature_traces_the_stored_lens(self):
        from openlens.gui.widgets.simulation_viz import SimulationVisualizationWidget

        calls = []

        class _Recording(SimulationVisualizationWidget):
            def run_simulation(self, *args, **kwargs):
                calls.append((args, kwargs))

        lens = _lens()
        self.parent._current_lens = lens
        self.tab._sim_viz = _Recording(self.tab)

        self.tab._on_run_simulation()

        self.assertIs(calls[-1][0][0], lens)

    def test_run_traces_a_conditioned_system_for_an_assembly(self):
        from openlens.gui.widgets.simulation_viz import SimulationVisualizationWidget

        calls = []

        class _Recording(SimulationVisualizationWidget):
            def run_simulation(self, *args, **kwargs):
                calls.append((args, kwargs))

        system = OpticalSystem("Assembly")
        system.add_lens(_lens("BK7", name="First"))
        system.add_lens(_lens("SF11", name="Second"), air_gap_before=8.0)
        self.parent._current_assembly = system
        self.tab._sim_viz = _Recording(self.tab)
        self.tab._sim_temperature.setValue(120.0)

        self.tab._on_run_simulation()

        target = calls[-1][0][0]
        self.assertIsInstance(target, OpticalSystem)
        self.assertIs(target, system)

        conditioned = calls[-1][1]["conditioner"](system)
        self.assertIsNot(conditioned, system)
        self.assertEqual(
            [element.lens.temperature for element in conditioned.elements], [120.0, 120.0]
        )
        self.assertEqual(system.elements[0].lens.temperature, DEFAULT_TEMPERATURE)

    def test_a_hot_simulation_changes_the_traced_path(self):
        lens = _lens()
        self.parent._current_lens = lens

        self.tab._sim_temperature.setValue(DEFAULT_TEMPERATURE)
        self.tab._on_run_simulation()
        cold_path = [tuple(point) for point in self.tab._sim_viz._rays[0].path]

        self.tab._sim_temperature.setValue(200.0)
        self.tab._on_run_simulation()
        hot_path = [tuple(point) for point in self.tab._sim_viz._rays[0].path]

        self.assertNotEqual(cold_path, hot_path)

    def test_temperature_combines_with_multiple_wavelengths(self):
        from openlens.gui.tabs.simulation_tab import SIMULATION_WAVELENGTHS

        lens = _lens("SF11")
        self.parent._current_lens = lens
        self.tab._sim_temperature.setValue(120.0)
        self.tab._sim_wavelength.setCurrentIndex(
            next(
                index
                for index, (nm, _label) in enumerate(SIMULATION_WAVELENGTHS)
                if nm == WAVELENGTH_RED
            )
        )
        self.tab._add_wavelength()

        self.tab._on_run_simulation()

        # The widget holds the live lens; the temperature reaches the trace
        # through the conditioner.
        conditioned = self.tab._sim_viz._conditioner(self.tab._sim_viz._lens)
        self.assertEqual(conditioned.temperature, 120.0)
        self.assertEqual(len(self.tab._sim_viz._ray_groups), 2)


if __name__ == "__main__":
    unittest.main()
