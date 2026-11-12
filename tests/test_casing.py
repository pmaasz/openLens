#!/usr/bin/env python3
"""Lens casings: model, persistence, validation, tracing and thermal effects (#3)."""

import math
import os
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from openlens.analysis.environmental import EnvironmentalAnalyzer
from openlens.casing import Casing, validate_casing
from openlens.database import DatabaseManager
from openlens.lens import Lens
from openlens.mechanical_materials import (
    MechanicalMaterialCatalog,
    get_mechanical_material_catalog,
)
from openlens.optical_system import OpticalSystem
from openlens.ray import Ray, Ray3D
from openlens.tracer_2d import SystemRayTracer
from openlens.tracer_3d import SystemRayTracer3D
from openlens.validation import ValidationError
from openlens.vector3 import vec3


def _lens(name: str = "Lens", diameter: float = 20.0) -> Lens:
    return Lens(
        name=name,
        radius_of_curvature_1=50.0,
        radius_of_curvature_2=-50.0,
        thickness=5.0,
        diameter=diameter,
        refractive_index=1.5168,
    )


def _system(gap: float = 5.0) -> OpticalSystem:
    system = OpticalSystem(name="Cased")
    system.add_lens(_lens("Front"))
    system.add_lens(_lens("Back"), air_gap_before=gap)
    return system


def _casing(bore: float = 20.0, start: float = 0.0, end: float = 100.0) -> Casing:
    return Casing(
        material="Aluminium",
        bore_diameter=bore,
        wall_thickness=2.0,
        start_x=start,
        end_x=end,
    )


class TestCasingModel(unittest.TestCase):
    def test_default_casing_is_valid(self):
        casing = Casing()
        self.assertEqual(casing.inner_radius, 25.0)
        self.assertEqual(casing.outer_diameter, 54.0)
        self.assertEqual(casing.length, 100.0)

    def test_closed_end_is_rejected(self):
        with self.assertRaisesRegex(ValidationError, "open at both ends"):
            Casing(start_x=10.0, end_x=10.0)
        with self.assertRaisesRegex(ValidationError, "open at both ends"):
            Casing(start_x=10.0, end_x=5.0)

    def test_non_positive_dimensions_are_rejected(self):
        with self.assertRaisesRegex(ValidationError, "bore must be positive"):
            Casing(bore_diameter=0.0)
        with self.assertRaisesRegex(ValidationError, "wall thickness must be positive"):
            Casing(wall_thickness=-1.0)

    def test_non_finite_dimensions_are_rejected(self):
        with self.assertRaisesRegex(ValidationError, "must be finite"):
            Casing(bore_diameter=math.inf)
        with self.assertRaisesRegex(ValidationError, "must be finite"):
            Casing(end_x=math.nan)

    def test_blank_material_is_rejected(self):
        with self.assertRaisesRegex(ValidationError, "material"):
            Casing(material="")

    def test_bore_smaller_than_a_lens_is_rejected(self):
        system = _system()
        casing = _casing(bore=15.0)
        with self.assertRaisesRegex(ValidationError, "cut into the lens"):
            system.set_casing(casing)
        self.assertIsNone(system.casing)

    def test_casing_clear_of_the_stack_is_accepted(self):
        system = _system()
        casing = _casing(bore=25.0)
        system.set_casing(casing)
        self.assertIs(system.casing, casing)
        system.clear_casing()
        self.assertIsNone(system.casing)

    def test_casing_must_not_become_the_aperture_stop(self):
        system = _system()
        system.set_aperture_stop(0, 24.0)
        with self.assertRaisesRegex(ValidationError, "aperture stop"):
            validate_casing(_casing(bore=22.0), system)

    def test_lens_outside_the_casing_does_not_constrain_the_bore(self):
        system = _system()
        system.elements[1].position = 200.0
        system.elements[1].lens.diameter = 60.0
        validate_casing(_casing(bore=20.0, end=50.0), system)
        system.set_casing(_casing(bore=20.0, end=50.0))

        self.assertIsNone(system.casing_warning())


class TestCasingPersistence(unittest.TestCase):
    def test_dict_round_trip(self):
        system = _system()
        system.set_casing(_casing(bore=24.0, start=-5.0, end=80.0))

        restored = OpticalSystem.from_dict(system.to_dict())

        self.assertEqual(restored.casing, system.casing)

    def test_absent_casing_round_trips_as_none(self):
        system = _system()
        restored = OpticalSystem.from_dict(system.to_dict())
        self.assertIsNone(restored.casing)

    def test_sqlite_round_trip(self):
        system = _system()
        system.set_casing(_casing(bore=24.0, start=-5.0, end=80.0))
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            path = tmp.name
        try:
            db = DatabaseManager(path)
            db.save_assembly(system.to_dict())
            rows = [row for row in db.load_all() if row.get("row_type") == "OpticalSystem"]
            restored = OpticalSystem.from_dict(rows[0])
        finally:
            os.remove(path)

        self.assertEqual(restored.casing, system.casing)


