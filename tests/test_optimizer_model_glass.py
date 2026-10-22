#!/usr/bin/env python3
"""
An index or Abbe variable must not overwrite the other glass parameter.

The optimizer switched a lens to model-glass mode and wrote only the
parameter being optimised. The companion value kept the model default
(BK7's 1.5168 / 64.17), so optimising the index of an SF11 lens also changed
its Abbe number - and optimising the Abbe number changed its index. Applying
a variable at its own current value changed the lens.
"""

import unittest

from openlens.lens import Lens
from openlens.optical_system import OpticalSystem
from openlens.optimizer import LensOptimizer, OptimizationVariable


def _sf11_system():
    system = OpticalSystem("SF11")
    system.add_lens(
        Lens(
            name="SF11",
            radius_of_curvature_1=100.0,
            radius_of_curvature_2=-100.0,
            thickness=5.0,
            diameter=25.0,
            material="SF11",
            refractive_index=1.78472,
        )
    )
    return system


class TestModelGlassCompanionIsSeeded(unittest.TestCase):
    """The model glass must describe the glass the lens actually is."""

    def test_the_index_variable_keeps_the_abbe_number(self):
        """Optimising the index must not change the glass's dispersion"""
        system = _sf11_system()
        lens = system.elements[0].lens
        optimizer = LensOptimizer(
            system,
            [OptimizationVariable("N", 0, "refractive_index", lens.refractive_index, 1.3, 2.4)],
            [],
        )

        applied = optimizer._apply_variables([lens.refractive_index])
        result = applied.elements[0].lens

        self.assertTrue(result.model_glass_mode)
        self.assertAlmostEqual(result.model_nd, 1.78472, places=5)
        self.assertAlmostEqual(
            result.model_vd,
            25.68,
            places=2,
            msg="the Abbe number was replaced by the model default",
        )

    def test_the_abbe_variable_keeps_the_index(self):
        """Optimising the Abbe number must not change the index"""
        system = _sf11_system()
        optimizer = LensOptimizer(
            system,
            [OptimizationVariable("V", 0, "abbe_number", 25.68, 20.0, 80.0)],
            [],
        )

        applied = optimizer._apply_variables([25.68])
        result = applied.elements[0].lens

        self.assertAlmostEqual(
            result.model_nd,
            1.78472,
            places=5,
            msg="the index was replaced by the model default",
        )
        self.assertAlmostEqual(result.model_vd, 25.68, places=2)

    def test_applying_the_index_at_its_value_changes_nothing(self):
        """The lens must be the same before and after the edit"""
        system = _sf11_system()
        lens = system.elements[0].lens
        before_focal_length = system.get_system_focal_length()
        before_chromatic = system.calculate_chromatic_aberration()["longitudinal"]
        optimizer = LensOptimizer(
            system,
            [OptimizationVariable("N", 0, "refractive_index", lens.refractive_index, 1.3, 2.4)],
            [],
        )

        applied = optimizer._apply_variables([lens.refractive_index])

        # The model glass recomputes the index from nd/Vd, so the numbers
        # move in the last decimals - the glass itself must not change.
        self.assertAlmostEqual(applied.get_system_focal_length(), before_focal_length, delta=0.01)
        self.assertAlmostEqual(
            applied.calculate_chromatic_aberration()["longitudinal"],
            before_chromatic,
            delta=0.01,
        )


if __name__ == "__main__":
    unittest.main()
