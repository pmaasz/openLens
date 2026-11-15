"""Catalog-aware glass substitution: nearest search, snap and glass map."""

import os
import tempfile
import unittest

from openlens.glass_substitution import (
    GlassSubstituter,
    SubstitutionReport,
    find_nearest_glass,
    substitute_glasses,
)
from openlens.lens import Lens
from openlens.material_database import MaterialDatabase
from openlens.optical_system import OpticalSystem
from openlens.optimizer import OptimizationTarget

try:
    from matplotlib.figure import Figure

    MATPLOTLIB_AVAILABLE = True
except ImportError:  # pragma: no cover - environment guard
    MATPLOTLIB_AVAILABLE = False


class TestNearestGlass(unittest.TestCase):
    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        os.unlink(self.db_path)
        self.database = MaterialDatabase(db_path=self.db_path)

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    def test_exact_sf11_pair_returns_sf11(self):
        match = GlassSubstituter(self.database).nearest(1.78472, 25.68)

        self.assertEqual(match.material.name, "SF11")
        self.assertAlmostEqual(match.distance, 0.0, places=12)

    def test_exact_bk7_pair_is_deterministic(self):
        match = GlassSubstituter(self.database).nearest(1.5168, 64.17)

        self.assertEqual(match.material.name, "BK7")

    def test_a_near_pair_snaps_to_the_expected_glass(self):
        match = GlassSubstituter(self.database).nearest(1.780, 25.0)

        self.assertEqual(match.material.name, "SF11")

    def test_catalog_filter_excludes_other_vendors(self):
        match = GlassSubstituter(self.database, catalog="Ohara").nearest(1.780, 25.0)

        self.assertEqual(match.material.catalog, "Ohara")

    def test_invalid_weight_raises(self):
        with self.assertRaises(ValueError):
            GlassSubstituter(self.database, nd_weight=0)

    def test_invalid_pair_raises(self):
        with self.assertRaises(ValueError):
            GlassSubstituter(self.database).nearest(-1.5, 60.0)

    def test_free_function_returns_a_material(self):
        material = find_nearest_glass(1.5168, 64.17, database=self.database)

        self.assertIsNotNone(material)
        self.assertEqual(material.name, "BK7")


class TestSubstituteLens(unittest.TestCase):
    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        os.unlink(self.db_path)
        self.database = MaterialDatabase(db_path=self.db_path)

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    def test_a_model_glass_is_snapped_and_reported(self):
        lens = Lens(
            radius_of_curvature_1=100.0,
            radius_of_curvature_2=-100.0,
            material="Custom",
            model_glass_mode=True,
            model_nd=1.7847,
            model_vd=25.7,
        )

        report = GlassSubstituter(self.database).substitute_lens(lens)

        self.assertTrue(report.changed)
        self.assertEqual(lens.material, "SF11")
        self.assertEqual(lens.model_nd, 1.78472)
        self.assertEqual(lens.model_vd, 25.68)
        self.assertEqual(lens.refractive_index, 1.78472)
        self.assertFalse(lens.model_glass_mode)

    def test_a_catalog_lens_is_a_no_op(self):
        lens = Lens(material="BK7")

        report = GlassSubstituter(self.database).substitute_lens(lens)

        self.assertFalse(report.changed)
        self.assertEqual(lens.material, "BK7")
        self.assertEqual(lens.refractive_index, 1.5168)


class TestSubstituteSystem(unittest.TestCase):
    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        os.unlink(self.db_path)
        self.database = MaterialDatabase(db_path=self.db_path)

        self.system = OpticalSystem(name="Substitution")
        self.system.add_lens(
            Lens(
                name="Front",
                radius_of_curvature_1=50.0,
                radius_of_curvature_2=-50.0,
                thickness=5.0,
                diameter=20.0,
                material="Custom",
                model_glass_mode=True,
                model_nd=1.7847,
                model_vd=25.7,
            )
        )
        self.system.add_lens(
            Lens(
                name="Rear",
                radius_of_curvature_1=40.0,
                radius_of_curvature_2=-40.0,
                thickness=4.0,
                diameter=18.0,
                material="BK7",
            )
        )

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    def test_selected_element_only_is_snapped(self):
        report = GlassSubstituter(self.database).substitute_system(self.system, element_indices=[0])

        self.assertEqual(len(report.substitutions), 1)
        self.assertEqual(self.system.elements[0].lens.material, "SF11")
        self.assertEqual(self.system.elements[1].lens.material, "BK7")

    def test_merit_before_and_after_are_reported(self):
        targets = [OptimizationTarget("focal_length", 80.0, weight=1.0, target_type="target")]

        report = GlassSubstituter(self.database).substitute_system(self.system, targets=targets)

        self.assertIsNotNone(report.merit_before)
        self.assertIsNotNone(report.merit_after)
        self.assertIsNotNone(report.merit_change)
        self.assertIn("Merit change", report.format())

    def test_no_op_reports_no_change(self):
        system = OpticalSystem(name="Already Catalog")
        system.add_lens(Lens(material="BK7"))

        report = substitute_glasses(system, database=self.database)

        self.assertFalse(report.changed)
        self.assertIn("[unchanged]", report.format())

    def test_empty_report_formats(self):
        report = SubstitutionReport()

        self.assertIn("No lens elements", report.format())


@unittest.skipUnless(MATPLOTLIB_AVAILABLE, "matplotlib not available")
class TestGlassMap(unittest.TestCase):
    def test_map_marks_catalog_and_design_points(self):
        from openlens.analysis.plots import plot_glass_map

        system = OpticalSystem(name="Map")
        system.add_lens(Lens(material="BK7"))

        figure = Figure()
        ax = figure.add_subplot(111)
        catalog_count, design_count = plot_glass_map(ax, system)

        self.assertGreater(catalog_count, 0)
        self.assertEqual(design_count, 1)
        self.assertEqual(ax.get_xlabel(), "Abbe number Vd")
        self.assertEqual(ax.get_ylabel(), "Refractive index nd")


if __name__ == "__main__":
    unittest.main()
