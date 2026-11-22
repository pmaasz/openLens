import json
import os
import tempfile
import unittest

from openlens.database import DatabaseManager
from openlens.optical_system import OpticalSystem, create_doublet
from openlens.optimizer import LensOptimizer, OptimizationTarget, OptimizationVariable


class TestMultiConfig(unittest.TestCase):
    def _make_two_config(self):
        system = create_doublet(diameter=25.0)
        system.add_configuration("Config 2")
        system.set_active_config(1)
        system.air_gaps[0].thickness += 5.0
        system._sync_active_config_from_air_gaps()
        system.set_active_config(0)
        return system

    def test_switch_preserves_identity_and_changes_efl_bfl(self):
        system = self._make_two_config()
        ids_before = [id(e.lens) for e in system.elements]
        efl0 = system.get_system_focal_length()
        bfl0 = system.calculate_back_focal_length()

        system.set_active_config(1)
        ids_after = [id(e.lens) for e in system.elements]
        efl1 = system.get_system_focal_length()
        bfl1 = system.calculate_back_focal_length()

        self.assertEqual(ids_before, ids_after)
        self.assertIsNotNone(efl0)
        self.assertIsNotNone(efl1)
        self.assertNotAlmostEqual(efl0, efl1, places=3)
        self.assertNotAlmostEqual(bfl0, bfl1, places=3)

    def test_json_round_trip_preserves_configs(self):
        system = self._make_two_config()
        data = json.loads(json.dumps(system.to_dict()))
        loaded = OpticalSystem.from_dict(data)

        self.assertEqual(len(loaded.configurations), 2)
        self.assertEqual(loaded.active_config, 0)
        self.assertAlmostEqual(
            loaded.get_system_focal_length(), system.get_system_focal_length(), places=6
        )
        loaded.set_active_config(1)
        system.set_active_config(1)
        self.assertAlmostEqual(
            loaded.get_system_focal_length(), system.get_system_focal_length(), places=6
        )

    def test_db_round_trip_preserves_configs(self):
        system = self._make_two_config()
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "test.db")
            db = DatabaseManager(db_path)
            db.save_assembly(system.to_dict())
            loaded_data = [r for r in db.load_all() if r.get("id") == system.id][0]
            loaded = OpticalSystem.from_dict(loaded_data)

            self.assertEqual(len(loaded.configurations), 2)
            self.assertEqual(loaded.active_config, 0)
            efl0 = loaded.get_system_focal_length()
            loaded.set_active_config(1)
            efl1 = loaded.get_system_focal_length()
            system.set_active_config(0)
            self.assertAlmostEqual(efl0, system.get_system_focal_length(), places=6)
            system.set_active_config(1)
            self.assertAlmostEqual(efl1, system.get_system_focal_length(), places=6)

    def test_single_config_default_unchanged(self):
        system = create_doublet(diameter=25.0)
        self.assertEqual(len(system.configurations), 1)
        self.assertEqual(system.active_config, 0)
        data = system.to_dict()
        self.assertIn("configurations", data)
        self.assertEqual(data["active_config"], 0)
        loaded = OpticalSystem.from_dict(
            {"name": "Legacy", "elements": data["elements"], "air_gaps": data["air_gaps"]}
        )
        self.assertEqual(len(loaded.configurations), 1)
        self.assertEqual(loaded.active_config, 0)

    def test_optimizer_merit_summed_over_selected_configs(self):
        system = self._make_two_config()
        vars_ = [
            OptimizationVariable(
                name="r1",
                element_index=0,
                parameter="radius_of_curvature_1",
                current_value=system.elements[0].lens.radius_of_curvature_1,
                min_value=10.0,
                max_value=500.0,
            )
        ]
        targets = [
            OptimizationTarget(
                name="system_length", target_value=0.0, weight=1.0, target_type="minimize"
            )
        ]
        opt_single = LensOptimizer(system, vars_, targets, config_indices=[0])
        opt_multi = LensOptimizer(system, vars_, targets, config_indices=[0, 1])
        v = [vars_[0].current_value]
        m0 = opt_single._evaluate_design(v)
        m01 = opt_multi._evaluate_design(v)
        self.assertGreater(m01, m0)

    def test_spot_and_mtf_change_with_config(self):
        try:
            import numpy  # noqa: F401
        except ImportError:
            self.skipTest("numpy not available")
        from openlens.analysis.spot_diagram import SpotDiagram

        system = self._make_two_config()
        spot = SpotDiagram(system)
        s0 = spot.trace_spot(
            field_angle_x_deg=0.0, field_angle_y_deg=0.0, wavelength_nm=587.6, num_rings=3
        )
        system.set_active_config(1)
        s1 = spot.trace_spot(
            field_angle_x_deg=0.0, field_angle_y_deg=0.0, wavelength_nm=587.6, num_rings=3
        )
        self.assertNotAlmostEqual(s0["rms_radius"], s1["rms_radius"], places=6)

        system.set_active_config(0)
        from openlens.analysis.psf_mtf import ImageQualityAnalyzer

        mtf0 = ImageQualityAnalyzer(system).calculate_mtf(field_angle_deg=0.0, wavelength_nm=587.6)
        system.set_active_config(1)
        mtf1 = ImageQualityAnalyzer(system).calculate_mtf(field_angle_deg=0.0, wavelength_nm=587.6)
        self.assertFalse(all(abs(a - b) < 1e-9 for a, b in zip(mtf0["mtf_tan"], mtf1["mtf_tan"])))


if __name__ == "__main__":
    unittest.main()
