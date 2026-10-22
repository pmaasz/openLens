#!/usr/bin/env python3
"""Pressure conditioning must survive the ray-traced analyses.

``EnvironmentalAnalyzer.apply_environment`` folds the ambient-pressure air
correction into ``lens.refractive_index``. Every traced analysis then calls
``Lens.update_refractive_index(wavelength_nm=...)``, which recomputed the
catalog index at the reference pressure and overwrote the conditioned value.
A system at 2 atm therefore traced bit-identically to one at 1 atm, while the
paraxial numbers saw the corrected index.
"""

import unittest

from openlens.analysis.environmental import EnvironmentalAnalyzer
from openlens.analysis.spot_diagram import SpotDiagram
from openlens.lens import Lens
from openlens.material_database import get_material_database
from openlens.optical_system import OpticalSystem

TRACE_WAVELENGTH_NM = 550.0


def _system():
    system = OpticalSystem("Pressure test")
    system.add_lens(
        Lens(
            radius_of_curvature_1=50.0,
            radius_of_curvature_2=-50.0,
            thickness=5.0,
            diameter=25.0,
            material="BK7",
            refractive_index=1.5168,
        )
    )
    return system


def _expected_conditioned_index(lens, wavelength_nm):
    """Catalog index at the wavelength, scaled from 1 atm to the lens pressure."""
    catalog = get_material_database().get_refractive_index(
        lens.material, wavelength_nm, lens.temperature
    )
    n_air_ref = EnvironmentalAnalyzer.calculate_air_index(
        wavelength_nm, lens.temperature, EnvironmentalAnalyzer.REF_PRESSURE
    )
    n_air_new = EnvironmentalAnalyzer.calculate_air_index(
        wavelength_nm, lens.temperature, lens.pressure_atm
    )
    return catalog * (n_air_ref / n_air_new)


class TestPressureSurvivesTracedAnalysis(unittest.TestCase):
    def test_a_conditioned_system_traces_to_a_different_focus(self):
        nominal = _system()
        conditioned = EnvironmentalAnalyzer.apply_environment(nominal, 20.0, 2.0)

        nominal_focus = SpotDiagram(nominal).trace_spot(wavelength_nm=TRACE_WAVELENGTH_NM)[
            "image_plane_x"
        ]
        conditioned_focus = SpotDiagram(conditioned).trace_spot(wavelength_nm=TRACE_WAVELENGTH_NM)[
            "image_plane_x"
        ]

        # 2 atm of air lowers the relative glass index by ~2.7e-4; on a
        # ~300 mm focus that is a shift of a few tenths of a millimetre, far
        # above a micron. Before the fix the two traces were identical.
        self.assertGreater(abs(nominal_focus - conditioned_focus), 1e-3)

    def test_the_conditioned_index_survives_a_wavelength_update(self):
        conditioned = EnvironmentalAnalyzer.apply_environment(_system(), 20.0, 2.0)
        lens = conditioned.elements[0].lens
        conditioned_index = lens.refractive_index

        lens.update_refractive_index(wavelength_nm=lens.wavelength)

        self.assertAlmostEqual(lens.refractive_index, conditioned_index, places=12)

    def test_reindexing_matches_the_pressure_formula(self):
        conditioned = EnvironmentalAnalyzer.apply_environment(_system(), 20.0, 2.0)
        lens = conditioned.elements[0].lens

        lens.update_refractive_index(wavelength_nm=TRACE_WAVELENGTH_NM)

        self.assertAlmostEqual(
            lens.refractive_index,
            _expected_conditioned_index(lens, TRACE_WAVELENGTH_NM),
            places=12,
        )

    def test_the_conditioned_lens_records_its_pressure(self):
        nominal = _system()
        conditioned = EnvironmentalAnalyzer.apply_environment(nominal, 20.0, 2.0)

        self.assertAlmostEqual(nominal.elements[0].lens.pressure_atm, 1.0)
        self.assertAlmostEqual(conditioned.elements[0].lens.pressure_atm, 2.0)

    def test_the_original_system_is_not_conditioned(self):
        nominal = _system()
        nominal_index = nominal.elements[0].lens.refractive_index

        EnvironmentalAnalyzer.apply_environment(nominal, 20.0, 2.0)

        self.assertAlmostEqual(nominal.elements[0].lens.refractive_index, nominal_index)
        self.assertAlmostEqual(nominal.elements[0].lens.pressure_atm, 1.0)

    def test_pressure_round_trips_through_serialization(self):
        conditioned = EnvironmentalAnalyzer.apply_environment(_system(), 20.0, 2.0)
        lens = conditioned.elements[0].lens

        rebuilt = Lens.from_dict(lens.to_dict())

        self.assertAlmostEqual(rebuilt.pressure_atm, 2.0)
        self.assertAlmostEqual(rebuilt.refractive_index, lens.refractive_index)


if __name__ == "__main__":
    unittest.main()
