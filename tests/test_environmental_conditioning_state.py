#!/usr/bin/env python3
"""Thermal conditioning must be idempotent and reversible.

``condition_at_temperature`` used ``Lens.temperature`` - the temperature at
which the *index* was last resolved - as the marker for "the geometry has
already been thermally expanded". Those are different states:

* ``Lens.for_material(..., temperature=120)`` has a 120 C index on 20 C
  geometry, so conditioning it to 120 C skipped the expansion;
* a custom glass never refreshed the field, so the same conditioning applied
  the CTE expansion a second time;
* an expanded copy could never be brought back to 20 C.

The geometry's thermal state is now tracked separately.
"""

import unittest

from openlens.analysis.environmental import EnvironmentalAnalyzer
from openlens.lens import Lens
from openlens.optical_system import OpticalSystem

SHAPE = dict(
    radius_of_curvature_1=100.0,
    radius_of_curvature_2=-100.0,
    thickness=5.0,
    diameter=40.0,
)


class TestThermalConditioningState(unittest.TestCase):
    def test_a_lens_built_at_the_target_temperature_is_expanded(self):
        """A 120 C index on 20 C geometry still needs the CTE expansion."""
        built_hot = Lens.for_material("BK7", 587.6, 120.0, **SHAPE)
        reference = EnvironmentalAnalyzer.condition_at_temperature(
            Lens(material="BK7", **SHAPE), 120.0
        )

        conditioned = EnvironmentalAnalyzer.condition_at_temperature(built_hot, 120.0)

        self.assertIsNot(conditioned, built_hot)
        self.assertGreater(conditioned.radius_of_curvature_1, 100.0)
        self.assertAlmostEqual(
            conditioned.radius_of_curvature_1,
            reference.radius_of_curvature_1,
            places=9,
        )
        self.assertAlmostEqual(conditioned.thickness, reference.thickness, places=9)

    def test_conditioning_twice_gives_the_same_geometry(self):
        system = OpticalSystem("custom")
        system.add_lens(Lens(material="Custom", refractive_index=1.7, **SHAPE))

        once = EnvironmentalAnalyzer.condition_at_temperature(system, 120.0)
        twice = EnvironmentalAnalyzer.condition_at_temperature(once, 120.0)

        self.assertIs(twice, once)
        self.assertGreater(once.elements[0].lens.radius_of_curvature_1, 100.0)
        self.assertAlmostEqual(
            twice.elements[0].lens.radius_of_curvature_1,
            once.elements[0].lens.radius_of_curvature_1,
            places=12,
        )

    def test_conditioning_back_restores_the_reference_geometry(self):
        hot = EnvironmentalAnalyzer.condition_at_temperature(Lens(material="BK7", **SHAPE), 120.0)

        back = EnvironmentalAnalyzer.condition_at_temperature(hot, 20.0)

        self.assertAlmostEqual(back.radius_of_curvature_1, 100.0, places=9)
        self.assertAlmostEqual(back.radius_of_curvature_2, -100.0, places=9)
        self.assertAlmostEqual(back.thickness, 5.0, places=9)
        self.assertAlmostEqual(back.temperature, 20.0, places=9)

    def test_custom_glass_updates_its_temperature_field(self):
        system = OpticalSystem("custom")
        system.add_lens(Lens(material="Custom", refractive_index=1.7, **SHAPE))

        hot = EnvironmentalAnalyzer.condition_at_temperature(system, 120.0)

        lens = hot.elements[0].lens
        self.assertAlmostEqual(lens.temperature, 120.0)
        self.assertAlmostEqual(lens.thermal_state_temperature, 120.0)
        # No catalog model for this glass: the index itself is unchanged.
        self.assertAlmostEqual(lens.refractive_index, 1.7)

    def test_conditioning_back_restores_the_air_gaps(self):
        system = OpticalSystem("pair")
        system.add_lens(Lens(material="BK7", **SHAPE))
        system.add_lens(Lens(material="BK7", **SHAPE), air_gap_before=10.0)

        hot = EnvironmentalAnalyzer.condition_at_temperature(system, 120.0)
        self.assertGreater(hot.air_gaps[0].thickness, 10.0)
        back = EnvironmentalAnalyzer.condition_at_temperature(hot, 20.0)

        self.assertAlmostEqual(back.air_gaps[0].thickness, 10.0, places=9)

    def test_the_thermal_state_survives_serialization(self):
        hot = EnvironmentalAnalyzer.condition_at_temperature(Lens(material="BK7", **SHAPE), 120.0)
        rebuilt = Lens.from_dict(hot.to_dict())

        self.assertAlmostEqual(rebuilt.thermal_state_temperature, 120.0)
        self.assertAlmostEqual(rebuilt.radius_of_curvature_1, hot.radius_of_curvature_1, places=9)

        system = OpticalSystem("pair")
        system.add_lens(Lens(material="BK7", **SHAPE))
        system.add_lens(Lens(material="BK7", **SHAPE), air_gap_before=10.0)
        hot_system = EnvironmentalAnalyzer.condition_at_temperature(system, 120.0)
        rebuilt_system = OpticalSystem.from_dict(hot_system.to_dict())

        self.assertAlmostEqual(rebuilt_system.thermal_state_temperature, 120.0)
        self.assertAlmostEqual(
            rebuilt_system.air_gaps[0].thickness,
            hot_system.air_gaps[0].thickness,
            places=9,
        )

    def test_reference_conditions_still_return_the_original(self):
        lens = Lens(material="BK7", **SHAPE)

        self.assertIs(EnvironmentalAnalyzer.condition_at_temperature(lens, 20.0), lens)


if __name__ == "__main__":
    unittest.main()
