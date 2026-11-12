"""#643: the chromatic analyzer must use the same thermal model as the app.

It applied dn/dT to the index only. At 120 C the CTE expansion dominates the
index change, so the analyzer and the conditioned lens predicted defocus with
opposite signs.
"""

import math
import unittest

from openlens.analysis.environmental import EnvironmentalAnalyzer
from openlens.chromatic_analyzer import ChromaticAnalyzer
from openlens.lens import Lens

PARAMS = {
    "radius1": 50.0,
    "radius2": -50.0,
    "thickness": 5.0,
    "diameter": 25.0,
    "material": "BK7",
}


def _conditioned_focal_length(temperature_c: float):
    lens = Lens(
        radius_of_curvature_1=PARAMS["radius1"],
        radius_of_curvature_2=PARAMS["radius2"],
        thickness=PARAMS["thickness"],
        diameter=PARAMS["diameter"],
        material=PARAMS["material"],
    )
    return EnvironmentalAnalyzer.condition_at_temperature(
        lens, temperature_c
    ).calculate_focal_length()


class TestChromaticThermalGeometry(unittest.TestCase):
    def setUp(self):
        self.analyzer = ChromaticAnalyzer()

    def _analyzer_focal_length(self, temperature_c: float) -> float:
        return self.analyzer.analyze_lens(
            PARAMS, wavelengths=[587.6], temperature_c=temperature_c
        ).focal_lengths[0]

    def test_the_analyzer_matches_the_conditioned_lens_when_heated(self):
        """Both modules answer the same thermal question the same way."""
        for temperature_c in (60.0, 120.0):
            with self.subTest(temperature_c=temperature_c):
                self.assertAlmostEqual(
                    self._analyzer_focal_length(temperature_c),
                    _conditioned_focal_length(temperature_c),
                    places=6,
                )

    def test_expansion_makes_the_heated_focal_length_longer(self):
        """The CTE term must dominate the index term at high temperature."""
        self.assertGreater(
            self._analyzer_focal_length(120.0),
            self._analyzer_focal_length(20.0),
        )

    def test_lateral_color_uses_the_same_conditioned_geometry(self):
        result = self.analyzer.analyze_lens(
            PARAMS,
            wavelengths=[486.1, 587.6, 656.3],
            temperature_c=120.0,
        )

        self.assertEqual(len(result.focal_lengths), 3)
        self.assertTrue(all(f > 0.0 for f in result.focal_lengths))
        self.assertFalse(math.isnan(result.lateral_color))


if __name__ == "__main__":
    unittest.main()