class TestCasingRayTracing(unittest.TestCase):
    def setUp(self):
        self.system = _system()
        self.system.set_casing(_casing(bore=20.0, start=0.0, end=100.0))

    def test_ray_inside_the_bore_passes(self):
        ray = Ray(x=-10, y=0, angle_rad=0.0)
        SystemRayTracer(self.system).trace_ray(ray)
        self.assertFalse(ray.absorbed)
        self.assertFalse(ray.terminated)

    def test_ray_crossing_the_wall_is_absorbed_2d(self):
        ray = Ray(x=-10, y=15, angle_rad=0.0)
        SystemRayTracer(self.system).trace_ray(ray)
        self.assertTrue(ray.absorbed)
        self.assertTrue(ray.terminated)
        self.assertEqual(ray.path[-1], (0.0, 15.0))

    def test_ray_crossing_the_wall_is_absorbed_3d(self):
        ray = Ray3D(origin=vec3(-10, 15, 0), direction=vec3(1, 0, 0))
        SystemRayTracer3D(self.system).trace_ray(ray)
        self.assertTrue(ray.absorbed)
        self.assertTrue(ray.terminated)

    def test_ray_inside_the_bore_passes_3d(self):
        ray = Ray3D(origin=vec3(-10, 0, 0), direction=vec3(1, 0, 0))
        SystemRayTracer3D(self.system).trace_ray(ray)
        self.assertFalse(ray.absorbed)
        self.assertFalse(ray.terminated)

    def test_casing_lowers_throughput(self):
        cased = SystemRayTracer(self.system).trace_parallel_rays(num_rays=9, angle_deg=10.0)
        uncased_system = _system()
        uncased = SystemRayTracer(uncased_system).trace_parallel_rays(num_rays=9, angle_deg=10.0)
        absorbed = sum(1 for ray in cased if ray.absorbed)
        self.assertGreater(absorbed, 0)
        self.assertEqual(sum(1 for ray in uncased if ray.absorbed), 0)


class TestOpaqueMaterialFlag(unittest.TestCase):
    """The custom material's "opaque inner wall" flag decides absorption."""

    def setUp(self):
        self.catalog = get_mechanical_material_catalog()
        self.material = "Clear Resin (test)"
        self.catalog.add_custom_material(self.material, 60e-6, 1.2, opaque=False)
        self.system = OpticalSystem(name="Transparent casing")
        self.system.add_lens(
            Lens(
                name="Concave",
                radius_of_curvature_1=-50.0,
                radius_of_curvature_2=50.0,
                thickness=5.0,
                diameter=20.0,
                refractive_index=1.5168,
            )
        )
        casing = _casing(bore=20.0)
        casing.material = self.material
        self.system.set_casing(casing)

    def tearDown(self):
        self.catalog.remove_custom_material(self.material)

    def _trace_2d(self):
        ray = Ray(x=-10.0, y=5.0, angle_rad=0.0)
        SystemRayTracer(self.system).trace_ray(ray)
        return ray

    def _trace_3d(self):
        ray = Ray3D(origin=vec3(-10.0, 5.0, 0.0), direction=vec3(1.0, 0.0, 0.0))
        SystemRayTracer3D(self.system).trace_ray(ray)
        return ray

    def test_transparent_wall_does_not_absorb_after_the_lens_2d(self):
        """The concave lens sends the ray through the wall beyond the bore."""
        ray = self._trace_2d()
        self.assertFalse(ray.absorbed)
        self.assertTrue(ray.hit)
        self.assertGreater(ray.path[-1][0], 0.0)

    def test_opaque_wall_absorbs_after_the_lens_2d(self):
        self.system.casing.material = "Aluminium"
        self.assertTrue(self._trace_2d().absorbed)

    def test_transparent_wall_does_not_absorb_after_the_lens_3d(self):
        ray = self._trace_3d()
        self.assertFalse(ray.absorbed)

    def test_transparent_wall_does_not_absorb_before_the_lens_2d(self):
        ray = Ray(x=-10.0, y=15.0, angle_rad=0.0)
        SystemRayTracer(self.system).trace_ray(ray)
        self.assertFalse(ray.absorbed)

    def test_transparent_wall_does_not_absorb_before_the_lens_3d(self):
        ray = Ray3D(origin=vec3(-10.0, 15.0, 0.0), direction=vec3(1.0, 0.0, 0.0))
        SystemRayTracer3D(self.system).trace_ray(ray)
        self.assertFalse(ray.absorbed)


