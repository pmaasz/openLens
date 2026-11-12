"""Focal-plane selection for spot-based analyses and optimization.

A lens or system may name its detector plane (``image_plane_x_mm``). When it
does, spot-based analyses must measure there instead of at the paraxial
focus; when it does not, the paraxial focus remains the default.
"""

import math
import os
import tempfile
import unittest

from openlens.aberrations import AberrationsCalculator
from openlens.analysis.paraxial import find_paraxial_focus
from openlens.analysis.spot_diagram import SpotDiagram
from openlens.lens import Lens
from openlens.optical_system import OpticalSystem, as_system
from openlens.optimizer import MeritFunction, OptimizationTarget


def _lens(**kwargs):
    options = dict(
        name="Focal plane lens",
        radius_of_curvature_1=50.0,
        radius_of_curvature_2=-50.0,
        thickness=5.0,
        diameter=25.0,
        refractive_index=1.5168,
    )
    options.update(kwargs)
    return Lens(**options)


def _system(**kwargs):
    system = OpticalSystem(name="Focal plane system")
    system.add_lens(_lens(**kwargs))
    return system


class TestModelCarriesTheFocalPlane(unittest.TestCase):
    def test_a_lens_defaults_to_auto(self):
        self.assertIsNone(_lens().image_plane_x_mm)

    def test_a_lens_round_trips_its_focal_plane(self):
        lens = _lens(image_plane_x_mm=123.456)

        clone = Lens.from_dict(lens.to_dict())

        self.assertEqual(clone.image_plane_x_mm, 123.456)
        self.assertNotIn("image_plane_x_mm", clone.metadata)

    def test_a_lens_rejects_a_non_finite_focal_plane(self):
        for value in (math.inf, -math.inf, math.nan):
            with self.assertRaises(ValueError):
                _lens(image_plane_x_mm=value)

    def test_a_system_round_trips_its_focal_plane(self):
        system = _system()
        system.image_plane_x_mm = 88.5

        clone = OpticalSystem.from_dict(system.to_dict())

        self.assertEqual(clone.image_plane_x_mm, 88.5)
        self.assertNotIn("image_plane_x_mm", clone.metadata)

    def test_wrapping_a_lens_carries_the_plane(self):
        lens = _lens(image_plane_x_mm=77.0)

        self.assertEqual(as_system(lens).image_plane_x_mm, 77.0)

    def test_a_copied_wrapper_carries_the_plane(self):
        lens = _lens(image_plane_x_mm=77.0)

        self.assertEqual(as_system(lens, copy_system=True).image_plane_x_mm, 77.0)

    def test_a_database_round_trip_keeps_the_plane(self):
        from openlens.database import DatabaseManager
        from openlens.gui.storage import LensStorage

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "lenses.db")
            DatabaseManager(path).save_lens(_lens(image_plane_x_mm=42.0).to_dict())

            loaded = LensStorage(path).load_lenses()

        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0].image_plane_x_mm, 42.0)

    def test_an_assembly_database_round_trip_keeps_the_plane(self):
        from openlens.database import DatabaseManager

        system = _system()
        system.image_plane_x_mm = 55.5

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "assemblies.db")
            db = DatabaseManager(path)
            db.save_assembly(system.to_dict())

            rows = db.load_all()

        assemblies = [row for row in rows if row.get("type") == "OpticalSystem"]
        self.assertEqual(len(assemblies), 1)
        clone = OpticalSystem.from_dict(assemblies[0])
        self.assertEqual(clone.image_plane_x_mm, 55.5)


class TestSpotDiagramUsesTheFocalPlane(unittest.TestCase):
    def setUp(self):
        self.system = _system()
        self.focus = find_paraxial_focus(self.system)
        self.assertIsNotNone(self.focus)

    def test_no_plane_uses_the_paraxial_focus(self):
        result = SpotDiagram(self.system).trace_spot(num_rings=2)

        self.assertAlmostEqual(result["image_plane_x"], self.focus, places=6)

    def test_a_configured_plane_is_used(self):
        plane = self.focus + 5.0
        self.system.image_plane_x_mm = plane

        result = SpotDiagram(self.system).trace_spot(num_rings=2)

        self.assertAlmostEqual(result["image_plane_x"], plane, places=6)

    def test_a_defocused_plane_has_a_larger_spot(self):
        at_focus = SpotDiagram(self.system).trace_spot(num_rings=2)["rms_radius"]
        self.system.image_plane_x_mm = self.focus + 5.0
        defocused = SpotDiagram(self.system).trace_spot(num_rings=2)["rms_radius"]

        self.assertIsNotNone(at_focus)
        self.assertIsNotNone(defocused)
        self.assertGreater(defocused, at_focus)

    def test_a_configured_plane_moves_the_chief_ray_hit(self):
        at_focus = SpotDiagram(self.system).trace_chief_ray(field_angle_y_deg=5.0)
        self.system.image_plane_x_mm = self.focus + 5.0
        at_plane = SpotDiagram(self.system).trace_chief_ray(field_angle_y_deg=5.0)

        self.assertIsNotNone(at_focus)
        self.assertIsNotNone(at_plane)
        self.assertNotEqual(at_focus, at_plane)

    def test_a_non_finite_plane_falls_back_to_the_paraxial_focus(self):
        self.system.image_plane_x_mm = math.inf

        result = SpotDiagram(self.system).trace_spot(num_rings=2)

        self.assertAlmostEqual(result["image_plane_x"], self.focus, places=6)


class TestAberrationSpotUsesTheFocalPlane(unittest.TestCase):
    def test_the_spot_rms_is_measured_at_the_configured_plane(self):
        system = _system()
        at_focus = AberrationsCalculator(system)._calculate_spot_rms()
        system.image_plane_x_mm = find_paraxial_focus(system) + 5.0

        defocused = AberrationsCalculator(system)._calculate_spot_rms()

        self.assertIsNotNone(at_focus)
        self.assertIsNotNone(defocused)
        self.assertGreater(defocused, at_focus)


class TestMeritUsesTheFocalPlane(unittest.TestCase):
    @staticmethod
    def _merit(system):
        return MeritFunction(
            system,
            [OptimizationTarget("rms_spot_radius", 0.0, target_type="minimize")],
        ).evaluate(system)

    def test_a_defocused_plane_has_a_larger_merit(self):
        system = _system()
        at_focus = self._merit(system)
        system.image_plane_x_mm = find_paraxial_focus(system) + 5.0

        defocused = self._merit(system)

        self.assertGreater(defocused, at_focus)


if __name__ == "__main__":
    unittest.main()
