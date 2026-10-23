#!/usr/bin/env python3
"""#657: flat surfaces have one accepted spelling end to end."""

import os
import tempfile
import unittest
from unittest import mock

from openlens.constants import FLAT_RADIUS
from openlens.lens import Lens
from openlens.lens_editor import LensManager
from openlens.optical_system import OpticalSystem
from openlens.validation import (
    ValidationError,
    validate_lens_parameters,
    validate_radius,
)


class TestFlatRadiusValidation(unittest.TestCase):
    def test_zero_is_rejected_by_default(self):
        with self.assertRaises(ValidationError):
            validate_radius(0.0)

    def test_allow_flat_accepts_zero_and_infinity_as_the_model_spelling(self):
        for value in (0, 0.0, float("inf")):
            with self.subTest(value=value):
                self.assertEqual(validate_radius(value, allow_flat=True), FLAT_RADIUS)

    def test_allow_flat_still_rejects_negative_infinity(self):
        with self.assertRaises(ValidationError):
            validate_radius(float("-inf"), allow_flat=True)

    def test_allow_flat_still_rejects_bool(self):
        with self.assertRaises(ValidationError):
            validate_radius(True, allow_flat=True)

    def test_validate_lens_parameters_accepts_a_plano_surface(self):
        result = validate_lens_parameters(
            radius1=float("inf"),
            radius2=-100.0,
            thickness=5.0,
            diameter=25.0,
            refractive_index=1.5168,
        )

        self.assertEqual(result["radius1"], FLAT_RADIUS)
        self.assertEqual(result["radius2"], -100.0)


class TestPlanoLensCli(unittest.TestCase):
    def setUp(self):
        handle, self.storage_file = tempfile.mkstemp(suffix=".json")
        os.close(handle)
        self.addCleanup(self._cleanup)
        self.manager = LensManager(storage_file=self.storage_file)

    def _cleanup(self):
        base = self.storage_file.replace(".json", ".db")
        for path in (base, base + "-shm", base + "-wal", self.storage_file):
            if os.path.exists(path):
                os.unlink(path)

    def test_create_accepts_zero_for_a_flat_surface(self):
        answers = ["Plano", "0", "-100", "5", "25", "1.5168", "Plano-Convex", "BK7"]
        with mock.patch("builtins.input", side_effect=answers):
            lens = self.manager.create_lens()

        self.assertIsInstance(lens, Lens)
        self.assertEqual(lens.radius_of_curvature_1, FLAT_RADIUS)
        self.assertEqual(lens.radius_of_curvature_2, -100.0)

    def test_modify_can_edit_a_surface_to_flat(self):
        lens = Lens(
            name="demo",
            radius_of_curvature_1=100.0,
            radius_of_curvature_2=-100.0,
            thickness=5.0,
            diameter=50.0,
            refractive_index=1.5168,
            material="BK7",
        )
        self.manager.lenses = [lens]

        answers = ["1", "", "", "0", "5", "50", "1.5168", "", ""]
        with mock.patch("builtins.input", side_effect=answers):
            with mock.patch.object(self.manager, "save_lenses") as save:
                self.manager.modify_lens()

        self.assertEqual(lens.radius_of_curvature_2, FLAT_RADIUS)
        save.assert_called_once()


class TestPlanoLensRoundTrip(unittest.TestCase):
    def test_a_plano_lens_survives_save_and_load(self):
        system = OpticalSystem(name="Plano system")
        system.add_lens(
            Lens(
                name="plano",
                radius_of_curvature_1=FLAT_RADIUS,
                radius_of_curvature_2=-100.0,
                thickness=5.0,
                diameter=25.0,
                refractive_index=1.5168,
                material="BK7",
            )
        )

        with tempfile.TemporaryDirectory() as temp:
            path = os.path.join(temp, "plano.json")
            self.assertTrue(system.save(path))
            loaded = OpticalSystem.load(path)

        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.elements[0].lens.radius_of_curvature_1, FLAT_RADIUS)
        self.assertEqual(loaded.elements[0].lens.radius_of_curvature_2, -100.0)


if __name__ == "__main__":
    unittest.main()