class TestCasingThermal(unittest.TestCase):
    def test_material_cte_scales_the_air_gap(self):
        steel = _system()
        steel.casing = _casing()
        steel.casing.material = "Steel"
        aluminium = _system()
        aluminium.casing = _casing()
        aluminium.casing.material = "Aluminium"

        hot_steel = EnvironmentalAnalyzer.condition_at_temperature(steel, 100.0)
        hot_aluminium = EnvironmentalAnalyzer.condition_at_temperature(aluminium, 100.0)

        self.assertLess(hot_steel.air_gaps[0].thickness, hot_aluminium.air_gaps[0].thickness)
        self.assertGreater(hot_steel.casing.bore_diameter, steel.casing.bore_diameter)
        self.assertAlmostEqual(hot_steel.casing.thermal_state_temperature, 100.0)

    def test_casing_cte_replaces_the_default_housing(self):
        cased = _system()
        cased.casing = _casing()
        cased.casing.material = "Titanium"
        uncased = _system()

        hot_cased = EnvironmentalAnalyzer.condition_at_temperature(cased, 100.0)
        hot_uncased = EnvironmentalAnalyzer.condition_at_temperature(uncased, 100.0)

        self.assertLess(hot_cased.air_gaps[0].thickness, hot_uncased.air_gaps[0].thickness)

    def test_explicit_housing_cte_still_wins(self):
        system = _system()
        system.casing = _casing()
        system.casing.material = "Titanium"

        explicit = EnvironmentalAnalyzer.apply_environment(system, 100.0, 1.0, housing_cte=0.0)

        self.assertAlmostEqual(explicit.air_gaps[0].thickness, system.air_gaps[0].thickness)

    def test_cold_casing_reports_mechanical_interference(self):
        system = _system()
        system.set_casing(_casing(bore=20.0))
        system.casing.material = "Titanium"

        cold = EnvironmentalAnalyzer.condition_at_temperature(system, -60.0)

        self.assertIsNone(system.casing_warning())
        self.assertIsNotNone(cold.casing_warning())
        self.assertIn("interference", cold.casing_warning().lower())


class TestMechanicalMaterialCatalog(unittest.TestCase):
    def test_custom_material_persists(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "mechanical_materials.json")
            catalog = MechanicalMaterialCatalog(path)
            catalog.add_custom_material("Invar", 1.2e-6, 8.1)
            catalog.save_custom_materials()

            reloaded = MechanicalMaterialCatalog(path)
            material = reloaded.get_material("Invar")

        self.assertIsNotNone(material)
        self.assertAlmostEqual(material["cte"], 1.2e-6)
        self.assertTrue(material["custom"])

    def test_standard_material_cannot_be_redefined(self):
        with tempfile.TemporaryDirectory() as directory:
            catalog = MechanicalMaterialCatalog(os.path.join(directory, "materials.json"))
            with self.assertRaisesRegex(ValueError, "standard material"):
                catalog.add_custom_material("aluminium", 1.0e-6, 2.7)

    def test_invalid_custom_material_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            catalog = MechanicalMaterialCatalog(os.path.join(directory, "materials.json"))
            with self.assertRaisesRegex(ValueError, "CTE"):
                catalog.add_custom_material("Bad", math.nan, 1.0)
            with self.assertRaisesRegex(ValueError, "Density"):
                catalog.add_custom_material("Bad", 1.0e-6, -1.0)


try:
    from PySide6.QtWidgets import QWidget

    from openlens.gui.tabs.assembly_tab import AssemblyTab
    from openlens.gui.tabs.simulation_tab import SimulationTab
    from openlens.gui.widgets.simulation_viz import SimulationVisualizationWidget

    HAS_PYSIDE = True
except ImportError:  # pragma: no cover - depends on install
    HAS_PYSIDE = False


if HAS_PYSIDE:

    class _Parent(QWidget):
        """Minimal window surface used by AssemblyTab."""

        def __init__(self, lenses):
            super().__init__()
            self._lenses = list(lenses)
            self._current_assembly = None
            self._current_lens = None
            self.status = []

        def _update_status(self, message):
            self.status.append(message)


@unittest.skipUnless(HAS_PYSIDE, "PySide6 is not installed")
class TestCasingEditor(unittest.TestCase):
    def setUp(self):
        from tests import ensure_qapp

        ensure_qapp()

    @staticmethod
    def _lenses():
        return [_lens("Front"), _lens("Back")]

    def _tab(self):
        from tests import flush_qt

        parent = _Parent(self._lenses())
        tab = AssemblyTab(parent)
        system = _system()
        tab.load_system(system)

        def _dispose():
            tab.close()
            tab.deleteLater()
            parent.close()
            parent.deleteLater()
            flush_qt()

        self.addCleanup(_dispose)
        return tab, system

    def test_toggle_adds_and_removes_the_casing_with_undo(self):
        tab, system = self._tab()
        self.assertIsNone(system.casing)
        tab._casing_check.setChecked(True)

        self.assertIsNotNone(system.casing)
        self.assertGreaterEqual(system.casing.bore_diameter, 20.0)
        self.assertTrue(tab._casing_check.isChecked())
        self.assertEqual(tab.undo_stack.count(), 1)

        tab.undo_stack.undo()
        self.assertIsNone(system.casing)
        self.assertFalse(tab._casing_check.isChecked())

        tab.undo_stack.redo()
        self.assertIsNotNone(system.casing)

    def test_apply_updates_the_casing(self):
        tab, system = self._tab()
        tab._casing_check.setChecked(True)
        tab._casing_bore_input.setValue(30.0)
        tab._casing_wall_input.setValue(3.0)
        tab._casing_start_input.setValue(-4.0)
        tab._casing_end_input.setValue(60.0)
        tab._on_casing_apply()

        self.assertEqual(system.casing.bore_diameter, 30.0)
        self.assertEqual(system.casing.wall_thickness, 3.0)
        self.assertEqual(system.casing.start_x, -4.0)
        self.assertEqual(system.casing.end_x, 60.0)

    def test_invalid_apply_keeps_the_previous_casing(self):
        tab, system = self._tab()
        tab._casing_check.setChecked(True)
        previous = system.casing
        tab._casing_end_input.setValue(tab._casing_start_input.value())

        tab._on_casing_apply()

        self.assertEqual(system.casing, previous)
        self.assertIn("open", tab._casing_status.text().lower())


@unittest.skipUnless(HAS_PYSIDE, "PySide6 is not installed")
class TestSimulationCasingReporting(unittest.TestCase):
    def setUp(self):
        from tests import ensure_qapp

        ensure_qapp()

    def _widget(self):
        from tests import flush_qt

        widget = SimulationVisualizationWidget()
        self.addCleanup(lambda: (widget.deleteLater(), flush_qt()))
        return widget

    def test_run_reports_absorbed_rays(self):
        system = _system()
        system.set_casing(_casing(bore=20.0, end=100.0))
        widget = self._widget()

        widget.run_simulation(system, 9, angle=10.0)

        self.assertEqual(widget.ray_count, 9)
        self.assertGreater(widget.absorbed_count, 0)
        self.assertIsNone(widget.casing_warning)

    def test_conditioned_run_reports_thermal_interference(self):
        system = _system()
        system.set_casing(_casing(bore=20.0))
        system.casing.material = "Titanium"
        widget = self._widget()

        def _cold(target):
            return EnvironmentalAnalyzer.condition_at_temperature(target, -60.0)

        widget.run_simulation(system, 5, angle=0.0, conditioner=_cold)

        self.assertIn("interference", widget.casing_warning.lower())


@unittest.skipUnless(HAS_PYSIDE, "PySide6 is not installed")
class TestSimulationTabCasingStatus(unittest.TestCase):
    def setUp(self):
        from tests import ensure_qapp

        ensure_qapp()

    def _tab(self, system):
        from tests import flush_qt

        parent = _Parent([])
        parent._current_assembly = system
        tab = SimulationTab(parent)
        self.addCleanup(
            lambda: (
                tab.close(),
                tab.deleteLater(),
                parent.close(),
                parent.deleteLater(),
                flush_qt(),
            )
        )
        return tab

    def test_status_reports_absorbed_count_and_fraction(self):
        system = _system()
        system.set_casing(_casing(bore=20.0, end=100.0))
        tab = self._tab(system)
        tab._sim_num_rays.setValue(9)
        tab._sim_angle.setValue(10.0)

        tab._on_run_simulation()

        text = tab._sim_casing_status.text()
        self.assertIn("of 9 rays absorbed", text)
        self.assertIn("%", text)

    def test_status_reports_thermal_interference(self):
        system = _system()
        system.set_casing(_casing(bore=20.0))
        system.casing.material = "Titanium"
        tab = self._tab(system)
        tab._sim_temperature.setValue(-60.0)

        tab._on_run_simulation()

        self.assertIn("interference", tab._sim_casing_status.text().lower())


if __name__ == "__main__":
    unittest.main()
